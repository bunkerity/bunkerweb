"""`send_pending_reports` — a killed run must not re-send batches it already delivered.

bunkernet-send used to persist the outstanding reports only after every batch had gone out.
Delivery is at-least-once, and this job spends nearly all its wall-clock in the two-second sleep
between batches, so a worker killed there was redelivered, re-read an untouched reports.json and
re-sent every batch it had already delivered — duplicating reports on BunkerNet in proportion to
how far it got.

The invariant these tests protect: after each successful batch, what is persisted is exactly the
reports still owed. Anything already sent is gone from the persisted state.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "bunkernet" / "jobs" / "bunkernet-send.py"


def _load_definitions():
    """Load definitions only — the module is a script that sends reports and exits."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("bunkernet", "API", "ApiCaller", "logger", "jobs")}
    stubs["bunkernet"].send_reports = Mock()
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["logger"].getLogger = Mock(return_value=Mock())
    stubs["jobs"].Job = Mock()

    module = ModuleType("bw_bunkernet_send")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    # The real one sleeps 2s between batches; tests would take minutes.
    module.sleep = Mock()
    return module


SEND = _load_definitions()
BATCH_SIZE = SEND.BATCH_SIZE


def _reports(count):
    return [{"date": f"2026-07-31T00:00:{i:02d}+00:00", "id": i} for i in range(count)]


class Recorder:
    """Captures what each persist call was handed, in order."""

    def __init__(self, fail_on=None):
        self.snapshots = []
        self.fail_on = fail_on

    def __call__(self, remaining):
        self.snapshots.append(list(remaining))
        return not (self.fail_on is not None and len(self.snapshots) == self.fail_on)


def _ok_sender(sent):
    def send(batch):
        sent.append(list(batch))
        return True, 200, {}

    return send


class TestPersistPerBatch:
    def test_every_delivered_batch_is_persisted_before_the_next_one(self):
        sent, persist = [], Recorder()

        remaining, cache_failed = SEND.send_pending_reports(_reports(BATCH_SIZE * 3), False, _ok_sender(sent), persist, Mock())

        assert len(sent) == 3, "all three full batches should have been sent"
        assert cache_failed is False
        assert remaining == []
        # One persist per delivered batch, each holding only what was still owed.
        assert [len(snap) for snap in persist.snapshots] == [BATCH_SIZE * 2, BATCH_SIZE, 0]

    def test_a_persisted_snapshot_never_contains_an_already_sent_report(self):
        """The actual anti-duplication property, stated over ids rather than counts."""
        sent, persist = [], Recorder()

        SEND.send_pending_reports(_reports(BATCH_SIZE * 2), False, _ok_sender(sent), persist, Mock())

        # Without this the loop below is vacuous, and a build that persists nothing at all —
        # the exact bug under test — would pass.
        assert len(persist.snapshots) == len(sent) == 2

        delivered = set()
        for batch, snapshot in zip(sent, persist.snapshots):
            delivered.update(report["id"] for report in batch)
            still_owed = {report["id"] for report in snapshot}
            assert not (delivered & still_owed), "a report that was already sent is still marked as owed — a redelivery would re-send it"

    def test_nothing_is_persisted_when_there_is_nothing_to_send(self):
        persist = Recorder()

        remaining, cache_failed = SEND.send_pending_reports(_reports(BATCH_SIZE - 1), False, _ok_sender([]), persist, Mock())

        assert persist.snapshots == [], "a run below the batch threshold should not write"
        assert len(remaining) == BATCH_SIZE - 1
        assert cache_failed is False

    def test_force_send_delivers_a_partial_batch(self):
        sent, persist = [], Recorder()

        remaining, _ = SEND.send_pending_reports(_reports(10), True, _ok_sender(sent), persist, Mock())

        assert len(sent) == 1 and len(sent[0]) == 10
        assert remaining == []
        assert persist.snapshots == [[]]


class TestFailurePaths:
    def test_a_refused_batch_goes_back_and_is_not_persisted_as_sent(self):
        sent, persist = [], Recorder()

        def send(batch):
            sent.append(list(batch))
            return True, 429, {}

        remaining, cache_failed = SEND.send_pending_reports(_reports(BATCH_SIZE * 2), False, send, persist, Mock())

        assert len(sent) == 1, "the loop must stop at the rate limit, not keep hammering"
        assert len(remaining) == BATCH_SIZE * 2, "the refused batch must be put back"
        assert persist.snapshots == [], "nothing was delivered, so nothing may be recorded as delivered"
        assert cache_failed is False

    def test_a_transport_error_puts_the_batch_back(self):
        remaining, cache_failed = SEND.send_pending_reports(_reports(BATCH_SIZE), False, lambda batch: (False, 0, "boom"), Recorder(), Mock())

        assert len(remaining) == BATCH_SIZE
        assert cache_failed is False

    def test_a_failed_persist_stops_the_loop_and_is_reported(self):
        """Continuing past a failed write would send batches with no record that they went out —
        exactly the duplication this exists to prevent, only worse."""
        sent, persist = [], Recorder(fail_on=1)

        remaining, cache_failed = SEND.send_pending_reports(_reports(BATCH_SIZE * 3), False, _ok_sender(sent), persist, Mock())

        assert len(sent) == 1, "the loop must stop once it can no longer record progress"
        assert cache_failed is True, "the caller needs this to set a failing exit status"
        assert len(remaining) == BATCH_SIZE * 2
