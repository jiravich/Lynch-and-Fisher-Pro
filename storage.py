"""Small single-user SQLite persistence layer for the terminal."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "research.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                ticker TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def list_watchlist() -> list[str]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist ORDER BY created_at ASC"
        ).fetchall()
    return [row["ticker"] for row in rows]


def add_watchlist(ticker: str) -> None:
    ticker = ticker.strip().upper()
    if not ticker:
        return
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist (ticker, created_at) VALUES (?, ?)",
            (ticker, datetime.now(timezone.utc).isoformat()),
        )


def remove_watchlist(ticker: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker.strip().upper(),))


def save_note(ticker: str, note: str) -> None:
    ticker = ticker.strip().upper()
    note = note.strip()
    if not ticker or not note:
        return
    init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO research_notes (ticker, note, created_at) VALUES (?, ?, ?)",
            (ticker, note, datetime.now(timezone.utc).isoformat()),
        )


def list_notes(ticker: str, limit: int = 20) -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, note, created_at
            FROM research_notes
            WHERE ticker = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (ticker.strip().upper(), int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]
