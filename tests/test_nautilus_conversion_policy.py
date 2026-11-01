from pathlib import Path

from algotrd.adapters.nautilus_adapter import classify_option_rows, release_option_rows, write_quality_report


RELEASE = Path("data/releases/nifty-options-2026-09-5session-pilot-v3")


def test_null_volume_policy_accounts_for_every_immutable_option_row(tmp_path):
    rows = release_option_rows(RELEASE)
    accepted, rejected = classify_option_rows(rows)

    assert len(rows) == 36_035
    assert len(accepted) == 36_011
    assert len(rejected) == 24
    assert len(rows) == len(accepted) + len(rejected)
    assert {row["reason"] for row in rejected} == {"canonical volume is null; Nautilus Bar requires Quantity"}

    report = write_quality_report(RELEASE, tmp_path / "quality.json")
    assert report["accounting_invariant_holds"] is True
    assert report["catalog_coverage"] == "PARTIAL"
