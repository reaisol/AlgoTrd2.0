from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow.parquet as pq

from algotrd.data.collectors.historical import HistoricalCollector
from algotrd.data.schemas.candle import candle_from_row, validate_candles
from algotrd.data.storage.manifest import Manifest
from algotrd.data.storage.parquet_writer import SCHEMA, write_candles
from algotrd.data.storage.raw_writer import write_raw_response


def make_candle(row=None):
    return candle_from_row(row or ["2025-11-03T09:15:00", 100, 102, 99, 101, None, None], instrument_id="NIFTY50", groww_symbol="NSE-NIFTY", exchange="NSE", segment="CASH", interval_seconds=60, ingested_at_utc=datetime.now(UTC))


def test_timestamp_and_nullable_index_fields():
    candle = make_candle()
    assert candle.timestamp_utc.isoformat() == "2025-11-03T03:45:00+00:00"
    assert candle.volume is None and candle.open_interest is None
    assert validate_candles([candle]) == []


def test_parquet_schema_and_atomic_raw_write(tmp_path: Path):
    raw, checksum = write_raw_response(tmp_path, request_id="abc", window_start=datetime(2025, 11, 1, tzinfo=UTC), response={"payload": {"candles": []}}, metadata={"provider": "groww"})
    assert raw.exists() and len(checksum) == 64 and not list(raw.parent.glob("*.tmp"))
    paths = write_candles(tmp_path, [make_candle()], "abc")
    # Read the file directly: dataset discovery would also infer hive partition columns
    # from parent directories, which intentionally duplicate canonical file columns.
    table = pq.ParquetFile(paths[0]).read()
    assert table.schema == SCHEMA
    assert table.column("volume").to_pylist() == [None]


class FakeGroww:
    def __init__(self): self.calls = 0
    def historical_candles(self, **_):
        self.calls += 1
        return {"status": "SUCCESS", "payload": {"candles": [["2025-11-03T09:15:00", 100, 102, 99, 101, None, None]]}}


def test_manifest_resume_prevents_duplicate_downloads(tmp_path: Path):
    manifest = Manifest(tmp_path / "manifests" / "ingestion.sqlite3")
    fake = FakeGroww()
    collector = HistoricalCollector(fake, tmp_path, manifest)
    # One one-day request; calling again must use the completed checkpoint.
    first = collector.download(date(2025, 11, 3), date(2025, 11, 3))
    second = collector.download(date(2025, 11, 3), date(2025, 11, 3))
    assert first["candles"] == 1 and fake.calls == 1 and second["skipped"] == 1
    assert len(list((tmp_path / "raw").rglob("*.json.gz"))) == 1
