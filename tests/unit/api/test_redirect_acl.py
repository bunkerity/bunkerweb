import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_redirects", "_resolve_resource_and_perm", "_extract_resource_id"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def test_redirect_acl_mapping():
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/redirects", "GET") == ("redirects", "redirect_read")
    assert resolve("/redirects/red-1", "GET") == ("redirects", "redirect_read")
    assert resolve("/redirects", "POST") == ("redirects", "redirect_create")
    assert resolve("/redirects/red-1", "PATCH") == ("redirects", "redirect_update")
    assert resolve("/redirects/red-1", "PUT") == ("redirects", "redirect_update")
    assert resolve("/redirects/red-1", "DELETE") == ("redirects", "redirect_delete")


def test_attachment_routes_need_the_assign_permission():
    # Attaching changes what a service serves without touching the rule, and detaching must
    # not be granted by redirect_delete — both carry redirect_assign instead.
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/redirects/red-1/attachments", "POST") == ("redirects", "redirect_assign")
    assert resolve("/redirects/red-1/attachments/app1.example.com", "DELETE") == ("redirects", "redirect_assign")


def test_resource_id_extraction():
    extract = _load_resolvers()["_extract_resource_id"]
    assert extract("/redirects/red-1", "redirects") == "red-1"
    assert extract("/redirects/red-1/attachments", "redirects") == "red-1"
    assert extract("/redirects", "redirects") is None


def test_permissions_are_declared_in_the_model_enum():
    # The guard rejects a permission the enum does not carry, so the two must stay in sync.
    model = (ROOT / "src" / "common" / "db" / "model.py").read_text(encoding="utf-8")
    for permission in ("redirect_read", "redirect_create", "redirect_update", "redirect_delete", "redirect_assign"):
        assert f'"{permission}"' in model
    assert '"redirects",\n    name="api_resource_enum"' in model
