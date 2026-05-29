# Vibe Check V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V1 Python helpers and supporting scaffolding for Vibe Check, an OCS-driven personal work-log assistant. Each helper is independently testable; together they back an OCS pipeline that interviews the user in Slack, classifies the entry into one of 5 shapes, persists structured logs, posts a daily bulletin to Afrolabs, and aggregates monthly timesheets.

**Architecture:** Pydantic v2 models in `helpers/types.py` are the single source of truth for entry shapes. JSON Schemas for the OCS Extract node are generated from those models. Each helper is a pure function with typed I/O and zero knowledge of OCS. Logs are markdown files with YAML frontmatter, stored outside the repo at `~/vibe-check-logs/` in a local git repo, auto-committed per entry.

**Tech Stack:** Python 3.12, uv, Pydantic v2, pytest, ruff, mypy, httpx, respx (HTTP mocking), PyYAML.

**Spec:** [docs/superpowers/specs/2026-05-28-vibe-check-design.md](../docs/superpowers/specs/2026-05-28-vibe-check-design.md)

---

## Task 1: Bootstrap the Python project

**Files:**
- Create: `pyproject.toml`
- Create: `helpers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `.env.example`

- [ ] **Step 1: Create `pyproject.toml`**

Create `pyproject.toml` with the contents below.

```toml
[project]
name = "vibe-check"
version = "0.1.0"
description = "Personal work-log assistant: OCS-driven Slack interviews, structured logs, monthly timesheets."
requires-python = ">=3.12"
dependencies = [
    "pydantic>=2.6",
    "httpx>=0.27",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "respx>=0.21",
    "ruff>=0.6",
    "mypy>=1.10",
    "types-pyyaml>=6.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM", "PL"]
ignore = ["PLR0913"]  # too-many-arguments — Pydantic models legitimately have many fields

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["PLR2004"]  # magic-value-comparison is fine in tests

[tool.mypy]
strict = true
python_version = "3.12"
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Create empty `__init__.py` files**

```bash
mkdir -p helpers tests
: > helpers/__init__.py
: > tests/__init__.py
```

- [ ] **Step 3: Create `tests/conftest.py` with a tmp logs-dir fixture**

```python
"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def logs_dir(tmp_path: Path) -> Iterator[Path]:
    """Provide an isolated, ephemeral logs directory per test."""
    d = tmp_path / "vibe-check-logs"
    d.mkdir()
    yield d
```

- [ ] **Step 4: Create `.env.example`**

```bash
# Acme Jira API token (Atlassian → Account settings → Security → API tokens)
JIRA_BASE_URL=https://acme.atlassian.net
JIRA_EMAIL=barry@example.com
JIRA_TOKEN=

# The Jira account id whose activity Vibe Check should ingest
JIRA_ACCOUNT_ID=

# Local OCS instance
OCS_BASE_URL=http://localhost:8000

# Directory where daily log markdown files live (outside this repo)
VIBE_CHECK_LOGS_DIR=$HOME/vibe-check-logs

# Configured git repos to scrape (colon-separated absolute paths)
VIBE_CHECK_GIT_REPOS=
```

- [ ] **Step 5: Verify the project bootstraps**

Run: `uv sync`
Expected: succeeds, creates `.venv/` and `uv.lock`.

Run: `uv run pytest`
Expected: exits 0 with "no tests ran" (no tests yet).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock helpers/__init__.py tests/__init__.py tests/conftest.py .env.example
git commit -m "chore: bootstrap Python project (uv + pytest + ruff + mypy + Pydantic)"
```

---

## Task 2: Common envelope and shared types

**Files:**
- Create: `helpers/types.py`
- Create: `tests/test_types_envelope.py`

- [ ] **Step 1: Write the failing envelope test**

Create `tests/test_types_envelope.py`:

```python
"""Tests for shared envelope and value types."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import pytest
from pydantic import ValidationError

from helpers.types import LinkedSignal


def test_linked_signal_accepts_known_kinds() -> None:
    sig = LinkedSignal(kind="git", ref="repo@a1b2c3")
    assert sig.kind == "git"
    assert sig.ref == "repo@a1b2c3"


def test_linked_signal_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        LinkedSignal(kind="ldap", ref="anything")  # type: ignore[arg-type]


def test_envelope_requires_core_fields() -> None:
    from helpers.types import EntryEnvelope

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
    from helpers.types import EntryEnvelope

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
    from helpers.types import EntryEnvelope

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
    from helpers.types import EntryEnvelope

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
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_types_envelope.py -v`
Expected: ImportError or AttributeError — `helpers.types` does not exist yet.

- [ ] **Step 3: Implement `helpers/types.py` envelope + LinkedSignal**

Create `helpers/types.py`:

```python
"""Pydantic models — single source of truth for Vibe Check entry shapes.

