import asyncio
import os
import time

from pathlib import Path
from collections import deque
from contextlib import asynccontextmanager
from file_manager import FileManager
from page_task import PageTask
from parse_request import ParseRequest
from log_manager import log_manager


class PageData:
    """Класс для хранения и управления данными о страницах каталога."""

    def __init__(self, request: ParseRequest):
        """
        Инициализация класса PageData.

        Args:
            request (ParseRequest): Запрос для парсинга каталога.
        """

        self.request = request
        self.save_file = Path(__file__).parent / "result" / request.query
        self.save_file.mkdir(parents=True, exist_ok=True)
        self.save_file /= f"catalog_progress_{request.query}.json"

        # Serialization data
        self.max_page_found = 0
        self.processed_pages: set[int] = set()
        self.download_queue: deque[str] = deque()
        self.downloaded: set[str] = set()
        # End of serialization data

        self.pending_tasks: deque[PageTask] = deque()
        self.no_more_pages = False
        self.has_error = False

        self.lock = asyncio.Lock()
        self.logger = log_manager.get_logger(__name__)

    @asynccontextmanager
    async def protected_access(self) -> "asyncio.AsyncGenerator['PageData', None]":
        """
        Контекстный менеджер для безопасного доступа к данным с блокировкой.

        Returns:
            asyncio.AsyncGenerator(['PageData', None]): Асинхронный генератор с доступом к данным страницы.
        """

        await self.lock.acquire()
        try:
            yield self
        finally:
            self.lock.release()

    async def load_progress(self) -> None:
        """Загрузка прогресса парсинга каталога из файла JSON."""

        if not os.path.exists(self.save_file):
            self.logger.warning(f"Файл прогресса {self.save_file.name} не найден")
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

                self.logger.info(
                    f"Загружен прогресс: обработано {len(data.processed_pages)} страниц, "
                    f"в очереди {len(data.pending_tasks)} страниц для дообработки"
                )

        except Exception as e:
            self.logger.exception(f"Ошибка при загрузке прогресса: {e}", exc_info=True)

    async def save_progress(self) -> None:
        """Сохранение текущего прогресса парсинга каталога в файл JSON."""

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

            self.logger.info(f"Прогресс каталога {self.request.query} сохранен:")
            self.logger.info(f"    {len(data.processed_pages)} страниц обработано")
            self.logger.info(
                f"    {len(data.download_queue)} документов в очереди на загрузку"
            )
            self.logger.info(f"    {len(data.downloaded)} загруженных документов")

        except Exception as e:
            self.logger.exception(
                f"Ошибка при сохранении прогресса: {e}", exc_info=True
            )
