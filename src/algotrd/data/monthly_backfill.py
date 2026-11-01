"""Checkpointed, single-month backfill orchestrator."""
from __future__ import annotations
import argparse,json,shutil
from datetime import date
from pathlib import Path
from .calendar import KNOWN_HOLIDAYS
from .monthly_inventory import expected_weekdays
from .config import Settings
from .providers.groww import GrowwClient
from .collectors.historical import HistoricalCollector
from .storage.manifest import Manifest
STAGES=('PREFLIGHT','CASH','DISCOVERY','INVENTORY','OPTIONS','VALIDATION','MAPPING','RELEASE','QLIB','NAUTILUS','COMPLETE')
MIN_FREE_GB=8
def state_path(root,month):return root/'generated/phase5b'/f'{month}-state.json'
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args(argv)
 try:y,m=map(int,a.month.split('-'));assert 1<=m<=12
 except Exception:raise SystemExit('--month must be YYYY-MM')
 root=Path('data');root.joinpath('generated/phase5b').mkdir(parents=True,exist_ok=True);free=shutil.disk_usage(root).free/2**30
 if free<MIN_FREE_GB:raise SystemExit(f'insufficient free space: {free:.2f} GB')
 import calendar
 sessions=expected_weekdays(date(y,m,1),date(y,m,calendar.monthrange(y,m)[1]),KNOWN_HOLIDAYS)
 path=state_path(root,a.month);state=json.loads(path.read_text()) if path.exists() else {'month':a.month,'completed':[]}
 report={'month':a.month,'sessions_expected':len(sessions),'free_gb':free,'state_machine':STAGES,'completed':state['completed'],'dry_run':a.dry_run}
 if 'PREFLIGHT' not in state['completed']:state['completed'].append('PREFLIGHT')
 path.write_text(json.dumps(state,indent=2)+'\n')
 print(json.dumps(report))
 if a.dry_run:return
 # CASH is deliberately bounded to this month; durable manifest rows make a
 # repeated invocation skip checksum-recorded windows.
 if 'CASH' not in state['completed']:
  client=GrowwClient(Settings()); manifest=Manifest(root/'manifests/ingestion.sqlite3')
  try: cash=HistoricalCollector(client,root,manifest).download(date(y,m,1),date(y,m,calendar.monthrange(y,m)[1]))
  finally: client.close();manifest.close()
  if cash['invalid']:raise SystemExit(f'cash validation failed: {cash}')
  state['cash']=cash;state['completed'].append('CASH');path.write_text(json.dumps(state,indent=2)+'\n')
 raise SystemExit('CASH complete; DISCOVERY/INVENTORY/OPTIONS require the month-independent contract registry adapter')
if __name__=='__main__':main()
