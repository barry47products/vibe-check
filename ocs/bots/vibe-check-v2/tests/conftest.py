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
