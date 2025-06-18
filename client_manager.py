import httpx
from pathlib import Path
import asyncio
from fake_useragent import FakeUserAgent


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
        self.clients = self._spawn_clients(proxy_file, use_socks5, count_clients)
        self.lock = asyncio.Lock()

    async def pop_client(self) -> httpx.AsyncClient:
        async with self.lock:
            if not self.clients:
                raise ValueError(
                    "Нет доступных клиентов. Пожалуйста, проверьте настройки прокси"
                )
            if len(self.clients) < 10:
                self.clients.extend(self._spawn_clients(count_clients=10))
            return self.clients.pop(0)

    def _spawn_clients(
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
            proxies = self._read_http_proxies(proxy_file)

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
    def _read_http_proxies(proxy_file: Path) -> list[httpx.Proxy]:
        http_proxies = []

        with proxy_file.open("r", encoding="utf-8") as f:
            for line in f:
                host, port, user, password = line.strip().split(":")
                proxy = httpx.Proxy(url=f"http://{host}:{port}", auth=(user, password))

                if ClientManager._check_http_proxy(proxy):
                    print("работает ✅")
                    http_proxies.append(proxy)
                else:
                    print("не работает ❌")

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
    def _check_http_proxy(
        proxy: httpx.Proxy,
        test_url: str = "https://httpbin.org/ip",
        retries: int = 1,
        timeout: float = 10.0,
    ) -> bool:
        fake_useragent = FakeUserAgent()
        http_transport = httpx.HTTPTransport(retries=retries, proxy=proxy)
        http_timeout = httpx.Timeout(timeout)
        print(f"{proxy}: ", end="")

        with httpx.Client(
            headers={"User-Agent": fake_useragent.random},
            transport=http_transport,
            timeout=http_timeout,
        ) as client:
            try:
                response = client.get(test_url)
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

    client = await manager.pop_client()
    print("Client obtained:", client)

    await client.aclose()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
