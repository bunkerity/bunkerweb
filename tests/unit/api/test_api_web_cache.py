"""FastAPI web-cache fanout and ACL mapping contracts."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace
from typing import Optional
from unittest.mock import Mock, call, patch

import schemas  # type: ignore

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_web_cache": ModuleType("bw_web_cache"),
        "bw_web_cache.routers": ModuleType("bw_web_cache.routers"),
        "bw_web_cache.auth": ModuleType("bw_web_cache.auth"),
        "bw_web_cache.auth.guard": ModuleType("bw_web_cache.auth.guard"),
        "bw_web_cache.deps": ModuleType("bw_web_cache.deps"),
        "bw_web_cache.schemas": schemas,
        "bw_web_cache.utils": ModuleType("bw_web_cache.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_web_cache"].__path__ = []
    names["bw_web_cache.routers"].__path__ = []
    names["bw_web_cache.auth"].__path__ = []
    names["bw_web_cache.auth.guard"].guard = object()
    names["bw_web_cache.deps"].get_instances_api_caller = object()
    names["bw_web_cache.utils"].get_db = lambda: SimpleNamespace(
        get_config=lambda **_kwargs: {},
        get_services=lambda **_kwargs: [],
    )
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "web_cache.py"
        spec = importlib.util.spec_from_file_location("bw_web_cache.routers.web_cache", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def test_status_and_metrics_fanout():
    caller = Mock()
    caller.send_to_apis.side_effect = [
        (True, {"node": {"enabled": True}}),
        (True, {"node": {"HIT": 2}}),
    ]

    status = ROUTER.web_cache_status(caller)
    metrics = ROUTER.web_cache_metrics(caller)

    assert (status.status_code, metrics.status_code) == (200, 200)
    assert status.content == {
        "status": "success",
        "instances": {"node": {"enabled": True}},
        "services": [],
        "message": None,
    }
    assert metrics.content == {
        "status": "success",
        "instances": {"node": {"HIT": 2}},
        "message": None,
    }
    assert caller.send_to_apis.call_args_list == [
        call("GET", "/proxy-cache/status", response=True),
        call("GET", "/metrics/reverseproxy", response=True),
    ]


def test_purge_forwards_validated_payload():
    caller = Mock()
    caller.send_to_apis.return_value = True, {"node": {"purged": 1}}
    request = schemas.WebCachePurgeRequest(scope="url", urls=[{"url": "https://example.com/a.js"}])

    response = ROUTER.web_cache_purge(request, caller)

    assert response.status_code == 200
    assert response.content["summary"] == {
        "requested": 1,
        "succeeded": 1,
        "failed": 0,
        "skipped": 0,
    }
    caller.send_to_apis.assert_called_once_with(
        "POST",
        "/proxy-cache/purge",
        data={"scope": "url", "urls": [{"url": "https://example.com/a.js"}]},
        response=True,
    )


def test_fanout_failure_is_503_with_structured_body():
    caller = Mock()
    caller.send_to_apis.return_value = False, None

    response = ROUTER.web_cache_status(caller)

    assert response.status_code == 503
    assert response.content == {
        "status": "error",
        "instances": {},
        "services": [],
        "message": "No BunkerWeb instance reported cache status",
    }


def test_status_partial_response_preserves_successes():
    caller = Mock()
    caller.send_to_apis.return_value = (
        False,
        {"node-a": {"status": "success", "data": {"enabled": True}}},
    )

    response = ROUTER.web_cache_status(caller)

    assert response.status_code == 207
    assert response.content["status"] == "partial"
    assert response.content["instances"]["node-a"]["data"]["enabled"] is True


def test_status_with_no_configured_instances_is_unavailable():
    caller = Mock()
    caller.send_to_apis.return_value = True, {}

    response = ROUTER.web_cache_status(caller)

    assert response.status_code == 503
    assert response.content["status"] == "error"


def test_status_includes_effective_service_enablement(monkeypatch):
    db = Mock()
    db.get_services.return_value = [
        {"id": "online.example", "is_draft": False},
        {"id": "draft.example", "is_draft": True},
    ]
    db.get_config.return_value = {
        "USE_PROXY_CACHE": "no",
        "online.example_USE_PROXY_CACHE": "yes",
    }
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    caller = Mock()
    caller.send_to_apis.return_value = True, {"node": {"status": "success"}}

    response = ROUTER.web_cache_status(caller)

    assert response.content["services"] == [
        {"id": "online.example", "enabled": True, "is_draft": False},
        {"id": "draft.example", "enabled": False, "is_draft": True},
    ]


def test_partial_purge_marks_unreachable_instances_skipped_without_queue():
    caller = Mock()
    caller.apis = [
        SimpleNamespace(endpoint="http://node-a:5000"),
        SimpleNamespace(endpoint="http://node-b:5000"),
        SimpleNamespace(endpoint="http://node-c:5000"),
    ]
    caller.send_to_apis.return_value = (
        False,
        {
            "node-a": {"status": "success", "data": {"purged": True}},
            "node-c": {"status": "error", "msg": "purge failed"},
        },
    )
    request = schemas.WebCachePurgeRequest(scope="all")

    response = ROUTER.web_cache_purge(request, caller)

    assert response.status_code == 207
    assert response.content["status"] == "partial"
    assert response.content["summary"] == {
        "requested": 3,
        "succeeded": 1,
        "failed": 1,
        "skipped": 1,
    }
    assert response.content["instances"]["node-b"] == {
        "status": "skipped",
        "reason": "unreachable",
        "queued": False,
    }


def test_native_purge_all_uses_module_not_shell_delete():
    lua = (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua").read_text(encoding="utf-8")
    nginx = (ROOT / "src" / "common" / "confs" / "api.conf").read_text(encoding="utf-8")

    assert 'ngx.location.capture("/_proxy-cache/purge-all"' in lua
    assert "-mindepth 1 -type f -delete" not in lua
    assert "proxy_cache_purge POST purge_all from all;" in nginx


def test_native_purge_remains_configured_when_no_service_cache_is_enabled():
    nginx = (ROOT / "src" / "common" / "confs" / "api.conf").read_text(encoding="utf-8")
    reverse_proxy = (ROOT / "src" / "common" / "core" / "reverseproxy" / "confs" / "http" / "reverse-proxy.conf").read_text(encoding="utf-8")

    assert 'has_variable(all, "USE_PROXY_CACHE", "yes")' not in nginx
    assert 'has_variable(all, "USE_PROXY_CACHE", "yes")' not in reverse_proxy
    assert "keys_zone=proxycache:" in reverse_proxy


def test_instance_purge_defensively_matches_api_limits_and_url_parts():
    lua = (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "api.lua").read_text(encoding="utf-8")

    assert "MAX_PROXY_CACHE_PURGE_URLS = 100" in lua
    assert "MAX_PROXY_CACHE_URL_LENGTH = 8192" in lua
    assert "MAX_PROXY_CACHE_KEY_TEMPLATE_LENGTH = 4096" in lua
    assert '["$http_host"] = authority' in lua
    assert 'uri:sub(1, 1) == "?"' in lua
    assert 'uri:find("#", 1, true)' in lua
    assert 'key_template:gsub("%$({?)([%w_]+)(}?)", substitute)' in lua


def test_openapi_metadata_lists_resource_groups_and_web_cache():
    main = (ROOT / "src" / "api" / "app" / "main.py").read_text(encoding="utf-8")

    assert '"name": "resource_groups"' in main
    assert '"name": "web_cache"' in main


def _load_acl_resolvers():
    path = ROOT / "src" / "api" / "app" / "auth" / "biscuit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"_resolve_web_cache", "_resolve_resource_and_perm"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {"Optional": Optional}
    exec(compile(ast.Module(nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_resolve_resource_and_perm"]


def test_web_cache_acl_mapping():
    resolve = _load_acl_resolvers()
    assert resolve("/web-cache/status", "GET") == ("web_cache", "web_cache_read")
    assert resolve("/web_cache/metrics", "OPTIONS") == ("web_cache", "web_cache_read")
    assert resolve("/web-cache/purge", "POST") == ("web_cache", "web_cache_purge")
    assert resolve("/web-cache/purge", "DELETE") == ("web_cache", None)
