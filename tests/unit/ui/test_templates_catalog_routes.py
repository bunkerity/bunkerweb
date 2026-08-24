"""`/templates/catalog/install` — the gates on the template half of the catalogue.

**This file exists because the route had none.** The plugin half was covered by 19 route tests
and this one by nothing, which left five mutations surviving the whole suite: delete the admin
gate, delete the kill switch, make `is_stale` always False, make `verify_digest` always True, and
drop the `declared != template_id` check. Each of those has a test below.

That gap mattered more here than it would anywhere else, for two reasons the spec review already
named:

* **C8a** — a template's ``configs[].data`` reaches the database with *no content validation*.
  ``_prepare_template_entities`` validates every setting hard, then for configs it stringifies,
  encodes, hashes and stores. That text becomes NGINX configuration on the instances. So the
  bytes this route accepts are as consequential as a plugin's, with less downstream checking.
* **C9** — the admin gate exists **only** in this route. The API authenticates the UI's single
  service credential and has no per-user role to check, so there is no second line behind it.

The route answers JSON rather than redirecting to /loading (it matches ``/templates/create``, the
page's existing idiom), so unlike the plugin half these tests can assert on status codes.

Both decorators are bypassed the way ``test_dashboard_comfort.py`` does it — ``login_required``
and ``cors_required`` are applied at import time, so the view's ``__wrapped__.__wrapped__`` is
called inside a request context. Both guards are pinned separately at the bottom.
"""

import importlib.util
import sys
from datetime import datetime, timedelta
from hashlib import sha256
from json import dumps
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from flask_login import LoginManager

from app.models.plugin_catalog import CATALOG_MAX_AGE  # type: ignore

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "templates.py"

GOOD_URL = "https://github.com/bunkerity/bunkerweb-plugins/releases/download/v1.11/template-wordpress-1.0.json"

PAYLOAD = dumps(
    {
        "id": "wordpress",
        "name": "WordPress",
        "steps": [{"title": "Basics", "settings": ["USE_ANTIBOT"]}],
        "settings": {"USE_ANTIBOT": "captcha"},
        "configs": [],
    }
).encode()
DIGEST = sha256(PAYLOAD).hexdigest()


def _entry(**over):
    item = {
        "id": "wordpress",
        "name": "WordPress",
        "description": "",
        "version": "1.0",
        "url": GOOD_URL,
        "sha256": DIGEST,
        "size": len(PAYLOAD),
        "bw_min": "1.7.0",
        "bw_max": None,
        "requires": [],
        "homepage": None,
    }
    item.update(over)
    return item


@pytest.fixture(scope="module")
def route_module():
    client, config, data = Mock(), Mock(), {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = config
    dependencies.DATA = data
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.LOGGER = Mock()
    # routes/templates.py pulls CONFIG_TYPES from routes/configs.py, which needs these to import.
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.CORE_PLUGINS_PATH = Path("/tmp/_core")
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/tmp/_ext")
    dependencies.PRO_PLUGINS_PATH = Path("/tmp/_pro")

    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._templates_catalog_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client, data


@pytest.fixture
def ctx(route_module, monkeypatch):
    module, client, data = route_module
    client.reset_mock(return_value=True, side_effect=True)
    data.clear()

    monkeypatch.setenv("USE_PLUGIN_CATALOG", "yes")

    class _Data(dict):
        def load_from_file(self):
            pass

    holder = _Data({"PLUGIN_CATALOG": {"fetched_at": datetime.now().astimezone().isoformat(), "catalog": {"plugins": [], "templates": [_entry()]}}})
    monkeypatch.setattr(module, "DATA", holder)

    client.readonly = False
    client.get_metadata.return_value = {"version": "1.7.0"}
    client.get_templates.return_value = {"low": {}, "high": {}}

    created = []
    client.create_template.side_effect = lambda tid, **kw: created.append((tid, kw))

    downloads = []

    def _fetch(url, cap):
        downloads.append((url, cap))
        return PAYLOAD

    monkeypatch.setattr(module, "fetch_artifact", _fetch)

    app = Flask(__name__)
    app.secret_key = "test"
    app.config["WTF_CSRF_ENABLED"] = False
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.templates)

    admin = SimpleNamespace(admin=True, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: "1", list_permissions=["write"])
    monkeypatch.setattr(module, "current_user", admin)

    return SimpleNamespace(app=app, module=module, client=client, data=holder, created=created, downloads=downloads, user=admin)


def _post(ctx, **form):
    """Drive the view body past @login_required and @cors_required.

    Both are applied at import time, so patching them afterwards does nothing; the view's
    ``__wrapped__.__wrapped__`` is called directly instead. Returns ``(payload, status)``.
    """
    payload = {"id": "wordpress"}
    payload.update(form)
    view = ctx.module.templates_catalog_install
    with ctx.app.test_request_context("/templates/catalog/install", method="POST", data=payload):
        result = view.__wrapped__.__wrapped__()
    body, status = result if isinstance(result, tuple) else (result, 200)
    return body.get_json(), status


