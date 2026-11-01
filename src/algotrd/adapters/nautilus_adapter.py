"""NautilusTrader 2.x conversion for the immutable Phase 3 option release.

The module intentionally uses only public NautilusTrader interfaces.  It is
loaded by the dedicated Python 3.14 environment; the project's normal Python
environment does not need NautilusTrader installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
import json

import pyarrow.parquet as pq


@dataclass(frozen=True)
class CatalogVerification:
    instruments: int
    bars: int
    mismatches: int


@dataclass(frozen=True)
class ConversionResult:
    catalog: CatalogVerification
    rejected_rows: int
    coverage: str


def _row_identity(row: dict[str, Any]) -> dict[str, str]:
    """Stable enough evidence to locate an immutable source row."""
    return {
        "instrument_id": row["instrument_id"],
        "provider_instrument_id": row["provider_instrument_id"],
        "ts_bar_end_utc": row["ts_bar_end_utc"].isoformat(),
        "trading_date_ist": (row.get("trading_date_ist") or row["ts_bar_end_utc"].astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).date()).isoformat(),
    }


def classify_option_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return eligible rows plus a deterministic non-destructive rejection ledger."""
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    seen: set[tuple[str, datetime]] = set()
    for row in sorted(rows, key=lambda r: (r["provider_instrument_id"], r["ts_bar_end_utc"])):
        identity = _row_identity(row)
        key = (row["provider_instrument_id"], row["ts_bar_end_utc"])
        reason: str | None = None
        if key in seen:
            reason = "duplicate instrument/timestamp key"
        elif row["volume"] is None:
            reason = "canonical volume is null; Nautilus Bar requires Quantity"
        elif isinstance(row["volume"], bool) or int(row["volume"]) != row["volume"] or int(row["volume"]) < 0:
            reason = "volume is not a non-negative integral Quantity"
        elif any(row[name] is None or float(row[name]) <= 0 for name in ("open", "high", "low", "close")):
            reason = "OHLC contains a non-positive or null value"
        elif row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(
            row["open"], row["close"], row["high"]
        ):
            reason = "OHLC range is inconsistent"
        if reason:
            rejected.append({**identity, "reason": reason})
        else:
            accepted.append(row)
        seen.add(key)
    return accepted, rejected


def _nt() -> dict[str, Any]:
    """Import the tested NautilusTrader 2.x public surface lazily."""
    from nautilus_trader.model import (
        AggregationSource,
        AssetClass,
        Bar,
        BarAggregation,
        BarSpecification,
        BarType,
        Currency,
        InstrumentId,
        OptionContract,
        OptionKind,
        Price,
        PriceType,
        Quantity,
        Symbol,
        Venue,
    )
    from nautilus_trader.persistence import ParquetDataCatalog

    return locals()


