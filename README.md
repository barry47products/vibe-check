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
