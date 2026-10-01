"""`POST/PATCH /templates`: a refused request is a 4xx, never a 500, and a new id follows the
USE_TEMPLATE rule (QA-UI H14).

The router mapped a DB refusal to 400 only when its text matched a hint list, so every refusal
nobody had listed -- "A template must contain at least one step" first -- answered 500, which the
UI then showed as "API returned 500: ...". Only a failed commit is a server error.

Loader: the stubbed-`sys.modules` pattern of `test_plugins_toggle.py` (no live TestClient here).
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        pass

    def _passthrough(self, *_args, **_kwargs):
        return lambda function: function

    get = _passthrough
    post = _passthrough
    patch = _passthrough
    delete = _passthrough


class _Response:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.content = content


def _load_router():
    names = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_templates": ModuleType("bw_templates"),
        "bw_templates.routers": ModuleType("bw_templates.routers"),
        "bw_templates.auth": ModuleType("bw_templates.auth"),
        "bw_templates.auth.guard": ModuleType("bw_templates.auth.guard"),
        "bw_templates.utils": ModuleType("bw_templates.utils"),
    }
    names["fastapi"].APIRouter = _Router
    names["fastapi"].Depends = lambda dependency: dependency
    names["fastapi"].Body = lambda default=..., **_kwargs: default
    names["fastapi.responses"].JSONResponse = _Response
    for package in ("bw_templates", "bw_templates.routers", "bw_templates.auth"):
        names[package].__path__ = []
    names["bw_templates.auth.guard"].guard = object()
    names["bw_templates.utils"].get_db = Mock()
    with patch.dict(sys.modules, names):
        path = ROOT / "src" / "api" / "app" / "routers" / "templates.py"
        spec = importlib.util.spec_from_file_location("bw_templates.routers.templates", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


@pytest.fixture
def db(monkeypatch):
    fake_db = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: fake_db)
    return fake_db


def _create(template_id="web"):
    return ROUTER.TemplateCreateRequest(id=template_id, name="Web", steps=[{"title": "Step 1", "settings": []}])


@pytest.mark.parametrize(
    "message",
    [
        "A template must contain at least one step",
        "Step 1 must have a title",
        "Unknown settings: NOPE",
        "Invalid value for setting USE_ANTIBOT: bad",
        "Template web already exists",
        "The database is read-only, the changes will not be saved",
        "Plugin nope does not exist",
    ],
)
def test_a_refused_creation_is_a_400(db, message):
    db.create_template.return_value = message
    response = ROUTER.create_template(_create())
    assert response.status_code == 400
    assert response.content == {"status": "error", "message": message}


def test_a_failed_commit_is_still_a_500(db):
    db.create_template.return_value = "An error occurred while creating template web.\nboom"
    assert ROUTER.create_template(_create()).status_code == 500


@pytest.mark.parametrize("template_id", ["bad id!", "a b", "slash/id", "-x"])
def test_an_id_outside_the_use_template_rule_is_refused_before_the_database(db, template_id):
    response = ROUTER.create_template(_create(template_id))
    assert response.status_code == 400
    assert response.content["message"] == ROUTER.TEMPLATE_ID_RULE
    assert not db.create_template.called


@pytest.mark.parametrize(
    ("message", "status"),
    [
        ("Template not found", 404),
        ("Template name Web already exists", 400),
        ("A template must contain at least one step", 400),
        ("An error occurred while updating template web.\nboom", 500),
    ],
)
def test_update_maps_refusals_to_4xx(db, message, status):
    db.update_template.return_value = message
    response = ROUTER.update_template("web", ROUTER.TemplateUpdateRequest(name="Web"))
    assert response.status_code == status


def test_the_router_and_the_ui_editor_share_one_id_rule():
    """The UI template editor refuses the id before posting it; its copy of the rule must be the
    DB module's, character for character."""
    editor = (ROOT / "src" / "ui" / "app" / "static" / "js" / "pages" / "template_edit.js").read_text(encoding="utf-8")
    assert f"const TEMPLATE_ID_PATTERN = /{ROUTER.TEMPLATE_ID_RX.pattern}/;" in editor
