# Vibe Check — Design (Mirror)

**Date:** 2026-06-01
**Status:** Draft, pending user review
**Owner:** Barry Tandy
**Supersedes:** `docs/superpowers/specs/2026-05-28-vibe-check-design.md` (the work-log
interviewer) and the activity-synthesiser design in the Open Chat Studio workspace
(`vibe-check-design.md`, dated 2026-05-29). Both are folded into this one; see §11.

---

## 1. What Vibe Check is now

Vibe Check is a **reflective mirror** for one person (Barry). On demand, it holds up what
his **signals** show he actually did against what he **said he intended**, and — using
non-violent communication — invites him to notice the gap himself. It is not a manager, a
coach, or a status report. It is the one place he can be honest with himself about the
distance between the work and the story he tells about it.

This is a deliberate reframing. The two prior designs were **output machines**: feed them
activity, get an artefact (a log, a bulletin, a timesheet). This design makes the
**reflection the product**; artefacts, if they ever return, are downstream outputs the
mirror can emit — never its centre.

The shift was validated by a hands-on spike in OCS before this document was written (§3),
so the decisions below rest on observed behaviour, not speculation.

## 2. The core loop

```text
You tell it your intent  ──►  it gathers your real signals  ──►  it reflects the two
                                                                  against each other (NVC)
                                                              ──►  it asks one real question
```

- **Signals** — evidence of what was actually done in a period: git commits, PRs, issues
  (later: Jira, Drive). Facts.
- **Stated intent** — what Barry said the period was meant to be about. The "portrayal"
  side of the mirror.
- The mirror surfaces the **gap** between them, names it neutrally, and asks one open
  question. It holds tension without resolving it.

## 3. What the spike proved (evidence base)

Three check-ins were run by hand in OCS against the spike prompt
(`ocs/prompts/mirror-agent.md`); notes in `docs/runbooks/mirror-spike-notes.md`.

| Run | Data | Result |
| --- | ---- | ------ |
| 1 | Rigged sample (clean gap) | Caught the unmentioned context cleanly; NVC tone held; refused to reflect with only one face (intent missing → asked for it). |
| 2 | Real week (18–21 May) | Held the **both/and** on messy data: the intent *did* land but was compressed into one day around three days of other work. Did not flatter, did not nag. Question quality improved unprompted. |
| 3 | Run 2 data, billing-trigger added | Trigger fired mechanically, but the **invoice framing was rejected** — it made the mirror transactional. Correction: context-awareness is part of the mirror; invoices are a deferred output. |

**Conclusion:** the central bet — that signal-vs-intent reflection in NVC tone produces a
useful mirror — is proven. The remaining work is implementation, not concept.

## 4. Non-goals

- Not a project manager, scrum tool, or OKR tracker.
- Not a status report or bulletin generator (that was a prior design).
- Not a coach that prescribes; it reflects and asks.
- Not multi-user in V1.
- **Not a billing/timesheet tool.** It may *notice* that work spanned contexts; it does
  not propose invoices. (See §9 deferred.)

## 5. The mirror (the product)

The product is largely **one prompt**. `ocs/prompts/mirror-agent.md` is its source of
truth; it is not duplicated here. Its load-bearing properties, each confirmed in the
spike:

- **Two faces required.** With signals but no intent, it asks for intent once before
  reflecting. It will not reflect on half a mirror.
- **Observe, don't evaluate.** States what signals show in specific terms; never labels
  ("scattered", "good week").
- **Name the gap, don't judge it.** Puts intent and signal side by side; leaves the gap
  for Barry to resolve.
- **One real question.** Open, grounded, non-leading. Ends the turn.
- **Context-awareness is intrinsic.** When a period spans more than one context (OCS
  *and* Mulligans), it names this as *shape of attention* — a mirror observation, not
  admin.
- **No flattery, no moralising, no invoices.**

When the prompt is tuned in OCS and improves, the change is written back to
`mirror-agent.md` so the working version is the kept version.

## 6. Architecture — OCS-native spine

Built inside Open Chat Studio, reusing its primitives (the "Approach 1" spine from the
2026-05-29 design). The novelty is concentrated at the reflection node and the intent
store; the rest is known-good plumbing.

```text
input (Slack DM/channel, or OCS preview)
   │
   ▼
[Start]
   │
   ▼
[Router · cheap LLM]        check-in? · set-intent? · switch-context? · question?
   │                        reads contexts + intent + session state via built-in tools
   ▼
[Time-Range · code]         "this week" → ISO date range (deterministic, not the LLM)
   │
   ▼
[Signal gather]             github_activity + github_pulls_issues for the active context
   │
   ▼
[normalize · code]          → one context-tagged signal list (the contract, §7)
   │
   ▼
[Mirror · premium LLM]      reflect signals vs stated intent (the proven prompt, §5)
   │                        reads/writes intent memory (§8)
   ▼
[End]
```

