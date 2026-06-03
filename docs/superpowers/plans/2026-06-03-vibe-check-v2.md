# Vibe Check v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a private, draft-first "vibe" bot as a brand-new OCS experiment — a linear `Start → Resolve → Fetch → Draft → End` pipeline that gathers GitHub signals for a gap-aware window and hands Barry a grouped summary he shapes in chat.

**Architecture:** Two OCS Code nodes (Resolve, Fetch) + one LLM node (Draft). Resolve is deterministic (period/scope/admin); Fetch is pure GitHub I/O; Draft writes/revises the vibe. The node *logic* is tested locally via a harness that execs each snippet with stubbed injected globals and a frozen clock. v1 stays deployed and untouched.

**Tech Stack:** Python 3.13 (OCS RestrictedPython code nodes), pytest (local logic tests only), OCS pipeline UI, GitHub REST API, Slack DM channel.

**Spec:** `docs/superpowers/specs/2026-06-03-vibe-check-v2-design.md`

---

## OCS sandbox rules (apply to every `.py` node)

- Exactly one top-level `def main(input, **kwargs)`. Helpers **nested inside** `main`. Constants inside `main`. Only `import` stays at module level.
- **No `enumerate`, `zip`, `map`, `next`, `open`** — not in the sandbox. Use a manual index (`i = 0 … i = i + 1`).
- No tuple-unpack assignment (`a, b = …`). No names starting with `_`.
- Injected globals are available inside `main`: `get_participant_data`, `set_participant_data_key`, `append_to_participant_data_key`, `get_session_state_key`, `set_session_state_key`, `get_temp_state_key`, `set_temp_state_key`, `http`, `datetime`.
- `http.get/post(url, params=, headers=, auth=, timeout=)` → `{"json", "status_code", "is_success"}`; `auth=` is the **name** of an OCS Bearer auth provider. Budget: 10 HTTP calls/run.

## File Structure

```
ocs/bots/vibe-check-v2/
  snippets/resolve.py        # period + scope + admin, writes temp state for Fetch
  snippets/fetch.py          # GitHub signals for the resolved window; RELAY passthrough
  prompts/draft.md           # the Draft LLM prompt
  prompts/nudge.md           # weekday morning ScheduledMessage prompt_text
  NODES.md                   # node → file map, pipeline graph, schedule + model notes
  tests/conftest.py          # load_node() harness: stubbed globals + frozen clock
  tests/test_resolve.py      # period/window/scope/stickiness/admin behaviour
  tests/test_fetch.py        # signal assembly + RELAY with a stubbed http
  tests/sandbox_scan.py      # scans snippets for sandbox-forbidden builtins
  pytest.ini                 # rootdir + testpaths
```

---

## Task 1: Test scaffold (harness + sandbox scanner)

**Files:**
- Create: `ocs/bots/vibe-check-v2/tests/conftest.py`
- Create: `ocs/bots/vibe-check-v2/tests/sandbox_scan.py`
- Create: `ocs/bots/vibe-check-v2/pytest.ini`

- [ ] **Step 1: Write the harness** — `tests/conftest.py`

```python
import datetime as _dt
import pathlib
import sys

SNIPPETS = pathlib.Path(__file__).resolve().parent.parent / "snippets"


def make_dt(frozen_now):
    # Stand-in for the injected `datetime` module with a frozen now().
    class FrozenDatetime(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now.astimezone(tz) if tz is not None else frozen_now

    class Shim:
        datetime = FrozenDatetime
        timedelta = _dt.timedelta
        timezone = _dt.timezone
        date = _dt.date

    return Shim


def load_node(name, participant=None, session=None, temp=None, http=None, frozen_now=None):
    """Exec an OCS code-node source with stubbed injected globals; return (main, pdata, sstate, tstate)."""
    pdata = dict(participant or {})
    sstate = dict(session or {})
    tstate = dict(temp or {})
    g = {
        "get_participant_data": lambda: pdata,
        "set_participant_data_key": lambda k, v: pdata.__setitem__(k, v),
        "append_to_participant_data_key": lambda k, v: pdata.setdefault(k, []).append(v),
        "get_session_state_key": lambda k: sstate.get(k),
        "set_session_state_key": lambda k, v: sstate.__setitem__(k, v),
        "get_temp_state_key": lambda k: tstate.get(k),
        "set_temp_state_key": lambda k, v: tstate.__setitem__(k, v),
        "http": http,
    }
    src = (SNIPPETS / name).read_text()
    saved = sys.modules.get("datetime")
    if frozen_now is not None:
        sys.modules["datetime"] = make_dt(frozen_now)
    try:
        exec(compile(src, str(SNIPPETS / name), "exec"), g)
    finally:
        if saved is not None:
            sys.modules["datetime"] = saved
        elif frozen_now is not None:
            del sys.modules["datetime"]
    return g["main"], pdata, sstate, tstate


def sast(y, m, d, hh=9, mm=0):
    return _dt.datetime(y, m, d, hh, mm, tzinfo=_dt.timezone(_dt.timedelta(hours=2)))
```

