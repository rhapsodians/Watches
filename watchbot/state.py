from __future__ import annotations
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from watchbot.models import Listing


_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_listings (
    dedup_key TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    price_gbp REAL,
    target_reference TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    targets_searched INTEGER,
    total_listings INTEGER,
    new_listings INTEGER,
    errors TEXT
);
"""


class ListingStore:
    def __init__(self, db_path: str = "data/seen_listings.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def is_new(self, listing: Listing) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_listings WHERE dedup_key = ?",
            (listing.dedup_key,)
        ).fetchone()
        return row is None

    def mark_seen(self, listing: Listing, target_reference: str) -> None:
        now = datetime.utcnow().isoformat()
        self._conn.execute("""
            INSERT INTO seen_listings
                (dedup_key, source, url, title, price_gbp, target_reference, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dedup_key) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                price_gbp = excluded.price_gbp,
                title = excluded.title
        """, (
            listing.dedup_key, listing.source, listing.url,
            listing.title, listing.price_gbp, target_reference, now, now
        ))
        self._conn.commit()

    def prune_stale(self, ttl_days: int = 30) -> None:
        cutoff = (datetime.utcnow() - timedelta(days=ttl_days)).isoformat()
        self._conn.execute(
            "DELETE FROM seen_listings WHERE last_seen_at < ?", (cutoff,)
        )
        self._conn.commit()

    def log_run(self, targets: int, total: int, new: int, errors: str) -> None:
        self._conn.execute(
            "INSERT INTO run_log (run_at, targets_searched, total_listings, new_listings, errors) VALUES (?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), targets, total, new, errors)
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
