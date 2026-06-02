# OCS node → file map

One canonical file per OCS node, so you can open the file, **copy all, paste into the node** in
the OCS UI. After pasting any Code node or LLM prompt, **Publish the chatbot** (Slack serves the
published version). Full walkthrough: [runbooks/build-heartbeat.md](runbooks/build-heartbeat.md).

These files are the **source of truth** — they match what should be live in the nodes.

## Pipeline graph

```text
[Start] → [Resolve-HB] → [Branch · vc_hb_route]
              ├─ spine → [Spine · Resolve] → [Spine · Fetch] → [Spine · Mirror] → [End]
              ├─ open  → [Open · Fetch]  → [Open · Draft]  → [Open · Stage]  → [End]
              └─ reply → [Reply · Interpret] → [Reply · Close] → [Reply · Post] → [End]
```

## Code nodes

| Node | File | Notes |
| ---- | ---- | ----- |
| Resolve-HB | [snippets/resolve_hb.py](snippets/resolve_hb.py) | front-router; weekly + gap-aware windows |
| Spine · Resolve | [snippets/resolve.py](snippets/resolve.py) | on-demand resolver (single context + period) |
| Spine · Fetch | [snippets/fetch_signals.py](snippets/fetch_signals.py) | GitHub fetch |
| Open · Fetch | [snippets/fetch_signals.py](snippets/fetch_signals.py) | **same file** as Spine · Fetch (separate node instance) |
| Open · Stage | [snippets/open_stage.py](snippets/open_stage.py) | stages draft, invites shaping |
| Reply · Close | [snippets/reply_close.py](snippets/reply_close.py) | clears handshake, records engagement |
| Reply · Post | [snippets/reply_post.py](snippets/reply_post.py) | posts salute; channel `C0B6S0T2NES` |

## LLM nodes (prompts)

| Node | Prompt file | Model | Provider |
| ---- | ----------- | ----- | -------- |
| Spine · Mirror | [prompts/mirror-agent.md](prompts/mirror-agent.md) (+ wiring note) | gpt-5.4 | Vibe Check OpenAI |
| Open · Draft | [prompts/open_draft.md](prompts/open_draft.md) | gpt-5.4 | Vibe Check OpenAI |
| Reply · Interpret | [prompts/reply_interpret.md](prompts/reply_interpret.md) | gpt-5.4-mini | Vibe Check OpenAI |

History Type **Global** on all LLM nodes. Do **not** set them to the Anthropic provider — its
key rejects the catalog's default models (see build-heartbeat gotchas).

## Branch · vc_hb_route (Static Router — no code)

- Data source: **Temporary State**
- Route key: `vc_hb_route`
- Keywords: `spine`, `open`, `reply` (default `spine`)

## Schedule (not a pipeline node)

The morning nudge `prompt_text` for the five weekday `ScheduledMessage`s is in
[prompts/nudge.md](prompts/nudge.md). It's stored on the `ScheduledMessage` (not pasted into a
node); EventBot — the experiment's default LLM provider — rephrases it and it does **not** run
the pipeline. To change it, update the schedule's params, not a node.
