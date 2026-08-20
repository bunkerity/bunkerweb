"""F-SCHED-3: `certbot-new` must not start issuing before `push-configs` has delivered.

The scheduler dispatches both in the same `run_once` batch and both are HEAVY_JOBS, so with
`--concurrency=2` they run side by side. certbot can therefore begin an HTTP-01 validation before
the instances have the challenge location (`confs/server-http/lets-encrypt.conf`) or the service's
own server block, and with `LETS_ENCRYPT_MAX_RETRIES` defaulting to 0 the whole run is two attempts
30 seconds apart -- a slow push costs every service its certificate for that boot.

What is asserted here is the *intent* the ruling fixed, not the code's current shape:

  * the readiness predicate is push-configs' own acknowledgement list -- nothing new to keep in
    sync, and all-clear genuinely means delivered because since 1.7 those flags are cleared by the
    run that pushed (`Database.clear_applied_changes`);
  * a deferral NEVER sleeps -- blocking holds one of the two heavy prefork children, and two
    waiting certbot runs would deadlock the lane against the push they are waiting for;
  * a deferral is LOUD -- from the outside a deferred run is indistinguishable from a run with
    nothing to do, so a precondition that never becomes true would otherwise be invisible;
  * the gate can never permanently prevent issuance. An instance that stays down keeps those flags
    raised forever; once the budget is spent the run proceeds exactly as it did before the gate.

`certbot-new.py` is a script -- importing it runs it and ends in `sys_exit` -- so only its
definitions are loaded. `jobs` is deliberately NOT stubbed: the requeue channel it provides is half
of what is under test.
"""

import ast
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import pytest

from jobs import JOB_REQUEUE_COUNT_ENV, MAX_JOB_REQUEUES, drain_requeue_request

ROOT = Path(__file__).resolve().parents[3]
CERTBOT_NEW = ROOT / "src" / "common" / "core" / "letsencrypt" / "jobs" / "certbot-new.py"


def _load_definitions():
    tree = ast.parse(CERTBOT_NEW.read_text(encoding="utf-8"), filename=str(CERTBOT_NEW))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    # Runtime-image modules that are not in the unit venv. `jobs` is absent from this list on
    # purpose -- `can_requeue` / `job_requeue_count` / `request_requeue` are the real ones.
    stubs = {name: MagicMock() for name in ("API", "ApiCaller", "certbot_concurrency", "letsencrypt_utils", "requests", "logger", "common_utils")}
    stubs["logger"].getLogger = Mock(return_value=Mock())

    module = ModuleType("bw_certbot_new")
    module.__dict__["__file__"] = str(CERTBOT_NEW)
    with patch.dict(sys.modules, stubs):
        exec(compile(tree, str(CERTBOT_NEW), "exec"), module.__dict__)  # noqa: S102
    return module


MODULE = _load_definitions()


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """The requeue handoff is module state, and so is the deferral counter."""
    drain_requeue_request()
    monkeypatch.setattr(MODULE, "LOGGER", Mock())
    # A worker is behind this run unless a test says otherwise; the worker always sets it.
    monkeypatch.setenv(JOB_REQUEUE_COUNT_ENV, "0")
    yield
    drain_requeue_request()


def _db(**metadata):
    """A database whose `get_metadata` answers with the flags a test cares about."""
    base = {
        "custom_configs_changed": False,
        "external_plugins_changed": False,
        "pro_plugins_changed": False,
        "instances_changed": False,
        "plugins_config_changed": {},
    }
    base.update(metadata)
    return Mock(get_metadata=Mock(return_value=base))


PENDING_FLAGS = [
    ({"custom_configs_changed": True}, "custom_configs"),
    ({"external_plugins_changed": True}, "external_plugins"),
    ({"pro_plugins_changed": True}, "pro_plugins"),
    ({"instances_changed": True}, "instances"),
    ({"plugins_config_changed": {"letsencrypt": None}}, "plugins_config"),
]


