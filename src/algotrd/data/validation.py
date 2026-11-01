from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import date
from typing import Any

from .calendar import expected_starts

@dataclass
class QualityReport:
    expected: int=0; received: int=0; missing: int=0; duplicates: int=0; unexpected: int=0; quarantined: int=0; anomalies: int=0; complete_sessions: int=0; incomplete_sessions: int=0; unverified_sessions: int=0
    def dict(self): return asdict(self)

def validate(rows: list[dict[str, Any]]) -> tuple[QualityReport, list[dict[str, Any]]]:
    report, bad = QualityReport(received=len(rows)), []
    keys=Counter((r["instrument_id"],r["interval_seconds"],r["ts_bar_start_utc"]) for r in rows)
    report.duplicates=sum(v-1 for v in keys.values() if v>1)
    per_day=defaultdict(list)
    for row in rows:
        failure=None
        prices=[row[x] for x in ("open","high","low","close")]
        if not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in prices): failure="INVALID_PRICE"
        elif row["high"] < max(row["open"],row["close"],row["low"]) or row["low"] > min(row["open"],row["close"],row["high"]): failure="INVALID_OHLC"
        elif any(row.get(x) is not None and row[x] < 0 for x in ("volume","open_interest")): failure="NEGATIVE_SIZE"
        elif row["ts_bar_end_utc"] <= row["ts_bar_start_utc"]: failure="INVALID_BAR_RANGE"
        if failure: bad.append({"row":row,"code":failure})
        per_day[row["trading_date_ist"]].append(row)
    report.quarantined=len(bad)
    for day, day_rows in per_day.items():
        expected=expected_starts(day, day_rows[0]["interval_seconds"])
        if expected is None: report.unverified_sessions += 1; continue
        got={r["ts_bar_start_utc"] for r in day_rows}; missing=set(expected)-got; unexpected=got-set(expected)
        report.expected += len(expected); report.missing += len(missing); report.unexpected += len(unexpected)
        if not missing and not unexpected and len(got)==len(day_rows): report.complete_sessions += 1
        else: report.incomplete_sessions += 1
    return report,bad
