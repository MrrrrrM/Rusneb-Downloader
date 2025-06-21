import random
import httpx
import asyncio

from pathlib import Path
from client_manager import ClientManager
from page_data import PageData
from parse_request import ParseRequest
from log_manager import log_manager


class Downloader:
    """Класс для загрузки документов с сайта Rusneb."""

    DOWNLOAD_URL = f"https://rusneb.ru/local/tools/exalead/getFiles.php"

    def __init__(
        self,
        request: ParseRequest,
        client_manager: ClientManager,
        page_data: PageData,
        num_workers: int = 10,
    ):
        """
        Инициализация класса Downloader.

        Args:
            request (ParseRequest): Запрос для загрузки документов.
            client_manager (ClientManager): Менеджер HTTP-клиентов.
            page_data (PageData): Данные страницы с информацией о загрузке.
            num_workers (int): Количество воркеров для загрузки.
        """

        self.request = request
        self.client_manager = client_manager
        self.page_data = page_data
        self.num_workers = num_workers

        self.stop_event = asyncio.Event()
        self.logger = log_manager.get_logger(__name__)

        self.save_directory = (
            Path(__file__).parent / "result" / request.query / "downloads"
        )
        self.save_directory.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        """Запуск загрузчика документов с использованием асинхронных воркеров."""

        workers = [asyncio.create_task(self.worker(i)) for i in range(self.num_workers)]
        pending = set(workers)

        try:
            done, pending = await asyncio.wait(
                workers, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            self.logger.warning("Загрузка была отменена пользователем")
        except Exception as e:
            self.logger.exception(f"Вызвано исключение в воркерах: {e}", exc_info=True)
        finally:
            if not self.stop_event.is_set():
                self.stop_event.set()
                self.logger.info("Ожидание завершения всех воркеров...")

            for worker in pending:
                if not worker.done():
                    worker.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

    async def worker(self, worker_id: int) -> None:
        """Асинхронный воркер для загрузки документов."""

        self.logger.info(f"Воркер {worker_id} запущен для загрузки документов")

        client = await self.client_manager.pop_client()

        async with client:
            while not self.stop_event.is_set():
                success = False
                file_id = None
                try:
                    async with self.page_data.protected_access() as data:
                        if not data.download_queue:
                            self.logger.info(
                                "Очередь загрузки пуста, ожидание обновлений..."
                            )
                            await asyncio.sleep(10)
                            continue
                        file_id = data.download_queue.popleft()
                        if file_id in data.downloaded:
                            continue
                    success = await self._download_file(client, file_id)
                except asyncio.CancelledError:
                    self.logger.warning(f"Воркер {worker_id} отменен")
                except Exception as e:
                    self.logger.exception(
                        f"Ошибка в воркере {worker_id} для файла {file_id}: {e}",
                        exc_info=True,
                    )
                finally:
                    if file_id:
                        async with self.page_data.protected_access() as data:
                            if success:
                                data.downloaded.add(file_id)
                                self.logger.info(f"Файл {file_id} успешно загружен")
                            else:
                                self.logger.warning(
                                    f"Не удалось загрузить {file_id}, повторное добавление в очередь"
                                )
                                data.download_queue.append(file_id)
                    await asyncio.sleep(random.uniform(1, 3))

    async def _download_file(self, client: httpx.AsyncClient, file_id: str) -> bool:
        """
        Загрузка файла по идентификатору.

        Args:
            client (httpx.AsyncClient): Асинхронный HTTP-клиент.
            file_id (str): Идентификатор файла для загрузки.

        Returns:
            bool: True, если загрузка прошла успешно, иначе False.
        """

        self.logger.info(f"Загрузка файла {file_id}")

        params = {"book_id": file_id, "doc_type": "pdf"}

        try:
            response = await client.get(self.DOWNLOAD_URL, params=params)
        except Exception as e:
            self.logger.exception(
                f"Вызвано исключение для {file_id}: {e}", exc_info=True
            )
            return False

        if response.status_code != 200:
            self.logger.error(
                f"Ошибка загрузки файла {file_id}: статус {response.status_code}"
            )
            return False

        content_type = response.headers.get("Content-Type")
        if content_type != "application/pdf":
            self.logger.error(
                f"Неверный тип содержимого для {file_id}: {content_type}, ожидается application/pdf"
            )
            return False

        filename = (
            response.headers.get("Content-Disposition")
            .split("filename=")[-1]
            .strip('"')
        )
        full_path = self.save_directory / f"{filename}.pdf"

        with open(full_path, "wb") as f:
            f.write(response.content)

        return True


async def test() -> None:
    try:
        # request = ParseRequest("000200_000018_RU_NLR_DRGNLR_3107")
        request = ParseRequest("Петроградская газета 1911", is_search=True)

        client_manager = ClientManager(
            timeout=30.0,  # proxy_file=Path(__file__).parent / "proxies.txt"
        )
        await client_manager.setup()

        page_data = PageData(request)
        await page_data.load_progress()

        downloader = Downloader(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=1,
        )
        await downloader.run()
    finally:
        await page_data.save_progress()


if __name__ == "__main__":
    asyncio.run(test())
