from __future__ import annotations
import hashlib,json,os
from datetime import UTC,datetime
from pathlib import Path
import pyarrow as pa, pyarrow.parquet as pq
from .canonical import CANONICAL_SCHEMA, CANONICAL_SCHEMA_VERSION, canonicalize_legacy_row
from .validation import validate

def digest(path:Path)->str:
 h=hashlib.sha256();
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 return h.hexdigest()
def create_release(root:Path,version:str)->Path:
 target=root/'releases'/version
 if target.exists(): raise FileExistsError(f'release already immutable: {version}')
 source=list((root/'clean').rglob('*.parquet'))
 if not source: raise FileNotFoundError('no Phase 1 parquet partitions')
 rows=[]
 for p in source: rows += [canonicalize_legacy_row(r,version) for r in pq.ParquetFile(p).read().to_pylist()]
 report,bad=validate(rows)
 if bad: raise ValueError(f'publication blocked: {len(bad)} invalid candle(s)')
 target.mkdir(parents=True); data=target/'candles.parquet'; tmp=target/'candles.tmp'
 pq.write_table(pa.Table.from_pylist(sorted(rows,key=lambda r:r['ts_bar_start_utc']),schema=CANONICAL_SCHEMA),tmp,compression='zstd'); os.replace(tmp,data)
 manifest={'dataset_version':version,'status':'DRAFT','schema_version':CANONICAL_SCHEMA_VERSION,'created_at_utc':datetime.now(UTC).isoformat(),'partitions':[{'path':'candles.parquet','sha256':digest(data),'rows':len(rows)}],'quality':report.dict(),'source_partitions':[{'path':str(p),'sha256':digest(p)} for p in source]}
 (target/'manifest.json').write_text(json.dumps(manifest,indent=2,default=str)); return target
def verify_release(root:Path,version:str)->dict:
 target=root/'releases'/version; manifest=json.loads((target/'manifest.json').read_text())
 for part in manifest['partitions']:
  if digest(target/part['path']) != part['sha256']: raise ValueError('checksum mismatch')
 return manifest
def publish_release(root:Path,version:str)->dict:
 m=verify_release(root,version)
 if m['quality']['quarantined'] or m['quality']['missing'] or m['quality']['unverified_sessions']: raise ValueError('publication blocked by incomplete or unverified coverage')
 m['status']='APPROVED';m['published_at_utc']=datetime.now(UTC).isoformat();(root/'releases'/version/'manifest.json').write_text(json.dumps(m,indent=2));return m
