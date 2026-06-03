# Vibe Check — Resolve-HB (heartbeat front-router, OCS Code node)
# Node: Resolve-HB  (first node after Start)
# Grammar: addressing the bot IS the request; words only SCOPE it.
#   no scope                 -> OPEN  (gap-aware salute: yesterday, or since your last check-in)
#   "this week" / "weekly"   -> OPEN  (weekly salute over all contexts)
#   other period / a context -> SPINE (on-demand Mirror reflection on that scope)
#   add/list context         -> SPINE (resolve.py handles context admin)
#   reply while awaiting      -> REPLY (confirm / edit / day off)
# Injected globals: get_participant_data, get_session_state_key, set_session_state_key,
#                    set_temp_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(sast)
    today_iso = now.date().isoformat()
    msg = input or ""
    low = msg.lower().strip()

    months = ["january", "february", "march", "april", "may", "june", "july",
              "august", "september", "october", "november", "december"]

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    pdata = get_participant_data() or {}
    contexts = pdata.get("contexts", [])
    available = ", ".join([c.get("slug", "") for c in contexts]) or "(none yet)"
    set_temp_state_key("vc_message", msg)
    set_temp_state_key("vc_available", available)

    has_period = ("yesterday" in low) or ("last week" in low) or ("this week" in low)
    words = low.replace(",", " ").replace(".", " ").split()
    ambiguous_months = ("may", "march")  # also everyday English words
    month_lead = ("in", "during", "for", "since", "over", "back")
    for i, w in enumerate(words):
        if w in months:
            if w in ambiguous_months and len(words) > 1:
                prev = words[i - 1] if i > 0 else ""
                nxt = words[i + 1] if i + 1 < len(words) else ""
                if not ((nxt.isdigit() and len(nxt) == 4) or prev in month_lead):
                    continue
            has_period = True
    has_context = False
    for c in contexts:
        slug = (c.get("slug") or "").lower()
        cname = (c.get("name") or "").lower()
        if slug in ("vibe-check", "vibe check") or cname in ("vibe check", "vibe-check"):
            continue
        if (slug and slug in low) or (cname and cname in low):
            has_context = True

    is_manage = ("add a context" in low) or ("list context" in low) or low in ("contexts", "what contexts")
    is_scoped = has_period or has_context or is_manage
    is_weekly = (("this week" in low) or ("weekly" in low) or low == "week") and not has_context

    awaiting = get_session_state_key("vc_hb_awaiting")

    # reply to a pending draft (unless it's a fresh scoped/manage command)
    if awaiting and not is_scoped:
        pending = get_session_state_key("vc_hb_pending_text") or ""
        set_temp_state_key("vc_hb_route", "reply")
        return f"REPLY_MESSAGE: {msg}\n\nPENDING_DRAFT: {pending}"

    # Continuation: an on-demand reflection is live (same session + day) -> keep follow-ups on
    # the spine, even ones with no period/context word, instead of re-routing them to a salute.
    # A new explicit period or a manage command breaks out; a new day lets the lock go stale.
    convo_scope = get_session_state_key("vc_convo_scope") or ""
    convo_fresh = (get_session_state_key("vc_convo_date") or "") == today_iso
    if convo_scope and convo_fresh and not has_period and not is_manage:
        set_temp_state_key("vc_hb_route", "spine")
        return msg

    # OPEN window: weekly, or gap-aware daily (yesterday, widened across a break)
    open_mode = ""
    if is_weekly:
        open_mode = "weekly"
    elif not is_scoped:
        open_mode = "daily"

    if open_mode and contexts:
        if open_mode == "weekly":
            start = (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
            since_date = start.date().isoformat()
            until_date = now.date().isoformat()
            label = "this week"
        else:
            yest = (now - datetime.timedelta(days=1)).date()
            last = pdata.get("last_heartbeat_date") or ""
            piece = last.split("-")
            last_date = datetime.date(int(piece[0]), int(piece[1]), int(piece[2])) if len(piece) == 3 else None
            gap = (now.date() - last_date).days if last_date else 1
            if last_date and gap > 1:
                start = datetime.datetime(last_date.year, last_date.month, last_date.day, tzinfo=sast)
                end = now
                since_date = last_date.isoformat()
                until_date = now.date().isoformat()
                label = f"since your last check-in on {last_date.isoformat()} ({gap} days)"
            else:
                start = datetime.datetime(yest.year, yest.month, yest.day, tzinfo=sast)
                end = start + datetime.timedelta(days=1)
                since_date = yest.isoformat()
                until_date = yest.isoformat()
                label = "yesterday"
        repos = []
        author = ""
        for c in contexts:
            gh = c.get("github", {})
            if not author:
                author = gh.get("author_handle", "")
            for r in gh.get("repos", []):
                if r not in repos:
                    repos.append(r)
        set_temp_state_key("vc_mode", "checkin")
        set_temp_state_key("vc_repos", repos[:5])
        set_temp_state_key("vc_author", author)
        set_temp_state_key("vc_since_iso", to_iso(start))
        set_temp_state_key("vc_until_iso", to_iso(end))
        set_temp_state_key("vc_since_date", since_date)
        set_temp_state_key("vc_until_date", until_date)
        set_temp_state_key("vc_slug", "all")
        set_temp_state_key("vc_period_label", label)
        set_temp_state_key("vc_intent", "(heartbeat - no reflection)")
        set_session_state_key("vc_convo_scope", "")  # a salute supersedes any live reflection
        set_temp_state_key("vc_hb_route", "open")
        return msg

    # scoped (other period/context) or context-admin, or no contexts -> the on-demand spine
    set_temp_state_key("vc_hb_route", "spine")
    return msg