- [ ] **Step 2: Write the sandbox scanner** — `tests/sandbox_scan.py`

```python
import pathlib
import re
import sys

FORBIDDEN = ("enumerate", "zip", "map", "next", "open")
SNIPPETS = pathlib.Path(__file__).resolve().parent.parent / "snippets"


def scan(path):
    hits = []
    text = path.read_text()
    line_no = 0
    for line in text.splitlines():
        line_no = line_no + 1
        for name in FORBIDDEN:
            if re.search(r"(?<![\w.])" + name + r"\s*\(", line):
                hits.append((path.name, line_no, name, line.strip()))
    return hits


def main():
    all_hits = []
    for path in sorted(SNIPPETS.glob("*.py")):
        all_hits.extend(scan(path))
    for name, ln, builtin, line in all_hits:
        print(name + ":" + str(ln) + ": forbidden '" + builtin + "()' -> " + line)
    if all_hits:
        sys.exit(1)
    print("sandbox scan clean")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Verify pytest collects (no tests yet is fine)**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest -q`
Expected: "no tests ran" (exit 5) — confirms config + imports load.

- [ ] **Step 5: Commit**

```bash
git add ocs/bots/vibe-check-v2/tests ocs/bots/vibe-check-v2/pytest.ini
git commit -m "test(vibe-check-v2): node-exec harness + sandbox-builtin scanner"
```

---

## Task 2: Resolve — write the failing tests

**Files:**
- Create: `ocs/bots/vibe-check-v2/tests/test_resolve.py`

- [ ] **Step 1: Write the test suite**

