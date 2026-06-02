# Vibe Check — Build Manual (Heartbeat)

A click-by-click guide to adding the **proactive heartbeat** to the existing Vibe Check bot.
You follow the steps and paste the artefacts; almost no coding. Design rationale lives in
[`../superpowers/specs/2026-06-02-vibe-check-heartbeat-design.md`](../superpowers/specs/2026-06-02-vibe-check-heartbeat-design.md).

**What the heartbeat does:** every weekday morning the bot DMs you a nudge. You reply; it
pulls yesterday's GitHub activity across all your declared contexts, drafts a 2-sentence
salute in your voice, and asks you to confirm. On your "yep" (or an edit), it posts the salute
to a team channel. Nothing is posted without your approval.

**The flow (three separate turns in one persistent DM thread):**

```text
(weekday AM)  schedule → EventBot NUDGE in the DM                       ← run 1 (not the pipeline)
you reply "go" → Resolve-HB → Open · Fetch → Open · Draft → Open · Stage ← run 2 (the pipeline)
you reply "yep" → Reply · Interpret → Reply · Close → Reply · Post       ← run 3 (the pipeline)
```

**The pipeline** (front-router + three branches). Canonical node names are tagged by branch
(`Spine ·` / `Open ·` / `Reply ·`) so the two Fetch nodes never collide:

```text
[Start] → [Resolve-HB · Code] → [Branch · vc_hb_route · StaticRouter]
                                     ├─ "spine" → [Spine · Resolve] → [Spine · Fetch] → [Spine · Mirror] → [End]
                                     ├─ "open"  → [Open · Fetch] → [Open · Draft] → [Open · Stage] → [End]
                                     └─ "reply" → [Reply · Interpret] → [Reply · Close] → [Reply · Post] → [End]
```

The **`Spine ·`** branch is the V1 on-demand mirror (its code lives in
[`ocs/snippets/resolve.py`](../../ocs/snippets/resolve.py),
[`ocs/snippets/fetch_signals.py`](../../ocs/snippets/fetch_signals.py),
[`ocs/prompts/mirror-agent.md`](../../ocs/prompts/mirror-agent.md) — see
[build-v1-declared-spine.md](build-v1-declared-spine.md)). The **`Open ·`** and **`Reply ·`**
branches are new in this manual.

**Artefacts you'll paste** (all inline below; save each to `ocs/snippets/` or `ocs/prompts/`
once it works in OCS, matching the repo convention):

- Code: `Resolve-HB` (front-router), `Open · Stage`, `Reply · Close`, `Reply · Post`
- Prompts: the nudge instruction, the `Open · Draft` prompt, the `Reply · Interpret` prompt
- Reused as-is: [`ocs/snippets/fetch_signals.py`](../../ocs/snippets/fetch_signals.py) (as `Open · Fetch`)

---

## Prerequisites

- The **V1 declared spine is built and working** ([build-v1-declared-spine.md](build-v1-declared-spine.md)):
  contexts seeded, GitHub Auth Provider (`github-vibe-check`), and the Slack DM works.
- You can reach your OCS instance's Service Providers and pipeline editor.
- 30–45 minutes (the spike in Step 0 is the gating risk — do it first).

---

## Step 0 — SPIKE FIRST: prove the salute-to-channel post

This is the one mechanism the design isn't certain of: posting to a **team channel** (a
different destination from the DM). Prove it before building anything else. If it can't be
made to work, the heartbeat still ships with a **salute-to-self** fallback (Step 7), so this
de-risks the whole increment up front.

### 0a. Create a Slack app bot token with `chat:write`

