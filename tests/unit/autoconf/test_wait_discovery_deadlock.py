"""Autoconf must be able to *discover* instances while the scheduler's apply flags are raised.

The Kubernetes/mariadb upgrade arm of CI run 33528164796 (branch 1.7, ``d898d5c66``) never
recovered, and the loop was closed:

* the database still named the pre-upgrade instance, ``10-244-0-10`` -- that pod is gone, so every
  push to it failed with ``[Errno 113] No route to host``. The live pod was ``10.244.0.20``;
* push-configs therefore could not apply anything, so the change flags it clears stayed raised;
* ``Controller.wait()`` spun on exactly those flags -- ``have_to_wait()`` returns a reason while
  any of them is set, and the loop ``continue``\\ s on a reason -- so it never reached the
  ``get_instances()`` call one block below;
* which is the only thing that would have replaced ``10-244-0-10`` with ``10.244.0.20`` and let
  the next push succeed.

The controller logged ``Waiting for the scheduler to finish applying (custom_configs_changed,
instances_changed)`` every 5s until the harness gave up. A previous wave fixed that *message*
(see ``test_wait_reason``); the deadlock it describes was still there.

``wait()`` only reads. The gate belongs on the write, and the write already has its own: the first
one is ``initial_apply()`` -> ``Config.apply()``, which opens with ``wait_applying()`` on the same
flags. ``test_the_write_path_is_still_gated`` pins that so the read-side relaxation cannot quietly
grow into the write side.
"""

import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
_CONTROLLER_PATH = ROOT / "src" / "autoconf" / "controllers" / "Controller.py"

# The scheduler has dispatched an apply and no job has acknowledged it yet: precisely the state
# the upgrade arm was stuck in.
PENDING = {
    "is_initialized": True,
    "first_config_saved": True,
    "custom_configs_changed": True,
    "external_plugins_changed": False,
    "pro_plugins_changed": False,
    "plugins_config_changed": {},
    "instances_changed": True,
}

DEAD_POD = "10-244-0-10.bunkerweb.pod.cluster.local"
LIVE_POD = "10-244-0-20.bunkerweb.pod.cluster.local"


def _load_controller():
    """Import ``Controller.py`` with its two container-only imports stubbed."""
    api_client = ModuleType("api_client")
    api_client.ApiUnavailableError = RuntimeError

    config_path = ROOT / "src" / "autoconf" / "Config.py"
    with patch.dict(sys.modules, {"api_client": api_client}):
        spec = importlib.util.spec_from_file_location("Config", config_path)
        config_mod = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"Config": config_mod}):
            spec.loader.exec_module(config_mod)
            spec2 = importlib.util.spec_from_file_location("bw_autoconf_controller_deadlock", _CONTROLLER_PATH)
            module = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(module)
    return module


controller_module = _load_controller()


class _Api:
    readonly = False

    def __init__(self, metadata):
        self.metadata = metadata
        self.save_config = Mock(return_value=set())
        self.update_instances = Mock(return_value=None)
        self.save_custom_configs = Mock(return_value=None)
        self.checked_changes = Mock(return_value=None)

    def get_metadata(self):
        return self.metadata

    def get_services(self):
        return []

    def get_instances(self, autoconf=False):
        # The stale row the upgrade left behind. Only reached by the `_first_start` fallback,
        # i.e. when the orchestrator itself reports nothing.
        return [{"hostname": DEAD_POD, "name": DEAD_POD, "health": False}]

    def validate_setting(self, *_args, **_kwargs):
        return True, None

    def expect_errors(self):
        return nullcontext()


class _Controller(controller_module.Controller):
    """A controller whose cluster contains exactly the live pod, and nothing else."""

    def __init__(self, metadata, live=True):
        self._live = live
        super().__init__("kubernetes", api_client=_Api(metadata))

    def _get_controller_instances(self):
        return [LIVE_POD] if self._live else []

    def _to_instances(self, controller_instance):
        return [{"hostname": controller_instance, "health": True, "name": controller_instance}]

    def _get_controller_services(self):
        return []

    def _to_services(self, controller_service):
        return []

    def apply_config(self, force: bool = False):
        return True


@pytest.fixture
def no_spinning(monkeypatch):
    """Turn "loops forever" into a readable failure instead of a hung test run.

    ``wait()`` sleeps between polls, so on unfixed code this test would hang rather than fail.
    The third sleep raises: three polls is far more than a controller needs when the API answers,
    the database is initialised and the one instance in the cluster is healthy.
    """
    calls = []

    def _sleep(seconds):
        calls.append(seconds)
        if len(calls) >= 3:
            raise TimeoutError(f"Controller.wait() is still spinning after {len(calls)} polls")

    monkeypatch.setattr(controller_module, "sleep", _sleep)
    return calls


def test_discovery_replaces_a_dead_instance_while_the_apply_flags_are_set(no_spinning):
    """The deadlock, end to end: pending flags must not stop the controller seeing the live pod."""
    instances = _Controller(dict(PENDING)).wait(1)

    assert [instance["hostname"] for instance in instances] == [LIVE_POD]
    assert DEAD_POD not in [instance["hostname"] for instance in instances]
    assert no_spinning == [], "the controller waited on the scheduler before reading the cluster"


def test_an_unreachable_api_still_holds_discovery_back(no_spinning):
    """The relaxation is scoped: without the API there is genuinely nothing to read."""
    with pytest.raises(TimeoutError):
        _Controller("connection refused").wait(1)

    assert no_spinning, "an unreachable API must still make the controller wait"


def test_an_uninitialized_database_still_holds_discovery_back(no_spinning):
    with pytest.raises(TimeoutError):
        _Controller(dict(PENDING, is_initialized=False)).wait(1)

    assert no_spinning, "an uninitialised database must still make the controller wait"


def test_an_empty_cluster_still_waits(no_spinning):
    """Unchanged behaviour: no instance anywhere is not something to proceed on."""
    with pytest.raises(TimeoutError):
        _Controller(dict(PENDING), live=False).wait(1)

    assert no_spinning


def test_the_write_path_is_still_gated():
    """`include_pending=False` is for reads only -- every other call site guards an apply.

    Read-side and write-side share one helper, so the cheapest way to keep them from merging is to
    count: exactly one call site opts out, and it is the discovery loop in ``Controller.wait``.
    """
    # Every .py under src/autoconf, not a hand-listed few: DockerController, SwarmController,
    # IngressController and GatewayController also subclass Controller, and an opt-out added in
    # any of them would sail past a three-file list.
    sources = {path: path.read_text(encoding="utf-8") for path in (ROOT / "src" / "autoconf").rglob("*.py")}
    assert len(sources) >= 6, f"only {len(sources)} autoconf sources scanned — the glob is not finding the package"
    opt_outs = sum(text.count("have_to_wait(include_pending=False)") for text in sources.values())
    total = sum(text.count("self.have_to_wait(") for text in sources.values())

    assert opt_outs == 1, f"exactly one call site may skip the pending-changes gate, found {opt_outs}"
    assert total > opt_outs, "the remaining call sites must keep the default gate"

    # And the default really is still the gate.
    config = _Controller(dict(PENDING))
    assert "custom_configs_changed" in config.have_to_wait()
    assert config.have_to_wait(include_pending=False) == ""

    # The write path opens with its own wait on the same flags, untouched by this change.
    assert any("self.wait_applying()" in text for path, text in sources.items() if path.name == "Config.py")
