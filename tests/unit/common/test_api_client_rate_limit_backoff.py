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
