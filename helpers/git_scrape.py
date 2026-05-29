"""Scrape commit activity from local git repositories."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class GitScrapeError(RuntimeError):
    """Raised when a repo can't be reached or git fails for any reason."""


class CommitSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str
    sha: str
    when: datetime
    author_email: str
    message: str
    files_touched_count: int


def get_git_activity(
    repos: Sequence[Path],
    *,
    since: datetime,
    until: datetime,
    author: str | None = None,
) -> list[CommitSummary]:
    """Return commits across the configured repos within [since, until].

    Hard-fails (raises GitScrapeError) if any configured repo is missing
    or not a git repo, or if `git log` errors. This is intentional — the
    Vibe Check pipeline halts rather than producing logs with silent gaps.
    """
    results: list[CommitSummary] = []
    for repo in repos:
        if not repo.exists():
            raise GitScrapeError(f"configured repo does not exist: {repo}")
        if not (repo / ".git").exists():
            raise GitScrapeError(f"not a git repository: {repo}")
        results.extend(
            _scrape_one(
                repo, since=since, until=until, author=author
            )
        )
    return results


def _scrape_one(
    repo: Path,
    *,
    since: datetime,
    until: datetime,
    author: str | None,
) -> list[CommitSummary]:
    sep = "\x1f"  # ASCII unit separator — extremely unlikely to appear in commit text
    fmt = sep.join(["%H", "%aI", "%ae", "%s"])
    cmd = [
        "git",
        "log",
        f"--since={since.isoformat()}",
        f"--until={until.isoformat()}",
        f"--pretty=format:{fmt}",
        "--shortstat",
    ]
    if author is not None:
        cmd.append(f"--author={author}")

    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise GitScrapeError(
            f"git log failed in {repo}: {e.stderr.strip() or e}"
        ) from e

    return _parse_log_output(proc.stdout, repo_name=repo.name, sep=sep)


def _parse_log_output(stdout: str, *, repo_name: str, sep: str) -> list[CommitSummary]:
    commits: list[CommitSummary] = []
    blocks = [b for b in stdout.split("\n\n") if b.strip()]
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        header = lines[0]
        try:
            sha, when_iso, email, message = header.split(sep, 3)
        except ValueError as e:
            raise GitScrapeError(f"unparseable git log line in {repo_name}: {header!r}") from e
        files_touched = 0
        for tail in lines[1:]:
            if "file" in tail and "changed" in tail:
                files_touched = int(tail.strip().split()[0])
        commits.append(
            CommitSummary(
                repo=repo_name,
                sha=sha,
                when=datetime.fromisoformat(when_iso),
                author_email=email,
                message=message,
                files_touched_count=files_touched,
            )
        )
    return commits
