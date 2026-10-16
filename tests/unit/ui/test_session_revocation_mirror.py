"""A revoked session stays revoked through a Redis outage (D4, the revocation half).

`ResilientRedisSessionInterface` serves a session from a local store while Redis is unreachable.
A revocation marker that only lives in Redis would stop applying at exactly that moment, and one
that could not be written to a dead Redis would never apply at all. `revoke_sessions` therefore
mirrors every marker into the interface's local fallback, and `is_session_revoked` consults both
stores (skipping Redis while the interface is not talking to it).

Same harness as test_resilient_redis_session.py: a real `redis-server` the test stops and restarts
with its keys kept (AOF), the real Flask-Session interface and main.py's own session statements.
"""

import shutil
from time import monotonic
from unittest.mock import patch

import pytest

from test_resilient_redis_session import _reopen_breaker, redis_server, stack  # noqa: F401  (fixtures)

from app.utils import is_session_revoked, revoke_sessions  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("redis-server") is None, reason="needs the redis-server binary")


def test_a_session_revoked_while_redis_is_down_reads_as_revoked_during_and_after_the_outage(stack):  # noqa: F811
    app, _, server = stack
    server.stop()

    with app.test_request_context():
        assert revoke_sessions(["sid-a"]) != "", "the caller must still be told Redis did not take the marker"
        assert is_session_revoked("sid-a") is True, "revoked during the outage"
        assert is_session_revoked("sid-other") is False

        server.start()
        _reopen_breaker(app)

        assert is_session_revoked("sid-a") is True, "revoked after Redis returns, though Redis never saw the marker"
        assert is_session_revoked("sid-other") is False


def test_a_revocation_made_while_redis_was_up_still_applies_when_redis_goes_away(stack):  # noqa: F811
    app, _, server = stack

    with app.test_request_context():
        assert revoke_sessions(["sid-b"]) == ""
        server.stop()

        assert is_session_revoked("sid-b") is True, "the marker lives in the local store too"
        assert is_session_revoked("sid-other") is False


def test_the_check_skips_redis_while_the_interface_has_given_up_on_it(stack):  # noqa: F811
    app, client, server = stack

    with app.test_request_context():
        assert revoke_sessions(["sid-c"]) == ""
        app.session_interface._breaker_until = monotonic() + 60

        with patch.object(client, "exists", side_effect=AssertionError("Redis was called while its breaker is open")):
            assert is_session_revoked("sid-c") is True
            assert is_session_revoked("sid-other") is False


def test_nothing_is_revoked_that_was_not_revoked(stack):  # noqa: F811
    app, _, _ = stack

    with app.test_request_context():
        assert is_session_revoked("sid-d") is False
