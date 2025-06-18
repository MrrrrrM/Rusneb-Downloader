from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageTask:
    """Задача обработки страницы каталога"""

    catalog_id: str
    page_number: int
    worker_id: Optional[int] = None
    processed: bool = False
    items: list[str] = field(default_factory=list)
    attempt_count: int = 0
    last_error: Optional[Exception] = None
