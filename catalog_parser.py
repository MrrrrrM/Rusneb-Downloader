import asyncio
import os
import random
import time
import httpx

from bs4 import BeautifulSoup
from client_manager import ClientManager
from file_manager import FileManager
from page_task import PageTask
from page_data import PageData


class AsyncCatalogParser:
    def __init__(
        self,
        catalog_id: str,
        client_manager: ClientManager,
        num_workers: int = 5,
        chunk_size: int = 10,
        max_retries: int = 3,
        save_file: str = None,
    ):
        self.catalog_id = catalog_id
        self.client_manager = client_manager
        self.num_workers = num_workers
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.save_file = save_file or f"catalog_progress_{catalog_id}.json"

        self.page_data = PageData(catalog_id=self.catalog_id, page_number=1)

        self.stop_event = asyncio.Event()
        self.start_time = time.time()
        self.last_save_time = 0.0

    async def run(self) -> list[str]:
        self.start_time = time.time()

        await self._load_progress()

        try:
            print(
                f"Запуск парсинга каталога {self.catalog_id} с {self.num_workers} воркерами"
            )

            workers = [
                asyncio.create_task(self.worker(i)) for i in range(self.num_workers)
            ]

            done, pending = await asyncio.wait(
                workers, return_when=asyncio.FIRST_COMPLETED
            )

            while pending:
                if self.stop_event.is_set():
                    for task in pending:
                        task.cancel()
                    break

                done, pending = await asyncio.wait(
                    pending, timeout=0.5, return_when=asyncio.FIRST_COMPLETED
                )

            await self.save_progress()

            total_time = time.time() - self.start_time
            print(f"Парсинг завершен за {total_time:.2f} секунд ✅")

            async with self.page_data.protected_access() as data:
                print(f"Обработано {len(data.processed_pages)} страниц")
                print(f"Найдено {len(data.all_items)} элементов")
                return list(data.all_items)

        except Exception as e:
            print(f"Ошибка при выполнении парсинга: {e} ❌")
            async with self.page_data.protected_access() as data:
                data.has_error = True
            await self.save_progress()

            async with self.page_data.protected_access() as data:
                return list(data.all_items)

    async def worker(self, worker_id: int) -> None:
        print(f"Запущен воркер {worker_id}")

        client = await self.client_manager.pop_client()

        async with client:
            while not self.stop_event.is_set():
                tasks = await self._get_next_tasks(worker_id, self.chunk_size)

                if not tasks:
                    async with self.page_data.protected_access() as data:
                        if data.no_more_pages and not data.pending_tasks:
                            print(
                                f"Воркер {worker_id} завершается: задачи закончились ⚠️"
                            )
                            break
                        else:
                            await asyncio.sleep(0.5)
                            continue

                for task in tasks:
                    if self.stop_event.is_set():
                        break
                    await self._process_page(task, client)
                    await asyncio.sleep(random.uniform(0.5, 2))

    async def save_progress(self) -> None:
        current_time = time.time()
        if current_time - self.last_save_time < 10.0:
            return

        file_manager = FileManager.get_instance()
        self.last_save_time = current_time

        async with self.page_data.protected_access() as data:
            if os.path.exists(self.save_file):
                try:
                    saved_data = file_manager.read_json(self.save_file)
                    saved_data["timestamp"] = current_time
                    saved_data["max_page_found"] = data.max_page_found
                    saved_data["processed_pages"] = list(data.processed_pages)
                    saved_data["download_queue"].extend(data.download_queue)
                    data.download_queue.clear()
                except Exception as e:
                    print(f"Ошибка при чтении файла прогресса: {e}")
                    return
            else:
                saved_data = {
                    "timestamp": current_time,
                    "catalog_id": self.catalog_id,
                    "max_page_found": data.max_page_found,
                    "processed_pages": list(data.processed_pages),
                    "download_queue": list(data.download_queue),
                }
                data.download_queue.clear()

            try:
                file_manager.write_json(self.save_file, saved_data)

                print(
                    f"Прогресс сохранен: {len(data.all_items)} уникальных элементов, "
                    f"{len(data.processed_pages)} страниц обработано ❗"
                )
            except Exception as e:
                print(f"Ошибка при сохранении прогресса: {e} ❌")
                return

    async def _load_progress(self) -> None:
        if not os.path.exists(self.save_file):
            return

        file_manager = FileManager.get_instance()

        try:
            file_data = file_manager.read_json(self.save_file)

            async with self.page_data.protected_access() as data:
                data.max_page_found = file_data.get("max_page_found", 0)
                data.processed_pages = set(file_data.get("processed_pages", []))

                for page in range(1, data.max_page_found + 1):
                    if page not in data.processed_pages:
                        data.pending_tasks.append(
                            PageTask(catalog_id=self.catalog_id, page_number=page)
                        )

                print(
                    f"Загружен прогресс: обработано {len(data.processed_pages)} страниц, "
                    f"в очереди {len(data.pending_tasks)} страниц для дообработки"
                )
        except Exception as e:
            print(f"Ошибка при загрузке прогресса: {e} ❌")

    async def _get_next_tasks(self, worker_id: int, count: int) -> list[PageTask]:
        tasks = []

        async with self.page_data.protected_access() as data:
            while len(tasks) < count and data.pending_tasks:
                task = data.pending_tasks.popleft()
                task.worker_id = worker_id
                tasks.append(task)

            if len(tasks) < count and not data.no_more_pages:
                start_page = data.max_page_found + 1
                end_page = start_page + (count - len(tasks))

                for page in range(start_page, end_page):
                    if page not in data.processed_pages:
                        tasks.append(
                            PageTask(
                                catalog_id=self.catalog_id,
                                worker_id=worker_id,
                                page_number=page,
                            )
                        )
                data.max_page_found = end_page - 1

        return tasks

    async def _process_page(self, task: PageTask, client: httpx.AsyncClient) -> None:
        async with self.page_data.protected_access() as data:
            if task.page_number in data.processed_pages:
                task.processed = True
                return

        url = f"https://rusneb.ru/catalog/{task.catalog_id}/?volumes=page-{task.page_number}"

        print(
            f"Воркер {task.worker_id} обрабатывает страницу {task.page_number}: {url}"
        )

        try:
            response = await client.get(url)

            if response.status_code == 200:
                html_content = response.text
                items = self._parse_catalog_page(html_content)

                if items:
                    async with self.page_data.protected_access() as data:
                        new_items = [
                            item for item in items if item not in data.all_items
                        ]
                        data.all_items.update(new_items)
                        data.download_queue.update(new_items)
                        task.items = new_items

                        if task.page_number > data.max_page_found:
                            data.max_page_found = task.page_number

                        data.processed_pages.add(task.page_number)
                        data.processed_count += 1
                        processed_count = data.processed_count

                    task.processed = True
                    print(
                        f"Страница {task.page_number}: найдено {len(items)} элементов, {len(new_items)} новых ✅"
                    )

                    if processed_count % 10 == 0:
                        await self.save_progress()

                    return

                print(f"Страница {task.page_number}: не найдено элементов ⚠️")
                async with self.page_data.protected_access() as data:
                    if task.page_number > data.max_page_found:
                        data.no_more_pages = True
                        print(
                            f"Похоже, достигнут конец каталога на странице {task.page_number-1} ⚠️"
                        )
                return

            print(
                f"Ошибка при запросе страницы {task.page_number}: статус {response.status_code} ⚠️"
            )
            task.attempt_count += 1
            task.last_error = Exception(f"HTTP error {response.status_code}")
            if task.attempt_count < self.max_retries:
                async with self.page_data.protected_access() as data:
                    data.pending_tasks.append(task)
                return
        except Exception as e:
            if not e:
                print(f"Таймаут при запросе страницы {task.page_number} ⚠️")
                return

            print(f"Исключение при обработке страницы {task.page_number}: {e} ❌")
            task.attempt_count += 1
            task.last_error = e
            if task.attempt_count < self.max_retries:
                async with self.page_data.protected_access() as data:
                    data.pending_tasks.append(task)
                return

    @staticmethod
    def _parse_catalog_page(html_content: str) -> list[str]:
        soup = BeautifulSoup(html_content, "html.parser")
        items = []
        for card in soup.select(".cards-results__item"):
            link = card.select_one("a.cards-results__link")
            if link:
                href = link.get("href", "")
                if href is not None and "/catalog/" in href:
                    href = href.split("/catalog/")[1]
                    items.append(href)
        return items


if __name__ == "__main__":
    try:
        catalog_id = "000200_000018_RU_NLR_DRGNLR_3107"
        client_manager = ClientManager(
            timeout=30.0, proxy_file=Path(__file__).parent / "proxies.txt"
        )

        asyncio.run(client_manager.setup())

        parser = AsyncCatalogParser(
            catalog_id=catalog_id,
            client_manager=client_manager,
            num_workers=3,
            chunk_size=10,
        )

        results = asyncio.run(parser.run())

        if results:
            print("\nПримеры найденных элементов:")
            for i, item in enumerate(list(results)[:5], 1):
                print(f"  {i}. {item}")
    except KeyboardInterrupt:
        if parser:
            parser.stop_event.set()
            asyncio.run(parser.save_progress())
        print("\nПарсинг прерван. Программа завершена.")
    except Exception as e:
        if parser:
            parser.stop_event.set()
            asyncio.run(parser.save_progress())
        print(f"Необработанное исключение: {e}")
