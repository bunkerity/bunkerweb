"""REDIS_SSL_CA has to reach the Python clients, not just exist as a setting.

With ``REDIS_SSL_VERIFY`` at its product default (yes) every Python client verifies against the
system/certifi trust store -- redis-py's ``SSLConnection`` defaults to ``ssl_cert_reqs="required"``
-- and that store never holds a private CA. A perfectly valid certificate therefore failed
``CERTIFICATE_VERIFY_FAILED``, and the only escape was ``REDIS_SSL_VERIFY=no``, which turns
verification off for every consumer at once. ``REDIS_SSL_CA`` names a bundle to trust instead.

The Celery broker needs no client-side plumbing: the all-in-one derivation puts ``ssl_ca_certs``
in the URL and both kombu and ``redis.Redis.from_url`` read it back out (guarded in
``tests/unit/integrations/test_all_in_one_broker_url.py``). The two consumers that do NOT go
through that URL are guarded here:

* ``common_utils.get_redis_client`` -- ``bwcli``, the ``sync-bans`` job and the web UI (twice).
* ``api/app/rate_limit.py`` ``_build_storage`` -- the API's rate-limit storage.

Both are loaded without their real dependencies: redis-py is not in the unit venv, and
``rate_limit`` imports fastapi/slowapi, which are not either. So a fake ``redis`` module records
the kwargs, and ``_build_storage`` is exec'd from its own AST slice -- the shipped source, not a
copy, so a change to the function is a change to what this test runs.

The negative half matters as much as the positive one: with the setting unset, nothing may carry
an ``ssl_*`` key it did not carry before.
"""

import ast
import sys
from json import loads
from os import environ
from pathlib import Path
from runpy import run_path
from types import ModuleType
from typing import Any, Dict, Optional, Tuple
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
SYNC_BANS = ROOT.joinpath("src", "common", "core", "jobs", "jobs", "sync-bans.py")
sys.path.append(ROOT.joinpath("src", "common", "utils").as_posix())

from common_utils import get_redis_client  # noqa: E402

# --------------------------------------------------------------------------------------
# common_utils.get_redis_client
# --------------------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def ping(self):
        return True


class _FakeSentinel:
    def __init__(self, sentinels, **kwargs):
        self.sentinels = sentinels
        self.kwargs = kwargs
        _FakeSentinel.last = self

    def discover_master(self, name):
        return ("master", 6379)

    def master_for(self, *args, **kwargs):
        return _FakeClient(**kwargs)


@pytest.fixture
def fake_redis():
    """Stand in for redis-py, which the unit venv does not install.

    ``get_redis_client`` imports it *inside* the function and returns None on ImportError, so
    without this the call under test would quietly return None and every assertion below would
    be vacuous -- the failure mode the fixture exists to prevent.
    """
    module = ModuleType("redis")
    module.StrictRedis = _FakeClient
    module.Sentinel = _FakeSentinel
    with patch.dict(sys.modules, {"redis": module}):
        yield


def test_the_ca_reaches_a_direct_connection(fake_redis):
    client = get_redis_client(use_redis=True, redis_host="valkey", redis_ssl=True, redis_ssl_ca="/etc/bunkerweb/redis-ca.pem")
    assert client is not None, "the fake redis module was not picked up; the assertion below would be vacuous"
    assert client.kwargs["ssl"] is True
    assert client.kwargs["ssl_ca_certs"] == "/etc/bunkerweb/redis-ca.pem"


def test_the_ca_reaches_a_sentinel_connection(fake_redis):
    client = get_redis_client(
        use_redis=True,
        redis_sentinel_hosts="sentinel1:26379 sentinel2:26379",
        redis_sentinel_master="mymaster",
        redis_ssl=True,
        redis_ssl_ca="/etc/bunkerweb/redis-ca.pem",
    )
    assert client is not None
    assert _FakeSentinel.last.kwargs["ssl_ca_certs"] == "/etc/bunkerweb/redis-ca.pem"


def test_tls_verification_can_be_disabled_without_emitting_the_ca(fake_redis):
    client = get_redis_client(
        use_redis=True,
        redis_host="valkey",
        redis_ssl=True,
        redis_ssl_ca="/etc/bunkerweb/redis-ca.pem",
        redis_ssl_verify=False,
    )
    assert client is not None
    assert client.kwargs["ssl_cert_reqs"] == "none"
    assert "ssl_ca_certs" not in client.kwargs


def test_tls_verification_stays_required_by_default(fake_redis):
    client = get_redis_client(use_redis=True, redis_host="valkey", redis_ssl=True)
    assert client is not None
    assert "ssl_cert_reqs" not in client.kwargs, "redis-py's required default must remain in effect"


