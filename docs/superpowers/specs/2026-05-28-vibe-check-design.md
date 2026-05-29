# Vibe Check — Design

**Date:** 2026-05-28
**Status:** Draft, pending user review
**Owner:** Barry Tandy
**Audience:** Barry (V1 user), with Afrolabs (David) as the bulletin recipient

---

## 1. Purpose

Vibe Check is a personal work-log assistant for an engineer (Barry) who is contracted through Afrolabs and embedded at Acme Bank.

Two outcomes:

1. **Honest, structured daily logs** of what work was done — usable for the monthly timesheet that accompanies the invoice.
2. **A daily Slack bulletin to Afrolabs** giving them a low-cost signal of what's moving, without micromanagement.

V1 is single-user (Barry). The architecture is shaped so a V2 rollout to other Afrolabs contractors is a configuration task, not a rewrite.

## 2. Non-goals

- Not a project management tool. It records what happened; it doesn't plan.
- Not a passive scraper. The user is in the loop on every entry.
- Not a multi-tenant SaaS in V1. One person, one machine, one Slack workspace.
- Not a replacement for Acme-internal tools (Jira, GitHub, calendar) — it observes them.

## 3. Decisions log

| Decision                  | Choice                                                            | Rationale                                                                             |
| ------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| V1 scope                  | Barry first, Afrolabs-shaped seams                                | Single-user value now, easy rollout later.                                            |
| Signal sources            | Manual Q&A + git commits + Jira tickets                           | Calendar / Confluence deferred.                                                       |
| Cadence                   | On-demand only                                                    | No scheduler, no daemon. User initiates.                                              |
| Data boundary             | Local-only on Barry's machine                                     | Acme data sensitivity.                                                               |
| Outputs (layered)         | Local markdown + Slack bulletin + monthly CSV/PDF                 | Three views of the same daily entries.                                                |
| Interview interface       | Slack (via OCS)                                                   | Original vision; OCS already running locally.                                         |
| Architecture style        | OCS pipeline + thin Python helpers                                | OCS does the conversational + extraction work; Python handles the deterministic bits. |
| Entry shapes              | 5 fixed: `deep_work`, `meeting`, `offsite`, `ops`, `learning`     | Predictable validation, deterministic rollups.                                        |
| Schema source of truth    | Pydantic models → JSON Schemas generated for OCS Extract node     | Single source; no drift.                                                              |
| Logs storage              | `~/vibe-check-logs/`, **auto-committed to a local git repo**      | Tamper-resistant history outside the code repo.                                       |
| Source-ingestion failures | **Hard fail** — don't log without git + Jira context              | Stricter; entries always grounded in real signals.                                    |
| Testing                   | pytest with TDD on helpers; pipeline manually smoke-tested for V1 | Helpers are real code; pipelines are config.                                          |

## 4. Architecture overview

```bash
                      [ Slack DM / channel ]
                              ▲ ▼
                  ┌───────────────────────────┐
                  │      OCS Pipeline         │  (already-running local OCS instance)
                  │                           │
   git log ─────► │  Python: git_scrape       │
                  │           │               │
   Jira API ────► │  Python: jira_fetch       │
                  │           │               │
                  │  LLM: interview           │
                  │  Routing: pick shape      │
                  │  Extract Structured Data  │  (consumes generated JSON Schema)
                  │           │               │
                  │  Python: log_writer       │──► ~/vibe-check-logs/2026-05-28.md
                  │  Python: log_git.commit   │       (auto-commit per entry)
                  │           │               │
                  │  Python: bulletin_render  │
                  │  LLM: confirm bulletin    │
                  │  Send-to-Slack node       │──► #vibe-check-barry (Afrolabs visibility)
                  └───────────────────────────┘

                      [ on-demand monthly ]
                              │
                              ▼
                  ┌───────────────────────────┐
                  │  Python: timesheet build  │──► timesheet-out/2026-05.csv
                  │                           │    timesheet-out/2026-05-summary.md
                  └───────────────────────────┘
```

**Boundaries:**

- **OCS pipeline** owns conversation, routing, structured extraction, Slack I/O.
- **Python helpers** own deterministic logic: source scraping, file I/O, rendering, aggregation.
- **Helpers never know about OCS.** They are pure functions of their inputs and importable from any Python context.
- **Markdown files are the source of truth.** OCS's Postgres holds only conversational scratch.

## 5. Repository layout

