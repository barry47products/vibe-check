"""Tests for helpers.log_writer."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from helpers.log_writer import write_log
from helpers.types import DeepWorkEntry, MeetingEntry


def _deep_work(id_: str = "01HXYZ") -> DeepWorkEntry:
    return DeepWorkEntry.model_validate(
        {
            "id": id_,
            "date": date(2026, 5, 28),
            "shape": "deep_work",
            "duration_hours": 4.5,
            "client": "Acme",
            "project": "Policy Documentation",
            "title": "Drafted section 4",
            "narrative": "Spent the morning on the compliance overview.",
            "area": "documentation",
            "outputs": ["Section 4.2"],
        }
    )


def _meeting(id_: str = "01HMTG") -> MeetingEntry:
    return MeetingEntry.model_validate(
        {
            "id": id_,
            "date": date(2026, 5, 28),
            "shape": "meeting",
            "duration_hours": 0.5,
            "client": "Acme",
            "project": "Onboarding",
            "title": "Standup",
            "narrative": "Quick async standup.",
            "meeting_type": "standup",
            "attendees": ["Barry", "Lerato"],
            "decisions": [],
            "action_items": [],
        }
    )


def test_creates_file_on_first_entry(logs_dir: Path) -> None:
    path = write_log(_deep_work(), logs_dir=logs_dir)
    assert path == logs_dir / "2026-05-28.md"
    assert path.exists()
    contents = path.read_text()
    assert contents.startswith("---\n")
    assert "shape: deep_work" in contents
    assert "## Drafted section 4" in contents
    assert "Spent the morning on the compliance overview." in contents


def test_appends_to_existing_day(logs_dir: Path) -> None:
    write_log(_deep_work(id_="01HONE"), logs_dir=logs_dir)
    path = write_log(_meeting(id_="01HTWO"), logs_dir=logs_dir)
    contents = path.read_text()
    # Two frontmatter blocks separated by blank lines
    assert contents.count("---\n") == 4  # 2 blocks × 2 fences each
    assert "## Drafted section 4" in contents
    assert "## Standup" in contents
    # Order: first entry first
    assert contents.index("Drafted section 4") < contents.index("Standup")


def test_frontmatter_round_trips(logs_dir: Path) -> None:
    entry = _deep_work()
    path = write_log(entry, logs_dir=logs_dir)
    text = path.read_text()
    # Extract the first frontmatter block.
    _, _, after_first = text.partition("---\n")
    yaml_block, _, _ = after_first.partition("\n---\n")
    parsed = yaml.safe_load(yaml_block)
    assert parsed["id"] == entry.id
    assert parsed["shape"] == "deep_work"
    assert parsed["duration_hours"] == 4.5
    assert parsed["outputs"] == ["Section 4.2"]


def test_idempotent_on_same_entry(logs_dir: Path) -> None:
    """Writing the same entry twice should not duplicate it."""
    entry = _deep_work(id_="01HSAME")
    write_log(entry, logs_dir=logs_dir)
    path = write_log(entry, logs_dir=logs_dir)
    contents = path.read_text()
    assert contents.count("id: 01HSAME") == 1
