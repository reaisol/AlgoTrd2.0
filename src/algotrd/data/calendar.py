from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
# Known NSE full-day holidays in target period; uncertain sessions remain unverified.
# 2026-09-14 (Ganesh Chaturthi) is confirmed by NSE's equity/F&O holiday
# notices.  Keep this compact local calendar conservative: uncertain special
# sessions remain unverified rather than being declared missing.
KNOWN_HOLIDAYS = {date(2025, 11, 5), date(2025, 12, 25), date(2026, 1, 26), date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31), date(2026, 4, 3), date(2026, 4, 14), date(2026, 5, 1), date(2026, 8, 15), date(2026, 8, 26), date(2026, 9, 14), date(2026, 10, 2), date(2026, 10, 20), date(2026, 10, 29)}

def session(day: date) -> tuple[datetime, datetime] | None:
    if day.weekday() >= 5 or day in KNOWN_HOLIDAYS: return None
    return datetime.combine(day, time(9, 15), IST), datetime.combine(day, time(15, 30), IST)

def expected_starts(day: date, interval_seconds: int) -> list[datetime] | None:
    bounds = session(day)
    if not bounds: return None
    start, end = bounds; result=[]; cursor=start
    while cursor <= end:
        result.append(cursor.astimezone(UTC)); cursor += timedelta(seconds=interval_seconds)
    return result
