"""Commit appended log files to a local git repo at the logs directory."""

from __future__ import annotations

import subprocess
from pathlib import Path


class LogGitError(RuntimeError):
    """Raised when git operations on the logs directory fail unrecoverably."""


def commit(path: Path, *, message: str) -> None:
    """Stage and commit `path` inside its enclosing logs directory.

    Initializes a git repo on first use. A no-op commit (nothing to stage)
    is treated as success, not an error.
    """
    if not path.exists():
        raise LogGitError(f"cannot commit a non-existent path: {path}")

    repo = path.parent
    try:
        if not (repo / ".git").exists():
            _git("init", "-q", "-b", "main", cwd=repo)
            _git("config", "user.email", "vibe-check@local", cwd=repo)
            _git("config", "user.name", "Vibe Check", cwd=repo)

        _git("add", str(path.name), cwd=repo)

        status = _git("status", "--porcelain", cwd=repo).stdout
        if not status.strip():
            return  # nothing to commit; no-op success

        _git("commit", "-q", "-m", message, cwd=repo)
    except subprocess.CalledProcessError as e:
        raise LogGitError(
            f"git operation failed in {repo}: {e.stderr.strip() or e}"
        ) from e


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
