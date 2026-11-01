# AlgoTrd 2.0 — Repository-wide agent instructions

This repository is a research-first historical-market-data system for NIFTY 50 cash and NSE NIFTY CE/PE options. Verify current local code, manifests, checkpoints, tests, and checksums before relying on prior progress reports.

Never manufacture prices, candles, volume, contracts, order-book data, fills, or coverage. Do not perform live trading, broker order placement, ML training, or profitability backtests without explicit separate authorization and required data validation.

## Source of truth

1. Checked-out code, tests, manifests, CLI/checkpoint state, and verified checksums.
2. Archived Groww responses, contract-discovery registry, and request provenance.
3. Canonical Parquet, session/rejection/mapping-quality reports.
4. Reproducible Qlib and NautilusTrader outputs, never master source data.
5. Historical notes, which may be stale.

Never commit raw market data, credentials, generated catalogs, or large files without permission.

## Non-negotiable data semantics

- Store timestamps UTC-aware; interpret NSE sessions in `Asia/Kolkata`.
- Approved end-labelled research window: 09:16–15:30 IST inclusive, 375 candles per complete session.
- Keep raw out-of-window data, but classify it as outside the approved window; do not assert verified pre-open/post-close semantics.
- Use the latest strictly earlier cash candle at each decision timestamp.
- Build expiry, strike ladders, and CE/PE identities from archived historical contract discovery, never downloaded bars.
- Select ATM plus three actual listed strikes either side; retain all 14 potential CE/PE slots with explicit unavailable reasons.
- Option pricing is backward-as-of only, age no more than 60 seconds, never future data.
- Validate option prices on the ₹0.05 grid using `Decimal`.
- `volume=None` means unknown, never zero. Nautilus bars require non-null volume, so reject such bars deterministically while preserving canonical data and mapping availability.
- Historical API listing does not prove activation, exchange tradability, or executable fills.

## Pipeline

Groww raw responses + metadata → canonical Parquet → archived historical contract registry → point-in-time ATM±3 mapping → atomic immutable DRAFT release → Qlib/Nautilus generated outputs.

Neon is an audit/metadata store, not a replacement for immutable Parquet.

## Phase 5B monthly backfill

The intended state machine is:

`PREFLIGHT → CASH → DISCOVERY → INVENTORY → OPTIONS → VALIDATION → MAPPING → RELEASE → QLIB → NAUTILUS → COMPLETE`

Every stage must persist and verify its artifacts before it is skipped on rerun. `--dry-run` must not collect or publish. Only the requested month may run; never automatically launch a year-long backfill. Keep at least 8 GB free space.

For CASH, deduplicate by instrument/timestamp and mark each session COMPLETE only with 375 approved one-minute bars. Preserve incomplete-session raw evidence and exclude it from complete-session research.

For DISCOVERY, archive expiry and contract responses, including following-month expiries needed for rollover. For OPTIONS, retain raw-response SHA-256 checkpoints, rate limiting, bounded retries, and idempotent verified skips. Never silently skip failures.

For RELEASE, use same-filesystem atomic staging/rename, never overwrite an immutable release, and label partial coverage truthfully as `DRAFT — PARTIAL COVERAGE — ENGINEERING ONLY`.

## Frameworks

- `.venv312`: primary collector runtime.
- `.venv-qlib`: Qlib 0.9.7. Its binary features are float32; compare to expected float32 input, report float64 residuals, and preserve cash null volume as NaN.
- `.venv-nautilus314`: NautilusTrader 2.0.0rc8. Use public imports from `nautilus_trader.model` and `nautilus_trader.persistence`.

Nautilus instruments remain engineering-only where `activation_ns=0` or `multiplier=1` is provisional. Never use them for execution-grade P&L claims.

## Security and discipline

Keep Groww credentials only in environment or untracked files. Never print or commit them. Only call read-only historical endpoints; never call orders, positions, holdings, or funds endpoints. Update `docs/PROJECT_STATE.md` with verified state and blockers.
