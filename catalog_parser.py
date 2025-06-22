import asyncio
import random
import time
import httpx

from bs4 import BeautifulSoup

from client_manager import ClientManager
from page_task import PageTask
from page_data import PageData
from parse_request import ParseRequest
from log_manager import log_manager


class CatalogParser:
    """Парсер для обработки страниц каталога на сайте Rusneb."""

    def __init__(
        self,
        request: ParseRequest,
        client_manager: ClientManager,
        page_data: PageData,
        num_workers: int = 5,
        chunk_size: int = 10,
        max_retries: int = 3,
    ):
        """
        Инициализация парсера каталога.

        Args:
            request (ParseRequest): Запрос на парсинг.
            client_manager (ClientManager): Менеджер HTTP-клиентов.
            page_data (PageData): Данные о страницах.
            num_workers (int): Количество воркеров.
            chunk_size (int): Размер чанка.
            max_retries (int): Максимальное количество попыток.
        """

        self.request = request
        self.client_manager = client_manager
        self.num_workers = num_workers
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.page_data = page_data

        self.next_page = 0
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.logger = log_manager.get_logger(__name__)
        self.start_time = time.time_ns()

    async def run(self) -> None:
        """Запуск процесса парсинга каталога."""

        self.start_time = time.time_ns()

        self.logger.info(
            f"Запуск парсинга каталога {self.request.query} с {self.num_workers} воркерами"
        )

        workers = [asyncio.create_task(self.worker(i)) for i in range(self.num_workers)]
        pending = set(workers)

        try:
            done, pending = await asyncio.wait(
                workers, return_when=asyncio.ALL_COMPLETED
            )

        except asyncio.CancelledError:
            self.logger.warning("Парсинг отменен пользователем, завершаем работу...")
            async with self.page_data.protected_access() as data:
                data.has_error = True
        except Exception as e:
            self.logger.exception(f"Ошибка при выполнении парсинга: {e}", exc_info=True)
            async with self.page_data.protected_access() as data:
                data.has_error = True

        finally:
            if not self.stop_event.is_set():
                self.stop_event.set()
                self.logger.info("Ожидание завершения всех воркеров...")
            for worker in pending:
                if not worker.done():
                    worker.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

            total_time = time.time_ns() - self.start_time
            self.logger.info(
                f"Парсинг завершен за {total_time / 1_000_000_000:.2f} секунд"
            )

            async with self.page_data.protected_access() as data:
                self.logger.info(f"Обработано страниц: {len(data.processed_pages)}")

    async def worker(self, worker_id: int) -> None:
        """
        Воркеры для параллельной обработки страниц каталога.

        Args:
            worker_id (int): Идентификатор воркера.
        """

        self.logger.info(f"Запущен воркер {worker_id} для обработки страниц каталога")

        client = await self.client_manager.pop_client()

        async with client:
            while not self.stop_event.is_set():
                tasks = await self._get_next_tasks(worker_id, self.chunk_size)
                if not tasks:
                    async with self.page_data.protected_access() as data:
                        if data.no_more_pages and not data.pending_tasks:
                            self.logger.warning(
                                f"Воркер {worker_id} завершается: задачи закончились"
                            )
                            break
                        else:
                            await asyncio.sleep(0.5)
                            continue

                for task in tasks:
                    if self.stop_event.is_set():
                        break
                    await self._process_page(task, client)
                    if task.no_more_pages:
                        break
                    await asyncio.sleep(random.uniform(0.5, 2.0))

    async def _get_next_tasks(self, worker_id: int, count: int) -> list[PageTask]:
        """
        Получение следующего набора задач для воркера.
        Args:
            worker_id (int): Идентификатор воркера.
            count (int): Количество задач для получения.

            Returns:
                list[PageTask]: Список задач для обработки.
        """

        tasks = []

        async with self.page_data.protected_access() as data:
            while len(tasks) < count and data.pending_tasks:
                task = data.pending_tasks.popleft()
                task.worker_id = worker_id
                tasks.append(task)

            if len(tasks) < count and not data.no_more_pages:
                async with self.lock:
                    start_page = self.next_page + 1
                    end_page = start_page + (count - len(tasks))

                    for page in range(start_page, end_page):
                        if page not in data.processed_pages:
                            tasks.append(
                                PageTask(
                                    request=self.request,
                                    worker_id=worker_id,
                                    page_number=page,
                                )
                            )
                    self.next_page = end_page - 1

        return tasks

    async def _process_page(self, task: PageTask, client: httpx.AsyncClient) -> None:
        """
        Обработка страницы каталога.

        Args:
            task (PageTask): Задача на обработку страницы.
            client (httpx.AsyncClient): HTTP-клиент для выполнения запросов.
        """

        async with self.page_data.protected_access() as data:
            if task.page_number in data.processed_pages:
                task.processed = True
                return

            url = (
                f"https://rusneb.ru/search/?q={task.request.query}&PAGEN_1={task.page_number}"
                if task.request.is_search
                else f"https://rusneb.ru/catalog/{task.request.query}/?volumes=page-{task.page_number}"
            )

        self.logger.info(
            f"Воркер {task.worker_id} обрабатывает страницу {task.page_number}: {url}"
        )

        try:
            response = await client.get(url)
            if response.status_code != 200:
                self.logger.warning(
                    f"Ошибка при запросе страницы {task.page_number}: статус {response.status_code}"
                )
                task.attempt_count += 1
                task.last_error = Exception(f"HTTP error {response.status_code}")
                if task.attempt_count < self.max_retries:
                    async with self.page_data.protected_access() as data:
                        data.pending_tasks.append(task)
                return

        except httpx.ReadError:
            self.logger.warning(f"Ошибка чтения ответа для страницы {task.page_number}")
            task.attempt_count += 1
            task.last_error = Exception("Read error")
            if task.attempt_count < self.max_retries:
                async with self.page_data.protected_access() as data:
                    data.pending_tasks.append(task)
            return
        except httpx.TimeoutException:
            self.logger.warning(f"Таймаут при запросе страницы {task.page_number}")
            task.attempt_count += 1
            task.last_error = Exception("Timeout")
            if task.attempt_count < self.max_retries:
                async with self.page_data.protected_access() as data:
                    data.pending_tasks.append(task)
            return
        except Exception as e:
            if not e:
                self.logger.warning(f"Таймаут при запросе страницы {task.page_number}")
                return
            self.logger.exception(
                f"Исключение при обработке страницы {task.page_number}: {e}",
                exc_info=True,
            )
            task.attempt_count += 1
            task.last_error = e
            if task.attempt_count < self.max_retries:
                async with self.page_data.protected_access() as data:
                    data.pending_tasks.append(task)
            return

        html_content = response.text
        items = (
            self._parse_search_page(html_content)
            if self.request.is_search
            else self._parse_catalog_page(html_content)
        )
        if not items:
            self.logger.warning(f"Страница {task.page_number}: не найдено элементов")
            async with self.page_data.protected_access() as data:
                if task.page_number > data.max_page_found:
                    data.no_more_pages = True
                    self.logger.warning(
                        f"Похоже, достигнут конец каталога на странице {task.page_number-1}"
                    )
            task.no_more_pages = True
            return

        async with self.page_data.protected_access() as data:
            new_items = [
                item
                for item in items
                if item not in data.download_queue and item not in data.downloaded
            ]
            data.download_queue.extend(new_items)
            task.items = new_items

            data.max_page_found = max(data.max_page_found, task.page_number)
            data.processed_pages.add(task.page_number)

        task.processed = True
        self.logger.info(
            f"Страница {task.page_number}: найдено {len(items)} элементов, {len(new_items)} новых"
        )

    @staticmethod
    def _parse_catalog_page(html_content: str) -> list[str]:
        """
        Парсинг страницы каталога.

        Args:
            html_content (str): HTML-контент страницы каталога.

        Returns:
            list[str]: Список идентификаторов элементов на странице.
        """

        soup = BeautifulSoup(html_content, "html.parser")
        items = []
        for card in soup.select(".cards-results__item"):
            link = card.select_one("a.cards-results__link")
            if link:
                href = link.get("href", "")
                if href and "/catalog/" in href:
                    href = href.split("/catalog/")[1]
                    items.append(href)
        return items

    @staticmethod
    def _parse_search_page(html_content: str) -> list[str]:
        """
        Парсинг страницы результатов поиска.

        Args:
            html_content (str): HTML-контент страницы результатов поиска.

        Returns:
            list[str]: Список идентификаторов элементов на странице.
        """

        soup = BeautifulSoup(html_content, "html.parser")
        items = []
        for card in soup.select(".search-list__item"):
            link = card.select_one("a.search-list__item_link")
            if link:
                href = link.get("href", "")
                if href and "/catalog/" in href:
                    href = href.split("/catalog/")[1].split("/")[0]
                    items.append(href)
        return items


async def test() -> None:
    try:
        # request = ParseRequest("000200_000018_RU_NLR_DRGNLR_3107")
        request = ParseRequest("Петроградская газета 1911", is_search=True)

        client_manager = ClientManager(
            # proxy_file=Path(__file__).parent / "proxies.txt"
        )
        await client_manager.setup()

        page_data = PageData(request)
        await page_data.load_progress()

        parser = CatalogParser(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=3,
            chunk_size=10,
        )

        results = await parser.run()

        if results:
            print("\nПримеры найденных элементов:")
            for i, item in enumerate(list(results)[:5], 1):
                print(f"  {i}. {item}")
    finally:
        await page_data.save_progress()


if __name__ == "__main__":
    asyncio.run(test())