```python
from conftest import load_node, sast

CTXS = [
    {"slug": "chatterbridge", "name": "chatterbridge", "github": {"repos": ["barry/chatterbridge"], "author_handle": "barry47products"}},
    {"slug": "ocs", "name": "ocs", "github": {"repos": ["dimagi/open-chat-studio"], "author_handle": "barry47products"}},
]
NOW = sast(2026, 6, 3, 8, 0)  # Wednesday


def resolve(msg, participant=None, session=None):
    main, pdata, sstate, tstate = load_node(
        "resolve.py",
        participant={"contexts": CTXS} if participant is None else participant,
        session=session, frozen_now=NOW)
    ret = main(msg)
    return ret, pdata, sstate, tstate


def test_first_ever_vibe_covers_last_7_days():
    ret, pdata, sstate, tstate = resolve("vibe check")  # no last_vibe_date
    assert ret == "checkin"
    assert tstate["vc_since_date"] == "2026-05-27"
    assert tstate["vc_until_date"] == "2026-06-03"
    assert pdata["last_vibe_date"] == "2026-06-03"


def test_gap_aware_yesterday_when_checked_in_recently():
    ret, pdata, sstate, tstate = resolve("vibe check", participant={"contexts": CTXS, "last_vibe_date": "2026-06-02"})
    assert tstate["vc_period_label"] == "yesterday"
    assert tstate["vc_since_date"] == "2026-06-02"


def test_gap_aware_widens_across_a_break():
    ret, pdata, sstate, tstate = resolve("vibe check", participant={"contexts": CTXS, "last_vibe_date": "2026-05-29"})
    assert "since your last vibe on 2026-05-29" in tstate["vc_period_label"]
    assert tstate["vc_since_date"] == "2026-05-29"


def test_explicit_last_week():
    ret, pdata, sstate, tstate = resolve("vibe check last week")
    assert tstate["vc_period_label"] == "last week"
    assert tstate["vc_since_date"] == "2026-05-25"  # Monday of previous week
    assert sstate["vc_last_period"] == "last week"


def test_may_the_verb_is_not_a_month():
    ret, pdata, sstate, tstate = resolve("there may have been other things i may have tackled")
    # falls through to gap-aware default, NOT month "may"
    assert "may 20" not in tstate["vc_period_label"].lower()


def test_may_the_month_when_dated():
    ret, pdata, sstate, tstate = resolve("vibe check in may")
    assert tstate["vc_period_label"] == "may 2026"


def test_scope_narrows_to_named_context():
    ret, pdata, sstate, tstate = resolve("vibe check ocs")
    assert tstate["vc_slug"] == "ocs"
    assert tstate["vc_repos"] == ["dimagi/open-chat-studio"]


def test_scope_defaults_to_all_contexts():
    ret, pdata, sstate, tstate = resolve("vibe check")
    assert tstate["vc_slug"] == "chatterbridge, ocs"
    assert tstate["vc_repos"] == ["barry/chatterbridge", "dimagi/open-chat-studio"]


def test_window_is_sticky_within_the_day():
    # turn 1: explicit last week stores the window
    main, pdata, sstate, tstate = load_node("resolve.py", participant={"contexts": CTXS}, frozen_now=NOW)
    main("vibe check last week")
    # turn 2: a bare correction reuses the stored window (still last week)
    main2, pdata2, sstate2, tstate2 = load_node("resolve.py", participant={"contexts": CTXS}, session=sstate, frozen_now=NOW)
    main2("merge those two")
    assert tstate2["vc_period_label"] == "last week"
    assert tstate2["vc_since_date"] == "2026-05-25"


def test_add_context():
    ret, pdata, sstate, tstate = resolve("add a context bermuda for barry/bermuda-core")
    assert ret == "manage"
    assert tstate["vc_mode"] == "manage"
    assert any(c["slug"] == "bermuda" for c in pdata["contexts"])
    assert "bermuda" in tstate["vc_reply"]


def test_list_contexts():
    ret, pdata, sstate, tstate = resolve("list contexts")
    assert ret == "manage"
    assert "chatterbridge" in tstate["vc_reply"]


def test_no_contexts_offers_to_add():
    ret, pdata, sstate, tstate = resolve("vibe check", participant={"contexts": []})
    assert ret == "no_context"
    assert tstate["vc_mode"] == "no_context"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest tests/test_resolve.py -q`
Expected: FAIL — `FileNotFoundError` / no `resolve.py` yet.

- [ ] **Step 3: Commit**

```bash
git add ocs/bots/vibe-check-v2/tests/test_resolve.py
git commit -m "test(vibe-check-v2): resolve behaviour — window, scope, stickiness, admin"
```

---

## Task 3: Resolve — implement to green

**Files:**
- Create: `ocs/bots/vibe-check-v2/snippets/resolve.py`

- [ ] **Step 1: Write `resolve.py`**

```python
# Vibe Check v2 — Resolve (OCS Code node). Start -> [Resolve] -> Fetch -> Draft -> End.
# Deterministic: period + scope for this turn; context admin; writes TEMP state for Fetch.
# Period precedence: explicit > sticky (same-day stored window) > gap-aware default.
# Scope precedence: named contexts > sticky (same day) > all contexts.
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

    def to_iso(moment):
        return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def parse_period(text):
        if yesterday_kw in text:
            return yesterday_kw
        if last_week_kw in text:
            return last_week_kw
        if this_week_kw in text:
            return this_week_kw
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

    if not contexts:
        set_temp_state_key("vc_mode", "no_context")
        set_temp_state_key("vc_reply", "You have no contexts yet. Add one, e.g. 'add a context ocs for dimagi/open-chat-studio'.")
        return "no_context"

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

    set_participant_data_key("last_vibe_date", today_iso)
    set_temp_state_key("vc_mode", "checkin")
    set_temp_state_key("vc_repos", union_repos(scope))
    set_temp_state_key("vc_author", scope_author(scope, author_handle))
    set_temp_state_key("vc_slug", ", ".join([c.get("slug", "") for c in scope]))
    set_temp_state_key("vc_period_label", label)
    set_temp_state_key("vc_since_iso", since_iso)
    set_temp_state_key("vc_until_iso", until_iso)
    set_temp_state_key("vc_since_date", since_date)
    set_temp_state_key("vc_until_date", until_date)
    return "checkin"
```

