"""ACL resolution for the instances router, incl. GET /instances/{hostname}/health.

Same shape as ``test_plugins_acl.py``: parse ``biscuit.py`` and exec just the instances resolver,
so the (resource_type, permission) mapping is asserted without importing the whole auth stack.

The health route matters because the scheduler calls it on every healthcheck pass. Falling
through to the verb mapping would still land on ``instances_read`` today, but only by accident —
the explicit case is what keeps it stable if the fallback ever changes.
"""

import ast
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[3]


def _load_instances_resolver():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    nodes = [
        node
        for node in tree.body
        if (isinstance(node, ast.FunctionDef) and node.name == "_resolve_instances")
        or (isinstance(node, ast.Assign) and any(getattr(tgt, "id", None) == "PERM_VERB_BY_METHOD" for tgt in node.targets))
    ]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_resolve_instances"]


def test_instances_acl_mapping():
    resolve = _load_instances_resolver()
    assert resolve("/instances", "GET") == ("instances", "instances_read")
    assert resolve("/instances/ping", "GET") == ("instances", "instances_read")
    assert resolve("/instances/bw/ping", "GET") == ("instances", "instances_read")
    assert resolve("/instances/bw/health", "GET") == ("instances", "instances_read")
    assert resolve("/instances/reload", "POST") == ("instances", "instances_execute")
    assert resolve("/instances/bw/reload", "POST") == ("instances", "instances_execute")
    assert resolve("/instances/bw/stop", "POST") == ("instances", "instances_execute")


def test_health_is_read_only_for_other_methods():
    resolve = _load_instances_resolver()
    # Only GET/OPTIONS take the read shortcut; a POST to the same path must not inherit it.
    assert resolve("/instances/bw/health", "POST") == ("instances", "instances_create")
