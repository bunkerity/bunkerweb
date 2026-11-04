"""``bwcli`` sent unauthenticated requests when the API token lived only in the configuration.

``API`` falls back to the ``API_TOKEN`` environment variable, which a shell running ``bwcli`` does not
have: the token is stored in the database (or in ``variables.env``). ``CLI.__init__`` must read it
from its merged configuration and hand it to every API client it builds, both the per-instance
clients and the single local fallback client. The tests send a request through the built clients and
read the ``Authorization`` header, the one place the token becomes visible.

Refs: #3810.
"""

import sys
from pathlib import Path
from types import ModuleType

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

import API as API_MODULE  # noqa: E402
import CLI as CLI_MODULE  # noqa: E402


class _Response:
    status_code = 200
    content = b"{}"
    text = "{}"

    def json(self):
        return {}


@pytest.fixture
def sent_headers(monkeypatch):
    """Headers of every request the API clients send, in order."""
    sent = []

    def fake_request(method, url, **kwargs):
        sent.append(kwargs.get("headers", {}))
        return _Response()

    monkeypatch.setattr(API_MODULE, "request", fake_request)
    return sent


@pytest.fixture
def cli_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("BWCLI_API_URL", raising=False)
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: None)
    return tmp_path


def _install_database(monkeypatch, tmp_path, config, instances):
    class FakeDatabase:
        def __init__(self, *args, **kwargs):
            pass

        def get_metadata(self):
            return {"default": False, "is_initialized": True}

        def get_config(self, *args, **kwargs):
            return dict(config)

        def get_instances(self, *args, **kwargs):
            return list(instances)

    module = ModuleType("Database")
    module.Database = FakeDatabase
    module.DatabaseInitError = type("DatabaseInitError", (Exception,), {})
    module.mask_db_uri = lambda uri: uri
    monkeypatch.setitem(sys.modules, "Database", module)
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    monkeypatch.setattr(CLI_MODULE, "DB_PATH", db_dir)
    monkeypatch.setattr(CLI_MODULE, "resolve_variables", lambda *a, **k: {})


def test_token_from_the_database_reaches_every_instance_client(monkeypatch, cli_environment, sent_headers):
    instances = [{"hostname": "bw-one", "port": 5000}, {"hostname": "bw-two", "port": 5000}]
    _install_database(monkeypatch, cli_environment, {"API_TOKEN": "token-from-database"}, instances)

    cli = CLI_MODULE.CLI()

    assert len(cli.apis) == 2
    for api in cli.apis:
        api.request("GET", "ping")
    assert [headers.get("Authorization") for headers in sent_headers] == ["Bearer token-from-database"] * 2


def test_token_from_the_variables_file_reaches_the_local_fallback_client(monkeypatch, cli_environment, sent_headers):
    monkeypatch.setattr(CLI_MODULE, "DB_PATH", cli_environment / "absent")
    monkeypatch.setattr(CLI_MODULE, "resolve_variables", lambda *a, **k: {"API_TOKEN": "token-from-file"})

    cli = CLI_MODULE.CLI()

    assert len(cli.apis) == 1
    cli.apis[0].request("GET", "ping")
    assert sent_headers[0].get("Authorization") == "Bearer token-from-file"


def test_without_any_token_no_authorization_header_is_sent(monkeypatch, cli_environment, sent_headers):
    monkeypatch.setattr(CLI_MODULE, "DB_PATH", cli_environment / "absent")
    monkeypatch.setattr(CLI_MODULE, "resolve_variables", lambda *a, **k: {})

    cli = CLI_MODULE.CLI()
    cli.apis[0].request("GET", "ping")

    assert "Authorization" not in sent_headers[0]
