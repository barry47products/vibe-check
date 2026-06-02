# Vibe Check — Design (Heartbeat)

**Date:** 2026-06-02
**Status:** Consensus reached (Round 3 outside review); ready to build
**Owner:** Barry Tandy
**Extends:** [`2026-06-01-vibe-check-mirror-design.md`](2026-06-01-vibe-check-mirror-design.md)
(the reflective Mirror). This document makes its **committed Phase 2 — Proactivity**
concrete. It does not supersede the Mirror design; it builds the proactive layer the
roadmap promised, and reuses the V1/V1.5 spine (Resolve → Fetch → Mirror).

> **Revision note.** R1 corrected the trigger mechanism (an OCS `ScheduledMessage` runs a
> one-shot `EventBot`, **not** a pipeline). R2 fixed the handshake-state write ownership,
> unified node names, sourced the liveness metric correctly, and added the multi-session-drift
> guard. See the revision log (§15).

---

## 1. What this increment is

The **Heartbeat** is the proactive layer of Vibe Check: instead of waiting to be messaged,
it **reaches out every weekday morning** with a nudge; when Barry replies, it shows him a
draft of what his real signals say he did yesterday, lets him confirm or correct it with **a
reply and a tap**, and — on his approval — posts a short **salute** to a team channel so the
work is *seen*.

This is the move the source conversations (Barry ↔ David, May–June 2026) returned to as **the
heart of the product**: *"for it to reach out to you in a DM and say, hey, did you work on
Joule yesterday? … and then it goes to the Joule channel: heads up, Barry did some work on
Joule yesterday."* The Mirror design deferred this; this increment delivers it.

**Why proactive, why now.** The Mirror (V1) proved the *reflection* works on a reliable
GitHub-only spine. But a mirror you must remember to look into is not yet a habit. The
recurring failure mode across years of Afrolabs engagement logs is that visibility tooling
gets **overcooked** — a grind, batched, late, dead. The bet: **a once-a-day, low-friction,
signals-grounded reach-out** is the smallest thing resilient enough to become a living habit —
and *being seen* (the salute) is the feedback loop that keeps it alive. §11 defines how we'll
know whether the bet is working, and when to kill it.

## 2. Two surfaces, one human gate

Vibe Check has **two distinct surfaces**, and conflating them would break the product:

- **The private mirror** — audience-free, forever. Its prompt is explicit: *"You belong to
  Barry alone. Nobody else reads this"* (`ocs/prompts/mirror-agent.md`). This is where Barry
  is honest with himself. The deep NVC reflection lives here. **The heartbeat never posts
  this anywhere.** (Deferred in this increment — D6.)
- **The salute** — deliberately *performative* and team-visible. A short, Barry-approved line
  that says *"I'm here, this is what moved."* It has its own norms (presence over volume; §8).

**Honest about the boundary:** the salute is drafted from the *same* yesterday signals the
mirror reflects on, so the separation is **conceptual, enforced by one human gate** — the D4
approval step — not by a mechanical wall. One distracted "yep" could surface a private-repo
project name to a team channel. The mitigations, in order of strength: (a) the approval gate
(Barry edits before posting — always); (b) **optional deterministic guard** in the Stage-draft
node that strips private-context names / requires an extra confirm when a private context
appears in the draft (recommended once private contexts are declared); this guard lives in the
**Stage** node. We never point the
mirror at a channel; the salute is its own, deliberately-public thing.

## 3. The core loop

```text
weekday morning: schedule fires an EventBot NUDGE into the DM       (run #1 — not the pipeline)
      │
      ▼
Barry replies ("go" / "vibe check")                                 (run #2 — the pipeline)
      │
      ├─ fetch real signals (all declared contexts, "yesterday")
      ├─ draft a 2-sentence salute in Barry's voice
      └─ DM the draft + "post this? (yep / edit / day off)"
      │
      ▼
Barry taps "yep" (or edits, or "day off")                           (run #3 — the pipeline)
      │
      ▼
post the approved salute to the team channel        (nothing posts without Barry's approval)
```

> **Note:** the confirm step crosses pipeline-run boundaries. The nudge, the draft, and the
> confirmation are **three separate invocations** in one persistent DM thread; state is carried
> between them via session + participant data (§6, §7). This is why the handshake needs an
> explicit state machine (§9).

