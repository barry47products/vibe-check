# Vibe Check — Reply · Post (OCS Code node). REPLY path, after Reply · Close.
# Posts the approved salute to the team channel via Slack chat.postMessage.
# Injected globals: get_temp_state_key, http.
# ruff: noqa: F821
def main(input, **kwargs):
    channel = "C0B6S0T2NES"          # team channel id
    auth_provider = "slack-vibe-check"
    text = get_temp_state_key("vc_hb_post_text") or ""
    if not text.strip():
        return "Noted — enjoy the day off. Nothing posted. 🌴"
    resp = http.post("https://slack.com/api/chat.postMessage",
                     json={"channel": channel, "text": text},
                     auth=auth_provider, timeout=15)
    if not resp["is_success"]:
        return f"Couldn't reach Slack (HTTP {resp['status_code']}). Try again shortly."
    body = resp["json"] or {}
    if not body.get("ok"):
        return f"Slack rejected the post ({body.get('error', 'unknown')})."
    return "Posted to the team channel. 🫡"
