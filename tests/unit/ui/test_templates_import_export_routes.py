"""`GET /templates/<id>/export` and `POST /templates/import` (CAT-C2).

The import route is the UI half of design §2.5 for templates: an uploaded file is capped before it
is parsed, parsed by the one shared parser (`template_package`), never trusted for its path
names, and admin-only -- a template's config blobs become NGINX configuration that nothing
downstream inspects, exactly like a catalogue install. Replacing needs an explicit `replace=yes`;
the API then refuses anything the UI does not own.

Harness: the one of `test_templates_catalog_routes.py` -- the route module loaded with a stubbed
`app.dependencies`, the view body driven past `@login_required`/`@cors_required` through
`__wrapped__`, and both decorators pinned separately at the bottom.
"""

import importlib.util
import sys
from io import BytesIO
from json import dumps, loads
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest
from flask import Flask
from flask_babel import Babel
from flask_login import LoginManager

from app.api_client import ApiClientError  # type: ignore
from template_package import PACKAGE_FORMAT, PACKAGE_MAX  # type: ignore

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "templates.py"

PACKAGE = {
    "format": PACKAGE_FORMAT,
    "id": "web",
    "name": "Web template",
    "settings": {"USE_ANTIBOT": "captcha"},
    "steps": [{"title": "Basics", "subtitle": "", "settings": ["USE_ANTIBOT"], "configs": ["modsec/fp.conf"]}],
    "configs": [{"type": "modsec", "name": "fp", "data": "SecRuleRemoveById 942100\n"}],
}
EXPECTED = {key: PACKAGE[key] for key in ("format", "id", "name", "settings", "steps", "configs")}


def _tar(members):
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        for name, blob in members.items():
            info = TarInfo(name)
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    return buf.getvalue()


def _folder(meta=None, root="web"):
    meta = meta or {
        "id": "web",
        "name": "Web template",
        "settings": {"USE_ANTIBOT": "captcha"},
        "steps": [{"title": "Basics", "subtitle": "", "settings": ["USE_ANTIBOT"], "configs": ["modsec/fp.conf"]}],
        "configs": ["modsec/fp.conf"],
    }
    return {f"{root}/template.json": dumps(meta).encode(), f"{root}/configs/modsec/fp.conf": b"SecRuleRemoveById 942100\n"}


@pytest.fixture(scope="module")
def route_module():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = Mock()
    dependencies.DATA = {}
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.CORE_PLUGINS_PATH = Path("/tmp/_core")
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/tmp/_ext")
    dependencies.PRO_PLUGINS_PATH = Path("/tmp/_pro")

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._templates_io_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def ctx(route_module, monkeypatch):
    module, client = route_module
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    imported = []
    client.import_template.side_effect = lambda package, replace=False: imported.append((package, replace)) or {"status": "success"}

    app = Flask(__name__)
    app.secret_key = "test"
    app.config["WTF_CSRF_ENABLED"] = False
    Babel(app)
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.templates)

    admin = SimpleNamespace(admin=True, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: "1", list_permissions=["write"])
    monkeypatch.setattr(module, "current_user", admin)
    flashes = []
    monkeypatch.setattr(module, "flash", lambda message, category="success", *a, **k: flashes.append((message, category)))
    return SimpleNamespace(app=app, module=module, client=client, imported=imported, flashes=flashes)


def _import(ctx, blob=None, *, filename="web.json", **form):
    data = dict(form)
    if blob is not None:
        data["template_file"] = (BytesIO(blob), filename)
    view = ctx.module.templates_import
    with ctx.app.test_request_context("/templates/import", method="POST", data=data, content_type="multipart/form-data"):
        result = view.__wrapped__.__wrapped__()
    body, status = result if isinstance(result, tuple) else (result, 200)
    return body.get_json(), status


# ── import: what is accepted ────────────────────────────────────────────────────


def test_a_package_file_is_sent_to_the_api_as_the_package(ctx):
    body, status = _import(ctx, dumps(PACKAGE | {"locales": {"fr": {}}}).encode())
    assert status == 200 and body["status"] == "success"
    assert ctx.imported == [(EXPECTED, False)]
    assert ctx.flashes and "web" in ctx.flashes[0][0]


