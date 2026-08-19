"""Per-request API accounting: the counter, the header, and the correlation id.

Lot A of the UI performance work is measurement, and its one hard rule is that the regression
guard counts **calls**, never milliseconds: a stopwatch assertion in CI measures the runner, not
the code. `test_home_call_budget.py` holds the budgets; this file holds the machinery.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "common" / "utils"))

from app import perf  # noqa: E402
from base_api_client import REQUEST_CACHE, REQUEST_ID, ApiUnavailableError, BaseApiClient  # noqa: E402


@pytest.fixture
def app():
    return Flask(__name__)


@pytest.fixture(autouse=True)
def _no_memo_across_tests():
    """`perf.start()` opens the memo and only `perf.finish()` closes it — which in production is
    the teardown Flask always runs. A test that opens one must not hand it to the next."""
    token = REQUEST_CACHE.set(None)
    yield
    REQUEST_CACHE.reset(token)


# --------------------------------------------------------------------------------------
# The counter
# --------------------------------------------------------------------------------------
def test_calls_and_time_add_up_over_a_request(app):
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/services", 12.0, 200)
        perf.record_api_call("GET", "/metadata", 8.0, 200)

        calls, api_ms, total_ms = perf.totals()

    assert calls == 2
    assert api_ms == 20.0
    assert total_ms >= 0


def test_a_failed_call_counts_like_any_other(app):
    """A page that is slow because the API is timing out has to look slow in the accounting."""
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/services", 30_000.0, None)

        calls, api_ms, _ = perf.totals()

    assert (calls, api_ms) == (1, 30_000.0)


def test_the_counter_is_per_request(app):
    with app.test_request_context("/home"):
        perf.start("first")
        perf.record_api_call("GET", "/services", 12.0, 200)
        first, _, _ = perf.totals()

    with app.test_request_context("/home"):
        perf.start("second")
        second, _, _ = perf.totals()

    assert (first, second) == (1, 0)


def test_a_call_outside_a_request_is_ignored_rather_than_crashing():
    """The scheduler and the autoconf share this client; a background call must not explode."""
    perf.record_api_call("GET", "/services", 12.0, 200)

    assert perf.totals() is None


# --------------------------------------------------------------------------------------
# The header
# --------------------------------------------------------------------------------------
def test_server_timing_splits_api_time_from_the_rest(app):
    """The split is the point: it says which of the two services to go and look at."""
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/services", 10.0, 200)
        header = perf.server_timing()

    assert 'desc="1 calls"' in header
    assert header.startswith("api;dur=10.0")
    assert "app;dur=" in header and "total;dur=" in header


def test_the_header_carries_no_path_and_no_argument(app):
    """`Server-Timing` is readable by anything that can read the response."""
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/services?name=secret-customer.example.com", 10.0, 200)
        header = perf.server_timing()

    assert "secret-customer" not in header
    assert "/services" not in header


def test_no_header_when_the_request_was_never_started(app):
    """CSRF failures and early returns skip `before_request`; that must not 500 the response."""
    with app.test_request_context("/home"):
        assert perf.server_timing() is None


# --------------------------------------------------------------------------------------
# The client hook
# --------------------------------------------------------------------------------------
def _client(response=None, boom=None):
    client = BaseApiClient(base_url="http://api", api_token="t")
    client.session = Mock()
    if boom:
        client.session.request.side_effect = boom
    else:
        client.session.request.return_value = response
    return client


def _response(status=200, payload=None):
    return SimpleNamespace(status_code=status, content=b"{}", text="{}", json=lambda: payload or {"status": "success"})


def test_every_call_reaches_the_observer_with_its_duration_and_status():
    seen = []
    client = _client(_response())
    client.observer = lambda method, path, ms, status: seen.append((method, path, ms, status))

    client._get("/services")

    assert len(seen) == 1
    method, path, ms, status = seen[0]
    assert (method, path, status) == ("GET", "/services", 200)
    assert ms >= 0


def test_an_unreachable_api_still_reaches_the_observer():
    from requests.exceptions import Timeout

    seen = []
    client = _client(boom=Timeout("too slow"))
    client.observer = lambda *args: seen.append(args)

    with pytest.raises(ApiUnavailableError):
        client._get("/services")

    assert len(seen) == 1
    assert seen[0][3] is None, "an unreachable API has no status, and that has to be visible"


def test_a_broken_observer_cannot_take_the_request_down():
    """Accounting that can break a page is worse than no accounting."""
    client = _client(_response())
    client.observer = Mock(side_effect=RuntimeError("boom"))

    assert client._get("/services") == {"status": "success"}


def test_the_client_costs_nothing_when_nobody_is_observing():
    client = _client(_response())

    assert client.observer is None
    assert client._get("/services") == {"status": "success"}


# --------------------------------------------------------------------------------------
# The correlation id
# --------------------------------------------------------------------------------------
def test_the_request_id_travels_with_every_api_call():
    client = _client(_response())
    token = REQUEST_ID.set("page-render-1")
    try:
        client._get("/services")
    finally:
        REQUEST_ID.reset(token)

    assert client.session.request.call_args.kwargs["headers"]["X-Request-ID"] == "page-render-1"


def test_no_header_is_sent_outside_a_request():
    client = _client(_response())
    token = REQUEST_ID.set("")
    try:
        client._get("/services")
    finally:
        REQUEST_ID.reset(token)

    assert "headers" not in client.session.request.call_args.kwargs


def test_a_caller_supplied_header_is_not_dropped():
    client = _client(_response())
    token = REQUEST_ID.set("page-render-1")
    try:
        client._get("/services", headers={"Accept": "text/csv"})
    finally:
        REQUEST_ID.reset(token)

    sent = client.session.request.call_args.kwargs["headers"]
    assert sent["Accept"] == "text/csv"
    assert sent["X-Request-ID"] == "page-render-1"


# --------------------------------------------------------------------------------------
# The wiring — asserted at the source, since booting main.py needs container-only paths
# --------------------------------------------------------------------------------------
MAIN = Path(__file__).resolve().parents[3] / "src" / "ui" / "main.py"


def test_the_ui_opens_the_accounting_and_publishes_it():
    source = MAIN.read_text()

    assert "perf.start(request_id)" in source
    assert "REQUEST_ID.set(request_id)" in source
    assert 'response.headers["Server-Timing"] = timing' in source
    assert 'response.headers["X-Request-ID"] = g.request_id' in source


def test_an_inbound_request_id_is_never_trusted_verbatim():
    """It is echoed in a response header and written to two services' logs."""
    source = MAIN.read_text()

    assert '_REQUEST_ID_RE = re_compile(r"[A-Za-z0-9._-]{1,64}")' in source
    assert "request_id = inbound if _REQUEST_ID_RE.fullmatch(inbound) else token_hex(8)" in source


