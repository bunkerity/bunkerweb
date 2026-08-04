import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_workflows", "_resolve_resource_and_perm", "_extract_resource_id"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def test_workflow_acl_mapping():
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/workflows", "GET") == ("workflows", "workflow_read")
    assert resolve("/workflows/wf-1", "GET") == ("workflows", "workflow_read")
    assert resolve("/workflows/wf-1/definition", "GET") == ("workflows", "workflow_read")
    assert resolve("/workflows", "POST") == ("workflows", "workflow_create")
    assert resolve("/workflows/wf-1", "PATCH") == ("workflows", "workflow_update")
    assert resolve("/workflows/wf-1/definition", "PUT") == ("workflows", "workflow_update")
    assert resolve("/workflows/wf-1", "DELETE") == ("workflows", "workflow_delete")


def test_cloning_needs_create_not_read():
    """A clone writes a new resource, so reading the original is not enough."""
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/workflows/wf-1/clone", "POST") == ("workflows", "workflow_create")


def test_validating_a_draft_is_a_read():
    # It stores nothing — it is the editor asking whether a definition would be accepted.
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/workflows/validate", "POST") == ("workflows", "workflow_read")


def test_attachment_routes_need_the_assign_permission():
    # Attaching changes what a service enforces without touching the policy, and detaching
    # must not be granted by workflow_delete — both carry workflow_assign instead.
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/workflows/wf-1/attachments", "POST") == ("workflows", "workflow_assign")
    assert resolve("/workflows/wf-1/attachments/app1.example.com", "DELETE") == ("workflows", "workflow_assign")


def test_resource_id_extraction():
    extract = _load_resolvers()["_extract_resource_id"]
    assert extract("/workflows/wf-1", "workflows") == "wf-1"
    assert extract("/workflows/wf-1/definition", "workflows") == "wf-1"
    assert extract("/workflows", "workflows") is None


def test_permissions_are_declared_in_the_model_enum():
    # The guard rejects a permission the enum does not carry, so the two must stay in sync.
    model = (ROOT / "src" / "common" / "db" / "model.py").read_text(encoding="utf-8")
    for permission in ("workflow_read", "workflow_create", "workflow_update", "workflow_delete", "workflow_assign"):
        assert f'"{permission}"' in model
    resource_enum = model.split("API_RESOURCE_ENUM = Enum(", 1)[1].split(")", 1)[0]
    assert '"workflows"' in resource_enum


def test_the_router_prefix_matches_the_plugin_id():
    """The loader locks a plugin router to /<plugin_id>, so the id is what yields /workflows."""
    import json

    manifest = json.loads((ROOT / "src" / "common" / "core" / "workflows" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["id"] == "workflows"
    assert manifest["extensions"]["api"]["prefix"] == f"/{manifest['id']}"


def test_testing_a_draft_is_a_read_not_a_write():
    """It evaluates and stores nothing. Left to fall through to the POST line it would demand
    workflow_create, refusing a read-only operator a question they are entitled to ask."""
    resolve = _load_resolvers()["_resolve_resource_and_perm"]
    assert resolve("/workflows/wf-1/test", "POST") == ("workflows", "workflow_read")
