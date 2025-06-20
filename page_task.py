from dataclasses import dataclass, field
from typing import Optional

from parse_request import ParseRequest


@dataclass
class PageTask:
    request: ParseRequest
    page_number: int
    worker_id: Optional[int] = None
    processed: bool = False
    items: list[str] = field(default_factory=list)
    attempt_count: int = 0
    last_error: Optional[Exception] = None
    no_more_pages: bool = False
