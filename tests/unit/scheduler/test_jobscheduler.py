"""JobScheduler — job-definition validation and dispatch payload building.

Construction is light (globs fixed plugin dirs that don't exist locally -> no jobs).
``__validate_jobs`` is name-mangled, accessed as ``_JobScheduler__validate_jobs``.
"""

import logging

import pytest

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
        }

    def test_build_dispatch_item_defaults(self, js):
        job = {"name": "j", "file": "j.py", "path": "/p", "every": "once"}
        item = js._build_dispatch_item(job, "pl")
        assert item["reload"] is False and item["async"] is False
