"""Tests for the discriminated Entry union."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from helpers.types import DeepWorkEntry, Entry, MeetingEntry

ENVELOPE_BASE = {
    "id": "01HXYZ",
    "date": date(2026, 5, 28),
    "duration_hours": 4.0,
    "client": "Acme",
    "project": "p",
    "title": "t",
    "narrative": "n",
}

entry_adapter: TypeAdapter[Entry] = TypeAdapter(Entry)


def test_union_routes_to_deep_work() -> None:
    e = entry_adapter.validate_python(
        {**ENVELOPE_BASE, "shape": "deep_work", "area": "code", "outputs": []}
    )
    assert isinstance(e, DeepWorkEntry)


def test_union_routes_to_meeting() -> None:
    e = entry_adapter.validate_python(
        {
            **ENVELOPE_BASE,
            "shape": "meeting",
            "meeting_type": "review",
            "attendees": [],
            "decisions": [],
            "action_items": [],
        }
    )
    assert isinstance(e, MeetingEntry)


def test_union_rejects_unknown_shape() -> None:
    with pytest.raises(ValidationError):
        entry_adapter.validate_python(
            {**ENVELOPE_BASE, "shape": "yoga", "extras": "stuff"}
        )
