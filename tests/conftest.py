"""Pytest fixtures and environment isolation for Orin test suite."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_orin_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate configuration and database paths to temporary directories for each test."""
    orin_home = tmp_path / ".orin"
    orin_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("ORIN_HOME", str(orin_home))
    monkeypatch.setenv("ORIN_CONFIG_PATH", str(orin_home / "config.toml"))
    monkeypatch.setenv("ORIN_DB_PATH", str(orin_home / "orin.db"))
