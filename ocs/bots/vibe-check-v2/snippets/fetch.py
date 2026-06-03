# Vibe Check v2 — Fetch (OCS Code node). Start -> Resolve -> [Fetch] -> Draft -> End.
# Pure I/O over the resolved request in TEMP state. Admin/no-context pass through as RELAY.
# OCS sandbox: one main; helpers nested; no enumerate/zip/map/next/open.
# ruff: noqa: F821
def main(input, **kwargs):
    auth_provider = "github-vibe-check"
    max_repos = 5
    accept = {"Accept": "application/vnd.github+json"}

    mode = get_temp_state_key("vc_mode") or "checkin"
    msg = get_temp_state_key("vc_message") or (input or "")

    if mode == "manage" or mode == "no_context":
        return "RELAY: " + (get_temp_state_key("vc_reply") or "")

    repos = get_temp_state_key("vc_repos") or []
    author = get_temp_state_key("vc_author") or ""
    since_iso = get_temp_state_key("vc_since_iso")
    until_iso = get_temp_state_key("vc_until_iso")
    slug = get_temp_state_key("vc_slug") or ""
    period = get_temp_state_key("vc_period_label") or ""
    since_date = get_temp_state_key("vc_since_date")
    until_date = get_temp_state_key("vc_until_date")

    if get_temp_state_key("vc_discover"):
        # No contexts configured: discover the PAT user's repos pushed within the window.
        # Capped at 4 to stay within the 10-call budget (1 list + 4 x 2 per-repo calls).
        listing = http.get("https://api.github.com/user/repos",
                           params={"sort": "pushed", "direction": "desc", "per_page": 30,
                                   "affiliation": "owner,collaborator,organization_member"},
                           headers=accept, auth=auth_provider, timeout=15)
        if listing["is_success"]:
            for r in (listing["json"] or []):
                pushed = (r.get("pushed_at", "") or "")[:10]
                full = r.get("full_name", "") or ""
                if full and since_date and pushed >= since_date and full not in repos:
                    repos.append(full)
        repos = repos[:4]

    def repo_lines(repo):
        commits = http.get("https://api.github.com/repos/" + repo + "/commits",
                           params={"author": author, "since": since_iso, "until": until_iso, "per_page": 100},
                           headers=accept, auth=auth_provider, timeout=15)
        if commits["status_code"] == 404:
            return {"skip": "Repo: " + repo + "\n  (skipped — HTTP 404; private/not in token scope, or wrong path)"}
        if not commits["is_success"]:
            return {"error": "FETCH_ERROR: commits for " + repo + " -> HTTP " + str(commits["status_code"]) + "."}
        issues = http.get("https://api.github.com/repos/" + repo + "/issues",
                          params={"creator": author, "state": "all", "since": since_iso, "per_page": 100},
                          headers=accept, auth=auth_provider, timeout=15)
        issues_items = []
        if issues["is_success"]:
            issues_items = issues["json"] or []
        out = ["Repo: " + repo]
        for c in (commits["json"] or []):
            commit = c.get("commit", {})
            text = commit.get("message", "") or ""
            first = text.splitlines()[0][:140] if text else ""
            cdate = (commit.get("author", {}).get("date", "") or "")[:10]
            out.append("  - commit " + cdate + "  " + first)
        for item in issues_items:
            created = (item.get("created_at", "") or "")[:10]
            if since_date <= created <= until_date:
                kind = "pr" if item.get("pull_request") else "issue"
                out.append("  - " + kind + " #" + str(item.get("number", "")) + " [" + (item.get("state", "") or "") + "] " + (item.get("title", "") or "")[:140])
        if len(out) == 1:
            out.append("  (no activity in window)")
        return {"lines": out}

    lines = []
    for repo in repos[:max_repos]:
        result = repo_lines(repo)
        if "error" in result:
            return "BARRY'S MESSAGE: " + msg + "\n\n" + result["error"]
        if "skip" in result:
            lines.append(result["skip"])
        else:
            lines.extend(result["lines"])
    note = ""
    dropped = repos[max_repos:]
    if dropped:
        note = "\n(NOTE: " + str(len(dropped)) + " repo(s) not fetched due to the call budget: " + ", ".join(dropped) + ")"
    body = "\n".join(lines) if lines else "(no repos)"
    head = "SIGNALS for " + slug + ", period: " + period + " (" + since_date + " to " + until_date + ")"
    return "BARRY'S MESSAGE: " + msg + "\n\n" + head + "\n\n" + body + note
