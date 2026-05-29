"""Tests for helpers.bulletin_render."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from helpers.bulletin_render import render_bulletin
from helpers.types import DeepWorkEntry, MeetingEntry, OpsEntry

FIXTURES = Path(__file__).parent / "fixtures"


def _entries() -> list:
    return [
        DeepWorkEntry.model_validate(
            {
                "id": "01H1",
                "date": date(2026, 5, 28),
                "shape": "deep_work",
                "duration_hours": 4.5,
                "client": "Acme",
                "project": "Policy Documentation",
                "title": "Drafted section 4 of compliance overview",
                "narrative": "Made progress on 4.1 and 4.2.",
                "area": "documentation",
                "outputs": ["Section 4.2 draft"],
            }
        ),
        MeetingEntry.model_validate(
            {
                "id": "01H2",
                "date": date(2026, 5, 28),
                "shape": "meeting",
                "duration_hours": 1.0,
                "client": "Acme",
                "project": "Onboarding",
                "title": "MFA design review with security",
                "narrative": "Reviewed the proposed MFA flow with the security team.",
                "meeting_type": "review",
                "attendees": ["Lerato", "Sipho"],
                "decisions": ["Adopt WebAuthn as primary"],
                "action_items": [{"owner": "Barry", "item": "Spike WebAuthn lib"}],
            }
        ),
        OpsEntry.model_validate(
            {
                "id": "01H3",
                "date": date(2026, 5, 28),
                "shape": "ops",
                "duration_hours": 0.25,
                "client": "Acme",
                "project": "Admin",
                "title": "Submitted April timesheet",
                "narrative": "Logged and emailed.",
                "category": "invoicing",
                "items": ["April invoice submitted"],
            }
        ),
    ]


def test_renders_bulletin_in_slack_style(tmp_path: Path) -> None:
    rendered = render_bulletin(_entries(), date(2026, 5, 28), style="slack")
    expected = (FIXTURES / "bulletin_two_entries.expected.md").read_text()
    assert rendered == expected


def test_groups_entries_by_shape() -> None:
    rendered = render_bulletin(_entries(), date(2026, 5, 28), style="slack")
    # Deep work section appears before Meetings, which appears before Ops.
    assert rendered.index("Deep work") < rendered.index("Meetings")
    assert rendered.index("Meetings") < rendered.index("Ops")


def test_total_hours_is_summed() -> None:
    rendered = render_bulletin(_entries(), date(2026, 5, 28), style="slack")
    assert "5.75" in rendered  # 4.5 + 1.0 + 0.25


def test_renders_empty_day() -> None:
    rendered = render_bulletin([], date(2026, 5, 28), style="slack")
    assert "no entries" in rendered.lower()
