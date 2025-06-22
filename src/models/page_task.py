from dataclasses import dataclass, field

from src.models.parse_request import ParseRequest


@dataclass
class PageTask:
    """Класс для хранения информации о задаче парсинга страницы."""

    request: ParseRequest
    page_number: int
    worker_id: int | None = None
    processed: bool = False
    items: list[str] = field(default_factory=list)
    attempt_count: int = 0
    last_error: Exception | None = None
    no_more_pages: bool = False
