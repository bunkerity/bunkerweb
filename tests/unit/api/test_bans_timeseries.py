"""Bans ACL verb fallback, without the 1.7-only timeseries endpoint."""

import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]
BISCUIT = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"


def _load_bans_resolver():
    tree = ast.parse(BISCUIT.read_text(encoding="utf-8"), filename=str(BISCUIT))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name == "_resolve_bans")
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(BISCUIT), "exec"), namespace)
    return namespace["_resolve_bans"]


class TestAcl:
    def test_the_new_get_resolves_to_ban_read_through_the_verb_fallback(self):
        assert _load_bans_resolver()("/bans/timeseries", "GET") == ("bans", "ban_read")

    def test_it_resolves_the_same_way_the_other_read_routes_do(self):
        resolve = _load_bans_resolver()
        assert resolve("/bans/timeseries", "GET") == resolve("/bans", "GET") == resolve("/bans/instances", "GET")

    def test_a_write_verb_on_the_same_path_does_not_inherit_read(self):
        """The fallback is per-verb: reading the chart must not become a way to mutate bans."""
        resolve = _load_bans_resolver()
        assert resolve("/bans/timeseries", "POST") == ("bans", "ban_created")
        assert resolve("/bans/timeseries", "DELETE") == ("bans", "ban_delete")
        assert resolve("/bans/timeseries", "PATCH") == ("bans", "ban_update")

    def test_an_unknown_verb_resolves_to_no_permission_rather_than_a_default_grant(self):
        assert _load_bans_resolver()("/bans/timeseries", "TRACE") == ("bans", None)