- **Two-model split:** cheap model on the Router, premium on the Mirror (reflection
  quality is the whole point).
- **Reuse:** the GitHub Custom Actions, Time-Range node, Router skeleton, Slack binding,
  and participant-data storage all come from the 2026-05-29 design. The tested Python
  helpers from the 2026-05-28 design (`git_scrape`, `jira_fetch`) can back the Custom
  Actions.

## 7. Signals — declared-only, with a discovery seam

**V1 stance: declared-only.** Signals come from contexts Barry has declared (repos +
author handle in participant data). No discovery sweep across all his activity yet.

- **Why:** prove "no more pasting" on the reliable spine before taking on the broad-scope
  credential and messy mapping that discovery requires.
- **Credential upside:** no broad PAT. Public declared repos need only rate-limit auth;
  private declared repos need a token scoped to *just those repos*.

**The signal contract** (Pydantic, reusing the 2026-05-28 discipline):

```text
Signal = { context, source: "github", kind: "commit" | "pr" | "issue",
           ref, title, when, url }
```

The mirror reasons over a list of these — it never touches GitHub directly.

**The discovery seam.** Because the mirror consumes a `context`-tagged list, the model
*never changes* between phases:

- **Declared-only (V1):** every signal is tagged → no surprises, by construction.
- **Discovery (deferred):** a single additive fetch step appends `context: null` signals;
  the prompt already handles "activity outside what you've told me about." The mirror
  node, the contract, and the contexts are untouched.

This is the hybrid model's spine; the surprise layer is one step away when wanted.

## 8. Intent memory (promoted to core)

The spike showed (Run 1, fresh thread) that without recall of stated intent, every
check-in must re-ask for it. So **cross-session intent memory is load-bearing**, not the
"phase 5" nicety the prior design called it.

V1 implementation: a JSON field on the participant record, written by the Mirror node
when Barry states intent and read on the next check-in.

```text
intents: [ { context, stated, on_date, status } ]
```

Lightest possible home; no new Django models. Reconciliation of *stale* intent (e.g. an
intent never acted on) is a reflection opportunity the mirror can raise.

## 9. Data model

All storage rides on OCS primitives — no custom models in V1.

- **Contexts** — JSON on the participant record: `{ slug, name, github: { repos,
  author_handle } }`. Read/written via built-in Get/Update Participant Data.
- **Intent memory** — JSON on the participant record (§8).
- **Session state** — `{ active_context, conversation_phase }` for multi-turn flow
  (e.g. `awaiting_intent`).

## 10. Conversation & failure modes

| Situation | Response |
| --------- | -------- |
| Intent missing | Ask once what the period was meant to be about; don't reflect yet. |
| Signals sparse / zero | Treat as conversation, not error: ask what the period held (off, travel, non-code work). |
| Active context references an unknown repo | Surface the broken config; offer to fix it conversationally. |
| GitHub API failure | Tell the user, offer retry, fall back to conversation-only. |
| Work spans multiple contexts | Name it as shape of attention (mirror), never as an invoice prompt. |

## 11. Roadmap

V1 proves the loop on the smallest reliable surface. The **committed** phases then build
toward the full vision — they are planned work, not maybes. Each is cheap because the V1
architecture leaves a seam for it. A separate **optional tail** may never land.

### Committed roadmap

| Phase | Adds | Why / the seam it uses |
| ----- | ---- | ---------------------- |
| **V1 — Declared spine** | On-demand GitHub check-in, intent memory, the mirror | Proves "no more pasting" on the reliable surface |
| **2 — Proactivity** | Scheduled / signal-triggered check-ins — *it reaches out to you* | The heart of the original vision; same pipeline behind an OCS scheduled trigger. Runs on V1 signals — the value is the reach-out itself, before sources widen |
| **3 — Discovery signals** | Catches work you didn't mention (the "I noticed a PR on that OSS project" move) | Additive `context: null` fetch step (§7); the mirror prompt already handles it. Revisits the broad-PAT credential question (§7) |
| **4 — Jira / Slack / Drive sources** | Reflects the non-GitHub week (governance docs, community, eng tickets) | Signal contract (§7) is source-agnostic; add fetchers that emit the same shape |

**Order is deliberate:** proactivity comes early because "it reaches out" is the heart of
the product, worth having even on GitHub-only signals; discovery and broader sources then
enrich the proactive check-in. (Phases 3 and 4 are close in priority; either may go first.)

### Optional tail (genuinely deferred — may never land)

