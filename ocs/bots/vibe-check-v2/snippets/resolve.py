# Vibe Check v2 — Resolve (OCS Code node). Start -> [Resolve] -> Fetch -> Draft -> End.
# Deterministic: period + scope for this turn; context admin; writes TEMP state for Fetch.
# Period precedence: explicit > sticky (same-day stored window) > gap-aware default.
# Scope precedence: named contexts > sticky (same day) > all contexts.
# OCS sandbox: one main; helpers nested; constants inside main; no enumerate/zip/map/next/open.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    author_handle = "barry47products"
    sast = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(sast)
    today_iso = now.date().isoformat()
    msg = input or ""
    low = msg.lower().strip()

    months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
              "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    yesterday_kw = "yesterday"
    last_week_kw = "last week"
    this_week_kw = "this week"
    ambiguous_months = ("may", "march")
    month_lead = ("in", "during", "for", "since", "over", "back")
    number_words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "a": 1,
                    "couple": 2, "few": 3, "several": 4}
    span_units = ("day", "days", "week", "weeks")

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def parse_period(text):
        if yesterday_kw in text:
            return yesterday_kw
        if last_week_kw in text:
            return last_week_kw
        if this_week_kw in text:
            return this_week_kw
        if "fortnight" in text:
            return "days:14"
        toks = text.replace("-", " ").replace(",", " ").replace(".", " ").split()
        j = 0
        for t in toks:
            if t in span_units:
                prev = toks[j - 1] if j > 0 else ""
                n = int(prev) if prev.isdigit() else number_words.get(prev, 0)
                if n > 0:
                    mult = 7 if t[0] == "w" else 1
                    return "days:" + str(n * mult)
            j = j + 1
        words = text.replace(",", " ").replace(".", " ").split()
        i = 0
        for w in words:
            if w in months:
                ok = True
                if w in ambiguous_months and len(words) > 1:
                    prev = words[i - 1] if i > 0 else ""
                    nxt = words[i + 1] if i + 1 < len(words) else ""
                    ok = (nxt.isdigit() and len(nxt) == 4) or (prev in month_lead)
                if ok:
                    return w
            i = i + 1
        return None

    def window_for(period, tz, last_date):
        if period.startswith("days:"):
            n = int(period[5:])
            since = now - datetime.timedelta(days=n)
            if n % 7 == 0:
                wks = n // 7
                lbl = "the last " + str(wks) + (" week" if wks == 1 else " weeks")
            else:
                lbl = "the last " + str(n) + (" day" if n == 1 else " days")
            return {"label": lbl, "since": since, "until": now}
        if period in months:
            num = months[period]
            year = now.year if datetime.datetime(now.year, num, 1, tzinfo=tz) <= now else now.year - 1
            start = datetime.datetime(year, num, 1, tzinfo=tz)
            end = datetime.datetime(year + 1, 1, 1, tzinfo=tz) if num == 12 else datetime.datetime(year, num + 1, 1, tzinfo=tz)
            return {"label": period + " " + str(year), "since": start, "until": end}
        if period == yesterday_kw:
            day = (now - datetime.timedelta(days=1)).date()
            start = datetime.datetime(day.year, day.month, day.day, tzinfo=tz)
            return {"label": yesterday_kw, "since": start, "until": start + datetime.timedelta(days=1)}
        monday = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        if period == last_week_kw:
            since = monday - datetime.timedelta(days=7)
            return {"label": last_week_kw, "since": since, "until": monday}
        if period == this_week_kw:
            return {"label": this_week_kw, "since": monday, "until": now}
        # gap-aware "auto"
        piece = (last_date or "").split("-")
        ld = datetime.date(int(piece[0]), int(piece[1]), int(piece[2])) if len(piece) == 3 else None
        if not ld:
            return {"label": "the last week", "since": now - datetime.timedelta(days=7), "until": now}
        gap = (now.date() - ld).days
        if gap <= 1:
            day = (now - datetime.timedelta(days=1)).date()
            start = datetime.datetime(day.year, day.month, day.day, tzinfo=tz)
            return {"label": yesterday_kw, "since": start, "until": start + datetime.timedelta(days=1)}
        start = datetime.datetime(ld.year, ld.month, ld.day, tzinfo=tz)
        return {"label": "since your last vibe on " + ld.isoformat() + " (" + str(gap) + " days)", "since": start, "until": now}

    def contexts_in(text, contexts):
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

    def union_repos(scope):
        repos = []
        for ctx in scope:
            for r in ctx.get("github", {}).get("repos", []):
                if r not in repos:
                    repos.append(r)
        return repos

    def scope_author(scope, fallback):
        for ctx in scope:
            handle = ctx.get("github", {}).get("author_handle", "")
            if handle:
                return handle
        return fallback

    def parse_add(text):
        lower = text.lower()
        if "add" not in lower or "context" not in lower:
            return None
        after = text[lower.index("context") + 7:]
        repos = []
        pair = 2
        junk = "<>`'\" "
        for raw in after.replace(",", " ").replace(" and ", " ").split():
            tok = raw.strip(junk).strip(".").strip(junk)
            if "|" in tok:
                tok = tok.split("|", 1)[0].strip(junk)
            lt = tok.lower()
            if "github.com/" in lt:
                parts = tok.split("github.com/", 1)[1].strip("/").split("/")
                if len(parts) >= pair:
                    repos.append(parts[0].strip(junk) + "/" + parts[1].replace(".git", "").strip(junk))
            elif tok.count("/") == 1 and "." not in tok.split("/")[0]:
                repos.append(tok.strip(junk))
        if not repos:
            return None
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

    if "list context" in low or low in ("contexts", "list contexts", "what contexts", "what contexts do i have"):
        set_temp_state_key("vc_mode", "manage")
        set_temp_state_key("vc_reply", ("Contexts: " + available) if contexts else
                           "No contexts yet — add one, e.g. 'add a context ocs for dimagi/open-chat-studio'.")
        return "manage"

    add = parse_add(msg)
    if add:
        if any(c.get("slug") == add["slug"] for c in contexts):
            set_temp_state_key("vc_reply", "Context '" + add["slug"] + "' already exists.")
        else:
            append_to_participant_data_key("contexts", {"slug": add["slug"], "name": add["name"],
                                                        "github": {"repos": add["repos"], "author_handle": author_handle}})
            set_temp_state_key("vc_reply", "Added context '" + add["slug"] + "' tracking " + ", ".join(add["repos"]) + ".")
        set_temp_state_key("vc_mode", "manage")
        return "manage"

    explicit_period = parse_period(low)
    win_fresh = (get_session_state_key("vc_win_date") or "") == today_iso
    if (not explicit_period) and win_fresh:
        since_iso = get_session_state_key("vc_win_since_iso")
        until_iso = get_session_state_key("vc_win_until_iso")
        since_date = get_session_state_key("vc_win_since_date")
        until_date = get_session_state_key("vc_win_until_date")
        label = get_session_state_key("vc_win_label")
    else:
        if explicit_period:
            set_session_state_key("vc_last_period", explicit_period)
        win = window_for(explicit_period or "auto", sast, pdata.get("last_vibe_date"))
        since_iso = to_iso(win["since"])
        until_iso = to_iso(win["until"])
        since_date = win["since"].date().isoformat()
        until_date = win["until"].date().isoformat()
        label = win["label"]
        set_session_state_key("vc_win_since_iso", since_iso)
        set_session_state_key("vc_win_until_iso", until_iso)
        set_session_state_key("vc_win_since_date", since_date)
        set_session_state_key("vc_win_until_date", until_date)
        set_session_state_key("vc_win_label", label)
        set_session_state_key("vc_win_date", today_iso)

    if not contexts:
        # No contexts configured -> Fetch auto-discovers recently-pushed repos via the PAT.
        set_temp_state_key("vc_discover", "1")
        repos_out = []
        author_out = author_handle
        slug_label = "your recent work"
    else:
        set_temp_state_key("vc_discover", "")
        named = contexts_in(low, contexts)
        if named:
            scope = named
            set_session_state_key("vc_last_scope", ",".join([c.get("slug", "") for c in named]))
        elif win_fresh:
            last_scope = get_session_state_key("vc_last_scope") or ""
            scope = [c for c in contexts if c.get("slug") in last_scope.split(",")] if last_scope else contexts
        else:
            scope = contexts
            set_session_state_key("vc_last_scope", "")
        if not scope:
            scope = contexts
        repos_out = union_repos(scope)
        author_out = scope_author(scope, author_handle)
        slug_label = ", ".join([c.get("slug", "") for c in scope])

    set_participant_data_key("last_vibe_date", today_iso)
    set_temp_state_key("vc_mode", "checkin")
    set_temp_state_key("vc_repos", repos_out)
    set_temp_state_key("vc_author", author_out)
    set_temp_state_key("vc_slug", slug_label)
    set_temp_state_key("vc_period_label", label)
    set_temp_state_key("vc_since_iso", since_iso)
    set_temp_state_key("vc_until_iso", until_iso)
    set_temp_state_key("vc_since_date", since_date)
    set_temp_state_key("vc_until_date", until_date)
    return "checkin"
