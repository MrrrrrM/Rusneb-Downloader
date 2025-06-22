from pathlib import Path


class Config:
    # Базовая директория проекта (корневая)
    BASE_DIR = Path(__file__).parent.parent.parent

    # Директория для результатов
    RESULT_DIR = BASE_DIR / "results"

    # Директория для логов
    LOGS_DIR = BASE_DIR / "logs"

    # Файл логов
    DEFAULT_LOGS_FILE = "main.log"

    # Количество воркеров для парсинга
    DEFAULT_PARSER_WORKERS = 3

    # Размер чанка для парсинга
    DEFAULT_PARSER_CHUNK_SIZE = 10

    # Количество повторных попыток парсинга
    DEFAULT_PARSER_RETRIES = 3

    # Количество воркеров для загрузки
    DEFAULT_DOWNLOADER_WORKERS = 1

    # Количество повторных попыток загрузки
    DEFAULT_DOWNLOADER_RETRIES = 3