All entry shape changes start here. Run `python scripts/generate_schemas.py`
to regenerate the JSON Schemas consumed by the OCS Extract node.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_types_envelope.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/types.py tests/test_types_envelope.py
git commit -m "feat(types): add EntryEnvelope and LinkedSignal Pydantic models"
```

---

## Task 3: The five shape models

**Files:**
- Modify: `helpers/types.py`
- Create: `tests/test_types_shapes.py`

The five shapes share the envelope. Each contributes a shape-specific payload. We model them as concrete Pydantic models that extend `EntryEnvelope` with a literal `shape` discriminator value and the payload fields.

- [ ] **Step 1: Write failing tests for all five shapes**

Create `tests/test_types_shapes.py`:

```python
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
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_types_shapes.py -v`
Expected: ImportError — the shape classes don't exist yet.

- [ ] **Step 3: Add the five shape models to `helpers/types.py`**

Append to `helpers/types.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_types_shapes.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/types.py tests/test_types_shapes.py
git commit -m "feat(types): add 5 entry shapes (deep_work, meeting, offsite, ops, learning)"
```

---

## Task 4: Discriminated `Entry` union and parser

**Files:**
- Modify: `helpers/types.py`
- Create: `tests/test_types_union.py`

`Entry` is a tagged union over the five shapes, discriminated by the `shape` field. Pydantic v2 routes raw dicts to the right concrete class.

- [ ] **Step 1: Write the failing union test**

Create `tests/test_types_union.py`:

```python
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
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_types_union.py -v`
Expected: ImportError — `Entry` does not exist.

- [ ] **Step 3: Add the `Entry` union to `helpers/types.py`**

Append to `helpers/types.py`:

```python
# --- Discriminated union ----------------------------------------------------

from typing import Annotated, Union  # noqa: E402  (kept near use site for clarity)

Entry = Annotated[
    Union[DeepWorkEntry, MeetingEntry, OffsiteEntry, OpsEntry, LearningEntry],
    Field(discriminator="shape"),
]
```

Note: the `# noqa: E402` is the one allowed exception to the "imports at top" rule — this `Annotated`/`Union` import is colocated with the union definition for readability. If ruff still complains, hoist these two names into the top imports.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_types_union.py -v`
Expected: all 3 tests PASS.

Run: `uv run pytest -v` (the full suite)
Expected: all tests from Tasks 2, 3, 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/types.py tests/test_types_union.py
git commit -m "feat(types): add discriminated Entry union"
```

---

## Task 5: Schema generation script + sync test

**Files:**
- Create: `scripts/generate_schemas.py`
- Create: `schemas/.gitkeep` (then populated by the script)
- Create: `tests/test_schemas_in_sync.py`

The OCS Extract node consumes JSON Schemas. We generate one schema per concrete shape (not the union) so OCS targets a specific shape post-routing. A CI-style test asserts the committed schemas match the current Pydantic models.

- [ ] **Step 1: Create the schemas directory placeholder**

```bash
mkdir -p schemas
: > schemas/.gitkeep
```

- [ ] **Step 2: Write the schema-generation script**

Create `scripts/generate_schemas.py`:

```python
"""Regenerate JSON Schemas under schemas/ from helpers/types.py.

One file per concrete shape (not the union) — the OCS Extract node
targets a specific shape post-routing. Re-run after any change to
helpers/types.py and commit the resulting schemas/*.json alongside.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from helpers.types import (
    DeepWorkEntry,
    LearningEntry,
    MeetingEntry,
    OffsiteEntry,
    OpsEntry,
)

SHAPE_FILES: dict[type[BaseModel], str] = {
    DeepWorkEntry: "entry.deep-work.json",
    MeetingEntry: "entry.meeting.json",
    OffsiteEntry: "entry.offsite.json",
    OpsEntry: "entry.ops.json",
    LearningEntry: "entry.learning.json",
}


def generate(schemas_dir: Path) -> dict[str, str]:
    """Write one JSON Schema per shape. Returns {filename: schema_json_text}."""
    schemas_dir.mkdir(exist_ok=True)
    written: dict[str, str] = {}
    for model_cls, filename in SHAPE_FILES.items():
        schema = model_cls.model_json_schema()
        text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        (schemas_dir / filename).write_text(text)
        written[filename] = text
    return written


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "schemas"
    files = generate(out_dir)
    for name in sorted(files):
        print(f"wrote {out_dir / name}")
```

- [ ] **Step 3: Run the script to produce real schemas**

Run: `uv run python scripts/generate_schemas.py`
Expected: prints 5 "wrote ..." lines; `schemas/entry.*.json` now exist.

Run: `ls schemas/`
Expected:
```
entry.deep-work.json
entry.learning.json
entry.meeting.json
entry.offsite.json
entry.ops.json
.gitkeep
```

- [ ] **Step 4: Write the sync test**

Create `tests/test_schemas_in_sync.py`:

```python
"""Fail CI if the committed schemas/ drift from helpers/types.py."""

from __future__ import annotations

from pathlib import Path

from scripts.generate_schemas import SHAPE_FILES, generate

SCHEMAS_DIR = Path(__file__).resolve().parent.parent / "schemas"


def test_committed_schemas_match_current_models(tmp_path: Path) -> None:
    fresh = generate(tmp_path)
    for filename in SHAPE_FILES.values():
        committed = (SCHEMAS_DIR / filename).read_text()
        assert committed == fresh[filename], (
            f"{filename} is stale — run `uv run python scripts/generate_schemas.py` "
            "and commit the result."
        )
```

Note: this import requires `scripts/` to be importable. Add an `__init__.py`:

```bash
: > scripts/__init__.py
```

- [ ] **Step 5: Run the sync test**

Run: `uv run pytest tests/test_schemas_in_sync.py -v`
Expected: PASS.

Sanity-check the drift detection — change one Pydantic field temporarily, re-run the test, observe failure, revert:

```bash
# (Manual sanity check, optional)
# 1. In helpers/types.py change DeepWorkEntry.outputs default to default=[]
#    in a way that's not equivalent (e.g. add an extra field temporarily).
# 2. Run: uv run pytest tests/test_schemas_in_sync.py -v
#    Expected: FAIL with "stale".
# 3. Revert the change.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/generate_schemas.py schemas/ tests/test_schemas_in_sync.py
git commit -m "feat(schemas): generate JSON Schemas from Pydantic models + sync test"
```

---

## Task 6: Git scraper helper

**Files:**
- Create: `helpers/git_scrape.py`
- Create: `tests/test_git_scrape.py`

Reads commits from configured local git repos within a time window. Uses `git log` via `subprocess.run` (no `gitpython` dependency — simpler, fewer moving parts).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_git_scrape.py`:

```python
"""Tests for helpers.git_scrape."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from helpers.git_scrape import GitScrapeError, get_git_activity


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _seed_repo(path: Path, *, author_email: str = "barry@example.com") -> None:
    path.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", author_email, cwd=path)
    _git("config", "user.name", "Barry", cwd=path)
    (path / "README.md").write_text("hello\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-m", "init", cwd=path)
    (path / "README.md").write_text("hello, world\n")
    _git("add", "README.md", cwd=path)
    _git("commit", "-m", "expand greeting", cwd=path)


