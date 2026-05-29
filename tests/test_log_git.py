"""Tests for helpers.log_git."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from helpers.log_git import LogGitError, commit


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def test_initializes_repo_on_first_call(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "2026-05-28.md"
    log_file.write_text("---\nid: x\n---\n\n## t\n\nn\n")

    commit(log_file, message="log: 2026-05-28")

    assert (logs_dir / ".git").exists()
    log_output = _run("log", "--oneline", cwd=logs_dir).stdout
    assert "log: 2026-05-28" in log_output


def test_appends_commit_to_existing_repo(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    _run("init", "-q", "-b", "main", cwd=logs_dir)
    _run("config", "user.email", "test@example.com", cwd=logs_dir)
    _run("config", "user.name", "Test", cwd=logs_dir)

    f1 = logs_dir / "first.md"
    f1.write_text("first\n")
    _run("add", "first.md", cwd=logs_dir)
    _run("commit", "-m", "first", cwd=logs_dir)

    f2 = logs_dir / "second.md"
    f2.write_text("second\n")
    commit(f2, message="second")

    log_output = _run("log", "--oneline", cwd=logs_dir).stdout
    assert "first" in log_output
    assert "second" in log_output


def test_raises_on_unstageable_path(tmp_path: Path) -> None:
    bogus = tmp_path / "nope" / "missing.md"
    with pytest.raises(LogGitError):
        commit(bogus, message="x")


def test_handles_no_changes_gracefully(tmp_path: Path) -> None:
    """Committing the same file twice in a row is a no-op, not an error."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    f = logs_dir / "x.md"
    f.write_text("content\n")
    commit(f, message="first")
    # No changes since — should not raise.
    commit(f, message="redundant")
