from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def write_raw_response(root: Path, *, request_id: str, window_start: datetime, response: dict[str, Any], metadata: dict[str, Any]) -> tuple[Path, str]:
    """Write a unique immutable gzip JSON envelope atomically; never replace a raw response."""
    directory = root / "raw" / "groww" / "indices" / "nifty50" / f"year={window_start.year}" / f"month={window_start.month:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    final = directory / f"response-{request_id}.json.gz"
    suffix = 1
    while final.exists():
        final = directory / f"response-{request_id}-v{suffix}.json.gz"
        suffix += 1
    envelope = {"metadata": {**metadata, "downloaded_at_utc": datetime.now(UTC).isoformat()}, "response": response}
    raw = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode()
    temp = final.with_suffix(final.suffix + ".tmp")
    with gzip.open(temp, "wb", compresslevel=9) as handle:
        handle.write(raw)
    os.replace(temp, final)
    return final, hashlib.sha256(raw).hexdigest()
