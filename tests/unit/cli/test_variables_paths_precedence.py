"""``bwcli`` reads the operator's ``DATABASE_URI``, not the loading render's default
(port of dev d97f69835).

``/etc/nginx/variables.env`` is generated output: during the loading render it carries plugin
defaults for every setting ``start.sh`` does not whitelist, ``DATABASE_URI`` among them. Reading it
before ``/etc/bunkerweb/variables.env`` made that default win, so a fresh boot (or any instance that
has not re-rendered yet) sent ``bwcli`` at the default SQLite path instead of the operator's real
database. ``CLI.__init__`` keeps first-write-wins (``if not self.__variables.get(key)``), so the fix
is entirely in the order of ``OPERATOR_VARIABLES_PATHS`` / ``GENERATED_VARIABLES_PATHS`` — this test
reads those from the real module rather than assuming them, so a regression that swaps them back
flips the assertion, not just the fixture.
"""

import sys
from io import StringIO
from pathlib import Path as RealPath
from types import ModuleType

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

        def read_text(self, encoding=None):
            return files[self._parts]

        def as_posix(self):
            return "/".join(self._parts).replace("//", "/")

    return FakePath


def test_the_operators_file_wins_over_the_loading_renders_default(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("BWCLI_API_URL", raising=False)

    # Capture the real, currently-shipped order before Path gets patched.
    real_operator = [p.parts for p in CLI_MODULE.OPERATOR_VARIABLES_PATHS]
    real_generated = [p.parts for p in CLI_MODULE.GENERATED_VARIABLES_PATHS]
    real_order = real_operator + real_generated

    files = {}
    for parts in real_order:
        if parts in real_generated:
            files[parts] = "DATABASE_URI=sqlite:////var/tmp/loading-default.sqlite3\n"
        else:
            files[parts] = "DATABASE_URI=sqlite:////var/lib/bunkerweb/db.sqlite3\n"

    fake_path = _fake_path_factory(files, dirs=set())
    monkeypatch.setattr(CLI_MODULE, "Path", fake_path)
    monkeypatch.setattr(CLI_MODULE, "OPERATOR_VARIABLES_PATHS", tuple(fake_path(*parts) for parts in real_operator))
    monkeypatch.setattr(CLI_MODULE, "GENERATED_VARIABLES_PATHS", tuple(fake_path(*parts) for parts in real_generated))
    monkeypatch.setattr(CLI_MODULE, "VARIABLES_PATHS", tuple(fake_path(*parts) for parts in real_order))
    monkeypatch.setattr(CLI_MODULE, "handle_docker_secrets", lambda: {})
    monkeypatch.setattr(CLI_MODULE, "get_redis_client", lambda **kwargs: None)

    captured = {}

    def fake_database(*args, **kwargs):
        captured["sqlalchemy_string"] = kwargs.get("sqlalchemy_string")
        db = type(
            "FakeDB",
            (),
            {
                "get_metadata": lambda self: {"default": False, "is_initialized": True},
                "get_config": lambda self, *a, **k: {},
                "get_instances": lambda self, *a, **k: [],
            },
        )()
        return db

    module = ModuleType("Database")
    module.Database = fake_database
    monkeypatch.setitem(sys.modules, "Database", module)
    # The db directory only needs to `exist()`, which our FakePath always answers False for
    # (dirs=set()) unless it's DB_DIR -- patch exists() narrowly via a dirs set instead.
    monkeypatch.setattr(fake_path, "exists", lambda self: self._parts == DB_DIR, raising=False)

    CLI_MODULE.CLI()

    assert captured["sqlalchemy_string"] == "sqlite:////var/lib/bunkerweb/db.sqlite3", (
        "bwcli must prefer /etc/bunkerweb/variables.env's DATABASE_URI over the loading render's " f"default, got {captured['sqlalchemy_string']!r}"
    )


def test_the_shipped_paths_are_the_ones_the_scheduler_unit_exports():
    """The merge logic above runs on substituted paths, so the shipped tuples get their own check.

    ``bunkerweb-scheduler.sh`` exports ``/etc/bunkerweb/variables.env`` then
    ``/etc/bunkerweb/scheduler.env``; a Scheduler Only install writes DATABASE_URI to the second
    file and nowhere else, so bwcli has to read both, in that order (port of dev ``25e6cfc97``).
    """
    operator = [p.as_posix() for p in CLI_MODULE.OPERATOR_VARIABLES_PATHS]
    generated = [p.as_posix() for p in CLI_MODULE.GENERATED_VARIABLES_PATHS]
    assert operator == ["/etc/bunkerweb/variables.env", "/etc/bunkerweb/scheduler.env"]
    assert generated == ["/etc/nginx/variables.env"]
    # The generated render never counts as an operator file, whatever else moves.
    assert "/etc/nginx/variables.env" not in operator
    assert [p.as_posix() for p in CLI_MODULE.VARIABLES_PATHS] == operator + generated
