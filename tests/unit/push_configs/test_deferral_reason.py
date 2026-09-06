"""push-configs' deferral branch has to tell the worker WHY it left the change flags pending.

"Every registered instance is down" is a routine, expected state (a restart, a rolling upgrade)
and `push-configs` correctly leaves the change pending rather than acknowledging it -- see
`test_pending_changes.py`. But `sys_exit(0)` alone carries no reason, and `Jobs_runs.success=True`
with no `error` is exactly what an ordinary "ran, changed nothing" run also looks like. The fix
under test is two lines right before that `sys_exit(0)`: log the reason (already there) and hand
the SAME string to `jobs.note_deferral`, so `src/worker/tasks.py` can fold it into the run row
(covered separately in `tests/unit/worker/test_job_deferral_reason.py`).

Unlike `test_pending_changes.py`/`test_lease.py`, this loads the FULL module -- including its
top-level `try/except` -- rather than stripping to definitions only, because the call under test
lives inline in that top-level block, not in a standalone function. `jobs` is deliberately left
unstubbed (real `note_deferral`/`drain_deferral_reason`): the point is to prove push-configs
reaches the real relay, not a mock of it.
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from jobs import drain_deferral_reason

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"
SOURCE = JOB_PATH.read_text(encoding="utf-8")


class _FakeRedis:
    """Just enough to let `acquire_lease` succeed on the first `SET NX` and the `finally` release
    to no-op -- the lease itself is not what this test is about."""

    def set(self, *_args, **_kwargs):
        return True

    def delete(self, *_args, **_kwargs):
        return True


def _run_until_exit(registered_instances):
    """Execute the real push-configs script up to its first `sys_exit`, with every registered
    instance down. Returns the `SystemExit` raised."""
    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["redis"].Redis.from_url = Mock(return_value=_FakeRedis())
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    db = Mock()
    db.get_instances = Mock(return_value=registered_instances)
    db.delete_job_cache = Mock(return_value="")
    db.get_metadata = Mock(return_value={})
    stubs["Database"].Database = Mock(return_value=db)
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs_full")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        with pytest.raises(SystemExit) as exc_info:
            exec(compile(SOURCE, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return exc_info.value


REGISTERED_ALL_DOWN = [{"hostname": "bunkerweb", "status": "down", "credential": "x"}]


@pytest.fixture(autouse=True)
def _empty_queue():
    drain_deferral_reason()
    yield
    drain_deferral_reason()


def test_the_deferral_branch_records_a_reason():
    exc = _run_until_exit(REGISTERED_ALL_DOWN)

    assert exc.code == 0  # a deferral is not a failure
    reason = drain_deferral_reason()
    assert reason is not None, "push-configs deferred but noted no reason for the worker to record"
    assert "1 registered BunkerWeb instance(s) are down" in reason


def test_the_recorded_reason_is_the_same_string_that_was_logged():
    """Not a second, independently-worded reason -- the operator reading the worker log and the
    operator reading the Jobs page must see the same sentence."""
    exc = _run_until_exit(REGISTERED_ALL_DOWN)
    assert exc.code == 0

    reason = drain_deferral_reason()
    assert reason == "All 1 registered BunkerWeb instance(s) are down; leaving the changes pending for a later run"


def test_mutation_dropping_the_note_deferral_call_leaves_the_drain_empty():
    """Pins the two-line fix in place: without `note_deferral(reason)` the deferral still exits 0
    (that half already worked -- see `test_pending_changes.py`) but the worker gets nothing to
    record, reproducing the exact defect this lane fixes.
    """
    mutated = SOURCE.replace("            note_deferral(reason)\n", "")
    assert mutated != SOURCE, "mutation did not apply; the call no longer reads `note_deferral(reason)`"

    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["redis"].Redis.from_url = Mock(return_value=_FakeRedis())
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    db = Mock()
    db.get_instances = Mock(return_value=REGISTERED_ALL_DOWN)
    db.delete_job_cache = Mock(return_value="")
    db.get_metadata = Mock(return_value={})
    stubs["Database"].Database = Mock(return_value=db)
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs_mutated")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        with pytest.raises(SystemExit):
            exec(compile(mutated, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102

    assert drain_deferral_reason() is None
