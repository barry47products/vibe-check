# Vibe Check — Build Manual (V1 declared spine)

A click-by-click guide to assembling the V1 mirror in the OCS UI. You follow the steps;
you paste two artefacts (a prompt and a Code-node snippet). No coding.

**What V1 does:** on demand, it pulls your real GitHub activity for the active context,
holds it up against your stated intent (remembered across conversations), and reflects in
NVC tone. Signals are fetched automatically — no more pasting.

**The pipeline you're building:**

```text
[Start] → [Fetch signals · Code node] → [Mirror · LLM node] → [End]
```

Everything deterministic (window + GitHub fetch) happens in the Code node; the reflection
happens in the LLM node. Design rationale lives in
[`../superpowers/specs/2026-06-01-vibe-check-mirror-design.md`](../superpowers/specs/2026-06-01-vibe-check-mirror-design.md).

**Artefacts you'll paste:**

- [`ocs/prompts/mirror-agent.md`](../../ocs/prompts/mirror-agent.md) — the Mirror system prompt
- [`ocs/snippets/fetch_signals.py`](../../ocs/snippets/fetch_signals.py) — the Fetch Code node

---

## Prerequisites

- Local OCS running, with Slack already integrated (you have this).
- A GitHub account (`barry47products`).
- 15 minutes.

---

## Step 1 — Create a GitHub token

Public repos can be read without a token, but private ones (e.g. `mulligans-law-monorepo`)
need one, and a token also lifts your rate limit. Create a **fine-grained PAT**:

1. GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token.
2. **Repository access:** only the repos you'll declare (e.g. `mulligans-law-monorepo`;
   public ones like `dimagi/open-chat-studio` need no grant but it's harmless to include).
3. **Permissions:** Repository → **Contents: Read-only** and **Issues/Pull requests: Read-only**.
   Nothing else. (This is the smallest token that works — the upside of declared-only.)
4. Copy the token.

---

## Step 2 — Store the token as an OCS Auth Provider

The Code-node `http` client injects this by _name_, so the token never lives in the snippet.

1. In OCS: **Service Providers → Auth Provider → Create → Bearer**
   (URL: `/service_providers/auth_provider/create/bearer/`).
2. **Name:** `github-vibe-check` (must match `AUTH_PROVIDER_NAME` in the snippet).
3. **Bearer Token:** paste the PAT. Save. (Stored encrypted.)

---

## Step 3 — Contexts (managed conversationally; shell seeding optional)

Contexts live in participant data and are **managed by talking to the bot** — no code edits,
no re-publish. After the pipeline's built, just say:

- `add a context ocs for dimagi/open-chat-studio`
- `add a context mulligans for barry47products/mulligans-law-monorepo, barry47products/mulligans-law-front-end`
- `list contexts`

The Mirror node appends them to participant data via the Append-to-Participant-Data tool, and
naming a context in a check-in switches to it. The Fetch node only _reads_ contexts.

The Django-shell seed below is **optional** — a faster way to bulk-preload contexts for a
specific participant (e.g. your Slack user) instead of adding them one message at a time.

Two facts make this robust (verified in OCS, `apps/experiments/models.py:1303-1308`):
participant data is keyed on the experiment's **working version** (a Slack/preview session
on a _published_ version resolves back to it), and it's per-**participant**. So we seed
against `.get_working_version()` and seed **every participant that's used the chatbot** —
no identifier guessing.

The seed is a small script at [`ocs/seed/seed_contexts.py`](../../ocs/seed/seed_contexts.py).
Edit its top constants — `TEAM_SLUG`, `CHATBOT_ID` (from the URL `/chatbots/<ID>/`), and
`CONTEXTS` — then **pipe it into Django's shell** from the OCS repo directory:

```bash
uv run python manage.py shell < "/Users/barrytandy/Dev/Afrolabs/Vibe Check/ocs/seed/seed_contexts.py"
```

> **Run it piped, do NOT paste it into the interactive `>>>` shell.** The interactive REPL
> executes pasted blocks line-by-line and mangles blank lines / loops. Piping feeds Django
> the whole file as one script, which just works.

Expect output like `seeded: web | <your-identifier>` (and `slack | …` if you've messaged
it there). Those printed identifiers confirm the data landed on the right participants, so
the old `NO_CONTEXT` mismatch can't bite. Re-run the same command after editing the file.

---

## Step 4 — Use the chatbot

Reuse your `vibe-check-mirror-spike` copy, or create a fresh chatbot. Open its **pipeline**.

---

## Step 5 — Build the pipeline

### 5a. Fetch signals (Code node)

1. Add a **Code** node between Start and the rest.
2. Paste **all** of [`ocs/snippets/fetch_signals.py`](../../ocs/snippets/fetch_signals.py)
   into the node's code field.
3. Confirm the top constants: `AUTH_PROVIDER_NAME = "github-vibe-check"` and
   `MAX_REPOS_PER_CHECKIN = 5`.
4. Wire **Start → Fetch**.

### 5b. Mirror (LLM node)

1. Add an **LLM** node (the plain one — not OpenAI Assistant, not Router).
2. **Model:** a premium model. **History Type:** **Global**.
3. **Prompt:** paste everything below the blockquote from
   [`ocs/prompts/mirror-agent.md`](../../ocs/prompts/mirror-agent.md), then append this
   **wiring note** so it knows where its inputs come from and how to remember intent:

   ```text
   ## How your inputs arrive (wiring)

   Each turn you receive one message, assembled by an upstream step, containing:
   - BARRY'S MESSAGE: his actual words this turn.
   - SIGNALS: the real activity for the active context + period — already fetched. These
     are the facts; never ask Barry to paste signals.
   - STATED INTENT: what he previously said the period was about, or "(none on record)".

   Rules:
   - If STATED INTENT is "(none on record)" and BARRY'S MESSAGE states what the period was
     meant to be about, FIRST persist it: use the Update Participant Data tool to set
     `current_intent` to {"stated": "<his words>", "on_date": "<today's ISO date>"}. Then reflect.
   - If STATED INTENT is present, reflect SIGNALS against it.
   - If STATED INTENT is "(none on record)" and he hasn't stated one, ask for it (one question) — don't reflect yet.
   ```