@pytest.mark.parametrize("pack", ["tar", "zip"])
def test_a_folder_archive_becomes_the_same_package(ctx, pack):
    members = _folder()
    if pack == "tar":
        blob = _tar(members)
    else:
        buf = BytesIO()
        with ZipFile(buf, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        blob = buf.getvalue()
    _, status = _import(ctx, blob, filename=f"web.{pack}")
    assert status == 200
    assert ctx.imported == [(EXPECTED, False)]


def test_replace_is_only_asked_for_explicitly(ctx):
    _import(ctx, dumps(PACKAGE).encode(), replace="yes")
    _import(ctx, dumps(PACKAGE).encode(), replace="on")
    assert [replace for _, replace in ctx.imported] == [True, False]


# ── import: what is refused, readably, before the API ───────────────────────────


@pytest.mark.parametrize(
    ("blob", "fragment", "status"),
    [
        (dumps(PACKAGE | {"id": "../etc"}).encode(), "invalid template id", 400),
        (dumps(PACKAGE | {"format": "other/1"}).encode(), "unsupported package format", 400),
        (b"{not json", "not valid UTF-8 JSON", 400),
        (b"plain text, not an archive", "neither a JSON package nor a .zip / .tar archive", 400),
        (_tar({"../evil/template.json": b"{}"}), "invalid template id '..'", 400),
        (_tar(_folder(root="web") | _folder(root="other")), "exactly one template folder", 400),
        (b" " * (PACKAGE_MAX + 1), "1 MiB", 413),
    ],
    ids=["bad-id", "bad-format", "bad-json", "not-an-archive", "traversal", "two-folders", "oversized"],
)
def test_a_bad_file_is_refused_with_a_readable_message(ctx, blob, fragment, status):
    body, got = _import(ctx, blob)
    assert got == status
    assert body["status"] == "error"
    assert body["message"].startswith("The template was not imported")
    assert fragment in body["message"]
    assert ctx.imported == []


def test_no_file_is_a_400(ctx):
    body, status = _import(ctx)
    assert status == 400 and ctx.imported == []
    assert body["message"]


def test_the_api_refusal_is_passed_through_with_its_status(ctx):
    ctx.client.import_template.side_effect = ApiClientError("Template web already exists", status_code=409)
    body, status = _import(ctx, dumps(PACKAGE).encode())
    assert status == 409
    assert body["message"] == "Template web already exists"
    assert ctx.flashes == []


# ── import: who may ─────────────────────────────────────────────────────────────


def test_a_non_admin_writer_is_refused(ctx, monkeypatch):
    """Same bar as a catalogue install, not /templates/create's `write`: the config blobs become
    NGINX configuration, and the API sees only the UI's credential, never the user."""
    monkeypatch.setattr(ctx.module, "current_user", SimpleNamespace(admin=False, is_authenticated=True, list_permissions=["write"]))
    _, status = _import(ctx, dumps(PACKAGE).encode())
    assert status == 403 and ctx.imported == []


def test_a_read_only_database_is_refused(ctx):
    ctx.client.readonly = True
    _, status = _import(ctx, dumps(PACKAGE).encode())
    assert status == 409 and ctx.imported == []


# ── export ──────────────────────────────────────────────────────────────────────


def test_export_serves_the_api_package_as_an_attachment(ctx):
    ctx.client.export_template.return_value = PACKAGE
    view = ctx.module.templates_export
    with ctx.app.test_request_context("/templates/web/export"):
        response = view.__wrapped__("web")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"] == 'attachment; filename="web.bwtemplate.json"'
    assert response.mimetype == "application/json"
    assert loads(response.get_data()) == PACKAGE
    ctx.client.export_template.assert_called_once_with("web")


def test_an_export_failure_flashes_and_goes_back_to_the_list(ctx):
    ctx.client.export_template.side_effect = ApiClientError("Template not found", status_code=404)
    view = ctx.module.templates_export
    with ctx.app.test_request_context("/templates/nope/export"):
        response = view.__wrapped__("nope")
    assert response.status_code == 302 and response.location.endswith("/templates")
    assert ctx.flashes and ctx.flashes[0][1] == "error"


# ── the decorators ──────────────────────────────────────────────────────────────


def test_import_is_login_and_cors_protected_and_export_login_protected(ctx):
    assert getattr(ctx.module.templates_import.__wrapped__, "__wrapped__", None) is not None
    assert getattr(ctx.module.templates_export, "__wrapped__", None) is not None
    with ctx.app.test_client() as http:
        assert http.post("/templates/import", data={"template_file": (BytesIO(dumps(PACKAGE).encode()), "web.json")}).status_code in (302, 401, 403)
        assert http.get("/templates/web/export").status_code in (302, 401, 403)
    assert ctx.imported == []


# ── the list area (templates.html) ──────────────────────────────────────────────


def _render_list(**context):
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

    templates_dir = ROUTE_PATH.parents[1] / "templates"
    env = Environment(
        loader=ChoiceLoader([DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}), FileSystemLoader(templates_dir)]),
        autoescape=True,
    )
    env.globals.update(
        _=lambda key, **_kwargs: key,
        plugin_text=lambda plugin_id, key, fallback="": fallback,
        setting_text=lambda setting_id, field, fallback="": fallback,
        csrf_token=lambda: "t",
        url_for=lambda endpoint, **kwargs: f"/{endpoint}/{kwargs.get('template_id', '')}",
    )
    base = dict(template_usage={}, template_badges={}, is_readonly=False, user_readonly=False, theme="light", script_nonce="n", style_nonce="n")
    return env.get_template("templates.html").render(**(base | context))


def test_every_card_exports_and_only_an_admin_gets_the_import_modal():
    templates = {
        "mine": {"method": "ui", "plugin_id": None, "name": "Mine", "settings": {}, "configs": {}, "steps": []},
        "owned": {"method": "ui", "plugin_id": "someplugin", "name": "Owned", "settings": {}, "configs": {}, "steps": []},
    }
    admin = _render_list(templates=templates, user_admin=True)
    assert admin.count('href="/templates.templates_export/') == 2
    assert 'id="modal-import-template"' in admin and 'id="templates-import-btn"' in admin
    # A UI-uploaded plugin's template has method "ui" but the API refuses to delete it: the button
    # is disabled and names the plugin, not the method.
    owned = admin[admin.index('data-template-id="owned"', admin.index('id="templates-grid"')) :]
    assert "delete-template disabled" in owned[: owned.index("</button>")]
    mine = admin[admin.index('data-template-id="mine"', admin.index('id="templates-grid"')) :]
    assert "delete-template disabled" not in mine[: mine.index("</button>")]

    writer = _render_list(templates=templates, user_admin=False)
    assert 'id="modal-import-template"' not in writer and 'id="templates-import-btn"' not in writer
    assert writer.count('href="/templates.templates_export/') == 2
