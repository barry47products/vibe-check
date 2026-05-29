"""Tests for the five entry shapes."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from helpers.types import (
    DeepWorkEntry,
    LearningEntry,
    MeetingEntry,
    OffsiteEntry,
    OpsEntry,
)

ENVELOPE_BASE = {
    "id": "01HXYZ",
    "date": date(2026, 5, 28),
    "duration_hours": 4.0,
    "client": "Acme",
    "project": "Policy Documentation",
    "title": "x",
    "narrative": "y",
}


def test_deep_work_entry_minimal() -> None:
    e = DeepWorkEntry.model_validate(
        {**ENVELOPE_BASE, "shape": "deep_work", "area": "documentation", "outputs": ["Section 4.2"]}
    )
    assert e.shape == "deep_work"
    assert e.area == "documentation"
    assert e.outputs == ["Section 4.2"]
    assert e.blockers == []


def test_deep_work_rejects_invalid_area() -> None:
    with pytest.raises(ValidationError):
        DeepWorkEntry.model_validate(
            {**ENVELOPE_BASE, "shape": "deep_work", "area": "yoga", "outputs": []}
        )


def test_meeting_entry_minimal() -> None:
    e = MeetingEntry.model_validate(
        {
            **ENVELOPE_BASE,
            "shape": "meeting",
            "meeting_type": "1:1",
            "attendees": ["David"],
            "decisions": [],
            "action_items": [{"owner": "Barry", "item": "Follow up on contract"}],
        }
    )
    assert e.meeting_type == "1:1"
    assert e.action_items[0].owner == "Barry"


def test_meeting_rejects_unknown_meeting_type() -> None:
    with pytest.raises(ValidationError):
        MeetingEntry.model_validate(
            {
                **ENVELOPE_BASE,
                "shape": "meeting",
                "meeting_type": "lunch",
                "attendees": [],
                "decisions": [],
                "action_items": [],
            }
        )


def test_offsite_entry_minimal() -> None:
    e = OffsiteEntry.model_validate(
        {
            **ENVELOPE_BASE,
            "shape": "offsite",
            "location": "Cape Town office",
            "purpose": "Q2 planning",
            "outcomes": ["Roadmap aligned"],
        }
    )
    assert e.location == "Cape Town office"
    assert e.travel_hours_separate is None


def test_ops_entry_minimal() -> None:
    e = OpsEntry.model_validate(
        {
            **ENVELOPE_BASE,
            "shape": "ops",
            "category": "invoicing",
            "items": ["Submitted April timesheet"],
        }
    )
    assert e.category == "invoicing"


def test_learning_entry_minimal() -> None:
    e = LearningEntry.model_validate(
        {
            **ENVELOPE_BASE,
            "shape": "learning",
            "topic": "Pydantic v2 discriminated unions",
            "sources": ["https://docs.pydantic.dev/latest/concepts/unions/"],
            "summary": "Use Annotated[Union, Field(discriminator=...)] for tagged unions.",
            "applies_to": ["Vibe Check Entry model"],
        }
    )
    assert e.topic.startswith("Pydantic")
