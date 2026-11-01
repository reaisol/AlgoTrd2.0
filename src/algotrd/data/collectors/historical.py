from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from ..providers.groww import GrowwClient
from ..schemas.candle import IST, Candle, candle_from_row, validate_candles
from ..storage.manifest import Manifest
from ..storage.parquet_writer import write_candles
from ..storage.raw_writer import write_raw_response
from .windows import RequestWindow, iter_one_minute_windows

NIFTY50 = {"instrument_id": "NIFTY50", "groww_symbol": "NSE-NIFTY", "exchange": "NSE", "segment": "CASH"}


def request_id(window: RequestWindow) -> str:
    return hashlib.sha256(f"NIFTY50|1minute|{window.start.isoformat()}|{window.end.isoformat()}".encode()).hexdigest()[:16]


def _extract_rows(response: dict[str, Any]) -> list[list[Any]]:
    payload = response.get("payload", response)
    rows = payload.get("candles") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError("Groww response does not contain a candles array")
    return rows


class HistoricalCollector:
    def __init__(self, client: GrowwClient, root: Path, manifest: Manifest):
        self.client, self.root, self.manifest = client, root, manifest

    def plan(self, start: date, end: date) -> list[RequestWindow]:
        return iter_one_minute_windows(start, end)

    @staticmethod
    def completed_end(end: date) -> date:
        """Never request an in-progress IST session; future empty windows are avoided."""
        latest = datetime.now(IST).date()
        return min(end, latest - timedelta(days=1))

    def download(self, start: date, end: date, *, refresh: bool = False) -> dict[str, int]:
        end = self.completed_end(end)
        if end < start:
            return {"windows": 0, "downloaded": 0, "skipped": 0, "candles": 0, "invalid": 0}
        totals = {"windows": 0, "downloaded": 0, "skipped": 0, "candles": 0, "invalid": 0}
        for window in self.plan(start, end):
            totals["windows"] += 1
            rid = request_id(window)
            if self.manifest.completed(rid) and not refresh:
                totals["skipped"] += 1
                continue
            self.manifest.started(rid, "NIFTY50", window.start.isoformat(), window.end.isoformat(), "1minute")
            try:
                response = self.client.historical_candles(groww_symbol="NSE-NIFTY", start=window.start, end=window.end)
                rows = _extract_rows(response)
                ingested = datetime.now(UTC)
                candles = [candle_from_row(row, **NIFTY50, interval_seconds=60, ingested_at_utc=ingested) for row in rows]
                candles.sort(key=lambda value: value.timestamp_utc)
                issues = validate_candles(candles)
                if issues:
                    totals["invalid"] += len(issues)
                    raise ValueError("; ".join(issues[:5]))
                raw_path, checksum = write_raw_response(self.root, request_id=rid, window_start=window.start, response=response, metadata={
                    "provider": "groww", "exchange": "NSE", "segment": "CASH", "instrument": "NSE-NIFTY",
                    "interval": "1minute", "requested_start": window.start.isoformat(), "requested_end": window.end.isoformat(),
                    "http_status": 200, "candle_count": len(candles),
                })
                parquet_paths = write_candles(self.root, candles, rid)
                self.manifest.complete(rid, len(candles), raw_path, parquet_paths, checksum)
                totals["downloaded"] += 1
                totals["candles"] += len(candles)
            except Exception as exc:
                self.manifest.failed(rid, exc)
                raise
        return totals
