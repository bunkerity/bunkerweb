"""Autoconf stores canonical values once instead of reconfiguring forever."""

import importlib.util
import logging
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def _load_config():
    api_client = ModuleType("api_client")
    api_client.ApiUnavailableError = RuntimeError
    with patch.dict(sys.modules, {"api_client": api_client}):
        path = ROOT / "src" / "autoconf" / "Config.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Config


Config = _load_config()


class _Api:
    readonly = False

    def __init__(self):
        self.save_config = Mock(return_value=set())
        self.update_instances = Mock(return_value=None)
        self.save_custom_configs = Mock(return_value=None)
        self.checked_changes = Mock(return_value=None)

    def get_services(self):
        return []

    def validate_setting(self, *_args, **_kwargs):
        return True, None

    def get_metadata(self):
        return {"is_initialized": True, "first_config_saved": True}

    def expect_errors(self):
        return nullcontext()


def test_canonical_values_do_not_trigger_second_save():
    api = _Api()
    config = Config("docker", api_client=api)
    config._settings = {
        "CHECK": {"type": "check"},
        "DURATION": {"type": "duration"},
        "SIZE": {"type": "size"},
        "MODE": {"type": "select", "select": ["modern"], "case_insensitive": True},
        "VALUES": {"type": "multivalue", "separator": ","},
        "OPTIONS": {
            "type": "multiselect",
            "separator": " ",
            "multiselect": [{"value": "one"}, {"value": "two"}],
            "case_insensitive": True,
        },
    }
    service = {
        "SERVER_NAME": "app.example",
        "CHECK": " enabled ",
        "DURATION": "30 sec",
        "SIZE": "64 M",
        "MODE": "MODERN",
        "VALUES": " a , b, ",
        "OPTIONS": "ONE TWO",
    }
    configs = {kind: {} for kind in config._supported_config_types}

    assert config.apply([], [service], configs=configs, first=True) is True
    assert config.apply([], [service], configs=configs) is True

    api.save_config.assert_called_once()
    saved = api.save_config.call_args.args[0]
    assert saved == {
        "SERVER_NAME": "app.example",
        "MULTISITE": "yes",
        "app.example_SERVER_NAME": "app.example",
        "app.example_CHECK": "yes",
        "app.example_DURATION": "30s",
        "app.example_SIZE": "64m",
        "app.example_MODE": "modern",
        "app.example_VALUES": "a,b",
        "app.example_OPTIONS": "one two",
    }


class _Capture(logging.Handler):
    """Collect records off one logger.

    Not caplog, and not `record.levelname`: importing any product module runs
    src/common/utils/logger.py, which calls addLevelName() on every level -- INFO's name is
    "ℹ️ ", not "INFO" -- and it installs its own handlers via basicConfig(handlers=[…]).
    """

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def _saved_count(capture):
    return sum(1 for record in capture.records if "Successfully saved new configuration" in record.getMessage())


def test_an_apply_that_changes_nothing_signals_nothing():
    """An empty `changes` list is not "no changes" by the time it reaches the database.

    Database.checked_changes() opens with `changes = changes or [<all seven>]` so that a caller
    passing None means "everything" -- and an empty list is falsy too. So signalling [] set all
    seven bw_metadata *_changed flags, and the scheduler re-dispatches its whole job batch on
    those flags. Combined with an update_needed that false-positived on dict insertion order
    (test_config_update_needed_order.py), that is the whole job-storm loop: the controller
    re-applies, apply() finds nothing to do, and "nothing happened" is broadcast as "everything
    changed" every ~20 seconds.
    """
    api = _Api()
    config = Config("docker", api_client=api)
    config._settings = {"SERVER_NAME": {"type": "text"}}
    service = {"SERVER_NAME": "app.example"}
    configs = {kind: {} for kind in config._supported_config_types}

    capture = _Capture()
    config._Config__logger.addHandler(capture)
    try:
        assert config.apply([], [service], configs=configs, first=True) is True
        assert api.checked_changes.call_count == 1
        assert _saved_count(capture) == 1
        # …and not vacuously: the first apply really did have something to signal.
        assert api.checked_changes.call_args.args[0]

        assert config.apply([], [service], configs=configs) is True
        assert api.checked_changes.call_count == 1
        assert _saved_count(capture) == 1
    finally:
        config._Config__logger.removeHandler(capture)


def test_a_later_real_change_is_still_signalled():
    """The guard must not swallow the next genuine change."""
    api = _Api()
    config = Config("docker", api_client=api)
    config._settings = {"SERVER_NAME": {"type": "text"}}
    configs = {kind: {} for kind in config._supported_config_types}

    assert config.apply([], [{"SERVER_NAME": "app.example"}], configs=configs, first=True) is True
    assert config.apply([], [{"SERVER_NAME": "app.example"}], configs=configs) is True
    assert config.apply([], [{"SERVER_NAME": "other.example"}], configs=configs) is True

    assert api.checked_changes.call_count == 2
    assert "services" in api.checked_changes.call_args.args[0]
