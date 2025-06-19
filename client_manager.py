import httpx
import asyncio
import logging
import log_config
from pathlib import Path
from fake_useragent import FakeUserAgent
from tqdm.asyncio import tqdm_asyncio as tqdm

class ClientManager:
    def __init__(
        self,
        timeout: float = 10.0,
        retries: int = 3,
        proxy_file: Path = None,
        count_clients: int = 100,
    ):
        self.timeout = timeout
        self.retries = retries
        self.clients = []
        self.lock = asyncio.Lock()
        self.proxy_file = proxy_file
        self.count_clients = count_clients

    async def setup(self):
        """Asynchronously initialize clients."""
        self.clients = await self._spawn_clients(self.proxy_file, self.count_clients)

    async def pop_client(self) -> httpx.AsyncClient:
        async with self.lock:
            if not self.clients:
                raise ValueError(
                    "Нет доступных клиентов. Пожалуйста, проверьте настройки прокси"
                )
            if len(self.clients) < 10:
                self.clients.extend(await self._spawn_clients(count_clients=10))
            return self.clients.pop(0)

    async def _spawn_clients(
        self,
        proxy_file: Path = None,
        count_clients: int = 100,
    ) -> list[httpx.AsyncClient]:
        fake_useragent = FakeUserAgent()
        http_transport = httpx.AsyncHTTPTransport(retries=self.retries)
        http_timeout = httpx.Timeout(self.timeout)

        if not proxy_file or not proxy_file.exists():
            logging.warning(
                f"Прокси файл {proxy_file} не найден или не существует. Создаю {count_clients} клиентов без прокси"
            )
            return [
                self._generate_client(
                    fake_useragent,
                    http_transport,
                    http_timeout,
                )
                for _ in range(count_clients)
            ]

        proxies = await self._read_http_proxies(proxy_file)

        if not proxies:
            logging.warning(
                f"В вашем файле {proxy_file} не найдено рабочих прокси. Создаю {count_clients} клиентов без прокси"
            )
            return [
                self._generate_client(
                    fake_useragent,
                    http_transport,
                    http_timeout,
                )
                for _ in range(count_clients)
            ]

        logging.warning(
            f"Доступно {len(proxies)} прокси. Создаю {len(proxies)} клиентов с прокси"
        )
        return [
            self._generate_client(
                fake_useragent,
                http_transport,
                http_timeout,
                self.retries,
                proxy,
            )
            for proxy in proxies
        ]

    @staticmethod
    def _generate_client(
        fake_useragent, http_transport, http_timeout, retries=None, proxy=None
    ):
        if proxy is not None:
            logging.info(f"Создаем клиент с использованием прокси: {proxy}")
            transport = httpx.AsyncHTTPTransport(retries=retries, proxy=proxy)
        else:
            logging.info(f"Создаем клиент без использования прокси")
            transport = http_transport

        return httpx.AsyncClient(
            headers={"User-Agent": fake_useragent.random},
            transport=transport,
            timeout=http_timeout,
        )

    @staticmethod
    async def _read_http_proxies(proxy_file: Path) -> list[httpx.Proxy]:
        http_proxies = []
        tasks = []
        proxies = []

        with proxy_file.open("r", encoding="utf-8") as f:
            for line in f:
                host, port, user, password = line.strip().split(":")
                proxy = httpx.Proxy(url=f"http://{host}:{port}", auth=(user, password))
                proxies.append(proxy)
                tasks.append(ClientManager._check_http_proxy(proxy))

        logging.warning(f"Проверка {len(proxies)} прокси серверов:")
        results = await tqdm.gather(*tasks, desc="Проверка прокси")

        working_count = 0
        for proxy, is_working in zip(proxies, results):
            if is_working:
                working_count += 1
                http_proxies.append(proxy)

        logging.warning(f"Найдено рабочих прокси: {working_count} из {len(proxies)}")
        return http_proxies

    @staticmethod
    async def _check_http_proxy(
        proxy: httpx.Proxy,
        test_url: str = "https://httpbin.org/ip",
        retries: int = 1,
        timeout: float = 10.0,
    ) -> bool:
        fake_useragent = FakeUserAgent()
        http_transport = httpx.AsyncHTTPTransport(retries=retries, proxy=proxy)
        http_timeout = httpx.Timeout(timeout)

        async with httpx.AsyncClient(
            headers={"User-Agent": fake_useragent.random},
            transport=http_transport,
            timeout=http_timeout,
        ) as client:
            try:
                response = await client.get(test_url)
                return response.status_code == 200
            except Exception:
                return False
        return False


async def main():
    proxy_file = None
    proxy_file = Path(__file__).parent / "proxies.txt"

    if proxy_file is None:
        manager = ClientManager()
    else:
        manager = ClientManager(proxy_file=proxy_file)

    await manager.setup()

    client = await manager.pop_client()
    logging.info(f"Client obtained: {client}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
