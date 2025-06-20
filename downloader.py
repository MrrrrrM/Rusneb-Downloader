import random
import httpx
import asyncio

from pathlib import Path

from client_manager import ClientManager
from page_data import PageData
from parse_request import ParseRequest


class Downloader:
    DOWNLOAD_URL = f"https://rusneb.ru/local/tools/exalead/getFiles.php"

    def __init__(
        self,
        request: ParseRequest,
        client_manager: ClientManager,
        page_data: PageData,
        num_workers: int = 10,
    ):
        self.request = request
        self.client_manager = client_manager
        self.page_data = page_data
        self.num_workers = num_workers

        self.stop_event = asyncio.Event()

        self.save_directory = (
            Path(__file__).parent / "result" / request.query / "downloads"
        )
        self.save_directory.mkdir(parents=True, exist_ok=True)

    async def run(self) -> None:
        workers = [asyncio.create_task(self.worker(i)) for i in range(self.num_workers)]
        pending = set(workers)

        try:
            done, pending = await asyncio.wait(
                workers, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            print("Downloader cancelled by user, stopping workers...")
        except Exception as e:
            print(f"Error occurred in workers: {e}")
        finally:
            if not self.stop_event.is_set():
                self.stop_event.set()
                print("Ожидание завершения всех воркеров...")

            for worker in pending:
                if not worker.done():
                    worker.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

    async def worker(self, worker_id: int) -> None:
        print(f"Worker {worker_id} started.")

        client = await self.client_manager.pop_client()

        async with client:
            while not self.stop_event.is_set():
                success = False
                file_id = None
                try:
                    async with self.page_data.protected_access() as data:
                        if not data.download_queue:
                            print("Download queue is empty, waiting for updates...")
                            await asyncio.sleep(10)
                            continue
                        file_id = data.download_queue.popleft()
                        if file_id in data.downloaded:
                            continue
                    success = await self._download_file(client, file_id)
                except asyncio.CancelledError:
                    print(f"Worker {worker_id} cancelled.")
                except Exception as e:
                    print(f"Error in worker {worker_id} for file {file_id}: {e}")
                finally:
                    if file_id is not None:
                        async with self.page_data.protected_access() as data:
                            if success:
                                data.downloaded.add(file_id)
                            else:
                                print(
                                    f"Failed to download {file_id}, re-adding to queue."
                                )
                                data.download_queue.append(file_id)
                await asyncio.sleep(random.uniform(1, 3))

    async def _download_file(self, client: httpx.AsyncClient, file_id: str) -> bool:
        print(f"Downloading file {file_id}...")

        params = {"book_id": file_id, "doc_type": "pdf"}

        try:
            response = await client.get(self.DOWNLOAD_URL, params=params)
        except Exception as e:
            print(f"Request error for {file_id}: {e}")
            return False

        if response.status_code != 200:
            return False

        content_type = response.headers.get("Content-Type")
        if content_type != "application/pdf":
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
