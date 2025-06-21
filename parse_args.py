import argparse
import sys


def parse_args() -> argparse.Namespace:
    """Парсинг аргументов командной строки для Rusneb парсера и загрузчика документов."""

    parser = argparse.ArgumentParser(description="Rusneb парсер и загрузчик документов")
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Поисковый запрос или идентификатор каталога для обработки",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="Используйте этот флаг, если запрос является поисковым термином, а не идентификатором каталога",
    )
    parser.add_argument(
        "--proxy-file",
        type=str,
        help="Путь к файлу, содержащему адреса прокси (по одному на строку)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Таймаут для HTTP-запросов в секундах (по умолчанию: 30.0)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Размер чанка для обработки (по умолчанию: 10)",
    )
    parser.add_argument(
        "--parser-workers",
        type=int,
        default=3,
        help="Количество воркеров для парсинга каталога (по умолчанию: 3)",
    )
    parser.add_argument(
        "--download-workers",
        type=int,
        default=1,
        help="Количество воркеров для загрузки файлов (по умолчанию: 1)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Установить уровень логирования (по умолчанию: INFO)",
    )
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
    return parser.parse_args()
