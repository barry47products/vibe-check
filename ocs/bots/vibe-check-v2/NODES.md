# Vibe Check v2 — node → file map

A new OCS experiment, **Vibe Check v2**. Linear pipeline, **private DM only** — no router, no
branches, no posting. v1 stays deployed and untouched. Source of truth for the live nodes: the
files in this folder. After pasting any node, **Publish the chatbot**.

Full design: [../../../docs/superpowers/specs/2026-06-03-vibe-check-v2-design.md](../../../docs/superpowers/specs/2026-06-03-vibe-check-v2-design.md)

## Pipeline graph

```text
[Start] → [Resolve] → [Discover] → [Fetch] → [Draft] → [End]
```

## Nodes

| Node | Type | File | Notes |
| ---- | ---- | ---- | ----- |
| Resolve | Code | [snippets/resolve.py](snippets/resolve.py) | period + scope + context admin; writes temp state |
| Discover | Code | [snippets/discover.py](snippets/discover.py) | discovery mode only: ranks repos by commit activity (search/commits ∪ recent-push) + repo-name match; sets `vc_repos`. Passes through when contexts are configured. ≤2 calls |
| Fetch | Code | [snippets/fetch.py](snippets/fetch.py) | per-repo GitHub signals for `vc_repos`; `RELAY:` passthrough for admin. ≤10 calls |
| Draft | LLM | [prompts/draft.md](prompts/draft.md) | gpt-5.4-mini · Vibe Check OpenAI · **History = Global** · **no tools** |

Splitting Discover from Fetch gives each node its **own 10-call budget**, so activity-ranking (Discover) and per-repo signal fetch (Fetch) don't compete.

## Auth provider

`github-vibe-check` — Bearer auth provider holding the GitHub PAT (repo Contents:Read). Reuse the
v1 one.

## How it routes (no router needed)

Resolve sets `vc_mode` and returns; Fetch and Draft branch on it in-line:
- `checkin` → Fetch builds a `SIGNALS …` block → Draft writes the vibe.
- `manage` / `no_context` → Fetch returns `RELAY: <text>` → Draft echoes it verbatim.

## Period & scope grammar

- **No contexts configured →** Discover ranks your repos by **actual commit activity** in the
  window (`search/commits`) unioned with recently-pushed repos (so today's not-yet-indexed work
  still shows), top 5. Name a repo and it fetches that one — **exact name** wins (only that repo),
  otherwise a fuzzy token match. Contexts are optional — add them for guaranteed scoping/grouping.
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
