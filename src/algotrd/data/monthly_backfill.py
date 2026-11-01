"""Bounded monthly historical backfill entrypoint.

October execution deliberately stops after its one requested month; it never
chains into a year-long job.
"""
from __future__ import annotations
import argparse, json, shutil
from datetime import date
from pathlib import Path
from .calendar import KNOWN_HOLIDAYS
from .monthly_inventory import expected_weekdays

MIN_FREE_GB=8
def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--month',required=True);p.add_argument('--dry-run',action='store_true');a=p.parse_args(argv)
 year,month=map(int,a.month.split('-')); root=Path('data'); free=shutil.disk_usage(root).free/1024**3
 if free<MIN_FREE_GB: raise SystemExit(f'insufficient free space: {free:.2f} GB')
 import calendar
 sessions=expected_weekdays(date(year,month,1),date(year,month,calendar.monthrange(year,month)[1]),KNOWN_HOLIDAYS)
 report={'month':a.month,'sessions_expected':len(sessions),'free_gb_before':free,'status':'DRY_RUN' if a.dry_run else 'NOT_IMPLEMENTED','safeguard':'no multi-month continuation'}
 (root/'generated/phase5b').mkdir(parents=True,exist_ok=True);(root/'generated/phase5b'/f'{a.month}-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 if not a.dry_run: raise SystemExit('October collection adapter requires verified calendar/provider normalization wiring before live execution')
if __name__=='__main__':main()