4. **Tools:** enable the built-in **Update Participant Data** and **Append to Participant
   Data** tools — the first remembers intent and the active context; the second lets you add
   contexts conversationally ("add a context X for owner/repo").
5. Wire **Fetch → Mirror**, then **Mirror → End**.

---

## Step 6 — Test on Slack (the real end-to-end test)

> **The pipeline preview ("Send test message") can't test this.** It runs under a
> throwaway _anonymous_ participant and a temporary experiment, all rolled back when done
> (`apps/pipelines/nodes/helpers.py` `temporary_session`), so `get_participant_data()` is
> always empty there → you'll only ever get `NO_CONTEXT`. The preview is fine for stateless
> prompt testing; participant-data flows must be tested in a **real session** (Slack).

1. Make sure Step 3 seeded your **Slack** participant (`platform="slack"`, your Slack user id).
2. **Publish a new version** of the chatbot (Slack serves the _published_ version — see gotchas).
3. In Slack, message the bot in a thread: `vibe check this week`.
   - Expect: it fetches your real OCS signals, sees no stored intent, and **asks** what the
     week was meant to be about. (`NO_CONTEXT` → the Slack participant isn't seeded;
     `FETCH_ERROR` → token / Auth Provider name.)
4. Reply with an intent, e.g. `finishing the embedding retrieval work`.
   - Expect: it **reflects** signals against that intent in NVC tone — _and_ silently saves
     `current_intent` via the Update Participant Data tool.
5. Start a **new thread**, send `vibe check`.
   - Expect: it already **knows** your intent (read from participant data) and reflects
     immediately. This proves cross-conversation intent memory — the load-bearing V1 feature.

To check a different window: `vibe check yesterday` or `vibe check last week`.

---

## Gotchas (read before debugging)

- **Publish trap.** Slack serves the **published** version; the preview serves your
  **working** version. After any edit, _publish_ before testing on Slack, or you'll see the
  old behaviour. (You hit this during the spike.)
- **All code inside `main`.** A Code node defines exactly one top-level function, `main`.
  Helper functions are allowed but must be **nested inside `main`** (per the
  [Python node docs](https://docs.openchatstudio.com/tech-hub/python_node/)). Our snippet
  inlines instead — either is fine.
- **LLM-node prompts are Python `.format()` templates.** A literal `{` or `}` in the prompt
  (e.g. a JSON example) is parsed as a template variable and rejected ("Invalid prompt
  variable"). Describe structures in prose, or double the braces (`{{` / `}}`).
- **Module-level names are invisible inside `main`.** The node `exec`s with separate
  globals/locals, so top-level constants (`X = 5`) aren't visible inside `main` —
  `NameError`. Put everything `main` needs inside `main`; only `import` stays outside.
  (Injected globals like `http`/`datetime` *are* visible.)
- **No attribute access at module level.** Code outside `main` runs at save/validate time
  with bare globals, so `X = datetime.timezone(...)` fails with a `_getattr_ not defined`
  error.
  Keep only `import` and plain-literal constants outside `main`; do attribute access inside it
  (where it works fine).
- **No leading underscores in Code nodes.** OCS's RestrictedPython sandbox rejects any
  variable/function name starting with `_` (e.g. `_helper`). Name everything plainly.
- **Limited builtins in Code nodes.** `next()`, `open()`, etc. aren't available; stick to
  plain names, list comprehensions, and the injected helpers (`http`, `get_participant_data`,
  `set_temp_state_key`).
- **No tuple-unpacking assignment** (`a, b = x, y`) — the sandbox lacks the unpack guard.
  Assign one variable per line. (Unpacking in `for` loops/comprehensions is fine.)
- **Call budget.** A Code node may make **10 HTTP calls** per run; the Fetch node uses 2 per
  repo → **max 5 repos per context per check-in**. More than that and the snippet skips the
  extras and says so. (It's your instance — you can raise `RESTRICTED_HTTP_MAX_REQUESTS` in
  settings if needed.)
- **Search rate limit.** GitHub's search API is 30 req/min; fine for declared repos.
- **Private repos** need the fine-grained PAT to actually grant them (Step 1.2), or the
  commits/issues calls return empty or 404.
- **Don't use GitHub's Search API with a fine-grained PAT.** `/search/issues` with a
  `repo:` qualifier returns **422** unless the token is scoped to that repo — even for
  public repos (you can't scope a fine-grained PAT to someone else's org repo). Direct REST
  reads (`/repos/{o}/{r}/commits`, `/repos/{o}/{r}/issues`) work on public repos with any
  token. The snippet uses REST for this reason. (Implication: Phase-3 discovery, which needs
  cross-repo search, will require a classic PAT or unauthenticated search.)
- **Identifier mismatch** is the #1 cause of `NO_CONTEXT` — see the Step 3 snag.
- **Tracing stays off.** You have no tracing provider configured, so signal content stays in
  local Postgres and isn't exported. Keep it that way until the privacy gate (design §13.6)
  is addressed — relevant only when non-GitHub/sensitive sources arrive later.

---

## What's deliberately _not_ here (later phases)

Per the design roadmap: **proactive** check-ins (Phase 2), **discovery** of unmentioned work
(Phase 3), and **Jira/Slack/Drive** sources (Phase 4). V1 is the reliable spine they build on.
Each gets its own manual when we reach it.
