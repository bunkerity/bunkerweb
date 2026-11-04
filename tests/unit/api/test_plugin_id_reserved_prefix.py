"""A plugin id may not live in the push swap's reserved namespace (port of dev ``1a76b2943``).

``pushswap.RESERVED_PREFIX`` is ``.bw-``: the instance-side swap keeps its own bookkeeping under
that prefix (``.bw-trash``, the parked originals) and exempts it from the stale-entry sweep. A
plugin whose id starts with it therefore lands in a directory the sweep will not remove, so the
plugin survives its own deletion — and its files keep being served after the operator deleted it.

Both gates get the same guard: the API's path-supplied ``plugin_id`` and the UI's plugin name.
Read out of the sources by AST so no FastAPI/Flask import is needed.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA_PUSHSWAP = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "pushswap.lua"


def _regex_literal(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == name for tgt in node.targets):
            call = node.value
            assert isinstance(call, ast.Call) and call.args, f"{name} is not a compiled regex"
            return call.args[0].value
    raise AssertionError(f"{name} not found in {path}")


PATTERNS = {
    "api": _regex_literal(ROOT / "src" / "api" / "app" / "routers" / "plugins.py", "_PLUGIN_ID_RX"),
    "ui": _regex_literal(ROOT / "src" / "ui" / "app" / "utils.py", "PLUGIN_NAME_RX"),
}


def test_the_reserved_prefix_is_still_what_the_swap_uses():
    """If the Lua side renames the namespace, these guards have to follow it."""
    lua = LUA_PUSHSWAP.read_text(encoding="utf-8")
    assert 'pushswap.RESERVED_PREFIX = ".bw-"' in lua


@pytest.mark.parametrize("gate", sorted(PATTERNS))
@pytest.mark.parametrize("plugin_id", (".bw-trash", ".bw-swap", ".bw-anything.here"))
def test_a_reserved_plugin_id_is_refused(gate, plugin_id):
    assert re.match(PATTERNS[gate], plugin_id) is None, f"{gate} gate accepts {plugin_id!r}"


@pytest.mark.parametrize("gate", sorted(PATTERNS))
@pytest.mark.parametrize("plugin_id", ("bunkernet", "my.plugin", "my-plugin_2", ".bwvalid", "bw-plugin"))
def test_an_ordinary_plugin_id_still_passes(gate, plugin_id):
    assert re.match(PATTERNS[gate], plugin_id) is not None, f"{gate} gate refuses {plugin_id!r}"


@pytest.mark.parametrize("gate", sorted(PATTERNS))
@pytest.mark.parametrize("plugin_id", ("bad", "plugin\n", "plugin/../etc", "a" * 65))
def test_the_existing_shape_rules_are_untouched(gate, plugin_id):
    assert re.match(PATTERNS[gate], plugin_id) is None, f"{gate} gate accepts {plugin_id!r}"