| Item | Note |
| ---- | ---- |
| **Invoices / timesheets / billing outputs** | The context split is already surfaced as data; a renderer could consume it later. Explicitly *not* the mirror's job (Run 3). |
| **External-artefact ingestion** (standup posts, actual invoices) | Intent is already a stored "portrayal" side; another portrayal source slots beside it. |
| **Team / client as first-class modes** | Self-core today; the team nudge is already an optional, real-knowledge-only output. |

## 12. Decision log (traced to evidence)

| Decision | Choice | Basis |
| -------- | ------ | ----- |
| Core purpose | Mirror is the product; artefacts are downstream | User direction; reframes both prior designs |
| Mirror's two sides | Stated intent vs signals | User direction; proven Runs 1–2 |
| Tone | Non-violent communication | Proven: held both/and without flattery or nagging (Run 2) |
| Initiation | On-demand in V1; **proactivity is committed Phase 2** | User decision; on-demand is V1 scaffold, "it reaches out" is the goal |
| Roadmap order | Spine → proactivity → discovery → sources | User decision; proactivity early because reach-out is the heart of the product |
| Relationship scope | Self-core; team/client as optional outputs | User decision, refined by Run 3 |
| Intent memory | Core, not deferred | Spike finding (Run 1 fresh-thread) |
| Signals model | Declared-only V1; discovery via additive seam | User decision; hybrid phased |
| Multi-context | Intrinsic mirror observation ("shape of attention") | Run 3: invoice framing rejected |
| Invoices/timesheets | Deferred output; prompt forbids proposing them | Run 3 |
| Substrate | OCS-native spine (Approach 1) | Reuses recent eng-reviewed work; smallest new surface |

## 13. Resolved implementation notes

Resolved by reading the OCS codebase (citations inline); these are inputs to the plan.

1. **GitHub Custom Actions.** OCS Custom Actions wrap an OpenAPI schema + a Bearer-token
   `AuthProvider` (`apps/custom_actions/models.py:32-125`,
   `apps/service_providers/auth_service/main.py:71-75`).
   - `github_activity` (commits): `GET /repos/{owner}/{repo}/commits?author=&since=&until=&per_page=100`,
     one call per declared repo; cap 100/page, flag `truncated` if a `next` link exists (D6).
   - `github_pulls_issues`: use the **Search API** — `GET /search/issues?q=author:{h}+repo:{o}/{r}+created:{a}..{b}`
     (PRs + issues in one call; split on `is:pr`/`is:issue`). **Rate limit 30 req/min** — a
     constraint for Phase-3 discovery, not for declared repos.
   - Normalize node maps responses → the `Signal` contract (§7).

2. **Time-Range node** (Python `CodeNode`): fixed configured timezone
   (Africa/Johannesburg), **not** Slack locale; compute in local time, emit UTC ISO-8601.
   Half-open `[since, until)`; "this week" = ISO Monday 00:00 → now; "yesterday" = literal
   calendar previous day (no weekend-skipping).

3. **Intent-memory write safety:** **thin validation wrapper** (reuse Design B's D9
   `update_context` pattern). Participant data is free-form encrypted JSON with no schema
   validation and a JSON-only LLM write tool (`apps/experiments/models.py:1317-1350`,
   `apps/chat/agent/tools.py:333-350`), so a Code node validates each intent against a
   Pydantic schema and appends to a bounded `participant_data["intents"]` list.

4. **One session per Slack thread: confirmed.** `external_id = "{channel_id}:{thread_ts}"`,
   `get_or_create` on it; `ExperimentSession.state` is per-session JSON loaded/saved each
   turn (`apps/slack/utils.py`, `apps/slack/slack_listeners.py:70-126`,
   `apps/experiments/models.py:1418`). **Consequence:** session state is per-thread and does
   not survive a new thread — which is *why* intent memory lives in participant data (§8),
   not session state. A check-in must stay within its thread.

