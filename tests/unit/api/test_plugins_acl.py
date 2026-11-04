"""ACL resolution for the plugins router — PATCH /plugins/{id} (enable/disable toggle).

Mirrors ``test_certificate_acl.py``: parse ``biscuit.py`` and exec just the plugins resolver
so the (resource_type, permission) mapping is asserted without importing the whole auth stack.
"""

import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_plugins_resolver():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name == "_resolve_plugins")
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_resolve_plugins"]


def test_plugins_acl_mapping():
    resolve = _load_plugins_resolver()
    assert resolve("/plugins", "GET") == ("plugins", "plugin_read")
    assert resolve("/plugins/myplugin", "GET") == ("plugins", "plugin_read")
    assert resolve("/plugins/upload", "POST") == ("plugins", "plugin_create")
    # The new enable/disable toggle: PATCH /plugins/{id} -> plugin_create (no separate update perm)
    assert resolve("/plugins/myplugin", "PATCH") == ("plugins", "plugin_create")
    assert resolve("/plugins/myplugin", "DELETE") == ("plugins", "plugin_delete")
