# Mirror spike — notes

Capture each check-in here **immediately after running it**, while it's fresh. These
notes are the raw material for the evolved design doc — don't batch them, don't polish
them.

For each run, the questions that matter: did it surface the *gap* (not just summarise)?
Was the tone a mirror (not a manager, cheerleader, or therapist)? Did its one question
make you reflect? What would you change in the prompt?

---

## Run 1 — sample signals (dry run)

- **Date run:** 2026-06-01 (in OCS web preview + Slack)
- **Stated intent given:** "This week was meant to be OCS embedding work — finishing
  the Voyage/Google retrieval fix."
- **Signals given:** sample (Bermuda hotfix gap)
- **Did it catch the gap?** **Yes — cleanly, first try.** Restated intent neutrally,
  observed the signals specifically (PR #3432, ~9 embedding commits, issue #3433, the
  Thursday docs commit, the 3 Tuesday `bermudabank/core` commits), then named the gap in
  plain terms: *"the week's stated shape was OCS embeddings; the actual shape also
  included Bermuda production/infra work and an adjacent retrieval bug."* Did not judge it.
- **Tone:** **mirror ✓** — neutral observation, no flattery, no "you got distracted,"
  one question and stop. NVC discipline held.
- **Its question — did it land?** *"What do you want to acknowledge about that difference?"*
  Open and non-leading (good), but slightly **abstract / therapy-speak-adjacent**. A more
  grounded version to A/B: *"Where should the Bermuda work sit — detour, or the week's
  real emergency?"*