5. **Prompt-injection hardening:** signals are attacker-influenceable (mainly shared/OSS
   repos). V1 mitigations: a prompt clause that signals are *data, not instructions*;
   structure + length-cap signals at the normalize node; route the only write through the
   §13.3 validation wrapper. Full sanitisation scales up at Phase 4 (others' content).

6. **Privacy/retention — constraint, not just a note.** Traces store full input/output +
   a `participant_data` snapshot + `session_state`, **indefinitely, no TTL, no redaction**,
   and export full content to Langfuse if a TraceProvider is set; Sentry uses
   `send_default_pii=True` (`apps/trace/models.py:19-60`, `config/settings.py`,
   `apps/service_providers/tracing/langfuse.py`).
   - **V1:** **no tracing provider is configured** on Barry's instance, so trace content
     stays in local Postgres and is *not* exported off-platform — the main worry is moot.
     Residual concern is only local indefinite retention; optionally add a trace/session
     purge task later (mirror `cleanup_old_evaluation_data`'s TTL pattern). Keep the
     tracing provider unset.
   - **HARD GATE before Phase 4 / any sensitive context:** redaction or retention must be
     solved before Jira/Drive/client data enters the `participant_data` snapshot — and
     before ever attaching a tracing provider once sensitive data flows.

## 14. V1.5 — pipeline split + (context, period) state model

V1 shipped as a single Code node that resolves context, switches, parses + persists the
period, fetches, and renders (cognitive complexity ~90). Live testing exposed two things that
make the monolith the wrong shape going forward:

- **Intent doesn't persist.** `current_intent` is written by the *LLM* (Update-Participant-Data
  tool) and `gpt-5.4` doesn't reliably call it — participant data shows `current_intent: None`
  after every run, so each new thread re-asks. Meanwhile the *deterministic* write the Code node
  does (`active_context`) is rock-solid. **Lesson: state must be written deterministically, not
  by the LLM.**
- **Multi-turn state is fragile.** The period had to be hacked into session state so the
  intent-answer turn didn't reset the window. More state is coming; it needs a home.

### Decomposition

```text
Start
 → Router            classify: manage-context (add/list) vs check-in
     ├─ manage ─────────────────────────────► Mirror (handles add/list via tools) → End
     └─ check-in →
         Resolve/State (Code, deterministic)
            • resolve context: message mention → switch + persist; else sticky
            • resolve period → a normalised period KEY (2026-05, 2026-W23, 2026-05-18)
            • look up the (context, period) record → intent
            • intent state machine (below)
            • owns ALL participant-data state writes
         → Fetch (Code, pure)   given repos + window → GitHub commits/PRs/issues
         → Mirror (LLM, pure)   reflect signals vs intent, OR ask for intent when flagged
         → End
```

Each node does one job: **Resolve/State** owns state, **Fetch** owns GitHub, **Mirror** owns
reflection. `fetch_signals.py` shrinks back to pure fetch.

### The (context, period) record — the memory that fixes intent

Stored in participant data, keyed by context slug + a **normalised period key** (so "this week"
in different weeks don't collide):

```text
participant_data["records"]["chatterbridge|2026-05"] = { intent: { stated, on_date } }
```

| In the record | Persist? | Why |
| ------------- | -------- | --- |
| **Intent** | **Yes, always** | Stable; written *deterministically* by Resolve. Per (context, period) → fixes both the re-asking and any cross-context bleed. |
| **Signals** | **No — re-fetch each run** | They change; caching goes stale for ongoing periods. Optional cache for *closed* periods is a later optimisation, not V1.5. |

### Intent state machine (deterministic, in Resolve)

- **Check-in for (ctx, period):** record has intent → pass it to the Mirror to reflect against.
  No intent → set a session flag `awaiting_intent = "<ctx>|<periodkey>"`; the Mirror asks.
- **Next turn:** if `awaiting_intent` is set **and** the message isn't a new check-in (no "vibe
  check" / context name / period) → treat the message as the intent answer, **store it in the
  record deterministically**, clear the flag, fetch + reflect. A new check-in instead overrides
  the pending question.

This is the user's own sketch ("check for what we know about ctx+period; if missing, get it +
store it; then reflect") realised — with intent as the stored thing and signals always fresh.

### Open implementation choices (for the build)

- **Router:** deterministic keyword vs LLM. "add a context X for owner/repo" wants LLM parsing
  of the repo; a Static/keyword router is fine for routing the branch itself.
- **Management writes** (add/list contexts): LLM via Append-tool, or deterministic in Resolve.
- **Inter-node state:** Code nodes pass strings, so structured handoff goes via session/temp
  state — Resolve writes the resolved `{context, window, intent, awaiting}`, Fetch/Mirror read it.

This supersedes the single-node pipeline shape in §6 for the next iteration; V1's monolith
stays as the working baseline until the split is built.

## 15. Next step — a build manual, not a code plan

Vibe Check is assembled in the OCS UI (pipelines are configuration, not a codebase), so
the forward artefact is a **build manual**: sequenced OCS-UI steps with copy-paste prompts
and Code-node snippets that Barry follows by hand. Not a TDD implementation plan, not a
Python package.

The first manual covers the **declared spine end-to-end**: create the chatbot → seed a
context → create the two GitHub Custom Actions → build the pipeline node-by-node (Router,
Time-Range, signal actions, normalize, Mirror, intent-memory wrapper) → test in the
preview → go live on Slack. Copy-paste artefacts live in their own files (as
`ocs/prompts/mirror-agent.md` already does) and are linked from the manual.

---

*This document is the contract for the Mirror version of Vibe Check. It supersedes the two
earlier specs and is meant to be read, argued with, and amended.*
