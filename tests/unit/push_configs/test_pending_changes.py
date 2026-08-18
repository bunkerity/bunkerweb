"""A push that reached nobody must not clear the change flags.

push-configs ends by acknowledging the changes it applied, which clears the database flags. Nothing
else re-raises them, so acknowledging a run that pushed to zero instances loses the configuration:
the fleet keeps serving its previous one until an unrelated change happens along.

Found on a live Autoconf stack. A container restart left every registered instance marked `down`
at the moment push-configs ran; it pushed nothing, acknowledged anyway, and the instance went on
enforcing `USE_MODSECURITY=yes` while the database held `no` — a 5 MB POST that should have
returned 200 was rejected with 400 by ModSecurity.

The distinction that matters, and it is not symmetric: "registered but currently down" is pending
and must not be acknowledged, while "nothing registered at all" must be, because autoconf will not
register an instance until the change flags are clear and only a push clears them. Treating the
two alike deadlocks the bootstrap — tried, observed on an Autoconf stack, reverted.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py"


def _load_definitions():
    """Load definitions only — the module is a script that pushes configs and exits."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    stubs = {name: ModuleType(name) for name in ("redis", "API", "ApiCaller", "Database", "logger", "jobs", "letsencrypt_consistency")}
    stubs["redis"].Redis = Mock()
    stubs["API"].API = Mock()
    stubs["ApiCaller"].ApiCaller = Mock()
    stubs["Database"].Database = Mock()
    stubs["logger"].setup_logger = Mock(return_value=Mock())
    stubs["jobs"]._write_atomic = Mock()
    stubs["letsencrypt_consistency"].le_cache_write_lock = Mock()

    module = ModuleType("bw_push_configs")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    module.LOGGER = Mock()
    return module


PUSH = _load_definitions()


def test_nothing_registered_may_acknowledge():
    """Not a convenience — the autoconf bootstrap deadlocks without it.

    Autoconf refuses to register an instance while any change flag is set (`have_to_wait`, spun
    on by `wait_applying` for 240s inside `expect_errors`, so it waits silently). Only a push
    clears those flags, and a push needs an instance. Holding the flags here instead was tried
    and reverted: on an Autoconf stack the run came up with zero instances and stayed that way,
    autoconf logged `Instances changed` and then nothing, and no configuration was ever pushed.
    """
    assert PUSH.may_acknowledge_without_pushing([]) is True


@pytest.mark.parametrize(
    "registered",
    (
        [{"hostname": "bunkerweb", "status": "down"}],
        [{"hostname": "bw-1", "status": "down"}, {"hostname": "bw-2", "status": "down"}],
        [{"hostname": "bw-1", "status": "failover"}],
    ),
)
def test_registered_but_none_live_must_not_acknowledge(registered):
    # This is the regression: the change is pending, not inapplicable.
    assert PUSH.may_acknowledge_without_pushing(registered) is False


def test_the_predicate_does_not_look_at_status():
    """Deliberate: the caller has already filtered the live ones out.

    `may_acknowledge_without_pushing` is only ever reached when the live list is empty, so its
    single question is whether anything is registered at all. Re-deriving liveness here would
    duplicate the filter and let the two drift apart.
    """
    assert PUSH.may_acknowledge_without_pushing([{"hostname": "bw", "status": "up"}]) is False


def test_acknowledge_changes_clears_exactly_the_applied_flags():
    """The flag set is part of the contract: `plugins_config` in particular gates autoconf.

    Leaving it out stranded the flag with nothing else to clear it, and autoconf's readiness gate
    blocks on it — every configuration change then cost autoconf the full 240s it waits.
    """
    db = Mock()
    db.clear_applied_changes.return_value = ""
    snapshot = {"marker": 1}

    PUSH.acknowledge_changes(db, snapshot, "test")

    db.clear_applied_changes.assert_called_once()
    passed_snapshot, flags = db.clear_applied_changes.call_args[0]
    assert passed_snapshot is snapshot
    assert set(flags) == {"custom_configs", "external_plugins", "pro_plugins", "instances", "plugins_config"}


def test_a_failed_acknowledge_is_logged_and_not_fatal():
    # Leaving a flag set costs a redundant push; clearing it wrongly costs a configuration.
    db = Mock()
    db.clear_applied_changes.return_value = "database is read-only"

    PUSH.acknowledge_changes(db, {}, "test")

    assert PUSH.LOGGER.error.called
