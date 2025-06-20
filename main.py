import asyncio
import argparse

from parse_args import parse_args
from catalog_parser import CatalogParser
from client_manager import ClientManager
from downloader import Downloader
from page_data import PageData
from parse_request import ParseRequest


async def main() -> None:
    try:
        args = parse_args()
    except argparse.ArgumentError as e:
        print(f"Argument error: {e}")
        return

    try:
        request = ParseRequest(args.query, is_search=args.search)
        client_manager = ClientManager(timeout=args.timeout, proxy_file=args.proxy_file)
        await client_manager.setup()

        page_data = PageData(request)
        await page_data.load_progress()

        catalog_parser = CatalogParser(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=args.parser_workers,
            chunk_size=args.chunk_size,
        )

        downloader = Downloader(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=args.download_workers,
        )

        tasks = [catalog_parser.run(), downloader.run()]
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        print("Operation cancelled.")
    finally:
        await page_data.save_progress()


if __name__ == "__main__":
    asyncio.run(main())