```bash
vibe-check/
├── README.md
├── CLAUDE.md                       # project-level Claude Code instructions
├── pyproject.toml                  # uv + ruff + pytest
├── .env.example                    # JIRA_TOKEN, OCS URL, etc.
│
├── ocs/
│   ├── pipelines/
│   │   └── interview.json          # exported OCS pipeline (committed)
│   └── prompts/
│       ├── system.md
│       └── shape-router.md
│
├── schemas/                        # generated from helpers/types.py
│   ├── entry.deep-work.json
│   ├── entry.meeting.json
│   ├── entry.offsite.json
│   ├── entry.ops.json
│   └── entry.learning.json
│
├── scripts/
│   └── generate_schemas.py         # regenerates schemas/ from Pydantic models
│
├── helpers/
│   ├── __init__.py
│   ├── types.py                    # Pydantic models = single source of truth
│   ├── git_scrape.py
│   ├── jira_fetch.py
│   ├── log_writer.py
│   ├── log_git.py                  # commits appended entries
│   ├── bulletin_render.py
│   └── timesheet.py
│
├── tests/                          # pytest, mirrors helpers/
│   ├── conftest.py
│   ├── fixtures/                   # valid + invalid entry examples per shape
│   ├── test_git_scrape.py
│   ├── test_jira_fetch.py
│   ├── test_log_writer.py
│   ├── test_log_git.py
│   ├── test_bulletin_render.py
│   ├── test_timesheet.py
│   └── test_schemas_in_sync.py     # asserts schemas/ matches current Pydantic models
│
└── docs/
    └── superpowers/specs/
        └── 2026-05-28-vibe-check-design.md   # this file
```

**Logs live outside the repo** at `~/vibe-check-logs/`, which is itself a git repo (initialized on first use, local-only). This keeps Acme-derived content out of the code repo.

## 6. Entry shapes

### Common envelope

| Field            | Type                 | Required | Notes                                                        |
| ---------------- | -------------------- | -------- | ------------------------------------------------------------ |
| `id`             | string (UUID)        | ✓        |                                                              |
| `date`           | ISO date             | ✓        |                                                              |
| `shape`          | enum (discriminator) | ✓        | `deep_work` \| `meeting` \| `offsite` \| `ops` \| `learning` |
| `duration_hours` | float                | ✓        | Invoiceable hours.                                           |
| `client`         | string               | ✓        | Defaults to `"Acme"`.                                       |
| `project`        | string               | ✓        | e.g., `"Policy Documentation"`.                              |
| `title`          | string               | ✓        | Short summary for the bulletin (<10 words).                  |
| `narrative`      | string               | ✓        | Free-text prose.                                             |
| `tags`           | list[string]         |          |                                                              |
| `linked_signals` | list[{kind, ref}]    |          | `kind ∈ {git, jira}`.                                        |
| `needs_review`   | bool                 |          | Set true when extraction had to give up after retries.       |

### Shape-specific payloads

**`deep_work`**

- `area`: `code` \| `design` \| `policy` \| `documentation` \| `review` \| `other`
- `outputs`: list[string]
- `blockers`: list[string] (optional)

**`meeting`**

- `meeting_type`: `1:1` \| `standup` \| `review` \| `workshop` \| `interview` \| `other`
- `attendees`: list[string]
- `decisions`: list[string]
- `action_items`: list[{`owner`, `item`}]

**`offsite`**

- `location`: string
- `purpose`: string
- `outcomes`: list[string]
- `travel_hours_separate`: float (optional)

**`ops`**

- `category`: `invoicing` \| `expenses` \| `access-management` \| `tooling` \| `compliance` \| `other`
- `items`: list[string]

**`learning`**

- `topic`: string
- `sources`: list[string]
- `summary`: string
- `applies_to`: list[string]

### Discriminator routing rule

Location and context choose first (`offsite` wins when location is unusual), then mode of work (deep solo vs. meeting), with `ops` and `learning` as catchalls. The pipeline always asks one confirmation question ("this looks like a `deep_work` entry — sound right?") before extracting.

## 7. OCS pipeline (interview flow)

The pipeline is one OCS pipeline, started by Barry messaging the bot in Slack.

**Steps:**

