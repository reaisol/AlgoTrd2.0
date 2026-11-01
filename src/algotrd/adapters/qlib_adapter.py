"""Minimal Qlib 0.9.7 binary-data export for the immutable cash snapshot."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
import shutil
import statistics

import numpy as np
import pyarrow.parquet as pq


FIELDS = ("open", "high", "low", "close", "volume", "factor")


def export_cash_snapshot(release: Path, output: Path) -> int:
    """Export the cash snapshot in Qlib's documented file-storage layout.

    The Qlib calendar is UTC-naive text representing the original UTC
    instants.  It deliberately contains only the supplied five sessions.
    Factor is one because this is an unadjusted index series, not a fabricated
    corporate-action adjustment.
    """
    if output.exists():
        shutil.rmtree(output)
    (output / "calendars").mkdir(parents=True)
    (output / "instruments").mkdir()
    feature_dir = output / "features" / "nifty"
    feature_dir.mkdir(parents=True)
    rows = sorted(pq.read_table(release / "cash_reference.parquet").to_pylist(), key=lambda r: r["timestamp_utc"])
    if not rows:
        raise ValueError("cash snapshot is empty")
    timestamps = [r["timestamp_utc"].astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") for r in rows]
    (output / "calendars" / "1min.txt").write_text("\n".join(timestamps) + "\n")
    (output / "instruments" / "all.txt").write_text(f"NIFTY\t{timestamps[0]}\t{timestamps[-1]}\n")
    for field in FIELDS:
        values = np.ones(len(rows), dtype="<f4") if field == "factor" else np.asarray(
            [np.nan if r.get(field) is None else r[field] for r in rows], dtype="<f4"
        )
        np.hstack((np.asarray([0], dtype="<f4"), values)).astype("<f4").tofile(feature_dir / f"{field}.1min.bin")
    return len(rows)


def reconcile_cash_snapshot(release: Path, provider_uri: Path) -> dict[str, float | int | bool]:
    """Query Qlib and measure its documented float32 representation precisely."""
    import qlib
    from qlib.data import D

    source = sorted(pq.read_table(release / "cash_reference.parquet").to_pylist(), key=lambda r: r["timestamp_utc"])
    qlib.init(provider_uri=str(provider_uri), region="cn")
    queried = D.features(["NIFTY"], ["$open", "$high", "$low", "$close", "$volume", "$factor"], freq="1min")
    queried = queried.reset_index().sort_values("datetime").reset_index(drop=True)
    expected_times = [row["timestamp_utc"].astimezone(UTC).replace(tzinfo=None) for row in source]
    actual_times = queried["datetime"].tolist()
    errors: list[float] = []
    float32_mismatches = 0
    original_float64_differences = 0
    nan_prices = 0
    for index, row in enumerate(source):
        for field in ("open", "high", "low", "close"):
            actual = float(queried.iloc[index]["$" + field])
            expected32 = float(np.float32(row[field]))
            if np.isnan(actual):
                nan_prices += 1
            if actual != expected32:
                float32_mismatches += 1
            if actual != float(row[field]):
                original_float64_differences += 1
            errors.append(abs(actual - float(row[field])))
    return {
        "rows": len(queried),
        "timestamp_mismatches": sum(left != right for left, right in zip(expected_times, actual_times)),
        "instrument_mismatches": int(set(queried["instrument"]) != {"NIFTY"}),
        "float32_mismatches": float32_mismatches,
        "original_float64_differences": original_float64_differences,
        "nan_prices": nan_prices,
        "nan_volumes": int(queried["$volume"].isna().sum()),
        "unexpected_factor_values": int((queried["$factor"] != 1.0).sum()),
        "maximum_absolute_price_error": max(errors),
        "median_absolute_price_error": statistics.median(errors),
    }