# ── MUTANT 1: the kill switch (templates.py:615) ────────────────────────────


def test_the_kill_switch_refuses_and_touches_nothing(ctx, monkeypatch):
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "no")
    body, status = _post(ctx)
    assert status == 403
    assert "disabled" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


# ── MUTANT 2: the admin gate (templates.py:620) ─────────────────────────────
#
# C9: this gate exists ONLY here. The API sees the UI's service credential, not the end user, so
# nothing behind this route re-checks it.


def test_a_non_admin_is_refused(ctx, monkeypatch):
    monkeypatch.setattr(ctx.module, "current_user", SimpleNamespace(admin=False, is_authenticated=True, list_permissions=["write"]))
    body, status = _post(ctx)
    assert status == 403
    assert "administrators" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


def test_a_write_only_user_is_refused_even_though_templates_create_would_allow_them(ctx, monkeypatch):
    """The asymmetry with /templates/create is deliberate, so it gets its own test.

    Authoring a template by hand needs `write`. Installing one from the internet needs admin,
    because its `configs[].data` becomes NGINX configuration that nothing in the stack inspects
    (C8a). If this ever loosens to match /templates/create, this test is the one that should
    fail first.
    """
    monkeypatch.setattr(ctx.module, "current_user", SimpleNamespace(admin=False, is_authenticated=True, list_permissions=["write"]))
    _, status = _post(ctx)
    assert status == 403


def test_a_read_only_database_is_refused(ctx):
    ctx.client.readonly = True
    _, status = _post(ctx)
    assert status in (403, 409)
    assert ctx.created == []


# ── MUTANT 3: the freshness gate (templates.py:633) ─────────────────────────


def test_a_stale_cache_refuses_the_install(ctx):
    ctx.data["PLUGIN_CATALOG"] = {
        "fetched_at": (datetime.now().astimezone() - CATALOG_MAX_AGE - timedelta(minutes=1)).isoformat(),
        "catalog": {"plugins": [], "templates": [_entry()]},
    }
    body, status = _post(ctx)
    assert status == 409
    assert "out of date" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


def test_a_future_stamp_also_refuses(ctx):
    # ui_data.json is written by other processes; a stamp ahead of now is not evidence of
    # freshness, so it must not read as fresh.
    ctx.data["PLUGIN_CATALOG"] = {
        "fetched_at": (datetime.now().astimezone() + timedelta(days=4000)).isoformat(),
        "catalog": {"plugins": [], "templates": [_entry()]},
    }
    _, status = _post(ctx)
    assert status == 409
    assert ctx.created == []


# ── MUTANT 4: the hash gate (templates.py:660) ──────────────────────────────


def test_a_digest_mismatch_creates_nothing(ctx, monkeypatch):
    monkeypatch.setattr(ctx.module, "fetch_artifact", lambda url, cap: PAYLOAD + b" ")
    body, status = _post(ctx)
    assert status == 502
    assert "Integrity check failed" in body["message"]
    assert ctx.created == []


def test_the_hash_gate_runs_before_the_payload_is_parsed(ctx, monkeypatch):
    """Ordering, not just outcome: unparseable bytes must fail on the DIGEST, not on the JSON.

    If the parse ran first the message would be "not valid JSON", which would mean the route had
    already fed attacker-controlled bytes to a parser before establishing they were the ones the
    manifest named.
    """
    monkeypatch.setattr(ctx.module, "fetch_artifact", lambda url, cap: b"\xff\xfe not json at all")
    body, _ = _post(ctx)
    assert "Integrity check failed" in body["message"]
    assert "JSON" not in body["message"]


# ── MUTANT 5: declared id must equal the manifest id (templates.py:674) ─────


def test_a_payload_declaring_another_id_creates_nothing(ctx, monkeypatch):
    other = dumps({"id": "evil", "name": "Evil", "steps": [], "settings": {}, "configs": []}).encode()
    ctx.data["PLUGIN_CATALOG"] = {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "catalog": {"plugins": [], "templates": [_entry(sha256=sha256(other).hexdigest(), size=len(other))]},
    }
    monkeypatch.setattr(ctx.module, "fetch_artifact", lambda url, cap: other)
    body, status = _post(ctx)
    assert status == 502
    assert "evil" in body["message"] and "wordpress" in body["message"]
    assert ctx.created == []


def test_a_payload_with_no_id_creates_nothing(ctx, monkeypatch):
    other = dumps({"name": "Anonymous", "steps": [], "settings": {}}).encode()
    ctx.data["PLUGIN_CATALOG"] = {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "catalog": {"plugins": [], "templates": [_entry(sha256=sha256(other).hexdigest(), size=len(other))]},
    }
    monkeypatch.setattr(ctx.module, "fetch_artifact", lambda url, cap: other)
    _, status = _post(ctx)
    assert status == 502
    assert ctx.created == []


# ── The remaining gates, so the whole chain is held ─────────────────────────