1. **Router: intent.** `log` \| `view` \| `timesheet` \| `help`.
2. **Source scrape (parallel).** Python nodes `git_scrape` and `jira_fetch` retrieve activity since the last log entry. Hard fail if either errors.
3. **LLM: opening probe.** Greets, summarizes detected signals, asks "what were you up to?"
4. **LLM Router: pick shape.** Identifies which of 5 shapes the entry is. Confirms with a single yes/no question.
5. **Extract Structured Data.** Uses the JSON Schema for the chosen shape. Up to 3 retries on validation failure; sets `needs_review: true` if all retries fail.
6. **LLM: render draft entry; ask accept / correct.**
7. **Python: `log_writer.write_log(entry, logs_dir)`** appends to today's markdown file.
8. **Python: `log_git.commit(path, message)`** commits the new entry. Best-effort; failure is non-fatal.
9. **LLM: "more to log?"** — loop back to step 3 if yes.
10. **Python: `bulletin_render.render(entries, date, style="slack")`.**
11. **LLM: show draft bulletin; ask post / correct.**
12. **Send-to-Slack node** posts to `#vibe-check-barry`.

**The same Slack thread holds the entire interaction.** Afrolabs sees only the final bulletin in the channel, not the interview noise.

## 8. Python helper contracts

Each helper is a pure function with Pydantic-typed I/O. Importable from OCS Python nodes or any Python context.

```python
# helpers/git_scrape.py
def get_git_activity(repos: list[Path], since: datetime, until: datetime,
                     author: str | None = None) -> list[CommitSummary]:
    """Returns commits in the window. Raises GitScrapeError on repo/shell failure."""

# helpers/jira_fetch.py
def get_jira_activity(base_url: str, token: str, account_id: str,
                      since: datetime, until: datetime) -> list[JiraEvent]:
    """Returns user's Jira activity in the window. Raises JiraFetchError on HTTP/auth failure."""

# helpers/log_writer.py
def write_log(entry: Entry, logs_dir: Path) -> Path:
    """Appends entry to logs_dir/YYYY-MM-DD.md with YAML frontmatter.
    Creates file if first entry of the day. Returns path."""

# helpers/log_git.py
def commit(path: Path, message: str) -> None:
    """Stages and commits path in its enclosing git repo. Initializes repo on first use."""

# helpers/bulletin_render.py
def render_bulletin(entries: list[Entry], date: date,
                    style: Literal["slack", "markdown"] = "slack") -> str:
    """Pure render. No I/O."""

# helpers/timesheet.py
def build_timesheet(logs_dir: Path, year: int, month: int) -> Timesheet:
    """Pure aggregation. Returns Timesheet(csv: bytes, summary_md: str,
    total_hours: float, by_project: dict[str, float])."""
```

**Properties:**

- All inputs are parameters. No module-level env reads.
- Pydantic models are the source of truth; JSON Schemas are generated via `python scripts/generate_schemas.py`.
- A `test_schemas_in_sync.py` test asserts the generated schemas match the current models — fails CI if you forget to regenerate.

## 9. Storage and data flow

```bash
                      ┌──────────────────────────┐
                      │   OCS Postgres           │  conversation transcripts,
                      │   (already running)      │  participant data, session state
                      └──────────────────────────┘  — internal to OCS only

                      ┌──────────────────────────┐
                      │   ~/vibe-check-logs/     │  SOURCE OF TRUTH for entries.
                      │   2026-05-28.md          │  Local git repo, auto-commit per entry.
                      │   2026-05-29.md          │
                      └──────────────────────────┘

                      ┌──────────────────────────┐
                      │ Slack: #vibe-check-barry │  Afrolabs signal — append-only,
                      │   2026-05-28 bulletin    │  one final bulletin per day.
                      └──────────────────────────┘

                      ┌──────────────────────────┐
                      │   timesheet-out/         │  DERIVED. Re-runnable any time.
                      │   2026-05.csv            │  Attach to monthly invoice.
                      │   2026-05-summary.md     │
                      └──────────────────────────┘
```

**Per-day markdown structure** — one file per day, N entries appended:

```markdown
---
id: 01HXYZ...
date: 2026-05-28
shape: deep_work
duration_hours: 4.5
client: Acme
project: Policy Documentation
title: Drafted section 4 of compliance overview
tags: [compliance, drafting]
linked_signals:
  - kind: git
    ref: acme-policy-docs@a1b2c3
  - kind: jira
    ref: JEWL-87
area: documentation
outputs: [Section 4.2 draft]
needs_review: false
---

## Deep work — section 4 draft

Spent the morning on the compliance overview... [narrative]
```

**Invariants:**

- Markdown is canonical. OCS-side state is recoverable from these files; the reverse is not true.
- Slack posts are broadcast-only. Corrections are made by editing the markdown and running another session.
- Timesheet is always re-computed from markdown — corrections propagate automatically.