The principle, straight from the conversations: **correct, don't create.** The bot never opens
with a blank *"what did you do yesterday?"* (the version that "never really worked — you just
get silence"). The signals-grounded draft (run #2) is where the "magic" lives; Barry's job is
to ratify or fix it, not author it.

## 4. Product decisions (locked this session)

| # | Decision | Choice | Why |
| - | -------- | ------ | --- |
| D1 | Initiation | **Proactive** — schedule nudges Barry; his reply runs the pipeline | "The heart of the product." Mirror V1 was on-demand. |
| D2 | Reach-out shape | **Signals-grounded draft** he confirms/corrects | "Correct, don't create." Blank interrogation dies in silence. |
| D3 | Cadence & scope | **Daily (weekday morning), all declared projects in one ping**, signal-gated (§8) | Fullest "magic mirror." Signal-gating keeps quiet days from nagging. |
| D4 | Approval gate | **Always** — exact line shown; reply, then one tap to post, or edit first | "Federated — you decide what to share." The V1 redaction mechanism (§2, §8). |
| D5 | Salute voice | **Short narrative** (≈2 sentences), *bot-drafted*, Barry one-taps to post | Answers *did you work?* and *on what?* Bot drafts → ratify is one tap, not authoring. |
| D6 | NVC reflection in the heartbeat | **Deferred** (Mirror "Option 3") | Heartbeat first; earn the daily habit before re-layering the deep mirror. |
| D7 | Pipeline granularity | **Fine-grained, branched**, ≤3 LLM nodes *on the heartbeat path* | Tune/test each prompt and Code node independently (§5). |

## 5. Pipeline architecture (fine-grained, branched)

Per D7, small single-purpose nodes; deterministic work in cheap **Code** nodes; **LLM** nodes
limited to three *on the heartbeat path* (Router, Draft, Interpret). The reused on-demand
branch adds the premium Mirror node — four LLM nodes exist across the whole graph, three on any
single heartbeat path.

**Canonical node names** (used consistently below): **Router**, **Resolve-HB** (the forked
heartbeat resolver/router), **Fetch**, **Draft**, **Stage** (stages the draft + opens the
handshake), **Interpret**, **Close** (closes the handshake), **Post**.

```text
(weekday morning)  ScheduledMessage → EventBot nudge into DM     ← run #1, NOT the pipeline (§6)
        │
        ▼  Barry replies in the DM thread
[Start]
        │
        ▼
[Router · cheap LLM]   coarse intent only:  check-in-ish │ manage-context
        ├─ manage-context ──────────► [Context admin · Code] ─────────────────► [End]
        │
        └─ check-in-ish ─►
              [Resolve-HB · Code]   THE deterministic brain. Decides the precise route
                    │               from STATE, not from an LLM guess:
                    │                 • awaiting_confirm set? → heartbeat-REPLY
                    │                 • else if nudge-originated / "vibe check" → heartbeat-OPEN
                    │                 • else → on-demand check-in (existing V1.5)
                    │
                    ├─ on-demand ─────► (existing Resolve→Fetch→Mirror, untouched) ──► [End]
                    │
                    ├─ heartbeat-OPEN ─►
                    │     [Fetch · Code]    GitHub across all declared repos  ← fetch_signals.py
                    │           │
                    │           ▼
                    │     [Draft · LLM]     2-sentence salute draft   ◄── TUNE: voice
                    │           │
                    │           ▼
                    │     [Stage · Code]    write pending_salute(date,text); set awaiting_confirm;
                    │           │           DM the draft + "yep / edit / day off"
                    │           ▼
                    │         [End]   (Barry replies later → run #3)
                    │
                    └─ heartbeat-REPLY ─►
                          [Interpret · LLM]  classify: approve │ edited-text │ day-off  ◄── TUNE
                                │
                                ▼
                          [Close · Code]   match reply to pending_salute(date); clear flag;
                                │           on approve/edit → hand text to Post; on day-off → stop
                                ▼
                          [Post · Code]     chat.postMessage to team channel (§6)
                                │
                                ▼
                              [End]
```

**Why this split.** Each node has one responsibility and is independently testable/tunable;
the voice lives in one LLM node, fetch bugs can't reach the salute, and the three routes are
isolated. **The disambiguation the review flagged as the linchpin is deterministic**, decided
in **Resolve-HB** from `awaiting_confirm` — exactly as `resolve.py:158-162` already
disambiguates an intent answer from a new command via `awaiting` + `is_command` — *not* left to
a cheap LLM. The Router only does coarse routing; the precise open/reply/on-demand decision is
state, not guesswork.

**Reuse ledger (corrected).** The heartbeat **forks** a dedicated **Resolve-HB** Code node
(window fixed to "yesterday", scope = *all* declared contexts, owns routing + handshake-clear).
The existing `resolve.py` stays **untouched** for the on-demand branch (single active context,
full period parsing). They do **not** share a node and use **separate** session-state keys, so
a heartbeat run can't clobber `vc_last_period`/`vc_awaiting` set by an on-demand turn in the
same thread (§7). `fetch_signals.py` is reused as-is. **New** work: the scheduled nudge,
Resolve-HB, Draft, Stage, Interpret, Close, Post.

## 6. OCS mechanics (verified against OCS source)

The proactive capability is native to OCS but **not** how the first draft assumed.

**What the schedule actually does (the R1 correction).** A `ScheduledMessage`
(`apps/events/models.py:459`) fires via the Celery-beat task `poll_scheduled_messages`
(`apps/events/tasks.py:66`; beat interval 60s, `config/settings.py:486-488`). When due,
`ScheduledMessage._trigger()` (`apps/events/models.py:541`) calls
`experiment_session.ad_hoc_bot_message(prompt_text)` (`apps/experiments/models.py:1523`) →
`_bot_prompt_for_user` (`:1568`) → **`EventBot.get_user_message()`** (`apps/chat/bots.py:351`,
class at `:301`). `EventBot` is a **single-shot LLM** whose system prompt only *rephrases an
instruction into a chat message* from conversation history + participant data + datetime. It
**cannot** run the pipeline, call Code nodes, or fetch GitHub. The event action `PIPELINE_START`
(`apps/events/actions.py:100`) exists but is reachable only from `StaticTrigger`/`TimeoutTrigger.fire()`,
never from a `ScheduledMessage`.

**Consequence (the architecture this drives).** The morning schedule sends a **nudge** only
(e.g. *"Morning 👋 ready for your vibe check? Reply and I'll pull yesterday."*). Barry's reply
is an inbound message that **runs the pipeline** — confirmed: inbound Slack →
`apps/slack/slack_listeners.py:31-42` → `channels.py` `new_user_message` →
`PipelineBot.process_input` → `invoke_pipeline` → `_run_pipeline` (`apps/chat/bots.py:62,139,144`),
which builds the full DAG, so Code nodes run on inbound turns. His confirmation reply runs it
again. The pipeline executes on Barry's turns, exactly as the existing on-demand check-in does.

**Verbatim where it matters.** The nudge is *rephrased* by `EventBot` (not sent verbatim) —
harmless for a pre-fetch nudge. The **draft and salute are produced in-pipeline** (Draft LLM
node + Post Code node), so they are verbatim and approval-gated.

**Existing-session constraint (real).** `_trigger()` no-ops if
`participant.get_latest_session(experiment)` is None (`apps/events/models.py:543-546`). The
heartbeat lives in **one persistent DM thread**: Barry messages the bot once to bootstrap it,
and the schedule reaches into that thread thereafter. The scheduled nudge posts into the
session's stored thread because `SlackChannel.send_text_to_user` parses the session
`external_id` (`channel_id:thread_ts`) when there's no inbound message
(`apps/chat/channels.py:1399-1411`); Barry's in-thread reply carries that `thread_ts`, so
`get_session_for_thread` (`apps/slack/slack_listeners.py:118-123`) returns the **same** session
and Resolve-HB sees `awaiting_confirm`.

**Multi-session drift (R2 guard).** `_trigger()` fires into `get_latest_session`, ordered by
`-created_at` (`apps/experiments/models.py:1159`). If Barry ever starts a **new top-level DM**
(no `thread_ts`), a new session is created and becomes "latest"; future nudges fire there
(empty state) while a staged draft is stranded in the old thread. Mitigation (§8 + setup): pin
the heartbeat to a known session, and have Resolve-HB detect drift by **session identity** — a
nudge arriving in a session whose stored thread differs from the pinned heartbeat thread (not
via `last_heartbeat_date`, which is participant-level and therefore present in any new session)
— and re-bootstrap; document "reply in-thread; don't start a new DM."

**Salute-to-channel — a tracked dependency (R1/R2), not a footnote.** The salute goes to a
*team channel*, a different destination from the DM. `send_message_to_user()` cannot target an
arbitrary channel and **no native send-to-channel node exists** (the node set is
RenderTemplate, LLM, SendEmail, Router/StaticRouter, Extract*, Assistant, Code —
`apps/pipelines/nodes/nodes.py`). The viable route is a **Code-node `http.post` to
`https://slack.com/api/chat.postMessage`** with a `chat:write` Bearer **AuthProvider** (the
`http` client is injected into Code nodes and supports `auth=<provider>`,
`apps/utils/restricted_http.py:122,328`) — equivalently an OpenAPI **Custom Action**. **Spike
this before the build** (§10.1): confirm `slack.com` is reachable under the team's
`RestrictedHttpClient` egress rules and the AuthProvider resolves inside a Code node
(`_resolve_auth_headers` can raise "not available in this context"), and define a **degraded
fallback** (salute-to-self in the DM) so a failed spike doesn't sink the increment.

**Scheduling is interval-based, not cron.** `next_trigger_date` advances by `relativedelta`
(`apps/events/models.py:491`); there is no native "weekdays only" or fixed-clock-time
expression. The pipeline must **early-exit on weekends** and the morning window is computed
in-pipeline (Africa/Johannesburg, per Mirror §13.2). (This weekend gate is a *cadence* concern;
it does **not** change the Mirror's "yesterday" = literal previous calendar day definition.)

## 7. State model

Rides on OCS participant data + session state — no new Django models. **Placement is
load-bearing**: session state is per-thread and does not survive a new thread (Mirror §13,
item 4); temp state is per-*run* only; participant data is the only cross-thread home.
Session state persists across separate inbound runs in the *same* thread —
`_get_input_state` loads `session.state` each run and `_persist_pipeline_state` writes it back
(`apps/chat/bots.py:117,225-228`; `session.state` is a JSONField, `apps/experiments/models.py:1388`).

| Key | Home | Why this home |
| --- | ---- | ------------- |
| **contexts** (existing) | participant data | Cross-session; declared once, used everywhere. |
| **records / intent** (existing) | participant data | Mirror §14. Unused by the heartbeat draft (D6); untouched. |
| **`awaiting_confirm`** | **session** state | The handshake happens entirely in the one persistent heartbeat thread; per-thread is correct and runs share it. |
| **`pending_salute`** | **session** state, **keyed by draft date** | Survives between the open run and the reply run (same thread). Date-keyed so a late reply can't post the wrong day's salute (§8). **Never temp** — temp wouldn't survive to the reply run. |
| **`last_heartbeat_date`** + reply outcome | **participant** data | A cross-thread fact used for quiet-day logic and the §11 metric numerator. Session state would not survive. |
| heartbeat-run scratch (window, fetched signals) | temp state | Per-run only; `fetch_signals.py` reads temp keys set by the resolver in the same run. |

**Handshake write ownership (corrected R2).** The deterministic Code nodes on the heartbeat
path own all handshake-state writes: **`Stage` sets** `pending_salute`/`awaiting_confirm` on
open (it runs *after* Draft, so it is the only node that has the draft text — Resolve-HB runs
before the text exists and therefore cannot set `pending_salute`); **`Close` clears** them on
reply. The LLM nodes (Draft, Interpret) and `Post` never write handshake state. Resolve-HB
*reads* `awaiting_confirm` to route and may *reset* a stale flag on a new open. The heartbeat
uses session keys **distinct** from `resolve.py`'s (`vc_last_period`, `vc_awaiting`).

## 8. Edge & failure modes

| Situation | Response |
| --------- | -------- |
| **No signals yesterday** (signal-gated) | Don't force authoring. The nudge still arrives; on reply, if signals are empty the bot offers a **one-tap "day off / non-code"** (nothing posts) or a one-tap "I was in meetings" presence line. Never the blank "what did you do?" interrogation. |
| **Barry doesn't reply** | Nothing posts. No escalation (out of scope §12). The non-reply is recorded for the §11 metric. |
| **Stale draft** (Mon draft never confirmed; Tue nudge) | Tue's heartbeat-OPEN: Resolve-HB resets `awaiting_confirm`, `Stage` overwrites `pending_salute`, and the abandoned Monday draft is logged. No silent carry-over. |
| **Late reply to a prior day's draft** | `pending_salute` is date-keyed; `Close` matches the reply to the live pending date. **Tie-break:** while `awaiting_confirm` is live, any non-command free text is treated as an **edit** of the live draft unless it is an explicit new command ("vibe check" / context name). |
| **Multi-session drift** (a new top-level DM steals "latest session") | Resolve-HB detects drift by session identity (nudge in a session whose thread ≠ the pinned heartbeat thread) and re-bootstraps / surfaces it; setup docs say "reply in-thread, don't start a new DM"; setup checks count sessions (§6). |
| **Private-repo content in the draft** | Approval gate (D4) is the redaction control + optional deterministic private-context guard in Stage (§2). Nothing team-visible bypasses Barry's eyes. |
| **Work spans multiple contexts** | Named as fact in the draft (*"OCS and Mulligans"*) — shape of attention, not an invoice prompt (Mirror Run 3). |
| **GitHub fetch error** | Tell Barry in the DM, offer retry; never post a salute from failed data. |
| **Salute post fails** (Slack API) | Tell Barry, offer retry; don't silently drop. A missed post beats a duplicate. |
| **Performance/optics pressure** | The salute celebrates **presence and continuity, not output volume** (§2). Quiet days post nothing. Gaming/comparison are named risks to watch via §11 as the audience widens (§13). |

## 9. The handshake state machine

The two-phase confirm is the genuinely new mechanism; all transitions are deterministic, in
Code nodes (per §7 ownership).

```text
IDLE
  │  (weekday AM schedule)            → EventBot nudge; state unchanged (still IDLE)
  │
  ▼  Barry replies, awaiting_confirm not set
DRAFTING                               Resolve-HB: route=OPEN, window=yesterday, scope=all contexts
  │                                    → Fetch → Draft
  │  Stage (Code)                     → write pending_salute(today, text); awaiting_confirm=true
  ▼
AWAITING_CONFIRM(date)
  ├─ reply "yep"        → Interpret=approve  → Close: post pending_salute(date); clear → IDLE
  ├─ reply "<edit>"     → Interpret=edit     → Close: post edited text; clear → IDLE
  ├─ reply "day off"    → Interpret=day-off  → Close: post nothing; clear → IDLE
  ├─ next-day nudge+reply (new OPEN) → Resolve-HB resets flag; Stage overwrites; log abandoned → DRAFTING
  └─ explicit new "vibe check"       → treated as on-demand / new open; stale draft logged
```

Invariants: exactly one live `pending_salute` per thread; `awaiting_confirm` true **iff** a
live draft exists; only `Stage` (set) and `Close` (clear) mutate it; Resolve-HB may reset a
*stale* flag on a new open.

## 10. Open implementation questions (for the build manual)

1. **Salute-to-channel mechanism + auth (tracked dependency, §6).** Spike a Code-node
   `http.post` to `chat.postMessage` with a `chat:write` AuthProvider; confirm `slack.com`
   egress + AuthProvider resolution in a Code node; define the salute-to-self fallback.
   **Before committing the build.**
2. **Nudge wording + scheduling.** The `ScheduledMessage` `prompt_text` EventBot rephrases;
   weekday-only via in-pipeline weekend early-exit; bootstrap DM session step.
3. **Reply routing + session pinning.** Confirm the schedule fires into, and Barry replies in,
   the same persistent thread; implement the multi-session-drift guard (§6/§8).
4. **Timezone.** Africa/Johannesburg (Mirror §13.2); morning fire time + "yesterday" local.
5. **EventBot nudge variance.** Keep the pre-fetch nudge short/varied; the signal "magic"
   appears at the draft step.

## 11. Is it alive? — success metric & kill criterion

The product's whole history is "the last three of these died." We will not ship without a
falsifiable liveness signal.

- **Liveness metric:** rolling 2-week **weekday reply rate** = (mornings Barry replies
  yep/edit/day-off) ÷ (weekday nudges fired). The **numerator** comes from
  `last_heartbeat_date` + reply outcomes in participant data (§7); the **denominator** comes
  from the schedule's own fire log — `ScheduledMessage.total_triggers` / `last_triggered_at` and
  `ScheduledMessageAttempt` rows (`apps/events/models.py`) — *not* from pipeline state (the
  nudge is a non-pipeline EventBot, so it cannot write pipeline state). A "day off" reply
  **counts as engagement** (Barry showed up). (Caveat: `total_triggers` increments in
  `_trigger()`'s `finally` even on the no-session early-return, so the denominator assumes the
  session-bootstrap invariant holds — which the pinned heartbeat session guarantees.)
- **Warm-up + floor:** don't evaluate until ≥ 8 weekday nudges have fired (avoid holiday/sick
  noise on a single user).
- **Healthy:** ≥ 60%. **Watch:** 40–60% → reduce cadence (signal-gated days only, or 3×/week).
  **Kill/rethink:** < 40% sustained past warm-up → it's a grind; stop or redesign, don't nag.
- **Self-mirror:** a gentle weekly *"you checked in N/5 days"* to Barry himself, so a dying
  habit is visible to him rather than silently abandoned.

## 12. Non-goals (this increment)

- **Not** escalating nudges (Slack→WhatsApp→call). Later increment; the heartbeat sends one DM.
- **Not** the deep NVC reflection in the daily flow (D6); the on-demand Mirror (V1) serves it.
- **Not** multi-persona / flight-level views (CTO / risk / client lenses).
- **Not** non-GitHub sources (Jira/Slack/Drive); declared-GitHub-only as V1, behind the privacy gate.
- **Not** edge-agent redaction for sensitive sources; the approval gate (+ optional Stage guard) is V1 redaction.
- **Not** multi-user.

## 13. Roadmap fit

Mirror Phase 2 made concrete. What it sets up, each cheap because the heartbeat leaves a seam:

| Next | Builds on the heartbeat by… |
| ---- | --------------------------- |
| **Reflection-in-heartbeat** (Mirror "Option 3") | Add the NVC gap-question to the Draft node when intent exists. |
| **Escalation nudges** (Slack→WhatsApp→call) | The "no reply" branch (§8/§11) becomes a follow-up action; `ad_hoc_bot_message` already targets any channel. |
| **Discovery signals** (Mirror Phase 3) | Additive `context:null` fetch; the draft already narrates multi-context. |
| **Non-GitHub sources** (Mirror Phase 4) | Source-agnostic signal contract; gated by privacy §13.6. |
| **Personas / flight levels; community-of-practice** | The salute becomes the first of several lenses/audiences; a shared channel becomes build-in-public. |

## 14. Decision log (this increment)

| Decision | Choice | Basis |
| -------- | ------ | ----- |
| Increment purpose | Proactive heartbeat + team-visible salute | Source conversations: "the heart of the product" |
| Trigger mechanism | **Schedule nudges; reply runs the pipeline** | R1: `ScheduledMessage`→`EventBot`, not pipeline (verified) |
| Reach-out shape | Signals-grounded draft (at the draft step), confirm/correct | "Correct, don't create" |
| Cadence/scope | Daily weekday AM, all declared projects, signal-gated | Magic + resilience; quiet days don't nag |
| Approval gate | Always; one-tap ratify or edit | Federated/you-decide; redaction |
| Salute voice | Short narrative, bot-drafted | Barry's choice; ratify ≠ author |
| Two surfaces | Private mirror audience-free; salute performative, **one human gate** | R1/R2: protect honesty; be honest the gate is manual |
| Router vs Resolve-HB | Coarse routing in Router; **state-aware route in Resolve-HB** | R1: disambiguation must be deterministic |
| Resolve node | **Fork** Resolve-HB; resolve.py untouched | R1: "trim + untouched" contradiction |
| Handshake writes | **`Stage` sets, `Close` clears** | R2: Resolve-HB can't set pending_salute (text not yet drafted) |
| State placement | `last_heartbeat_date`→participant; handshake→session; never temp | R1: cross-thread survival |
| NVC reflection | Deferred | Heartbeat-first |
| LLM-node budget | ≤3 on the heartbeat path | latency/cost; on-demand adds Mirror |
| Substrate | OCS-native `ScheduledMessage` nudge + inbound pipeline | Verified in OCS source |
| Salute-to-channel | Code-node `http.post` to `chat.postMessage` (chat:write AuthProvider); **spike + fallback** | R1/R2: no native channel send |
| Liveness | 2-week weekday reply rate (denominator from schedule log); kill < 40% past warm-up | R1/R2: predecessors died unmeasured |

## 15. Revision log

- **R0 (initial draft):** assumed `ScheduledMessage` could fire `PIPELINE_START`.
- **R1:** three-lens outside review. Corrected the trigger mechanism (§6), forked Resolve-HB
  (§5), fixed state placement (§7), made routing deterministic (§5), added surface separation
  (§2), the handshake state machine (§9), the liveness metric (§11), edge rows for stale/late
  drafts (§8). Promoted salute-to-channel to a tracked dependency.
- **R2:** Round-2 review. Fixed the handshake write-ownership (Stage sets / Close clears — the
  invariant was physically impossible as drafted), unified node names (§5), sourced the metric
  denominator from the schedule's fire log + added a warm-up floor (§11), softened §2 to "one
  human gate" + optional deterministic guard, added the multi-session-drift guard (§6/§8),
  late-reply tie-break (§8), salute fallback + egress/auth spike items (§6/§10), and tightened
  OCS citations.

---

*This document is the contract for the Heartbeat increment. It extends the Mirror design and is
meant to be read, argued with, and amended.*
