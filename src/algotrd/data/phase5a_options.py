"""Resumable bounded September-2026 NIFTY option collection."""
from __future__ import annotations
import gzip, hashlib, json
from datetime import UTC, date, datetime, time
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from .config import Settings
from .derivatives import parse_contract
from .providers.groww import GrowwClient
from .storage.raw_writer import write_raw_response
from .schemas.candle import IST

def run(root: Path) -> dict:
    inventory=json.loads((root/'generated/phase5a/option-inventory.json').read_text())['contracts']
    checkpoint=root/'generated/phase5a/option-checkpoints.json'; state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    client=GrowwClient(Settings()); totals={'requested':0,'success':0,'failed':0,'rows':0,'skipped':0}
    try:
      for symbol in inventory:
        key=hashlib.sha256(symbol.encode()).hexdigest()[:16]
        if state.get(symbol,{}).get('status')=='COMPLETE' and Path(state[symbol]['parquet']).exists(): totals['skipped']+=1; continue
        c=parse_contract(symbol); start=max(date(2026,9,1), c.expiry.replace(day=1)); end=min(date(2026,9,30), c.expiry)
        # October expiry is only relevant to Sep-30; earlier expiries are bounded at expiry.
        if c.expiry.month==10: start=end=date(2026,9,30)
        s=datetime.combine(start,time(9,15),IST); e=datetime.combine(end,time(15,30),IST); totals['requested']+=1
        try:
          rsp=client.historical_candles(groww_symbol=symbol,start=s,end=e,segment='FNO')
          payload=rsp.get('payload',rsp); candles=payload.get('candles',[])
          raw,sha=write_raw_response(root,request_id='phase5a-option-'+key,window_start=s,response=rsp,metadata={'provider':'groww','symbol':symbol,'segment':'FNO','start':s.isoformat(),'end':e.isoformat(),'count':len(candles)})
          out=[]
          for x in candles:
            ts=datetime.fromisoformat(x[0]).replace(tzinfo=IST).astimezone(UTC) if isinstance(x[0],str) else datetime.fromtimestamp(x[0],UTC)
            out.append({'instrument_id':c.instrument_id,'provider_instrument_id':symbol,'contract_expiry':c.expiry,'strike_price':c.strike,'option_type':c.option_type,'ts_bar_end_utc':ts,'open':x[1],'high':x[2],'low':x[3],'close':x[4],'volume':x[5] if len(x)>5 else None,'open_interest':x[6] if len(x)>6 else None,'source':'groww','source_timestamp_raw':str(x[0])})
          path=root/f'clean/phase5a_options/expiry={c.expiry}/option_type={c.option_type}/strike={c.strike:g}/part-{key}.parquet'; path.parent.mkdir(parents=True,exist_ok=True); pq.write_table(pa.Table.from_pylist(out),path,compression='zstd')
          state[symbol]={'status':'COMPLETE','raw':str(raw),'raw_sha256':sha,'parquet':str(path),'rows':len(out)}; totals['success']+=1;totals['rows']+=len(out)
        except Exception as exc:
          state[symbol]={'status':'FAILED','error':str(exc)};totals['failed']+=1
        checkpoint.write_text(json.dumps(state,indent=2)+'\n')
    finally: client.close()
    return totals
