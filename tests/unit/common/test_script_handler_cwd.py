"""The `script` action's cwd must follow the example-stack MARKER, not a leftover directory.

`tests/core_handlers/script_handler.py` runs an example-backed spec's script from
`/tmp/example-stack`. It used to decide that on the directory alone, while every other consumer
(`start.sh` in five places, `utils.sh:restart_stack`) keys on `/tmp/example_stack.txt` -- and the
example cleanup (`test-example-hook.sh`) removes only the marker, leaving the directory behind.
So after any example-backed run on the box, every subsequent CORE spec's script action silently
ran from that leftover directory instead of the repo root, and any repo-relative path in it
failed. Seen live: geoip.yml's seed action dying on
`cp: cannot stat 'tests/core/geoip/fixtures/geoip-test-city.mmdb'` with the fixtures plainly
present.
"""

import importlib.util
import sys
from logging import getLogger
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
TESTS = ROOT / "tests"


@pytest.fixture
def handler(monkeypatch):
    monkeypatch.syspath_prepend(str(TESTS))
    # core_handlers/__init__.py pulls in the whole handler set, several of which import the
    # docker SDK and selenium; import the one module directly instead.
    for name in ("docker", "selenium"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    spec = importlib.util.spec_from_file_location("_script_handler_under_test", TESTS / "core_handlers" / "script_handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(handler, monkeypatch, tmp_path, *, marker: bool, directory: bool):
    """Return the cwd script_handler would use for the given /tmp state."""
    stack_dir = tmp_path / "example-stack"
    marker_file = tmp_path / "example_stack.txt"
    if directory:
        stack_dir.mkdir()
    if marker:
        marker_file.write_text(f"{stack_dir}/docker-compose.yml")

    monkeypatch.setattr(handler, "EXAMPLE_STACK_DIR", stack_dir)
    monkeypatch.setattr(handler, "EXAMPLE_STACK_MARKER", marker_file)

    seen = {}

    def fake_run(_argv, **kwargs):
        seen["cwd"] = kwargs.get("cwd")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(handler, "run", fake_run)
    action = SimpleNamespace(script=["true"], success=True, result=None)
    handler.handle(getLogger("test"), action)
    return seen["cwd"], stack_dir


def test_leftover_directory_without_marker_does_not_hijack_the_cwd(handler, monkeypatch, tmp_path):
    """The regression: directory present, marker gone -> must run from the repo root (cwd None)."""
    cwd, _ = _run(handler, monkeypatch, tmp_path, marker=False, directory=True)
    assert cwd is None


def test_marker_and_directory_together_select_the_example_stack(handler, monkeypatch, tmp_path):
    """A real example-backed run still runs from the example stack."""
    cwd, stack_dir = _run(handler, monkeypatch, tmp_path, marker=True, directory=True)
    assert cwd == stack_dir


def test_marker_without_directory_falls_back_to_the_repo_root(handler, monkeypatch, tmp_path):
    """A stale marker pointing at a directory that is gone must not set a nonexistent cwd."""
    cwd, _ = _run(handler, monkeypatch, tmp_path, marker=True, directory=False)
    assert cwd is None