1. In your Slack workspace, the Vibe Check Slack app → **OAuth & Permissions** → Bot Token
   Scopes → add **`chat:write`** (and `chat:write.public` if you'll post to channels the bot
   hasn't joined). Reinstall the app if prompted; copy the **Bot User OAuth Token** (`xoxb-…`).
2. **Invite the bot to the target channel**: in the channel, `/invite @your-vibe-check-bot`.
3. Note the **channel ID** (channel → View channel details → bottom, `C0…`).

### 0b. Store the token as an OCS Auth Provider

1. OCS → **Service Providers → Auth Provider → Create → Bearer**.
2. **Name:** `slack-vibe-check` (must match the snippets).
3. **Bearer Token:** paste the `xoxb-…` token. Save (stored encrypted).

### 0c. Throwaway test node

In any test pipeline, add a **Code** node, paste the snippet below (set your channel ID), wire
Start → it → End, and send any message in the **preview**:

```python
# SPIKE ONLY — delete after Step 0. Proves chat.postMessage works from a Code node.
def main(input, **kwargs):
    channel = "C0XXXXXXXX"          # <-- your team channel id
    resp = http.post("https://slack.com/api/chat.postMessage",
                     json={"channel": channel, "text": "Vibe Check spike: hello team 🫡"},
                     auth="slack-vibe-check", timeout=15)
    return f"is_success={resp['is_success']} status={resp['status_code']} body={resp['json']}"
```

**Pass =** the message appears in the channel and the node returns `is_success=True` with
`body={'ok': True, ...}`. **Watch for:**

- `body={'ok': False, 'error': 'not_in_channel'}` → invite the bot (0a.2).
- `body={'ok': False, 'error': 'missing_scope'}` → add `chat:write` and reinstall (0a.1).
- `body={'ok': False, 'error': 'not_authed'/'invalid_auth'}` → the Auth Provider didn't resolve
  inside the Code node: check the name is exactly `slack-vibe-check` and that a Bearer provider
  works in this context.
- An egress error / "Auth providers are not available in this context" → your instance's
  `RestrictedHttpClient` is blocking `slack.com` or the Auth Provider isn't resolvable in a
  Code node. If this can't be lifted, **use the salute-to-self fallback** (Step 7) and skip
  the channel post for now.

Delete the spike node once it passes (or fallback is chosen). **Do not proceed until you know
which path you're on.**

---

## Step 1 — Set up the morning nudge (schedule)

The schedule sends a **nudge only** — an `EventBot` rephrases your `prompt_text` into a chat
message and sends it into the DM. (It cannot run the pipeline; that's why your _reply_ does the
work.) The nudge needs an existing DM session, so **message the bot once in Slack first** to
bootstrap the thread (you already have this from V1).

**MVP (simplest):** one **daily** scheduled message. You'll naturally ignore weekend nudges,
and the liveness metric (Step 8) counts weekdays only.

In the bot's **Events** area (the experiment's triggers/scheduled-messages UI), create a
**Scheduled Message** for your participant:

- **Frequency / period:** every **1 day**.
- **Prompt text** (what EventBot rephrases): `Greet Barry briefly and invite him to do his
vibe check — tell him to reply and you'll pull yesterday's activity. One short, friendly
sentence; vary the wording.`
- **First trigger:** tomorrow at your chosen hour (e.g. 08:00 Africa/Johannesburg).

> **Weekday-only upgrade (optional):** OCS scheduling is interval-based (no cron / weekday
> field). For weekday-only nudges, create **five weekly** scheduled messages instead — one each
> first-firing on Mon, Tue, Wed, Thu, Fri morning, period = 1 week. No weekend nudges, no
> pipeline weekend-gate needed.
> **If there's no Events UI on your instance:** scheduled messages can be created via the API
> or Django shell (`ScheduledMessage` + a `schedule_trigger` `EventAction` holding the params,
> `apps/events/models.py:459`). Prefer the UI; drop to shell only if needed.

---

## Step 2 — Resolve-HB (front-router Code node)

This is the deterministic brain. It runs first, peels off the two heartbeat cases, and passes
everything else to the **existing** spine untouched. It writes the route to **temp** state for
the StaticRouter (Step 3) and the fetch inputs for the OPEN path; it reads/writes the handshake
flag in **session** state.

Add a **Code** node right after **Start**. Paste:

