from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

IST = ZoneInfo("Asia/Kolkata")


class Candle(BaseModel):
    """Canonical, provider-normalized candle. Index volume/OI remain null when absent."""

    model_config = ConfigDict(frozen=True)
    instrument_id: str
    groww_symbol: str
    exchange: str
    segment: str
    timestamp_utc: datetime
    trading_date_ist: date
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    open_interest: int | None = None
    interval_seconds: int
    source: str = "groww"
    ingested_at_utc: datetime

    @field_validator("timestamp_utc", "ingested_at_utc")
    @classmethod
    def must_be_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(UTC)


def parse_provider_timestamp(value: str | int | float) -> datetime:
    if isinstance(value, (int, float)):
        # Groww's newer backtesting endpoint uses ISO strings; legacy endpoints used epoch seconds.
        return datetime.fromtimestamp(value, tz=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    # Groww documents a timestamp without timezone; it represents the NSE session clock (IST).
    return parsed.replace(tzinfo=IST) if parsed.tzinfo is None else parsed.astimezone(IST)


def candle_from_row(
    row: list[Any], *, instrument_id: str, groww_symbol: str, exchange: str,
    segment: str, interval_seconds: int, ingested_at_utc: datetime,
) -> Candle:
    if len(row) < 5:
        raise ValueError("candle must contain timestamp, open, high, low, close")
    timestamp_ist = parse_provider_timestamp(row[0]).astimezone(IST)
    volume = row[5] if len(row) > 5 else None
    oi = row[6] if len(row) > 6 else None
    return Candle(
        instrument_id=instrument_id, groww_symbol=groww_symbol, exchange=exchange,
        segment=segment, timestamp_utc=timestamp_ist.astimezone(UTC),
        trading_date_ist=timestamp_ist.date(), open=float(row[1]), high=float(row[2]),
        low=float(row[3]), close=float(row[4]),
        volume=None if volume is None else int(volume),
        open_interest=None if oi is None else int(oi), interval_seconds=interval_seconds,
        ingested_at_utc=ingested_at_utc,
    )


def validate_candles(candles: list[Candle]) -> list[str]:
    issues: list[str] = []
    seen: set[datetime] = set()
    previous: datetime | None = None
    for candle in candles:
        if candle.timestamp_utc in seen:
            issues.append(f"duplicate timestamp: {candle.timestamp_utc.isoformat()}")
        seen.add(candle.timestamp_utc)
        if previous and candle.timestamp_utc <= previous:
            issues.append("candles are not in chronological order")
        previous = candle.timestamp_utc
        if candle.high < max(candle.open, candle.close, candle.low) or candle.low > min(candle.open, candle.close, candle.high):
            issues.append(f"invalid OHLC at {candle.timestamp_utc.isoformat()}")
        if candle.volume is not None and candle.volume < 0:
            issues.append(f"negative volume at {candle.timestamp_utc.isoformat()}")
    # A received regular-length session is checked for missing minutes. We deliberately
    # do not label an absent date as missing: it can be an NSE holiday. Short sessions
    # remain a Phase 2 calendar reconciliation item rather than being fabricated.
    by_day: dict[date, set[datetime]] = {}
    for candle in candles:
        by_day.setdefault(candle.trading_date_ist, set()).add(candle.timestamp_utc)
    for trading_day, timestamps in by_day.items():
        ist_times = [timestamp.astimezone(IST).time() for timestamp in timestamps]
        if min(ist_times) <= time(9, 20) and max(ist_times) >= time(15, 25):
            expected = {
                datetime.combine(trading_day, time(9, 15), IST).astimezone(UTC) + timedelta(minutes=index)
                for index in range(376)
            }
            missing = expected - timestamps
            if missing:
                issues.append(f"missing {len(missing)} regular-session minute(s) on {trading_day.isoformat()}")
    return issues
