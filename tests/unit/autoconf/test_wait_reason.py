"""Autoconf must say what it is waiting for, not blame the API for all three causes.

``Controller.wait()`` logged "Waiting for the API to be ready" whenever ``have_to_wait()`` was
true. That is right for exactly one of its three causes. The other two -- an uninitialised
database, and a configuration change the scheduler has dispatched whose job has not acknowledged
it yet -- have nothing to do with the API being reachable, and the second one is by far the common
one: on the Kubernetes arm of run 32820557847 the controller printed that line every 5s for six
minutes while ``[AUTOCONF] API is available`` sat one second above it in the same log. Two separate
CI investigations went after the API before anyone read ``Config.have_to_wait``.

So ``have_to_wait`` returns the reason, empty when there is none. Every caller only ever tested it
for truthiness, so the six call sites are unchanged.
"""

import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]

READY = {
    "is_initialized": True,
    "first_config_saved": True,
    "custom_configs_changed": False,
    "external_plugins_changed": False,
    "pro_plugins_changed": False,
    "plugins_config_changed": {},
    "instances_changed": False,
}


def _load_config():
    api_client = ModuleType("api_client")
    api_client.ApiUnavailableError = RuntimeError
    with patch.dict(sys.modules, {"api_client": api_client}):
        path = ROOT / "src" / "autoconf" / "Config.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_config_wait_reason", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Config


Config = _load_config()


class _Api:
    readonly = False

    def __init__(self, metadata):
        self.metadata = metadata
        self.save_config = Mock(return_value=set())
        self.update_instances = Mock(return_value=None)
        self.save_custom_configs = Mock(return_value=None)
        self.checked_changes = Mock(return_value=None)

    def get_services(self):
        return []

    def validate_setting(self, *_args, **_kwargs):
        return True, None

    def get_metadata(self):
        return self.metadata

    def expect_errors(self):
        return nullcontext()


def _config(metadata):
    return Config("kubernetes", api_client=_Api(metadata))


def test_no_reason_when_everything_is_applied():
    assert _config(dict(READY)).have_to_wait() == ""


def test_unreachable_api_says_so_and_carries_the_error():
    reason = _config("connection refused").have_to_wait()
    assert "API" in reason
    assert "connection refused" in reason


def test_uninitialized_database_is_not_reported_as_an_api_problem():
    reason = _config(dict(READY, is_initialized=False)).have_to_wait()
    assert "database" in reason
    assert "API" not in reason


def test_pending_change_names_the_flags_and_does_not_blame_the_api():
    """The Kubernetes deadlock: this is what six minutes of "Waiting for the API" really meant."""
    reason = _config(
        dict(
            READY,
            custom_configs_changed=True,
            instances_changed=True,
            plugins_config_changed={"inject": "2026-08-25T07:36:02"},
        )
    ).have_to_wait()

    assert "scheduler" in reason
    assert "API" not in reason
    for flag in ("custom_configs_changed", "plugins_config_changed", "instances_changed"):
        assert flag in reason
    for flag in ("external_plugins_changed", "pro_plugins_changed"):
        assert flag not in reason


def test_every_pending_flag_alone_is_enough_to_wait():
    """`plugins_config_changed` is the one that went missing from a copy of this tuple once."""
    for flag in Config.PENDING_CHANGE_FLAGS:
        assert _config(dict(READY, **{flag: True})).have_to_wait(), f"{flag} did not hold autoconf back"


def test_callers_can_still_treat_it_as_a_boolean():
    assert not _config(dict(READY)).have_to_wait()
    assert _config(dict(READY, instances_changed=True)).have_to_wait()