def test_returns_commits_in_window(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo)

    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    until = datetime.now(timezone.utc)

    commits = get_git_activity([repo], since=since, until=until)
    assert len(commits) == 2
    messages = [c.message for c in commits]
    assert "init" in messages
    assert "expand greeting" in messages
    for c in commits:
        assert c.repo == "demo"
        assert len(c.sha) >= 7


def test_filters_by_author(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo, author_email="barry@example.com")

    since = datetime(2000, 1, 1, tzinfo=timezone.utc)
    until = datetime.now(timezone.utc)

    matching = get_git_activity(
        [repo], since=since, until=until, author="barry@example.com"
    )
    assert len(matching) == 2

    none = get_git_activity(
        [repo], since=since, until=until, author="someone-else@example.com"
    )
    assert none == []


def test_raises_on_missing_repo(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist"
    with pytest.raises(GitScrapeError):
        get_git_activity(
            [bogus],
            since=datetime(2000, 1, 1, tzinfo=timezone.utc),
            until=datetime.now(timezone.utc),
        )


def test_raises_on_non_git_directory(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(GitScrapeError):
        get_git_activity(
            [plain],
            since=datetime(2000, 1, 1, tzinfo=timezone.utc),
            until=datetime.now(timezone.utc),
        )


def test_empty_window_returns_empty_list(tmp_path: Path) -> None:
    repo = tmp_path / "demo"
    _seed_repo(repo)
    far_past = datetime(1990, 1, 1, tzinfo=timezone.utc)
    far_past_end = datetime(1991, 1, 1, tzinfo=timezone.utc)
    assert get_git_activity([repo], since=far_past, until=far_past_end) == []
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_git_scrape.py -v`
Expected: ImportError — `helpers.git_scrape` doesn't exist.

- [ ] **Step 3: Implement the helper**

Create `helpers/git_scrape.py`:

```python
"""Scrape commit activity from local git repositories."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class GitScrapeError(RuntimeError):
    """Raised when a repo can't be reached or git fails for any reason."""


class CommitSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo: str
    sha: str
    when: datetime
    author_email: str
    message: str
    files_touched_count: int


def get_git_activity(
    repos: Sequence[Path],
    *,
    since: datetime,
    until: datetime,
    author: str | None = None,
) -> list[CommitSummary]:
    """Return commits across the configured repos within [since, until].

    Hard-fails (raises GitScrapeError) if any configured repo is missing
    or not a git repo, or if `git log` errors. This is intentional — the
    Vibe Check pipeline halts rather than producing logs with silent gaps.
    """
    results: list[CommitSummary] = []
    for repo in repos:
        if not repo.exists():
            raise GitScrapeError(f"configured repo does not exist: {repo}")
        if not (repo / ".git").exists():
            raise GitScrapeError(f"not a git repository: {repo}")
        results.extend(
            _scrape_one(
                repo, since=since, until=until, author=author
            )
        )
    return results


def _scrape_one(
    repo: Path,
    *,
    since: datetime,
    until: datetime,
    author: str | None,
) -> list[CommitSummary]:
    sep = "\x1f"  # ASCII unit separator — extremely unlikely to appear in commit text
    fmt = sep.join(["%H", "%aI", "%ae", "%s"])
    cmd = [
        "git",
        "log",
        f"--since={since.isoformat()}",
        f"--until={until.isoformat()}",
        f"--pretty=format:{fmt}",
        "--shortstat",
    ]
    if author is not None:
        cmd.append(f"--author={author}")

    try:
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        raise GitScrapeError(
            f"git log failed in {repo}: {e.stderr.strip() or e}"
        ) from e

    return _parse_log_output(proc.stdout, repo_name=repo.name, sep=sep)


def _parse_log_output(stdout: str, *, repo_name: str, sep: str) -> list[CommitSummary]:
    commits: list[CommitSummary] = []
    blocks = [b for b in stdout.split("\n\n") if b.strip()]
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        header = lines[0]
        try:
            sha, when_iso, email, message = header.split(sep, 3)
        except ValueError as e:
            raise GitScrapeError(f"unparseable git log line in {repo_name}: {header!r}") from e
        files_touched = 0
        for tail in lines[1:]:
            if "file" in tail and "changed" in tail:
                files_touched = int(tail.strip().split()[0])
        commits.append(
            CommitSummary(
                repo=repo_name,
                sha=sha,
                when=datetime.fromisoformat(when_iso),
                author_email=email,
                message=message,
                files_touched_count=files_touched,
            )
        )
    return commits
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_git_scrape.py -v`
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/git_scrape.py tests/test_git_scrape.py
git commit -m "feat(helpers): add git_scrape with hard-fail policy on missing repos"
```

---

## Task 7: Jira fetcher helper

**Files:**
- Create: `helpers/jira_fetch.py`
- Create: `tests/test_jira_fetch.py`

Fetches user activity from Jira Cloud (issues created, transitioned, commented on, assigned). Uses `httpx` for the request and `respx` to mock in tests.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_jira_fetch.py`:

```python
"""Tests for helpers.jira_fetch."""

from __future__ import annotations

from datetime import datetime, timezone

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
        since=datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc),
        until=datetime(2026, 5, 28, 23, 59, tzinfo=timezone.utc),
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
        since=datetime(2026, 5, 28, 0, 0, tzinfo=timezone.utc),
        until=datetime(2026, 5, 28, 23, 59, tzinfo=timezone.utc),
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
            since=datetime(2026, 5, 28, tzinfo=timezone.utc),
            until=datetime(2026, 5, 29, tzinfo=timezone.utc),
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
            since=datetime(2026, 5, 28, tzinfo=timezone.utc),
            until=datetime(2026, 5, 29, tzinfo=timezone.utc),
        )
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_jira_fetch.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the helper**

