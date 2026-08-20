"""`bwcli` reads API_TOKEN from the configuration, because a shell has no environment.

F-CLI-2. `API.__init__` ends with `token if token is not None else getenv("API_TOKEN")`, and a
shell running `bwcli` inherits none of the service environment — so every request went out with no
token and the API answered 401. The token lives in the database, or in `/etc/nginx/variables.env`.

Coverage note, and the reason this file exists: `test_ban_reporting.py` covers F-CLI-1 only, and a
branch-coverage run over the lines this row changed showed CLI.py:149, :155 and :167 — the token
read and BOTH call sites that consume it — with zero coverage. The row was shipped untested.

Every test clears `API_TOKEN` from the environment first. Leaving it set makes `API.__init__`'s own
fallback supply the token, and these tests would pass against the unfixed code.
"""

import sys
from io import StringIO
from pathlib import Path as RealPath
from types import ModuleType
from unittest.mock import Mock

import pytest

_ROOT = RealPath(__file__).resolve().parents[3]
for _p in (
    _ROOT / "src" / "common" / "cli",
    _ROOT / "src" / "common" / "api",
    _ROOT / "src" / "common" / "utils",
    _ROOT / "src" / "common" / "db",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import CLI as CLI_MODULE  # noqa: E402
from API import API  # noqa: E402

VARIABLES_ENV = ("/", "etc", "nginx", "variables.env")
DB_DIR = ("/", "usr", "share", "bunkerweb", "db")


def _fake_path_factory(files: dict, dirs: set):
    class FakePath:
        def __init__(self, *parts):
            self._parts = tuple(str(p) for p in parts)

        def is_file(self):
            return self._parts in files

        def exists(self):
            return self._parts in dirs

        def open(self):
            return StringIO(files[self._parts])

    return FakePath


def _build_cli(monkeypatch, *, variables: str, instances=None):
    """Drive the real CLI.__init__ with the filesystem, Redis and terminal stubbed out."""
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("API_SERVER_NAME", raising=False)

    files = {VARIABLES_ENV: variables}
    dirs = {DB_DIR} if instances is not None else set()
    monkeypatch.setattr(CLI_MODULE, "Path", _fake_path_factory(files, dirs))
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: None)
    monkeypatch.setattr(CLI_MODULE, "get_terminal_size", lambda: Mock(columns=80))

    if instances is not None:
        config = dict(line.split("=", 1) for line in variables.splitlines() if "=" in line)
        db = Mock()
        db.get_config.return_value = config
        db.get_instances.return_value = instances
        module = ModuleType("Database")
        module.Database = lambda *a, **k: db
        monkeypatch.setitem(sys.modules, "Database", module)

    return CLI_MODULE.CLI()


def _tokens(cli):
    return [api._API__token for api in cli.apis]


class TestTheShellHasNoEnvironment:
    """No database on this host: the single local endpoint is built from variables.env."""

    def test_the_token_comes_from_variables_env(self, monkeypatch):
        cli = _build_cli(monkeypatch, variables="API_TOKEN=from-variables-env\nAPI_SERVER_NAME=bwapi\n")
        assert _tokens(cli) == ["from-variables-env"]

    def test_no_token_anywhere_stays_none_rather_than_becoming_empty_string(self, monkeypatch):
        """`or None` matters: API treats "" as a supplied token and sends `Bearer `, which is a 401
        that looks like a configured token rather than a missing one."""
        cli = _build_cli(monkeypatch, variables="API_TOKEN=\n")
        assert _tokens(cli) == [None]

    def test_an_absent_key_is_also_none(self, monkeypatch):
        cli = _build_cli(monkeypatch, variables="API_SERVER_NAME=bwapi\n")
        assert _tokens(cli) == [None]


class TestTheDatabasePath:
    """With a database, one API per registered instance — the other call site."""

    def test_an_instance_without_its_own_credential_gets_the_fallback(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=from-the-database\n",
            instances=[{"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi"}],
        )
        assert _tokens(cli) == ["from-the-database"]

    def test_a_per_instance_credential_still_wins(self, monkeypatch):
        """FALLBACK, not override. `API.from_instance` uses `instance.get("credential") or token`,
        so an instance carrying its own credential must keep it -- the whole point of per-instance
        tokens is that they differ from the global one."""
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=the-global-one\n",
            instances=[
                {"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi", "credential": "mine-alone"},
                {"hostname": "10.0.0.2", "port": 5000, "server_name": "bwapi"},
            ],
        )
        assert _tokens(cli) == ["mine-alone", "the-global-one"]

    def test_an_invalid_instance_is_skipped_without_taking_the_others_down(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=the-global-one\n",
            instances=[
                {"hostname": "not a host name", "port": 5000, "server_name": "bwapi"},
                {"hostname": "10.0.0.2", "port": 5000, "server_name": "bwapi"},
            ],
        )
        assert _tokens(cli) == ["the-global-one"]


def test_the_environment_is_still_honoured_when_it_does_exist():
    """Not a regression of the fix: inside a container the env is set, and API's own fallback
    must keep working. Asserted against API directly, since that is where the fallback lives."""
    import os

    os.environ["API_TOKEN"] = "from-the-environment"
    try:
        assert API("http://10.0.0.1:5000", "bwapi")._API__token == "from-the-environment"
        assert API("http://10.0.0.1:5000", "bwapi", token="explicit")._API__token == "explicit"
    finally:
        del os.environ["API_TOKEN"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