- [ ] **Step 2: Run the tests**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest tests/test_resolve.py -q`
Expected: PASS (all tests green).

- [ ] **Step 3: Sandbox scan + compile**

Run: `cd "ocs/bots/vibe-check-v2" && python3 tests/sandbox_scan.py && python3 -m py_compile snippets/resolve.py`
Expected: "sandbox scan clean" and no compile errors.

- [ ] **Step 4: Commit**

```bash
git add ocs/bots/vibe-check-v2/snippets/resolve.py
git commit -m "feat(vibe-check-v2): Resolve node — gap-aware window, scope, sticky, admin"
```

---

## Task 4: Fetch — write the failing tests

**Files:**
- Create: `ocs/bots/vibe-check-v2/tests/test_fetch.py`

- [ ] **Step 1: Write the test suite**

```python
from conftest import load_node


class FakeHttp:
    def __init__(self, responses):
        self.responses = responses  # dict: url-substring -> response dict
        self.calls = []

    def get(self, url, params=None, headers=None, auth=None, timeout=None):
        self.calls.append(url)
        for key in self.responses:
            if key in url:
                return self.responses[key]
        return {"json": [], "status_code": 200, "is_success": True}


def ok(json_body):
    return {"json": json_body, "status_code": 200, "is_success": True}


def test_relay_passthrough_for_manage():
    main, _, _, _ = load_node("fetch.py", temp={"vc_mode": "manage", "vc_reply": "Contexts: ocs"})
    assert main("x") == "RELAY: Contexts: ocs"


def test_checkin_assembles_signals_block():
    commit = {"commit": {"message": "fix retrieval\n\nbody", "author": {"date": "2026-06-02T10:00:00Z"}}}
    http = FakeHttp({
        "/commits": ok([commit]),
        "/issues": ok([]),
    })
    temp = {"vc_mode": "checkin", "vc_message": "vibe check", "vc_repos": ["dimagi/ocs"],
            "vc_author": "barry47products", "vc_slug": "ocs", "vc_period_label": "yesterday",
            "vc_since_iso": "2026-06-02T00:00:00Z", "vc_until_iso": "2026-06-03T00:00:00Z",
            "vc_since_date": "2026-06-02", "vc_until_date": "2026-06-02"}
    main, _, _, _ = load_node("fetch.py", temp=temp, http=http)
    out = main("vibe check")
    assert "SIGNALS for ocs, period: yesterday" in out
    assert "fix retrieval" in out
    assert "BARRY'S MESSAGE: vibe check" in out


def test_404_repo_is_skipped_not_fatal():
    http = FakeHttp({"/commits": {"json": None, "status_code": 404, "is_success": False}})
    temp = {"vc_mode": "checkin", "vc_message": "x", "vc_repos": ["x/private"], "vc_author": "barry47products",
            "vc_slug": "x", "vc_period_label": "yesterday", "vc_since_iso": "a", "vc_until_iso": "b",
            "vc_since_date": "2026-06-02", "vc_until_date": "2026-06-02"}
    main, _, _, _ = load_node("fetch.py", temp=temp, http=http)
    out = main("x")
    assert "skipped — HTTP 404" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest tests/test_fetch.py -q`
Expected: FAIL — no `fetch.py` yet.

- [ ] **Step 3: Commit**

```bash
git add ocs/bots/vibe-check-v2/tests/test_fetch.py
git commit -m "test(vibe-check-v2): fetch — RELAY passthrough + signal assembly + 404 skip"
```

---

## Task 5: Fetch — implement to green

**Files:**
- Create: `ocs/bots/vibe-check-v2/snippets/fetch.py`

- [ ] **Step 1: Write `fetch.py`**

```python
# Vibe Check v2 — Fetch (OCS Code node). Start -> Resolve -> [Fetch] -> Draft -> End.
# Pure I/O over the resolved request in TEMP state. Admin/no-context pass through as RELAY.
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
```

- [ ] **Step 2: Run the tests**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest tests/test_fetch.py -q`
Expected: PASS.

