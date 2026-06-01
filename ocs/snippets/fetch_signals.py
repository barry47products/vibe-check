# Vibe Check — Fetch Signals (OCS Code node)
#
# Paste this whole file into a Code node placed between Start and the Mirror LLM node.
# For the active context it pulls GitHub commits + PRs/issues in the requested window,
# normalises them, and passes a readable block to the Mirror.
#
# OCS Code-node rules (https://docs.openchatstudio.com/tech-hub/python_node/ + sandbox quirks):
#   - exactly ONE top-level function, `main(input, **kwargs)` -> str. Helpers nested inside main,
#     called only from main, taking everything as params (no closures over main's locals).
#   - MODULE-LEVEL NAMES ARE INVISIBLE INSIDE main (exec uses separate globals/locals). So all
#     constants live INSIDE main; only `import` stays outside. Injected globals (http, datetime,
#     get_participant_data, set_temp_state_key) ARE visible inside main.
#   - no module-level executable attribute access; no names starting with "_"; no next()/open();
#     no tuple-unpack assignment (a, b = ...).
#   - http.get(url, params=, headers=, auth=, timeout=) -> {"json","status_code","is_success"};
#     `auth=` is the (case-insensitive) NAME of an OCS Bearer AuthProvider holding the PAT.
#   - limits: 10 http calls per run (= 5 repos x 2 calls), 30s max timeout, 5MB response.
#
# Linters can't see the runtime-injected globals, so silence "undefined name":
# ruff: noqa: F821
# pyright: reportUndefinedVariable=false
import datetime  # main actually uses the injected `datetime` global; this is for linters/validate


