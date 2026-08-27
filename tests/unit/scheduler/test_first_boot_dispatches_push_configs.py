"""The scheduler's first boot must dispatch ``push-configs``, and it does so silently.

Nothing in the scheduler log names ``push-configs`` on a cold boot: ``run_once`` dispatches the
whole once-set in a single ``/jobs/dispatch`` call and logs only ``All jobs in run_once() were
successful``. The explicit ``run_single("push-configs")`` at ``main.py:917`` is gated on
``not FIRST_START``, so it prints nothing on the first pass either. That silence made it look, in
the Kubernetes failure logs of run 32820557847, as though the first boot never dispatched a push
at all -- the string appears exactly twice in 300 KB, once in a harness baseline and once in the
300s watchdog re-dispatch.

The two calls this file pins are the ones that decide it, and they pull in opposite directions:

* ``main.py:882-904`` -- first boot: ``changed_plugins`` is still ``[]`` (initialised at
  ``main.py:874``, only ever populated in the *poll* loop at ``main.py:1109``, i.e. after pass 1),
  and ``run_once`` reads an empty list as "no filter". push-configs IS dispatched.
* every later pass: ``changed_plugins`` holds the plugins whose config moved, ``run_once`` filters
  to exactly those, and the ``jobs`` plugin that owns push-configs is not among them -- which is
  precisely why the explicit ``run_single`` exists. push-configs is NOT dispatched by ``run_once``.

Swap either behaviour and a cold boot stops pushing any configuration until the 300s
``APPLY_RETRY_INTERVAL`` watchdog fires, with no error in any log. The job map here is built from
the shipped ``src/common/core/*/plugin.json`` rather than a fixture, so moving push-configs to
another plugin reds this instead of quietly un-testing it.
"""

import logging
import re
from contextlib import contextmanager
from json import loads
from pathlib import Path

import pytest

from JobScheduler import JobScheduler  # type: ignore  (src/scheduler on path; needs `schedule`)

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "common" / "core"
MAIN = (ROOT / "src" / "scheduler" / "main.py").read_text(encoding="utf-8")

LOGGER = logging.getLogger("first-boot-dispatch")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)


class _Api:
    """Records what reached ``POST /jobs/dispatch`` instead of queueing it."""

    readonly = False

    def __init__(self, worker_stats=None):
        self.dispatched = []
        self.worker_stats = worker_stats or {}
        self.probe_error = None
        self.probe_timeout = None

    def dispatch_jobs(self, items):
        self.dispatched.extend(items)
        return True, []

    @contextmanager
    def expect_errors(self):
        yield

    def _get(self, path, timeout=None):
        assert path == "/jobs/queue"
        self.probe_timeout = timeout
        if self.probe_error is not None:
            raise self.probe_error
        return {
            "status": "success",
            "active": {},
            "scheduled": {},
            "reserved": {},
            "stats": self.worker_stats,
        }


def _shipped_jobs():
    """{plugin_id: [job, ...]} straight from the shipped core plugin manifests."""
    jobs = {}
    for manifest in sorted(CORE.glob("*/plugin.json")):
        plugin = manifest.parent.name
        declared = loads(manifest.read_text(encoding="utf-8")).get("jobs", [])
        for job in declared:
            job["path"] = str(manifest.parent)
        jobs[plugin] = declared
    return jobs


@pytest.fixture
def scheduler():
    js = JobScheduler(LOGGER)
    js.api_client = _Api()
    js._JobScheduler__jobs = _shipped_jobs()
    return js


def _names(scheduler):
    return {item["name"] for item in scheduler.api_client.dispatched}


def test_push_configs_is_owned_by_the_jobs_plugin(scheduler):
    """Precondition. Without it every assertion below could pass on an empty job map."""
    owners = [plugin for plugin, jobs in scheduler._JobScheduler__jobs.items() if any(job["name"] == "push-configs" for job in jobs)]
    assert owners == ["jobs"], f"push-configs is declared by {owners}, this file assumes the 'jobs' plugin"


def test_first_boot_dispatches_push_configs(scheduler):
    """`changed_plugins == []` is no filter, so the cold-boot pass ships the whole once-set."""
    assert scheduler.run_once([], ["misc", "pro", "backup"]) is True
    assert "push-configs" in _names(scheduler)


