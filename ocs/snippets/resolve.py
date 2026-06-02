# Vibe Check — Resolve / State (OCS Code node)
#
# Runs FIRST in the V1.5 pipeline:  Start -> [Resolve] -> Fetch -> Mirror -> End.
# Deterministic. Classifies the message, resolves context + period, runs the intent
# state machine, and handles context add/list. Writes the resolved request to TEMP state
# for the Fetch + Mirror nodes. Persists contexts/active/intent in PARTICIPANT data;
# the last period + the "awaiting intent" flag in SESSION state.
#
# OCS Code-node rules: one top-level `main`; helpers nested; no leading-underscore names;
# no next()/open(); no tuple-unpack assignment; constants inside main. Injected globals:
# get_participant_data, set_participant_data_key, append_to_participant_data_key,
# get_session_state_key, set_session_state_key, set_temp_state_key, datetime.
#
# ruff: noqa: F821
# pyright: reportUndefinedVariable=false
import datetime


def main(input, **kwargs):
    author_handle = "barry47products"  # default author for newly-added contexts
    months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
              "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    sast = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(sast)
    today_iso = now.date().isoformat()
    msg = input or ""
    low = msg.lower()

    def two(n):
        return ("0" + str(n))[-2:]

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    yesterday_kw = "yesterday"
    last_week_kw = "last week"
    this_week_kw = "this week"

    def parse_period(text):
        for name in months:
            if name in text:
                return name
        if yesterday_kw in text:
            return yesterday_kw
        if last_week_kw in text:
            return last_week_kw
        if this_week_kw in text:
            return this_week_kw
        return None

    def window_for(period, tz):
        if period in months:
            num = months[period]
            year = now.year if datetime.datetime(now.year, num, 1, tzinfo=tz) <= now else now.year - 1
            start = datetime.datetime(year, num, 1, tzinfo=tz)
            end = datetime.datetime(year + 1, 1, 1, tzinfo=tz) if num == 12 else datetime.datetime(year, num + 1, 1, tzinfo=tz)
            return {"label": f"{period} {year}", "key": f"m-{year}-{two(num)}", "since": start, "until": end}
        if period == yesterday_kw:
            day = (now - datetime.timedelta(days=1)).date()
            start = datetime.datetime(day.year, day.month, day.day, tzinfo=tz)
            return {"label": yesterday_kw, "key": f"d-{day.isoformat()}", "since": start, "until": start + datetime.timedelta(days=1)}
        monday = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        if period == last_week_kw:
            since = monday - datetime.timedelta(days=7)
            return {"label": last_week_kw, "key": f"w-{since.date().isoformat()}", "since": since, "until": monday}
        return {"label": this_week_kw, "key": f"w-{monday.date().isoformat()}", "since": monday, "until": now}

    def contexts_in(text, contexts):
        # Every context whose slug/name/word-token appears in the text (token match, so
        # "docs" != "ocs"). Returns all matches in context order — the scope of a check-in.
        words = text.replace("-", " ").replace(",", " ").split()
        found = []
        for ctx in contexts:
            slug = (ctx.get("slug") or "").lower()
            name = (ctx.get("name") or "").lower()
            keys = [slug, name]
            for w in (slug + " " + name).replace("-", " ").split():
                if len(w) > 2 and w not in keys:
                    keys.append(w)
            hit = False
            for k in keys:
                if k and k in words:
                    hit = True
            if hit:
                found.append(ctx)
        return found

    def active_or_first(contexts, active):
        for ctx in contexts:
            if ctx.get("slug") == active:
                return ctx
        return contexts[0]

    def union_repos(scope):
        repos = []
        for ctx in scope:
            for r in ctx.get("github", {}).get("repos", []):
                if r not in repos:
                    repos.append(r)
        return repos

    def scope_author(scope):
        for ctx in scope:
            handle = ctx.get("github", {}).get("author_handle", "")
            if handle:
                return handle
        return author_handle

    def scope_key(scope, win):
        slugs = sorted([c.get("slug", "") for c in scope])
        return win["key"] + "::" + "+".join(slugs)

    def scope_label(scope):
        return ", ".join([c.get("slug", "") for c in scope])

    def parse_add(text):
        # "add a context <name> [for|with|tracking|repo] <owner/repo or github URL>[, ...]"
        lower = text.lower()
        if "add" not in lower or "context" not in lower:
            return None
        after = text[lower.index("context") + 7:]
        repos = []
        pair = 2  # owner/repo
        junk = "<>`'\" "  # Slack/markdown wrappers: angle brackets, backticks, quotes, spaces
        for raw in after.replace(",", " ").replace(" and ", " ").split():
            tok = raw.strip(junk).strip(".").strip(junk)
            if "|" in tok:  # Slack formats links as <url|label>; keep the url
                tok = tok.split("|", 1)[0].strip(junk)
            lt = tok.lower()
            if "github.com/" in lt:
                parts = tok.split("github.com/", 1)[1].strip("/").split("/")
                if len(parts) >= pair:
                    owner = parts[0].strip(junk)
                    repo = parts[1].replace(".git", "").strip(junk)
                    repos.append(owner + "/" + repo)
            elif tok.count("/") == 1 and "." not in tok.split("/")[0]:
                repos.append(tok.strip(junk))
        if not repos:
            return None
        # name = text after 'context' up to the first connector word / repo / URL
        name_part = after
        for sep in (" for ", " with ", " tracking ", " repo ", " repos ", "github.com", "http"):
            pos = name_part.lower().find(sep)
            if pos != -1:
                name_part = name_part[:pos]
        name = name_part.strip().strip(":").strip()
        if not name:
            return None
        return {"name": name, "slug": name.lower().replace(" ", "-"), "repos": repos}

    pdata = get_participant_data() or {}
    contexts = pdata.get("contexts", [])
    available = ", ".join([c.get("slug", "") for c in contexts]) or "(none yet)"
    set_temp_state_key("vc_message", msg)
    set_temp_state_key("vc_available", available)

    # --- MANAGE: list ---
    if "list context" in low or low.strip() in ("contexts", "list contexts", "what contexts", "what contexts do i have"):
        set_temp_state_key("vc_mode", "manage")
        set_temp_state_key("vc_reply", f"Contexts: {available}" if contexts else
                           "No contexts yet — add one, e.g. 'add a context ocs for dimagi/open-chat-studio'.")
        return "manage"

    # --- MANAGE: add ---
    add = parse_add(msg)
    if add:
        if any(c.get("slug") == add["slug"] for c in contexts):
            set_temp_state_key("vc_reply", f"Context '{add['slug']}' already exists.")
        else:
            append_to_participant_data_key("contexts", {"slug": add["slug"], "name": add["name"],
                                                        "github": {"repos": add["repos"], "author_handle": author_handle}})
            set_participant_data_key("active_context", add["slug"])
            set_temp_state_key("vc_reply", f"Added context '{add['slug']}' tracking {', '.join(add['repos'])}, and switched to it.")
        set_temp_state_key("vc_mode", "manage")
        return "manage"

    # --- CHECK-IN ---
    if not contexts:
        set_temp_state_key("vc_mode", "no_context")
        return "no_context"

    explicit_period = parse_period(low)
    awaiting = get_session_state_key("vc_awaiting") or ""
    awaiting_scope = get_session_state_key("vc_awaiting_scope") or ""
    awaiting_period = get_session_state_key("vc_awaiting_period") or ""
    records = pdata.get("records", {})

    # A non-redirecting turn while we're awaiting an intent answer = the answer itself.
    # An explicit period in the turn means Barry is starting a fresh check-in instead.
    answering = bool(awaiting) and (explicit_period is None)

    # --- Period ---
    if answering:
        period = awaiting_period or this_week_kw
    elif explicit_period:
        set_session_state_key("vc_last_period", explicit_period)
        period = explicit_period
    else:
        period = get_session_state_key("vc_last_period") or this_week_kw
    win = window_for(period, sast)

    # --- Scope (one or more contexts) ---
    # The scope is whatever Barry NAMES — in the check-in, or in his intent answer. We never
    # pin a context he didn't choose: bare "last week" asks generically, and the answer (which
    # names contexts) becomes the scope. Reflection then spans every context in scope.
    named_here = contexts_in(low, contexts)
    if answering:
        if named_here:
            scope = named_here
        elif awaiting_scope:
            scope = [c for c in contexts if c.get("slug") in awaiting_scope.split(",")]
        else:
            scope = [active_or_first(contexts, pdata.get("active_context"))]
    elif named_here:
        scope = named_here
        if len(named_here) == 1 and named_here[0].get("slug") != pdata.get("active_context"):
            set_participant_data_key("active_context", named_here[0].get("slug"))
    else:
        scope = []  # undecided — ask intent generically; the answer will pick scope

    set_temp_state_key("vc_slug", scope_label(scope))  # "" while scope is undecided
    set_temp_state_key("vc_period_label", win["label"])

    # --- Intent (stored per period + scope) ---
    if answering:
        rec_key = scope_key(scope, win)
        records[rec_key] = {"intent": {"stated": msg, "on_date": today_iso}}
        set_participant_data_key("records", records)
        set_session_state_key("vc_awaiting", "")
        set_session_state_key("vc_awaiting_scope", "")
        intent_obj = records[rec_key]["intent"]
    elif scope:
        intent_obj = records.get(scope_key(scope, win), {}).get("intent")
    else:
        intent_obj = None

    if not intent_obj:
        set_session_state_key("vc_awaiting", "1")
        set_session_state_key("vc_awaiting_scope", ",".join([c.get("slug", "") for c in scope]))
        set_session_state_key("vc_awaiting_period", period)
        set_temp_state_key("vc_mode", "ask_intent")
        return "ask_intent"

    set_temp_state_key("vc_mode", "checkin")
    set_temp_state_key("vc_repos", union_repos(scope))
    set_temp_state_key("vc_author", scope_author(scope))
    set_temp_state_key("vc_intent", intent_obj.get("stated", ""))
    set_temp_state_key("vc_since_iso", to_iso(win["since"]))
    set_temp_state_key("vc_until_iso", to_iso(win["until"]))
    set_temp_state_key("vc_since_date", win["since"].date().isoformat())
    set_temp_state_key("vc_until_date", win["until"].date().isoformat())
    return "checkin"