def main(input, **kwargs):
    # EDIT THESE for your setup (must live inside main — module-level names aren't visible here):
    auth_provider = "github-vibe-check"
    max_repos = 5
    accept = {"Accept": "application/vnd.github+json"}

    # Contexts are pure participant data, managed conversationally by the Mirror node
    # ("add a context X for owner/repo", "list contexts"). This node only reads + resolves them.
    sast = datetime.timezone(datetime.timedelta(hours=2))  # South Africa, no DST

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
              "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}

    def parse_period(message, month_map):
        # Return an explicit period token from the message, or None if it names none.
        low = (message or "").lower()
        for name in month_map:
            if name in low:
                return name
        if "yesterday" in low:
            return "yesterday"
        if "last week" in low:
            return "last week"
        if "this week" in low:
            return "this week"
        return None

    def window_from_period(period, now, tz, month_map):
        if period in month_map:
            num = month_map[period]
            year = now.year if datetime.datetime(now.year, num, 1, tzinfo=tz) <= now else now.year - 1
            start = datetime.datetime(year, num, 1, tzinfo=tz)
            if num == 12:
                end = datetime.datetime(year + 1, 1, 1, tzinfo=tz)
            else:
                end = datetime.datetime(year, num + 1, 1, tzinfo=tz)
            return {"mode": f"{period} {year}", "since": start, "until": end}
        if period == "yesterday":
            day = (now - datetime.timedelta(days=1)).date()
            start = datetime.datetime(day.year, day.month, day.day, tzinfo=tz)
            return {"mode": "yesterday", "since": start, "until": start + datetime.timedelta(days=1)}
        if period == "last week":
            monday = (now - datetime.timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0)
            return {"mode": "last week", "since": monday - datetime.timedelta(days=7), "until": monday}
        start = (now - datetime.timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return {"mode": "this week", "since": start, "until": now}

    def resolve_context(message, contexts, stored_active):
        # Explicit mention in the message wins (token match, so "docs" != "ocs"); else sticky.
        words = (message or "").lower().replace("-", " ").replace(",", " ").split()
        for ctx in contexts:
            slug = (ctx.get("slug") or "").lower()
            name = (ctx.get("name") or "").lower()
            keys = [slug, name]
            for w in (slug + " " + name).replace("-", " ").split():
                if len(w) > 2 and w not in keys:
                    keys.append(w)
            for k in keys:
                if k and k in words:
                    return {"ctx": ctx, "matched": True}
        for ctx in contexts:
            if ctx.get("slug") == stored_active:
                return {"ctx": ctx, "matched": False}
        return {"ctx": contexts[0], "matched": False}

    def repo_lines(repo, author, since_iso, until_iso, since_date, until_date, auth, hdr):
        commits = http.get(
            f"https://api.github.com/repos/{repo}/commits",
            params={"author": author, "since": since_iso, "until": until_iso, "per_page": 100},
            headers=hdr, auth=auth, timeout=15)
        if commits["status_code"] == 404:
            # Repo not visible to this token (private + not in PAT scope, or wrong path).
            # Skip it and note it rather than halting the whole check.
            return {"skip": f"Repo: {repo}\n  (skipped — HTTP 404; private/not in token scope, or wrong path)"}
        if not commits["is_success"]:
            return {"error": f"FETCH_ERROR: commits for {repo} -> HTTP {commits['status_code']}. Halting."}
        # REST /issues (direct public read like commits) instead of /search/issues, which
        # 422s when a fine-grained PAT isn't scoped to the repo named in a `repo:` qualifier.
        # /issues returns PRs + issues by creator; `since` filters on updated, so we also
        # date-filter on created in code to match the window.
        issues = http.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"creator": author, "state": "all", "since": since_iso, "per_page": 100},
            headers=hdr, auth=auth, timeout=15)
        issues_items = []
        if issues["is_success"]:
            issues_items = issues["json"] or []
        elif issues["status_code"] not in (404, 410):
            # 404/410 = issues disabled (e.g. a fork) -> treat as no issues, don't halt.
            return {"error": f"FETCH_ERROR: issues for {repo} -> HTTP {issues['status_code']}. Halting."}

        out = [f"Repo: {repo}"]
        for c in (commits["json"] or []):
            commit = c.get("commit", {})
            msg = commit.get("message", "") or ""
            first = msg.splitlines()[0][:140] if msg else ""
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

    participant_data = get_participant_data() or {}
    contexts = participant_data.get("contexts", [])
    available = ", ".join([c.get("slug", "") for c in contexts]) or "(none yet)"
    if not contexts:
        return (f"BARRY'S MESSAGE: {input or ''}\n\nAVAILABLE CONTEXTS: (none yet)\n"
                "NO_CONTEXTS: Barry has no contexts configured. If his message asks to add one, "
                "handle it; otherwise offer to add one, e.g. "
                "'add a context ocs for dimagi/open-chat-studio'.")
    resolved = resolve_context(input, contexts, participant_data.get("active_context"))
    context = resolved["ctx"]
    if resolved["matched"] and context.get("slug") != participant_data.get("active_context"):
        set_participant_data_key("active_context", context.get("slug"))  # remember the switch

    gh = context.get("github", {})
    repos = gh.get("repos", [])
    author = gh.get("author_handle", "")

    # Resolve the period, persisting it across the multi-turn intent exchange: if this turn
    # names a period use + remember it; otherwise reuse the last one (so the intent answer,
    # which won't repeat "May", reflects the same window as the check-in).
    period = parse_period(input, months)
    if period:
        set_session_state_key("period", period)
    else:
        period = get_session_state_key("period") or "this week"
    win = window_from_period(period, datetime.datetime.now(sast), sast, months)
    since_iso = to_iso(win["since"])
    until_iso = to_iso(win["until"])
    since_date = win["since"].date().isoformat()
    until_date = win["until"].date().isoformat()

    lines = []
    for repo in repos[:max_repos]:
        result = repo_lines(repo, author, since_iso, until_iso, since_date, until_date, auth_provider, accept)
        if "error" in result:
            return result["error"]
        if "skip" in result:
            lines.append(result["skip"])
            continue
        lines.extend(result["lines"])

    set_temp_state_key("signals", {"context": context.get("slug", ""), "period": win["mode"]})

    intent = participant_data.get("current_intent") or {}
    intent_text = intent.get("stated") or "(none on record - ask Barry)"
    slug = context.get("slug", "")
    header = f"SIGNALS for context '{slug}', period: {win['mode']} ({since_date} to {until_date})"

    note = ""
    dropped = repos[max_repos:]
    if dropped:
        note = f"\n(NOTE: {len(dropped)} repo(s) not fetched this run due to the call budget: {', '.join(dropped)})"

    body = "\n".join(lines) if lines else "(no repos)"
    return (f"BARRY'S MESSAGE: {input or ''}\n\nAVAILABLE CONTEXTS: {available}\n"
            f"STATED INTENT: {intent_text}\n{header}\n\n{body}{note}")
