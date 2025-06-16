import asyncio

from client_manager import ClientManager
import dotenv

dotenv.load_dotenv()

client_manager = ClientManager(timeout=5.0, retries=3, use_socks5=True)


async def main():
    max_concurrent_requests = dotenv.get_key(dotenv.find_dotenv(), "MAX_CONCURRENT_REQUESTS")
    


if __name__ == "__main__":
    asyncio.run(main())
