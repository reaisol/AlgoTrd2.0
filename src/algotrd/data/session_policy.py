"""Explicit NIFTY cash session classification for Phase 3 research use."""
from collections import defaultdict
from datetime import time
from zoneinfo import ZoneInfo
IST=ZoneInfo("Asia/Kolkata")
TIMESTAMP_CONVENTION="END_LABELED_INFERRED"
def classify(timestamp):
    value=timestamp.astimezone(IST).time()
    if time(9,16)<=value<=time(15,30): return "REGULAR"
    if time(9,0)<=value<=time(9,15): return "PRE_OPEN"
    if time(15,31)<=value<=time(15,59): return "POST_CLOSE"
    return "UNKNOWN"
def session_report(rows):
    report=defaultdict(lambda:{"included":0,"excluded":0,"classifications":defaultdict(int)})
    for row in rows:
        v=report[str(row['trading_date_ist'])]; c=classify(row['timestamp_utc']); v['classifications'][c]+=1; v['included' if c=='REGULAR' else 'excluded']+=1
    return {d:{**v,'classifications':dict(v['classifications'])} for d,v in sorted(report.items())}
