from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ..schemas.candle import Candle

SCHEMA = pa.schema([
    ("instrument_id", pa.string()), ("groww_symbol", pa.string()), ("exchange", pa.string()),
    ("segment", pa.string()), ("timestamp_utc", pa.timestamp("us", tz="UTC")), ("trading_date_ist", pa.date32()),
    ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()), ("close", pa.float64()),
    ("volume", pa.int64()), ("open_interest", pa.int64()), ("interval_seconds", pa.int32()),
    ("source", pa.string()), ("ingested_at_utc", pa.timestamp("us", tz="UTC")),
])


def write_candles(root: Path, candles: list[Candle], request_id: str) -> list[Path]:
    by_partition: dict[tuple[int, int], list[Candle]] = defaultdict(list)
    for candle in candles:
        by_partition[(candle.trading_date_ist.year, candle.trading_date_ist.month)].append(candle)
    paths: list[Path] = []
    for (year, month), group in by_partition.items():
        first = group[0]
        directory = root / "clean" / "indices" / f"exchange={first.exchange}" / f"instrument={first.instrument_id}" / f"interval={first.interval_seconds // 60}min" / f"year={year}" / f"month={month:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        final = directory / f"part-{request_id}.parquet"
        if final.exists():
            raise FileExistsError(f"refusing to overwrite canonical parquet: {final}")
        table = pa.Table.from_pylist([c.model_dump() for c in group], schema=SCHEMA)
        temp = final.with_suffix(".parquet.tmp")
        pq.write_table(table, temp, compression="zstd")
        os.replace(temp, final)
        paths.append(final)
    return paths
