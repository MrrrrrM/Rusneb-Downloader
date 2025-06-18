import asyncio
from collections import deque
from page_task import PageTask


class PageData:
    def __init__(self, catalog_id: str, page_number: int):
        self.catalog_id = catalog_id
        self.initial_page = page_number

        self.max_page_found = 0
        self.processed_count = 0
        self.all_items: set[str] = set()
        self.download_queue: set[str] = set()
        self.processed_pages: set[int] = set()
        self.pending_tasks: deque[PageTask] = deque()
        self.no_more_pages = False
        self.has_error = False

        self.lock = asyncio.Lock()

    def protected_access(self):
        """Предоставляет защищённый доступ к данным с использованием блокировки."""

        class ProtectedAccessContextManager:
            def __init__(self, data, lock):
                self.data = data
                self.lock = lock

            async def __aenter__(self):
                await self.lock.acquire()
                return self.data

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.lock.release()

        return ProtectedAccessContextManager(self, self.lock)