## 10. Error handling

**Principle:** entries are committed to disk the moment they're validated. Everything after that is recoverable.

| Failure point                     | Policy                                                                                       |
| --------------------------------- | -------------------------------------------------------------------------------------------- |
| `git_scrape` error                | **Hard fail.** Halt; ask user to retry. No logging without context.                          |
| `jira_fetch` error                | **Hard fail.** Same.                                                                         |
| Extract returns invalid data      | **Re-ask** up to 3 times; then store with `needs_review: true`.                              |
| `write_log` (disk)                | **Hard fail.** Surface in Slack; user can retry.                                             |
| `log_git.commit` (post-write)     | **Warn, proceed.** Best-effort.                                                              |
| `render_bulletin`                 | **Hard fail with fallback.** Post a plain "see ~/vibe-check-logs/<date>.md" instead.         |
| Send-to-Slack                     | **Tell user, offer retry.** Don't auto-retry — duplicate posts are uglier than one missed.   |
| OCS session expires mid-interview | **Resumable.** `write_log` appends per entry; next session reads the day's file and resumes. |

## 11. Testing strategy

**Primary: pytest unit tests on helpers, TDD.**

- One test file per helper, mirroring the module name.
- Schema validation: per-shape `valid_*` and `invalid_*` fixtures in `tests/fixtures/`.
- Bulletin: golden-file tests on `render_bulletin`.
- Timesheet: contrived month → expected totals per project.
- Schemas-in-sync: a test that fails if `python scripts/generate_schemas.py` would produce different output than what's committed.

**Concrete first-day test set (TDD seed):**

1. `test_get_git_activity_returns_commits_in_window`
2. `test_get_git_activity_raises_on_missing_repo`
3. `test_write_log_creates_file_on_first_entry`
4. `test_write_log_appends_to_existing_day`
5. `test_render_bulletin_groups_by_shape` (golden file)
6. `test_build_timesheet_totals_hours_per_project`
7. `test_entry_validation_rejects_missing_required_field` (one per shape)

**Secondary: manual pipeline smoke test.**

- Spin up OCS locally with the imported pipeline.
- Throwaway git repo with seeded commits.
- Jira sandbox or recorded fixture.
- Run a real Slack session; verify bulletin posts.

**Deferred: OCS Evaluations.** Worth setting up once V1 has a corpus of real interview transcripts.

**Explicit non-tests:**

- Don't TDD the OCS pipeline (it's config).
- Don't mock the LLM in helper tests (helpers don't call the LLM).
- Don't write tests that bind to OCS internals.

## 12. V2 / Afrolabs migration

| What changes                                                        | What stays                                                     |
| ------------------------------------------------------------------- | -------------------------------------------------------------- |
| Pipeline becomes a template; one OCS chatbot per contractor.        | Entry shapes and helpers don't change.                         |
| Helpers become a `pip install vibe-check-helpers` package.          | TDD discipline on the package stays.                           |
| Each contractor's logs stay local; only bulletins flow to Afrolabs. | The "bulletin = signal, log = source of truth" boundary stays. |
| Optional team-level rollup service consuming bulletins.             | No V1 decision needs to anticipate this.                       |

**Single most important migration discipline:** keep Pydantic models, JSON Schemas, and the exported pipeline in lock-step. Any shape change = regenerate schemas + re-export pipeline + commit all three.

## 13. Out of scope for V1

- Calendar ingestion (Google / Microsoft).
- Confluence ingestion.
- Multi-user / multi-tenant.
- Scheduled prompts (end-of-day pings, morning brief).
- Mobile / web UI beyond Slack.
- Cloud-hosted storage of any kind.
- Off-machine backup of the logs git repo (it's local-only by default; user can add a private remote later).

## 14. Open items for the implementation plan

These are not design decisions — they're discovery items for the implementation phase:

1. Exact Jira API endpoints + auth model to use (cloud token vs. OAuth).
2. OCS Slack channel setup specifics on the user's instance (bot scopes, app-level config).
3. The exact prompt for the shape-routing LLM node (will iterate during smoke tests).
4. Whether OCS pipelines can be round-tripped JSON ↔ UI cleanly, or if some manual UI steps remain.
5. Whether to add a one-line `/vibe status` quick command for "what's logged so far today" without going through the interview flow.

These belong in the implementation plan (next step), not here.

---

**Next step:** invoke `superpowers:writing-plans` to turn this design into an executable implementation plan.