Create `helpers/jira_fetch.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_jira_fetch.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/jira_fetch.py tests/test_jira_fetch.py
git commit -m "feat(helpers): add jira_fetch with hard-fail on HTTP/network errors"
```

> **Note for the engineer:** the exact Jira activity endpoint and payload shape vary by Jira deployment. If the smoke test reveals a different shape on the user's instance, adjust `get_jira_activity` and update the tests. The contract (returns `JiraEvent` list, raises `JiraFetchError`) is the stable bit; the endpoint shape is discovery for the smoke-test phase (spec §14).

---

## Task 8: Log writer (markdown + YAML frontmatter)

**Files:**
- Create: `helpers/log_writer.py`
- Create: `tests/test_log_writer.py`

Each day is one markdown file at `<logs_dir>/YYYY-MM-DD.md`. Each entry is appended as: a YAML frontmatter block (the envelope + shape fields), a blank line, an H2 title, the narrative.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_log_writer.py`:

```python
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
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_log_writer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the writer**

Create `helpers/log_writer.py`:

```python
"""Append validated entries to per-day markdown files with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from helpers.types import EntryEnvelope


def write_log(entry: EntryEnvelope, *, logs_dir: Path) -> Path:
    """Append `entry` to `<logs_dir>/YYYY-MM-DD.md` and return the path.

    Idempotent on the entry's `id`: if an entry with the same id is already
    present in the file, the file is returned unchanged.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"{entry.date.isoformat()}.md"
    existing = path.read_text() if path.exists() else ""

    if _file_contains_id(existing, entry.id):
        return path

    block = _format_block(entry)
    new_text = block if not existing else existing.rstrip() + "\n\n" + block
    path.write_text(new_text)
    return path


def _format_block(entry: BaseModel) -> str:
    data = entry.model_dump(mode="json", exclude_none=False)
    # `model_dump(mode='json')` produces JSON-safe scalars (dates as ISO strings),
    # which yaml.safe_dump renders cleanly.
    fm = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
    title = data["title"]
    narrative = data["narrative"]
    return f"---\n{fm}\n---\n\n## {title}\n\n{narrative}\n"


_ID_PATTERN = re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE)


def _file_contains_id(text: str, target_id: str) -> bool:
    return any(m.group(1) == target_id for m in _ID_PATTERN.finditer(text))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_log_writer.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/log_writer.py tests/test_log_writer.py
git commit -m "feat(helpers): add log_writer with append + idempotency"
```

---

## Task 9: Log git-commit helper

**Files:**
- Create: `helpers/log_git.py`
- Create: `tests/test_log_git.py`

