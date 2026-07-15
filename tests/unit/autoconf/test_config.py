"""Autoconf stores canonical values once instead of reconfiguring forever."""

import importlib.util
import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]


def _load_config():
    api_client = ModuleType("api_client")
    api_client.ApiUnavailableError = RuntimeError
    previous = sys.modules.get("api_client")
    sys.modules["api_client"] = api_client
    try:
        path = ROOT / "src" / "autoconf" / "Config.py"
        spec = importlib.util.spec_from_file_location("bw_autoconf_config", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.Config
    finally:
        if previous is None:
            sys.modules.pop("api_client", None)
        else:
            sys.modules["api_client"] = previous


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
