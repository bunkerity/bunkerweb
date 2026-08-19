"""A 429 from the API must not park the caller's thread.

urllib3 retries 429 whenever the response carries a `Retry-After` (429 is in
`Retry.RETRY_AFTER_STATUS_CODES`) and *sleeps* for the value the server sent. The API's rate
limiter answers with the time left in its fixed window, up to a full minute, so one 429 blocked
a UI worker thread inside a request handler for longer than BunkerWeb's own 60s proxy read
timeout: the browser's connection was closed before the page ever came back.

Measured against the pinned urllib3: with `respect_retry_after_header` left at its default,
`is_retry("GET", 429, has_retry_after=True)` is True and `get_retry_after` returns the header
verbatim; the client then waits that long before its single retry.
"""

from base_api_client import BaseApiClient


def _retry_policy():
    client = BaseApiClient("http://bw-api:5000", "token")
    return client.session.get_adapter("http://bw-api:5000").max_retries


def test_a_rate_limited_call_fails_fast_instead_of_sleeping_out_the_window():
    retry = _retry_policy()

    assert retry.respect_retry_after_header is False
    # has_retry_after=True is the case that used to sleep; 429 must not be retried at all now.
    assert retry.is_retry("GET", 429, has_retry_after=True) is False


def test_the_transient_5xx_retry_is_still_in_place():
    retry = _retry_policy()

    assert retry.total == 1
    for status in (502, 503, 504):
        assert retry.is_retry("GET", status) is True


# --------------------------------------------------------------------------------------
# A retried 5xx must still surface as ApiUnavailableError, not as a raw requests exception
# --------------------------------------------------------------------------------------
def _server(status):
    """A one-off HTTP server that answers every request with `status`.

    A real socket rather than a mocked adapter on purpose: what is under test is what urllib3's
    Retry does when it gives up, and that only happens on a real response cycle.
    """
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from threading import Thread

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_an_exhausted_5xx_retry_is_reported_as_the_api_being_unavailable():
    """`status_forcelist=[502, 503, 504]` means requests never *returns* those responses once the
    retries are spent — urllib3 raises `MaxRetryError` and requests re-raises `RetryError`, which
    subclasses `RequestException` and **not** `ConnectionError`.

    That made the `resp.status_code >= 500` branch dead for precisely the three statuses it exists
    for, and let a raw requests exception escape the client. Every UI route catches
    `(ApiClientError, ApiUnavailableError)` and none of them catch that, so a degraded API turned
    every page into a 500 instead of the "API unavailable" flash. Found on `/web-cache` and
    `/timings`, but the reach is any endpoint during an API restart.
    """
    from base_api_client import ApiUnavailableError
    import pytest

    server = _server(503)
    try:
        client = BaseApiClient(f"http://127.0.0.1:{server.server_address[1]}", "token")
        with pytest.raises(ApiUnavailableError):
            client._get("/whatever")
    finally:
        server.shutdown()
        server.server_close()


def test_a_5xx_outside_the_retry_list_still_reports_the_same_way():
    """500 is not in the forcelist, so it comes back as a response and takes the other path. Both
    roads have to end at the same exception or a caller cannot handle "the API is broken" once."""
    from base_api_client import ApiUnavailableError
    import pytest

    server = _server(500)
    try:
        client = BaseApiClient(f"http://127.0.0.1:{server.server_address[1]}", "token")
        with pytest.raises(ApiUnavailableError):
            client._get("/whatever")
    finally:
        server.shutdown()
        server.server_close()


def test_the_binary_download_path_reports_it_the_same_way():
    """`_raw_request` serves plugin tarballs, log downloads and config/service exports. It shares
    the session and therefore the retry policy, so it had the identical hole — found only because
    the same `except` clause appears twice in the file and the first fix touched one of them."""
    from base_api_client import ApiUnavailableError
    import pytest

    server = _server(503)
    try:
        client = BaseApiClient(f"http://127.0.0.1:{server.server_address[1]}", "token")
        with pytest.raises(ApiUnavailableError):
            client._raw_request("GET", "/download")
    finally:
        server.shutdown()
        server.server_close()


def test_no_handler_in_this_client_forgets_retryerror():
    """Both call paths had to be found by reading. A retried 5xx escaping as a raw requests
    exception is invisible until a page 500s, so pin the rule rather than the two sites: every
    handler that catches the connection errors must catch the retry error beside them."""
    from pathlib import Path
    import re

    source = (Path(__file__).resolve().parents[3] / "src" / "common" / "utils" / "base_api_client.py").read_text(encoding="utf-8")
    handlers = re.findall(r"except \(([^)]*)\)", source)
    connection_handlers = [h for h in handlers if "RequestsConnectionError" in h]

    assert connection_handlers, "the handlers moved; this test is looking at the wrong thing"
    for handler in connection_handlers:
        assert "RetryError" in handler, f"`except ({handler})` lets a retried 502/503/504 escape as a raw requests exception"
