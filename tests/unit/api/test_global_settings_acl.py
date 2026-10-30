"""ACL resolution for the global settings endpoints.

The fine-grained permission a resolver returns is only meaningful if ``API_PERMISSION_ENUM``
actually carries that name: a grant row can never hold an unknown permission, so a resolver that
asks for one refuses every non-admin user (admins bypass the check). ``_resolve_global_settings``
asked for ``global_settings_read``/``global_settings_update`` while the enum only ever declared
``global_config_read``/``global_config_update``.

Mirrors ``test_plugins_acl.py``: parse the two files and exec just the resolver, so no
SQLAlchemy import and no auth stack are needed. Port of dev ``ca81f07c3``.
"""

import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_global_settings_resolver():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name == "_resolve_global_settings")
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_resolve_global_settings"]


def _enum_values(name: str) -> set:
    """The literal members of an ``Enum(...)`` in ``model.py``, read without importing it."""
    path = ROOT / "src" / "common" / "db" / "model.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == name for tgt in node.targets):
            return {arg.value for arg in node.value.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
    raise AssertionError(f"{name} not found in model.py")


def test_the_resolved_resource_and_permissions_exist_in_the_enums():
    resolve = _load_global_settings_resolver()
    known_perms = _enum_values("API_PERMISSION_ENUM")
    known_resources = _enum_values("API_RESOURCE_ENUM")
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        rtype, permission = resolve(method)
        assert rtype in known_resources, f"{method} /global_settings resolves to resource type {rtype!r}, which no grant row can hold"
        if permission is not None:
            assert permission in known_perms, f"{method} /global_settings resolves to {permission!r}, which no grant row can hold"


def test_global_settings_acl_mapping():
    resolve = _load_global_settings_resolver()
    assert resolve("GET") == ("global_config", "global_config_read")
    assert resolve("POST") == ("global_config", "global_config_update")
    assert resolve("PUT") == ("global_config", "global_config_update")
    assert resolve("PATCH") == ("global_config", "global_config_update")
    # DELETE has no fine-grained mapping; the resource type is still canonical.
    assert resolve("DELETE") == ("global_config", None)
