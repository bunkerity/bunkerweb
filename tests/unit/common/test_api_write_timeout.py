"""``API.request`` must always return its four-tuple, and must bound the body write.

Port of dev ``7a6bf2c70`` (row 20 of the fold-in). Three defects, all reachable on 1.7 before this:

* ``resp.json()`` sat AFTER the try, so a body that is not JSON -- an HTML 502 from a proxy, a
  truncated response -- raised out of ``request()``. Every caller unpacks a four-tuple
  (``ApiCaller.send_to_apis`` does it inside a thread-pool task), so the raise took the caller down
  instead of being reported as a failed push.
* the cleartext retry ran INSIDE ``except ConnectionError``, where its own ``ConnectionError``
  escaped the sibling ``except Exception``. Same broken contract.
* nothing bounded the body write. urllib3 hands the socket the CONNECT budget and only swaps in the
  read budget once the request is fully written, so a peer that accepts and then stops reading
  blocks a folder push for as long as connecting is allowed to take. ``ApiCaller.send_files``
  computes a write budget and ``ApiCaller._accepts_write_timeout`` drops it on the floor for any
  client whose ``request()`` does not take it -- which was every client until this landed.
"""

import socket
import sys
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError

ROOT = Path(__file__).resolve().parents[3]
for _p in (ROOT / "src" / "common" / "api", ROOT / "src" / "common" / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from API import API, _InstanceAdapter, _carries_write_timeout, _BodyWriteTimeout  # noqa: E402
from ApiCaller import _accepts_write_timeout  # noqa: E402


class _NotJson:
    status_code = 200
    reason = "Bad Gateway"
    text = "<html>502 Bad Gateway</html>"

    @staticmethod
    def json():
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


@pytest.fixture()
def deaf_peer():
    """A listening socket that never accepts and whose receive buffer is tiny.

    The connection completes from the backlog, so the client believes it is talking to a live
    instance; the body then has nowhere to go after a few kilobytes. That is the shape of the
    stall the write budget exists for -- an instance that is up but wedged.
    """
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        yield server.getsockname()[1]
    finally:
        server.close()


def test_a_body_that_is_not_json_is_reported_not_raised():
    api = API("http://instance.example.com:5000", token="t")

    with patch("API.request", return_value=_NotJson()):
        result = api.request("POST", "/cache")

    assert result[0] is False
    assert "Request failed" in result[1]
    assert len(result) == 4, "the caller unpacks four values whatever happens"


def test_a_failing_cleartext_retry_is_reported_not_raised():
    """The HTTPS failure is retried in plaintext; that retry failing is still a returned failure."""
    api = API("https://instance.example.com:5443", token="t")
    calls = []

    def _both_fail(*args, **kwargs):
        calls.append(args)
        raise RequestsConnectionError(f"call {len(calls)} refused")

    with patch("API.request", side_effect=_both_fail):
        result = api.request("POST", "/cache")

    assert len(calls) == 2, "the HTTPS failure should still produce exactly one plaintext retry"
    assert result == (False, "Request failed: call 2 refused", None, None)


def test_the_write_budget_bounds_a_body_the_peer_never_reads(deaf_peer):
    """The write budget must bound the upload even when connect and read are generous."""
    api = API(f"http://127.0.0.1:{deaf_peer}", token="t")

    started = monotonic()
    # (30, 30): neither the connect nor the read budget can be what ends this call.
    result = api.request("POST", "/cache", data=bytes(4 * 1024 * 1024), timeout=(30, 30), write_timeout=1)
    elapsed = monotonic() - started

    assert result[0] is False
    assert result[1].startswith("Write timed out"), result[1]
    assert elapsed < 15, f"the body write ran for {elapsed:.1f}s on a 1s write budget"


def test_a_write_that_ran_out_is_never_retried_in_cleartext():
    """Retrying it would spend the budget twice and re-upload the whole archive.

    The https endpoint would otherwise be downgraded on any ConnectionError; the write marker is
    what tells this one apart from a failed TLS handshake.
    """
    api = API("https://instance.example.com:5443", token="t")
    calls = []

    def _write_timed_out(*args, **kwargs):
        calls.append(args)
        raise RequestsConnectionError(RuntimeError(_BodyWriteTimeout("timed out")))

    with patch("requests.sessions.Session.request", side_effect=_write_timed_out):
        result = api.request("POST", "/cache", data=b"x" * 32, timeout=(30, 30), write_timeout=1)

    assert len(calls) == 1, "one dial, no cleartext second upload"
    assert result[0] is False
    assert result[1].startswith("Write timed out"), result[1]


def test_a_connect_failure_is_not_reported_as_a_write_timeout():
    """A refused connection carries no write marker, so it must keep its own message."""
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()

    api = API(f"http://127.0.0.1:{port}", token="t")
    result = api.request("POST", "/cache", data=b"x", timeout=(2, 2), write_timeout=1)

    assert result[0] is False
    assert result[1].startswith("Connection error"), result[1]


def test_a_pinned_instance_is_still_never_downgraded_to_plaintext():
    api = API("https://instance.example.com:5443", token="t", tls_mode="pinned", tls_fingerprint="ab" * 32)
    calls = []

    def _fail(*args, **kwargs):
        calls.append(args)
        raise RequestsConnectionError("TLS handshake failed")

    with patch("requests.sessions.Session.request", side_effect=_fail):
        result = api.request("POST", "/cache", write_timeout=5)

    assert len(calls) == 1, "a pinned instance must never be retried in cleartext"
    assert result == (False, "Connection error: TLS handshake failed", None, None)


def test_one_adapter_carries_the_pin_and_the_write_budget_at_once():
    """They share the https:// mount, so two adapters cannot both be installed."""
    adapter = _InstanceAdapter("ab" * 32, 7)

    assert adapter.poolmanager.connection_pool_kw["assert_fingerprint"] == "ab" * 32
    pool_classes = adapter.poolmanager.pool_classes_by_scheme
    assert pool_classes["https"].ConnectionCls.__name__ == "_Connection"
    assert pool_classes["http"].ConnectionCls.__name__ == "_Connection"


def test_the_shared_pool_class_mapping_is_never_mutated():
    from urllib3.poolmanager import PoolManager, pool_classes_by_scheme

    _InstanceAdapter(None, 7)

    assert PoolManager().pool_classes_by_scheme == pool_classes_by_scheme


def test_an_unpinned_dial_without_a_write_budget_still_uses_the_plain_sender():
    """No Session, no adapter: the default path must not change at all."""
    api = API("http://instance.example.com:5000", token="t")

    class _Ok:
        status_code = 200
        reason = "OK"
        text = "{}"

        @staticmethod
        def json():
            return {"ok": True}

    with patch("API.request", return_value=_Ok()) as plain, patch("requests.sessions.Session.request") as session_request:
        result = api.request("GET", "/ping")

    assert result == (True, "ok", 200, {"ok": True})
    assert plain.call_count == 1
    assert session_request.call_count == 0


def test_the_marker_survives_the_wrappers_requests_puts_around_it():
    inner = _BodyWriteTimeout("timed out")
    wrapped = RequestsConnectionError(RuntimeError(inner))

    assert _carries_write_timeout(wrapped) is True
    assert _carries_write_timeout(RequestsConnectionError(OSError("refused"))) is False


def test_the_client_now_advertises_the_argument_api_caller_looks_for():
    """``ApiCaller`` computes a write budget and drops it unless ``request()`` takes it."""
    assert _accepts_write_timeout(API("http://instance.example.com:5000")) is True
