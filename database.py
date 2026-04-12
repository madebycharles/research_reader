import sqlite3
import json
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DB_PATH = Path("data/reader.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                filename    TEXT NOT NULL,
                sections    TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS voices (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                filename    TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS progress (
                paper_id        TEXT PRIMARY KEY,
                section_idx     INTEGER NOT NULL DEFAULT 0,
                paragraph_idx   INTEGER NOT NULL DEFAULT 0,
                updated_at      TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(id)
            );
        """)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
