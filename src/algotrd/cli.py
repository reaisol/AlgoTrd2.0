from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from .data.collectors.historical import HistoricalCollector
from .data.config import Settings
from .data.providers.groww import GrowwClient
from .data.storage.manifest import Manifest
from .data.releases import create_release, verify_release, publish_release
from .data.validation import validate as validate_rows
from .data.canonical import canonicalize_legacy_row
import pyarrow.parquet as pq
import json
from .data.session_policy import session_report, TIMESTAMP_CONVENTION
from .data.derivatives import extract_list, parse_contract
from .data.storage.raw_writer import write_raw_response
from datetime import datetime, UTC

app = typer.Typer(no_args_is_help=True, help="Read-only Groww NIFTY 50 historical data collector.")


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter("expected ISO date YYYY-MM-DD") from exc


def services() -> tuple[Settings, GrowwClient, Manifest, HistoricalCollector]:
    settings = Settings()
    client = GrowwClient(settings)
    manifest = Manifest(settings.manifest_path)
    return settings, client, manifest, HistoricalCollector(client, settings.algotrd_data_root, manifest)


@app.command("test-connection")
def test_connection() -> None:
    """Validate authentication only; no trading/account endpoints are called."""
    _, client, manifest, _ = services()
    try:
        client.access_token()
        typer.echo("Groww historical-data authentication succeeded.")
    finally:
        client.close(); manifest.close()


@app.command()
def download(
    instrument: str = typer.Option("NIFTY50"), interval: str = typer.Option("1min"),
    start: str = typer.Option(...), end: str = typer.Option(...), dry_run: bool = False,
    refresh: bool = False,
) -> None:
    if instrument != "NIFTY50" or interval != "1min":
        raise typer.BadParameter("Phase 1 supports only --instrument NIFTY50 --interval 1min")
    start_date, end_date = parse_iso_date(start), parse_iso_date(end)
    _, client, manifest, collector = services()
    try:
        completed_end = collector.completed_end(end_date)
        windows = collector.plan(start_date, completed_end) if completed_end >= start_date else []
        if dry_run:
            typer.echo(f"Would request {len(windows)} Groww windows (max 28 calendar days each); no network or files used.")
            return
        result = collector.download(start_date, end_date, refresh=refresh)
        typer.echo(" ".join(f"{key}={value}" for key, value in result.items()))
    finally:
        client.close(); manifest.close()


@app.command()
def status() -> None:
    settings = Settings(); manifest = Manifest(settings.manifest_path)
    try:
        rows = manifest.rows()
        completed = sum(row["status"] == "completed" for row in rows)
        candles = sum((row["candle_count"] or 0) for row in rows if row["status"] == "completed")
        typer.echo(f"requests={len(rows)} completed={completed} candles={candles} data_root={settings.algotrd_data_root}")
    finally:
        manifest.close()

@app.command("validate")
def validate_data(instrument:str=typer.Option("NIFTY50"), interval:str=typer.Option("1min"), start:str=typer.Option(...), end:str=typer.Option(...)) -> None:
    settings=Settings(); rows=[]
    for path in (settings.algotrd_data_root/'clean').rglob('*.parquet'):
        rows.extend(canonicalize_legacy_row(row,'working') for row in pq.ParquetFile(path).read().to_pylist())
    report,bad=validate_rows(rows)
    typer.echo(json.dumps({**report.dict(),'quarantine_candidates':len(bad)}))

@app.command('session-report')
def session_report_command(instrument:str=typer.Option('NIFTY50')):
    settings=Settings(); rows=[]
    for path in (settings.algotrd_data_root/'clean').rglob('*.parquet'):
        rows.extend(pq.ParquetFile(path).read().to_pylist())
    typer.echo(json.dumps({'timestamp_convention':TIMESTAMP_CONVENTION,'sessions':session_report(rows)},default=str))

fno_app=typer.Typer(no_args_is_help=True); app.add_typer(fno_app,name='fno')
def fno_services():
    settings=Settings(); return settings,GrowwClient(settings)
@fno_app.command('expiries')
def fno_expiries(underlying:str=typer.Option('NIFTY'),year:int=typer.Option(...),month:int|None=typer.Option(None)):
    settings,client=fno_services()
    try:
        response=client.expiries(underlying=underlying,year=year,month=month); values=extract_list(response,'expiries')
        raw,_=write_raw_response(settings.algotrd_data_root,request_id=f'expiries-{underlying}-{year}-{month or "all"}',window_start=datetime.now(UTC),response=response,metadata={'provider':'groww','kind':'expiries','underlying':underlying,'year':year,'month':month,'count':len(values)})
        typer.echo(json.dumps({'expiries':values,'raw_file':str(raw)},default=str))
    finally: client.close()
@fno_app.command('contracts')
def fno_contracts(underlying:str=typer.Option('NIFTY'),expiry:str=typer.Option(...)):
    settings,client=fno_services()
    try:
        response=client.contracts(underlying=underlying,expiry=expiry); values=extract_list(response,'contracts'); parsed=[]; rejected=[]
        for value in values:
            try: parsed.append(parse_contract(value).__dict__ | {'instrument_id':parse_contract(value).instrument_id})
            except ValueError as exc: rejected.append({'symbol':value,'error':str(exc)})
        raw,_=write_raw_response(settings.algotrd_data_root,request_id=f'contracts-{underlying}-{expiry}',window_start=datetime.now(UTC),response=response,metadata={'provider':'groww','kind':'contracts','underlying':underlying,'expiry':expiry,'count':len(values)})
        typer.echo(json.dumps({'contracts':parsed,'rejected':rejected,'raw_file':str(raw)},default=str))
    finally: client.close()

dataset_app=typer.Typer(no_args_is_help=True)
app.add_typer(dataset_app,name='dataset')
@dataset_app.command('create')
def dataset_create(instrument:str=typer.Option('NIFTY50'), interval:str=typer.Option('1min'), version:str=typer.Option(...)):
    typer.echo(str(create_release(Settings().algotrd_data_root,version)))
@dataset_app.command('validate')
@dataset_app.command('verify')
def dataset_verify(version:str=typer.Option(...)):
    typer.echo(json.dumps(verify_release(Settings().algotrd_data_root,version),default=str))
@dataset_app.command('publish')
def dataset_publish(version:str=typer.Option(...)):
    typer.echo(json.dumps(publish_release(Settings().algotrd_data_root,version),default=str))


@app.command()
def report(instrument: str = typer.Option("NIFTY50")) -> None:
    if instrument != "NIFTY50":
        raise typer.BadParameter("Phase 1 supports only NIFTY50")
    settings = Settings(); manifest = Manifest(settings.manifest_path)
    try:
        rows = manifest.rows()
        raw_bytes = sum(Path(row["raw_path"]).stat().st_size for row in rows if row["raw_path"] and Path(row["raw_path"]).exists())
        parquet_paths = [path for row in rows if row["parquet_paths"] for path in row["parquet_paths"].split("|")]
        parquet_bytes = sum(Path(path).stat().st_size for path in parquet_paths if Path(path).exists())
        candles = sum((row["candle_count"] or 0) for row in rows if row["status"] == "completed")
        typer.echo(f"completed_requests={sum(row['status'] == 'completed' for row in rows)} candles={candles} raw_bytes={raw_bytes} parquet_bytes={parquet_bytes}")
        typer.echo("Calendar-aware missing-minute analysis is deferred to Phase 2; no missing prices are filled.")
    finally:
        manifest.close()
