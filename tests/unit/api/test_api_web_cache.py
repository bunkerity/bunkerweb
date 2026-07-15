"""FastAPI web-cache fanout and ACL mapping contracts."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
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
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi.responses"].JSONResponse = _Response
    names["bw_web_cache"].__path__ = []
    names["bw_web_cache.routers"].__path__ = []
    names["bw_web_cache.auth"].__path__ = []
    names["bw_web_cache.auth.guard"].guard = object()
    names["bw_web_cache.deps"].get_instances_api_caller = object()
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
    caller.send_to_apis.assert_called_once_with(
        "POST",
        "/proxy-cache/purge",
        data={"scope": "url", "urls": [{"url": "https://example.com/a.js"}]},
        response=True,
    )


def test_fanout_failure_is_502_with_fallback_body():
    caller = Mock()
    caller.send_to_apis.return_value = False, None

    response = ROUTER.web_cache_status(caller)

    assert response.status_code == 502
    assert response.content == {"status": "error", "msg": "internal error"}


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