def test_an_unknown_id_is_a_404(ctx):
    _, status = _post(ctx, id="not-in-the-catalogue")
    assert status == 404
    assert ctx.downloads == []


def test_a_missing_id_is_a_400(ctx):
    _, status = _post(ctx, id="")
    assert status == 400


def test_metadata_failure_refuses_rather_than_assuming_unknown(ctx):
    """Fails closed, and says which failure it was.

    Falling back to `bw_version = "unknown"` also ends in a refusal, because `is_compatible`
    fails closed on an unparseable version — so only the message distinguishes "we could not ask"
    from "we asked and you are too old".
    """
    from app.api_client import ApiUnavailableError  # type: ignore

    ctx.client.get_metadata.side_effect = ApiUnavailableError("api down")
    body, status = _post(ctx)
    assert status == 503
    assert "determine the BunkerWeb version" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


def test_an_incompatible_version_refuses(ctx):
    ctx.client.get_metadata.return_value = {"version": "1.6.11"}
    body, status = _post(ctx)
    assert status == 422
    assert "1.6.11" in body["message"]
    assert ctx.downloads == []


def test_an_already_installed_template_is_a_409(ctx):
    ctx.client.get_templates.return_value = {"wordpress": {}}
    _, status = _post(ctx)
    assert status == 409
    assert ctx.downloads == []


def test_a_refused_download_creates_nothing(ctx, monkeypatch):
    def _boom(url, cap):
        raise ValueError("URL is not allowlisted")

    monkeypatch.setattr(ctx.module, "fetch_artifact", _boom)
    body, status = _post(ctx)
    assert status == 502
    assert "Refused to download" in body["message"]
    assert ctx.created == []


def test_a_payload_that_is_not_a_json_object_creates_nothing(ctx, monkeypatch):
    other = dumps(["not", "an", "object"]).encode()
    ctx.data["PLUGIN_CATALOG"] = {
        "fetched_at": datetime.now().astimezone().isoformat(),
        "catalog": {"plugins": [], "templates": [_entry(sha256=sha256(other).hexdigest(), size=len(other))]},
    }
    monkeypatch.setattr(ctx.module, "fetch_artifact", lambda url, cap: other)
    _, status = _post(ctx)
    assert status == 502
    assert ctx.created == []


def test_a_create_template_rejection_is_surfaced_not_swallowed(ctx):
    """The DB layer is the template half's second compatibility gate.

    `create_template` validates every setting id against the live Settings table, so a template
    naming a setting this BunkerWeb does not have is refused with `Unknown settings: ...`
    whatever `bw_min` claimed. That refusal has to reach the operator.
    """
    from app.api_client import ApiClientError  # type: ignore

    error = ApiClientError("Unknown settings: USE_NOT_A_THING")
    error.status_code = 400
    ctx.client.create_template.side_effect = error
    body, status = _post(ctx)
    assert status == 400
    assert "Unknown settings" in body["message"]


# ── The happy path, so every refusal above means something ──────────────────


def test_a_valid_entry_installs_through_the_existing_create_template(ctx):
    body, status = _post(ctx)
    assert status == 200 and body["status"] == "success"
    assert len(ctx.created) == 1
    template_id, kwargs = ctx.created[0]
    assert template_id == "wordpress"
    assert kwargs["name"] == "WordPress"
    assert kwargs["steps"] == [{"title": "Basics", "settings": ["USE_ANTIBOT"]}]
    assert kwargs["settings"] == {"USE_ANTIBOT": "captcha"}
    assert kwargs["configs"] == []


def test_the_download_is_capped_by_the_declared_size(ctx):
    # `size` used to be validated in the manifest and then never used; the cap passed was always
    # the type ceiling.
    from app.models.plugin_catalog import ARTIFACT_MAX_TEMPLATE  # type: ignore

    _post(ctx)
    (_url, cap) = ctx.downloads[0]
    assert cap == len(PAYLOAD)
    assert cap < ARTIFACT_MAX_TEMPLATE


def test_nothing_but_the_id_is_taken_from_the_request(ctx):
    """A client-supplied url or sha256 must be ignored in favour of the cached entry.

    Honouring either would hand the browser exactly the power the pinned manifest exists to
    remove.
    """
    _post(ctx, url="https://evil.example/x.json", sha256="0" * 64)
    (url, _cap) = ctx.downloads[0]
    assert url == GOOD_URL
    assert len(ctx.created) == 1


# ── The two decorators, since every test above drives the body past them ────


def test_the_route_is_login_and_cors_protected(ctx):
    view = ctx.module.templates_catalog_install
    assert getattr(view, "__wrapped__", None) is not None
    assert getattr(view.__wrapped__, "__wrapped__", None) is not None
    with ctx.app.test_client() as http:
        # No Sec-Fetch-Mode / X-Requested-With, and no session: it must not reach the body.
        assert http.post("/templates/catalog/install", data={"id": "wordpress"}).status_code in (302, 401, 403)
    assert ctx.created == []
