"""Exact durable report details reuse metrics read authorization."""

import ast
from unittest.mock import Mock

import pytest

from test_metrics_dashboard import ROOT, _load_router

ROUTER = _load_router()


def test_exact_detail_returns_payload_and_missing_is_404(monkeypatch):
    db = Mock()
    db.get_metrics_request_data.return_value = {"events": [{"url": "/kept"}]}
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    response = ROUTER.query_metrics_request_data("request-1", instance_hostname="node-1")
    assert response.status_code == 200
    assert response.content["data"] == {"events": [{"url": "/kept"}]}
    db.get_metrics_request_data.assert_called_once_with("request-1", instance_hostname="node-1")
    db.get_metrics_request_data.return_value = None
    assert ROUTER.query_metrics_request_data("missing").status_code == 404


@pytest.mark.parametrize("request_id,hostname", [("x" * 65, None), ("bad id", None), ("../id", None), ("ok", "x" * 257), ("ok", "bad\nhost")])
def test_invalid_identifiers_never_reach_database(monkeypatch, request_id, hostname):
    db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    assert ROUTER.query_metrics_request_data(request_id, instance_hostname=hostname).status_code == 400
    db.get_metrics_request_data.assert_not_called()


def test_detail_has_same_guard_and_permission_as_other_metrics_reads():
    module = ast.parse((ROOT / "src/api/app/routers/metrics.py").read_text())
    functions = {node.name: node for node in module.body if isinstance(node, ast.FunctionDef)}
    for name in ("query_metrics_requests", "query_metrics_request_data"):
        decorator = functions[name].decorator_list[0]
        dependencies = next(keyword.value for keyword in decorator.keywords if keyword.arg == "dependencies")
        assert ast.unparse(dependencies) == "[Depends(guard)]"
    # Generic resolver maps every GET /metrics/... to metrics_read and resource id requests.
    source = (ROOT / "src/api/app/auth/biscuit.py").read_text()
    function = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "_resolve_resource_and_perm")
    namespace = {"Optional": __import__("typing").Optional, "PERM_VERB_BY_METHOD": {"GET": "read"}}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "permission-resolver", "exec"), namespace)
    resolve = namespace["_resolve_resource_and_perm"]
    assert resolve("/metrics/requests/r/data", "GET") == resolve("/metrics/requests", "GET") == ("metrics", "metrics_read")
