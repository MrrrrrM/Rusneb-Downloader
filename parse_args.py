import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rusneb Catalog Parser and Downloader")
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Search query or catalog identifier (e.g., '000200_000018_RU_NLR_DRGNLR_3107')",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Use this flag if the query is a search term instead of a catalog identifier",
    )
    parser.add_argument(
        "--proxy-file",
        type=str,
        help="Path to the file containing proxy addresses (one per line)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout for HTTP requests in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Chunk size for processing (default: 10)",
    )
    parser.add_argument(
        "--parser-workers",
        type=int,
        default=3,
        help="Number of workers for catalog parsing (default: 3)",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=1,
        help="Number of workers for downloading files (default: 1)",
    )
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()
