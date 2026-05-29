"""Fetch the user's recent Jira activity."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict

JiraEventKind = Literal["created", "transitioned", "commented", "assigned"]


class JiraFetchError(RuntimeError):
    """Raised when the Jira API is unreachable or returns a non-2xx."""


class JiraEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    kind: JiraEventKind
    when: datetime
    summary: str


def get_jira_activity(
    *,
    base_url: str,
    email: str,
    token: str,
    account_id: str,
    since: datetime,
    until: datetime,
) -> list[JiraEvent]:
    """Return the user's Jira activity in [since, until].

    Hard-fails (raises JiraFetchError) on any network or HTTP error.
    """
    url = f"{base_url.rstrip('/')}/rest/api/3/activity"
    params = {"streams": f"user IS {account_id}"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, params=params, auth=(email, token))
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise JiraFetchError(f"failed to fetch Jira activity: {e}") from e

    events: list[JiraEvent] = []
    for raw in payload.get("values", []):
        when = datetime.fromisoformat(raw["timestamp"].replace("Z", "+00:00"))
        if not (since <= when <= until):
            continue
        kind = raw["action"]
        if kind not in ("created", "transitioned", "commented", "assigned"):
            continue
        obj = raw.get("object", {})
        events.append(
            JiraEvent(
                key=obj.get("objectId", ""),
                kind=kind,
                when=when,
                summary=obj.get("summary", ""),
            )
        )
    return events
