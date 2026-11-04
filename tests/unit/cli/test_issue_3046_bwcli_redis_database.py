"""``bwcli`` always read Redis database 0 because it looked up ``REDIS_DB`` instead of ``REDIS_DATABASE``.

``CLI.__init__`` builds its Redis client from the merged configuration. The test pins that a non-zero
``REDIS_DATABASE`` reaches the client builder, so ban commands read the database the instances write to,
and that the database still defaults to 0. The Web UI half is pinned in ``tests/unit/ui/routes``.

Refs: #3046.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _p in (
    _ROOT / "src" / "common" / "cli",
    _ROOT / "src" / "common" / "api",
    _ROOT / "src" / "common" / "utils",
    _ROOT / "src" / "common" / "db",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import CLI as CLI_MODULE  # noqa: E402


@pytest.fixture
def redis_calls(monkeypatch, tmp_path):
    """Keyword arguments of every Redis client ``CLI`` builds, with the configuration read from ``variables.env``."""
    calls = []
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("BWCLI_API_URL", raising=False)
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "DB_PATH", tmp_path / "absent")
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: calls.append(kwargs) or object())
    return calls


def test_a_non_zero_redis_database_reaches_the_client(monkeypatch, redis_calls):
    monkeypatch.setattr(CLI_MODULE, "resolve_variables", lambda *a, **k: {"USE_REDIS": "yes", "REDIS_HOST": "redis", "REDIS_DATABASE": "7"})

    CLI_MODULE.CLI()

    assert [call["redis_db"] for call in redis_calls] == ["7"]


def test_the_database_defaults_to_zero(monkeypatch, redis_calls):
    monkeypatch.setattr(CLI_MODULE, "resolve_variables", lambda *a, **k: {"USE_REDIS": "yes", "REDIS_HOST": "redis"})

    CLI_MODULE.CLI()

    assert [call["redis_db"] for call in redis_calls] == ["0"]
