from datetime import timedelta
from pathlib import Path

import pyarrow.parquet as pq

from algotrd.adapters.atm_resolver import AtmMappingResolver


RELEASE = Path("data/releases/nifty-options-2026-09-5session-pilot-v3")


def test_v3_atm_resolver_is_point_in_time_and_deterministic():
    resolver = AtmMappingResolver(RELEASE)
    first = resolver.rows[0]
    rows = resolver.resolve(first["decision_timestamp_utc"])

    assert len(rows) == 14
    assert rows == resolver.resolve(first["decision_timestamp_utc"])
    assert all(row["reference_timestamp_utc"] < first["decision_timestamp_utc"] for row in rows)
    assert {row["option_type"] for row in rows} == {"CE", "PE"}
    assert resolver.resolve(first["decision_timestamp_utc"] + timedelta(seconds=1)) == []


def test_v3_mapping_keeps_unavailable_prices_unavailable():
    rows = pq.read_table(RELEASE / "atm_mapping.parquet").to_pylist()
    assert len(rows) == 26_250
    assert sum(row["contract_available"] for row in rows) == 26_250
    assert sum(row["price_available"] for row in rows) == 25_088
    assert sum(not row["price_available"] for row in rows) == 1_162
