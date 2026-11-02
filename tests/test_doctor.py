"""Test suite for Orin diagnostics and doctor checks."""

from orin.cli.doctor import (
    check_connectivity,
    check_python_version,
    check_storage_and_permissions,
)


def test_python_version_check() -> None:
    res = check_python_version()
    assert res.component == "Python Runtime"
    # Current environment is Python 3.13
    assert res.status == "PASS"
    assert "3.13" in res.details


def test_storage_and_permissions_check(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ORIN_HOME", str(tmp_path))
    res = check_storage_and_permissions()
    assert res.component == "Storage & Access"
    assert res.status == "PASS"
    assert str(tmp_path) in res.details


def test_connectivity_check() -> None:
    res = check_connectivity()
    assert res.component == "Network Connectivity"
    assert res.status in ("PASS", "WARN")
