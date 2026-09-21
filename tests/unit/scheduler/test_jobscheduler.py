"""JobScheduler — job-definition validation and dispatch payload building.

Construction is light (globs fixed plugin dirs that don't exist locally -> no jobs).
``__validate_jobs`` is name-mangled, accessed as ``_JobScheduler__validate_jobs``.
"""

import logging
from datetime import time
from unittest.mock import MagicMock

import pytest
import schedule

from JobScheduler import JobScheduler  # type: ignore  (src/scheduler on path; needs `schedule`)

LOGGER = logging.getLogger("sched-test")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)


@pytest.fixture
def js():
    return JobScheduler(LOGGER)


def _validate(js, jobs):
    return js._JobScheduler__validate_jobs(jobs, "plug", "/path/plugin.json")


class TestValidateJobs:
    def test_valid_job_gets_path(self, js):
        out = _validate(js, [{"name": "myjob", "file": "myjob.py", "every": "hour", "reload": True}])
        assert len(out) == 1
        assert out[0]["path"] == "/path"  # dirname(plugin_file) injected

    def test_missing_keys_skipped(self, js):
        assert _validate(js, [{"name": "x"}]) == []

    def test_invalid_every_skipped(self, js):
        assert _validate(js, [{"name": "j", "file": "j.py", "every": "fortnight", "reload": True}]) == []

    def test_invalid_name_skipped(self, js):
        assert _validate(js, [{"name": "bad name!", "file": "j.py", "every": "hour", "reload": True}]) == []

    def test_non_bool_reload_skipped(self, js):
        assert _validate(js, [{"name": "j", "file": "j.py", "every": "hour", "reload": "yes"}]) == []

    def test_mixed_keeps_only_valid(self, js):
        out = _validate(
            js,
            [
                {"name": "good", "file": "g.py", "every": "day", "reload": False},
                {"name": "bad!", "file": "b.py", "every": "day", "reload": False},
            ],
        )
        assert [j["name"] for j in out] == ["good"]


class TestBuildDispatchItem:
    def test_build_dispatch_item(self, js):
        job = {"name": "j", "file": "j.py", "path": "/p", "every": "hour", "reload": True, "async": False}
        assert js._build_dispatch_item(job, "myplugin") == {
            "name": "j",
            "plugin_id": "myplugin",
            "file": "j.py",
            "path": "/p",
            "every": "hour",
            "reload": True,
            "async": False,
            "regenerate": False,
        }

    def test_build_dispatch_item_defaults(self, js):
        job = {"name": "j", "file": "j.py", "path": "/p", "every": "once"}
        item = js._build_dispatch_item(job, "pl")
        assert item["reload"] is False and item["async"] is False and item["regenerate"] is False


class TestStrToSchedule:
    """__str_to_schedule reads JOBS_DAILY_TIME/JOBS_WEEKLY_DAY from the process env at call
    time (same os.getenv pattern as CELERY_BROKER_URL, JobScheduler.py:233), so no fixture
    re-instantiates JobScheduler to pick up an env change — the `js` fixture is enough.

    Every case also calls ``.do()`` (production always does, JobScheduler.py:264) and asserts
    on ``next_run``: ``.at_time``/``.start_day`` alone are set before ``_schedule_next_run``
    runs and would stay green even if a `schedule` upgrade broke that computation.
    """

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch):
        monkeypatch.delenv("JOBS_DAILY_TIME", raising=False)
        monkeypatch.delenv("JOBS_WEEKLY_DAY", raising=False)
        schedule.clear()
        yield
        schedule.clear()

    def test_day_defaults_to_0300(self, js):
        job = js._JobScheduler__str_to_schedule("day").do(lambda: None)
        assert job.at_time == time(3, 0)
        assert (job.next_run.hour, job.next_run.minute) == (3, 0)

    def test_day_and_week_honor_env(self, js, monkeypatch):
        monkeypatch.setenv("JOBS_DAILY_TIME", "22:15")
        monkeypatch.setenv("JOBS_WEEKLY_DAY", "tuesday")

        day_job = js._JobScheduler__str_to_schedule("day").do(lambda: None)
        assert day_job.at_time == time(22, 15)
        assert (day_job.next_run.hour, day_job.next_run.minute) == (22, 15)

        week_job = js._JobScheduler__str_to_schedule("week").do(lambda: None)
        assert week_job.start_day == "tuesday"
        assert week_job.at_time == time(22, 15)
        assert (week_job.next_run.hour, week_job.next_run.minute) == (22, 15)
        assert week_job.next_run.strftime("%A").lower() == "tuesday"

    def test_invalid_daily_time_falls_back_and_warns(self, js, monkeypatch):
        monkeypatch.setenv("JOBS_DAILY_TIME", "not-a-time")
        js._JobScheduler__logger = MagicMock()

        job = js._JobScheduler__str_to_schedule("day").do(lambda: None)

        assert job.at_time == time(3, 0)
        assert (job.next_run.hour, job.next_run.minute) == (3, 0)
        js._JobScheduler__logger.warning.assert_called_once()

    def test_invalid_weekly_day_falls_back_and_warns(self, js, monkeypatch):
        monkeypatch.setenv("JOBS_WEEKLY_DAY", "someday")
        js._JobScheduler__logger = MagicMock()

        job = js._JobScheduler__str_to_schedule("week").do(lambda: None)

        assert job.start_day == "sunday"
        assert job.next_run.strftime("%A").lower() == "sunday"
        js._JobScheduler__logger.warning.assert_called_once()

    def test_minute_and_hour_unchanged(self, js):
        # Pre-existing behavior, not red-then-green: this passes identically against the
        # unfixed code (minute/hour branches are untouched). Kept as a regression guard.
        assert js._JobScheduler__str_to_schedule("minute").unit == "minutes"
        assert js._JobScheduler__str_to_schedule("hour").unit == "hours"
