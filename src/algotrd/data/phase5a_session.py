from __future__ import annotations
import json
from collections import Counter
from datetime import date,time
from pathlib import Path
from zoneinfo import ZoneInfo
import pyarrow.parquet as pq
IST=ZoneInfo('Asia/Kolkata')
def classify(row, eligible):
    local=row['ts_bar_end_utc'].astimezone(IST); d=local.date(); t=local.time()
    if d not in eligible:return 'NON_ELIGIBLE_SESSION'
    if t<time(9,16):return 'BEFORE_REGULAR_WINDOW'
    if t>time(15,30):return 'AFTER_REGULAR_WINDOW'
    return 'REGULAR_SESSION'
def report(root:Path):
    eligible={date(2026,9,d) for d in list(range(1,12))+list(range(15,29))+[30]}
    rows=[]
    for p in (root/'clean/phase5a_options').rglob('*.parquet'):rows+=pq.ParquetFile(p).read().to_pylist()
    ledger=[]; counts=Counter(); null_regular=0
    for r in rows:
      c=classify(r,eligible);counts[c]+=1
      if c=='REGULAR_SESSION' and r['volume'] is None:null_regular+=1
      if c!='REGULAR_SESSION':ledger.append({'instrument_id':r['instrument_id'],'provider_instrument_id':r['provider_instrument_id'],'timestamp_utc':r['ts_bar_end_utc'].isoformat(),'classification':c,'reason':'outside approved 20-session end-labelled research window'})
    out=root/'generated/phase5a';out.mkdir(parents=True,exist_ok=True)
    (out/'option-session-exclusion-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    result={'source_rows':len(rows),'accepted_regular_rows':counts['REGULAR_SESSION'],'excluded_rows':len(ledger),'classifications':dict(counts),'null_volume_regular_rows':null_regular,'accounting_holds':len(rows)==counts['REGULAR_SESSION']+len(ledger)}
    (out/'option-session-report.json').write_text(json.dumps(result,indent=2)+'\n');return result
