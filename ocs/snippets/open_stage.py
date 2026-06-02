# Vibe Check — Open · Stage (OCS Code node). OPEN path, after Open · Draft.
# Saves the draft to SESSION state (the handshake) and invites Barry to shape it.
# Injected globals: get_temp_state_key, set_session_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    today = datetime.datetime.now(sast).date().isoformat()
    draft = (input or "").strip()
    period = get_temp_state_key("vc_period_label") or "yesterday"
    set_session_state_key("vc_hb_awaiting", today)
    set_session_state_key("vc_hb_pending_date", today)
    set_session_state_key("vc_hb_pending_text", draft)
    return ("Here's what your activity shows for " + period + " — a starting point, not a finished post:\n\n"
            + draft +
            "\n\nWhat would you add or change? Reply with anything I missed, *yep* to post as-is, "
            "or *day off* to skip.")
