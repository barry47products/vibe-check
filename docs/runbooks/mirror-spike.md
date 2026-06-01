# Mirror spike — runbook

**Goal:** test the *one* unknowable thing in the evolved Vibe Check — does the NVC
mirror *feel right*? — by setting it up by hand in OCS and running real check-ins.
We are testing **tone and usefulness**, not plumbing. No code, no design doc yet; the
notes from this spike (see [mirror-spike-notes.md](mirror-spike-notes.md)) become the
design.

**What "good" looks like:** given your signals and what you said you intended, the bot
surfaces the *gap* between them, neutrally and curiously, and asks one real question —
rather than summarising your week back at you or congratulating you.

## Prerequisites (you have these)

- Local OCS instance running, with the spine pipeline + Slack integration already wired.
- A Slack channel/DM you can talk to the bot in.

## Step 1 — Make a throwaway copy of the chatbot

Don't touch your working spine. On your existing chatbot's home page in OCS, click
**Copy** — this duplicates the whole chatbot (pipeline included) as a new one. Rename it
`vibe-check-mirror-spike`. All edits below happen on the copy; delete it when you're done.

## Step 2 — Reduce the pipeline to just the mirror

Open the copy's pipeline editor. For this spike you only need the conversational
reflection, so simplify the graph to three nodes:

```
[Start] → [LLM] → [End]
```

`Start` and `End` are already on the canvas. Detach or delete any other nodes (bulletin
/ extract / Python / router) so the only thing between Start and End is one **LLM** node.
(They stay intact in your working spine — this is a copy.)

## Step 3 — Add and wire the LLM node

1. Add an **LLM** node (it's in the node palette — the plain LLM chat node, *not* "OpenAI
   Assistant" and *not* "LLM Router").
2. Connect **Start → LLM → End** by dragging from each node's output handle to the next
   node's input handle.

## Step 4 — Configure the LLM node

1. Set **LLM Provider** and pick a **premium model** (the reflection quality is the whole
   point — don't test tone on a cheap model).
2. Open **[`ocs/prompts/mirror-agent.md`](../../ocs/prompts/mirror-agent.md)**, copy
   everything **below** the `> blockquote` header note, and paste it into the node's
   **prompt** field.
3. Set **History Type** to **Global** so it remembers the conversation within a thread.
4. Leave Tools / Custom Actions / Built-in Tools empty for now.
5. Save.

## Step 5 — First dry run with sample signals (in the web preview)

You don't need Slack to test tone. Use OCS's built-in **chat preview / playground** on
the chatbot to run the dry conversation first — it's the fastest tuning loop.

This confirms the prompt behaves before you involve real data.

1. Open **[`mirror-spike-sample-signals.md`](mirror-spike-sample-signals.md)**.
2. In the preview chat, send the bot the **Stated intent** line first.
3. When it asks about the period (or right away), paste the **Signals** block.
4. Watch what it does. It should notice the **Bermuda Tuesday hotfix** isn't in your
   stated intent and ask about it *without judging* — possibly flagging it might belong
   on a different invoice. If it just lists your week back, the prompt needs tuning
   (note it, tweak `mirror-agent.md`, re-paste, retry).

## Step 6 — Real check-ins (the actual test)

Run **3–4 check-ins on your real, recent weeks.** For each:

1. Tell it what the period was *meant* to be about (your stated intent).
2. Paste your real signals for that period. Quickest source:
   - `git log --since=... --until=... --pretty='- %s' --author=barry47products` in each repo, **or**
   - your merged PRs / issues from the week, pasted as a short list.
3. Have the conversation. Answer its question honestly.
4. Immediately jot what happened in
   [mirror-spike-notes.md](mirror-spike-notes.md) — while it's fresh.

## Step 7 (optional) — Go live on Slack / wire a real signal source

Only once the *tone* feels right:

- **Slack:** bind the spike chatbot to a **test** Slack channel/DM (chatbot home →
  Channels → Add Channel → Slack) if you want to feel it in the real surface.
- **Signals:** if `github_activity` is already a Custom Action in your spine, add it
  before the LLM node so signals are pulled automatically instead of pasted. If it
  isn't, pasting is a perfectly good test of the mirror — wiring signals is known
  plumbing we can add later.

## Step 8 — Decide

After 3–4 runs, look at the notes and answer:

- Does the mirror earn its place — does it tell you something a plain summary wouldn't?
- Is the NVC tone right, or does it nag / flatter / go vague?
- Is "stated intent vs signals" the right axis, or did the useful reflections come from
  somewhere else?

Bring the notes back and we turn them into the evolved design doc — grounded in what
actually worked, not guesses.

## Tuning loop

Between any two runs, edit **[`ocs/prompts/mirror-agent.md`](../../ocs/prompts/mirror-agent.md)**,
re-copy it into the LLM node's **prompt** field, and go again. The file is the source of
truth for the prompt; keep it current so the version that works is the version we keep.
