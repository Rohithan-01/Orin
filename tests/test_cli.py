"""Test suite for Orin CLI interface."""

from typer.testing import CliRunner

from orin.cli.main import app

runner = CliRunner()


def test_cli_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Orin" in result.stdout
    assert "0.1.0" in result.stdout


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.stdout
    assert "status" in result.stdout
    assert "setup" in result.stdout
    assert "say" in result.stdout


def test_cli_status() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "System Status" in result.stdout
    assert "llama3.2:3b" in result.stdout


def test_cli_audit() -> None:
    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 0
    assert "Security Audit Trail" in result.stdout


def test_cli_index() -> None:
    result = runner.invoke(app, ["index"])
    assert result.exit_code == 0
    assert "Full-Text File Indexer" in result.stdout
    assert "Indexing complete" in result.stdout
