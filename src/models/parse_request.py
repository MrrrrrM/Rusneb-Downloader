from dataclasses import dataclass


@dataclass
class ParseRequest:
    """Класс для хранения запроса на парсинг каталога или поиска."""

    query: str
    is_search: bool = False
