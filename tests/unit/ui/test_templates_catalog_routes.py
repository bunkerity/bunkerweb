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
from io import BytesIO
from json import dumps
from pathlib import Path
from tarfile import TarInfo, open as tar_open
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from flask import Flask
from flask_login import LoginManager

from app.models.plugin_catalog import CATALOG_MAX_AGE  # type: ignore

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "templates.py"

TAG = "0.6"
ROOT = "bunkerity-bunkerweb-templates-509f350"

META = {
    "id": "wordpress",
    "name": "WordPress",
    "steps": [{"title": "Basics", "settings": ["USE_ANTIBOT"], "configs": ["modsec/wordpress_fp.conf"]}],
    "settings": {"USE_ANTIBOT": "captcha"},
    "configs": ["modsec/wordpress_fp.conf"],
}
CONFIG_BODY = b"SecRuleRemoveById 942100\n"


def _archive(meta=META, config=CONFIG_BODY, folder="wordpress", root=ROOT):
    """A release source archive shaped the way GitHub produces one.

    Upstream splits a template across `template.json` and sibling config FILES, and the
    `configs` value is a list of relative PATHS -- which is exactly why `template_payload`
    exists and why this fixture cannot be a single JSON blob any more.
    """
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        members = {f"templates/{folder}/template.json": dumps(meta).encode()}
        if config is not None:
            members[f"templates/{folder}/configs/modsec/wordpress_fp.conf"] = config
        for name, blob in members.items():
            info = TarInfo(f"{root}/{name}")
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    return buf.getvalue()


ARCHIVE = _archive()
DIGEST = sha256(ARCHIVE).hexdigest()


def _entry(**over):
    item = {"id": "wordpress", "name": "WordPress", "description": "", "version": "", "supported": [], "homepage": None}
    item.update(over)
    return item


def _cache(items=None, tag=TAG, sha=DIGEST, fetched_at=None):
    return {
        "fetched_at": fetched_at or datetime.now().astimezone().isoformat(),
        "catalog": {
            "plugins": {"tag": "v1.11", "sha256": "a" * 64, "items": []},
            "templates": {"tag": tag, "sha256": sha, "items": [_entry()] if items is None else items},
        },
    }


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

    holder = _Data({"PLUGIN_CATALOG": _cache()})
    monkeypatch.setattr(module, "DATA", holder)

    client.readonly = False
    client.get_metadata.return_value = {"version": "1.7.0"}
    client.get_templates.return_value = {"low": {}, "high": {}}

    created = []
    client.create_template.side_effect = lambda tid, **kw: created.append((tid, kw))

    downloads = []

    def _fetch(repo, tag):
        downloads.append((repo, tag))
        return ARCHIVE

    monkeypatch.setattr(module, "fetch_archive", _fetch)

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
    ctx.data["PLUGIN_CATALOG"] = _cache(fetched_at=(datetime.now().astimezone() - CATALOG_MAX_AGE - timedelta(minutes=1)).isoformat())
    body, status = _post(ctx)
    assert status == 409
    assert "out of date" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


def test_a_future_stamp_also_refuses(ctx):
    # ui_data.json is written by other processes; a stamp ahead of now is not evidence of
    # freshness, so it must not read as fresh.
    ctx.data["PLUGIN_CATALOG"] = _cache(fetched_at=(datetime.now().astimezone() + timedelta(days=4000)).isoformat())
    _, status = _post(ctx)
    assert status == 409
    assert ctx.created == []


# ── MUTANT 4: the hash gate (templates.py:660) ──────────────────────────────


def test_a_re_cut_tag_creates_nothing(ctx, monkeypatch):
    # A git tag can be force-moved, and codeload then serves different bytes for the same URL.
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: _archive(meta=META | {"name": "Tampered"}))
    body, status = _post(ctx)
    assert status == 502
    assert "no longer matches" in body["message"]
    assert ctx.created == []


