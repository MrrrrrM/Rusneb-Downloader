import os
import threading
import json

from typing import Any
from pathlib import Path


class FileManager:
    """
    A singleton class for thread-safe file access operations.
    Uses locks to prevent concurrent access issues when reading/writing files.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FileManager, cls).__new__(cls)
                cls._instance._file_locks = {}
                cls._instance._global_lock = threading.RLock()
            return cls._instance

    def __init__(self):
        pass

    @staticmethod
    def get_instance() -> "FileManager":
        """
        Get the singleton instance of FileManager.

        Returns:
            FileManager: The singleton FileManager instance.
        """
        if FileManager._instance is None:
            FileManager()
        return FileManager._instance

    def read_file(self, file_path: str | Path, binary: bool = False) -> str | bytes:
        """
        Read a file with thread safety.

        Args:
            file_path: Path to the file to read
            binary: Whether to read in binary mode

        Returns:
            The file contents as string or bytes
        """
        file_path = Path(file_path)

        with self._get_file_lock(file_path):
            mode = "rb" if binary else "r"
            encoding = None if binary else "utf-8"

            try:
                with open(file_path, mode=mode, encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                raise IOError(f"Error reading file {file_path}: {str(e)}")

    def write_file(
        self,
        file_path: str | Path,
        content: str | bytes,
        binary: bool = False,
    ) -> None:
        """
        Write to a file with thread safety.

        Args:
            file_path: Path to the file to write
            content: Content to write
            binary: Whether to write in binary mode
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
                raise IOError(f"Error writing to file {file_path}: {str(e)}")

    def append_file(
        self,
        file_path: str | Path,
        content: str | bytes,
        binary: bool = False,
    ) -> None:
        """
        Append to a file with thread safety.

        Args:
            file_path: Path to the file to append to
            content: Content to append
            binary: Whether to append in binary mode
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
                raise IOError(f"Error appending to file {file_path}: {str(e)}")

    def read_json(self, file_path: str | Path) -> dict[str, Any]:
        """
        Read a JSON file with thread safety.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dict containing parsed JSON data
        """
        file_path = Path(file_path)

        with self._get_file_lock(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                raise IOError(f"Error reading JSON file {file_path}: {str(e)}")

    def write_json(
        self, file_path: str | Path, data: dict[str, Any], indent: int = 4
    ) -> None:
        """
        Write a dictionary to a JSON file with thread safety.

        Args:
            file_path: Path to the file to write
            data: Dictionary to serialize as JSON
            indent: JSON indentation level
        """
        file_path = Path(file_path)

        os.makedirs(file_path.parent, exist_ok=True)

        with self._get_file_lock(file_path):
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=indent, ensure_ascii=False)
            except Exception as e:
                raise IOError(f"Error writing JSON file {file_path}: {str(e)}")

    def clear_locks(self):
        """Clear all file locks that are no longer needed"""
        with self._global_lock:
            self._file_locks.clear()

    def _get_file_lock(self, file_path: str | Path) -> threading.Lock:
        """
        Get a lock object for a specific file.
        Creates a new lock if one doesn't exist for the file.

        Args:
            file_path: Path to the file

        Returns:
            threading.Lock: The lock object for the specified file
        """
        file_path_str = str(file_path)

        with self._global_lock:
            if file_path_str not in self._file_locks:
                self._file_locks[file_path_str] = threading.RLock()

            return self._file_locks[file_path_str]
