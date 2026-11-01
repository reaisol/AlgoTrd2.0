from datetime import datetime
from pathlib import Path
import pyarrow.parquet as pq
from .releases import verify_release
class HistoricalDataRepository:
 def __init__(self,root:Path): self.root=root
 def get_candles(self,instrument_id:str,start_time:datetime,end_time:datetime,interval:str,dataset_version:str):
  if interval!='1min': raise ValueError('unsupported interval')
  verify_release(self.root,dataset_version)
  return [r for r in pq.ParquetFile(self.root/'releases'/dataset_version/'candles.parquet').read().to_pylist() if r['instrument_id']==instrument_id and start_time<=r['ts_bar_start_utc']<=end_time]
