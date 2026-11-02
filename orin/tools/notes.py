"""Notes management tool storing notes locally in SQLite."""

from __future__ import annotations

from typing import Any

from orin.memory.db import get_db, init_db


def create_note(content: str, title: str = "") -> dict[str, Any]:
    """Saves a new note to the database.

    If title is empty, extracts the first few words as the title.
    """
    init_db()
    clean_content = content.strip()
    if not clean_content:
        raise ValueError("Note content cannot be empty.")

    note_title = title.strip()
    if not note_title:
        words = clean_content.split()
        note_title = " ".join(words[:5]) + ("..." if len(words) > 5 else "")

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?);",
            (note_title, clean_content),
        )
        note_id = cur.lastrowid or 0

    return {
        "id": note_id,
        "title": note_title,
        "content": clean_content,
        "status": "created",
    }


def get_notes(limit: int = 10) -> list[dict[str, Any]]:
    """Retrieves recent notes in reverse chronological order."""
    init_db()
    with get_db() as conn:
        cur = conn.execute(
            "SELECT id, title, content, created_at FROM notes ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "Untitled",
                "content": r["content"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


def search_notes(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Searches notes by keyword in title or content."""
    init_db()
    clean_q = f"%{query.strip()}%"
    with get_db() as conn:
        cur = conn.execute(
            """
            SELECT id, title, content, created_at
            FROM notes
            WHERE title LIKE ? OR content LIKE ?
            ORDER BY id DESC
            LIMIT ?;
            """,
            (clean_q, clean_q, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "Untitled",
                "content": r["content"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]


def delete_note(note_id: int) -> bool:
    """Deletes a note by its ID."""
    init_db()
    with get_db() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?;", (note_id,))
        return cur.rowcount > 0
