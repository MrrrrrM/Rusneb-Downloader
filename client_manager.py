import httpx
import asyncio

from pathlib import Path
from fake_useragent import FakeUserAgent
from tqdm.asyncio import tqdm_asyncio as tqdm


class ClientManager:
    def __init__(
        self,
        timeout: float = 10.0,
        retries: int = 3,
        proxy_file: Path = None,
        use_socks5: bool = False,
        count_clients: int = 100,
    ):
        self.timeout = timeout
        self.retries = retries
        self.clients = []
        self.lock = asyncio.Lock()
        self.proxy_file = proxy_file
        self.use_socks5 = use_socks5
        self.count_clients = count_clients

    async def setup(self):
        """Asynchronously initialize clients."""
        self.clients = await self._spawn_clients(
            self.proxy_file, self.use_socks5, self.count_clients
        )

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
        use_socks5: bool = False,
        count_clients: int = 100,
    ) -> list[httpx.AsyncClient]:
        fake_useragent = FakeUserAgent()
        http_transport = httpx.AsyncHTTPTransport(retries=self.retries)
        http_timeout = httpx.Timeout(self.timeout)

        if not proxy_file or not proxy_file.exists():
            return [
                httpx.AsyncClient(
                    headers={"User-Agent": fake_useragent.random},
                    transport=http_transport,
                    timeout=http_timeout,
                )
                for _ in range(count_clients)
            ]

        if use_socks5:
            proxies = self._read_socks5_proxies(proxy_file)
        else:
            proxies = await self._read_http_proxies(proxy_file)

        if not proxies:
            print(
                f"Не найдено рабочих прокси. Создаю {count_clients} клиентов без прокси"
            )
            return [
                httpx.AsyncClient(
                    headers={"User-Agent": fake_useragent.random},
                    transport=http_transport,
                    timeout=http_timeout,
                )
                for _ in range(count_clients)
            ]

        print(f"Создаю {len(proxies)} клиентов с прокси")
        return [
            httpx.AsyncClient(
                headers={"User-Agent": fake_useragent.random},
                transport=httpx.AsyncHTTPTransport(retries=self.retries, proxy=proxy),
                timeout=http_timeout,
            )
            for proxy in proxies
        ]

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

        print(f"Проверка {len(proxies)} прокси серверов:")
        results = await tqdm.gather(*tasks, desc="Проверка прокси")

        working_count = 0
        for proxy, is_working in zip(proxies, results):
            if is_working:
                working_count += 1
                http_proxies.append(proxy)

        print(f"Найдено рабочих прокси: {working_count} из {len(proxies)}")
        return http_proxies

    @staticmethod
    def _read_socks5_proxies(proxy_file: Path) -> list[httpx.Proxy]:
        socks5_proxies = []

        with proxy_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("10."):
                    host = line.split(" ")[0]
                    proxy = httpx.Proxy(url=f"socks5://{host}:1080")
                    socks5_proxies.append(proxy)

        return socks5_proxies

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


async def test():
    proxy_file = None
    # proxy_file = Path(__file__).parent / "proxies.txt"

    if proxy_file is None:
        manager = ClientManager()
    else:
        manager = ClientManager(proxy_file=proxy_file)

    await manager.setup()

    client = await manager.pop_client()
    print("Client obtained:", client)
    print("Client count:", len(manager.clients))

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(test())
