"""Tests for helpers.timesheet."""

from __future__ import annotations

import csv
import io
from datetime import date
from pathlib import Path

from helpers.log_writer import write_log
from helpers.timesheet import Timesheet, build_timesheet
from helpers.types import DeepWorkEntry, MeetingEntry, OpsEntry


def _seed_month(logs_dir: Path) -> None:
    entries = [
        DeepWorkEntry.model_validate(
            {
                "id": "01M1",
                "date": date(2026, 5, 5),
                "shape": "deep_work",
                "duration_hours": 4.0,
                "client": "Acme",
                "project": "Policy",
                "title": "x",
                "narrative": "y",
                "area": "documentation",
                "outputs": [],
            }
        ),
        MeetingEntry.model_validate(
            {
                "id": "01M2",
                "date": date(2026, 5, 5),
                "shape": "meeting",
                "duration_hours": 1.0,
                "client": "Acme",
                "project": "Policy",
                "title": "review",
                "narrative": "n",
                "meeting_type": "review",
                "attendees": [],
                "decisions": [],
                "action_items": [],
            }
        ),
        DeepWorkEntry.model_validate(
            {
                "id": "01M3",
                "date": date(2026, 5, 12),
                "shape": "deep_work",
                "duration_hours": 3.0,
                "client": "Acme",
                "project": "Onboarding",
                "title": "y",
                "narrative": "z",
                "area": "code",
                "outputs": [],
            }
        ),
        OpsEntry.model_validate(
            {
                "id": "01M4",
                "date": date(2026, 4, 30),  # previous month — must be excluded
                "shape": "ops",
                "duration_hours": 0.5,
                "client": "Acme",
                "project": "Admin",
                "title": "z",
                "narrative": "z",
                "category": "invoicing",
                "items": [],
            }
        ),
    ]
    for e in entries:
        write_log(e, logs_dir=logs_dir)


def test_totals_hours_per_project(logs_dir: Path) -> None:
    _seed_month(logs_dir)
    sheet = build_timesheet(logs_dir, year=2026, month=5)
    assert isinstance(sheet, Timesheet)
    assert sheet.total_hours == 8.0  # 4 + 1 + 3
    assert sheet.by_project == {"Policy": 5.0, "Onboarding": 3.0}


def test_excludes_other_months(logs_dir: Path) -> None:
    _seed_month(logs_dir)
    sheet = build_timesheet(logs_dir, year=2026, month=5)
    assert "Admin" not in sheet.by_project  # April entry must not appear


def test_csv_contains_per_entry_rows(logs_dir: Path) -> None:
    _seed_month(logs_dir)
    sheet = build_timesheet(logs_dir, year=2026, month=5)
    reader = csv.DictReader(io.StringIO(sheet.csv.decode()))
    rows = list(reader)
    assert len(rows) == 3
    assert {row["project"] for row in rows} == {"Policy", "Onboarding"}
    assert {row["shape"] for row in rows} == {"deep_work", "meeting"}


def test_empty_month_returns_zero(logs_dir: Path) -> None:
    sheet = build_timesheet(logs_dir, year=2026, month=5)
    assert sheet.total_hours == 0.0
    assert sheet.by_project == {}
