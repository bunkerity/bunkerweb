"""push-configs is the only producer of the UI's NGINX failover banner.

The instance row's ``failover`` status lives one scheduler pass, and the scheduler loop no longer
writes ``bw_metadata.failover``. push-configs sees the reload responses, so it records a refused
reload (flag + NGINX output) and clears it on the next clean one. An unreachable instance answers
nothing and is never a failover (M18); an outage must not erase an earlier real refusal either.
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
CLEARED = {"failover": False, "failover_message": ""}


def _record(responses):
    db = Mock()
    db.set_metadata.return_value = ""
    PUSH._record_failover(db, responses)
    return db


def test_a_refused_reload_records_the_flag_and_the_nginx_output():
    db = _record({"bw-1": REFUSED})
    (payload,), _ = db.set_metadata.call_args
    assert payload["failover"] is True
    assert "bw-1" in payload["failover_message"] and "unknown directive" in payload["failover_message"]


def test_only_the_refusing_instance_is_named():
    db = _record({"bw-1": OK, "bw-2": REFUSED})
    (payload,), _ = db.set_metadata.call_args
    assert payload["failover"] is True
    assert "bw-2" in payload["failover_message"] and "bw-1" not in payload["failover_message"]


def test_a_clean_reload_clears_the_flag():
    db = _record({"bw-1": OK, "bw-2": OK})
    db.set_metadata.assert_called_once_with(CLEARED)


def test_an_unreachable_instance_next_to_a_clean_one_clears_and_never_raises():
    db = _record({"bw-1": OK})
    db.set_metadata.assert_called_once_with(CLEARED)


def test_an_outage_leaves_an_earlier_refusal_alone():
    db = _record({})
    db.set_metadata.assert_not_called()


def test_a_metadata_write_error_is_logged_not_raised():
    db = Mock()
    db.set_metadata.return_value = "read-only"
    PUSH._record_failover(db, {"bw-1": REFUSED})
    PUSH.LOGGER.error.assert_called()


def test_the_reload_keeps_the_instance_answers():
    caller = Mock()
    caller.apis = []
    caller.send_to_apis.return_value = (False, {"bw-1": REFUSED})
    sent, responses = PUSH._trigger_reload(caller)
    assert sent is False and responses == {"bw-1": REFUSED}
    assert caller.send_to_apis.call_args.kwargs["response"] is True
