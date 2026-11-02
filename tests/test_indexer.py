"""Tests for Orin SQLite FTS5 file indexer and incremental updates."""

from pathlib import Path

import pytest

from orin.config.settings import OrinConfig, SecurityConfig
from orin.tools.indexer import FileIndexer


def test_fts5_indexing_and_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_db = tmp_path / "test_indexer.db"
    monkeypatch.setenv("ORIN_DB_PATH", str(test_db))

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    file_a = docs_dir / "project_orin.md"
    file_a.write_text("Orin is a lightweight local voice assistant running offline on Windows.")

    file_b = docs_dir / "shopping.txt"
    file_b.write_text("Grocery list: apples, bananas, whole milk, espresso beans.")

    cfg = OrinConfig(security=SecurityConfig(allowlisted_folders=[str(docs_dir)]))
    indexer = FileIndexer(config=cfg)

    # Initial indexing run
    indexed, skipped = indexer.index_folders()
    assert indexed == 2
    assert skipped == 0
    assert indexer.get_indexed_count() == 2

    # Second indexing run: incremental, should skip unchanged files
    indexed_2, skipped_2 = indexer.index_folders()
    assert indexed_2 == 0
    assert skipped_2 == 2

    # Full-text search
    results = indexer.search("offline")
    assert len(results) >= 1
    assert "project_orin.md" in results[0]["filename"]

    results_grocery = indexer.search("espresso")
    assert len(results_grocery) >= 1
    assert "shopping.txt" in results_grocery[0]["filename"]

    # Search for nonexistent keyword
    results_empty = indexer.search("supercalifragilistic")
    assert len(results_empty) == 0

    # Clear index
    indexer.clear_index()
    assert indexer.get_indexed_count() == 0