def _epoch_ns(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("canonical timestamp must be timezone-aware")
    return int(value.astimezone(UTC).timestamp() * 1_000_000_000)


def _provider_symbol(row: dict[str, Any]) -> str:
    symbol = row["provider_instrument_id"]
    if not symbol.startswith("NSE-"):
        raise ValueError(f"unexpected provider symbol {symbol!r}")
    return symbol.removeprefix("NSE-")


def option_instrument_from_row(row: dict[str, Any]):
    """Create an engineering-only OptionContract from one canonical row.

    ``activation_ns=0`` records unknown historical activation time.  The
    multiplier of one is provisional: lot size is the historically verified
    65, but these catalog instruments are not approved for execution P&L.
    """
    nt = _nt()
    symbol = _provider_symbol(row)
    option_kind = nt["OptionKind"].CALL if row["option_type"] == "CE" else nt["OptionKind"].PUT
    expiry = datetime.combine(row["contract_expiry"], datetime.min.time(), tzinfo=UTC)
    expiry_ns = _epoch_ns(expiry)
    instrument_id = nt["InstrumentId"](nt["Symbol"](symbol), nt["Venue"]("NSE"))
    return nt["OptionContract"](
        instrument_id=instrument_id,
        raw_symbol=nt["Symbol"](symbol),
        asset_class=nt["AssetClass"].EQUITY,
        underlying="NIFTY",
        option_kind=option_kind,
        strike_price=nt["Price"](float(row["strike_price"]), 2),
        currency=nt["Currency"].from_str("INR"),
        activation_ns=0,
        expiration_ns=expiry_ns,
        price_precision=2,
        price_increment=nt["Price"](0.05, 2),
        multiplier=nt["Quantity"](1, 0),
        lot_size=nt["Quantity"](65, 0),
        ts_event=expiry_ns,
        ts_init=expiry_ns,
    )


def bar_from_row(row: dict[str, Any]):
    """Convert an end-labelled canonical one-minute candle into an external Bar."""
    nt = _nt()
    for name in ("open", "high", "low", "close"):
        if row[name] is None or float(row[name]) <= 0:
            raise ValueError(f"invalid {name} for {row['provider_instrument_id']}: {row[name]!r}")
    if row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(
        row["open"], row["close"], row["high"]
    ):
        raise ValueError(f"invalid OHLC range for {row['provider_instrument_id']}")
    if row["volume"] is None or int(row["volume"]) < 0:
        raise ValueError(f"invalid volume for {row['provider_instrument_id']}: {row['volume']!r}")

    instrument = option_instrument_from_row(row)
    bar_type = nt["BarType"](
        instrument.id,
        nt["BarSpecification"](1, nt["BarAggregation"].MINUTE, nt["PriceType"].LAST),
        nt["AggregationSource"].EXTERNAL,
    )
    # Source timestamps are verified candle *end* labels. ts_init is set to
    # ts_event because live arrival time is unknown, not because it was known
    # to be available at that instant.
    timestamp_ns = _epoch_ns(row["ts_bar_end_utc"])
    return nt["Bar"](
        bar_type,
        nt["Price"](float(row["open"]), 2),
        nt["Price"](float(row["high"]), 2),
        nt["Price"](float(row["low"]), 2),
        nt["Price"](float(row["close"]), 2),
        nt["Quantity"](int(row["volume"]), 0),
        timestamp_ns,
        timestamp_ns,
    )


def release_option_rows(release: Path) -> list[dict[str, Any]]:
    """Read all option records in deterministic contract/timestamp order."""
    manifest = __import__("json").loads((release / "manifest.json").read_text())
    rows: list[dict[str, Any]] = []
    for entry in manifest.get("options_files", manifest.get("options", [])):
        # Parquet paths sit below Hive-style ``option_type=`` directories and
        # also contain an option_type column.  ParquetFile avoids dataset
        # partition inference attempting to merge those two representations.
        rows.extend(pq.ParquetFile(release / entry["path"]).read().to_pylist())
    return sorted(rows, key=lambda r: (r["provider_instrument_id"], r["ts_bar_end_utc"]))


def write_catalog(release: Path, catalog_path: Path) -> CatalogVerification:
    """Write all immutable option data to a generated public catalog and verify it."""
    rows = release_option_rows(release)
    return write_catalog_rows(rows, catalog_path)


def write_catalog_preserving_nulls(release: Path, catalog_path: Path) -> ConversionResult:
    """Create the largest lossless Nautilus catalog and record unrepresentable bars.

    A Nautilus ``Bar`` requires a Quantity volume.  Canonical provider nulls
    are therefore not coerced to zero; they are listed beside the generated
    catalog so the shortfall is explicit and reproducible.
    """
    rows = release_option_rows(release)
    accepted, rejected = classify_option_rows(rows)
    catalog = write_catalog_rows(accepted, catalog_path)
    (catalog_path / "rejection_ledger.json").write_text(json.dumps(rejected, indent=2) + "\n")
    return ConversionResult(catalog=catalog, rejected_rows=len(rejected), coverage="PARTIAL" if rejected else "COMPLETE")


def write_quality_report(release: Path, report_path: Path) -> dict[str, Any]:
    """Account for all sources and assess rejected-row impact on ATM mappings."""
    rows = release_option_rows(release)
    accepted, rejected = classify_option_rows(rows)
    mapping = pq.read_table(release / "atm_mapping.parquet").to_pylist()
    rejected_keys = {(x["instrument_id"], x["ts_bar_end_utc"]) for x in rejected}
    mapping_overlaps = [
        row
        for row in mapping
        if row["option_bar_end_utc"] is not None
        and (row["contract_instrument_id"], row["option_bar_end_utc"].isoformat()) in rejected_keys
    ]
    by_instrument_session: dict[str, int] = {}
    for row in rejected:
        key = f"{row['provider_instrument_id']}|{row['trading_date_ist']}"
        by_instrument_session[key] = by_instrument_session.get(key, 0) + 1
    report = {
        "source_rows": len(rows),
        "converted_rows": len(accepted),
        "rejected_rows": len(rejected),
        "accounting_invariant_holds": len(rows) == len(accepted) + len(rejected),
        "catalog_coverage": "PARTIAL" if rejected else "COMPLETE",
        "rejections": rejected,
        "rejected_by_instrument_session": by_instrument_session,
        "atm_mapping_rows": len(mapping),
        "mapping_observations_using_rejected_candle": len(mapping_overlaps),
        "mapping_price_available_using_rejected_candle": sum(row["price_available"] for row in mapping_overlaps),
        "mapping_overlaps": [
            {
                "decision_timestamp_utc": row["decision_timestamp_utc"].isoformat(),
                "contract_instrument_id": row["contract_instrument_id"],
                "option_bar_end_utc": row["option_bar_end_utc"].isoformat(),
                "price_available": row["price_available"],
            }
            for row in mapping_overlaps
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def write_catalog_rows(rows: Iterable[dict[str, Any]], catalog_path: Path) -> CatalogVerification:
    """Write a supplied non-null-volume row set and reconcile it exactly."""
    nt = _nt()
    rows = sorted(rows, key=lambda r: (r["provider_instrument_id"], r["ts_bar_end_utc"]))
    catalog_path.mkdir(parents=True, exist_ok=True)
    first_by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        first_by_symbol.setdefault(row["provider_instrument_id"], row)
    instruments = [option_instrument_from_row(row) for _, row in sorted(first_by_symbol.items())]
    catalog = nt["ParquetDataCatalog"](str(catalog_path))
    catalog.write_instruments(instruments)
    # Nautilus' public writer requires a homogeneous bar-type batch.  Each
    # contract's source rows are already time ordered after the deterministic
    # sort above, so write one batch per actual contract.
    for symbol in sorted(first_by_symbol):
        catalog.write_bars([bar_from_row(row) for row in rows if row["provider_instrument_id"] == symbol])
    returned_instruments = catalog.instruments()
    returned_bars = catalog.query_bars()
    expected = [
        (_provider_symbol(r) + ".NSE", _epoch_ns(r["ts_bar_end_utc"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), int(r["volume"]))
        for r in rows
    ]
    actual = sorted(
        [
            # ``float(Quantity)`` can be infinitesimally below an integer for
            # large values.  The public Decimal representation preserves the
            # canonical volume exactly.
            (str(b.bar_type.instrument_id), int(b.ts_event), float(b.open), float(b.high), float(b.low), float(b.close), int(b.volume.as_decimal()))
            for b in returned_bars
        ],
        key=lambda value: (value[0], value[1]),
    )
    expected = sorted(expected, key=lambda value: (value[0], value[1]))
    mismatches = sum(left != right for left, right in zip(expected, actual)) + abs(len(expected) - len(actual))
    return CatalogVerification(len(returned_instruments), len(returned_bars), mismatches)
