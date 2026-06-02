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

    def resolve_ctx(text, contexts, stored_active):
        words = text.replace("-", " ").replace(",", " ").split()
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

    def parse_add(text):
        # "add a context <name> [for|with|tracking|repo] <owner/repo or github URL>[, ...]"
        lower = text.lower()
        if "add" not in lower or "context" not in lower:
            return None
        after = text[lower.index("context") + 7:]
        repos = []
        pair = 2  # owner/repo
        for raw in after.replace(",", " ").replace(" and ", " ").split():
            tok = raw.strip().strip("<>").strip(".").strip()
            if "|" in tok:  # Slack formats links as <url|label>; keep the url
                tok = tok.split("|", 1)[0].strip("<>").strip()
            lt = tok.lower()
            if "github.com/" in lt:
                parts = tok.split("github.com/", 1)[1].strip("/").split("/")
                if len(parts) >= pair:
                    owner = parts[0].strip("<>")
                    repo = parts[1].replace(".git", "").strip("<>")
                    repos.append(owner + "/" + repo)
            elif tok.count("/") == 1 and "." not in tok.split("/")[0]:
                repos.append(tok.strip("<>"))
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

    resolved = resolve_ctx(low, contexts, pdata.get("active_context"))
    ctx = resolved["ctx"]
    slug = ctx.get("slug", "")
    if resolved["matched"] and slug != pdata.get("active_context"):
        set_participant_data_key("active_context", slug)

    explicit_period = parse_period(low)
    if explicit_period:
        set_session_state_key("vc_last_period", explicit_period)
        period = explicit_period
    else:
        period = get_session_state_key("vc_last_period") or "this week"
    win = window_for(period, sast)
    rec_key = f"{slug}|{win['key']}"

    records = pdata.get("records", {})
    intent_obj = records.get(rec_key, {}).get("intent")
    awaiting = get_session_state_key("vc_awaiting")
    is_command = ("vibe check" in low) or resolved["matched"] or (explicit_period is not None)

    # The intent state machine: a non-command turn while awaiting = the intent answer -> store it.
    if (not intent_obj) and awaiting == rec_key and not is_command:
        records[rec_key] = {"intent": {"stated": msg, "on_date": today_iso}}
        set_participant_data_key("records", records)
        set_session_state_key("vc_awaiting", "")
        intent_obj = records[rec_key]["intent"]

    set_temp_state_key("vc_slug", slug)
    set_temp_state_key("vc_period_label", win["label"])

    if not intent_obj:
        set_session_state_key("vc_awaiting", rec_key)
        set_temp_state_key("vc_mode", "ask_intent")
        return "ask_intent"

    gh = ctx.get("github", {})
    set_temp_state_key("vc_mode", "checkin")
    set_temp_state_key("vc_repos", gh.get("repos", []))
    set_temp_state_key("vc_author", gh.get("author_handle", ""))
    set_temp_state_key("vc_intent", intent_obj.get("stated", ""))
    set_temp_state_key("vc_since_iso", to_iso(win["since"]))
    set_temp_state_key("vc_until_iso", to_iso(win["until"]))
    set_temp_state_key("vc_since_date", win["since"].date().isoformat())
    set_temp_state_key("vc_until_date", win["until"].date().isoformat())
    return "checkin"