def test_sync_bans_forwards_disabled_tls_verification():
    captured = {}

    def capture_redis_client(**kwargs):
        captured.update(kwargs)
        raise RuntimeError("stop after Redis configuration")

    job_instance = Mock()
    job_instance.db.get_metadata.return_value = {"scheduler_first_start": False}
    job = ModuleType("jobs")
    job.Job = Mock(return_value=job_instance)
    logger = ModuleType("logger")
    logger.getLogger = Mock(return_value=Mock())
    api = ModuleType("API")
    api.API = Mock()
    api_caller = ModuleType("ApiCaller")
    api_caller.ApiCaller = Mock()
    common_utils = ModuleType("common_utils")
    common_utils.get_redis_client = capture_redis_client

    with (
        patch.dict(sys.modules, {"jobs": job, "logger": logger, "API": api, "ApiCaller": api_caller, "common_utils": common_utils}),
        patch.dict(environ, {"USE_REDIS": "yes", "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no"}),
        pytest.raises(SystemExit),
    ):
        run_path(str(SYNC_BANS), run_name="__main__")

    assert captured["redis_ssl_verify"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # nothing asked for
        {"redis_ssl": True},  # TLS without a CA: the system store, exactly as before
        {"redis_ssl_ca": "/etc/bunkerweb/redis-ca.pem"},  # a CA without TLS is not a reason to send one
    ],
    ids=["plain", "tls-no-ca", "ca-without-tls"],
)
def test_nothing_new_travels_when_the_ca_is_not_in_play(fake_redis, kwargs):
    client = get_redis_client(use_redis=True, redis_host="valkey", **kwargs)
    assert client is not None
    assert "ssl_ca_certs" not in client.kwargs
    assert "ssl_cert_reqs" not in client.kwargs


# --------------------------------------------------------------------------------------
# api/app/rate_limit.py :: _build_storage
# --------------------------------------------------------------------------------------

RATE_LIMIT = ROOT.joinpath("src", "api", "app", "rate_limit.py")


def _build_storage(cfg: Dict[str, Any], env: Optional[Dict[str, str]] = None) -> Tuple[str, Dict[str, Any]]:
    """Run the shipped ``_build_storage`` out of its own AST slice.

    ``rate_limit`` cannot be imported here (fastapi/slowapi are not unit-test dependencies), and
    a copy of the function would drift silently. Slicing the two functions it needs out of the
    real file keeps this executing the code that ships. ``getenv`` is bound to ``env`` so the
    environment-wins-over-database branch is exercised deliberately instead of leaking in from
    whatever the test runner happens to export.
    """
    env = env or {}
    tree = ast.parse(RATE_LIMIT.read_text(encoding="utf-8"), filename=str(RATE_LIMIT))
    wanted = {"_build_storage", "_try_json"}
    found = {node.name for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted}
    assert found == wanted, f"rate_limit.py no longer defines {sorted(wanted - found)} at module level -- update this test with the code it guards"

    sliced = ast.Module(body=[node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted], type_ignores=[])

    class _ApiConfig:
        API_RATE_LIMIT_STORAGE_OPTIONS = ""

    namespace: Dict[str, Any] = {
        "Dict": Dict,
        "Any": Any,
        "Tuple": Tuple,
        "Optional": Optional,
        "loads": loads,
        "getenv": lambda name, default=None: env.get(name, default),
        "api_config": _ApiConfig,
    }
    exec(compile(sliced, "rate_limit-slice", "exec"), namespace)  # noqa: S102
    return namespace["_build_storage"](cfg)


BASE = {"USE_REDIS": "yes", "REDIS_HOST": "valkey"}


def test_the_api_rate_limiter_trusts_the_ca_while_verification_is_on():
    storage, options = _build_storage({**BASE, "REDIS_SSL": "yes", "REDIS_SSL_CA": "/etc/bunkerweb/redis-ca.pem"})
    assert storage == "rediss://valkey:6379/0"
    assert options["ssl_ca_certs"] == "/etc/bunkerweb/redis-ca.pem"
    assert "ssl_cert_reqs" not in options, "verification is on; forcing ssl_cert_reqs here would change the default"


def test_the_ca_is_not_emitted_when_nothing_is_verified():
    """``REDIS_SSL_VERIFY=no`` sets ``ssl_cert_reqs=None``. A CA alongside it would be dead
    configuration that reads, in the options dump, as though it were in use."""
    _, options = _build_storage({**BASE, "REDIS_SSL": "yes", "REDIS_SSL_VERIFY": "no", "REDIS_SSL_CA": "/etc/bunkerweb/redis-ca.pem"})
    assert options["ssl_cert_reqs"] is None
    assert "ssl_ca_certs" not in options


def test_the_ca_reaches_the_sentinel_options_too():
    _, options = _build_storage(
        {
            "USE_REDIS": "yes",
            "REDIS_SENTINEL_HOSTS": "sentinel1:26379 sentinel2",
            "REDIS_SENTINEL_MASTER": "mymaster",
            "REDIS_SSL": "yes",
            "REDIS_SSL_CA": "/etc/bunkerweb/redis-ca.pem",
        }
    )
    assert options["ssl_ca_certs"] == "/etc/bunkerweb/redis-ca.pem"
    assert options["sentinel_kwargs"]["ssl_ca_certs"] == "/etc/bunkerweb/redis-ca.pem"


def test_the_environment_still_wins_over_the_database():
    _, options = _build_storage(
        {**BASE, "REDIS_SSL": "yes", "REDIS_SSL_CA": "/from-db.pem"},
        env={"REDIS_SSL_CA": "/from-env.pem"},
    )
    assert options["ssl_ca_certs"] == "/from-env.pem"


@pytest.mark.parametrize(
    "cfg",
    [
        {**BASE, "REDIS_SSL": "yes"},  # TLS, no CA
        {**BASE, "REDIS_SSL_CA": "/etc/bunkerweb/redis-ca.pem"},  # CA, no TLS
        BASE,  # neither
    ],
    ids=["tls-no-ca", "ca-without-tls", "neither"],
)
def test_the_options_are_unchanged_when_the_ca_is_not_in_play(cfg):
    _, options = _build_storage(cfg)
    assert options == {"socket_timeout": 1.0, "socket_connect_timeout": 1.0, "socket_keepalive": True, "max_connections": 10}