- [ ] **Step 3: Sandbox scan + compile**

Run: `cd "ocs/bots/vibe-check-v2" && python3 tests/sandbox_scan.py && python3 -m py_compile snippets/fetch.py`
Expected: "sandbox scan clean" + no compile errors.

- [ ] **Step 4: Commit**

```bash
git add ocs/bots/vibe-check-v2/snippets/fetch.py
git commit -m "feat(vibe-check-v2): Fetch node — GitHub signals + RELAY passthrough"
```

---

## Task 6: Prompts (Draft + Nudge)

**Files:**
- Create: `ocs/bots/vibe-check-v2/prompts/draft.md`
- Create: `ocs/bots/vibe-check-v2/prompts/nudge.md`

- [ ] **Step 1: Write `prompts/draft.md`**

```
You write Barry's private "vibe" — a short, honest summary of what he's been working on, for his
eyes only (a personal awareness DM, never posted anywhere). You are given his real GitHub activity
(the SIGNALS block) and his latest message.

If the input is a `RELAY:` line, output exactly the text after `RELAY:` and nothing else.

Otherwise write the vibe for the period named in the SIGNALS header:

- One summary, grouped by project: a short *bold project name* heading per project that actually
  moved, each with one to three plain-language bullet lines (start each with `• `) about what got
  better — outcomes, not mechanism. Omit projects that were quiet; don't list them as empty.
- First person, warm, plain. Presence over volume.
- Read gaps as signal. Several days with no commits → name it gently ("a quiet stretch on code —
  looks like the focus was elsewhere"), never "no activity." A `FETCH_ERROR` or `skipped — HTTP …`
  line means a repo couldn't be read — say so plainly; never call a failed read "no activity."
- Absorb what Barry adds that GitHub can't see: if he says he was at an offsite, off sick, in
  interviews, or in meetings, fold it in and let it explain the quiet stretches. The signals are
  the skeleton; his words add the lived context.
- This is a continuing chat. When he corrects or adds to a draft, revise the same vibe — don't
  restart from scratch or re-list everything. Never ask him to send activity; it's always provided.
- No intent questions, no reflective questions, no preamble — just the vibe.

Slack formatting only: *bold*, _italic_, `• ` bullets. At most one tasteful emoji. Output only the
vibe text.
```

- [ ] **Step 2: Write `prompts/nudge.md`**

```
Greet Barry warmly and invite him to do his vibe check — one short, friendly sentence, varied each
time. Tell him to just reply and you'll pull together what he's been working on. It's a private
check-in, just for him.
```

- [ ] **Step 3: Commit**

```bash
git add ocs/bots/vibe-check-v2/prompts
git commit -m "feat(vibe-check-v2): Draft + Nudge prompts"
```

---

## Task 7: NODES.md + OCS wiring + schedule + manual verification

**Files:**
- Create: `ocs/bots/vibe-check-v2/NODES.md`

- [ ] **Step 1: Write `NODES.md`**

