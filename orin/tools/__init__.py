"""Tools subsystem for Orin: system control, notes, reminders, files, and indexer."""

from orin.tools.files import read_file_safe, search_files, write_file_safe
from orin.tools.indexer import FileIndexer, get_file_indexer
from orin.tools.notes import create_note, delete_note, get_notes, search_notes
from orin.tools.reminders import complete_reminder, create_reminder, get_pending_reminders
from orin.tools.system import (
    format_system_summary,
    get_battery_status,
    get_system_stats,
    launch_app,
    mute_system_volume,
    set_system_volume,
)

__all__ = [
    "get_battery_status",
    "get_system_stats",
    "format_system_summary",
    "set_system_volume",
    "mute_system_volume",
    "launch_app",
    "create_note",
    "get_notes",
    "search_notes",
    "delete_note",
    "create_reminder",
    "get_pending_reminders",
    "complete_reminder",
    "search_files",
    "read_file_safe",
    "write_file_safe",
    "FileIndexer",
    "get_file_indexer",
]
