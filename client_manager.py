import random
from pathlib import Path

import httpx


class ClientManager:
    SOCKS5_PROXY_SOURCE = "https://raw.githubusercontent.com/maximko/mullvad-socks-list/list/socks-ipv4_in-list.txt"
    HTTP_PROXY_FILE = Path(__file__).parent.parent / "proxies.txt"

    def __init__(
        self, timeout: float = 10.0, retries: int = 3, use_socks5: bool = True
    ):
        self.timeout = timeout
        self.retries = retries
        self.use_socks5 = use_socks5
        self.clients = self._spawn_clients()

    def _get_socks5_proxies(self) -> list[str]:
        response = httpx.get(self.SOCKS5_PROXY_SOURCE)
        response.raise_for_status()

        socks5 = []
        for line in response.text.splitlines():
            if line.startswith("10."):
                host = line.split(" ")[0]
                proxy = f"socks5://{host}:1080"
                socks5.append(proxy)
        return socks5

    def _read_http_proxies(self) -> list[str]:
        http_proxies = []

        with self.HTTP_PROXY_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                host, port, user, password = line.strip().split(":")
                proxy = f"http://{user}:{password}@{host}:{port}"
                http_proxies.append(proxy)

        return http_proxies

    def _spawn_clients(self) -> list[httpx.AsyncClient]:
        http_timeout = httpx.Timeout(self.timeout)
        http_transport = httpx.AsyncHTTPTransport(retries=self.retries)

        if self.use_socks5:
            clients = [
                httpx.AsyncClient(
                    transport=http_transport, timeout=http_timeout  # , proxy=proxy
                )
                for i in range(10)
                # for proxy in self._get_socks5_proxies()
            ]
        else:
            clients = [
                httpx.AsyncClient(
                    transport=http_transport, timeout=http_timeout, proxy=proxy
                )
                for proxy in self._read_http_proxies()
            ]
        return clients

    def get_client(self) -> httpx.AsyncClient:
        return random.choice(self.clients)
