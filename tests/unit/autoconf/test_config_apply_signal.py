"""An apply() that changes nothing signals nothing to the scheduler.

Restored from 1.7 tests/unit/autoconf/test_config.py (199d0b22c). Setup differs: dev's Config talks to
the Database directly (`_db`), 1.7 goes through an API client, so the fake below stands in for the
database and `Database` is patched on the loaded module. The assertions are the 1.7 ones.
"""

import importlib.util
import logging
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]


def _load_config():
    spec = importlib.util.spec_from_file_location("bw_autoconf_config_apply_signal", ROOT / "src" / "autoconf" / "Config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


config_module = _load_config()
Config = config_module.Config


class _Api:
    readonly = False
    database_uri = ""

    def __init__(self):
        self.save_config = Mock(return_value=set())
        self.update_instances = Mock(return_value=None)
        self.save_custom_configs = Mock(return_value=None)
        self.checked_changes = Mock(return_value=None)

    def test_write(self):
        return None

    def get_services(self):
        return []

    def is_valid_setting(self, *_args, **_kwargs):
        return True, None

    def get_metadata(self):
        return {"is_initialized": True, "first_config_saved": True}

    def expect_errors(self):
        return nullcontext()


def _config(api):
    with patch.object(config_module, "Database", return_value=api):
        return Config("docker")


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
    config = _config(api)
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
    config = _config(api)
    config._settings = {"SERVER_NAME": {"type": "text"}}
    configs = {kind: {} for kind in config._supported_config_types}

    assert config.apply([], [{"SERVER_NAME": "app.example"}], configs=configs, first=True) is True
    assert config.apply([], [{"SERVER_NAME": "app.example"}], configs=configs) is True
    assert config.apply([], [{"SERVER_NAME": "other.example"}], configs=configs) is True

    assert api.checked_changes.call_count == 2
    assert "services" in api.checked_changes.call_args.args[0]
