import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_certificates", "_resolve_resource_groups", "_resolve_resource_and_perm", "_extract_resource_id"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def test_certificate_acl_mapping():
    namespace = _load_resolvers()
    resolve = namespace["_resolve_resource_and_perm"]
    assert resolve("/certificates", "GET") == ("certificates", "certificate_read")
    assert resolve("/certificates/upload", "POST") == ("certificates", "certificate_create")
    assert resolve("/certificates/cert-1/download", "GET") == ("certificates", "certificate_download")
    assert resolve("/certificates/cert-1/attachments", "POST") == ("certificates", "certificate_assign")
    assert resolve("/certificates/cert-1/renew", "POST") == ("certificates", "certificate_renew")
    assert resolve("/certificates/cert-1/revoke", "POST") == ("certificates", "certificate_revoke")


def test_provider_certificate_acl_mapping():
    namespace = _load_resolvers()
    resolve = namespace["_resolve_resource_and_perm"]
    extract = namespace["_extract_resource_id"]

    assert resolve("/selfsigned/certificates", "POST") == ("certificates", "certificate_create")
    assert resolve("/customcert/certificates/upload", "POST") == ("certificates", "certificate_create")
    assert resolve("/selfsigned/certificates/renew-due", "POST") == ("certificates", "certificate_renew")
    assert resolve("/letsencrypt/certificates/orphans", "GET") == ("certificates", "certificate_read")
    assert extract("/letsencrypt/certificates/orphans", "certificates") is None
    assert extract("/selfsigned/certificates/renew-due", "certificates") is None


def test_resource_group_acl_mapping():
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/resource_groups", "GET") == ("resource_groups", "resource_group_read")
    assert resolve("/resource_groups", "POST") == ("resource_groups", "resource_group_create")
    assert resolve("/resource_groups/group-1/clone", "POST") == ("resource_groups", "resource_group_clone")


def test_action_paths_do_not_become_resource_ids():
    extract = _load_resolvers()["_extract_resource_id"]
    assert extract("/certificates/upload", "certificates") is None
    assert extract("/certificates/renew", "certificates") is None
    assert extract("/certificates/cert-1", "certificates") == "cert-1"
