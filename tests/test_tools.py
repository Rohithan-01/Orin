"""Tests for Orin local system control, notes, reminders, and file tools."""

from pathlib import Path

import pytest

from orin.config.settings import OrinConfig, SecurityConfig
from orin.tools.files import read_file_safe, search_files, write_file_safe
from orin.tools.notes import create_note, delete_note, get_notes, search_notes
from orin.tools.reminders import complete_reminder, create_reminder, get_pending_reminders
from orin.tools.system import (
    format_system_summary,
    get_battery_status,
    get_system_stats,
    launch_app,
)


def test_system_stats_and_battery() -> None:
    bat = get_battery_status()
    assert "has_battery" in bat
    assert "percent" in bat

    stats = get_system_stats()
    assert "cpu_percent" in stats
    assert "memory_percent" in stats
    assert stats["memory_percent"] >= 0

    summary = format_system_summary()
    assert "CPU is at" in summary
    assert "Memory is" in summary


def test_launch_app_security() -> None:
    # Attempting to launch an arbitrary unapproved app must be rejected
    success, msg = launch_app("malware.exe")
    assert success is False
    assert "not in the approved applications list" in msg


def test_notes_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "test_notes.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(test_db))

    note = create_note(content="Buy milk and coffee tomorrow morning", title="Groceries")
    assert note["id"] > 0
    assert note["title"] == "Groceries"

    all_notes = get_notes()
    assert len(all_notes) == 1
    assert all_notes[0]["content"] == "Buy milk and coffee tomorrow morning"

    search_res = search_notes("coffee")
    assert len(search_res) == 1

    search_empty = search_notes("nonexistent_keyword")
    assert len(search_empty) == 0

    deleted = delete_note(note["id"])
    assert deleted is True
    assert len(get_notes()) == 0


def test_reminders_crud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "test_reminders.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(test_db))

    rem = create_reminder(message="Team standup at 10 AM")
    assert rem["id"] > 0
    assert rem["status"] == "pending"

    pending = get_pending_reminders()
    assert len(pending) == 1
    assert pending[0]["message"] == "Team standup at 10 AM"

    done = complete_reminder(rem["id"])
    assert done is True
    assert len(get_pending_reminders()) == 0


def test_safe_file_operations(tmp_path: Path) -> None:
    allowlist_dir = tmp_path / "allowed"
    allowlist_dir.mkdir()
    cfg = OrinConfig(security=SecurityConfig(allowlisted_folders=[str(allowlist_dir)]))

    # Safe write
    target_file = allowlist_dir / "todo.txt"
    succ, msg = write_file_safe(target_file, "1. Task A\n2. Task B", config=cfg)
    assert succ is True
    assert target_file.exists()

    # Safe search
    hits = search_files("todo", config=cfg)
    assert len(hits) == 1
    assert str(target_file) in hits[0]

    # Safe read
    succ, content = read_file_safe(target_file, config=cfg)
    assert succ is True
    assert "Task A" in content
    assert "=== BEGIN UNTRUSTED DATA" in content

    # Rejection of file outside allowlist
    disallowed_file = tmp_path / "forbidden.txt"
    disallowed_file.write_text("secret")
    succ, err = read_file_safe(disallowed_file, config=cfg)
    assert succ is False
    assert "Security Error: Access denied" in err
