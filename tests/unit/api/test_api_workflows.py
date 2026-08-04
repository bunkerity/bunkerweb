"""Workflow router response and rollback contracts.

The router ships inside the plugin, so it is loaded here the way the plugin loader loads
it — under a synthetic package, with FastAPI and ``app.utils`` stubbed — rather than through
a live app.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src" / "common" / "core" / "workflows"


class _Router:
    def __init__(self, **_kwargs):
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    patch = get
    put = get
    delete = get


class _JSONResponse:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.body = json.dumps(content).encode()


def _load_router():
    modules = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "app": ModuleType("app"),
        "app.utils": ModuleType("app.utils"),
        "bw_workflows": ModuleType("bw_workflows"),
        "bw_workflows.api": ModuleType("bw_workflows.api"),
    }
    modules["app"].__path__ = []
    modules["bw_workflows"].__path__ = [str(PLUGIN)]
    # Real path, so ``from .schemas import ...`` loads the plugin's own Pydantic models.
    modules["bw_workflows.api"].__path__ = [str(PLUGIN / "api")]
    modules["fastapi"].APIRouter = _Router
    modules["fastapi"].Query = lambda default=..., **_kwargs: default
    modules["fastapi.responses"].JSONResponse = _JSONResponse
    modules["app.utils"].get_db = Mock()

    saved = {name: sys.modules.get(name) for name in modules}
    sys.modules.update(modules)
    try:
        path = PLUGIN / "api" / "router.py"
        spec = importlib.util.spec_from_file_location("bw_workflows.api.router", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        schemas = sys.modules["bw_workflows.api.schemas"]
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
    return module, schemas


ROUTER, SCHEMAS = _load_router()


def _json(response):
    return json.loads(response.body)


def _rule(rule_id="r1"):
    return {
        "id": rule_id,
        "name": "block FR",
        "enabled": True,
        "condition": {"op": "country", "values": ["FR"]},
        "action": {"type": "block"},
        "threshold": None,
    }


def _workflow(services=None, rules=None):
    return {
        "id": "wf-1",
        "name": "login-protection",
        "description": "",
        "schema_version": 1,
        "rules_count": len(rules or []),
        "enabled_rules_count": len(rules or []),
        "services": services or [],
        "definition": {"schema_version": 1, "rules": rules or []},
    }


def test_list_contract(monkeypatch):
    db = Mock()
    db.get_workflows.return_value = {"items": [_workflow()], "total": 1, "offset": 0, "limit": 100}
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.list_workflows(search="", service_id="", offset=0, limit=100)

    assert response.status_code == 200
    body = _json(response)
    assert body["total"] == 1 and body["workflows"][0]["id"] == "wf-1"


def test_create_attaches_every_requested_service(monkeypatch):
    db = Mock()
    db.create_workflow.return_value = ("wf-1", "")
    db.attach_workflow.return_value = ""
    db.get_workflow_details.return_value = _workflow(["a.example.com", "b.example.com"])
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = SCHEMAS.WorkflowCreateRequest(name="login-protection", service_ids=["a.example.com", "b.example.com"])
    response = ROUTER.create_workflow(payload)

    assert response.status_code == 201
    assert db.attach_workflow.call_count == 2


def test_create_rolls_back_when_an_attachment_is_refused(monkeypatch):
    db = Mock()
    db.create_workflow.return_value = ("wf-1", "")
    # The second service is already at its rule budget, so the whole creation is undone.
    db.attach_workflow.side_effect = ["", "Service b.example.com would hold 101 active workflow rules"]
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    payload = SCHEMAS.WorkflowCreateRequest(name="login-protection", service_ids=["a.example.com", "b.example.com"])
    response = ROUTER.create_workflow(payload)

    assert response.status_code == 400
    assert db.delete_workflow.called
    assert db.detach_workflow.call_count == 2


def test_saving_an_invalid_definition_returns_the_anchored_errors(monkeypatch):
    db = Mock()
    errors = [{"path": "rules[0].condition.value", "code": "regex_invalid", "message": "Invalid regular expression"}]
    db.save_workflow_definition.return_value = ("Invalid regular expression", errors)
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.save_workflow_definition("wf-1", SCHEMAS.WorkflowDefinitionRequest(definition={"schema_version": 1, "rules": []}))

    assert response.status_code == 400
    # The editor needs the path to anchor the message on the offending node.
    assert _json(response)["errors"] == errors


def test_validate_reports_invalid_without_failing_the_request(monkeypatch):
    db = Mock()
    errors = [{"path": "rules[0].condition", "code": "group_missing", "message": "Resource group ghost does not exist"}]
    db.validate_workflow_definition.return_value = (None, errors)
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.validate_workflow(SCHEMAS.WorkflowValidateRequest(definition={"schema_version": 1, "rules": []}))

    # A draft that does not validate is a successful answer to "is this valid?", not a 4xx.
    assert response.status_code == 200
    body = _json(response)
    assert body["valid"] is False and body["errors"] == errors


def test_validate_returns_a_summary_per_rule(monkeypatch):
    db = Mock()
    db.validate_workflow_definition.return_value = ({"schema_version": 1, "rules": [_rule()]}, [])
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.validate_workflow(SCHEMAS.WorkflowValidateRequest(definition={"schema_version": 1, "rules": [_rule()]}))

    body = _json(response)
    assert body["valid"] is True
    assert body["summaries"] == [{"id": "r1", "summary": "If country is FR, then block"}]


def test_a_budget_overflow_is_reported_as_a_field_error(monkeypatch):
    db = Mock()
    # The db layer emits the anchored triplet now, so the router no longer builds one by hand.
    errors = [{"path": "rules", "code": "budget_exceeded", "message": "Service a.example.com would hold 101 active workflow rules"}]
    db.validate_workflow_definition.return_value = ({"schema_version": 1, "rules": []}, errors)
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.validate_workflow(SCHEMAS.WorkflowValidateRequest(definition={"schema_version": 1, "rules": []}, service_ids=["a.example.com"]))

    body = _json(response)
    assert body["valid"] is False and body["errors"] == errors


def test_a_missing_challenge_credential_fails_validation_not_just_the_save(monkeypatch):
    """Validate ran fewer checks than save, so the editor said valid and Save answered 400."""
    db = Mock()
    message = "Service a.example.com cannot serve a hcaptcha challenge: ANTIBOT_HCAPTCHA_SITEKEY is not configured"
    errors = [{"path": "rules", "code": "provider_missing", "message": message}]
    db.validate_workflow_definition.return_value = ({"schema_version": 1, "rules": []}, errors)
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.validate_workflow(SCHEMAS.WorkflowValidateRequest(definition={"schema_version": 1, "rules": []}, service_ids=["a.example.com"]))

    assert response.status_code == 200
    body = _json(response)
    assert body["valid"] is False and body["errors"] == errors


def test_missing_workflow_is_a_404(monkeypatch):
    db = Mock()
    db.get_workflow_details.return_value = None
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    assert ROUTER.get_workflow("ghost").status_code == 404
    assert ROUTER.get_workflow_definition("ghost").status_code == 404


def test_conflicts_map_to_409(monkeypatch):
    db = Mock()
    db.delete_workflow.return_value = "Workflow is attached to a service"
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    assert ROUTER.delete_workflow("wf-1").status_code == 409
