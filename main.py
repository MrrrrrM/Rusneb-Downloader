import argparse
import asyncio

from parse_args import parse_args
from src.models.parse_request import ParseRequest
from src.models.page_data import PageData
from src.client.client_manager import ClientManager
from src.parsers.catalog_parser import CatalogParser
from src.downloaders.downloader import Downloader
from src.utils.log_manager import log_manager


async def main() -> None:
    """Основная функция для запуска парсера и загрузчика документов Rusneb."""

    logger = log_manager.get_logger(__name__)

    try:
        args = parse_args()
    except argparse.ArgumentError as e:
        logger.error(f"Ошибка парсинга аргументов: {e}")
        return

    log_manager.set_level(args.log_level.upper())

    try:
        logger.info("Начало работы Rusneb парсера и загрузчика документов")

        request = ParseRequest(args.query, args.search)
        logger.info(
            f"Запрос для обработки: {args.query}, режим поиска: {"да" if args.search else "нет"}"
        )

        logger.info(f"Настройка менеджера клиентов...")
        client_manager = ClientManager(proxy_file=args.proxy_file)
        await client_manager.setup()

        logger.info(f"Загрузка прогресса...")
        page_data = PageData(request)
        await page_data.load_progress()

        logger.info(
            f"Настройка парсера с {args.parser_workers} воркерами, размер чанка {args.chunk_size}..."
        )
        catalog_parser = CatalogParser(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=args.parser_workers,
            chunk_size=args.chunk_size,
        )

        logger.info(f"Настройка загрузчика с {args.download_workers} воркерами...")
        downloader = Downloader(
            request=request,
            client_manager=client_manager,
            page_data=page_data,
            num_workers=args.download_workers,
        )

        logger.info(f"Запуск задач парсинга и загрузки")
        tasks = [catalog_parser.run(), downloader.run()]
        await asyncio.gather(*tasks, return_exceptions=True)

    except asyncio.CancelledError:
        logger.warning("Операция отменена пользователем")
    except Exception as e:
        logger.exception(f"Вызвано исключение: {str(e)}", exc_info=True)

    finally:
        logger.info("Сохранение прогресса...")
        await page_data.save_progress()
        logger.info("Работа завершена")


if __name__ == "__main__":
    asyncio.run(main())
