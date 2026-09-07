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

    def test_something_installed_this_run_proceeds_when_nothing_failed(self, ns, tmp_path):
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


class TestAPartialRunKeepsThePreviousPluginSet:
    """A run where SOME plugins installed and at least one failed must publish nothing.

    Ported with dev ``a92cc3187``. ``should_keep_previous_cache`` alone cannot see this case, and
    said so in its own docstring: ``service_plugins[service] = plugins`` aliases the resolved URL
    set in as soon as a LOOKUP succeeds, so ``any(service_plugins.values())`` is already True
    before a single byte is downloaded. Measured on the pre-fix file: with plugin-a's download
    failed and plugin-b's succeeded, the swap went ahead, CRS_PLUGINS_DIR ended up holding only
    plugin-b, the incomplete set was written to the job cache, and the job exited 1 (success).
    The rendered conf is the intersection of crs-plugins.json and that directory, so plugin-a's
    rules silently left the WAF and the next run's fingerprint matched -- no retry, ever.
    """

    @pytest.fixture
    def swap(self, ns, tmp_path):
        """`swap_and_cache_plugins` wired to tmp dirs. It starts with `rmtree(CRS_PLUGINS_DIR)`
        against the real /var/cache path, so it is never called without this redirection."""
        previous = tmp_path / "crs"
        staging = tmp_path / "new"
        for plugin_id in ("plugin-a-1.0", "plugin-b-1.0"):
            (previous / plugin_id).mkdir(parents=True)
            (previous / plugin_id / "plugin.conf").write_text("SecRule previous\n")
        (staging / "plugin-b-1.0").mkdir(parents=True)  # only plugin-b came down this run
        (staging / "plugin-b-1.0" / "plugin.conf").write_text("SecRule fresh\n")

        job = MagicMock()
        job.cache_hash.return_value = b""
        job.cache_file.return_value = (True, "")
        job.cache_dir.return_value = (True, "")

        ns["CRS_PLUGINS_DIR"] = previous
        ns["NEW_PLUGINS_DIR"] = staging
        ns["JOB"] = job
        ns["status"] = 0
        return ns, previous, job

    def test_a_failure_leaves_the_previous_set_and_the_job_cache_untouched(self, swap):
        ns, previous, job = swap

        render_changed = ns["swap_and_cache_plugins"]({"svc": {"https://example.invalid/b.zip"}}, True)

        assert sorted(p.name for p in previous.iterdir()) == ["plugin-a-1.0", "plugin-b-1.0"]
        assert (previous / "plugin-a-1.0" / "plugin.conf").read_text() == "SecRule previous\n"
        assert (previous / "plugin-b-1.0" / "plugin.conf").read_text() == "SecRule previous\n", "the staged copy was published anyway"
        job.cache_file.assert_not_called()
        job.cache_dir.assert_not_called()
        assert ns["status"] == 2, "a partial run must report a failure, not a success"
        assert render_changed is False, "no re-render for a set that was never published"

    def test_a_clean_run_still_publishes(self, swap):
        """The guard must not be a blanket refusal: without a failure the swap still happens."""
        ns, previous, job = swap

        render_changed = ns["swap_and_cache_plugins"]({"svc": {"https://example.invalid/b.zip"}}, False)

        assert sorted(p.name for p in previous.iterdir()) == ["plugin-b-1.0"]
        assert (previous / "plugin-b-1.0" / "plugin.conf").read_text() == "SecRule fresh\n"
        job.cache_file.assert_called_once()
        job.cache_dir.assert_called_once()
        assert ns["status"] == 0
        assert render_changed is True

    def test_the_flag_alone_decides_regardless_of_what_resolved(self, ns, tmp_path):
        """`plugin_failures` is unconditional: it does not need a previous set to protect.

        On a first run there is nothing cached, so the emptiness half of the predicate is False;
        publishing an incomplete set as though it were complete is still the worse outcome.
        """
        crs_dir = tmp_path / "crs"  # never created -- cold start, nothing to keep

        assert ns["should_keep_previous_cache"]({"svc": {"plugin-1.0"}}, crs_dir, True) is True
        assert ns["should_keep_previous_cache"]({"svc": {"plugin-1.0"}}, crs_dir, False) is False