```markdown
# Vibe Check v2 — node → file map

New OCS experiment "Vibe Check v2". Linear pipeline, private DM only. v1 untouched.

## Pipeline graph

​```text
[Start] → [Resolve] → [Fetch] → [Draft] → [End]
​```

## Nodes

| Node | Type | File | Notes |
| ---- | ---- | ---- | ----- |
| Resolve | Code | snippets/resolve.py | period + scope + admin; writes temp state |
| Fetch | Code | snippets/fetch.py | GitHub signals; RELAY passthrough for admin |
| Draft | LLM | prompts/draft.md | gpt-5.4-mini, Vibe Check OpenAI provider, History = Global, no tools |

## Auth provider

`github-vibe-check` — Bearer auth provider holding the GitHub PAT (reuse the v1 one).

## Schedule (not a pipeline node)

Weekday-morning `ScheduledMessage`s (Mon–Fri, 08:00 SAST) with `prompt_text` from
prompts/nudge.md. EventBot rephrases; the reply runs the pipeline. To change the nudge, edit
prompts/nudge.md and update the schedules' `custom_schedule_params["prompt_text"]` (no publish).
```

- [ ] **Step 2: Run the full local check (all green before touching OCS)**

Run: `cd "ocs/bots/vibe-check-v2" && python3 -m pytest -q && python3 tests/sandbox_scan.py && python3 -m py_compile snippets/*.py`
Expected: all tests pass, "sandbox scan clean", no compile errors.

- [ ] **Step 3: Build the experiment in OCS** (manual UI steps)

  1. Create a new experiment **"Vibe Check v2"**, pipeline-backed.
  2. Add nodes wired `Start → Resolve → Fetch → Draft → End`.
  3. **Resolve** (Code): paste `snippets/resolve.py`.
  4. **Fetch** (Code): paste `snippets/fetch.py`.
  5. **Draft** (LLM): paste `prompts/draft.md`; model **gpt-5.4-mini**, provider **Vibe Check OpenAI**, **History = Global**, **no tools enabled**.
  6. Confirm the **github-vibe-check** auth provider exists (PAT with repo Contents:Read).
  7. **Publish.**

- [ ] **Step 4: Connect a Slack channel + seed a context**

  1. Connect the bot to a Slack DM channel (new Slack app or reuse, per the v1 setup runbook).
  2. In the DM: `add a context ocs for dimagi/open-chat-studio` → expect "Added context 'ocs' …".

- [ ] **Step 5: Manual DM verification scenarios**

  Run each in the DM and confirm:
  1. `vibe check` → a grouped vibe over the last 7 days (first-ever baseline).
  2. `vibe check last week` → vibe scoped to last week.
  3. `vibe check ocs` → vibe for the ocs context only.
  4. After a vibe, `actually I was at an offsite Tue–Wed` → the vibe is revised to fold that in and read the quiet days as the offsite (not "no activity").
  5. `there may have been other things I may have tackled` → does **not** error and does **not** jump to "May"; stays on the current window.
  6. `list contexts` → lists contexts, no LLM drafting.

- [ ] **Step 6: Set up the weekday schedule**

  Create five `ScheduledMessage`s (Mon–Fri 08:00 SAST) for the participant, `prompt_text` = contents of `prompts/nudge.md`. Verify one fires (or trigger manually) and that replying produces a vibe.

- [ ] **Step 7: Commit**

```bash
git add ocs/bots/vibe-check-v2/NODES.md
git commit -m "docs(vibe-check-v2): NODES.md + wiring/schedule/verification notes"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** linear pipeline ✓ (Tasks 3/5/6), gap-aware + first-7-days ✓ (Task 3 tests), grouped-by-project + read-gaps + non-code context ✓ (Task 6 draft.md), private/no-posting ✓ (no post node anywhere), on-demand scoping + stickiness ✓ (Task 3), nudge-then-draft ✓ (Task 7), per-bot folder ✓ (file structure), v2.1 cache ✓ explicitly deferred (not in any task).
- **Placeholder scan:** none — every code/test step shows full content.
- **Type consistency:** temp keys (`vc_mode`, `vc_repos`, `vc_slug`, `vc_period_label`, `vc_since_date`/`vc_until_date`, `vc_since_iso`/`vc_until_iso`, `vc_reply`, `vc_message`) match between `resolve.py` (writer) and `fetch.py` (reader); `RELAY:`/`SIGNALS` markers match between `fetch.py` and `draft.md`.

## Out of scope (v2.1+)

Immutable-history signal cache, optional team-channel publishing, persisted vibe journal — see the design doc.
```
