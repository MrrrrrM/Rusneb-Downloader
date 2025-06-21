import logging
import colorama
import atexit

from logging.handlers import RotatingFileHandler
from pathlib import Path


colorama.init()


class LogManager:
    """
    Класс для управления логированием в приложении.
    Предоставляет единую точку доступа к логгерам и их конфигурации.
    """

    class ColoredFormatter(logging.Formatter):
        """
        Кастомный форматтер для цветного вывода в консоль.
        Использует ANSI escape коды для цветового оформления сообщений в зависимости от уровня логирования.
        Наследует от logging.Formatter.
        """

        COLORS = {
            "RESET": "\033[0m",
            "RED": "\033[31m",
            "GREEN": "\033[32m",
            "YELLOW": "\033[33m",
            "BLUE": "\033[34m",
            "MAGENTA": "\033[35m",
            "CYAN": "\033[36m",
        }

        FORMATS = {
            logging.DEBUG: COLORS["BLUE"]
            + "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            + COLORS["RESET"],
            logging.INFO: COLORS["GREEN"]
            + "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            + COLORS["RESET"],
            logging.WARNING: COLORS["YELLOW"]
            + "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            + COLORS["RESET"],
            logging.ERROR: COLORS["RED"]
            + "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            + COLORS["RESET"],
            logging.CRITICAL: COLORS["MAGENTA"]
            + "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
            + COLORS["RESET"],
        }

        def format(self, record: logging.LogRecord) -> str:
            """
            Форматирует запись лога с учетом уровня.

            Args:
                record (logging.LogRecord): Запись лога.

            Returns:
                str: Отформатированная строка лога.
            """

            log_fmt = self.FORMATS.get(record.levelno)
            formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
            return formatter.format(record)

    def __init__(
        self,
        logs_dir: str = "logs",
        log_filename: str = "app.log",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        level: int = logging.INFO,
        file_level: int = logging.INFO,
        console_level: int = logging.DEBUG,
    ):
        """
        Инициализирует менеджер логирования.

        Args:
            logs_dir (str): Директория для логов.
            log_filename (str): Имя файла для логирования.
            max_bytes (int): Максимальный размер файла лога перед ротацией.
            backup_count (int): Количество файлов резервных копий для хранения.
            level (int): Общий уровень логирования для всех логгеров (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            file_level (int): Уровень логирования для файлового обработчика.
            console_level (int): Уровень логирования для консольного обработчика.
        """

        self._loggers = {}

        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)
        self.log_file = self.logs_dir / log_filename

        self.max_bytes = max_bytes
        self.backup_count = backup_count

        self.level = level
        self.file_level = file_level
        self.console_level = console_level

        root = logging.getLogger()
        if root.handlers:
            for handler in root.handlers:
                root.removeHandler(handler)

        atexit.register(self._cleanup_handlers)

        self.root_logger = self.get_logger()

    def get_logger(self, name: str | None = None) -> logging.Logger:
        """
        Получает логгер с настроенными обработчиками для заданного модуля.
        Если имя не указано, возвращается корневой логгер.

        Args:
            name (str | None): Имя логгера.

        Returns:
            logging.Logger: Настроенный логгер.
        """

        cache_key = name if name else "_root_"
        if cache_key in self._loggers:
            return self._loggers[cache_key]

        logger = logging.getLogger(name)
        logger.propagate = False
        logger.handlers = []
        logger.setLevel(self.level)

        file_handler = RotatingFileHandler(
            filename=self.log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(self.file_level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(self.ColoredFormatter())

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        self._loggers[cache_key] = logger
        return logger

    def set_level(
        self, level: int, name: str | None = None, handler_type: str | None = None
    ) -> None:
        """
        Устанавливает уровень логирования для указанного логгера или его обработчика.

        Args:
            level (int): Уровень логирования (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL).
            name (str | None): Имя логгера. Если None, применяется ко всем логгерам.
            handler_type (str | None): Тип обработчика ('file', 'console', или None для всех).
        """

        if name and name in self._loggers:
            logger = self._loggers[name]
            if not handler_type:
                logger.setLevel(level)
            else:
                self._set_handler_level(logger, level, handler_type)
            return
        else:
            if not handler_type or handler_type == "both":
                self.level = level
            if not handler_type or handler_type == "file":
                self.file_level = level
            if not handler_type or handler_type == "console":
                self.console_level = level

            for logger_name, logger in self._loggers.items():
                if not handler_type:
                    logger.setLevel(level)
                self._set_handler_level(logger, level, handler_type)

    def _set_handler_level(
        self, logger: logging.Logger, level: int, handler_type: str | None = None
    ) -> None:
        """
        Устанавливает уровень для определенного типа обработчика логгера.

        Args:
            logger (Logger): Логгер для настройки.
            level (int): Уровень логирования.
            handler_type (str | None): Тип обработчика ('file', 'console', или None для всех).
        """

        for handler in logger.handlers:
            if handler_type == "file" and isinstance(handler, RotatingFileHandler):
                handler.setLevel(level)
            elif (
                handler_type == "console"
                and isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, RotatingFileHandler)
            ):
                handler.setLevel(level)
            elif not handler_type:
                handler.setLevel(level)

    def _cleanup_handlers(self) -> None:
        """Очищает все обработчики при завершении работы программы."""

        for logger_name, logger in self._loggers.items():
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)


log_manager = LogManager()

__all__ = ["LogManager", "log_manager"]
