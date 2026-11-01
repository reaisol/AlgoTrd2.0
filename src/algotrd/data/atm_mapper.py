"""Point-in-time ATM selection: reference close must precede decision time."""
from bisect import bisect_right
from pathlib import Path
from datetime import timedelta
import pyarrow as pa
import pyarrow.parquet as pq
from .session_policy import classify
def select_atm(price, strikes):
    strikes=sorted(set(strikes)); return min(strikes,key=lambda s:(abs(s-price),s))
def map_atm(cash_rows, decision_ts, contracts, offsets=3):
    eligible=[r for r in cash_rows if r['timestamp_utc'] < decision_ts]
    if not eligible: raise ValueError('no completed reference candle before decision timestamp')
    ref=max(eligible,key=lambda r:r['timestamp_utc']); strikes=sorted({c.strike for c in contracts if c.strike is not None})
    atm=select_atm(ref['close'],strikes); index=strikes.index(atm); chosen=strikes[max(0,index-offsets):index+offsets+1]
    return {'reference_timestamp_utc':ref['timestamp_utc'],'reference_price':ref['close'],'atm_strike':atm,'strikes':chosen}

def build_real_mapping(root: Path, approved_days: set[str], max_age_seconds: int = 60):
    """Read cash/options separately and make backward-only option observations."""
    cash=[]
    for path in (root/'clean/indices').rglob('*.parquet'):
        cash.extend(pq.ParquetFile(path).read(columns=['timestamp_utc','trading_date_ist','close']).to_pylist())
    cash=sorted([r for r in cash if str(r['trading_date_ist']) in approved_days and classify(r['timestamp_utc'])=='REGULAR'],key=lambda r:r['timestamp_utc'])
    if len(cash)!=1875: raise ValueError(f'expected 1875 approved cash rows, got {len(cash)}')
    options=[]
    for path in (root/'clean/options').rglob('*.parquet'):
        options.extend(pq.ParquetFile(path).read().to_pylist())
    ids={r['instrument_id'] for r in options}
    if len(ids)!=22: raise ValueError(f'expected 22 option contracts, got {len(ids)}')
    by={}
    for r in options: by.setdefault(r['instrument_id'],[]).append(r)
    for values in by.values(): values.sort(key=lambda r:r['ts_bar_end_utc'])
    ce={r['strike_price']:r['instrument_id'] for r in options if r['option_type']=='CE'}; pe={r['strike_price']:r['instrument_id'] for r in options if r['option_type']=='PE'}; strikes=sorted(set(ce)&set(pe)); out=[]
    for ref in cash:
        decision=ref['timestamp_utc']+timedelta(minutes=1); atm=select_atm(ref['close'],strikes); index=strikes.index(atm)
        for strike in strikes[max(0,index-3):index+4]:
            for typ,book in [('CE',ce),('PE',pe)]:
                iid=book.get(strike); values=by.get(iid,[]); pos=bisect_right([x['ts_bar_end_utc'] for x in values],decision-timedelta(microseconds=1))-1; bar=values[pos] if pos>=0 else None; age=None if not bar else (decision-bar['ts_bar_end_utc']).total_seconds(); usable=bar is not None and age<=max_age_seconds
                out.append({'decision_timestamp_utc':decision,'reference_timestamp_utc':ref['timestamp_utc'],'reference_price':ref['close'],'expiry':'2026-09-08','atm_strike':atm,'strike_offset':strikes.index(strike)-index,'option_type':typ,'contract_instrument_id':iid,'option_bar_end_utc':None if not bar else bar['ts_bar_end_utc'],'option_reference_price':None if not bar else bar['close'],'option_data_age_seconds':age,'contract_available':iid is not None,'price_available':usable,'source_cash_dataset_version':'cash-working','source_options_dataset_version':'options-working'})
    dest=root/'derived/atm_mapping'; dest.mkdir(parents=True,exist_ok=True); final=dest/'nifty-options-2026-09-5session-pilot.parquet'; tmp=final.with_suffix('.tmp'); pq.write_table(pa.Table.from_pylist(out),tmp,compression='zstd'); tmp.replace(final); return out,final
