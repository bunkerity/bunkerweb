"""An untouched session was rewritten to the store on every request, static assets included.

Port of dev c58b69e07. flask-session's `should_set_storage` returns
`session.modified or SESSION_REFRESH_EACH_REQUEST`, and the Web UI sets that flag, so every
request with a non-empty session rewrote the whole payload just to slide its expiry — and
Flask serves the UI's static assets at the URL root here, so a single page load was a dozen
Redis writes.

A *modified* session still writes immediately: login, logout and session id rotation all
depend on it. An unmodified one writes only once its stored copy is old enough.
"""

import re
from pathlib import Path
from time import time
from typing import Any, Optional

import pytest

_UTILS = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "utils.py"


def _shipped():
    """Splice the shipped block out of `routes/utils.py` rather than importing it.

    The module pulls in Flask, qrcode and BW_CONFIG at import time, none of which this
    behaviour needs. Extracting keeps the test honest anyway: rename or delete the helper and
    the extraction fails here rather than the assertions passing against a local copy.
    """
    source = _UTILS.read_text(encoding="utf-8")
    match = re.search(r"^SESSION_STORAGE_REFRESH_RATIO = .*?^def session_storage_due\(.*?^    return True$", source, re.M | re.S)
    assert match, "session_storage_due is gone from app/routes/utils.py"
    namespace = {"time": time, "Any": Any, "Optional": Optional}
    exec(compile(match.group(0), str(_UTILS), "exec"), namespace)  # noqa: S102
    return namespace


_SHIPPED = _shipped()
SESSION_LAST_STORED_KEY = _SHIPPED["SESSION_LAST_STORED_KEY"]
SESSION_STORAGE_REFRESH_RATIO = _SHIPPED["SESSION_STORAGE_REFRESH_RATIO"]
session_storage_due = _SHIPPED["session_storage_due"]

LIFETIME = 12 * 3600.0
WINDOW = LIFETIME * SESSION_STORAGE_REFRESH_RATIO


class FakeSession(dict):
    def __init__(self, *, modified=False, **kwargs):
        super().__init__(**kwargs)
        self.modified = modified


# --------------------------------------------------------------------------------------
# The defect
# --------------------------------------------------------------------------------------
def test_an_untouched_session_is_not_rewritten_on_every_request():
    session = FakeSession()

    assert session_storage_due(session, LIFETIME, now=1000.0) is True, "the first request has no stamp yet"
    assert session_storage_due(session, LIFETIME, now=1001.0) is False
    assert session_storage_due(session, LIFETIME, now=1000.0 + WINDOW - 1) is False


def test_the_stamp_slides_once_the_window_is_burnt():
    session = FakeSession()
    session_storage_due(session, LIFETIME, now=1000.0)

    assert session_storage_due(session, LIFETIME, now=1000.0 + WINDOW) is True
    assert session[SESSION_LAST_STORED_KEY] == 1000.0 + WINDOW


# --------------------------------------------------------------------------------------
# What must never be throttled
# --------------------------------------------------------------------------------------
def test_a_modified_session_always_writes():
    """Login, logout and `_rotate_session_id` all depend on the write landing now."""
    session = FakeSession(modified=True)
    session_storage_due(session, LIFETIME, now=1000.0)

    assert session_storage_due(session, LIFETIME, now=1001.0) is True


def test_a_modified_session_still_gets_a_fresh_stamp():
    """Otherwise the next unmodified request would compare against a stale one and write."""
    session = FakeSession(modified=True)

    assert session_storage_due(session, LIFETIME, now=2000.0) is True
    assert session[SESSION_LAST_STORED_KEY] == 2000.0


@pytest.mark.parametrize("stamp", [None, "recently", True, False, [], {"t": 1}])
def test_a_junk_stamp_writes_rather_than_trusting_it(stamp):
    """A tampered or truncated payload must fall back to writing, never to skipping.

    `True` is the one that would slip through a bare `isinstance(x, (int, float))`: in Python
    a bool *is* an int, and `now - True` is a number, so a session carrying `True` would be
    treated as stamped at t=1 and, for any realistic clock, judged fresh forever.
    """
    session = FakeSession()
    if stamp is not None:
        session[SESSION_LAST_STORED_KEY] = stamp

    assert session_storage_due(session, LIFETIME, now=1000.0) is True


def test_a_stamp_from_the_future_does_not_freeze_the_session():
    """A clock step back must not park the session on a stamp it can never burn through."""
    session = FakeSession()
    session[SESSION_LAST_STORED_KEY] = 10_000.0

    # Still inside the window as measured from the future stamp, so the write is skipped...
    assert session_storage_due(session, LIFETIME, now=9_000.0) is False
    # ...but never past it: the difference only has to exceed the window.
    assert session_storage_due(session, LIFETIME, now=10_000.0 + WINDOW) is True


# --------------------------------------------------------------------------------------
# The wiring
# --------------------------------------------------------------------------------------
def test_the_ratio_leaves_the_cookie_and_the_store_sliding_together():
    """flask-session's `save_session` returns before `should_set_cookie` when storage is
    skipped, so a client can never hold a cookie for an expired key — but only while the
    ratio leaves real slack behind every skipped write."""
    assert 0 < SESSION_STORAGE_REFRESH_RATIO < 1


def test_main_installs_the_throttle_on_the_session_interface():
    """The helper is dead code unless `main.py` overrides `should_set_storage` with it."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py").read_text(encoding="utf-8")

    assert "session_storage_due" in source
    assert "app.session_interface.should_set_storage" in source
