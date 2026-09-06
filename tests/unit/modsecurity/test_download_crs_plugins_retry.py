"""`download-crs-plugins.py`'s retry/backoff and cache-preservation, added against a CI red
(run 33528164796, jobs 99927461927 / 99930908983): a GitHub API `ReadTimeoutError` on the
release lookup was never caught (the old loop only retried `ConnectionError`), so the job
crashed with an unhandled exception and reported no plugins installed -- "Failed to deduce the
download URL" -> nothing installed -> the wordpress exclusion plugin missing -> the spec's
request gets 403.

Two things changed, both covered here:
  * `request_with_retry` -- retries a timeout/connection error/5xx/rate-limited response up to
    3 times (4 total attempts) with 2/4/8s backoff (honouring a capped `Retry-After`), instead of
    only catching `ConnectionError` with a flat 3s delay.
  * `should_keep_previous_cache` -- the predicate guarding the final CRS_PLUGINS_DIR swap: if
    nothing was installed this run but a previous run's plugin set is still on disk, keep it
    rather than replacing it with nothing.

Both are exec'd from the job file's own source (see `crs_plugins_job_source.load_job_helpers`),
not re-typed, so this exercises the actual production code. `load_job_helpers()` returns the
exact namespace dict the exec'd functions close over as `__globals__`, so patching `ns["sleep"]`
in place is enough to stub the delay -- no need to touch the real `time.sleep`.
"""

from unittest.mock import MagicMock

import pytest

from crs_plugins_job_source import load_job_helpers


@pytest.fixture
def ns():
    namespace = load_job_helpers()
    namespace["sleep"] = lambda *_args: None  # stub the 2/4/8s backoff so tests run fast
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

    def test_exhausts_retries_and_reraises_the_last_timeout(self, ns):
        sleeps = []
        ns["sleep"] = lambda seconds: sleeps.append(seconds)
        timeout_error = ns["Timeout"]
        request_fn = MagicMock(side_effect=[timeout_error("1"), timeout_error("2"), timeout_error("3"), timeout_error("4")])

        with pytest.raises(timeout_error):
            ns["request_with_retry"](request_fn, "https://example.invalid", timeout=8)

        assert request_fn.call_count == 4
        assert sleeps == [2, 4, 8], "all three backoff values must be reachable, not just the first two"

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

    def test_a_multi_minute_retry_after_is_capped_to_the_longest_backoff(self, ns):
        """GitHub's primary rate limit sends `Retry-After` in MINUTES. Honouring it uncapped can
        sleep past Celery's `task_soft_time_limit` (src/worker/app.py) and lose the job on kill
        (Criticos round 2, concern 4) -- the value must never exceed max(RETRY_BACKOFFS_SECONDS)."""
        sleeps = []
        ns["sleep"] = lambda seconds: sleeps.append(seconds)
        request_fn = MagicMock(side_effect=[_response(403, {"X-RateLimit-Remaining": "0", "Retry-After": "300"}), _response(200)])

        result = ns["request_with_retry"](request_fn, "https://api.github.com/repos/x/y/releases")

        assert result.status_code == 200
        assert sleeps == [max(ns["RETRY_BACKOFFS_SECONDS"])]

    def test_always_fails_returns_the_last_bad_response_after_exhausting_retries(self, ns):
        sleeps = []
        ns["sleep"] = lambda seconds: sleeps.append(seconds)
        request_fn = MagicMock(return_value=_response(503))

        result = ns["request_with_retry"](request_fn, "https://example.invalid")

        assert result.status_code == 503
        assert request_fn.call_count == 4
        # The 5xx branch's own fallback schedule, not the Retry-After path (pinned separately by
        # test_rate_limited_response_honours_retry_after) -- both must independently reach 8s.
        assert sleeps == [2, 4, 8]

    def test_a_plain_403_without_the_rate_limit_header_is_not_retried(self, ns):
        """An auth/permission 403 must not be treated as a rate limit -- retrying it 3 times
        just delays a failure that will never resolve itself."""
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


class TestShouldKeepPreviousCache:
    def test_nothing_installed_and_something_cached_keeps_it(self, ns, tmp_path):
        crs_dir = tmp_path / "crs"
        crs_dir.mkdir()
        (crs_dir / "some-plugin").mkdir()

        assert ns["should_keep_previous_cache"]({"svc": set()}, crs_dir) is True

    def test_nothing_installed_and_nothing_cached_does_not_block_the_swap(self, ns, tmp_path):
        crs_dir = tmp_path / "crs"  # never created -- the cold-start case

        assert ns["should_keep_previous_cache"]({"svc": set()}, crs_dir) is False

    def test_something_installed_this_run_always_proceeds(self, ns, tmp_path):
        crs_dir = tmp_path / "crs"
        crs_dir.mkdir()
        (crs_dir / "old-plugin").mkdir()

        assert ns["should_keep_previous_cache"]({"svc": {"new-plugin-1.0"}}, crs_dir) is False

    def test_an_existing_but_empty_directory_does_not_count_as_cached(self, ns, tmp_path):
        crs_dir = tmp_path / "crs"
        crs_dir.mkdir()  # exists, but empty -- e.g. a fresh install that never installed anything

        assert ns["should_keep_previous_cache"]({"svc": set()}, crs_dir) is False

    def test_multiple_services_only_one_with_a_result_still_proceeds(self, ns, tmp_path):
        crs_dir = tmp_path / "crs"
        crs_dir.mkdir()
        (crs_dir / "old-plugin").mkdir()

        assert ns["should_keep_previous_cache"]({"a": set(), "b": {"plugin-1.0"}}, crs_dir) is False
