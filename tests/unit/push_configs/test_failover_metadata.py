"""push-configs feeds the UI's NGINX failover banner from what each instance answered to the reload.

The instance row's ``failover`` status lives one scheduler pass, and the scheduler loop no longer
writes ``bw_metadata.failover``. push-configs sees the reload responses and records them per host
(`Database.record_reload_outcome`): a refusal raises that host's entry with the NGINX output, an
accepted reload drops it. An unreachable or busy instance gives no verdict and is never a failover
(M18); an outage must not erase an earlier real refusal either.
"""

import ast
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

JOB_PATH = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


def _load_definitions():
    """Load definitions only -- the module is a script that pushes configs and exits."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "jobs", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["Database"].Database = Mock()
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["jobs"]._write_atomic = Mock()
    stubs["jobs"].note_deferral = Mock()
    stubs["jobs"].cache_publication_lock = lambda *a, **k: nullcontext(True)
    stubs["jobs"].CachePublicationLockError = type("CachePublicationLockError", (RuntimeError,), {})
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs_failover")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


PUSH = _load_definitions()
REFUSED = {"status": "error", "msg": 'config check failed: nginx: [emerg] unknown directive "bogus"'}
OK = {"status": "success", "msg": "reloaded"}
BUSY = {"status": "error", "msg": "a configuration swap is still in progress"}


def _record(responses, **kwargs):
    db = Mock()
    db.record_reload_outcome.return_value = ""
    PUSH._record_failover(db, responses, **kwargs)
    return db


def test_a_refused_reload_records_that_host_with_the_nginx_output():
    db = _record({"bw-1": REFUSED})
    db.record_reload_outcome.assert_called_once_with({"bw-1": REFUSED["msg"]}, fleet=True)


def test_each_host_keeps_its_own_verdict():
    db = _record({"bw-1": OK, "bw-2": REFUSED})
    db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": REFUSED["msg"]}, fleet=True)


def test_a_clean_reload_records_every_host_as_accepted():
    db = _record({"bw-1": OK, "bw-2": OK})
    db.record_reload_outcome.assert_called_once_with({"bw-1": None, "bw-2": None}, fleet=True)


def test_a_targeted_push_is_not_a_fleet_reload():
    db = _record({"bw-1": OK}, fleet=False)
    db.record_reload_outcome.assert_called_once_with({"bw-1": None}, fleet=False)


def test_an_outage_leaves_an_earlier_refusal_alone():
    db = _record({})
    db.record_reload_outcome.assert_not_called()


def test_a_busy_instance_is_not_a_verdict():
    db = _record({"bw-1": BUSY})
    db.record_reload_outcome.assert_not_called()


def test_a_metadata_write_error_is_logged_not_raised():
    db = Mock()
    db.record_reload_outcome.return_value = "boom"
    PUSH._record_failover(db, {"bw-1": REFUSED})
    PUSH.LOGGER.error.assert_called()


def test_the_main_flow_tells_a_targeted_push_from_a_fleet_one():
    """A push to a subset must not be able to end a fleet-wide legacy refusal."""
    source = JOB_PATH.read_text(encoding="utf-8")
    assert "_record_failover(db, reload_responses, fleet=not target_hostnames)" in source


def test_the_reload_keeps_the_instance_answers():
    caller = Mock()
    caller.apis = []
    caller.send_to_apis.return_value = (False, {"bw-1": REFUSED})
    sent, responses = PUSH._trigger_reload(caller)
    assert sent is False and responses == {"bw-1": REFUSED}
    assert caller.send_to_apis.call_args.kwargs["response"] is True
