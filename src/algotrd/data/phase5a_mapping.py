from bisect import bisect_right
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
import gzip, json
import pyarrow as pa
import pyarrow.parquet as pq
from .phase5a_session import classify
from .session_policy import classify as cash_classify
from .derivatives import extract_list, parse_contract

def build(root: Path, days=None):
    eligible={date(2026,9,d) for d in list(range(1,12))+list(range(15,29))+[30]}
    if days is not None: eligible &= days
    t0=perf_counter(); cash=[]
    for p in (root/'clean/indices/exchange=NSE/instrument=NIFTY50/interval=1min/year=2026/month=09').glob('*.parquet'): cash+=pq.ParquetFile(p).read().to_pylist()
    cash=sorted({r['timestamp_utc']:r for r in cash if r['trading_date_ist'] in eligible and cash_classify(r['timestamp_utc'])=='REGULAR'}.values(),key=lambda r:r['timestamp_utc'])
    # Historical contract discovery, rather than downloaded observations, is
    # authoritative for the strike ladder and individual CE/PE identity.
    registry={}; provenance={}
    for p in (root/'raw/groww/indices/nifty50/year=2026').rglob('response-phase5a-contracts-*.json.gz'):
      with gzip.open(p,'rt') as f: response=json.load(f)['response']
      for value in extract_list(response,'contracts'):
       symbol=value if isinstance(value,str) else value.get('groww_symbol') or value.get('symbol')
       try: c=parse_contract(symbol)
       except ValueError: continue
       if c.asset_class=='OPTION': registry[(c.expiry,c.strike,c.option_type)]=(c.instrument_id,c.provider_symbol);provenance[(c.expiry,c.strike,c.option_type)]=str(p)
    groups={}
    for p in (root/'clean/phase5a_options').rglob('*.parquet'):
      for r in pq.ParquetFile(p).read().to_pylist():
       if classify(r,eligible)=='REGULAR_SESSION':
                groups.setdefault(r['provider_instrument_id'],[]).append(r)
    indexed={}
    for s,rows in groups.items(): rows.sort(key=lambda r:r['ts_bar_end_utc']);indexed[s]=([r['ts_bar_end_utc'] for r in rows],rows)
    expiries=sorted({x[0] for x in registry}); strikes={e:sorted({x[1] for x in registry if x[0]==e}) for e in expiries}; out=[]; read=perf_counter()-t0
    for ref in cash:
      dec=ref['timestamp_utc']+timedelta(minutes=1); exp=next(e for e in expiries if e>=ref['trading_date_ist']); ladder=strikes[exp];atm=min(ladder,key=lambda x:(abs(x-ref['close']),x));i=ladder.index(atm); chosen=ladder[i-3:i+4]
      if len(chosen)!=7:raise ValueError('insufficient ATM ladder')
      for off,strike in zip(range(-3,4),chosen):
       for side in ('CE','PE'):
        inst,sym=registry.get((exp,strike,side),(None,None));bar=None
        if sym:
         ts,rows=indexed[sym];j=bisect_right(ts,dec)-1
         if j>=0 and (dec-ts[j]).total_seconds()<=60:bar=rows[j]
        out.append({'decision_timestamp_utc':dec,'reference_timestamp_utc':ref['timestamp_utc'],'reference_price':ref['close'],'expiry':exp.isoformat(),'atm_strike':atm,'strike_offset':off,'option_type':side,'contract_instrument_id':inst,'provider_instrument_id':sym,'option_bar_end_utc':bar['ts_bar_end_utc'] if bar else None,'option_reference_price':bar['close'] if bar else None,'contract_available':inst is not None,'price_available':bar is not None,'null_volume_source':bool(bar and bar['volume'] is None)})
    stats={'read_seconds':read,'total_seconds':perf_counter()-t0,'cash_rows':len(cash),'mapping_rows':len(out),'provider_listed':sum(x['contract_available'] for x in out),'downloaded_contract':sum(x['provider_instrument_id'] in indexed for x in out),'price_available':sum(x['price_available'] for x in out),'null_volume_source':sum(x['null_volume_source'] for x in out)}
    if days is None:
     p=root/'generated/phase5a/atm_mapping_20sessions.parquet';p.parent.mkdir(parents=True,exist_ok=True);pq.write_table(pa.Table.from_pylist(out),p,compression='zstd')
    return out,stats
