# Vibe Check v2 — node → file map

A new OCS experiment, **Vibe Check v2**. Linear pipeline, **private DM only** — no router, no
branches, no posting. v1 stays deployed and untouched. Source of truth for the live nodes: the
files in this folder. After pasting any node, **Publish the chatbot**.

Full design: [../../../docs/superpowers/specs/2026-06-03-vibe-check-v2-design.md](../../../docs/superpowers/specs/2026-06-03-vibe-check-v2-design.md)

## Pipeline graph

```text
[Start] → [Resolve] → [Fetch] → [Draft] → [End]
```

## Nodes

| Node | Type | File | Notes |
| ---- | ---- | ---- | ----- |
| Resolve | Code | [snippets/resolve.py](snippets/resolve.py) | period + scope + context admin; writes temp state |
| Fetch | Code | [snippets/fetch.py](snippets/fetch.py) | GitHub signals for the window; `RELAY:` passthrough for admin |
| Draft | LLM | [prompts/draft.md](prompts/draft.md) | gpt-5.4-mini · Vibe Check OpenAI · **History = Global** · **no tools** |

## Auth provider

`github-vibe-check` — Bearer auth provider holding the GitHub PAT (repo Contents:Read). Reuse the
v1 one.

## How it routes (no router needed)

Resolve sets `vc_mode` and returns; Fetch and Draft branch on it in-line:
- `checkin` → Fetch builds a `SIGNALS …` block → Draft writes the vibe.
- `manage` / `no_context` → Fetch returns `RELAY: <text>` → Draft echoes it verbatim.

## Period & scope grammar

- **No contexts configured →** Fetch auto-discovers the PAT user's recently-pushed repos within
  the window (capped at 4/run for the call budget) and drafts from those. Contexts are optional —
  add them only when you want named grouping or per-project scoping.
- Bare `vibe check` → gap-aware window (since last vibe; first-ever = last 7 days), all contexts.
- `vibe check last week` / `… yesterday` / `… in may` → that period.
- `vibe check ocs` → that context only.
- Window + scope are **sticky within the day** (corrections keep them); a new period word re-scopes.
- `add a context <name> for <owner/repo>` / `list contexts` → admin (no LLM draft).

## Schedule (not a pipeline node)

Weekday-morning `ScheduledMessage`s (Mon–Fri, 08:00 SAST) with `prompt_text` from
[prompts/nudge.md](prompts/nudge.md). EventBot rephrases it; Barry's reply runs the pipeline. To
change the nudge, edit `prompts/nudge.md` and update the schedules' `custom_schedule_params`
`prompt_text` (no publish needed).
