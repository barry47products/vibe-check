# Mirror spike — sample signals

A small, realistic week to paste into the thread on your **first dry run**, before
wiring real signal sources. It deliberately contains a gap: the stated intent is
single-context, but the signals show a second context the intent didn't mention.

Use the **Stated intent** as your _first_ message to the bot, then paste the
**Signals** block when it asks (or alongside, if you prefer).

---

## Stated intent (say this first)

> This week was meant to be OCS embedding work — finishing the Voyage/Google retrieval fix.

## Signals (paste when asked)

```bash
Period: 2026-05-25 → 2026-05-29
Context: ocs  (repo: dimagi/open-chat-studio, author: barry47products)
  - PR #3432 MERGED "Voyage/Google embed_documents + OpenAI base URL" (+313/-36, 5 files), 2-day review
  - 9 commits referencing embedding/input_type/base_url
  - issue #3433 OPENED "local-index retrieval surfaces chunks from FAILED files"

Context: bermuda-bank-eng  (repo: bermudabank/core, author: barry47products)
  - 3 commits Tuesday 2026-05-26, messages: "hotfix: rotate leaked webhook secret",
    "patch infra alarm threshold", "revert noisy alert"
  - no PR, committed straight to main

Context: ocs
  - 1 commit Thursday on docs/developer_guides/slack_channel_integration.md
```

---

A mirror that's working should notice the **Bermuda Tuesday hotfix** wasn't in the
stated intent, and ask about it without judging it — and may note it could belong on a
different invoice. If it just summarises the week back at you, the prompt needs work.
