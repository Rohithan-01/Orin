"""Tests for SQLite memory store and conversation persistence."""

from pathlib import Path

from orin.memory.db import get_db, init_db
from orin.memory.store import MemoryStore


def test_init_db(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_orin.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    init_db()
    assert db_file.exists()

    with get_db() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "conversations" in table_names
        assert "summaries" in table_names
        assert "user_preferences" in table_names
        assert "file_index" in table_names


def test_add_and_get_turns(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_orin.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    store = MemoryStore()
    session_id = "test-session-1"

    # Add 12 turns
    for i in range(12):
        role = "user" if i % 2 == 0 else "assistant"
        store.add_turn(session_id, role, f"Message {i}")

    assert store.get_turn_count(session_id) == 12

    # Verify limit of 10 returns the last 10 in chronological order
    recent = store.get_recent_turns(session_id, limit=10)
    assert len(recent) == 10
    assert recent[0]["content"] == "Message 2"
    assert recent[-1]["content"] == "Message 11"


def test_preferences(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_orin.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    store = MemoryStore()
    store.set_preference("favorite_color", "blue")
    assert store.get_preference("favorite_color") == "blue"

    # Update preference
    store.set_preference("favorite_color", "midnight blue")
    assert store.get_preference("favorite_color") == "midnight blue"

    all_prefs = store.get_all_preferences()
    assert "favorite_color" in all_prefs
    assert all_prefs["favorite_color"] == "midnight blue"


def test_rolling_summary_storage(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_orin.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    store = MemoryStore()
    session = "summary-session"

    assert store.get_latest_summary(session) is None

    store.save_summary(session, "User discussed Python and local LLMs.", turns_covered=6)
    latest = store.get_latest_summary(session)
    assert latest == "User discussed Python and local LLMs."


def test_clear_session(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_orin.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(db_file))

    store = MemoryStore()
    session = "clear-session"

    store.add_turn(session, "user", "Hello")
    store.save_summary(session, "Summary", turns_covered=1)
    assert store.get_turn_count(session) == 1

    store.clear_session(session)
    assert store.get_turn_count(session) == 0
    assert store.get_latest_summary(session) is None
