"""Tests for shared envelope and value types."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from helpers.types import EntryEnvelope, LinkedSignal


def test_linked_signal_accepts_known_kinds() -> None:
    sig = LinkedSignal(kind="git", ref="repo@a1b2c3")
    assert sig.kind == "git"
    assert sig.ref == "repo@a1b2c3"


def test_linked_signal_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        LinkedSignal(kind="ldap", ref="anything")  # type: ignore[arg-type]


def test_envelope_requires_core_fields() -> None:
    payload = {
        "id": "01HXYZABCDEFGHJKMNPQRSTVWX",
        "date": date(2026, 5, 28),
        "shape": "deep_work",
        "duration_hours": 4.5,
        "client": "Acme",
        "project": "Policy Documentation",
        "title": "Drafted section 4 of compliance overview",
        "narrative": "Spent the morning drafting section 4.2.",
    }
    env = EntryEnvelope.model_validate(payload)
    assert env.client == "Acme"
    assert env.tags == []
    assert env.linked_signals == []
    assert env.needs_review is False


def test_envelope_rejects_missing_required_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        EntryEnvelope.model_validate(
            {
                "id": "01HXYZ",
                "date": date(2026, 5, 28),
                "shape": "deep_work",
                "duration_hours": 4.5,
                "client": "Acme",
                "project": "Policy",
                "title": "x",
                # narrative intentionally missing
            }
        )
    assert "narrative" in str(exc_info.value)


def test_envelope_id_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        EntryEnvelope.model_validate(
            {
                "id": "",
                "date": date(2026, 5, 28),
                "shape": "deep_work",
                "duration_hours": 1.0,
                "client": "Acme",
                "project": "p",
                "title": "t",
                "narrative": "n",
            }
        )


def test_envelope_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        EntryEnvelope.model_validate(
            {
                "id": "01H",
                "date": date(2026, 5, 28),
                "shape": "deep_work",
                "duration_hours": 0,
                "client": "Acme",
                "project": "p",
                "title": "t",
                "narrative": "n",
            }
        )