Tiny helper: ensures the logs directory is a git repo (init on first call) and commits the file at `path` with `message`. Failure is non-fatal at the call site, but the helper itself just raises if git breaks — caller decides policy.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_log_git.py`:

```python
"""Tests for helpers.log_git."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from helpers.log_git import LogGitError, commit


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def test_initializes_repo_on_first_call(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_file = logs_dir / "2026-05-28.md"
    log_file.write_text("---\nid: x\n---\n\n## t\n\nn\n")

    commit(log_file, message="log: 2026-05-28")

    assert (logs_dir / ".git").exists()
    log_output = _run("log", "--oneline", cwd=logs_dir).stdout
    assert "log: 2026-05-28" in log_output


def test_appends_commit_to_existing_repo(tmp_path: Path) -> None:
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    _run("init", "-q", "-b", "main", cwd=logs_dir)
    _run("config", "user.email", "test@example.com", cwd=logs_dir)
    _run("config", "user.name", "Test", cwd=logs_dir)

    f1 = logs_dir / "first.md"
    f1.write_text("first\n")
    _run("add", "first.md", cwd=logs_dir)
    _run("commit", "-m", "first", cwd=logs_dir)

    f2 = logs_dir / "second.md"
    f2.write_text("second\n")
    commit(f2, message="second")

    log_output = _run("log", "--oneline", cwd=logs_dir).stdout
    assert "first" in log_output
    assert "second" in log_output


def test_raises_on_unstageable_path(tmp_path: Path) -> None:
    bogus = tmp_path / "nope" / "missing.md"
    with pytest.raises(LogGitError):
        commit(bogus, message="x")


def test_handles_no_changes_gracefully(tmp_path: Path) -> None:
    """Committing the same file twice in a row is a no-op, not an error."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    f = logs_dir / "x.md"
    f.write_text("content\n")
    commit(f, message="first")
    # No changes since — should not raise.
    commit(f, message="redundant")
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_log_git.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the helper**

Create `helpers/log_git.py`:

```python
"""Commit appended log files to a local git repo at the logs directory."""

from __future__ import annotations

import subprocess
from pathlib import Path


class LogGitError(RuntimeError):
    """Raised when git operations on the logs directory fail unrecoverably."""


def commit(path: Path, *, message: str) -> None:
    """Stage and commit `path` inside its enclosing logs directory.

    Initializes a git repo on first use. A no-op commit (nothing to stage)
    is treated as success, not an error.
    """
    if not path.exists():
        raise LogGitError(f"cannot commit a non-existent path: {path}")

    repo = path.parent
    try:
        if not (repo / ".git").exists():
            _git("init", "-q", "-b", "main", cwd=repo)
            _git("config", "user.email", "vibe-check@local", cwd=repo)
            _git("config", "user.name", "Vibe Check", cwd=repo)

        _git("add", str(path.name), cwd=repo)

        status = _git("status", "--porcelain", cwd=repo).stdout
        if not status.strip():
            return  # nothing to commit; no-op success

        _git("commit", "-q", "-m", message, cwd=repo)
    except subprocess.CalledProcessError as e:
        raise LogGitError(
            f"git operation failed in {repo}: {e.stderr.strip() or e}"
        ) from e


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_log_git.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/log_git.py tests/test_log_git.py
git commit -m "feat(helpers): add log_git.commit with repo auto-init"
```

---

## Task 10: Bulletin renderer

**Files:**
- Create: `helpers/bulletin_render.py`
- Create: `tests/test_bulletin_render.py`
- Create: `tests/fixtures/bulletin_two_entries.expected.md`

Pure function. Takes a list of entries + date + style, returns rendered text. Slack-flavored markdown for the OCS Slack post; plain markdown for human consumption.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bulletin_render.py`:

```python
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
```

- [ ] **Step 2: Create the expected golden file**

Create `tests/fixtures/bulletin_two_entries.expected.md`:

```markdown
*Vibe Check — 2026-05-28*  ·  *5.75h total*

*Deep work* — _4.5h_
• *Drafted section 4 of compliance overview* (Policy Documentation, 4.5h)
  Made progress on 4.1 and 4.2.

*Meetings* — _1.0h_
• *MFA design review with security* (Onboarding, 1.0h, _review_)
  Reviewed the proposed MFA flow with the security team.
  Decided: Adopt WebAuthn as primary.

*Ops* — _0.25h_
• *Submitted April timesheet* (Admin, 0.25h, _invoicing_)
  Logged and emailed.
```

- [ ] **Step 3: Run the failing tests**

Run: `uv run pytest tests/test_bulletin_render.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement the renderer**

Create `helpers/bulletin_render.py`:

```python
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
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_bulletin_render.py -v`
Expected: all 4 tests PASS.

If the golden file diff fails on whitespace, copy the actual output into `bulletin_two_entries.expected.md` (this is normal during the first golden file run — verify the output is correct, then commit it as the baseline).

- [ ] **Step 6: Commit**

```bash
git add helpers/bulletin_render.py tests/test_bulletin_render.py tests/fixtures/bulletin_two_entries.expected.md
git commit -m "feat(helpers): add bulletin_render with golden-file test"
```

---

## Task 11: Timesheet aggregator

**Files:**
- Create: `helpers/timesheet.py`
- Create: `tests/test_timesheet.py`

Walks the markdown logs for a month, parses each entry's YAML frontmatter, and aggregates totals by client/project/shape. Produces a CSV and a human-readable markdown summary.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_timesheet.py`:

```python
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
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest tests/test_timesheet.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the aggregator**

Create `helpers/timesheet.py`:

```python
"""Aggregate monthly logs into a CSV + markdown summary for the invoice."""

from __future__ import annotations

