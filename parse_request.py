from dataclasses import dataclass


@dataclass
class ParseRequest:
    query: str
    is_search: bool = False
