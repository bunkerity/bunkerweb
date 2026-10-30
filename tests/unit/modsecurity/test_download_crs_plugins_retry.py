"""CRS plugin request retries against dev's shipped helper."""

from unittest.mock import MagicMock

import pytest

from crs_plugins_job_source import load_job_helpers


@pytest.fixture
def ns():
    namespace = load_job_helpers()
    namespace["sleep"] = lambda *_args: None
    return namespace


def _response(status_code=200, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


class TestRequestWithRetryRecoversFromTransientFailures:
    def test_two_timeouts_then_success(self, ns):
        sleeps = []
        ns["sleep"] = lambda seconds: sleeps.append(seconds)
        timeout_error = ns["Timeout"]
        request_fn = MagicMock(side_effect=[timeout_error("timed out"), timeout_error("timed out"), _response(200)])

        result = ns["request_with_retry"](request_fn, "https://example.invalid", timeout=8)

        assert result.status_code == 200
        assert request_fn.call_count == 3
        assert sleeps == [2, 4]

    def test_5xx_retries_then_returns_the_eventual_response(self, ns):
        request_fn = MagicMock(side_effect=[_response(503), _response(502), _response(200)])

        result = ns["request_with_retry"](request_fn, "https://example.invalid")

        assert result.status_code == 200
        assert request_fn.call_count == 3

    def test_rate_limited_response_honours_retry_after(self, ns):
        sleeps = []
        ns["sleep"] = lambda seconds: sleeps.append(seconds)
        request_fn = MagicMock(side_effect=[_response(403, {"X-RateLimit-Remaining": "0", "Retry-After": "5"}), _response(200)])

        result = ns["request_with_retry"](request_fn, "https://api.github.com/repos/x/y/releases")

        assert result.status_code == 200
        assert sleeps == [5]

    def test_a_plain_403_without_the_rate_limit_header_is_not_retried(self, ns):
        """A non-rate-limited 403 cannot recover through retries."""
        request_fn = MagicMock(return_value=_response(403, {}))

        result = ns["request_with_retry"](request_fn, "https://example.invalid")

        assert result.status_code == 403
        assert request_fn.call_count == 1

    def test_a_connection_error_is_retried_like_a_timeout(self, ns):
        connection_error = ns["ConnectionError"]
        request_fn = MagicMock(side_effect=[connection_error("refused"), _response(200)])

        result = ns["request_with_retry"](request_fn, "https://example.invalid")

        assert result.status_code == 200
        assert request_fn.call_count == 2
