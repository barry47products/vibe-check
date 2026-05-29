"""Tests for helpers.git_scrape."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from helpers.git_scrape import GitScrapeError, get_git_activity


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _seed_repo(path: Path, *, author_email: str = "barry@example.com") -> None:
    path.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", author_email, cwd=path)
    _git("config", "user.name", "Barry", cwd=path)
    (path / "README.md").write_text("hello\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-m", "init", cwd=path)
    (path / "README.md").write_text("hello, world\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-m", "expand greeting", cwd=path)


def test_returns_commits_in_window(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo)

    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime.now(UTC)

    commits = get_git_activity([repo], since=since, until=until)
    assert len(commits) == 2
    messages = [c.message for c in commits]
    assert "init" in messages
    assert "expand greeting" in messages
    for c in commits:
        assert c.repo == "demo"
        assert len(c.sha) >= 7


def test_filters_by_author(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo, author_email="barry@example.com")

    since = datetime(2000, 1, 1, tzinfo=UTC)
    until = datetime.now(UTC)

    matching = get_git_activity(
        [repo], since=since, until=until, author="barry@example.com"
    )
    assert len(matching) == 2

    none = get_git_activity(
        [repo], since=since, until=until, author="someone-else@example.com"
    )
    assert none == []


def test_raises_on_missing_repo(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    with pytest.raises(GitScrapeError):
        get_git_activity(
            [bogus],
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime.now(UTC),
        )


def test_raises_on_non_git_directory(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitScrapeError):
        get_git_activity(
            [plain],
            since=datetime(2000, 1, 1, tzinfo=UTC),
            until=datetime.now(UTC),
        )


def test_empty_window_returns_empty_list(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo)
    far_past = datetime(1990, 1, 1, tzinfo=UTC)
    far_past_end = datetime(1991, 1, 1, tzinfo=UTC)
    assert get_git_activity([repo], since=far_past, until=far_past_end) == []
