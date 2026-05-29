# Vibe Check — project-level Claude Code instructions

> This file is loaded into every Claude Code session in this project. It complements `~/.claude/CLAUDE.md` (global). Where the two conflict, this file wins.

## What this project is

Vibe Check is a personal work-log assistant for Barry, contracted through **Afrolabs** and embedded at **Acme Bank**. It produces:

1. Structured daily work entries (5 fixed shapes) → monthly timesheet for invoicing.
2. A curated daily Slack bulletin → low-cost signal for Afrolabs.

**Design spec is canonical:** [docs/superpowers/specs/2026-05-28-vibe-check-design.md](docs/superpowers/specs/2026-05-28-vibe-check-design.md). Read it before making any non-trivial decision. If the spec is silent on something, raise the question — don't invent.

## Architecture in one paragraph

OCS (Open Chat Studio, already running locally) hosts the conversational pipeline that interviews Barry in Slack, classifies the entry into one of 5 shapes, and extracts structured data. OCS Python Nodes call into thin Python **helpers** in this repo for deterministic work: git scraping, Jira fetching, markdown log writing, bulletin rendering, monthly timesheet aggregation. **Pydantic models** in `helpers/types.py` are the single source of truth; JSON Schemas in `schemas/` are *generated* from them and consumed by OCS's Extract Structured Data node.

## Stack

- **Language:** Python 3.12+
- **Package manager:** `uv`
- **Tests:** `pytest`
- **Lint/format:** `ruff` (check + format)
- **Types:** Pydantic v2 + `mypy --strict` for the helpers
- **External:** OCS via its API/Slack channel; Jira REST API; local `git` for commit scraping and for committing log entries

## Non-negotiables for this project

These extend the global CLAUDE.md non-negotiables, not replace them.

1. **TDD on helpers, full stop.** Every helper function gets a failing test first. The global CLAUDE.md is authoritative here. Pipeline config is not code; it doesn't get TDD.
2. **No mocking the LLM in helper tests.** Helpers never call the LLM — the LLM lives in OCS. If you find yourself mocking an LLM in a helper test, you're testing the wrong thing.
3. **Markdown logs are the source of truth.** OCS's Postgres is conversational scratch. Any feature that treats OCS state as authoritative is broken.
4. **Hard fail on source-ingestion errors.** `git_scrape` and `jira_fetch` raise on failure; the pipeline halts. Don't add silent fallbacks "for convenience" — they corrupt the log.
5. **Helpers don't know about OCS.** They are pure functions of their inputs and importable from any Python context. If a helper imports anything OCS-shaped, the boundary is wrong.
6. **Schemas are generated, never hand-edited.** `schemas/entry.*.json` come from `scripts/generate_schemas.py` walking `helpers/types.py`. A test (`test_schemas_in_sync.py`) fails CI if the committed schemas drift from the models.
7. **Pydantic = source of truth for shapes.** All entry shape changes start in `helpers/types.py`, regenerate schemas, re-export the OCS pipeline, commit all three in the same change.
8. **Local-only data.** No cloud storage, no off-machine syncs (unless the user explicitly opts in for the log repo). Acme-derived data does not leave Barry's laptop.

## What V1 deliberately does NOT do

See §13 of the design spec for the full list. Do not add these without an explicit conversation:

- Calendar / Confluence ingestion
- Multi-user / multi-tenant
- Scheduled prompts
- Mobile or web UI
- Cloud-hosted storage of any kind

## Hexagonal architecture — calibrated

The global CLAUDE.md references the hexagonal-architecture skill. For Vibe Check V1, **we are deliberately not applying full hex arch.** Reason: OCS provides the platform-level structural separation that ports-and-adapters would otherwise give us. The Python helpers are narrow utilities, not a domain layer. Don't introduce a `domain/` directory, port interfaces, or adapter factories in V1. If complexity grows past one function per file, revisit.

## Conventions

- **Imports at module top level**, never inside functions. (Carry-over from global CLAUDE.md; reinforced here.)
- **No comments explaining *what*.** Names and types do that. Only write a comment when *why* is non-obvious — a hidden constraint, a workaround for a specific bug.
- **No 1:1 file-to-test mapping enforced.** Tests organize by behavior, not file structure. Mirror is a default, not a rule.
- **YAML frontmatter in markdown logs uses snake_case.** Mirrors the Pydantic field names.

## Skills that apply here

Load on demand:

| Skill | When |
|---|---|
| `testing` | Writing or reviewing tests. |
| `tdd` | Any time you're about to write production code. |
| `functional` | Refactoring helpers — preferred patterns. |
| `expectations` | After completing meaningful work, capture learnings. |
| `planning` | Significant work; we plan via spec + plan files in `plans/`. |

The `hexagonal-architecture` skill **does NOT apply to V1** of this project (see calibration above).

## Useful commands

```bash
# Once helpers/ exists:
uv sync                    # install deps
uv run pytest             # run tests
uv run ruff check         # lint
uv run ruff format        # format
uv run mypy helpers       # type check
uv run python scripts/generate_schemas.py   # regenerate JSON schemas

# Verify schemas haven't drifted:
uv run pytest tests/test_schemas_in_sync.py
```

## How to handle OCS pipeline edits

OCS pipelines are authored in the OCS web UI. The exported JSON lives in `ocs/pipelines/interview.json` and is committed. Workflow:

1. Edit the pipeline in OCS.
2. Export it.
3. Replace `ocs/pipelines/interview.json`.
4. Commit the change with a message explaining what changed and why (the JSON diff is large; the commit message is what reviewers actually read).

If a pipeline change requires a schema change, do the schema change *first* in `helpers/types.py`, regenerate, then update the pipeline. Reverse order causes pipelines to reference fields that don't exist yet.

## Where to find things

- **Design spec:** [docs/superpowers/specs/2026-05-28-vibe-check-design.md](docs/superpowers/specs/2026-05-28-vibe-check-design.md)
- **Implementation plan(s):** `plans/` (created by `superpowers:writing-plans`)
- **OCS pipeline source:** `ocs/pipelines/interview.json` + prompts in `ocs/prompts/`
- **Entry shape definitions:** `helpers/types.py` (Pydantic) → generated to `schemas/`
- **Local logs (outside this repo):** `~/vibe-check-logs/` (its own git repo)
