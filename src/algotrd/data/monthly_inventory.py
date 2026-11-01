"""Non-mutating monthly cash coverage inventory for bounded backfills."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .session_policy import classify


def expected_weekdays(start: date, end: date, holidays: set[date]) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5 and cursor not in holidays:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def september_2026_inventory(root: Path, holidays: set[date]) -> dict[str, Any]:
    """Inventory existing canonical cash data without downloading or modifying it."""
    month = root / "clean/indices/exchange=NSE/instrument=NIFTY50/interval=1min/year=2026/month=09"
    rows: list[dict[str, Any]] = []
    for file in sorted(month.glob("*.parquet")):
        rows.extend(pq.ParquetFile(file).read().to_pylist())
    # Additive repair files may overlap existing canonical partitions.  Count
    # coverage by the canonical timestamp key, never by physical row count.
    unique_rows: dict[tuple[str, object], dict[str, Any]] = {}
    for row in rows:
        unique_rows.setdefault((row["instrument_id"], row["timestamp_utc"]), row)
    by_day: dict[date, Counter[str]] = {}
    for row in unique_rows.values():
        by_day.setdefault(row["trading_date_ist"], Counter())[classify(row["timestamp_utc"])] += 1
    expected = expected_weekdays(date(2026, 9, 1), date(2026, 9, 30), holidays)
    sessions = [
        {
            "date": day.isoformat(),
            "regular_candles": by_day.get(day, Counter())["REGULAR"],
            "expected_regular_candles": 375,
            "missing_regular_candles": max(0, 375 - by_day.get(day, Counter())["REGULAR"]),
            "status": "COMPLETE" if by_day.get(day, Counter())["REGULAR"] == 375 else "INCOMPLETE",
        }
        for day in expected
    ]
    return {
        "month": "2026-09",
        "expected_sessions": len(expected),
        "complete_sessions": sum(x["status"] == "COMPLETE" for x in sessions),
        "cash_regular_candles": sum(x["regular_candles"] for x in sessions),
        "missing_regular_candles": sum(x["missing_regular_candles"] for x in sessions),
        "physical_rows": len(rows),
        "duplicate_timestamp_rows": len(rows) - len(unique_rows),
        "sessions": sessions,
    }


def write_inventory_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