```python
# Vibe Check — Resolve-HB (heartbeat front-router, OCS Code node)
# Grammar: addressing the bot IS the request; words only SCOPE it.
#   no scope                 -> OPEN  (today's salute: yesterday, all contexts)
#   period and/or context    -> SPINE (on-demand Mirror reflection on that scope)
#   add/list context         -> SPINE (resolve.py handles context admin)
#   reply while awaiting      -> REPLY (confirm / edit / day off)
# Injected globals: get_participant_data, get_session_state_key, set_temp_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(sast)
    msg = input or ""
    low = msg.lower().strip()

    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pdata = get_participant_data() or {}
    contexts = pdata.get("contexts", [])
    available = ", ".join([c.get("slug", "") for c in contexts]) or "(none yet)"
    set_temp_state_key("vc_message", msg)
    set_temp_state_key("vc_available", available)

    # scope detection: a reflection is requested only when the message names a period
    # and/or a specific declared context. The product-named context never counts, so
    # addressing the bot plainly always means "give me my check-in".
    has_period = ("yesterday" in low) or ("last week" in low) or ("this week" in low)
    for name in months:
        if name in low:
            has_period = True
    has_context = False
    for c in contexts:
        slug = (c.get("slug") or "").lower()
        cname = (c.get("name") or "").lower()
        if slug in ("vibe-check", "vibe check") or cname in ("vibe check", "vibe-check"):
            continue
        if (slug and slug in low) or (cname and cname in low):
            has_context = True

    is_manage = ("add a context" in low) or ("list context" in low) or low in ("contexts", "what contexts")
    is_scoped = has_period or has_context or is_manage

    awaiting = get_session_state_key("vc_hb_awaiting")

    # 1) reply to a pending draft (unless it's a fresh scoped/manage command)
    if awaiting and not is_scoped:
        pending = get_session_state_key("vc_hb_pending_text") or ""
        set_temp_state_key("vc_hb_route", "reply")
        return f"REPLY_MESSAGE: {msg}\n\nPENDING_DRAFT: {pending}"

    # 2) scoped or context-admin -> the on-demand spine
    if is_scoped:
        set_temp_state_key("vc_hb_route", "spine")
        return msg

    # 3) default: plain address, no scope -> today's salute (heartbeat OPEN)
    if contexts:
        day = (now - datetime.timedelta(days=1)).date()
        start = datetime.datetime(day.year, day.month, day.day, tzinfo=sast)
        end = start + datetime.timedelta(days=1)
        repos = []
        author = ""
        for c in contexts:
            gh = c.get("github", {})
            if not author:
                author = gh.get("author_handle", "")
            for r in gh.get("repos", []):
                if r not in repos:
                    repos.append(r)
        set_temp_state_key("vc_mode", "checkin")
        set_temp_state_key("vc_repos", repos[:5])
        set_temp_state_key("vc_author", author)
        set_temp_state_key("vc_since_iso", to_iso(start))
        set_temp_state_key("vc_until_iso", to_iso(end))
        set_temp_state_key("vc_since_date", start.date().isoformat())
        set_temp_state_key("vc_until_date", day.isoformat())
        set_temp_state_key("vc_slug", "all")
        set_temp_state_key("vc_period_label", "yesterday")
        set_temp_state_key("vc_intent", "(heartbeat - no reflection)")
        set_temp_state_key("vc_hb_route", "open")
        return msg

    # no contexts yet -> let the spine onboard (resolve.py NO_CONTEXT)
    set_temp_state_key("vc_hb_route", "spine")
    return msg
```

> **Routing rule — "address = ask; words only scope".** Addressing the bot (an `@mention` in a
> channel, or any message in a DM) _is_ the request, so the **default is the salute**:
>
> | Message (after the mention is stripped) | Route | Result |
> | --- | --- | --- |
> | bare / `go` / `hi` / anything with no period or context | **open** | today's salute (yesterday, all contexts) |
> | names a period or a specific context — `last week`, `ocs`, `may` | **spine** | reflection on that scope |
> | `add a context …` / `list contexts` | **spine** | context admin (resolve.py) |
> | a reply while a draft is pending | **reply** | confirm / edit / day off |
>
> The product-named `vibe-check` context is deliberately ignored in scope detection, so saying
> "vibe check" (or just addressing the bot) never collides with a real context and always means
> "give me my check-in." No trigger word to remember.
>
> **Deliberate simplification vs the design (§5).** The design draws a _cheap-LLM Router_ node
> first (coarse `check-in-ish` vs `manage-context`). For the MVP that Router is **collapsed into
> the deterministic Resolve-HB** — cheaper, no LLM guesswork, and it realises the design's
> "state-aware deterministic Router" recommendation. **Manage-context still works:** an
> `add a context …` / `list contexts` message matches no heartbeat case, so it falls through to
> `spine`, where the untouched `resolve.py` + Mirror handle add/list exactly as in V1.

---

## Step 3 — Branch router (`Branch · vc_hb_route`)

Add a **Static Router** node after Resolve-HB and name it **`Branch · vc_hb_route`**:

- **Data source:** **Temporary State**.
- **Route key:** `vc_hb_route`.
- **Keywords / routes:** `spine`, `open`, `reply` (set the **default** to `spine`).

