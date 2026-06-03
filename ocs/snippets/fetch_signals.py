# Vibe Check — Fetch (OCS Code node) — V1.5
#
# Runs AFTER Resolve:  Start -> Resolve -> [Fetch] -> Mirror -> End.
# Pure I/O: reads the resolved request from TEMP state (set by Resolve); on a check-in it
# calls GitHub and assembles the signals block for the Mirror. Other modes pass through.
# All context/period/intent logic lives in resolve.py — not here.
#
# OCS Code-node rules: one top-level `main`; helpers nested; no leading-underscore names.
# Injected globals: http, get_temp_state_key.
# ruff: noqa: F821
# pyright: reportUndefinedVariable=false


def main(input, **kwargs):
    auth_provider = "github-vibe-check"
    max_repos = 5
    accept = {"Accept": "application/vnd.github+json"}

    mode = get_temp_state_key("vc_mode") or "checkin"
    msg = get_temp_state_key("vc_message") or (input or "")
    available = get_temp_state_key("vc_available") or "(none yet)"

    def block(extra):
        return f"BARRY'S MESSAGE: {msg}\n\nAVAILABLE CONTEXTS: {available}\n{extra}"

    if mode == "manage":
        return block("MANAGE_RESULT: " + (get_temp_state_key("vc_reply") or ""))

    if mode == "no_context":
        return block("NO_CONTEXTS: Barry has no contexts configured. Offer to add one, "
                     "e.g. 'add a context ocs for dimagi/open-chat-studio'.")

    if mode == "ask_intent":
        slug = get_temp_state_key("vc_slug") or ""
        period = get_temp_state_key("vc_period_label") or ""
        head = f"NEEDS_INTENT for context '{slug}', period: {period}." if slug else f"NEEDS_INTENT period: {period}."
        return block("STATED INTENT: (none on record - ask Barry)\n" + head)

    # --- check-in ---
    repos = get_temp_state_key("vc_repos") or []
    author = get_temp_state_key("vc_author") or ""
    since_iso = get_temp_state_key("vc_since_iso")
    until_iso = get_temp_state_key("vc_until_iso")
    since_date = get_temp_state_key("vc_since_date")
    until_date = get_temp_state_key("vc_until_date")
    slug = get_temp_state_key("vc_slug") or ""
    period = get_temp_state_key("vc_period_label") or ""
    intent = get_temp_state_key("vc_intent") or "(none on record - ask Barry)"

    def repo_lines(repo):
        commits = http.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={"author": author, "since": since_iso, "until": until_iso, "per_page": 100},
            headers=accept, auth=auth_provider, timeout=15)
        if commits["status_code"] == 404:
            return {"skip": f"Repo: {repo}\n  (skipped — HTTP 404; private/not in token scope, or wrong path)"}
        if not commits["is_success"]:
            return {"error": f"FETCH_ERROR: commits for {repo} -> HTTP {commits['status_code']}. Halting."}
        issues = http.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"creator": author, "state": "all", "since": since_iso, "per_page": 100},
            headers=accept, auth=auth_provider, timeout=15)
        issues_items = []
        if issues["is_success"]:
            issues_items = issues["json"] or []
        elif issues["status_code"] not in (404, 410):
            return {"error": f"FETCH_ERROR: issues for {repo} -> HTTP {issues['status_code']}. Halting."}
        out = [f"Repo: {repo}"]
        for c in (commits["json"] or []):
            commit = c.get("commit", {})
            text = commit.get("message", "") or ""
            first = text.splitlines()[0][:140] if text else ""
            cdate = (commit.get("author", {}).get("date", "") or "")[:10]
            out.append(f"  - commit {cdate}  {first}")
        for item in issues_items:
            created = (item.get("created_at", "") or "")[:10]
            if created < since_date or created > until_date:
                continue
            kind = "pr" if "pull_request" in item else "issue"
            title = (item.get("title", "") or "")[:140]
            out.append(f"  - {kind} #{item.get('number')} [{item.get('state', '')}] {title}")
        if len(out) == 1:
            out.append("  (no activity in window)")
        return {"lines": out}

    lines = []
    for repo in repos[:max_repos]:
        result = repo_lines(repo)
        if "error" in result:
            return block(f"STATED INTENT: {intent}\n{result['error']}")
        if "skip" in result:
            lines.append(result["skip"])
            continue
        lines.extend(result["lines"])

    note = ""
    dropped = repos[max_repos:]
    if dropped:
        note = f"\n(NOTE: {len(dropped)} repo(s) not fetched due to the call budget: {', '.join(dropped)})"
    body = "\n".join(lines) if lines else "(no repos)"
    head = f"SIGNALS for context '{slug}', period: {period} ({since_date} to {until_date})"
    if get_temp_state_key("vc_continue"):
        head = ("CONTINUATION — Barry is still in this reflection; respond to his latest message "
                "and build on what you've already said. Don't restart the summary.\n" + head)
    return block(f"STATED INTENT: {intent}\n{head}\n\n{body}{note}")