class TestThePredicate:
    def test_a_converged_fleet_is_not_deferred(self):
        assert MODULE.defer_until_configuration_is_delivered(_db()) is False
        assert drain_requeue_request() is None

    @pytest.mark.parametrize(("metadata", "name"), PENDING_FLAGS)
    def test_every_flag_push_configs_acknowledges_defers_the_run(self, metadata, name):
        """One list, not two. A flag this gate waits on that push-configs does not clear would
        wait forever; a flag push-configs clears that this gate ignores is a hole in it."""
        assert MODULE.defer_until_configuration_is_delivered(_db(**metadata)) is True
        request = drain_requeue_request()
        assert request is not None
        assert name in request["reason"]

    def test_the_predicate_is_push_configs_own_acknowledgement_list(self):
        """Pinned against the other side of the contract rather than against a copy of it."""
        push_configs = (ROOT / "src" / "common" / "core" / "jobs" / "jobs" / "push-configs.py").read_text(encoding="utf-8")
        acknowledged = next(line for line in push_configs.splitlines() if "clear_applied_changes(metadata_snapshot" in line)
        for key in MODULE.PUSH_CONFIGS_ACK_KEYS + ("plugins_config",):
            assert f'"{key}"' in acknowledged, f"{key} is gated on here but push-configs never clears it"

    def test_a_database_that_will_not_answer_does_not_withhold_certificates(self):
        """Fails OPEN. A metadata read that raises is a diagnostic failure, not evidence that the
        configuration is undelivered, and it must not become a reason to skip issuance."""
        assert MODULE.defer_until_configuration_is_delivered(Mock(get_metadata=Mock(side_effect=RuntimeError("gone")))) is False
        assert drain_requeue_request() is None


class TestTheDeferral:
    def test_deferring_never_sleeps(self, monkeypatch):
        """Condition 1 of the ruling. Waiting in place holds one of the two heavy prefork children
        (`entrypoint.sh`, `--concurrency=2`), and two certbot runs waiting on the same push
        deadlock the lane against it."""
        monkeypatch.setattr(MODULE, "sleep", Mock(side_effect=AssertionError("a deferral must never block a heavy worker child")))
        assert MODULE.defer_until_configuration_is_delivered(_db(instances_changed=True)) is True

    def test_a_deferral_is_loud(self):
        """Condition 2. A deferred run has, from the outside, done nothing -- exactly like a run
        with nothing to do. Whatever level this lands at, it must not be below WARNING, or an
        unconverged fleet becomes a job that silently never runs."""
        logger = MODULE.LOGGER
        MODULE.defer_until_configuration_is_delivered(_db(instances_changed=True))
        loud = [call for name, call in ((n, c) for n in ("warning", "error") for c in getattr(logger, n).call_args_list)]
        assert loud, "the deferral produced nothing at WARNING or above"
        assert any("instances" in str(call) for call in loud), "the reason for the deferral is not in the log"
        logger.debug.assert_not_called()

    def test_the_requeue_carries_a_delay_the_worker_can_act_on(self):
        MODULE.defer_until_configuration_is_delivered(_db(instances_changed=True))
        request = drain_requeue_request()
        assert isinstance(request["delay"], int) and request["delay"] > 0


class TestTheGateCanAlwaysOpen:
    def test_a_spent_budget_proceeds_instead_of_giving_up(self, monkeypatch):
        """An instance that never comes back keeps these flags raised forever. A gate that can
        never open would be a NEW way to never get a certificate -- strictly worse than the race
        it closes. Past the budget the run behaves exactly as it did before the gate existed."""
        monkeypatch.setenv(JOB_REQUEUE_COUNT_ENV, str(MODULE.MAX_DEFERRALS))
        assert MODULE.defer_until_configuration_is_delivered(_db(instances_changed=True)) is False
        assert drain_requeue_request() is None
        assert MODULE.LOGGER.error.called, "giving up on the gate must be reported"

    def test_the_budget_is_one_the_worker_will_honour(self):
        """A job may ask for more deferrals than the worker grants; the extra ones are refused and
        the run would then never happen at all."""
        assert MODULE.MAX_DEFERRALS <= MAX_JOB_REQUEUES

    def test_a_run_with_no_dispatcher_behind_it_does_not_defer(self, monkeypatch):
        """`bwcli`, or any future in-process caller: nothing drains the requeue, so deferring
        there means doing nothing and never coming back."""
        monkeypatch.delenv(JOB_REQUEUE_COUNT_ENV, raising=False)
        assert MODULE.defer_until_configuration_is_delivered(_db(instances_changed=True)) is False
        assert drain_requeue_request() is None
        assert MODULE.LOGGER.warning.called


def test_raising_the_acme_retry_setting_is_not_the_fix():
    """Recorded so the cheap "fix" cannot come back: more certbot attempts means more failed ACME
    orders per service, which is rate-limited by the CA. The default is deliberately low."""
    assert 'env("LETS_ENCRYPT_MAX_RETRIES", "0")' in CERTBOT_NEW.read_text(encoding="utf-8")
