# Vibe Check pipeline smoke-test runbook

The OCS pipeline is configuration, not code. This runbook walks through bringing it up end-to-end against a local sandbox so the JSON we commit in `ocs/pipelines/interview.json` is reproducible.

## Prerequisites

- Local OCS instance running (`docker compose up` in your OCS checkout, typically).
- The Vibe Check repo cloned with `uv sync` complete.
- Generated JSON Schemas present in `schemas/` (`uv run python scripts/generate_schemas.py`).
- A throwaway git repo at e.g. `/tmp/vibe-smoke-repo/` with at least 2 seeded commits.
- A Jira API token for a sandbox project (or a recorded fixture — see §3 below).
- A Slack workspace with a bot configured in OCS pointing at a channel you can clean up (e.g. `#vibe-check-smoke`).

## 1. Bot + channel setup

1. In OCS, create a new chatbot named `vibe-check-smoke`.
2. Attach the Slack channel via OCS's Slack channel integration. Confirm a "hello" round-trip works.

## 2. Pipeline nodes (in order)

Match the flow from spec §7. Add these nodes:

1. **Router (intent).** Branches: `log`, `view`, `timesheet`, `help`.
2. **Python Node — git_scrape.** Call `helpers.git_scrape.get_git_activity` with the configured repos. **Hard-fail** policy: if it raises, route to a "couldn't reach git, please retry" reply node.
3. **Python Node — jira_fetch.** Same — hard-fail on error.
4. **LLM Node — opening probe.** Use `ocs/prompts/system.md` as the system prompt; pass git+jira context into the user message.
5. **LLM Router — pick shape.** Use `ocs/prompts/shape-router.md`. If output is `UNCLEAR: <q>`, ask the question and loop back.
6. **Extract Structured Data.** For the chosen shape, load `schemas/entry.<shape>.json`. Configure: up to 3 retries on validation failure; on final failure, set `needs_review: true` and store anyway.
7. **LLM Node — render draft entry; ask accept/correct.**
8. **Python Node — log_writer.write_log.** Pass the validated entry + the configured `logs_dir` (e.g. `/tmp/vibe-smoke-logs/`).
9. **Python Node — log_git.commit.** Best-effort.
10. **LLM Node — "more to log?"** Loop back to step 4 if yes.
11. **Python Node — bulletin_render.render_bulletin.** Style: `slack`.
12. **LLM Node — show bulletin, ask post/correct.**
13. **Send-to-Slack Node.** Channel: `#vibe-check-smoke`.

## 3. Recording a Jira fixture (optional)

If your Jira sandbox is unreliable, capture a payload once with curl:

```bash
curl -u "${JIRA_EMAIL}:${JIRA_TOKEN}" \
  "${JIRA_BASE_URL}/rest/api/3/activity?streams=user+IS+${JIRA_ACCOUNT_ID}" \
  > tests/fixtures/jira_activity.sample.json
```

In the Python node for Jira, you can branch: read from the fixture if `OCS_USE_JIRA_FIXTURE=1`, else hit the API.

## 4. Walkthrough

1. In Slack, DM the bot: `let's log today`.
2. Confirm git+jira summary is in the opening reply.
3. Type a deep work description, e.g.: `Spent 4 hours on the compliance policy section 4 draft.`
4. Confirm the shape question fires, answer `yes`.
5. Confirm the extracted entry rendering is accurate.
6. Confirm `/tmp/vibe-smoke-logs/<today>.md` was created with valid frontmatter.
7. Confirm a git commit appeared in `/tmp/vibe-smoke-logs/`.
8. Say `that's it for today`.
9. Confirm the bulletin renders and you can post it; verify it arrives in `#vibe-check-smoke`.

## 5. Export and commit the pipeline

Once the pipeline works end-to-end:

```bash
# Export from OCS UI → save as ocs/pipelines/interview.json
git add ocs/pipelines/interview.json
git commit -m "feat(ocs): commit working interview pipeline export"
```

## 6. Discovery items to revisit

These are listed in spec §14 and should be re-checked after smoke:

1. Exact Jira API endpoint behavior on your instance — adjust `helpers/jira_fetch.py` if needed.
2. OCS Slack channel scopes and app-level config specifics.
3. Whether the shape-router prompt needs tuning based on real responses.
4. Whether OCS round-trips the pipeline JSON cleanly or some UI-only state remains.
5. Whether a `/vibe status` quick command (no full interview) earns its place in V1.
