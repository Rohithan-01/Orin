"""SQLite database initialization, connection management, and schema."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from orin.config.settings import get_config_dir


def get_db_path() -> Path:
    """Returns the path to the SQLite database file."""
    custom_path = os.environ.get("ORIN_DB_PATH")
    if custom_path:
        return Path(custom_path).resolve()
    return get_config_dir() / "orin.db"


@contextmanager
def get_db() -> Generator[sqlite3.Connection]:
    """Context manager for SQLite database connection with row factory and WAL mode."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        # Enable WAL mode for high performance concurrent reads and writes
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initializes the database schema if tables do not exist."""
    with get_db() as conn:
        # 1. Conversations table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_session 
            ON conversations (session_id, timestamp);
            """
        )

        # 2. Conversation summaries table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                turns_covered INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 3. User preferences & persistent memory
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 4. Notes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 5. Reminders table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                remind_at DATETIME NOT NULL,
                message TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 6. Task queue table (offline queued tasks)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 7. Audit log table (append-only)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                details TEXT,
                confirmed INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # 8. File index FTS5 table
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS file_index USING fts5(
                path,
                filename,
                extension,
                content,
                modified_time
            );
            """
        )
