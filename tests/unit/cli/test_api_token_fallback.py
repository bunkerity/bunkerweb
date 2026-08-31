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
BW_VARIABLES_ENV = ("/", "etc", "bunkerweb", "variables.env")
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

        # `parse_env_file` reads the whole file at once; `CLI` still builds paths through
        # `Path(...)`, so both accessors have to exist on the stub.
        def read_text(self, encoding=None):
            return files[self._parts]

        def as_posix(self):
            return "/".join(self._parts).replace("//", "/")

    return FakePath


def _build_cli(monkeypatch, *, variables: str, instances=None, api_url=None, bw_variables=None, metadata=None):
    """Drive the real CLI.__init__ with the filesystem, Redis and terminal stubbed out."""
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("API_SERVER_NAME", raising=False)
    monkeypatch.delenv("BWCLI_API_URL", raising=False)
    if api_url:
        monkeypatch.setenv("BWCLI_API_URL", api_url)

    files = {VARIABLES_ENV: variables} if variables is not None else {}
    if bw_variables is not None:
        files[BW_VARIABLES_ENV] = bw_variables
    dirs = {DB_DIR} if instances is not None else set()
    fake_path = _fake_path_factory(files, dirs)
    monkeypatch.setattr(CLI_MODULE, "Path", fake_path)
    # `VARIABLES_PATHS` is built at import time with the real `Path`, so patching the name alone
    # leaves `CLI.__init__` reading the host's own files.
    monkeypatch.setattr(CLI_MODULE, "VARIABLES_PATHS", (fake_path(*VARIABLES_ENV), fake_path(*BW_VARIABLES_ENV)))
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: None)
    monkeypatch.setattr(CLI_MODULE, "get_terminal_size", lambda: Mock(columns=80))

    if instances is not None:
        config = dict(line.split("=", 1) for line in variables.splitlines() if "=" in line)
        db = Mock()
        # An uninitialized schema makes `CLI.__init__` exit, so the healthy metadata is part of
        # the stub rather than of any single test.
        db.get_metadata.return_value = metadata if metadata is not None else {"default": False, "is_initialized": True}
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

    def test_an_explicit_bwcli_api_url_overrides_database_discovery(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=the-global-one\nAPI_SERVER_NAME=control.example\n",
            instances=[{"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi"}],
            api_url="https://bw-api.example:5443",
        )
        assert [api.endpoint for api in cli.apis] == ["https://bw-api.example:5443/"]
        assert [api.host for api in cli.apis] == ["control.example"]
        assert _tokens(cli) == ["the-global-one"]

    def test_a_database_value_cannot_silently_disable_instance_discovery(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=the-global-one\nBWCLI_API_URL=https://stale.example:5443\n",
            instances=[{"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi"}],
        )
        assert [api.endpoint for api in cli.apis] == ["http://10.0.0.1:5000/"]

    def test_a_whitespace_environment_value_does_not_override_instance_discovery(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=the-global-one\n",
            instances=[{"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi"}],
            api_url="   ",
        )
        assert [api.endpoint for api in cli.apis] == ["http://10.0.0.1:5000/"]


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


class TestWhereDatabaseUriComesFrom:
    """`8f38c4b77`: /etc/nginx/variables.env only exists once an instance has rendered its
    configuration. On a Linux install that has not happened yet, DATABASE_URI lives in
    /etc/bunkerweb/variables.env, and reading the generated file alone left it empty -- so the
    CLI silently opened the default SQLite file instead of the stack's database."""

    def test_the_linux_variables_file_is_read_when_the_generated_one_is_absent(self, monkeypatch):
        cli = _build_cli(
            monkeypatch,
            variables=None,
            bw_variables="DATABASE_URI=postgresql://bunkerweb@db/bunkerweb\nAPI_TOKEN=from-etc-bunkerweb\n",
        )
        assert _tokens(cli) == ["from-etc-bunkerweb"]

    def test_the_generated_file_wins_where_both_declare_the_key(self, monkeypatch):
        """First path listed wins: the rendered configuration is the more specific one."""
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=from-etc-nginx\n",
            bw_variables="API_TOKEN=from-etc-bunkerweb\n",
        )
        assert _tokens(cli) == ["from-etc-nginx"]

    def test_an_empty_value_does_not_shadow_the_other_file(self, monkeypatch):
        """`variables.env` is written for every key, so the generated file carries `KEY=` for a
        setting it has no value for. Taking that as "declared" is what left DATABASE_URI empty."""
        cli = _build_cli(
            monkeypatch,
            variables="API_TOKEN=\n",
            bw_variables="API_TOKEN=from-etc-bunkerweb\n",
        )
        assert _tokens(cli) == ["from-etc-bunkerweb"]

    def test_an_uninitialized_database_exits_instead_of_tracebacking(self, monkeypatch):
        """SQLAlchemy creates the SQLite file on connect, so an unresolved URI connects fine and
        raises on the first query. Exiting names the actual problem."""
        with pytest.raises(SystemExit) as excinfo:
            _build_cli(
                monkeypatch,
                variables="API_TOKEN=whatever\n",
                instances=[{"hostname": "10.0.0.1", "port": 5000, "server_name": "bwapi"}],
                metadata={"default": True, "is_initialized": False},
            )
        assert excinfo.value.code == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
