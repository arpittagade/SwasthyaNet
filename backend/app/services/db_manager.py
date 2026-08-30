from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

DATABASE_PATH = os.getenv("DATABASE_PATH", "/tmp/swasthyanet.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS simulation_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    day TEXT NOT NULL,
    tick INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS phc_nodes (
    phc_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not already exist. Safe to call on every startup."""
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.Error:
        # Persistence is a nice-to-have for the demo; never let a DB issue
        # prevent the API from starting with fresh in-memory state.
        pass


def save_state(day: str, tick: int, phcs: list[dict]) -> bool:
    """Persist the current simulation snapshot. Returns True on success."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO simulation_meta (id, day, tick) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET day = excluded.day, tick = excluded.tick",
                (day, tick),
            )
            for phc in phcs:
                conn.execute(
                    "INSERT INTO phc_nodes (phc_id, payload) VALUES (?, ?) "
                    "ON CONFLICT(phc_id) DO UPDATE SET payload = excluded.payload",
                    (phc["id"], json.dumps(phc)),
                )
            conn.commit()
        return True
    except sqlite3.Error:
        return False


def load_state() -> tuple[str, int, list[dict]] | None:
    """Load a previously persisted snapshot. Returns None if nothing is stored
    or a DB error occurs, so callers can fall back to seeding fresh state."""
    try:
        with _connect() as conn:
            meta_row = conn.execute("SELECT day, tick FROM simulation_meta WHERE id = 1").fetchone()
            if not meta_row:
                return None
            day, tick = meta_row
            phc_rows = conn.execute("SELECT payload FROM phc_nodes").fetchall()
            if not phc_rows:
                return None
            phcs = [json.loads(row[0]) for row in phc_rows]
            return day, tick, phcs
    except (sqlite3.Error, json.JSONDecodeError, KeyError):
        return None
