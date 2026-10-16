"""HEALTHCHECK_INTERVAL and RELOAD_MIN_TIMEOUT (env only) accept the 1.6.16 time suffixes."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from test_healthcheck_loading import _MAIN_PATH, _sandboxed_mkdir


def _load(tmp_path, monkeypatch, **env):
    for name in ("HEALTHCHECK_INTERVAL", "RELOAD_MIN_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    spec = importlib.util.spec_from_file_location("bw_scheduler_main_duration", _MAIN_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bw_scheduler_main_duration"] = module
    try:
        with patch.object(Path, "mkdir", _sandboxed_mkdir(tmp_path, [])):
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop("bw_scheduler_main_duration", None)
    return module


@pytest.mark.parametrize(("value", "expected"), [(None, 30), ("30", 30), ("45s", 45), ("1m", 60), ("junk", 30), ("0", 0)])
def test_healthcheck_interval(tmp_path, monkeypatch, value, expected):
    env = {} if value is None else {"HEALTHCHECK_INTERVAL": value}
    assert _load(tmp_path, monkeypatch, **env).HEALTHCHECK_INTERVAL == expected


@pytest.mark.parametrize(("value", "expected"), [(None, 5), ("5", 5), ("30s", 30), ("2m", 120), ("junk", 5), ("500ms", 1)])
def test_reload_min_timeout(tmp_path, monkeypatch, value, expected):
    env = {} if value is None else {"RELOAD_MIN_TIMEOUT": value}
    assert _load(tmp_path, monkeypatch, **env).RELOAD_MIN_TIMEOUT == expected
