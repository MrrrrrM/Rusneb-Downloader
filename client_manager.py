import httpx
from pathlib import Path
import requests
import asyncio


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
                    "No clients available. Please check your configuration."
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
        http_timeout = httpx.Timeout(self.timeout)
        http_transport = httpx.AsyncHTTPTransport(retries=self.retries)

        if not proxy_file or not proxy_file.exists():
            return [
                httpx.AsyncClient(transport=http_transport, timeout=http_timeout)
                for _ in range(count_clients)
            ]

        if use_socks5:
            proxies = self._read_socks5_proxies(proxy_file)
        else:
            proxies = self._read_http_proxies(proxy_file)

        return [
            httpx.AsyncClient(
                transport=http_transport, timeout=http_timeout, proxy=proxy
            )
            for proxy in proxies
        ]

    @staticmethod
    def _read_http_proxies(proxy_file: Path) -> list[str]:
        http_proxies = []

        with proxy_file.open("r", encoding="utf-8") as f:
            for line in f:
                host, port, user, password = line.strip().split(":")
                proxy_url = f"http://{user}:{password}@{host}:{port}"

                if ClientManager._check_http_proxy(proxy_url, timeout=30.0):
                    print(f"Proxy работает: {proxy_url}")
                    http_proxies.append(proxy_url)
                else:
                    print(f"Proxy не работает: {proxy_url}")

        return http_proxies

    @staticmethod
    def _read_socks5_proxies(proxy_file: Path) -> list[str]:
        socks5_proxies = []

        with proxy_file.open("r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("10."):
                    host = line.split(" ")[0]
                    proxy = f"socks5://{host}:1080"
                    socks5_proxies.append(proxy)

        return socks5_proxies

    @staticmethod
    def _check_http_proxy(
        proxy_url: str, test_url: str = "https://httpbin.org/ip", timeout: float = 10.0
    ) -> bool:
        proxies = {"http": proxy_url, "https": proxy_url}
        print(proxies)
        try:
            response = requests.get(test_url, proxies=proxies, timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False


async def main():
    proxy_file = None
    # proxy_file = Path(__file__).parent / "proxies.txt"

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
