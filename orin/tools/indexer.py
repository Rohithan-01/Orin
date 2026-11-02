"""Local full-text file indexer using SQLite FTS5 for lightning-fast search in allowlisted folders."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from orin.config.settings import OrinConfig, get_config
from orin.memory.db import get_db, init_db
from orin.security.policy import is_path_allowlisted

INDEXABLE_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".csv",
    ".log",
    ".yaml",
    ".yml",
    ".toml",
    ".rst",
    ".html",
    ".xml",
    ".ini",
    ".cfg",
    ".bat",
    ".ps1",
}


class FileIndexer:
    """Indexes files in allowlisted folders into SQLite FTS5 for instant local content search."""

    def __init__(self, config: OrinConfig | None = None) -> None:
        init_db()
        self.config = config or get_config()

    def get_indexed_count(self) -> int:
        """Returns total number of currently indexed files."""
        with get_db() as conn:
            cur = conn.execute("SELECT COUNT(*) as cnt FROM file_index;")
            row = cur.fetchone()
            return row["cnt"] if row else 0

    def clear_index(self) -> None:
        """Clears all entries from the full-text search index."""
        with get_db() as conn:
            conn.execute("DELETE FROM file_index;")

    def index_folders(
        self,
        folders: list[str] | None = None,
        max_file_size: int = 300_000,
    ) -> tuple[int, int]:
        """Indexes text files in allowlisted folders incrementally.

        Returns (newly_or_updated_indexed_count, skipped_count).
        """
        target_folders = folders or self.config.security.allowlisted_folders
        indexed_count = 0
        skipped_count = 0

        # Build existing timestamp map to allow incremental updates
        existing_mtimes: dict[str, float] = {}
        with get_db() as conn:
            cur = conn.execute("SELECT path, modified_time FROM file_index;")
            for r in cur.fetchall():
                try:
                    existing_mtimes[r["path"]] = float(r["modified_time"])
                except (ValueError, TypeError):
                    existing_mtimes[r["path"]] = 0.0

        for folder_str in target_folders:
            folder = Path(folder_str)
            if not folder.exists() or not folder.is_dir():
                continue

            for root, _, files in os.walk(folder):
                for fname in files:
                    ext = Path(fname).suffix.lower()
                    if ext not in INDEXABLE_EXTENSIONS:
                        continue

                    full_path = Path(root) / fname
                    path_str = str(full_path.resolve())

                    # Ensure path is allowlisted
                    if not is_path_allowlisted(full_path, target_folders):
                        continue

                    try:
                        stat = full_path.stat()
                        mtime = stat.st_mtime
                        size = stat.st_size

                        # Incremental check: if mtime is identical, skip re-reading
                        if path_str in existing_mtimes and abs(existing_mtimes[path_str] - mtime) < 0.01:
                            skipped_count += 1
                            continue

                        # Read text content safely
                        if size > max_file_size:
                            with open(full_path, encoding="utf-8", errors="replace") as f:
                                content = f.read(max_file_size)
                        else:
                            content = full_path.read_text(encoding="utf-8", errors="replace")

                        with get_db() as conn:
                            # Remove old entry if updating
                            conn.execute("DELETE FROM file_index WHERE path = ?;", (path_str,))
                            conn.execute(
                                """
                                INSERT INTO file_index (path, filename, extension, content, modified_time)
                                VALUES (?, ?, ?, ?, ?);
                                """,
                                (path_str, fname, ext, content, str(mtime)),
                            )
                        existing_mtimes[path_str] = mtime
                        indexed_count += 1

                    except Exception:
                        continue

        return indexed_count, skipped_count

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Searches indexed files using FTS5 full-text search with fallback."""
        clean_q = query.strip()
        if not clean_q:
            return []

        # Sanitize query for FTS5 (escape quotes or match terms)
        sanitized_terms = [f'"{w}"' for w in clean_q.split() if w.isalnum()]
        fts_query = " ".join(sanitized_terms) if sanitized_terms else f'"{clean_q}"'

        results: list[dict[str, Any]] = []
        with get_db() as conn:
            try:
                cur = conn.execute(
                    """
                    SELECT path, filename, extension, snippet(file_index, 3, '[', ']', '...', 12) as snippet, modified_time
                    FROM file_index
                    WHERE file_index MATCH ?
                    ORDER BY rank
                    LIMIT ?;
                    """,
                    (fts_query, limit),
                )
                rows = cur.fetchall()
                for r in rows:
                    results.append(
                        {
                            "path": r["path"],
                            "filename": r["filename"],
                            "extension": r["extension"],
                            "snippet": r["snippet"],
                            "modified_time": r["modified_time"],
                        }
                    )
            except Exception:
                # Fallback to LIKE if FTS query syntax fails on special symbols
                like_term = f"%{clean_q}%"
                cur = conn.execute(
                    """
                    SELECT path, filename, extension, substr(content, 1, 100) as snippet, modified_time
                    FROM file_index
                    WHERE filename LIKE ? OR content LIKE ?
                    LIMIT ?;
                    """,
                    (like_term, like_term, limit),
                )
                rows = cur.fetchall()
                for r in rows:
                    results.append(
                        {
                            "path": r["path"],
                            "filename": r["filename"],
                            "extension": r["extension"],
                            "snippet": r["snippet"],
                            "modified_time": r["modified_time"],
                        }
                    )

        return results


_global_file_indexer: FileIndexer | None = None


def get_file_indexer() -> FileIndexer:
    """Singleton getter for FileIndexer."""
    global _global_file_indexer
    if _global_file_indexer is None:
        _global_file_indexer = FileIndexer()
    return _global_file_indexer
