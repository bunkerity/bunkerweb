"""Duration settings read by the jobs: CrowdSec bouncer times and the UI session cleanup."""

import importlib.util
import runpy
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONF_UTILS = ROOT / "src" / "common" / "core" / "crowdsec" / "jobs" / "crowdsec_conf_utils.py"
CLEANUP = ROOT / "src" / "common" / "core" / "db" / "jobs" / "cleanup-expired-ui-sessions.py"


def _conf_utils():
    spec = importlib.util.spec_from_file_location("crowdsec_conf_utils_duration", CONF_UTILS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DURATIONS = (
    "CROWDSEC_REQUEST_TIMEOUT",
    "CROWDSEC_CACHE_EXPIRATION",
    "CROWDSEC_UPDATE_FREQUENCY",
    "CROWDSEC_APPSEC_CONNECT_TIMEOUT",
    "CROWDSEC_APPSEC_SEND_TIMEOUT",
    "CROWDSEC_APPSEC_PROCESS_TIMEOUT",
)


def test_crowdsec_defaults_render_the_bare_integers_the_bouncer_expects():
    rendered = _conf_utils().render_variables({}.get)
    assert [rendered[name] for name in DURATIONS] == ["1000", "1", "10", "100", "100", "500"]


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"CROWDSEC_REQUEST_TIMEOUT": "2s"}, ("CROWDSEC_REQUEST_TIMEOUT", "2000")),
        ({"CROWDSEC_REQUEST_TIMEOUT": "1500"}, ("CROWDSEC_REQUEST_TIMEOUT", "1500")),
        ({"CROWDSEC_CACHE_EXPIRATION": "1m"}, ("CROWDSEC_CACHE_EXPIRATION", "60")),
        ({"CROWDSEC_UPDATE_FREQUENCY": "2m"}, ("CROWDSEC_UPDATE_FREQUENCY", "120")),
        ({"CROWDSEC_APPSEC_CONNECT_TIMEOUT": "1s"}, ("CROWDSEC_APPSEC_CONNECT_TIMEOUT", "1000")),
        ({"CROWDSEC_APPSEC_SEND_TIMEOUT": "250ms"}, ("CROWDSEC_APPSEC_SEND_TIMEOUT", "250")),
        # a sub-unit value must not collapse to 0, which the bouncer reads as "disabled"
        ({"CROWDSEC_CACHE_EXPIRATION": "500ms"}, ("CROWDSEC_CACHE_EXPIRATION", "1")),
        # an unparsable value falls back to the default instead of failing the job
        ({"CROWDSEC_REQUEST_TIMEOUT": "fast"}, ("CROWDSEC_REQUEST_TIMEOUT", "1000")),
    ],
)
def test_crowdsec_times_are_rendered_in_the_bouncers_unit(env, expected):
    assert _conf_utils().render_variables(env.get)[expected[0]] == expected[1]


def test_crowdsec_per_service_value_wins_and_is_parsed():
    env = {"CROWDSEC_REQUEST_TIMEOUT": "1s", "app.example.com_CROWDSEC_REQUEST_TIMEOUT": "3s"}
    assert _conf_utils().render_variables(env.get, "app.example.com")["CROWDSEC_REQUEST_TIMEOUT"] == "3000"


@pytest.mark.parametrize(("value", "days"), [(None, 14), ("14", 14), ("14d", 14), ("2w", 14), ("48h", 2), ("1y", 365), ("junk", 14)])
def test_session_cleanup_age_accepts_suffixes(monkeypatch, value, days):
    calls = []

    class FakeDatabase:
        def __init__(self, *_args, **_kwargs):
            pass

        def cleanup_expired_ui_sessions(self, max_age_days):
            calls.append(max_age_days)
            return "Removed 0 sessions"

    logger = types.ModuleType("logger")
    logger.getLogger = lambda _name: types.SimpleNamespace(info=lambda *_: None, warning=lambda *_: None, error=lambda *_: None)
    database = types.ModuleType("Database")
    database.Database = FakeDatabase
    monkeypatch.setitem(sys.modules, "logger", logger)
    monkeypatch.setitem(sys.modules, "Database", database)
    if value is None:
        monkeypatch.delenv("DATABASE_MAX_SESSION_AGE_DAYS", raising=False)
    else:
        monkeypatch.setenv("DATABASE_MAX_SESSION_AGE_DAYS", value)
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(CLEANUP), run_name="__main__")
    assert exit_info.value.code in (0, None)
    assert calls == [days]
