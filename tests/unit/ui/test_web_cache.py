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


# --------------------------------------------------------------------------------------
# Render tests — the aggregate distribution widget
#
# The route tests above mock ``render_template``, so nothing here was covered by them.
# These follow ``test_bans_stats.py``'s standalone-Jinja-env pattern.
# --------------------------------------------------------------------------------------

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def _render_web_cache(status_totals, **overrides):
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

    env = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": "{% block head %}{% endblock %}{% block content %}{% endblock %}"}),
                FileSystemLoader(TEMPLATES),
            ]
        ),
        autoescape=True,
    )
    env.globals.update(csrf_token=lambda: "test-token", url_for=lambda endpoint, **kwargs: "/" + "/".join([endpoint, *kwargs.values()]))
    total = sum(status_totals.values())
    context = {
        "cache_statuses": ["HIT", "MISS", "BYPASS", "EXPIRED", "STALE", "UPDATING", "REVALIDATED"],
        "status_totals": {status: 0 for status in ("HIT", "MISS", "BYPASS", "EXPIRED", "STALE", "UPDATING", "REVALIDATED")} | status_totals,
        "summary": {
            "total_requests": total,
            "hit_rate": round(status_totals.get("HIT", 0) / total * 100, 1) if total else None,
            "enabled_services": 1,
            "active_services": 1,
            "reporting_count": 1,
            "total_instances": 1,
            "total_files": 0,
            "total_size_bytes": 0,
        },
        "services_data": [],
        "instances_data": [],
        "is_readonly": False,
        "style_nonce": "nonce",
    }
    context.update(overrides)
    return env.get_template("web_cache.html").render(**context)


def test_metrics_widget_links_its_stylesheet():
    """The CSS is a separate file; a page that forgets the link renders an unstyled bar."""
    html = _render_web_cache({"HIT": 3, "MISS": 1})

    assert "css/pages/web-cache.css" in html


def test_metrics_widget_renders_one_segment_per_non_zero_status():
    html = _render_web_cache({"HIT": 750, "MISS": 250})

    assert '<div class="wc-stack"' in html
    assert 'style="width: 75.00%"' in html
    assert 'style="width: 25.00%"' in html
    # Zero-count statuses contribute no segment at all.
    assert html.count('<i class="bg-') == 2
    # The stacked Bootstrap progress bar it replaces is gone.
    assert "progress-bar" not in html


def test_metrics_widget_is_one_image_not_seven_progressbars():
    """A stacked share bar is a single figure; each slice is not its own 0-100 gauge."""
    html = _render_web_cache({"HIT": 750, "MISS": 250})

    assert '<div class="wc-stack" role="img" aria-label="Cache status distribution: HIT 75.0%, MISS 25.0%"' in html
    assert 'role="progressbar"' not in html
    assert "aria-valuenow" not in html


def test_metrics_legend_carries_count_and_share_for_each_status():
    html = _render_web_cache({"HIT": 12345, "MISS": 55})

    assert '<span class="wc-leg-val">12,345</span>' in html
    assert '<span class="wc-leg-val">55</span>' in html
    assert "99.6%" in html
    assert "0.4%" in html


def test_metrics_widget_marks_a_sub_tenth_share_rather_than_rounding_it_to_zero():
    """A single request in a million is not 0.0% — the old round(1) said it was."""
    html = _render_web_cache({"HIT": 999_999, "STALE": 1})

    assert "&lt;0.1%" in html
    # Not "0.0%" — which is what round(1) produced and what this replaces.
    assert '<span class="wc-leg-pct font-monospace">0.0%</span>' not in html
    # The slice still exists in the bar even though it is invisible at this width.
    assert 'style="width: 0.00%"' in html


def test_metrics_widget_falls_back_to_the_empty_state_with_no_traffic():
    html = _render_web_cache({})

    assert "wc-stack" not in html
    assert 'id="web-cache-metrics-empty"' in html
