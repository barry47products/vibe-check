"""Render a day's entries as a bulletin (Slack-flavored or plain markdown)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as date_cls
from typing import Literal

from helpers.types import (
    DeepWorkEntry,
    EntryEnvelope,
    LearningEntry,
    MeetingEntry,
    OffsiteEntry,
    OpsEntry,
)

Style = Literal["slack", "markdown"]

_SHAPE_HEADINGS: dict[str, str] = {
    "deep_work": "Deep work",
    "meeting": "Meetings",
    "offsite": "Off-site",
    "ops": "Ops",
    "learning": "Learning",
}

_SHAPE_ORDER = ["deep_work", "meeting", "offsite", "ops", "learning"]


def render_bulletin(
    entries: Sequence[EntryEnvelope],
    date: date_cls,
    *,
    style: Style = "slack",
) -> str:
    """Render the day's bulletin. Pure function — no I/O."""
    if not entries:
        return f"*Vibe Check — {date.isoformat()}*  ·  _no entries today._\n"

    total = sum(e.duration_hours for e in entries)
    lines = [f"*Vibe Check — {date.isoformat()}*  ·  *{_fmt(total)}h total*", ""]

    grouped = _group_by_shape(entries)
    for shape in _SHAPE_ORDER:
        bucket = grouped.get(shape, [])
        if not bucket:
            continue
        heading = _SHAPE_HEADINGS[shape]
        bucket_hours = sum(e.duration_hours for e in bucket)
        lines.append(f"*{heading}* — _{_fmt(bucket_hours)}h_")
        for entry in bucket:
            lines.extend(_render_entry(entry))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _group_by_shape(entries: Sequence[EntryEnvelope]) -> dict[str, list[EntryEnvelope]]:
    out: dict[str, list[EntryEnvelope]] = {}
    for e in entries:
        out.setdefault(e.shape, []).append(e)
    return out


def _render_entry(entry: EntryEnvelope) -> list[str]:
    lines: list[str] = []
    suffix = _entry_suffix(entry)
    head = (
        f"• *{entry.title}* "
        f"({entry.project}, {_fmt(entry.duration_hours)}h{suffix})"
    )
    lines.append(head)
    lines.append(f"  {entry.narrative}")
    extra = _entry_extra(entry)
    if extra is not None:
        lines.append(f"  {extra}")
    return lines


def _entry_suffix(entry: EntryEnvelope) -> str:
    if isinstance(entry, MeetingEntry):
        return f", _{entry.meeting_type}_"
    if isinstance(entry, OpsEntry):
        return f", _{entry.category}_"
    return ""


def _entry_extra(entry: EntryEnvelope) -> str | None:
    if isinstance(entry, MeetingEntry) and entry.decisions:
        return "Decided: " + "; ".join(entry.decisions) + "."
    if isinstance(entry, DeepWorkEntry) and entry.blockers:
        return "Blockers: " + "; ".join(entry.blockers) + "."
    if isinstance(entry, OffsiteEntry) and entry.outcomes:
        return "Outcomes: " + "; ".join(entry.outcomes) + "."
    if isinstance(entry, LearningEntry):
        return f"Takeaway: {entry.summary}"
    return None


def _fmt(hours: float) -> str:
    """Render hours without trailing .0 noise (4.5 not 4.50; 1 not 1.0)."""
    if hours == int(hours):
        return f"{int(hours)}.0" if hours != 0 else "0"
    return f"{hours:g}"
