"""The API rate limiter must count each request once, and never log a Redis password.

`limiter_dep_dynamic` used to decorate a fresh no-op with `_limiter.limit(...)` on every
request. slowapi appends a limit per decoration, so the stored limit list grew by one per
request and every later request was charged against all of them: after about `API_RATE_LIMIT`
requests since the API started, every client got a 429.

These tests drive the real module (real slowapi, real FastAPI dependency) in-process. Only
`.config` and `.utils` are replaced, because they pull the database and the YAML settings.
"""

import logging
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

pytest.importorskip("slowapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

API_APP = Path(__file__).resolve().parents[3] / "src" / "api" / "app"
PKG = "bw_rate_limit_under_test"


def _load_rate_limit(monkeypatch, **overrides):
    """Import rate_limit.py as a private package so it cannot clash with the UI's `app` package."""
    cfg = dict(
        API_ROOT_PATH="",
        API_TOKEN=None,
        API_RATE_LIMIT="3r/m",
        API_RATE_LIMIT_AUTH="10r/m",
        API_RATE_LIMIT_STORAGE_OPTIONS=None,
        API_RATE_LIMIT_STRATEGY="fixed-window",
        API_RATE_LIMIT_RULES=None,
        API_RATE_LIMIT_KEY="ip",
        API_RATE_LIMIT_EXEMPT_IPS="",
        rate_limit_enabled=True,
        rate_limit_headers_enabled=True,
    )
    cfg.update(overrides)
    logger = logging.getLogger(PKG)

    class _NoDb:
        def get_config(self, **_):
            raise RuntimeError("no database in this test")

    pkg = ModuleType(PKG)
    pkg.__path__ = [str(API_APP)]
    monkeypatch.setitem(sys.modules, PKG, pkg)
    monkeypatch.setitem(sys.modules, f"{PKG}.config", SimpleNamespace(api_config=SimpleNamespace(**cfg)))
    monkeypatch.setitem(sys.modules, f"{PKG}.utils", SimpleNamespace(LOGGER=logger, get_db=lambda **_: _NoDb()))
    for name in ("REDIS_HOST", "REDIS_PASSWORD", "REDIS_SENTINEL_HOSTS", "REDIS_CLUSTER_NODES", "USE_REDIS"):
        monkeypatch.delenv(name, raising=False)

    spec = spec_from_file_location(f"{PKG}.rate_limit", API_APP / "rate_limit.py")
    module = module_from_spec(spec)
    monkeypatch.setitem(sys.modules, f"{PKG}.rate_limit", module)
    spec.loader.exec_module(module)
    return module


def _client(module) -> TestClient:
    app = FastAPI()
    module.setup_rate_limiter(app)

    @app.get("/thing", dependencies=[module.limiter_dep_dynamic()])
    def thing():
        return {"ok": True}

    return TestClient(app)


def _statuses(client: TestClient, count: int, **kwargs):
    return [client.get("/thing", **kwargs).status_code for _ in range(count)]


@pytest.fixture
def rl(monkeypatch):
    return _load_rate_limit(monkeypatch)


def test_n_plus_one_requests_give_exactly_one_429(rl):
    assert _statuses(_client(rl), 4) == [200, 200, 200, 429]


def test_the_stored_limit_list_does_not_grow_with_traffic(rl):
    client = _client(rl)
    _statuses(client, 2)
    grown = sum(len(v) for v in rl._limiter._route_limits.values())
    _statuses(client, 20)
    assert sum(len(v) for v in rl._limiter._route_limits.values()) == grown


def test_two_clients_never_share_a_counter(rl):
    client_a = TestClient(_client(rl).app, client=("10.0.0.1", 5000))
    client_b = TestClient(client_a.app, client=("10.0.0.2", 5000))
    assert _statuses(client_a, 4) == [200, 200, 200, 429]
    assert _statuses(client_b, 3) == [200, 200, 200]


def test_a_matched_rule_is_counted_once_too(monkeypatch):
    module = _load_rate_limit(monkeypatch, API_RATE_LIMIT_RULES='[{"path": "/thing", "methods": "GET", "rate": "2r/m"}]')
    assert _statuses(_client(module), 3) == [200, 200, 429]


def test_the_limit_cache_resets_when_the_limiter_is_rebuilt(monkeypatch):
    module = _load_rate_limit(monkeypatch)
    _client(module)
    module._limit_check("3/minute")
    assert module._limit_checks
    _client(module)  # setup_rate_limiter runs again: the old limiter's checks are dead weight
    assert not module._limit_checks


def test_a_redis_password_never_reaches_the_logs(monkeypatch, caplog):
    secret = "s3cr3t-p@ss"
    module = _load_rate_limit(monkeypatch)
    monkeypatch.setattr(module, "_build_storage", lambda cfg: (f"redis://default:{secret}@redis.example:6379/0", {}))
    with caplog.at_level(logging.DEBUG, logger=PKG):
        _client(module)  # lazy connect: Limiter() succeeds, the "enabled" line is logged
        monkeypatch.setattr(module, "Limiter", _boom)
        module._make_limiter(
            f"redis://default:{secret}@redis.example:6379/0", {}, key_func=lambda r: "k", default_limits=[], strategy="fixed-window", headers_enabled=False
        )
    assert caplog.records, "nothing was logged"
    assert "redis.example:6379/0" in caplog.text
    for part in (secret, "s3cr3t", "default:"):
        assert part not in caplog.text


def _boom(*args, **kwargs):
    if kwargs.get("storage_uri", "").startswith("memory"):
        return SimpleNamespace()
    raise ValueError(f"bad uri {kwargs['storage_uri']}")


def test_redact_storage_keeps_scheme_host_and_path(rl):
    assert rl._redact_storage("redis://u:p@w@host:6379/0") == "redis://host:6379/0"
    assert rl._redact_storage("rediss://:pw@host:6379/1") == "rediss://host:6379/1"
    assert rl._redact_storage("memory://") == "memory://"
