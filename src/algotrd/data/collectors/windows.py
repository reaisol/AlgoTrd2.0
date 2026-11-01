from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from ..schemas.candle import IST

SESSION_OPEN = time(9, 15)
SESSION_CLOSE = time(15, 30)


@dataclass(frozen=True)
class RequestWindow:
    start: datetime
    end: datetime


def iter_one_minute_windows(start: date, end: date, max_days: int = 28) -> list[RequestWindow]:
    """Inclusive date windows intentionally below Groww's 30-day one-minute cap."""
    if end < start:
        raise ValueError("end must not precede start")
    windows: list[RequestWindow] = []
    cursor = start
    while cursor <= end:
        last = min(cursor + timedelta(days=max_days - 1), end)
        windows.append(RequestWindow(
            datetime.combine(cursor, SESSION_OPEN, IST),
            datetime.combine(last, SESSION_CLOSE, IST),
        ))
        cursor = last + timedelta(days=1)
    return windows