def test_the_digest_gate_runs_before_the_archive_is_opened(ctx, monkeypatch):
    """Ordering, not just outcome: unopenable bytes must fail on the DIGEST, not on the tar.

    If the archive were opened first the message would be about the archive, which would mean the
    route had already fed unverified bytes to a parser.
    """
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: b"\xff\xfe not a tar at all")
    body, _ = _post(ctx)
    assert "no longer matches" in body["message"]
    # NOT "Refused to install ...: the download is not a readable source archive", which is what
    # `template_payload` would have said had it been reached first.
    assert "Refused to install" not in body["message"]


def test_a_cache_with_no_pinned_tag_or_digest_refuses(ctx):
    for cache in (_cache(tag=""), _cache(sha="")):
        ctx.data["PLUGIN_CATALOG"] = cache
        body, status = _post(ctx)
        assert status == 409 and "incomplete" in body["message"]
    assert ctx.downloads == [] and ctx.created == []


def test_the_re_fetch_is_pinned_to_the_listed_tag_not_to_latest(ctx):
    _post(ctx)
    assert ctx.downloads == [("bunkerity/bunkerweb-templates", TAG)]


# ── MUTANT 5: declared id must equal the manifest id (templates.py:674) ─────


def _serve(ctx, monkeypatch, archive):
    """Point the route at `archive` and record it as the listed bytes, so only the id gate can fire."""
    ctx.data["PLUGIN_CATALOG"] = _cache(sha=sha256(archive).hexdigest())
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: archive)


def test_a_payload_declaring_another_id_creates_nothing(ctx, monkeypatch):
    _serve(ctx, monkeypatch, _archive(meta=META | {"id": "evil"}))
    body, status = _post(ctx)
    assert status == 502
    assert "evil" in body["message"] and "wordpress" in body["message"]
    assert ctx.created == []


def test_a_payload_with_no_id_creates_nothing(ctx, monkeypatch):
    _serve(ctx, monkeypatch, _archive(meta={"name": "Anonymous", "steps": [], "settings": {}}))
    _, status = _post(ctx)
    assert status == 502
    assert ctx.created == []


def test_a_folder_named_something_else_creates_nothing(ctx, monkeypatch):
    _serve(ctx, monkeypatch, _archive(folder="drupal"))
    _, status = _post(ctx)
    assert status == 502
    assert ctx.created == []


def test_a_config_reference_whose_file_is_absent_creates_nothing(ctx, monkeypatch):
    # The reference is in template.json but the blob is not in the archive: refuse rather than
    # create a template whose config silently becomes an empty string on the instances.
    _serve(ctx, monkeypatch, _archive(config=None))
    body, status = _post(ctx)
    assert status == 502 and "missing from the archive" in body["message"]
    assert ctx.created == []


@pytest.mark.parametrize("reference", ["../../../etc/passwd", "/etc/passwd.conf", "modsec/../../x.conf", "x.conf", "modsec/x"])
def test_a_hostile_config_reference_creates_nothing(ctx, monkeypatch, reference):
    meta = META | {"configs": [reference], "steps": [{"title": "Basics", "settings": ["USE_ANTIBOT"], "configs": [reference]}]}
    _serve(ctx, monkeypatch, _archive(meta=meta))
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


def test_the_version_gate_passes_everything_on_this_half_and_that_is_the_ruling(ctx):
    """PO ruling 2026-08-24, and it is a deliberate difference from the plugin half.

    The templates repository publishes no version field and no compatibility file, so a bound
    checked here would be one this route invented. `create_template` validating every setting id
    against the live Settings table is the semantic gate instead — see the test below — and it
    checks against THIS build rather than against a declared range.

    Note what this does NOT say: that the gate is absent. The route calls `item_compatible` and
    the call currently returns True. The distinction is the whole point of the test below.
    """
    _, status = _post(ctx)
    assert status == 200
    assert len(ctx.created) == 1


