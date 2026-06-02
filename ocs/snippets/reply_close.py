# Vibe Check — Reply · Close (OCS Code node). REPLY path, after Reply · Interpret.
# Reads the verdict, clears the handshake, stages the post text, records engagement.
# Injected globals: get_session_state_key, set_session_state_key, set_participant_data_key,
#                   set_temp_state_key, datetime.
# ruff: noqa: F821
import datetime


def main(input, **kwargs):
    sast = datetime.timezone(datetime.timedelta(hours=2))
    today = datetime.datetime.now(sast).date().isoformat()
    verdict = (input or "").strip()
    pending = get_session_state_key("vc_hb_pending_text") or ""

    set_session_state_key("vc_hb_awaiting", "")
    set_session_state_key("vc_hb_pending_text", "")
    set_session_state_key("vc_hb_pending_date", "")
    set_participant_data_key("last_heartbeat_date", today)

    upper = verdict.upper()
    post_text = pending
    if upper.startswith("DAYOFF"):
        post_text = ""
    elif upper.startswith("EDIT:"):
        post_text = verdict.split(":", 1)[1].strip()
    set_temp_state_key("vc_hb_post_text", post_text)
    return "ok"
