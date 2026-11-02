"""Reminders management tool storing reminders and alarms in SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from orin.memory.db import get_db, init_db


def create_reminder(message: str, remind_at: str | datetime | None = None) -> dict[str, Any]:
    """Creates a reminder with a scheduled time string (ISO format or parsed).

    If remind_at is None, defaults to 1 hour from current time.
    """
    init_db()
    clean_msg = message.strip()
    if not clean_msg:
        raise ValueError("Reminder message cannot be empty.")

    if remind_at is None:
        target_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(remind_at, datetime):
        target_time = remind_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        target_time = str(remind_at).strip()

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (remind_at, message, status) VALUES (?, ?, 'pending');",
            (target_time, clean_msg),
        )
        rem_id = cur.lastrowid or 0

    return {
        "id": rem_id,
        "message": clean_msg,
        "remind_at": target_time,
        "status": "pending",
    }


def get_pending_reminders(limit: int = 10) -> list[dict[str, Any]]:
    """Retrieves all active pending reminders ordered by remind_at."""
    init_db()
    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT id, remind_at, message, status, created_at
            FROM reminders
            WHERE status = 'pending'
            ORDER BY remind_at ASC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "remind_at": str(r["remind_at"]),
                "message": r["message"],
                "status": r["status"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


def complete_reminder(reminder_id: int) -> bool:
    """Marks a reminder as completed."""
    init_db()
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE reminders SET status = 'completed' WHERE id = ?;",
            (reminder_id,),
        )
        return cur.rowcount > 0
