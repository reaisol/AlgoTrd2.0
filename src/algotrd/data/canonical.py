from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any

import pyarrow as pa

CANONICAL_SCHEMA_VERSION = "2.0.0"
CANONICAL_SCHEMA = pa.schema([
    ("instrument_id", pa.string()), ("provider_instrument_id", pa.string()), ("exchange", pa.string()),
    ("segment", pa.string()), ("asset_class", pa.string()), ("ts_bar_start_utc", pa.timestamp("us", tz="UTC")),
    ("ts_bar_end_utc", pa.timestamp("us", tz="UTC")), ("ts_available_utc", pa.timestamp("us", tz="UTC")),
    ("trading_date_ist", pa.date32()), ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()),
    ("close", pa.float64()), ("volume", pa.int64()), ("open_interest", pa.int64()), ("interval_seconds", pa.int32()),
    ("source", pa.string()), ("source_timestamp_raw", pa.string()), ("ingested_at_utc", pa.timestamp("us", tz="UTC")),
    ("quality_status", pa.string()), ("dataset_version", pa.string()),
])

def canonicalize_legacy_row(row: dict[str, Any], version: str) -> dict[str, Any]:
    # Groww docs expose timestamp strings but do not state whether they label bar start/end.
    # Phase 1 evidence aligns them with session minute starts; this is an explicit convention,
    # not a claim of live data availability. ts_available_utc remains unknown.
    start = row["timestamp_utc"].astimezone(UTC)
    seconds = int(row["interval_seconds"])
    return {"instrument_id": "NSE:INDEX:NIFTY50", "provider_instrument_id": row["groww_symbol"], "exchange": "NSE",
        "segment": "INDEX", "asset_class": "INDEX", "ts_bar_start_utc": start, "ts_bar_end_utc": start + timedelta(seconds=seconds),
        "ts_available_utc": None, "trading_date_ist": row["trading_date_ist"], "open": row["open"], "high": row["high"],
        "low": row["low"], "close": row["close"], "volume": row["volume"], "open_interest": row["open_interest"],
        "interval_seconds": seconds, "source": row["source"], "source_timestamp_raw": start.isoformat(),
        "ingested_at_utc": row["ingested_at_utc"], "quality_status": "VALID", "dataset_version": version}