Wire its three outputs to the branches below. The **`spine`** output goes to your
`Spine · Resolve → Spine · Fetch → Spine · Mirror → End` chain (the V1 on-demand mirror — see
[build-v1-declared-spine.md](build-v1-declared-spine.md) for those three nodes' code).

---

## Step 4 — The "open" branch: Open · Fetch → Open · Draft → Open · Stage

### 4a. Open · Fetch (Code)

Add a **Code** node on the `open` route, name it **`Open · Fetch`**, and paste **all of**
[`ocs/snippets/fetch_signals.py`](../../ocs/snippets/fetch_signals.py) (the V1 fetcher, reused
verbatim — a separate instance from `Spine · Fetch`). It reads the temp keys Resolve-HB set and
returns the SIGNALS block. Wire **`Branch · vc_hb_route` [open] → Open · Fetch**.

### 4b. Open · Draft (LLM node)

Add an **LLM** node (plain LLM, premium model, History Type **Global**). Paste this prompt
(no `{`/`}` — OCS treats braces as template variables):

```text
You write Barry's short daily work salute for his team channel. You are given his real
GitHub activity for yesterday across his projects (the SIGNALS block below).

Write at most two sentences, first person, plain and warm. Name the projects and what
actually moved — a merged PR, a fix shipped, an issue opened. Presence over volume: if the
signals are thin or empty, say so honestly and briefly (e.g. a quiet day, or non-code work).
Never invent activity beyond the signals. No hashtags, no emoji pile-ups, no preamble.

Output only the salute text — nothing else.
```

Wire **Open · Fetch → Open · Draft**.

### 4c. Open · Stage (Code)

Add a **Code** node named **`Open · Stage`**; paste:

```python
# Vibe Check — Stage (OCS Code node). OPEN path, after Draft.
# Saves the draft to SESSION state (the handshake) and asks Barry to confirm.
# Injected globals: set_session_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    today = datetime.datetime.now(sast).date().isoformat()
    draft = (input or "").strip()
    set_session_state_key("vc_hb_awaiting", today)
    set_session_state_key("vc_hb_pending_date", today)
    set_session_state_key("vc_hb_pending_text", draft)
    return ("Here's your salute for the team:\n\n" + draft +
            "\n\nPost it? Reply *yep* to post, send edited wording to change it, "
            "or *day off* to skip.")
```

Wire **Open · Draft → Open · Stage → End**.

> **Deferred: the optional private-context guard.** The design (§2) recommends a deterministic
> guard in `Open · Stage` that strips/flags private-context names before a salute can be posted. It is
> **deferred** until you declare private contexts; for this GitHub-only MVP the **approval gate
> is the sole redaction control** (you read every salute before it posts). Add the guard here
> when a private repo first enters a context.

---

## Step 5 — The "reply" branch: Reply · Interpret → Reply · Close → Reply · Post

### 5a. Reply · Interpret (LLM node)

Add an **LLM** node named **`Reply · Interpret`** (a cheap model is fine). Its input is the
`REPLY_MESSAGE … / PENDING_DRAFT …` block Resolve-HB returned. Paste this prompt:

```text
Barry was shown a draft salute and has replied. Decide what he wants and output EXACTLY one
line, nothing else:

APPROVE
  — if he approves the draft as-is (e.g. yep, yes, post it, looks good, a thumbs up).
DAYOFF
  — if he says it was a day off, nothing to post, skip it, or there was no real work.
EDIT: <final salute text>
  — if he supplied a change or rewrite. Apply his change to the pending draft and write the
    final salute after EDIT: on the same line.

The block below contains his reply (REPLY_MESSAGE) and the draft he is responding to
(PENDING_DRAFT).
```

Wire **`Branch · vc_hb_route` [reply] → Reply · Interpret**.

### 5b. Reply · Close (Code)

Add a **Code** node named **`Reply · Close`**; paste:

```python
# Vibe Check — Close (OCS Code node). REPLY path, after Interpret.
# Reads the verdict, clears the handshake, stages the post text, records engagement.
# Injected globals: get_session_state_key, set_session_state_key, set_participant_data_key,
#                   set_temp_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    today = datetime.datetime.now(sast).date().isoformat()
    verdict = (input or "").strip()
    pending = get_session_state_key("vc_hb_pending_text") or ""

    set_session_state_key("vc_hb_awaiting", "")
    set_session_state_key("vc_hb_pending_text", "")
    set_session_state_key("vc_hb_pending_date", "")
    set_participant_data_key("last_heartbeat_date", today)

    upper = verdict.upper()
    post_text = pending
    if upper.startswith("DAYOFF"):
        post_text = ""
    elif upper.startswith("EDIT:"):
        post_text = verdict.split(":", 1)[1].strip()
    set_temp_state_key("vc_hb_post_text", post_text)
    return "ok"
```

Wire **Reply · Interpret → Reply · Close**.

### 5c. Reply · Post (Code)

Add a **Code** node named **`Reply · Post`**; paste the snippet below, then **⚠️ replace the
placeholder `channel = "C0XXXXXXXX"` with your real channel ID** (the one from your Step 0 spike).
Leaving the placeholder is the #1 cause of `channel_not_found` — the post silently fails and,
because `Reply · Close` has already cleared the handshake, retrying `yep` just starts over.

```python
# Vibe Check — Post (OCS Code node). REPLY path, after Close.
# Posts the approved salute to the team channel via Slack chat.postMessage.
# Injected globals: get_temp_state_key, http.
# ruff: noqa: F821
def main(input, **kwargs):
    channel = "C0XXXXXXXX"          # <-- your team channel id (from Step 0a.3)
    auth_provider = "slack-vibe-check"
    text = get_temp_state_key("vc_hb_post_text") or ""
    if not text.strip():
        return "Noted — enjoy the day off. Nothing posted. 🌴"
    resp = http.post("https://slack.com/api/chat.postMessage",
                     json={"channel": channel, "text": text},
                     auth=auth_provider, timeout=15)
    if not resp["is_success"]:
        return f"Couldn't reach Slack (HTTP {resp['status_code']}). Try again shortly."
    body = resp["json"] or {}
    if not body.get("ok"):
        return f"Slack rejected the post ({body.get('error', 'unknown')})."
    return "Posted to the team channel. 🫡"
```

Wire **Reply · Close → Reply · Post → End**.

> **Salute-to-self fallback (if Step 0 failed):** replace the Post node body with
> `return "Salute (not posted — channel disabled):\n\n" + (get_temp_state_key('vc_hb_post_text') or '(day off)')`.
> The whole heartbeat loop still works; only the team-visible post is deferred.

---

## Step 6 — Publish and wire-check

1. Confirm the graph: **Start → Resolve-HB → Branch · vc_hb_route** with three branches —
   `spine` (Spine · Resolve → Spine · Fetch → Spine · Mirror), `open` (Open · Fetch →
   Open · Draft → Open · Stage), `reply` (Reply · Interpret → Reply · Close → Reply · Post).
2. **Publish a new version** (Slack serves the _published_ version — the V1 "publish trap").

---

## Step 7 — Test on Slack (the real end-to-end test)

> The pipeline **preview can't test this** — it runs as an anonymous throwaway participant with
> empty participant data (V1 gotcha). Test in a **real Slack DM thread**.

In your bootstrapped DM thread:

1. **Simulate the morning:** just address the bot — `@VibeCheck` (channel) or `go` / `hi` (DM),
   or wait for the scheduled nudge and reply.
   - Expect: it fetches yesterday across all contexts, drafts a 2-sentence salute, and asks
     _"Post it? yep / edit / day off"_. (`NO_CONTEXT`/empty → re-seed contexts;
     `FETCH_ERROR` → GitHub token; routed to `spine` instead of `open` → your message named a
     period or context, which scopes it to a reflection.)
2. **Approve:** reply `yep`.
   - Expect: it posts the salute to the team channel and confirms _"Posted… 🫡"_. Check the
     channel.
3. **Edit path:** new thread → address the bot → reply with a rewrite, e.g.
   _"make it: wrapped the embedding fix on OCS; Mulligans rollout starts Thursday"_.
   - Expect: it posts your edited wording.
4. **Day-off path:** address the bot → `day off`.
   - Expect: _"enjoy the day off… nothing posted"_; channel unchanged.
5. **Reflection (scoped) still works:** `last week on ocs` (a period + context) → routes to the
   **spine** (the private Mirror reflection), **not** the salute flow.
6. **Stale/late drafts:** open a draft, don't confirm; next day open again → the new draft
   replaces the old (Stage overwrites `vc_hb_pending_*`). A late `yep` posts the _current_
   pending draft only.
7. **Drift (don't-do-this check):** start a brand-new top-level DM (not in the heartbeat
   thread). The next nudge fires there with empty state and any staged draft is stranded — this
   is the §6 multi-session-drift failure the MVP mitigates _procedurally_ (reply in the one
   thread). Confirm your setup has a single DM session; the in-pipeline drift guard is a later
   refinement.

---

## Step 8 — Is it alive? (the liveness metric)

Per design §11: rolling 2-week **weekday reply rate**.

- **Numerator** (you engaged): `last_heartbeat_date` written by Close into participant data —
  inspect via OCS admin or the Django shell (`ParticipantData.data["last_heartbeat_date"]`).
- **Denominator** (nudges fired): the schedule's own counters —
  `ScheduledMessage.total_triggers` / `last_triggered_at` (and `ScheduledMessageAttempt` rows),
  filtered to weekdays. Not pipeline state (the nudge is a non-pipeline EventBot).
- **Read it:** Healthy ≥ 60%; Watch 40–60% (reduce cadence / go weekday-only or 3×/week);
  Kill < 40% sustained past a **≥ 8-nudge warm-up**. A "day off" reply counts as engagement.
- **Caveat:** `total_triggers` increments even when a nudge couldn't be delivered (no session),
  so the denominator assumes the bootstrap invariant holds (one persistent DM session). A
  sudden low rate may be stranded-session drift (Step 7.7), not disengagement — check before
  acting on the kill criterion.

---

## Gotchas (read before debugging)

Carries the [V1 gotchas](build-v1-declared-spine.md#gotchas-read-before-debugging) (publish
trap, all-code-in-`main`, no leading underscores, no tuple-unpack, braces in LLM prompts,
10-HTTP-calls budget, preview-can't-test-participant-data). Plus, new to the heartbeat:

- **The nudge is rephrased, not verbatim.** `EventBot` rewrites your `prompt_text`
  (`apps/chat/bots.py:301`). Fine for a nudge; the **draft and salute are produced in-pipeline**
  and are verbatim/approval-gated.
- **The schedule can't run the pipeline.** A `ScheduledMessage` only fires `EventBot`
  (`apps/events/models.py:541`), never `PIPELINE_START`. The pipeline runs on **your reply** —
  this is by design, not a bug.
- **Reply in-thread; don't start a new DM.** Nudges fire into `get_latest_session` (newest by
  `created_at`). A new top-level DM creates a new session and future nudges go there, stranding
  any staged draft. (A future Resolve-HB refinement can detect a nudge arriving in a session
  whose thread ≠ the pinned heartbeat thread and re-bootstrap. For MVP: keep replying in the
  one thread; setup checks should confirm one DM session.)
- **`vc_hb_*` keys are heartbeat-only.** They're distinct from `resolve.py`'s `vc_awaiting` /
  `vc_last_period` so the heartbeat and the on-demand spine never clobber each other in the
  shared thread.
- **Post retry is best-effort.** If `chat.postMessage` fails, the handshake is already cleared,
  so a missed post isn't auto-retried (a missed post beats a duplicate). Re-run a `vibe check`
  to regenerate. Hardening retry (keep `vc_hb_post_text` in session until confirmed `ok`) is a
  later refinement.
- **Duplicate replies = Slack event retries.** The pipeline runs synchronously and takes
  ~10s; Slack expects a 200 ack within **3s**, so it **re-delivers** the same event and OCS
  re-runs it (it does not check `X-Slack-Retry-Num`). With state mutating between runs you can
  get two replies (one reflects, one drafts). Mitigate with faster models (mini / lower effort)
  and don't pile rapid messages on a slow turn. The real fix is OCS-level retry-dedup or async
  processing — worth a Dimagi issue.
- **Use a fresh thread per check-in while testing.** Session state is keyed to the Slack
  thread, and the LLM nodes use **History = Global**, so reusing/continuing an old thread
  carries stale handshake state (`vc_hb_awaiting`, an old `pending_salute`, a prior intent) and
  feeds the whole accumulated history to the model — which can make it re-reflect or behave
  oddly. Start a new top-level message for a clean run.
- **Repo cap.** Fetch is capped at 5 repos/run (10-HTTP-call budget, 2 calls/repo). With more
  than 5 declared repos, the extras are skipped and noted — keep declared repos lean, or raise
  `RESTRICTED_HTTP_MAX_REQUESTS`.

---

## What's deliberately not here (later phases)

Per the design roadmap (§13): **NVC reflection in the heartbeat** (Option 3), **escalation
nudges** (Slack→WhatsApp→call), **discovery** of unmentioned work, **non-GitHub sources**, and
**personas / flight levels**. Each gets its own manual when we reach it.
