# Surfaced v1 (personal) — Design

**Date:** 2026-06-09
**Status:** active
**Builds on:** the Vibe Check v2 pipeline (reuses its GitHub fetch logic + activity-ranking as the
basis for the GitHub tool). Surfaced is the *agentic* evolution: an OpenAI-Assistant-backed agent
with persistent memory, vs v2's deterministic pipeline.

## Why

Vibe Check v2 (deterministic `Resolve → Discover → Fetch → Draft`) answers "what did I do?" well,
but it can't accumulate context, take notes, or reason about its own tools. The "Surfaced" vision
(reflection + visibility + relationship management; *make work visible with the least effort*) needs
an **agent that holds editable memory and decides its own actions**. This was prototyped on a
separate agent platform; this spec brings the core loop into OCS.

## Substrate (decided)

Build inside OCS as an **Assistant** — which in OCS means a minimal pipeline `Start → Assistant →
End` where the **AssistantNode** is an OpenAI-Assistants-backed, tool-calling agent. (OCS has no
separate "assistant experiment" type; the AssistantNode is the agentic brain.)

What OCS supports (verified against the codebase):
- AssistantNode calls **Custom Actions** (HTTP/OpenAPI wrappers, Bearer auth) as tools.
- Agent reads **participant data** via `{participant_data}` in its instructions; writes it via the
  built-in Update/Append Participant Data tools.
- **Scheduled messages** route through the pipeline (so the heartbeat reaches the agent) — but post
  into the participant's latest session/thread (accepted limitation).
- **Slack @-mentions** in channels and DMs both route to the experiment (accepted).

Three gaps vs the agent platform, accepted for v1:
- **Self-updating instructions** → emulated with participant-data memory (the agent writes to
  memory, not to its own prompt).
- **Scheduled nudge threads into the last session** (no fresh top-level DM without an OCS change).
- **Parallel sub-agents** (`delegateTask`) → not native; the agent works sequentially.

## First slice (scope)

**Personal core loop only.** Out of scope for v1: team/client/management surfaces, weekly
stakeholder summaries, RAG/Collections. Those are later slices.

In scope:
- Accumulating memory: a `projects` registry + an `activity_log`, in participant data.
- Context capture via **DM** and **@-mention** in a channel.
- A **GitHub tool** (custom action) the agent calls on demand.
- A **daily heartbeat** ("did you work on X yesterday?").
- **Recall / synthesis** on demand from the activity log + a fresh GitHub pull.

## Components

### 1. The agent (AssistantNode)
- OpenAI assistant, capable model, instructions =
  [`ocs/bots/surfaced/prompts/assistant-instructions.md`](../../../ocs/bots/surfaced/prompts/assistant-instructions.md).
- Instructions embed `{participant_data}` (memory) and `{current_datetime}`; encode the GitHub
  rules, capture/heartbeat/recall behaviours, and Slack-mrkdwn style.
- Built-in tools (code interpreter / file search): **off** for v1.

### 2. Memory (participant data)
```json
{
  "projects": [
    {"name": "ChatterBridge", "repos": ["barry47products/chatterbridge"], "role": "owner",
     "cadence": "daily", "stakeholders": [], "notes": ""}
  ],
  "activity_log": [
    {"date": "2026-06-09", "project": "ChatterBridge", "source": "dm",
     "summary": "shipped v0.43.2", "context": ""}
  ]
}
```
- Read every turn via `{participant_data}`.
- Written via Update Participant Data (projects) and Append to Participant Data (activity_log) tools
  — which must be enabled on the agent/node.

### 3. GitHub custom action (the agent's hands on GitHub)
- OCS Custom Action: OpenAPI wrapper over `api.github.com`, auth provider `github-vibe-check`
  (Bearer PAT, read-only). Exposes: `search/commits`, `repos/{owner}/{repo}/commits`,
  `repos/{owner}/{repo}/pulls`, `user/repos`.
- The agent orchestrates ranking + per-repo rules in reasoning (logic moves from Discover/Fetch
  nodes into the agent + instructions). NOT a GitHub Action/CI — purely an outbound API call from
  local OCS.

### 4. Surfaces
- **DM** → check-in / ad-hoc capture / recall.
- **@-mention in a channel** → capture context to a project.
- **Daily heartbeat** → scheduled message → agent prompt (threads into latest session).

## Build order

1. Create the OpenAI **Assistant** in OCS (name, model, instructions). ← starting here
2. Create the **GitHub custom action** (OpenAPI schema + `github-vibe-check` auth) and attach it.
3. Enable the **participant-data tools** (Update/Append) on the agent.
4. Create the **experiment + pipeline** (`Start → Assistant → End`); connect **Slack** (DM + the
   channel for @-mentions).
5. Seed **participant data** (`projects` for ChatterBridge, Mulligans Law, OCS with roles).
6. Create the **daily heartbeat** scheduled message.

## Artefacts

```
ocs/bots/surfaced/
  prompts/assistant-instructions.md   # the agent's instructions
  github-action-schema.json           # OpenAPI schema for the GitHub custom action (next)
  NODES.md                            # assistant + action + pipeline + schedule notes (next)
```

## Out of scope / future

Team & client visibility, weekly management summaries, RAG/Collections for a large activity log,
multi-stakeholder distribution, fresh-thread scheduling, parallel delegation.
