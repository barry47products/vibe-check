"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def logs_dir(tmp_path: Path) -> Iterator[Path]:
    """Provide an isolated, ephemeral logs directory per test."""
    d = tmp_path / "vibe-check-logs"
    d.mkdir()
    yield d