def test_the_api_echoes_the_id_back_under_the_same_rule():
    source = (Path(__file__).resolve().parents[3] / "src" / "api" / "app" / "main.py").read_text()

    assert 'fullmatch(r"[A-Za-z0-9._-]{1,64}", inbound)' in source
    assert 'response.headers["X-Request-ID"] = request_id' in source


def test_the_observer_is_attached_to_the_client_the_ui_actually_uses():
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "dependencies.py").read_text()

    assert "API_CLIENT.observer = record_api_call" in source


def test_the_flask_g_is_where_the_counters_live(app):
    """Not a module global: the UI runs threaded workers, and a global would mix requests."""
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/services", 1.0, 200)

        assert g.api_calls == 1
        assert g.request_id == "abc123"


# --------------------------------------------------------------------------------------
# The per-request memo (Lot B)
# --------------------------------------------------------------------------------------
@pytest.fixture
def memo():
    token = REQUEST_CACHE.set({})
    yield
    REQUEST_CACHE.reset(token)


def test_the_same_get_twice_costs_one_round_trip(memo):
    """The measured case: one render asks for the metadata from the shared context and again
    from the route, because neither can see the other's answer."""
    client = _client(_response(payload={"metadata": {"version": "1.7.0"}}))

    first = client._get("/metadata")
    second = client._get("/metadata")

    assert first == second
    assert client.session.request.call_count == 1


def test_a_different_query_is_a_different_request(memo):
    client = _client(_response())

    client._get("/global_settings", params={"methods": "true"})
    client._get("/global_settings", params={"full": "true"})

    assert client.session.request.call_count == 2


def test_the_same_query_in_a_different_order_is_the_same_request(memo):
    client = _client(_response())

    client._get("/services", params={"a": "1", "b": "2"})
    client._get("/services", params={"b": "2", "a": "1"})

    assert client.session.request.call_count == 1


def test_a_write_empties_the_memo(memo):
    """A request that saves something and then reads it back must see what it wrote."""
    client = _client(_response())

    client._get("/metadata")
    client._patch("/metadata", json={"data": {}})
    client._get("/metadata")

    assert client.session.request.call_count == 3


