"""Web-cache UI client and Flask route contracts."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call, patch

import pytest
from flask import Flask

from app.api_client import ApiClient


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def web_cache_route():
    """Load route without booting container-only app.dependencies state."""
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    module_name = "app.routes._web_cache_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "web_cache.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def route_app(web_cache_route):
    module, client = web_cache_route
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    client.get_instances.return_value = []
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.web_cache)
    return module, client, app


def test_api_client_status_and_metrics_paths(api_client, monkeypatch):
    get = Mock(side_effect=[{"enabled": True}, {"hit": 3, "miss": 1}])
    monkeypatch.setattr(api_client, "_get", get)

    assert api_client.get_web_cache_status() == {"enabled": True}
    assert api_client.get_web_cache_metrics() == {"hit": 3, "miss": 1}
    assert get.call_args_list == [call("/web-cache/status"), call("/web-cache/metrics")]


def test_template_uses_semantic_cache_status_palette():
    source = (Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates" / "web_cache.html").read_text(encoding="utf-8")

    assert '"EXPIRED": "warning"' in source
    assert '"UPDATING": "info"' in source
    assert '"REVALIDATED": "primary"' in source
    assert '"REVALIDATED": "danger"' not in source


def test_api_client_purge_payloads(api_client, monkeypatch):
    post = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_post", post)

    api_client.purge_web_cache()
    post.assert_called_once_with("/web-cache/purge", json={"scope": "all"})

    urls = [{"url": "https://example.com/asset.js"}]
    api_client.purge_web_cache(scope="url", urls=urls)
    assert post.call_args_list[-1] == call("/web-cache/purge", json={"scope": "url", "urls": urls})


def test_page_forwards_status_and_metrics(route_app, monkeypatch):
    module, client, app = route_app
    client.get_web_cache_status.return_value = {
        "status": "success",
        "instances": {"node": {"status": "success", "msg": {"enabled": True, "file_count": 2, "size_bytes": 12}}},
        "services": [{"id": "example.com", "enabled": True, "is_draft": False}],
    }
    client.get_web_cache_metrics.return_value = {
        "status": "success",
        "instances": {"node": {"data": {"counter_cache_status_HIT": 3, "counter_cache_status_MISS": 1}}},
    }
    client.get_instances.return_value = [{"hostname": "node", "name": "Node A"}]
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/web-cache"):
        assert module.web_cache_page.__wrapped__() == "rendered"

    context = render.call_args.kwargs
    assert context["services_data"] == [{"id": "example.com", "enabled": True, "is_draft": False}]
    assert context["instances_data"][0] == {
        "hostname": "node",
        "name": "Node A",
        "reachable": True,
        "response_error": False,
        "enabled": True,
        "file_count": 2,
        "size_bytes": 12,
        "path": None,
        "counters": {"HIT": 3, "MISS": 1},
        "total_requests": 4,
    }
    assert context["summary"]["hit_rate"] == 75.0
    assert context["summary"]["enabled_services"] == 1


def test_page_keeps_metrics_when_status_fails(route_app, monkeypatch):
    module, client, app = route_app
    client.get_web_cache_status.side_effect = module.ApiClientError("status failed")
    client.get_web_cache_metrics.return_value = {"status": "success", "instances": {"node": {"data": {"counter_cache_status_MISS": 1}}}}
    client.get_instances.return_value = []
    render = Mock(return_value="rendered")
    flash = Mock()
    monkeypatch.setattr(module, "render_template", render)
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context("/web-cache"):
        assert module.web_cache_page.__wrapped__() == "rendered"

    flash.assert_called_once_with("Error fetching web cache status: status failed", "error")
    assert render.call_args.kwargs["instances_data"] == []
    assert render.call_args.kwargs["status_totals"]["MISS"] == 0


def test_page_distinguishes_instance_error_from_empty_cache(route_app, monkeypatch):
    module, client, app = route_app
    client.get_web_cache_status.return_value = {
        "status": "partial",
        "instances": {"node": {"status": "error", "msg": "status failed"}},
        "services": [],
    }
    client.get_web_cache_metrics.return_value = {"status": "success", "instances": {}}
    client.get_instances.return_value = [{"hostname": "node", "name": "Node A"}]
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/web-cache"):
        assert module.web_cache_page.__wrapped__() == "rendered"

    instance = render.call_args.kwargs["instances_data"][0]
    assert instance["reachable"] is True
    assert instance["response_error"] is True
    assert instance["enabled"] is None


def test_purge_rejects_readonly(route_app):
    module, client, app = route_app
    client.readonly = True

    with app.test_request_context("/web-cache/purge", method="POST", data={"scope": "all"}):
        response = module.web_cache_purge.__wrapped__()

    assert response.status_code == 403
    client.purge_web_cache.assert_not_called()


def test_purge_rejects_blank_url(route_app, monkeypatch):
    module, client, app = route_app
    flash = Mock()
    monkeypatch.setattr(module, "flask_flash", flash)

    with app.test_request_context("/web-cache/purge", method="POST", data={"scope": "url", "url": "   "}):
        response = module.web_cache_purge.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("A URL is required to purge by URL", "error")
    client.purge_web_cache.assert_not_called()


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ({"scope": "all"}, call(scope="all", urls=None)),
        ({"scope": "url", "url": " https://example.com/asset.js "}, call(scope="url", urls=[{"url": "https://example.com/asset.js"}])),
        (
            {"scope": "url", "url": "https://example.com/asset.js", "key": " $scheme$host$uri "},
            call(scope="url", urls=[{"url": "https://example.com/asset.js", "key": "$scheme$host$uri"}]),
        ),
    ],
)
def test_purge_forwards_payload(route_app, monkeypatch, form, expected):
    module, client, app = route_app
    monkeypatch.setattr(module, "flask_flash", Mock())

    with app.test_request_context("/web-cache/purge", method="POST", data=form):
        response = module.web_cache_purge.__wrapped__()

    assert response.status_code == 302
    assert client.purge_web_cache.call_args == expected


def test_purge_flashes_api_error(route_app, monkeypatch):
    module, client, app = route_app
    client.purge_web_cache.side_effect = module.ApiUnavailableError("offline")
    flash = Mock()
    monkeypatch.setattr(module, "flask_flash", flash)

    with app.test_request_context("/web-cache/purge", method="POST", data={"scope": "all"}):
        response = module.web_cache_purge.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("Error purging web cache: offline", "error")


def test_partial_purge_flashes_preserved_and_skipped_counts(route_app, monkeypatch):
    module, client, app = route_app
    client.purge_web_cache.return_value = {
        "status": "partial",
        "summary": {"succeeded": 2, "failed": 1, "skipped": 1},
    }
    flash = Mock()
    monkeypatch.setattr(module, "flask_flash", flash)

    with app.test_request_context("/web-cache/purge", method="POST", data={"scope": "all"}):
        response = module.web_cache_purge.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with(
        "Web cache purged on 2 instance(s); 1 failed and 1 unreachable instance(s) were skipped (nothing was queued).",
        "warning",
    )
