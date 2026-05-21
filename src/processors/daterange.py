

from datetime import date, timedelta
from typing import Iterator


def daterange(start: date, end: date) -> Iterator[date]:
    """Yields all dates sequentially from start to end inclusive."""
    curr = start
    while curr <= end:
        yield curr
        curr += timedelta(days=1)
