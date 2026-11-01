from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class Manifest:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, instrument TEXT NOT NULL, start_at TEXT NOT NULL,
                end_at TEXT NOT NULL, interval TEXT NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, candle_count INTEGER, raw_path TEXT,
                parquet_paths TEXT, checksum TEXT, error_classification TEXT, last_attempted_at TEXT
            )
        """)
        self.conn.commit()

    def completed(self, request_id: str) -> bool:
        row = self.conn.execute("SELECT status FROM requests WHERE request_id = ?", (request_id,)).fetchone()
        return row is not None and row["status"] == "completed"

    def started(self, request_id: str, instrument: str, start_at: str, end_at: str, interval: str) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute("""
            INSERT INTO requests(request_id, instrument, start_at, end_at, interval, status, attempts, last_attempted_at)
            VALUES (?, ?, ?, ?, ?, 'running', 1, ?)
            ON CONFLICT(request_id) DO UPDATE SET status='running', attempts=attempts + 1, last_attempted_at=excluded.last_attempted_at
        """, (request_id, instrument, start_at, end_at, interval, now))
        self.conn.commit()

    def complete(self, request_id: str, candle_count: int, raw_path: Path, parquet_paths: list[Path], checksum: str) -> None:
        self.conn.execute("""
            UPDATE requests SET status='completed', candle_count=?, raw_path=?, parquet_paths=?, checksum=?, error_classification=NULL
            WHERE request_id=?
        """, (candle_count, str(raw_path), "|".join(map(str, parquet_paths)), checksum, request_id))
        self.conn.commit()

    def failed(self, request_id: str, error: Exception) -> None:
        self.conn.execute("UPDATE requests SET status='failed', error_classification=? WHERE request_id=?", (type(error).__name__, request_id))
        self.conn.commit()

    def rows(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM requests ORDER BY start_at").fetchall()

    def close(self) -> None:
        self.conn.close()
