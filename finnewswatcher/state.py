from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from contextlib import closing


DB_PATH = os.environ.get(
    "FNW_STATE_DB",
    os.path.expanduser("~/.finnewswatcher/state.db")
)


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS sent (key TEXT PRIMARY KEY, ts INTEGER)")
    return conn


def make_key(source_name:str, headline:str) -> str:
    h = hashlib.sha256()
    h.update(source_name.encode("utf-8"))
    h.update(b"|")
    h.update(headline.strip().lower().encode("utf-8"))
    return h.hexdigest()


def was_sent(source_name:str, headline:str) -> bool:
    key = make_key(source_name, headline)
    with _conn() as c:
        cur = c.execute("SELECT 1 FROM sent WHERE key=?", (key,))
        return cur.fetchone() is not None
    
def mark_sent(source_name:str, headline:str) -> None:
    key = make_key(source_name, headline)
    ts = int(time.time())
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO sent(key, ts) VALUES (?, ?)", (key, ts))