import calendar
import csv
import io
import re
from collections import defaultdict
from datetime import date as date_cls
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class Timesheet(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    csv: bytes
    summary_md: str
    total_hours: float
    by_project: dict[str, float]


def build_timesheet(logs_dir: Path, *, year: int, month: int) -> Timesheet:
    """Walk `logs_dir`, sum hours for the given month, return CSV + summary."""
    if not logs_dir.exists():
        return _empty(year, month)

    entries = _read_month(logs_dir, year=year, month=month)

    by_project: dict[str, float] = defaultdict(float)
    for e in entries:
        by_project[e["project"]] += float(e["duration_hours"])

    total = round(sum(by_project.values()), 4)
    return Timesheet(
        csv=_to_csv(entries),
        summary_md=_to_summary_md(entries, year=year, month=month, total=total),
        total_hours=total,
        by_project=dict(by_project),
    )


def _read_month(logs_dir: Path, *, year: int, month: int) -> list[dict]:
    last_day = calendar.monthrange(year, month)[1]
    start = date_cls(year, month, 1)
    end = date_cls(year, month, last_day)

    entries: list[dict] = []
    for md_file in sorted(logs_dir.glob("*.md")):
        try:
            file_date = date_cls.fromisoformat(md_file.stem)
        except ValueError:
            continue
        if not (start <= file_date <= end):
            continue
        entries.extend(_parse_frontmatter_blocks(md_file.read_text()))
    return entries


_BLOCK = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL | re.MULTILINE)


def _parse_frontmatter_blocks(text: str) -> list[dict]:
    out: list[dict] = []
    for m in _BLOCK.finditer(text):
        parsed = yaml.safe_load(m.group(1))
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _to_csv(entries: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf, fieldnames=["date", "client", "project", "shape", "duration_hours", "title"]
    )
    writer.writeheader()
    for e in entries:
        writer.writerow(
            {
                "date": e.get("date", ""),
                "client": e.get("client", ""),
                "project": e.get("project", ""),
                "shape": e.get("shape", ""),
                "duration_hours": e.get("duration_hours", 0),
                "title": e.get("title", ""),
            }
        )
    return buf.getvalue().encode()


def _to_summary_md(entries: list[dict], *, year: int, month: int, total: float) -> str:
    by_project: dict[str, float] = defaultdict(float)
    for e in entries:
        by_project[e["project"]] += float(e["duration_hours"])

    lines = [f"# Vibe Check timesheet — {year}-{month:02d}", "", f"**Total: {total}h**", ""]
    for project in sorted(by_project):
        lines.append(f"- {project}: {by_project[project]}h")
    return "\n".join(lines) + "\n"


