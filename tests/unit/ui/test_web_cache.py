"""Web-cache UI client and Flask route contracts."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call

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
    previous_dependencies = sys.modules.get("app.dependencies")
    sys.modules["app.dependencies"] = dependencies
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_dependencies is None:
            sys.modules.pop("app.dependencies", None)
        else:
            sys.modules["app.dependencies"] = previous_dependencies

    yield module, client
    sys.modules.pop(module_name, None)


@pytest.fixture
def route_app(web_cache_route):
    module, client = web_cache_route
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
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
    client.get_web_cache_status.return_value = {"node": {"enabled": True}}
    client.get_web_cache_metrics.return_value = {"node": {"hit": 3}}
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/web-cache"):
        assert module.web_cache_page.__wrapped__() == "rendered"

    render.assert_called_once_with(
        "web_cache.html",
        web_cache_status={"node": {"enabled": True}},
        web_cache_metrics={"node": {"hit": 3}},
    )


def test_page_keeps_metrics_when_status_fails(route_app, monkeypatch):
    module, client, app = route_app
    client.get_web_cache_status.side_effect = module.ApiClientError("status failed")
    client.get_web_cache_metrics.return_value = {"node": {"miss": 1}}
    render = Mock(return_value="rendered")
    flash = Mock()
    monkeypatch.setattr(module, "render_template", render)
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context("/web-cache"):
        assert module.web_cache_page.__wrapped__() == "rendered"

    flash.assert_called_once_with("Error fetching web cache status: status failed", "error")
    assert render.call_args.kwargs["web_cache_status"] == {}
    assert render.call_args.kwargs["web_cache_metrics"] == {"node": {"miss": 1}}


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
