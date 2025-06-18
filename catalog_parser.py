# https://rusneb.ru/local/tools/exalead/getFiles.php?book_id=000200_000018_RU_NLR_BIBL_A_012520083
# https://rusneb.ru/catalog/000200_000018_RU_NLR_DRGNLR_3107/?volumes=page-1

import asyncio
import os
import time
import httpx

from typing import Optional
from bs4 import BeautifulSoup
from collections import deque
from client_manager import ClientManager
from file_manager import FileManager
from page_task import PageTask


class AsyncCatalogParser:
    """Асинхронный парсер каталога с динамическим распределением задач"""

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

        self.max_page_found = 0
        self.all_items: set[str] = set()
        self.download_queue: set[str] = set()
        self.processed_pages: set[int] = set()
        self.pending_tasks: deque[PageTask] = deque()
        self.no_more_pages = False
        self.has_error = False

        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()

        self.start_time = time.time()
        self.processed_count = 0
        self.last_save_time = 0

        self._load_progress()

    async def run(self) -> list[str]:
        """Запускает парсинг каталога в несколько асинхронных задач"""
        self.start_time = time.time()

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
            print(f"Парсинг завершен за {total_time:.2f} секунд")
            print(f"Обработано {len(self.processed_pages)} страниц")
            print(f"Найдено {len(self.all_items)} элементов")

            return list(self.all_items)

        except Exception as e:
            print(f"Ошибка при выполнении парсинга: {e}")
            self.has_error = True
            await self.save_progress()
            return list(self.all_items)

    async def worker(self, worker_id: int) -> None:
        """Рабочая функция для асинхронного обработчика"""
        print(f"Запущен воркер {worker_id}")

        client = await self.client_manager.pop_client()

        async with client:
            while not self.stop_event.is_set():
                tasks = await self._get_next_tasks(worker_id, self.chunk_size)

                if not tasks:
                    if self.no_more_pages and not self.pending_tasks:
                        print(f"Воркер {worker_id} завершается: задачи закончились")
                        break
                    else:
                        await asyncio.sleep(0.5)
                        continue

                for task in tasks:
                    if self.stop_event.is_set():
                        break
                    await self._process_page(task, client)

    async def save_progress(self) -> None:
        """Сохраняет текущий прогресс в файл"""
        current_time = time.time()
        if current_time - self.last_save_time < 5:
            return

        file_manager = FileManager.get_instance()

        if os.path.exists(self.save_file):
            try:
                data = file_manager.read_json(self.save_file)
                async with self.lock:
                    data["max_page_found"] = self.max_page_found
                    data["processed_pages"] = list(self.processed_pages)
                    data["download_queue"].extend(list(self.download_queue))
                    self.download_queue.clear()
                data["timestamp"] = current_time
            except Exception as e:
                print(f"Ошибка при чтении файла прогресса: {e}")
                return
        else:
            async with self.lock:
                data = {
                    "catalog_id": self.catalog_id,
                    "max_page_found": self.max_page_found,
                    "processed_pages": list(self.processed_pages),
                    "download_queue": list(self.download_queue),
                    "timestamp": current_time,
                }
                self.download_queue.clear()

        try:
            file_manager.write_json(self.save_file, data)

            print(
                f"Прогресс сохранен: {len(self.all_items)} уникальных элементов, "
                f"{len(self.processed_pages)} страниц обработано"
            )
        except Exception as e:
            print(f"Ошибка при сохранении прогресса: {e}")
            return

    def _load_progress(self) -> None:
        """Загружает сохраненный прогресс, если он есть"""
        if not os.path.exists(self.save_file):
            return

        file_manager = FileManager.get_instance()

        try:
            data = file_manager.read_json(self.save_file)

            self.max_page_found = data.get("max_page_found", 0)
            self.processed_pages = set(data.get("processed_pages", []))
            self.all_items = set(data.get("all_items", []))

            for page in range(1, self.max_page_found + 1):
                if page not in self.processed_pages:
                    self.pending_tasks.append(
                        PageTask(catalog_id=self.catalog_id, page_number=page)
                    )

            print(
                f"Загружен прогресс: обработано {len(self.processed_pages)} страниц, "
                f"найдено {len(self.all_items)} элементов, "
                f"в очереди {len(self.pending_tasks)} страниц для дообработки"
            )
        except Exception as e:
            print(f"Ошибка при загрузке прогресса: {e}")

    async def _get_next_tasks(self, worker_id: int, count: int) -> list[PageTask]:
        """Получает следующие задачи для обработки"""
        tasks = []

        async with self.lock:
            while len(tasks) < count and self.pending_tasks:
                task = self.pending_tasks.popleft()
                task.worker_id = worker_id
                tasks.append(task)

            if len(tasks) < count and not self.no_more_pages:
                start_page = self.max_page_found + 1
                end_page = start_page + (count - len(tasks))

                for page in range(start_page, end_page):
                    if page not in self.processed_pages:
                        tasks.append(
                            PageTask(
                                catalog_id=self.catalog_id,
                                worker_id=worker_id,
                                page_number=page,
                            )
                        )
                self.max_page_found = end_page

        return tasks

    async def _process_page(
        self, task: PageTask, client: httpx.AsyncClient
    ) -> Optional[PageTask]:
        """Обрабатывает страницу каталога"""
        if task.page_number in self.processed_pages:
            task.processed = True
            return task

        url = f"https://rusneb.ru/catalog/{task.catalog_id}/?volumes=page-{task.page_number}"

        print(
            f"Воркер {task.worker_id} обрабатывает страницу {task.page_number}: {url}"
        )

        try:
            response = await client.get(url, timeout=30.0)

            if response.status_code == 200:
                html_content = response.text
                items = self._parse_catalog_page(html_content)

                if items:
                    async with self.lock:
                        new_items = [
                            item for item in items if item not in self.all_items
                        ]
                        self.all_items.update(new_items)
                        self.download_queue.update(new_items)
                        task.items = new_items

                        if task.page_number > self.max_page_found:
                            self.max_page_found = task.page_number

                    task.processed = True
                    print(
                        f"Страница {task.page_number}: найдено {len(items)} элементов, {len(new_items)} новых"
                    )
                else:
                    print(f"Страница {task.page_number}: не найдено элементов")
                    if task.page_number > self.max_page_found:
                        async with self.lock:
                            self.no_more_pages = True
                            print(
                                f"Похоже, достигнут конец каталога на странице {task.page_number-1}"
                            )
            else:
                print(
                    f"Ошибка при запросе страницы {task.page_number}: статус {response.status_code}"
                )
                task.attempt_count += 1
                task.last_error = Exception(f"HTTP error {response.status_code}")
                if task.attempt_count < self.max_retries:
                    self.pending_tasks.append(task)
                    return None
        except Exception as e:
            if not e:
                print(f"Тайм-аут при запросе страницы {task.page_number}")
                return None

            print(f"Исключение при обработке страницы {task.page_number}: {e}")
            task.attempt_count += 1
            task.last_error = e
            if task.attempt_count < self.max_retries:
                self.pending_tasks.append(task)
                return None

        async with self.lock:
            self.processed_pages.add(task.page_number)
            self.processed_count += 1
            processed_count = self.processed_count

        if processed_count % 10 == 0:
            await self.save_progress()

        return task

    @staticmethod
    def _parse_catalog_page(html_content: str) -> list[str]:
        """Парсинг страницы каталога для извлечения идентификаторов элементов"""
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
        client_manager = ClientManager()

        parser = AsyncCatalogParser(
            catalog_id=catalog_id,
            client_manager=client_manager,
            num_workers=5,
            chunk_size=10,
        )

        results = asyncio.run(parser.run())

        if results:
            print("\nПримеры найденных элементов:")
            for i, item in enumerate(list(results)[:5], 1):
                print(f"  {i}. {item}")
    except KeyboardInterrupt:
        parser.stop_event.set()
        asyncio.run(parser.save_progress())
        print("\nПарсинг прерван. Программа завершена.")
    except Exception as e:
        parser.stop_event.set()
        asyncio.run(parser.save_progress())
        print(f"Необработанное исключение: {e}")
