"""The Web UI recycles its Gunicorn workers every 200 requests by default (#4163).

A worker keeps the memory of every session it served until it is recycled, and an admin UI takes days to reach 1000
requests. The jitter stays below a tenth of the limit so that two workers do not restart together.
"""

import runpy
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(monkeypatch, config, **env):
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in ("app.models.ui_database", "app.models.api_database", "app.dependencies", "app.utils", "biscuit_auth", "passlib.totp"):
        monkeypatch.setitem(sys.modules, name, MagicMock())
    logger = MagicMock()
    logger.log_types = {}
    monkeypatch.setitem(sys.modules, "logger", logger)
    for name in ("MAX_REQUESTS", "UI_MAX_REQUESTS", "API_MAX_REQUESTS", "DEBUG"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return runpy.run_path(str(ROOT / "src" / config))


def test_ui_default_is_200_with_a_tenth_of_jitter(monkeypatch):
    conf = load(monkeypatch, "ui/utils/gunicorn.conf.py")
    assert (conf["max_requests"], conf["max_requests_jitter"]) == (200, 20)


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"MAX_REQUESTS": "500"}, (500, 50)),
        ({"UI_MAX_REQUESTS": "100"}, (100, 10)),
        ({"MAX_REQUESTS": "500", "UI_MAX_REQUESTS": "100"}, (100, 10)),
        ({"UI_MAX_REQUESTS": "5000"}, (5000, 50)),
        ({"UI_MAX_REQUESTS": "5"}, (5, 0)),
    ],
)
def test_ui_overrides_and_jitter_bound(monkeypatch, env, expected):
    conf = load(monkeypatch, "ui/utils/gunicorn.conf.py", **env)
    assert (conf["max_requests"], conf["max_requests_jitter"]) == expected


def test_api_default_is_unchanged(monkeypatch):
    conf = load(monkeypatch, "api/utils/gunicorn.conf.py")
    assert (conf["max_requests"], conf["max_requests_jitter"]) == (1000, 50)
