import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_upstreams", "_resolve_resource_and_perm", "_extract_resource_id"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def test_upstream_acl_mapping():
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/upstreams", "GET") == ("upstreams", "upstream_read")
    assert resolve("/upstreams/up-1", "GET") == ("upstreams", "upstream_read")
    assert resolve("/upstreams", "POST") == ("upstreams", "upstream_create")
    assert resolve("/upstreams/up-1", "PATCH") == ("upstreams", "upstream_update")
    assert resolve("/upstreams/up-1", "PUT") == ("upstreams", "upstream_update")
    assert resolve("/upstreams/up-1", "DELETE") == ("upstreams", "upstream_delete")


def test_attachment_routes_need_the_assign_permission():
    # Attaching changes what a service proxies without touching the pool, and detaching must
    # not be granted by upstream_delete — both carry upstream_assign instead.
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/upstreams/up-1/attachments", "POST") == ("upstreams", "upstream_assign")
    assert resolve("/upstreams/up-1/attachments/app1.example.com", "DELETE") == ("upstreams", "upstream_assign")


def test_resource_id_extraction():
    extract = _load_resolvers()["_extract_resource_id"]
    assert extract("/upstreams/up-1", "upstreams") == "up-1"
    assert extract("/upstreams/up-1/attachments", "upstreams") == "up-1"
    assert extract("/upstreams", "upstreams") is None


def test_permissions_are_declared_in_the_model_enum():
    # The guard rejects a permission the enum does not carry, so the two must stay in sync.
    model = (ROOT / "src" / "common" / "db" / "model.py").read_text(encoding="utf-8")
    for permission in ("upstream_read", "upstream_create", "upstream_update", "upstream_delete", "upstream_assign"):
        assert f'"{permission}"' in model
    resource_enum = model.split("API_RESOURCE_ENUM = Enum(", 1)[1].split(")", 1)[0]
    assert '"upstreams"' in resource_enum
