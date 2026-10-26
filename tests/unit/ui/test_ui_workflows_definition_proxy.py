"""Canonical export proxy, and the Overview / Configuration shell of the workflow pages."""

from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader
from test_ui_workflows import route_app, workflows_route  # noqa: F401  (fixtures)

from app.api_client import ApiClientError

TEMPLATES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"


def test_definition_proxy_returns_canonical_data_in_readonly(route_app):  # noqa: F811
    module, api, _, app = route_app
    api.readonly = True
    definition = {"schema_version": 1, "rules": [{"id": "r1", "enabled": False}]}
    api.get_workflow_definition.return_value = {"status": "success", "definition": definition, "summaries": []}
    app.config["LOGIN_DISABLED"] = True
    with app.test_client() as client:
        response = client.get("/workflows/wf-1/definition", headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 200
    assert response.json == {"definition": definition}
    assert response.headers["Cache-Control"] == "no-store"
    api.get_workflow_definition.assert_called_once_with("wf-1")
    assert not api.save_workflow_definition.called


@pytest.mark.parametrize("status", [403, 404, 503])
def test_definition_proxy_preserves_api_refusal(route_app, status):  # noqa: F811
    module, api, _, app = route_app
    api.get_workflow_definition.side_effect = ApiClientError("Refused", status)
    app.config["LOGIN_DISABLED"] = True
    with app.test_client() as client:
        response = client.get("/workflows/wf-1/definition", headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == status
    assert "definition" not in response.json


def _tabs(active, count, config_id):
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    env.globals.update(_=lambda key, **kw: key, url_for=lambda *a, **kw: "/workflows")
    macro = env.get_template("workflow_shell.html").module.workflow_tabs
    return str(macro(active, count, config_id))


def test_the_shell_opens_the_workflow_the_configuration_tab_names():
    html = _tabs("overview", 3, "wf-9")
    assert 'href="/workflows/wf-9"' in html
    assert "data-wf-config-tab" in html
    # the responsive View select lists both sections and marks the current one
    assert '<option value="/workflows" selected>' in html
    assert '<option value="/workflows/wf-9">' in html
    assert 'aria-current="page"' in html


def test_the_configuration_tab_is_disabled_until_a_workflow_exists():
    html = _tabs("overview", 0, None)
    assert 'aria-disabled="true"' in html
    assert "data-wf-config-tab" not in html
    assert html.count("<option") == 1


def test_the_editor_route_feeds_the_header_switcher(route_app, monkeypatch):  # noqa: F811
    module, api, _, app = route_app
    app.config["LOGIN_DISABLED"] = True
    api.get_workflow.return_value = {"id": "wf-1", "name": "One", "services": [], "definition": {"rules": []}, "last_update": "2026-10-20T10:00:00"}
    api.get_resource_groups.return_value = {}
    api.get_workflows.return_value = {"workflows": [{"id": "wf-1", "name": "One"}, {"id": "wf-2", "name": "Two"}]}
    captured = {}
    monkeypatch.setattr(module, "render_template", lambda name, **context: captured.update(name=name, **context) or "")
    with app.test_client() as client:
        assert client.get("/workflows/wf-1").status_code == 200
    assert captured["name"] == "workflow_editor.html"
    assert [item["id"] for item in captured["switcher"]] == ["wf-1", "wf-2"]