def test_two_identical_writes_both_go_out(memo):
    """Only reads are idempotent. Memoising a write would swallow the second one and hand back
    the first one's response — a delete that reports success without deleting anything.

    Deliberately a *bodyless* write: a write that carries a body is already excluded by the
    body guard, so it proves nothing about the method check."""
    client = _client(_response())

    client._delete("/bans/1.2.3.4")
    client._delete("/bans/1.2.3.4")

    assert client.session.request.call_count == 2


def test_a_get_that_carries_a_body_is_not_memoised(memo):
    """The key is path plus query. A GET with a body — the API has a few filtered reads shaped
    that way — would collide with any other GET on the same path."""
    client = _client(_response())

    client._get("/services", json={"filter": "a"})
    client._get("/services", json={"filter": "b"})

    assert client.session.request.call_count == 2


def test_nothing_is_memoised_outside_a_request():
    """The scheduler and the autoconf share this client and run for hours."""
    client = _client(_response())

    client._get("/metadata")
    client._get("/metadata")

    assert client.session.request.call_count == 2


def test_a_caller_editing_what_it_got_cannot_corrupt_the_next_one(memo):
    """Callers treat a response as theirs and edit it in place. Without a copy the memo hands
    the second caller whatever the first one did to it — this is a bug that shipped: the plugin
    pages 500'd with `KeyError: 'id'` because the shared context had popped it off first."""
    client = _client(_response(payload={"plugins": [{"id": "antibot", "settings": {}}]}))

    first = client._get("/plugins")
    first["plugins"][0].pop("id")
    first["plugins"].append({"id": "invented"})

    second = client._get("/plugins")

    assert second == {"plugins": [{"id": "antibot", "settings": {}}]}
    assert client.session.request.call_count == 1, "still one round trip — isolation, not a second fetch"


def test_the_first_caller_cannot_poison_the_entry_either(memo):
    """The first caller does not read from the memo, it *fills* it — so the copy has to happen
    on the way in as well as on the way out."""
    client = _client(_response(payload={"metadata": {"version": "1.7.0"}}))

    client._get("/metadata")["metadata"]["version"] = "tampered"

    assert client._get("/metadata") == {"metadata": {"version": "1.7.0"}}


def test_a_later_caller_cannot_poison_the_one_after_it(memo):
    """Copying on the way in only protects the caller that *filled* the entry. Every caller
    after that reads from it, and one of them editing what it got would hand the next one the
    edit — the same bug, one call further down the render."""
    client = _client(_response(payload={"metadata": {"version": "1.7.0"}}))

    client._get("/metadata")
    client._get("/metadata")["metadata"]["version"] = "tampered"

    assert client._get("/metadata") == {"metadata": {"version": "1.7.0"}}


def test_a_failed_get_is_not_remembered(memo):
    """Remembering a failure would hold it for the whole render — and the pages guard each
    call individually precisely so one failure costs one card, not the page."""
    client = BaseApiClient(base_url="http://api", api_token="t")
    client.session = Mock()
    client.session.request.side_effect = [_response(status=503), _response()]

    with pytest.raises(ApiUnavailableError):
        client._get("/metadata")
    client._get("/metadata")

    assert client.session.request.call_count == 2


def test_a_memo_hit_is_reported_as_a_hit_not_as_a_call(app, memo):
    """`Server-Timing` has to show the saving, or there is no way to tell the memo is working
    in production."""
    client = _client(_response())
    client.observer = perf.record_api_call

    with app.test_request_context("/home"):
        perf.start("abc123")
        client._get("/metadata")
        client._get("/metadata")
        header = perf.server_timing()
        calls, _, _ = perf.totals()

    assert calls == 1
    assert 'cache;desc="1 hits"' in header


def test_the_header_says_nothing_about_the_cache_when_it_was_not_used(app):
    with app.test_request_context("/home"):
        perf.start("abc123")
        perf.record_api_call("GET", "/metadata", 5.0, 200)
        header = perf.server_timing()

    assert "cache" not in header


def test_the_memo_is_closed_when_the_request_ends(app):
    """Worker threads are reused; a memo left open is handed to the next request."""
    with app.test_request_context("/home"):
        perf.start("abc123")
        assert REQUEST_CACHE.get() is not None
        perf.finish()
        assert REQUEST_CACHE.get() is None


def test_the_ui_closes_it_in_teardown_which_always_runs():
    source = MAIN.read_text()
    teardown = source.split("@app.teardown_request", 1)[1]

    assert "perf.finish()" in teardown.split("def ", 2)[1]
