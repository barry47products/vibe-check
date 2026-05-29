# Vibe Check

A single-user work-log assistant. It runs a short daily interview over Slack, classifies each entry into one of five structured shapes, and produces three outputs:

- **Daily markdown logs** in `~/vibe-check-logs/` — the source of truth, auto-committed to a local git repository.
- **A daily Slack bulletin** posted to a configured channel.
- **A monthly timesheet** (CSV and markdown) for invoicing.

The conversational pipeline runs on Open Chat Studio (OCS). This repository holds the Python helpers, entry-shape definitions, and generated schemas that the pipeline depends on.

## How it works

OCS hosts the interview pipeline and the Slack integration. Its Python Nodes call into the helpers in this repository for all deterministic work: scraping git and Jira activity, writing log files, rendering the bulletin, and aggregating the monthly timesheet. The helpers have no knowledge of OCS and can be imported from any Python context.

Entry shapes are defined as Pydantic models in `helpers/types.py`, which are the single source of truth. The JSON Schemas in `schemas/` are generated from those models and consumed by the OCS Extract Structured Data node; they are never edited by hand.

The five entry shapes are `deep-work`, `learning`, `meeting`, `offsite`, and `ops`.

See [docs/superpowers/specs/2026-05-28-vibe-check-design.md](docs/superpowers/specs/2026-05-28-vibe-check-design.md) for the full design and rationale.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A running OCS instance, for the conversational pipeline
- A Jira API token, for activity scraping

## Setup

```bash
uv sync
cp .env.example .env      # then fill in JIRA_TOKEN and related values
uv run pytest             # run the test suite
```

## Regenerating schemas

After any change to `helpers/types.py`:

```bash
uv run python scripts/generate_schemas.py
uv run pytest tests/test_schemas_in_sync.py
```

Then re-import the affected shapes into the OCS Extract node and re-export the pipeline to `ocs/pipelines/interview.json`. `test_schemas_in_sync.py` fails if the committed schemas drift from the models.

## Project layout

| Path                          | Contents                                                              |
| ----------------------------- | --------------------------------------------------------------------- |
| `helpers/`                    | Deterministic Python helpers, one responsibility per file.            |
| `tests/`                      | pytest suite, organised by behaviour.                                 |
| `schemas/`                    | Generated JSON Schemas for the OCS Extract node. Do not edit by hand. |
| `scripts/generate_schemas.py` | Regenerates `schemas/` from `helpers/types.py`.                       |
| `ocs/pipelines/`              | Exported OCS pipeline JSON.                                           |
| `ocs/prompts/`                | System and routing prompts used in the pipeline.                      |
| `docs/`                       | Design spec and runbooks.                                             |

Daily logs live outside this repository in `~/vibe-check-logs/`, a separate local git repository.

## Development

See [CLAUDE.md](CLAUDE.md) for the full conventions. Key points:

- Helpers are developed test-first.
- Pydantic models are the source of truth; schemas are generated, never hand-edited.
- Git and Jira ingestion fail hard on error rather than logging without context.
- Helpers never import anything OCS-specific.
