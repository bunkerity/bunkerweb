"""A retry of deploy-certificates must not acknowledge what the first run failed to deliver.

Run 1 writes the certificate material to the worker's cache and exits 1, so the push and the reload
happen afterwards. If that push fails, the change flag stays raised and the scheduler re-dispatches
the job — the whole point of deferring the acknowledgement.

Run 2 then finds its own material already in the cache. The fingerprint check short-circuits every
service, so nothing is written, `status` stays 0, and the old code took that as "nothing to
deliver" and cleared the flag: the compare-and-set matched (no new change had moved the watermark),
the flag went down, and no push had ever reached the instances. `push-configs` runs `once`, so
nothing re-pushed. Every instance kept serving the previous certificate, with two successful job
runs as the only evidence.

Same failure class as the push-configs bug: acknowledging work that was not delivered.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "certificates" / "jobs" / "deploy-certificates.py"


def _load_definitions():
    """Definitions only — the module body deploys certificates and exits."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    names = ("Database", "logger", "jobs", "model", "common_utils")
    stubs = {name: ModuleType(name) for name in names}
    stubs["Database"].Database = Mock()
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["logger"].getLogger = Mock(return_value=Mock())
    stubs["jobs"].Job = Mock()
    stubs["jobs"].defer_change_acknowledgement = Mock(return_value="")
    stubs["model"].Certificates = Mock()
    stubs["common_utils"].bytes_hash = Mock()

    module = ModuleType("bw_deploy_certificates")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


JOB = _load_definitions()


def test_a_retry_that_wrote_nothing_asks_for_the_push_instead_of_acknowledging():
    """The undelivered case: nothing written, flag still raised."""
    assert JOB.must_push_instead_of_acknowledging(0, {"certificates_changed": True}) is True


def test_a_run_that_wrote_material_is_left_alone():
    """status 1 already defers and already triggers a reload — this must not touch it."""
    assert JOB.must_push_instead_of_acknowledging(1, {"certificates_changed": True}) is False


def test_a_routine_run_with_nothing_pending_does_not_push():
    """The common case by far: the periodic run, no change, no work. It must stay silent, or every
    instance in the fleet eats a pointless push and reload on this job's schedule."""
    assert JOB.must_push_instead_of_acknowledging(0, {"certificates_changed": False}) is False


@pytest.mark.parametrize("snapshot", ({}, {"certificates_changed": None}))
def test_an_absent_or_empty_flag_is_not_a_pending_change(snapshot):
    """`get_metadata` falls back to a default dict on a database error; a missing key must read as
    "nothing pending" rather than pushing the fleet every run."""
    assert JOB.must_push_instead_of_acknowledging(0, snapshot) is False


def test_a_failed_run_never_acknowledges_and_never_pushes():
    """status 2 is an error: the flag stays raised on its own and the job exits non-zero. Turning
    that into a reload request would report a delivery for material that failed to be written."""
    assert JOB.must_push_instead_of_acknowledging(2, {"certificates_changed": True}) is False