def test_first_boot_skip_list_never_hides_the_jobs_plugin():
    """`main.py` may skip plugins on the first pass; adding `jobs` there would kill the cold push."""
    match = re.search(r"skipped_plugins = \[([^\]]*)\] if FIRST_START else \[\]", MAIN)
    assert match, "main.py no longer builds skipped_plugins the way this test reads it"
    skipped = set(re.findall(r'"([^"]+)"', match.group(1)))
    extra = set(re.findall(r'skipped_plugins\.append\("([^"]+)"\)', MAIN))
    assert "jobs" not in skipped | extra, "the plugin that owns push-configs is skipped on first boot"


def test_a_filtered_pass_does_not_dispatch_push_configs(scheduler):
    """The complement, and the reason `run_single("push-configs")` exists at main.py:917."""
    changed = ["blacklist", "bunkernet", "general", "inject", "misc", "redis"]  # the real set from the failing run
    assert scheduler.run_once(changed, []) is True
    dispatched = _names(scheduler)
    assert dispatched, "the filtered pass dispatched nothing at all, so this asserts nothing"
    assert "push-configs" not in dispatched


def test_the_explicit_dispatch_is_gated_off_on_the_first_pass():
    """So the first boot depends on run_once alone — there is no second chance until the watchdog."""
    assert "if CONFIG_NEED_GENERATION and not FIRST_START:" in MAIN
    assert 'SCHEDULER.run_single("push-configs")' in MAIN


def test_a_readonly_database_makes_the_dispatch_a_silent_no_op(scheduler):
    """`run_once` keeps its read-only no-op contract; the liveness check is separate.

    Not the cause of the Kubernetes failures -- `Database is in read-only mode, jobs will not be
    dispatched` appears zero times in all three captured logs -- but it remains the one path where
    a successful return does not mean anything was queued, so it belongs in the record next to the
    assertions above.
    """
    scheduler.api_client.readonly = True
    assert scheduler.run_once([], None) is True
    assert scheduler.api_client.dispatched == []


def test_first_boot_live_worker_check_is_silent(scheduler, caplog):
    scheduler.api_client.worker_stats = {"celery@worker": {"pool": {"max-concurrency": 1}}}

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="first-boot-dispatch"):
        assert scheduler.confirm_worker_liveness() is True

    assert caplog.records == []


def test_first_boot_confirms_a_worker_before_reporting_success():
    assert "if not FIRST_START or SCHEDULER.confirm_worker_liveness():" in MAIN


def test_first_boot_no_worker_warns_without_raising(scheduler, caplog, monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:secret@bw-jobs-broker:6379/0")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="first-boot-dispatch"):
        assert scheduler.confirm_worker_liveness() is False

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "No Celery worker responded" in message
    assert "redis://***@bw-jobs-broker:6379/0" in message
    assert "secret" not in message


def test_first_boot_probe_is_bounded(scheduler):
    """The probe must not inherit the client's 30s default timeout (×2 with the retry)."""
    scheduler.api_client.worker_stats = {"celery@worker": {}}
    assert scheduler.confirm_worker_liveness() is True
    assert scheduler.api_client.probe_timeout == 10


def test_first_boot_redaction_survives_an_at_sign_in_the_password(scheduler, caplog, monkeypatch):
    """`[^/]*` runs to the LAST @ before the path; `[^@/]*` stopped at the first and leaked the tail."""
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://user:p@ssw0rd@bw-jobs-broker:6379/0")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="first-boot-dispatch"):
        assert scheduler.confirm_worker_liveness() is False

    message = caplog.records[0].getMessage()
    assert "redis://***@bw-jobs-broker:6379/0" in message
    assert "ssw0rd" not in message


def test_first_boot_probe_failure_warns_with_the_cause(scheduler, caplog, monkeypatch):
    """A 503/timeout/dead API must not raise, and the warning must say WHY the probe failed --
    an empty-stats broker and an unreachable API are different repairs."""
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://bw-jobs-broker:6379/0")
    scheduler.api_client.probe_error = RuntimeError("API unreachable (GET /jobs/queue)")

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="first-boot-dispatch"):
        assert scheduler.confirm_worker_liveness() is False

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "No Celery worker responded" in message
    assert "probe failed: API unreachable (GET /jobs/queue)" in message