def _empty(year: int, month: int) -> Timesheet:
    return Timesheet(
        csv=_to_csv([]),
        summary_md=_to_summary_md([], year=year, month=month, total=0.0),
        total_hours=0.0,
        by_project={},
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_timesheet.py -v`
Expected: all 4 tests PASS.

Run the full suite to confirm nothing regressed:
Run: `uv run pytest -v`
Expected: all tests across tasks 2–11 PASS.

- [ ] **Step 5: Commit**

```bash
git add helpers/timesheet.py tests/test_timesheet.py
git commit -m "feat(helpers): add monthly timesheet aggregator (CSV + summary)"
```

---

## Task 12: README and OCS prompts

**Files:**
- Create: `README.md`
- Create: `ocs/prompts/system.md`
- Create: `ocs/prompts/shape-router.md`

The OCS prompts are committed text — no tests, just author + commit. The README orients a future reader.

- [ ] **Step 1: Write the README**

Create `README.md`:

````markdown
# Vibe Check

A personal work-log assistant for Barry, contracted through Afrolabs and embedded at Acme Bank. Vibe Check interviews Barry in Slack each day, classifies the work into one of five structured shapes, and produces:

1. **Per-day markdown logs** in `~/vibe-check-logs/` (the source of truth, auto-committed).
2. **A daily Slack bulletin** to a configured channel — the Afrolabs signal.
3. **A monthly CSV + markdown timesheet** for the invoice.

## Architecture

- **OCS** (Open Chat Studio, already running locally) hosts the interview pipeline and Slack channel.
- **Python helpers in `helpers/`** handle deterministic work: git/Jira scraping, log writing, bulletin rendering, monthly aggregation. The helpers know nothing about OCS — they're imported by OCS Python Nodes (or called from any Python context).
- **Pydantic models in `helpers/types.py`** are the single source of truth for entry shapes. JSON Schemas in `schemas/` are generated from them (`uv run python scripts/generate_schemas.py`) and consumed by OCS's Extract Structured Data node.

See [docs/superpowers/specs/2026-05-28-vibe-check-design.md](docs/superpowers/specs/2026-05-28-vibe-check-design.md) for the full design and rationale.

## Setup

```bash
uv sync
cp .env.example .env       # then fill in JIRA_TOKEN, etc.
uv run pytest              # run the test suite
```

## Regenerate JSON Schemas

After any change to `helpers/types.py`:

```bash
uv run python scripts/generate_schemas.py
uv run pytest tests/test_schemas_in_sync.py
```

Then re-import the affected shapes into the OCS Extract node and re-export the pipeline JSON to `ocs/pipelines/interview.json`.

## Layout

- `helpers/` — Python helpers (one file per responsibility). All TDD.
- `tests/` — pytest, mirrors `helpers/`.
- `schemas/` — generated JSON Schemas for OCS's Extract node. **Do not edit by hand.**
- `scripts/generate_schemas.py` — regenerates `schemas/` from `helpers/types.py`.
- `ocs/pipelines/` — exported OCS pipeline JSON.
- `ocs/prompts/` — system and routing prompts used inside the pipeline.
- `~/vibe-check-logs/` (outside this repo) — daily markdown files, local git repo, auto-committed.

## Conventions

See [CLAUDE.md](CLAUDE.md) for full conventions. Highlights:

- TDD on helpers, strictly.
- Pydantic models are the source of truth. Schemas are generated.
- Hard fail on source-ingestion errors (git, Jira) — don't log without context.
- Helpers never import anything OCS-shaped.
````

- [ ] **Step 2: Write the OCS system prompt**

Create `ocs/prompts/system.md`:

```markdown
# Vibe Check system prompt

You are Vibe Check — Barry's work-log assistant. You help Barry record his daily work in structured entries that feed his monthly timesheet and a Slack bulletin to Afrolabs.

You are honest, concise, and warm. You do not flatter. You do not pad.

## Your job in a session

1. Greet Barry briefly. If signal data (git commits, Jira events) was provided in context, summarize it in 1-2 sentences.
2. Ask "what were you up to?" and listen.
3. For each unit of work Barry describes, classify it as exactly one of the five **shapes**: `deep_work`, `meeting`, `offsite`, `ops`, `learning`. Confirm the shape with Barry before extracting fields ("this sounds like deep_work — yes?").
4. Once confirmed, hand off to the Extract Structured Data node with the appropriate shape schema.
5. After extraction, render the entry back in plain prose (one paragraph) and ask Barry to accept or correct.
6. If accepted, the entry is written to disk. Ask "anything else from today?"
7. When Barry says he's done, hand off to the bulletin assembler.

## What you do NOT do

- Do not invent activity Barry didn't describe.
- Do not fill in fields you can't confirm. Leave them empty and mention what's missing.
- Do not silently auto-classify when the shape is ambiguous — ask one clarifying question.
- Do not summarize or compress narrative Barry gave you. Preserve his words.

## Bulletin tone

The bulletin posted to Afrolabs is professional, concise, and honest. Not chipper. Not corporate.
```

- [ ] **Step 3: Write the shape-router prompt**

Create `ocs/prompts/shape-router.md`:

```markdown
# Shape router

Given the most recent user message and the conversation context, output exactly one of the five shape labels:

- `deep_work` — Barry was working solo on something (writing code, drafting docs, designing, reviewing).
- `meeting` — Barry was in synchronous collaboration with one or more people.
- `offsite` — Barry was at a different location than usual (client offsite, conference, workshop) — this beats other shapes when location is unusual.
- `ops` — administrative or operational work (invoicing, expenses, access, tooling, compliance) — catchall.
- `learning` — research, reading, training, course work that benefits Barry's current projects.

## Rules

1. **Location and context first.** If the activity happened at an unusual location, choose `offsite` even if the activity itself was deep work.
2. **Mode of work second.** Solo focused work → `deep_work`. Synchronous with others → `meeting`.
3. **Catchalls last.** `ops` and `learning` are for things that don't fit the above.
4. **When ambiguous, output `UNCLEAR` and one short clarifying question** rather than guessing.

## Output format

A single line with one of: `deep_work`, `meeting`, `offsite`, `ops`, `learning`, `UNCLEAR: <question>`.
```

- [ ] **Step 4: Create the OCS directories and a pipeline placeholder**

```bash
mkdir -p ocs/pipelines
```

Create `ocs/pipelines/.gitkeep`:

```
# The exported interview.json lives here once the smoke-test pipeline is built in OCS.
# See docs/superpowers/specs/2026-05-28-vibe-check-design.md §7 for the pipeline shape.
```

- [ ] **Step 5: Commit**

```bash
git add README.md ocs/
git commit -m "docs(ocs): add README, system prompt, shape-router prompt + ocs/ layout"
```

---

## Task 13: OCS pipeline build + smoke-test runbook

**Files:**
- Create: `docs/runbooks/smoke-test.md`
- (Eventually) Update: `ocs/pipelines/interview.json` from OCS export

This task is integration work, not code. There are no automated tests — the spec says we manually smoke-test the pipeline once. The runbook captures the steps so future-you (or another contractor) can reproduce it.

- [ ] **Step 1: Write the smoke-test runbook**

Create `docs/runbooks/smoke-test.md`:

````markdown
# Vibe Check pipeline smoke-test runbook

The OCS pipeline is configuration, not code. This runbook walks through bringing it up end-to-end against a local sandbox so the JSON we commit in `ocs/pipelines/interview.json` is reproducible.

## Prerequisites

- Local OCS instance running (`docker compose up` in your OCS checkout, typically).
- The Vibe Check repo cloned with `uv sync` complete.
- Generated JSON Schemas present in `schemas/` (`uv run python scripts/generate_schemas.py`).
- A throwaway git repo at e.g. `/tmp/vibe-smoke-repo/` with at least 2 seeded commits.
- A Jira API token for a sandbox project (or a recorded fixture — see §3 below).
- A Slack workspace with a bot configured in OCS pointing at a channel you can clean up (e.g. `#vibe-check-smoke`).

## 1. Bot + channel setup

1. In OCS, create a new chatbot named `vibe-check-smoke`.
2. Attach the Slack channel via OCS's Slack channel integration. Confirm a "hello" round-trip works.

## 2. Pipeline nodes (in order)

Match the flow from spec §7. Add these nodes:

1. **Router (intent).** Branches: `log`, `view`, `timesheet`, `help`.
2. **Python Node — git_scrape.** Call `helpers.git_scrape.get_git_activity` with the configured repos. **Hard-fail** policy: if it raises, route to a "couldn't reach git, please retry" reply node.
3. **Python Node — jira_fetch.** Same — hard-fail on error.
4. **LLM Node — opening probe.** Use `ocs/prompts/system.md` as the system prompt; pass git+jira context into the user message.
5. **LLM Router — pick shape.** Use `ocs/prompts/shape-router.md`. If output is `UNCLEAR: <q>`, ask the question and loop back.
6. **Extract Structured Data.** For the chosen shape, load `schemas/entry.<shape>.json`. Configure: up to 3 retries on validation failure; on final failure, set `needs_review: true` and store anyway.
7. **LLM Node — render draft entry; ask accept/correct.**
8. **Python Node — log_writer.write_log.** Pass the validated entry + the configured `logs_dir` (e.g. `/tmp/vibe-smoke-logs/`).
9. **Python Node — log_git.commit.** Best-effort.
10. **LLM Node — "more to log?"** Loop back to step 4 if yes.
11. **Python Node — bulletin_render.render_bulletin.** Style: `slack`.
12. **LLM Node — show bulletin, ask post/correct.**
13. **Send-to-Slack Node.** Channel: `#vibe-check-smoke`.

## 3. Recording a Jira fixture (optional)

If your Jira sandbox is unreliable, capture a payload once with curl:

```bash
curl -u "${JIRA_EMAIL}:${JIRA_TOKEN}" \
  "${JIRA_BASE_URL}/rest/api/3/activity?streams=user+IS+${JIRA_ACCOUNT_ID}" \
  > tests/fixtures/jira_activity.sample.json
```

In the Python node for Jira, you can branch: read from the fixture if `OCS_USE_JIRA_FIXTURE=1`, else hit the API.

## 4. Walkthrough

1. In Slack, DM the bot: `let's log today`.
2. Confirm git+jira summary is in the opening reply.
3. Type a deep work description, e.g.: `Spent 4 hours on the compliance policy section 4 draft.`
4. Confirm the shape question fires, answer `yes`.
5. Confirm the extracted entry rendering is accurate.
6. Confirm `/tmp/vibe-smoke-logs/<today>.md` was created with valid frontmatter.
7. Confirm a git commit appeared in `/tmp/vibe-smoke-logs/`.
8. Say `that's it for today`.
9. Confirm the bulletin renders and you can post it; verify it arrives in `#vibe-check-smoke`.

## 5. Export and commit the pipeline

Once the pipeline works end-to-end:

```bash
# Export from OCS UI → save as ocs/pipelines/interview.json
git add ocs/pipelines/interview.json
git commit -m "feat(ocs): commit working interview pipeline export"
```

## 6. Discovery items to revisit

These are listed in spec §14 and should be re-checked after smoke:

1. Exact Jira API endpoint behavior on your instance — adjust `helpers/jira_fetch.py` if needed.
2. OCS Slack channel scopes and app-level config specifics.
3. Whether the shape-router prompt needs tuning based on real responses.
4. Whether OCS round-trips the pipeline JSON cleanly or some UI-only state remains.
5. Whether a `/vibe status` quick command (no full interview) earns its place in V1.
````

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/smoke-test.md
git commit -m "docs(runbook): add OCS pipeline smoke-test runbook"
```

- [ ] **Step 3: Run the smoke test**

Execute the runbook. When successful, export the pipeline JSON, place it at `ocs/pipelines/interview.json`, and commit:

```bash
git add ocs/pipelines/interview.json
git commit -m "feat(ocs): commit working interview pipeline export"
```

If the smoke test reveals issues that require helper changes, return to the relevant task above (likely Task 7 for Jira shape or Task 6 for git author behavior), update tests first, then code.

---

## Self-review

Spec coverage check (each spec section → task):

| Spec §                            | Implemented by                  |
| --------------------------------- | ------------------------------- |
| §4 Architecture overview          | Task 13 smoke-test wires it all |
| §5 Repository layout              | Tasks 1, 5, 12                  |
| §6 Entry shapes (envelope + 5)    | Tasks 2, 3, 4                   |
| §7 OCS pipeline interview flow    | Tasks 12 (prompts), 13 (build)  |
| §8 Python helper contracts        | Tasks 6–11                      |
| §9 Storage and data flow          | Tasks 8 (writer), 9 (commit)    |
| §10 Error handling (hard-fail)    | Tasks 6, 7 (raises)             |
| §11 Testing strategy + seed tests | Tasks 2–11 (all TDD)            |
| §12 V2 / Afrolabs migration       | §V2 of CLAUDE.md + Tasks 4, 5   |
| §13 Out of scope                  | Honored by not appearing        |
| §14 Open items                    | Task 13 §6 captures them        |

Placeholder scan: no "TBD" / "TODO" / "implement later" / placeholder helper bodies anywhere. Each code step shows the full code.

Type consistency: `Entry`, `EntryEnvelope`, `LinkedSignal`, `CommitSummary`, `JiraEvent`, `Timesheet`, and the 5 shape models keep consistent names across all tasks. Field names match between `helpers/types.py` (Task 2-3), the writer's `model_dump` output (Task 8), the renderer's `isinstance` checks (Task 10), and the timesheet aggregator's dict-key reads (Task 11).
