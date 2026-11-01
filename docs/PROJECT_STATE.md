# AlgoTrd 2.0 — Phase 1 state

Implemented: a read-only Groww NIFTY 50 one-minute candle collector, immutable gzip raw responses, ZSTD Parquet normalization, SQLite checkpoints, retries, CLI, and unit tests.

Smoke test completed on 2026-10-31: the documented historical endpoint returned 376 NIFTY cash-index one-minute candles for 2025-11-03. The immutable compressed raw response used 5,308 bytes and the canonical ZSTD Parquet output used 11,544 bytes. No invalid OHLC relationship, duplicate timestamp, negative volume, or missing regular-session minute was detected. This is a one-session verification only; the full-year acquisition has not been run.

Instrument mapping is `NIFTY50` → `exchange=NSE`, `segment=CASH`, `groww_symbol=NSE-NIFTY`.

Legacy reconciliation: no prior repository, code, Neon configuration, or 242-session dataset was accessible in this workspace. No legacy data was modified. Reconciliation remains pending until its location or a read-only database credential is provided.

The collector never invokes orders, positions, holdings, funds, or account endpoints. It needs `GROWW_ACCESS_TOKEN` or `GROWW_API_KEY` and `GROWW_API_SECRET` supplied through environment variables or an untracked `.env` file.

The requested range extends through 2026-10-31. The collector fetches only what Groww returns; reporting and no-data windows must be reviewed before claiming all sessions are complete. Qlib, NautilusTrader, futures/options collection, strategy, and execution work remain out of scope for Phase 1.

## Phase 2 state

Canonical schema v2, index identity `NSE:INDEX:NIFTY50`, session-aware validation, immutable release manifests, deterministic repository reads, and the separate Neon `algotrd_data` metadata schema are implemented. The one-session sample validated 376 of 376 expected bars with no duplicates, gaps, or quarantined rows. `nifty50-cash-1min-v1` is a checksum-verified **DRAFT** only; it has not been published because the requested one-year coverage has not been collected. Groww's documentation does not prove live availability timing, so canonical `ts_available_utc` remains null. Existing Neon public tables were inspected and not altered.
# Phase 4A engineering integration (2026-10-31)

- Input release remains `nifty-options-2026-09-5session-pilot-v3` (DRAFT,
  engineering-only); generated framework artifacts are outside the release.
- NautilusTrader 2.0.0rc8: the real 24050 CE contract completed an exact
  1,875-bar public `ParquetDataCatalog` round trip.  The full catalog has 22
  instruments and 36,011 losslessly represented bars.  Twenty-four canonical
  rows have null source volume and are explicitly listed in
  `data/generated/nautilus-v3-catalog-nonnull-final/rejected_null_volume.json`;
  they are not converted to zero because `Bar` requires a Quantity.
- Nautilus instrument conventions are engineering-only: unknown historical
  activation is represented by `activation_ns=0`, and `multiplier=1` is
  provisional.  The historical lot size remains 65.  These are not approved
  for execution-grade P&L.
- Qlib 0.9.7 export is in `data/generated/qlib-v3-cash`: 1,875 UTC-naive
  calendar timestamps that represent the original UTC instants, and factor=1
  for the unadjusted NIFTY index series.  Qlib's documented binary storage is
  float32, so it reconciles exactly at float32 precision, not original
  float64 precision.
- Phase 4A quality accounting: `36,035 = 36,011 converted + 24 rejected`.
  The generated catalog coverage is **PARTIAL**.  All 24 rejected rows have
  null canonical volume; no null was replaced with zero.  The rejection and
  ATM-impact reports are generated beside the catalog.  Ten timestamp-eligible
  ATM observations use one of these candles and are therefore unavailable as
  full Nautilus OHLCV bars, although their immutable mapping records remain.
- Qlib reconciliation has zero timestamp, instrument, or float32-representation
  mismatches.  Against original float64 OHLC, the maximum absolute error is
  0.0007812500007275958 and the median is 0.0003906249985448085.  This is below
  the verified 0.05 option tick, but it is a storage precision property, not a
  market-price adjustment. Cash index volume is unavailable and exports as NaN.

## Phase 5A dry-run (2026-11-01)

- Official NSE September calendar inventory: 21 expected sessions (Ganesh
  Chaturthi, 14 September, excluded); 20 have 375 regular end-labelled cash
  candles.  September 29 has 289, leaving 86 missing records.
- A bounded Groww repair request for September 29 14:00–15:30 IST returned
  only five already-held candles (14:00–14:04), not the missing interval. Its
  immutable raw response is retained and the source gap is unresolved.
- Groww discovery reported five expiries (1, 8, 15, 22, 29 September) and 383
  option contracts across their ladders.  No September option expansion,
  release, Qlib export, or Nautilus catalog was created because cash reference
  completeness is a mandatory gate.

