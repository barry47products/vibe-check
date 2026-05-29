"""Tests for helpers.jira_fetch."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from helpers.jira_fetch import JiraFetchError, get_jira_activity

BASE = "https://acme.atlassian.net"


def _activity_payload() -> dict:
    return {
        "values": [
            {
                "id": "10001",
                "timestamp": "2026-05-28T10:00:00.000+0000",
                "action": "created",
                "object": {"summary": "Add MFA to onboarding flow", "objectId": "JEWL-101"},
            },
            {
                "id": "10002",
                "timestamp": "2026-05-28T12:30:00.000+0000",
                "action": "commented",
                "object": {"summary": "Migration plan review", "objectId": "JEWL-87"},
            },
        ]
    }


@respx.mock
def test_returns_events_in_window() -> None:
    respx.get(f"{BASE}/rest/api/3/activity").respond(200, json=_activity_payload())
    events = get_jira_activity(
        base_url=BASE,
        email="barry@example.com",
        token="t",
        account_id="acc-1",
        since=datetime(2026, 5, 28, 0, 0, tzinfo=UTC),
        until=datetime(2026, 5, 28, 23, 59, tzinfo=UTC),
    )
    assert len(events) == 2
    assert events[0].key == "JEWL-101"
    assert events[0].kind == "created"
    assert events[1].kind == "commented"


@respx.mock
def test_filters_events_outside_window() -> None:
    payload = {
        "values": [
            {
                "id": "1",
                "timestamp": "2026-05-25T10:00:00.000+0000",
                "action": "created",
                "object": {"summary": "old", "objectId": "JEWL-1"},
            },
            {
                "id": "2",
                "timestamp": "2026-05-28T10:00:00.000+0000",
                "action": "created",
                "object": {"summary": "today", "objectId": "JEWL-2"},
            },
        ]
    }
    respx.get(f"{BASE}/rest/api/3/activity").respond(200, json=payload)
    events = get_jira_activity(
        base_url=BASE,
        email="barry@example.com",
        token="t",
        account_id="acc-1",
        since=datetime(2026, 5, 28, 0, 0, tzinfo=UTC),
        until=datetime(2026, 5, 28, 23, 59, tzinfo=UTC),
    )
    assert len(events) == 1
    assert events[0].key == "JEWL-2"


@respx.mock
def test_raises_on_http_error() -> None:
    respx.get(f"{BASE}/rest/api/3/activity").respond(503)
    with pytest.raises(JiraFetchError):
        get_jira_activity(
            base_url=BASE,
            email="barry@example.com",
            token="t",
            account_id="acc-1",
            since=datetime(2026, 5, 28, tzinfo=UTC),
            until=datetime(2026, 5, 29, tzinfo=UTC),
        )


@respx.mock
def test_raises_on_network_error() -> None:
    respx.get(f"{BASE}/rest/api/3/activity").mock(
        side_effect=httpx.ConnectError("boom")
    )
    with pytest.raises(JiraFetchError):
        get_jira_activity(
            base_url=BASE,
            email="barry@example.com",
            token="t",
            account_id="acc-1",
            since=datetime(2026, 5, 28, tzinfo=UTC),
            until=datetime(2026, 5, 29, tzinfo=UTC),
        )
