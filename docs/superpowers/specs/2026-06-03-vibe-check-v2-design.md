# Vibe Check v2 — Design

**Date:** 2026-06-03
**Status:** active
**Supersedes (in practice):** the v1 "heartbeat" pipeline described in
`2026-06-02-vibe-check-heartbeat-design.md`. v1 stays deployed and untouched as a fallback; v2 is
a **new OCS experiment/pipeline** built from scratch.

## Why v2

v1 grew a reflective "mirror" conversation on top of the salute: it asked for *intent* ("what was
this period meant to be about?"), reflected the gap between intent and signals, and asked
follow-up questions. That machinery — a front router, a static-router branch, three branches
(spine/open/reply), an intent state machine, and a conversation lock — turned out to fight the
actual need. In testing, the bot kept interrogating ("what pulled the week toward Chatterbridge?")
even when asked to "just give me the vibe check."

The real need is simpler: **gather context, hand me the vibe, let me correct it in chat.** v2 is
that, and nothing more.

## What it is

A **private** daily-awareness bot for Barry. Each weekday morning it nudges him; he replies and it
DMs back a **vibe** — a grouped, plain-language summary of what he actually shipped, drawn from his
GitHub activity — which he shapes conversationally. Also available any time via `vibe check`.
Nothing is posted anywhere. The vibe is for him.

## Goals

- One pipeline serves **both** entry points (morning nudge-reply and manual `vibe check`).
- Lead with the **draft**. No intent question, no reflective questions.
- Window is **gap-aware** — cadence emerges from how often Barry responds (daily *or* weekly both
  "just work"), nothing to configure.
- The vibe **reflects what actually exists** and reads **absence as signal**.
- **Correct-in-chat** absorbs real-world context GitHub can't see (offsite, sick day, interviews).
- Private DM only — no team channel, no posting, no Slack user token.

## Non-goals

- No team-channel salute / performative posting (a deliberate move away from the v1 "heartbeat"
  framing; can be revisited later as a separate feature).
- No intent capture, no reflective Q&A, no mirror.
- No multi-turn routing/branching, no approval handshake.

## Decisions (from brainstorming)

| Topic | Decision |
| ----- | -------- |
| Intent / reflection | **Dropped.** Just draft the vibe. |
| Destination | **Private DM only.** No posting, no user token, no channel. |
| Default period | **Gap-aware** (since last vibe; widens across a break). |
| First-ever vibe | **Last 7 days** (a richer baseline), then gap-aware after. |
| First-run context | **Auto-discover** when no contexts exist — a dedicated **Discover** node ranks repos by **actual commit activity** (`search/commits`) unioned with recently-pushed repos (catches today's un-indexed work), top 5. A repo named in the message is fetched directly (exact name → only that repo; else fuzzy). Push-recency alone was rejected: it buried the 71-commit repo behind low-activity recently-pushed ones. Contexts remain optional for guaranteed scoping/grouping. |
| Node split | **Discover** (rank/select repos, ≤2 calls) is separate from **Fetch** (per-repo signals, ≤10 calls) so each gets its own OCS call budget. |
| Cadence | **Emergent** from response frequency; weekday nudge is just an invitation. |
| Shape | **One summary, grouped by project** (only projects that moved). |
| Gaps | Read **no-commit stretches as signal** ("focus was elsewhere"), not "nothing." |
| Corrections | **Re-run the pipeline every turn**; Draft LLM revises from chat history. Window/scope sticky until renamed. |
| On-demand scoping | Bare `vibe check` = default; `vibe check last week` / `vibe check ocs` narrows. |
| Proactive delivery | **Nudge-then-draft** (OCS scheduled messages can't run the pipeline). |
| Build target | **New bot/experiment**; v1 untouched. Artefacts in a per-bot folder. |
| Signal cache | **Staged to v2.1** (designed below, built after the core is proven). |

## Architecture

A brand-new OCS experiment, **Vibe Check v2**, with a **linear 4-node pipeline** — no router, no
branches, no handshake:

```bash
Start → Resolve → Discover → Fetch → Draft → End
```

### Node 1 — Resolve (Code)

Determines *period* and *scope* for this turn, and handles context admin. Deterministic.

- **Period**
  - Gap-aware default: from `last_vibe_date` to now (widens across a break).
  - First-ever (no `last_vibe_date`): **last 7 days**.
  - Manual override via period words: `yesterday` / `last week` / `this week` / a month name.
    Month parsing must be robust — the everyday words **"may"/"march"** count as a month only
    when clearly a date (followed by a 4-digit year, preceded by `in`/`during`/`for`/`since`/
    `over`/`back`, or the whole message). **No `enumerate`/`zip`/`map`** (not in the OCS sandbox);
    use a manual index.
  - **Sticky**: if a turn names no period, reuse `last_period` (so corrections keep the window).
- **Scope**
  - All contexts by default; narrows to a named context (`ocs`). Also sticky via `last_scope`.
- **Admin**: `add a context <name> for <owner/repo>…` and `list contexts` (reuse v1's parser,
  including Slack URL-wrapper stripping).
- **Writes** temp state for Fetch (repos, author, since/until ISO + dates, period label, scope
  label) and remembers `last_scope` / `last_period` in session.
- Stamps `last_vibe_date = today` on a delivered vibe (drives gap-awareness next time).

### Node 2 — Fetch (Code)

Pulls GitHub commits + PRs/issues for the resolved repos and window. Reuses v1's `fetch_signals`
logic: per-repo `/commits` (author + since/until) and `/issues` (creator), 404 = skip-with-note,
other failures surfaced **verbatim** (never softened to "no activity"), **5-repo / 10-call cap**
with dropped repos named. Emits the SIGNALS block plus Barry's latest message for the Draft node.

### Node 3 — Draft (LLM, Global history)

Writes the vibe and revises it on follow-ups.

- **One summary, grouped by project** — a short bold heading per project that actually moved; quiet
  projects are simply omitted, not listed as empty.
- First person, plain-language **outcomes** (not mechanism), presence over volume.
- **Reads gaps as signal**: several no-commit days → name it gently ("a quiet stretch on code —
  looks like focus was elsewhere"), never "no activity."
- **Absorbs user-added non-code context** from corrections (offsite, sick day, interviews,
  meetings) and adjusts how it reads the quiet stretches. The signals are the skeleton; Barry's
  corrections add the lived context.
- **No intent, no questions.** It drafts; it doesn't interrogate.

### Node 4 — End

Returns the Draft output to the DM.

## Proactive nudge

A weekday-morning `ScheduledMessage` → EventBot one-line nudge ("morning — reply for your vibe").
Barry's reply runs the pipeline. The nudge **cannot** itself contain the vibe (OCS scheduled
messages fire a one-shot LLM, not the pipeline) — accepted constraint. Because the window is
gap-aware, ignoring a nudge loses nothing: the next reply sweeps up everything since the last vibe.
Nudge text lives in `prompts/nudge.md`; cadence/window are decoupled.

## Corrections

Every message re-runs `Start → Resolve → Fetch → Draft`. The Draft LLM, with Global history, sees
the prior draft and Barry's correction and revises. Re-fetch each turn (cheap, idempotent — and
superseded by the v2.1 cache). Window and scope stay **sticky** until Barry names new ones; a new
period word (`yesterday`, `last week`, `in may`) re-scopes.

## State model

- **Participant data:** `contexts[]` (slug, name, github.repos, github.author_handle),
  `last_vibe_date`. *(v2.1 adds `signal_cache`.)*
- **Session:** `last_scope`, `last_period` (stickiness).
- **Temp (per turn):** resolved repos/author/window/labels + the SIGNALS block.

No intent store, no `records`, no pending-salute handshake, no conversation lock.

## Dropped from v1 / reused from v1

**Dropped:** Resolve-HB router, Static Router branch, spine/open/reply branches, Spine·Mirror
reflection, intent ask/store, conversation lock, Reply·Interpret/Close/Post, the Slack user token
and team channel.

**Reused (ported into the new folder):** the GitHub fetch logic, gap-aware window math, the
grouped-by-project draft prompt, the `add/list context` parser, and the month-parse robustness.

## Artefacts

A per-bot, versioned folder, leaving v1 files in place:

```bash
ocs/bots/vibe-check-v2/
  snippets/
    resolve.py
    fetch.py
  prompts/
    draft.md
    nudge.md
  NODES.md        # node → file map, pipeline graph, schedule note
```

## Testing

OCS sandbox code nodes can't be unit-tested in OCS, so before each publish:

- **Compile-check** every snippet (`py_compile`).
- **Sandbox-safety scan** — flag `enumerate`/`zip`/`map` and other RestrictedPython gaps.
- **Scripted manual DM scenarios:** gap-aware default; `vibe check last week`; `vibe check ocs`; a
  correction turn that adds non-code context (sick day); a multi-day-gap vibe; `add a context`.

## Edges & accepted constraints

- Morning nudge can't contain the vibe (OCS limitation) → nudge-then-draft.
- Weekday-only schedule; on-demand works any day.
- Light/empty day → say so briefly, read as signal.
- First-ever vibe → last 7 days.

## v2.1 — Immutable-history signal cache (staged, not in the first build)

Past GitHub history is **immutable**: a commit dated last Monday never changes; new activity only
appends at *today's* date. So once a date range is fetched it can be served from a local cache, and
GitHub is only ever hit for the **open tail**.

- **Schema:** `signal_cache` in participant data, keyed `repo → date → events` (events = commits
  and PRs/issues created that day).
- **Fill rule:** for each day in the window, use cache if present; fetch only missing days **+
  today**. Past days are never re-fetched.
- **Invalidation rule:** cache everything **except the current day**; never trust cache for today.
- **PR/issue state caveat:** a PR's state change (open → merged) happens on a *later* date and
  belongs to that later bracket (the merge day) — consistent with the model. A PR opened Monday
  stays "opened Monday" in the Monday bracket.
- **Housekeeping:** optionally prune the cache to the last N weeks to bound participant-data size.
- **Payoff:** near-zero GitHub calls for repeated/historical queries; comfortably under the
  10-call budget; faster responses.

Deferred so the simple linear pipeline is proven before adding cache logic inside the
RestrictedPython Fetch node (the kind of place a sandbox gap like `enumerate` bites).

## Future / out of scope for now

- Optional team-channel publishing (re-introducing the performative salute as an explicit action).
- A persisted vibe "journal" (saving corrected vibes as a log).
- Multi-workspace / multi-user.
