"""CrowdSec router contract and decision-removal permission isolation."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request

ROOT = Path(__file__).resolve().parents[3]
ROUTER_PATH = ROOT / "src" / "api" / "app" / "routers" / "crowdsec.py"


def _load_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_resource_and_perm", "_extract_resource_id"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional, "PERM_VERB_BY_METHOD": {"GET": "read", "OPTIONS": "read", "DELETE": "delete"}}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def _load_router(api_db):
    prefix = "bw_crowdsec_test"
    modules = {
        prefix: ModuleType(prefix),
        f"{prefix}.auth": ModuleType(f"{prefix}.auth"),
        f"{prefix}.auth.guard": ModuleType(f"{prefix}.auth.guard"),
        f"{prefix}.routers": ModuleType(f"{prefix}.routers"),
        f"{prefix}.utils": ModuleType(f"{prefix}.utils"),
        "CrowdSec": ModuleType("CrowdSec"),
    }
    for name in (prefix, f"{prefix}.auth", f"{prefix}.routers"):
        modules[name].__path__ = [str(ROUTER_PATH.parent)]

    calls = []
    resolvers = _load_resolvers()

    def guard(request: Request):
        resource_type, permission = resolvers["_resolve_resource_and_perm"](request.url.path, request.method)
        resource_id = resolvers["_extract_resource_id"](request.url.path, resource_type)
        if not permission or not api_db.check_api_permission("alice", permission, resource_type=resource_type, resource_id=resource_id):
            raise HTTPException(status_code=403, detail="Forbidden")
        request.state.auth_subject = "alice"

    class CrowdSecError(Exception):
        def __init__(self, message, status=502):
            super().__init__(message)
            self.status = status

    class CrowdSecClient:
        def __init__(self, _db):
            pass

        def query(self, connection_id, action, params):
            calls.append((connection_id, action, params))
            return {"removed": True}

    modules[f"{prefix}.auth.guard"].guard = guard
    modules[f"{prefix}.utils"].get_db = lambda **_kwargs: object()
    modules[f"{prefix}.utils"].LOGGER = Mock()
    modules["CrowdSec"].CrowdSecClient = CrowdSecClient
    modules["CrowdSec"].CrowdSecError = CrowdSecError

    previous = {name: sys.modules.get(name) for name in modules}
    module_name = f"{prefix}.routers.crowdsec"
    previous[module_name] = sys.modules.get(module_name)
    sys.modules.update(modules)
    try:
        spec = importlib.util.spec_from_file_location(module_name, ROUTER_PATH)
        assert spec is not None and spec.loader is not None, "CrowdSec router source is missing"
        router_module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = router_module
        spec.loader.exec_module(router_module)
        return router_module, guard, calls
    finally:
        for name, saved in previous.items():
            if saved is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved


def test_crowdsec_acl_uses_its_own_permissions():
    resolve = _load_resolvers()["_resolve_resource_and_perm"]

    assert resolve("/crowdsec", "GET") == ("bans", "crowdsec_read")
    assert resolve("/crowdsec/connection/decisions", "GET") == ("bans", "crowdsec_read")
    assert resolve("/crowdsec/connection/decisions/7", "DELETE") == ("bans", "crowdsec_delete")


def test_global_ban_delete_does_not_authorize_crowdsec_removal(api_db):
    api_db.create_api_user("alice", b"hash-alice", method="manual", admin=False)
    api_db.grant_api_permission("alice", "ban_delete", resource_type="bans")
    module, guard, calls = _load_router(api_db)
    route_path = "/crowdsec/{connection_id}/decisions/{decision_id}"
    route = next(route for route in module.router.routes if route.path == route_path and "DELETE" in route.methods)
    assert (route.status_code or 200) == 200
    assert module.router.dependencies[0].dependency is guard

    from types import SimpleNamespace

    request = SimpleNamespace(
        url=SimpleNamespace(path="/crowdsec/connection-id/decisions/7"),
        method="DELETE",
        state=SimpleNamespace(),
    )
    with pytest.raises(HTTPException) as denied:
        guard(request)
    assert denied.value.status_code == 403
    assert calls == []

    api_db.grant_api_permission("alice", "crowdsec_delete", resource_type="bans")
    guard(request)
    result = module.remove("connection-id", 7, module.DecisionSelection(scope="Ip", value="192.0.2.1", decision_type="ban"), request)
    assert result == {"removed": True}
    assert calls == [("connection-id", "unban", {"scope": "Ip", "value": "192.0.2.1", "decision_type": "ban", "decision_id": 7})]


def test_biscuit_crowdsec_subject_rule_extracts_authority_username():
    from biscuit_auth import AuthorizerBuilder, BiscuitBuilder, KeyPair, Policy, Rule

    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    rule_call = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Rule")
    rule_text = ast.literal_eval(rule_call.args[0])
    token = BiscuitBuilder("user({username});", {"username": "alice"}).build(KeyPair().private_key)
    builder = AuthorizerBuilder()
    builder.add_policy(Policy("allow if true"))
    authorized = builder.build(token)
    authorized.authorize()

    subjects = authorized.query(Rule(rule_text))

    assert [str(subject.terms[0]) for subject in subjects] == ["alice"]
