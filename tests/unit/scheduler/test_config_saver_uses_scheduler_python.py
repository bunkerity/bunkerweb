"""The scheduler runs ``gen/save_config.py`` with its own interpreter, never through the shebang.

The script's shebang is ``/usr/bin/env python3``. On RHEL 9 that is the system Python 3.9, while the
dependencies (and the code, which needs 3.10+) live in the interpreter running the scheduler, so the
config saver died at import. ``subprocess_run`` has to get ``sys.executable`` as argv[0].

``src/scheduler/main.py`` cannot be imported (it starts the scheduler), so the call sites are cut out
of the source by AST: the two functions are run against a recorder, and the third site, which is
inline in the ``__main__`` block, is checked statically.
"""

import ast
import sys
from pathlib import Path
from subprocess import DEVNULL, STDOUT
from types import SimpleNamespace

MAIN = Path(__file__).resolve().parents[3] / "src" / "scheduler" / "main.py"
TREE = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
SAVER = Path("/usr/share/bunkerweb/gen/save_config.py")


def _function(name):
    node = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))


class _Logger:
    def __getattr__(self, level):
        return lambda *args, **kwargs: None


class _Client:
    readonly = False


def _namespace(calls):
    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0)

    return {
        "subprocess_run": fake_run,
        "sys_executable": sys.executable,
        "BUNKERWEB_PATH": Path("/usr/share/bunkerweb"),
        "LOGGER": _Logger(),
        "API_CLIENT": _Client(),
        "SCHEDULER": object(),
        "RUN": True,
        "RELOAD_SCAN_CONFIGS": False,
        "DEVNULL": DEVNULL,
        "STDOUT": STDOUT,
        "sep": "/",
        "join": lambda *parts: "/".join(parts).replace("//", "/"),
        "build_cmd_env": lambda: {},
        "NGINX_TMP_VARIABLES_PATH": Path("/nonexistent/variables.env"),
        "deepcopy": lambda value: value,
        "args": SimpleNamespace(variables=True),
        "tmp_variables_path": Path("/nonexistent/tmp-variables.env"),
        "env": {},
        "environ": {},
    }


def _run(name, *call_args):
    calls = []
    namespace = _namespace(calls)
    exec(compile(_function(name), str(MAIN), "exec"), namespace)  # noqa: S102
    namespace[name](*call_args)
    return calls


def test_sighup_reload_runs_the_saver_with_the_scheduler_python():
    (argv,) = _run("handle_reload", None, None)

    assert argv[:2] == [sys.executable, SAVER.as_posix()]


def test_plugin_rescan_runs_the_saver_with_the_scheduler_python():
    (argv,) = _run("run_config_saver", "log message")

    assert argv[:2] == [sys.executable, SAVER.as_posix()]


def test_every_saver_call_site_names_the_interpreter():
    """Includes the first-run site, which is inline in ``__main__`` and cannot be called alone."""
    sites = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "subprocess_run"
        and node.args
        and isinstance(node.args[0], ast.List)
    ]
    assert len(sites) == 3
    for site in sites:
        first = site.args[0].elts[0]
        assert isinstance(first, ast.Name) and first.id == "sys_executable", f"line {site.lineno} runs {ast.unparse(first)} first"
