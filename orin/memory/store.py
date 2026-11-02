"""Conversation memory and persistent user preferences store."""

from __future__ import annotations

from orin.memory.db import get_db, init_db


class MemoryStore:
    """Manages conversational history, rolling summaries, and user preferences in SQLite."""

    def __init__(self) -> None:
        init_db()

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        """Stores a single message turn in the conversations table."""
        with get_db() as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, role, content) VALUES (?, ?, ?);",
                (session_id, role, content),
            )

    def get_recent_turns(self, session_id: str, limit: int = 10) -> list[dict[str, str]]:
        """Retrieves the most recent `limit` turns for a session in chronological order."""
        with get_db() as conn:
            cur = conn.execute(
                """
                SELECT role, content FROM (
                    SELECT role, content, id 
                    FROM conversations 
                    WHERE session_id = ? 
                    ORDER BY id DESC 
                    LIMIT ?
                ) ORDER BY id ASC;
                """,
                (session_id, limit),
            )
            rows = cur.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def get_turn_count(self, session_id: str) -> int:
        """Counts total turns in the current session."""
        with get_db() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) as cnt FROM conversations WHERE session_id = ?;",
                (session_id,),
            )
            row = cur.fetchone()
            return row["cnt"] if row else 0

    def get_latest_summary(self, session_id: str) -> str | None:
        """Retrieves the most recent rolling summary for the session, if one exists."""
        with get_db() as conn:
            cur = conn.execute(
                """
                SELECT summary FROM summaries 
                WHERE session_id = ? 
                ORDER BY id DESC 
                LIMIT 1;
                """,
                (session_id,),
            )
            row = cur.fetchone()
            return row["summary"] if row else None

    def save_summary(self, session_id: str, summary: str, turns_covered: int) -> None:
        """Records a generated summary of older turns."""
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO summaries (session_id, summary, turns_covered) 
                VALUES (?, ?, ?);
                """,
                (session_id, summary, turns_covered),
            )

    def get_older_unsummarized_turns(
        self, session_id: str, keep_recent: int = 10
    ) -> list[dict[str, str]]:
        """Gets turns that are older than the most recent `keep_recent` turns to summarize."""
        total = self.get_turn_count(session_id)
        if total <= keep_recent:
            return []

        older_count = total - keep_recent
        with get_db() as conn:
            cur = conn.execute(
                """
                SELECT role, content FROM conversations 
                WHERE session_id = ? 
                ORDER BY id ASC 
                LIMIT ?;
                """,
                (session_id, older_count),
            )
            rows = cur.fetchall()
            return [{"role": r["role"], "content": r["content"]} for r in rows]

    def set_preference(self, key: str, value: str) -> None:
        """Stores or updates a persistent user preference / fact."""
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences (key, value, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET 
                    value = excluded.value, 
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (key.strip().lower(), value.strip()),
            )

    def get_preference(self, key: str, default: str = "") -> str:
        """Retrieves a single user preference."""
        with get_db() as conn:
            cur = conn.execute(
                "SELECT value FROM user_preferences WHERE key = ?;",
                (key.strip().lower(),),
            )
            row = cur.fetchone()
            return row["value"] if row else default

    def get_all_preferences(self) -> dict[str, str]:
        """Returns all stored user preferences as a dictionary."""
        with get_db() as conn:
            cur = conn.execute("SELECT key, value FROM user_preferences ORDER BY key ASC;")
            rows = cur.fetchall()
            return {r["key"]: r["value"] for r in rows}

    def clear_session(self, session_id: str) -> None:
        """Deletes conversation turns and summaries for a given session."""
        with get_db() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id = ?;", (session_id,))
            conn.execute("DELETE FROM summaries WHERE session_id = ?;", (session_id,))


_global_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """Singleton getter for MemoryStore."""
    global _global_memory_store
    if _global_memory_store is None:
        _global_memory_store = MemoryStore()
    return _global_memory_store
