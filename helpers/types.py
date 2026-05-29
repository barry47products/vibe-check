"""Pydantic models — single source of truth for Vibe Check entry shapes.

All entry shape changes start here. Run `python scripts/generate_schemas.py`
to regenerate the JSON Schemas consumed by the OCS Extract node.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

EntryShape = Literal["deep_work", "meeting", "offsite", "ops", "learning"]
LinkedSignalKind = Literal["git", "jira"]


class LinkedSignal(BaseModel):
    """A reference to an external signal that motivated this entry."""

    model_config = ConfigDict(extra="forbid")

    kind: LinkedSignalKind
    ref: str = Field(min_length=1)


class EntryEnvelope(BaseModel):
    """Common fields every entry carries, regardless of shape."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    date: date
    shape: EntryShape
    duration_hours: float = Field(gt=0)
    client: str = Field(min_length=1)
    project: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    linked_signals: list[LinkedSignal] = Field(default_factory=list)
    needs_review: bool = False


# --- Shape payloads ---------------------------------------------------------

DeepWorkArea = Literal["code", "design", "policy", "documentation", "review", "other"]
MeetingType = Literal["1:1", "standup", "review", "workshop", "interview", "other"]
OpsCategory = Literal[
    "invoicing", "expenses", "access-management", "tooling", "compliance", "other"
]


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner: str = Field(min_length=1)
    item: str = Field(min_length=1)


class DeepWorkEntry(EntryEnvelope):
    shape: Literal["deep_work"]
    area: DeepWorkArea
    outputs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class MeetingEntry(EntryEnvelope):
    shape: Literal["meeting"]
    meeting_type: MeetingType
    attendees: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)


class OffsiteEntry(EntryEnvelope):
    shape: Literal["offsite"]
    location: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    outcomes: list[str] = Field(default_factory=list)
    travel_hours_separate: float | None = Field(default=None, ge=0)


class OpsEntry(EntryEnvelope):
    shape: Literal["ops"]
    category: OpsCategory
    items: list[str] = Field(default_factory=list)


class LearningEntry(EntryEnvelope):
    shape: Literal["learning"]
    topic: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    applies_to: list[str] = Field(default_factory=list)


# --- Discriminated union ----------------------------------------------------

Entry = Annotated[
    DeepWorkEntry | MeetingEntry | OffsiteEntry | OpsEntry | LearningEntry,
    Field(discriminator="shape"),
]