- **No outward (billing) observation.** The prompt *permits* a client/billing note ("that
  hotfix may belong on the Bermuda invoice") but doesn't force it; here it chose pure
  self-reflection. Taste call: if billing reconciliation is a wanted payoff, the prompt
  needs a firmer nudge toward it.
- **Intent-memory finding (important).** In a fresh Slack thread it had signals but no
  intent, and correctly **refused to reflect** until intent was given — but it could not
  *recall* the intent stated in an earlier thread. First real evidence that cross-session
  **intent memory** (deliberately deferred) is load-bearing, not polish.
- **Prompt change made:** none yet — left as-is to compare against real-week runs.

## Run 2 — real week

- **Date run:** 2026-06-01 · **Period reflected:** 18–21 May 2026
- **Stated intent given:** "make the Mulligans Law design system more operator-grade"
- **Signals source:** real — OCS via local `git log`, mulligans-law via GitHub API (`gh`)
- **What it observed:** Mulligans operator-grade rollout landing as a PR stack on 21 May
  (#722/#738/#739/#740 + docs); OCS work carrying 18–20 May; no Mulligans commits 19–20.
- **The gap it surfaced:** **the both/and, held honestly** — *"the week's stated theme
  did happen, but it appears concentrated into one day after two days of OCS movement."*
  Did NOT flatten into "productive week!" (flattery) and did NOT only scold the OCS
  distraction (nagging). Held the tension. This was the hardest test and it passed.
- **Tone:** **mirror ✓** on messy real data.
- **Its question — did it land?** *"was the Mulligans work waiting for a clear run, or did
  OCS pull the centre of the week somewhere else?"* **Better than Run 1** — concrete, two
  honest framings, non-leading. The abstract/therapy-speak worry from Run 1 did **not**
  recur; richer data → more grounded question, with no prompt change.
- **Outward observation? (client/team):** **none again.** OCS vs Mulligans are different
  contexts (plausibly different invoices) but it stayed pure self-reflection. **Now a
  confirmed pattern across both runs** — the client/billing observation does not fire on
  its own.
- **What would make it better:** decide whether billing/context-split reconciliation is a
  wanted payoff; if so, the prompt needs a firmer nudge toward the outward observation
  (currently "at most one, only when signals point to it" → too soft, fires never).

## Run 3 — billing-trigger rerun (same 18–21 May data)

- **Date run:** 2026-06-01 · **Period reflected:** 18–21 May 2026 (rerun, only the prompt changed)
- **Change tested:** firmer trigger for the client/billing outward observation.
- **Mechanical result:** **worked** — self-reflection + good question unchanged, then a
  single clean closer *"OCS and Mulligans are different contexts — worth splitting those
  across invoices?"* Not preachy, didn't lead, didn't bury the reflection. The tuning did
  exactly what it was asked.
- **Product result: REJECTED.** Barry: the **invoice anchoring is wrong**. The *context
  split* is a real mirror observation (where attention went); the *invoice* is a downstream
  output we may add later and shouldn't centre now — billing framing makes the mirror
  transactional and premature.
- **Decision (refines "self-core, others as outputs"):**
  - **Context-awareness is intrinsic to the mirror** — noticing a period spanned multiple
    contexts is part of the self-reflection, named neutrally as *shape of attention*.
  - **Client/invoice/timesheet outputs are DEFERRED** (alongside proactivity, discovery,
    external-artefact ingestion). Prompt now forbids proposing invoices/billing/timesheets.
  - Team/collaboration stays optional, real-knowledge-only.
- **Prompt change made:** removed the billing offer; folded multi-context into the
  reflection as "shape of attention"; added a "do not propose invoices/billing/timesheets"
  rule. (mirror-agent.md updated.)

## Run 4 — real week

- **Date run:**  · **Period reflected:**
- **Stated intent given:**
- **Signals source:**
- **What it observed:**
- **The gap it surfaced (if any):**
- **Tone:** mirror / report / nag / flattery / vague →
- **Its question — did it land?**
- **Outward observation? (client/team)** — appropriate or forced?
- **What would make it better:**

---

## Signals subsystem — decisions (2026-06-01)

- **Model: hybrid, but phased — declared-only for V1.** Signals come from *declared
  contexts* (repos + author handle in participant data); no discovery sweep yet.
- **Why phased:** prove "no more pasting" on the reliable spine before taking on the
  broad-scope credential and messy mapping that discovery requires.
- **Credential upside of declared-only:** no broad PAT. Public declared repos need only
  rate-limit auth; private declared repos need a token scoped to *just those repos*.
- **The seam that avoids a rewrite:** the mirror reasons over a normalized,
  `context`-tagged **signal list** — never GitHub directly. Phase 1 = all signals tagged
  (no surprises). Discovery later = append `context: null` signals to the same list; the
  mirror prompt already handles "activity outside what you've told me about." Mirror node,
  signal contract, and contexts are unchanged between phases.
- **Signal contract:** `{ context, source, kind: commit|pr|issue, ref, title, when, url }`.
- **Deferred:** discovery sweep + broad/public-only credential question — revisit after
  the declared spine is in daily use.

## V1 build — outcome (2026-06-01)

**Working end-to-end in OCS on live data.** `Start → Fetch (Code node) → Mirror (LLM) → End`:
the Fetch node parses the window (relative + month names), pulls real GitHub commits + PRs/
issues for the declared context, and the Mirror reflects in NVC tone, asks for intent, and
persists it. Built entirely in the OCS UI from the manual + two paste artefacts.

**OCS Code-node rules learned the hard way** (all now in the build manual gotchas):
single top-level `main` only (helpers nested); module-level names invisible inside `main`
(define constants inside it); no module-level attribute access; no leading-underscore names;
no `next()`/`open()`; no tuple-unpack assignment; attribute access + subscripts work inside
`main`; injected globals = `http`, `datetime`, `get_participant_data`, `set_participant_data_key`,
`set_temp_state_key`. Plus: GitHub **Search API 422s** with a fine-grained PAT not scoped to
the repo → use REST `/commits` + `/issues`; fork `/issues` 404/410 (disabled) → tolerate;
pipeline **preview** uses a rolled-back anonymous participant → can't see seeded data, test on
Slack or rely on the snippet's self-seed.

**Confirmed on full-month real data (2026-06-01):** "vibe check mulligans May" → intent →
reflected the real May Mulligans commits — recognised the design-system push (21–24) *and*
surfaced the rest (CI migration, auth/waitlist fixes, coverage), held the both/and, asked a
genuine question. The whole concept works on messy real signals.

**Multi-turn state must persist (the last real bug).** The window/context are re-derived each
turn, but the user only names them once (turn 1); the intent-answer turn (turn 2) doesn't repeat
"May", so the window reset to "this week" (empty) → looked like a token/permissions failure but
wasn't. Fix: persist the period in **session_state** and reuse it when a turn names none (active
context already persisted the same way). Lesson: **state derived from the message must be sticky
across a multi-turn exchange.**

**Debugging lesson:** spent several turns theorising about token scope; the actual token,
pulled from the Auth Provider and used to make the exact call, returned 200/100 commits. **Get
ground truth (replay the real call / read the real state) before theorising.** Private repos need
the fine-grained token's **Contents: Read** permission (separate from repo access); public repos
(dimagi/ocs) read without it.

**Architecture note:** the single Fetch Code node now does five jobs (resolve context, switch,
parse+persist period, fetch, render) — complexity ~90. Works, but the planned next step is to
**split the pipeline** (Router → Resolve → Fetch → Mirror), which is also the shape Phase 2 needs.

**Open refinements (use-and-tune, not build):**

- Commits come from the repo's default branch — in-progress *branch* work isn't seen until merged.
- Window parsing covers relative + month names; explicit day-ranges ("15–30 May") snap to the month.
- No "remove repo / edit context" conversational command yet (add/list/switch only).

## Verdict

- **Does the mirror earn its place?** Yes — caught real gaps (Bermuda hotfix, OCS-vs-Mulligans
  split) and held the both/and without flattery or nagging, across rigged + real weeks.
- **Is "stated intent vs signals" the right axis?** Yes — proven across all runs.
- **On-demand enough?** For V1, yes; proactivity is the committed Phase 2.
- **Biggest prompt insight:** intent memory is load-bearing (the fresh-thread finding); and the
  outward observation should stay *context-as-mirror*, never invoice-anchored (Run 3).
- **Verdict: GO.** V1 spine proven; refine by use, then build Phase 2 (proactivity).