def test_flipping_the_flag_makes_the_TEMPLATE_ROUTE_refuse(ctx, monkeypatch):
    """The promise `item_compatible`'s docstring makes, tested where it can actually break.

    An earlier revision documented "flip `version_gate` and nothing else changes" while this route
    never called the gate at all. Flipping it hid the button — `templates.html` renders on
    `item.compatible` — and left this endpoint installing anyway. It is `@cors_required` JSON, not
    a form post, so "the button is gone" protects nobody who can issue a POST.

    `test_the_two_halves_are_switched_by_one_flag` cannot catch that: it compares the flag's
    *value* and stays green through exactly this drift. This asserts the SERVER refuses.
    """
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setitem(pc.SOURCES["templates"], "version_gate", True)
    body, status = _post(ctx)
    assert status == 422
    assert "declares support for no BunkerWeb version" in body["message"]
    assert ctx.created == [] and ctx.downloads == []


def test_the_flag_flip_refuses_even_when_the_button_would_have_rendered(ctx, monkeypatch):
    """Belt and braces on the same drift, from the other end.

    With the flag on and an item that DOES declare a matching version, the route must install —
    otherwise the previous test would also pass against a route that simply refuses everything.
    """
    import app.models.plugin_catalog as pc  # type: ignore

    monkeypatch.setitem(pc.SOURCES["templates"], "version_gate", True)
    ctx.data["PLUGIN_CATALOG"] = _cache(items=[_entry(supported=["1.7.0"])])
    _, status = _post(ctx)
    assert status == 200
    assert len(ctx.created) == 1


def test_the_version_source_fails_closed_on_this_half_too(ctx):
    """An unreachable API is not permission to skip the gate, on either half.

    The API is already required by `get_templates()` below, so this costs no new failure mode —
    what it buys is that the flag really is the only thing to change.
    """
    from app.api_client import ApiUnavailableError  # type: ignore

    ctx.client.get_metadata.side_effect = ApiUnavailableError("api down")
    body, status = _post(ctx)
    assert status == 503
    assert "determine the BunkerWeb version" in body["message"]
    assert ctx.created == [] and ctx.downloads == []


def test_an_already_installed_template_is_a_409(ctx):
    ctx.client.get_templates.return_value = {"wordpress": {}}
    _, status = _post(ctx)
    assert status == 409
    assert ctx.downloads == []


def test_a_refused_download_creates_nothing(ctx, monkeypatch):
    def _boom(repo, tag):
        raise ValueError("URL is not allowlisted")

    monkeypatch.setattr(ctx.module, "fetch_archive", _boom)
    body, status = _post(ctx)
    assert status == 502
    assert "Refused to download" in body["message"]
    assert ctx.created == []


def test_a_template_json_that_is_not_an_object_creates_nothing(ctx, monkeypatch):
    _serve(ctx, monkeypatch, _archive(meta=["not", "an", "object"]))
    _, status = _post(ctx)
    assert status == 502
    assert ctx.created == []


def test_a_create_template_rejection_is_surfaced_not_swallowed(ctx):
    """The DB layer is the template half's second compatibility gate.

    After the re-scope it is the ONLY compatibility gate this half has, by PO ruling: it
    validates every setting id against the live Settings table, so a template naming a setting
    this BunkerWeb does not have is refused with `Unknown settings: ...`. That refusal has to
    reach the operator.
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
    assert kwargs["steps"] == META["steps"]
    assert kwargs["settings"] == {"USE_ANTIBOT": "captcha"}
    # The path reference upstream ships has been materialised into the object the DB layer needs.
    assert kwargs["configs"] == [{"type": "modsec", "name": "wordpress_fp", "data": CONFIG_BODY.decode()}]


def test_nothing_but_the_id_is_taken_from_the_request(ctx):
    """A client-supplied repo, tag or digest must be ignored in favour of the cached entry.

    Honouring any of them would hand the browser exactly the power a pinned source exists to
    remove.
    """
    _post(ctx, tag="evil", repo="attacker/x", sha256="0" * 64, url="https://evil.example/x")
    assert ctx.downloads == [("bunkerity/bunkerweb-templates", TAG)]
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
