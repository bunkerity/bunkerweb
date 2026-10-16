"""`UI_USE_REDIS=no` keeps the Web UI off Redis, without touching USE_REDIS for the rest of the stack (D4).

A 1.6.16 operator whose shared Redis is broken sets `UI_USE_REDIS=no` on the UI container only. It
must give the UI file sessions and let every other Redis branch fall back to the instances API,
while the scheduler, the instances and the worker keep using Redis. Two places decide it:

- `get_redis_client` (app/routes/utils.py): the per-request and per-worker client. Opt-out returns
  `None` before BW_CONFIG is read or a connection is tried, and caches that `None` on `g`.
- gunicorn's `on_starting`: whether the "filesystem session backend" warning applies, and whether
  the API is asked for USE_REDIS at all. Its decision is `ui_wants_redis_sessions`.

Both are spliced out of the source and run here (the modules import qrcode, Flask-Session and
BW_CONFIG at import time, which the unit venv lacks).
"""

import pytest
from flask import Flask, g
from unittest.mock import Mock

from test_session_plumbing import GUNICORN, UTILS, _shipped
from common_utils import getenv_bool  # type: ignore

from os import getenv


def _routes_namespace(config):
    """`get_redis_client` as shipped, with BW_CONFIG and the shared client factory observable."""
    from flask import has_request_context

    bw_config = Mock()
    bw_config.get_config.return_value = config
    factory = Mock(return_value="REDIS-CLIENT")
    namespace = _shipped(
        UTILS,
        ("get_redis_client",),
        {
            "BW_CONFIG": bw_config,
            "LOGGER": Mock(),
            "g": g,
            "has_request_context": has_request_context,
            "get_common_redis_client": factory,
            "getenv_bool": getenv_bool,
            "flash": Mock(),
            "translated": lambda *_a, **_k: "",
        },
    )
    return namespace["get_redis_client"], bw_config, factory


@pytest.mark.parametrize("value", ["no", "NO", "false", "0"])
def test_opt_out_returns_no_client_and_never_reads_the_config_or_connects(monkeypatch, value):
    monkeypatch.setenv("UI_USE_REDIS", value)
    get_redis_client, bw_config, factory = _routes_namespace({"USE_REDIS": "yes", "REDIS_HOST": "redis"})

    assert get_redis_client() is None
    bw_config.get_config.assert_not_called()
    factory.assert_not_called()


def test_opt_out_is_cached_on_g_so_a_request_does_not_ask_again(monkeypatch):
    monkeypatch.setenv("UI_USE_REDIS", "no")
    get_redis_client, bw_config, factory = _routes_namespace({"USE_REDIS": "yes"})

    with Flask(__name__).test_request_context():
        assert get_redis_client() is None
        assert g.bw_redis_client is None
        assert get_redis_client() is None

    factory.assert_not_called()


@pytest.mark.parametrize("value", [None, "yes", "true"])
def test_default_and_yes_still_reach_redis(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("UI_USE_REDIS", raising=False)
    else:
        monkeypatch.setenv("UI_USE_REDIS", value)
    get_redis_client, bw_config, factory = _routes_namespace({"USE_REDIS": "yes", "REDIS_HOST": "redis"})

    assert get_redis_client() == "REDIS-CLIENT"
    bw_config.get_config.assert_called_once()
    assert factory.call_args.kwargs["use_redis"] is True


def _gunicorn_decision(api_answer):
    api_client = Mock()
    if isinstance(api_answer, Exception):
        api_client._get.side_effect = api_answer
    else:
        api_client._get.return_value = {"settings": {"USE_REDIS": api_answer}}
    namespace = _shipped(
        GUNICORN,
        ("ui_wants_redis_sessions",),
        {"getenv": getenv, "getenv_bool": getenv_bool, "ApiClientError": RuntimeError, "ApiUnavailableError": ConnectionError},
    )
    return namespace["ui_wants_redis_sessions"], api_client


def test_gunicorn_opt_out_does_not_ask_the_api_and_does_not_use_redis(monkeypatch):
    monkeypatch.setenv("UI_USE_REDIS", "no")
    monkeypatch.setenv("USE_REDIS", "yes")
    decide, api_client = _gunicorn_decision("yes")

    assert decide(api_client, Mock()) is False
    api_client._get.assert_not_called()


@pytest.mark.parametrize("ui_value", [None, "yes"])
def test_gunicorn_default_follows_use_redis(monkeypatch, ui_value):
    if ui_value is None:
        monkeypatch.delenv("UI_USE_REDIS", raising=False)
    else:
        monkeypatch.setenv("UI_USE_REDIS", ui_value)
    monkeypatch.delenv("USE_REDIS", raising=False)

    decide, api_client = _gunicorn_decision("yes")
    assert decide(api_client, Mock()) is True

    decide, api_client = _gunicorn_decision("no")
    assert decide(api_client, Mock()) is False

    monkeypatch.setenv("USE_REDIS", "yes")
    decide, api_client = _gunicorn_decision("no")
    assert decide(api_client, Mock()) is True
    api_client._get.assert_not_called()
