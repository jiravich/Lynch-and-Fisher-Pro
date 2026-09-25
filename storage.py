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

            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                framework TEXT NOT NULL,
                topic TEXT NOT NULL,
                statement TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_url TEXT,
                form TEXT,
                filing_date TEXT,
                period TEXT,
                fact_or_inference TEXT NOT NULL,
                polarity TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_evidence_ticker_topic
            ON evidence (ticker, topic);
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


def save_evidence(
    ticker: str,
    framework: str,
    topic: str,
    statement: str,
    source_type: str = "SEC filing",
    source_url: str | None = None,
    form: str | None = None,
    filing_date: str | None = None,
    period: str | None = None,
    fact_or_inference: str = "Fact",
    polarity: str = "Neutral",
) -> None:
    values = [
        ticker.strip().upper(),
        framework.strip(),
        topic.strip(),
        statement.strip(),
        source_type.strip(),
        (source_url or "").strip() or None,
        (form or "").strip() or None,
        (filing_date or "").strip() or None,
        (period or "").strip() or None,
        fact_or_inference.strip(),
        polarity.strip(),
    ]
    if not values[0] or not values[1] or not values[2] or not values[3]:
        return
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO evidence (
                ticker, framework, topic, statement, source_type, source_url,
                form, filing_date, period, fact_or_inference, polarity, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, datetime.now(timezone.utc).isoformat()),
        )


def list_evidence(
    ticker: str,
    topic: str | None = None,
    limit: int = 100,
) -> list[dict]:
    init_db()
    sql = """
        SELECT id, ticker, framework, topic, statement, source_type,
               source_url, form, filing_date, period,
               fact_or_inference, polarity, created_at
        FROM evidence
        WHERE ticker = ?
    """
    params: list[object] = [ticker.strip().upper()]
    if topic:
        sql += " AND topic = ?"
        params.append(topic.strip())
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete_evidence(evidence_id: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM evidence WHERE id = ?", (int(evidence_id),))
