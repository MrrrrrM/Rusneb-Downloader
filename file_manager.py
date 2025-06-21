import os
import threading
import json

from typing import Any
from pathlib import Path


class FileManager:
    """
    Синглтон класс для управления файлами с потокобезопасностью.
    Позволяет читать, записывать и добавлять данные в файлы, а также работать с JSON.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Создает новый экземпляр класса, если он еще не создан."""

        with cls._lock:
            if not cls._instance:
                cls._instance = super(FileManager, cls).__new__(cls)
                cls._instance._file_locks = {}
                cls._instance._global_lock = threading.RLock()
            return cls._instance

    def __init__(self):
        """Инициализация пропущена, так как используется паттерн Singleton."""

        pass

    @staticmethod
    def get_instance() -> "FileManager":
        """
        Получает экземпляр FileManager.

        Returns:
            FileManager: Синглтон экземпляр FileManager.
        """

        if not FileManager._instance:
            FileManager()
        return FileManager._instance

    def read_file(self, file_path: str | Path, binary: bool = False) -> str | bytes:
        """
        Чтение файла с потокобезопасностью.

        Args:
            file_path (str | Path): Путь к файлу для чтения.
            binary (bool): Нужно ли читать в бинарном режиме.

        Returns:
            (str | bytes): Содержимое файла в виде строки или байтов.
        """

        file_path = Path(file_path)

        with self._get_file_lock(file_path):
            mode = "rb" if binary else "r"
            encoding = None if binary else "utf-8"

            try:
                with open(file_path, mode=mode, encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                raise IOError(f"Ошибка чтения файла {file_path}: {str(e)}")

    def write_file(
        self,
        file_path: str | Path,
        content: str | bytes,
        binary: bool = False,
    ) -> None:
        """
        Запись в файл с потокобезопасностью.

        Args:
            file_path (str | Path): Путь к файлу для записи.
            content (str | bytes): Содержимое для записи.
            binary (bool): Нужно ли записывать в бинарном режиме.
        """

        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)

        with self._get_file_lock(file_path):
            mode = "wb" if binary else "w"
            encoding = None if binary else "utf-8"

            try:
                with open(file_path, mode=mode, encoding=encoding) as f:
                    f.write(content)
            except Exception as e:
                raise IOError(f"Ошибка записи в файл {file_path}: {str(e)}")

    def append_file(
        self,
        file_path: str | Path,
        content: str | bytes,
        binary: bool = False,
    ) -> None:
        """
        Добавление в файл с потокобезопасностью.

        Args:
            file_path (str | Path): Путь к файлу для добавления.
            content (str | bytes): Содержимое для добавления.
            binary (bool): Нужно ли добавлять в бинарном режиме.
        """

        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)

        with self._get_file_lock(file_path):
            mode = "ab" if binary else "a"
            encoding = None if binary else "utf-8"

            try:
                with open(file_path, mode=mode, encoding=encoding) as f:
                    f.write(content)
            except Exception as e:
                raise IOError(f"Ошибка добавления в файл {file_path}: {str(e)}")

    def read_json(self, file_path: str | Path) -> dict[str, Any]:
        """
        Чтение JSON файла с потокобезопасностью.

        Args:
            file_path (str | Path): Путь к JSON файлу

        Returns:
            dict ([str, Any]): Данные из JSON файла
        """

        file_path = Path(file_path)

        with self._get_file_lock(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise IOError(f"Ошибка чтения JSON файла {file_path}: {str(e)}")

    def write_json(
        self, file_path: str | Path, data: dict[str, Any], indent: int = 4
    ) -> None:
        """
        Запись словаря в JSON файл с потокобезопасностью.

        Args:
            file_path (str | Path): Путь к файлу для записи
            data (dict[str, Any]): Словарь для сериализации в JSON
            indent (int): Уровень отступа для JSON
        """

        file_path = Path(file_path)
        os.makedirs(file_path.parent, exist_ok=True)

        with self._get_file_lock(file_path):
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=indent, ensure_ascii=False)
            except Exception as e:
                raise IOError(f"Ошибка записи в JSON файл {file_path}: {str(e)}")

    def _get_file_lock(self, file_path: str | Path) -> threading.Lock:
        """
        Получение объекта блокировки для конкретного файла.
        Создает новую блокировку, если она еще не существует для файла.

        Args:
            file_path (str | Path): Путь к файлу

        Returns:
            threading.Lock: Объект блокировки для указанного файла
        """

        file_path_str = str(file_path)

        with self._global_lock:
            if file_path_str not in self._file_locks:
                self._file_locks[file_path_str] = threading.RLock()

            return self._file_locks[file_path_str]
