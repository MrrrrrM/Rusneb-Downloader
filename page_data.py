import asyncio
import os
from pathlib import Path
import time

from collections import deque
from contextlib import asynccontextmanager
from file_manager import FileManager
from page_task import PageTask
from parse_request import ParseRequest


class PageData:
    def __init__(self, request: ParseRequest):
        self.request = request
        self.save_file = Path(__file__).parent / "result" / request.query
        self.save_file.mkdir(parents=True, exist_ok=True)
        self.save_file /= f"catalog_progress_{request.query}.json"

        # Serialization data
        self.max_page_found: int = 0
        self.processed_pages: set[int] = set()
        self.download_queue: deque[str] = deque()
        self.downloaded: set[str] = set()

        self.pending_tasks: deque[PageTask] = deque()
        self.no_more_pages = False
        self.has_error = False

        self.lock = asyncio.Lock()

    @asynccontextmanager
    async def protected_access(self):
        await self.lock.acquire()
        try:
            yield self
        finally:
            self.lock.release()

    async def save_progress(self) -> None:
        async with self.protected_access() as data:
            saved_data = {
                "request": self.request.query,
                "timestamp": time.time_ns(),
                "max_page_found": data.max_page_found,
                "processed_pages": list(data.processed_pages),
                "download_queue": list(data.download_queue),
                "downloaded": list(data.downloaded),
            }

        try:
            file_manager = FileManager.get_instance()
            file_manager.write_json(self.save_file, saved_data)

            print(
                f"Прогресс каталога {self.request.query} сохранен:\n"
                f"    {len(data.processed_pages)} страниц обработано\n"
                f"    {len(data.download_queue)} документов в очереди на загрузку\n"
                f"    {len(data.downloaded)} загруженных документов\n"
            )
        except Exception as e:
            print(f"Ошибка при сохранении прогресса: {e} ❌")

    async def load_progress(self) -> None:
        if not os.path.exists(self.save_file):
            print(f"Файл прогресса {self.save_file.name} не найден ⚠️")
            return

        try:
            file_manager = FileManager.get_instance()
            file_data = file_manager.read_json(self.save_file)

            async with self.protected_access() as data:
                data.max_page_found = file_data.get("max_page_found", 0)
                data.processed_pages = set(file_data.get("processed_pages", []))
                data.download_queue = deque(file_data.get("download_queue", []))
                data.downloaded = set(file_data.get("downloaded", []))

                for page in range(1, data.max_page_found + 1):
                    if page not in data.processed_pages:
                        data.pending_tasks.append(
                            PageTask(request=self.request, page_number=page)
                        )

                print(
                    f"Загружен прогресс: обработано {len(data.processed_pages)} страниц, "
                    f"в очереди {len(data.pending_tasks)} страниц для дообработки"
                )
        except Exception as e:
            print(f"Ошибка при загрузке прогресса: {e} ❌")
