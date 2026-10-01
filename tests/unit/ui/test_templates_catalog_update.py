"""CAT-C4 — catalogue templates: listing states, the diff preview and `/templates/catalog/update`.

A template has no version, so "the catalogue holds another version" means its content differs.
The listing records a **fingerprint** of each catalogue template at refresh (settings, steps, config
digests), read out of the same digest-pinned archive the install reads. The page compares it with
the installed template to pick a state and render the diff the operator confirms. The update route
downloads and verifies the archive again, rebuilds both fingerprints, and refuses unless they are the
ones the operator reviewed (the ``confirm`` token), so a moved listing or an edit made in between
never goes through unseen.

The route is driven past ``login_required`` / ``cors_required`` the same way
``test_templates_catalog_routes.py`` does it, and both decorators are pinned at the bottom.
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
from flask_babel import Babel
from flask_login import LoginManager

import app.models.plugin_catalog as pc  # type: ignore
from app.models.plugin_catalog import (  # type: ignore
    CATALOG_MAX_AGE,
    build_catalog_view,
    template_diff,
    template_fingerprint,
    template_payload,
    template_state,
    update_token,
)

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "templates.py"
TAG = "v0.7"
ROOT = "bunkerity-bunkerweb-templates-509f350"

META = {
    "id": "wordpress",
    "name": "WordPress",
    "steps": [{"title": "Basics", "subtitle": "Start here", "settings": ["USE_ANTIBOT", "MAX_CLIENT_SIZE"], "configs": ["modsec-crs/wp_fp.conf"]}],
    "settings": {"USE_ANTIBOT": "captcha", "MAX_CLIENT_SIZE": "20M"},
    "configs": ["modsec-crs/wp_fp.conf"],
}
CONFIG_BODY = "SecRuleRemoveById 942100\n"


def _archive(meta=META, config=CONFIG_BODY):
    buf = BytesIO()
    with tar_open(fileobj=buf, mode="w:gz") as tar:
        members = {f"templates/{meta['id']}/template.json": dumps(meta).encode(), f"templates/{meta['id']}/configs/modsec-crs/wp_fp.conf": config.encode()}
        for name, blob in members.items():
            info = TarInfo(f"{ROOT}/{name}")
            info.size = len(blob)
            tar.addfile(info, BytesIO(blob))
    return buf.getvalue()


ARCHIVE = _archive()
DIGEST = sha256(ARCHIVE).hexdigest()
PAYLOAD = template_payload(ARCHIVE, "wordpress")[0]


def _row(settings=None, configs=None, steps=None, *, name="WordPress", method="ui", plugin_id=None):
    """An installed template the way `API_CLIENT.get_templates()` returns it: the DB spelling of a
    config type (`modsec_crs`), config refs in steps, a canonical size value."""
    return {
        "plugin_id": plugin_id,
        "name": name,
        "method": method,
        "settings": {"USE_ANTIBOT": "captcha", "MAX_CLIENT_SIZE": "20m"} if settings is None else settings,
        "configs": {"modsec_crs/wp_fp.conf": CONFIG_BODY} if configs is None else configs,
        "steps": (
            [{"title": "Basics", "subtitle": "Start here", "settings": ["USE_ANTIBOT", "MAX_CLIENT_SIZE"], "configs": ["modsec_crs/wp_fp.conf"]}]
            if steps is None
            else steps
        ),
    }


def _lower_sizes(key, value):
    """What the page's canon does for a `size` setting, reduced to the one rule these tests need."""
    return value.lower() if key == "MAX_CLIENT_SIZE" else value


# ── Fingerprint and diff (pure) ─────────────────────────────────────────────


def test_the_catalogue_payload_and_the_stored_template_fingerprint_alike():
    # The DB stores `modsec-crs` as `modsec_crs` (and the step's reference with it). Measured on the
    # real v0.7 archive: 7 of 13 templates differ only by that spelling, so it must not read as a change.
    listed = template_fingerprint(PAYLOAD)
    assert listed["configs"] == {"modsec_crs/wp_fp.conf": sha256(CONFIG_BODY.encode()).hexdigest()}
    assert template_diff(listed, template_fingerprint(_row()), _lower_sizes) == {}


def test_the_fingerprint_carries_config_digests_not_config_text():
    listed = template_fingerprint(PAYLOAD)
    assert CONFIG_BODY not in dumps(listed)


def test_a_canonical_spelling_is_not_a_change_but_a_real_value_is():
    # jellyfin ships MAX_CLIENT_SIZE "20M"; the DB stores "20m" (measured on the dev stack). With no
    # canon that would badge every installed jellyfin as "update" forever.
    listed, installed = template_fingerprint(PAYLOAD), template_fingerprint(_row())
    assert template_diff(listed, installed) == {"settings_changed": [["MAX_CLIENT_SIZE", "20m", "20M"]]}
    assert template_diff(listed, installed, _lower_sizes) == {}
    changed = template_fingerprint(_row(settings={"USE_ANTIBOT": "no", "MAX_CLIENT_SIZE": "20m"}))
    assert template_diff(listed, changed, _lower_sizes) == {"settings_changed": [["USE_ANTIBOT", "no", "captcha"]]}


def test_the_diff_names_added_removed_and_changed_parts():
    installed = _row(
        settings={"USE_ANTIBOT": "captcha", "USE_GZIP": "yes"},
        configs={"modsec_crs/wp_fp.conf": "old rule\n", "modsec/legacy.conf": "x"},
        steps=[
            {"title": "Old basics", "subtitle": "", "settings": ["USE_ANTIBOT", "USE_GZIP"], "configs": ["modsec_crs/wp_fp.conf", "modsec/legacy.conf"]},
            {"title": "Gone", "subtitle": "", "settings": [], "configs": []},
        ],
        name="WordPress (old)",
    )
    diff = template_diff(template_fingerprint(PAYLOAD), template_fingerprint(installed), _lower_sizes)
    assert diff == {
        "name": ["WordPress (old)", "WordPress"],
        "settings_added": [["MAX_CLIENT_SIZE", "20m"]],
        "settings_removed": [["USE_GZIP", "yes"]],
        "steps_changed": ["Basics"],
        "steps_removed": ["Gone"],
        "configs_changed": ["modsec_crs/wp_fp.conf"],
        "configs_removed": ["modsec/legacy.conf"],
    }


def test_a_new_step_is_named_as_added():
    installed = _row(steps=[])
    assert template_diff(template_fingerprint(PAYLOAD), template_fingerprint(installed), _lower_sizes)["steps_added"] == ["Basics"]


def test_an_oversized_or_malformed_template_has_no_fingerprint():
    assert template_fingerprint({"name": "x", "settings": {"A": "v" * 70000}, "steps": [], "configs": []}) is None
    assert template_fingerprint({"name": "x", "settings": [], "steps": [], "configs": []}) is None
    assert template_fingerprint(None) is None


def test_the_token_changes_with_either_side():
    listed, installed = template_fingerprint(PAYLOAD), template_fingerprint(_row())
    token = update_token(listed, installed)
    assert token == update_token(template_fingerprint(PAYLOAD), template_fingerprint(_row()))
    assert token != update_token(listed, template_fingerprint(_row(settings={"USE_ANTIBOT": "no", "MAX_CLIENT_SIZE": "20m"})))
    assert token != update_token(template_fingerprint(template_payload(_archive(config="other\n"), "wordpress")[0]), installed)


# ── Listing states ──────────────────────────────────────────────────────────


def _item(**over):
    return {"id": "wordpress", "name": "WordPress", "version": "", "supported": [], "fingerprint": template_fingerprint(PAYLOAD)} | over


@pytest.mark.parametrize(
    ("row", "state", "owner"),
    [
        (None, "available", ""),
        (_row(plugin_id="someplugin"), "managed", "someplugin"),
        (_row(method="scheduler"), "managed", "scheduler"),
        (_row(), "installed", ""),
        (_row(settings={"USE_ANTIBOT": "no", "MAX_CLIENT_SIZE": "20m"}), "update", ""),
    ],
)
def test_template_state(row, state, owner):
    result = template_state(_item(), row, _lower_sizes)
    assert result["state"] == state and result["managed_by"] == owner
    if state == "update":
        assert result["diff"] == {"settings_changed": [["USE_ANTIBOT", "no", "captcha"]]}
        assert result["confirm"] == update_token(_item()["fingerprint"], template_fingerprint(row))
    else:
        assert not result["diff"] and not result["confirm"]


def test_a_listing_cached_before_fingerprints_cannot_tell_so_offers_no_update():
    result = template_state(_item(fingerprint=None), _row(), _lower_sizes)
    assert result["state"] == "installed" and result["diff"] is None and not result["confirm"]


def test_a_tampered_cache_fingerprint_reads_as_unknown_not_as_a_crash():
    result = template_state(_item(fingerprint={"settings": "junk"}), _row(), _lower_sizes)
    assert result["state"] == "installed" and result["diff"] is None


def _cached(items, fetched_at=None):
    return {
        "fetched_at": fetched_at or datetime.now().astimezone().isoformat(),
        "catalog": {"plugins": {"tag": "v1.13", "sha256": "a" * 64, "items": []}, "templates": {"tag": TAG, "sha256": DIGEST, "items": items}},
    }


def test_the_templates_view_keeps_installed_items_with_their_state(monkeypatch):
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "yes")
    view = build_catalog_view("templates", _cached([_item(), _item(id="drupal")]), {"wordpress": _row(settings={"USE_ANTIBOT": "no"})}, "1.7.0", _lower_sizes)
    states = {item["id"]: item["state"] for item in view["catalog_items"]}
    assert states == {"wordpress": "update", "drupal": "available"}
    assert all(item["compatible"] for item in view["catalog_items"])


def test_fetch_source_records_a_fingerprint_for_every_template(monkeypatch):
    def _get(url, *, timeout, cap):
        return dumps({"tag_name": TAG}).encode() if "releases/latest" in url else ARCHIVE

    monkeypatch.setattr(pc, "_get_allowlisted", _get)
    section, errors = pc.fetch_source("templates")
    assert errors == [] and section["sha256"] == DIGEST
    assert section["items"][0]["fingerprint"] == template_fingerprint(PAYLOAD)


# ── `/templates/catalog/update` ─────────────────────────────────────────────


@pytest.fixture(scope="module")
def route_module():
    client, config, data = Mock(), Mock(), {}
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = config
    dependencies.DATA = data
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

    module_name = "app.routes._templates_catalog_update_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


STALE_ROW = _row(settings={"USE_ANTIBOT": "no", "MAX_CLIENT_SIZE": "20m"})
CONFIRM = update_token(template_fingerprint(PAYLOAD), template_fingerprint(STALE_ROW))


@pytest.fixture
def ctx(route_module, monkeypatch):
    module, client = route_module
    client.reset_mock(return_value=True, side_effect=True)
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "yes")

    class _Data(dict):
        def load_from_file(self):
            pass

    holder = _Data({"PLUGIN_CATALOG": _cached([_item()])})
    monkeypatch.setattr(module, "DATA", holder)
    client.readonly = False
    client.get_metadata.return_value = {"version": "1.7.0"}
    client.get_templates.return_value = {"low": _row(plugin_id="templates", name="Low"), "wordpress": STALE_ROW}
    imported = []
    client.import_template.side_effect = lambda package, replace=False: imported.append((package, replace)) or {"status": "success", "replaced": True}
    downloads = []
    monkeypatch.setattr(module, "fetch_archive", lambda repo, tag: downloads.append((repo, tag)) or ARCHIVE)
    flashed = []
    monkeypatch.setattr(module, "flash", lambda message, category="success": flashed.append((message, category)))

    app = Flask(__name__)
    app.secret_key = "test"
    Babel(app)  # `translated()` needs it, as in the product app
    manager = LoginManager()
    manager.init_app(app)
    manager.user_loader(lambda user_id: None)
    app.register_blueprint(module.templates)
    admin = SimpleNamespace(admin=True, is_authenticated=True, is_active=True, is_anonymous=False, get_id=lambda: "1", list_permissions=["write"])
    monkeypatch.setattr(module, "current_user", admin)
    return SimpleNamespace(app=app, module=module, client=client, data=holder, imported=imported, downloads=downloads, flashed=flashed)


def _post(ctx, **form):
    payload = {"id": "wordpress", "confirm": CONFIRM} | form
    with ctx.app.test_request_context("/templates/catalog/update", method="POST", data=payload):
        result = ctx.module.templates_catalog_update.__wrapped__.__wrapped__()
    body, status = result if isinstance(result, tuple) else (result, 200)
    return body.get_json(), status


def test_a_confirmed_update_replaces_the_template_through_the_import_api(ctx):
    body, status = _post(ctx)
    assert status == 200 and body["status"] == "success"
    assert ctx.downloads == [("bunkerity/bunkerweb-templates", TAG)]
    [(package, replace)] = ctx.imported
    assert replace is True
    assert package == {"format": "bunkerweb-template/1", **PAYLOAD}
    assert ctx.flashed and ctx.flashed[0][1] == "success" and "wordpress" in ctx.flashed[0][0]


@pytest.mark.parametrize("confirm", ["", "0" * 64, update_token(template_fingerprint(PAYLOAD), template_fingerprint(_row()))])
def test_an_unconfirmed_or_stale_preview_replaces_nothing(ctx, confirm):
    # "" = no preview at all; the last one is the token of a preview made against another installed
    # state -- the template was edited after the operator reviewed the diff.
    body, status = _post(ctx, confirm=confirm)
    assert status == 409 and "changed since" in body["message"]
    assert ctx.imported == []


def test_a_moved_listing_replaces_nothing(ctx, monkeypatch):
    # The listing refreshed to other bytes after the preview: same id, other fingerprint.
    other = _archive(config="another rule\n")
    cache = _cached([_item(fingerprint=template_fingerprint(template_payload(other, "wordpress")[0]))])
    cache["catalog"]["templates"]["sha256"] = sha256(other).hexdigest()
    ctx.data["PLUGIN_CATALOG"] = cache
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: other)
    _, status = _post(ctx)
    assert status == 409 and ctx.imported == []


def test_a_template_that_is_not_installed_is_refused_before_any_download(ctx):
    ctx.client.get_templates.return_value = {"low": _row(plugin_id="templates")}
    body, status = _post(ctx)
    assert status == 409 and "not installed" in body["message"]
    assert ctx.downloads == [] and ctx.imported == []


@pytest.mark.parametrize("row", [_row(plugin_id="someplugin"), _row(method="scheduler"), _row(method="autoconf")])
def test_a_managed_template_is_refused_before_any_download(ctx, row):
    ctx.client.get_templates.return_value = {"wordpress": row}
    body, status = _post(ctx)
    assert status == 409 and "managed by" in body["message"]
    assert ctx.downloads == [] and ctx.imported == []


def test_an_identical_template_is_not_replaced(ctx):
    installed = {"wordpress": _row(settings=dict(META["settings"]))}
    ctx.client.get_templates.return_value = installed
    body, status = _post(ctx, confirm=update_token(template_fingerprint(PAYLOAD), template_fingerprint(installed["wordpress"])))
    assert status == 409 and "already matches" in body["message"]
    assert ctx.imported == []


def test_a_non_admin_is_refused(ctx, monkeypatch):
    monkeypatch.setattr(ctx.module, "current_user", SimpleNamespace(admin=False, is_authenticated=True, list_permissions=["write"]))
    _, status = _post(ctx)
    assert status == 403 and ctx.downloads == [] and ctx.imported == []


def test_the_kill_switch_refuses(ctx, monkeypatch):
    monkeypatch.setenv("USE_PLUGIN_CATALOG", "no")
    _, status = _post(ctx)
    assert status == 403 and ctx.downloads == [] and ctx.imported == []


def test_a_read_only_database_is_refused(ctx):
    ctx.client.readonly = True
    _, status = _post(ctx)
    assert status in (403, 409) and ctx.imported == []


def test_a_stale_listing_is_refused(ctx):
    ctx.data["PLUGIN_CATALOG"] = _cached([_item()], fetched_at=(datetime.now().astimezone() - CATALOG_MAX_AGE - timedelta(minutes=1)).isoformat())
    body, status = _post(ctx)
    assert status == 409 and "out of date" in body["message"] and ctx.downloads == []


def test_a_re_cut_tag_replaces_nothing(ctx, monkeypatch):
    monkeypatch.setattr(ctx.module, "fetch_archive", lambda repo, tag: _archive(meta=META | {"name": "Tampered"}))
    body, status = _post(ctx)
    assert status == 502 and "no longer matches" in body["message"]
    assert ctx.imported == []


def test_an_unknown_id_is_a_404(ctx):
    _, status = _post(ctx, id="not-in-the-catalogue")
    assert status == 404 and ctx.downloads == []


def test_nothing_but_the_id_and_the_confirmation_is_taken_from_the_request(ctx):
    _post(ctx, tag="evil", repo="attacker/x", sha256="0" * 64, url="https://evil.example/x")
    assert ctx.downloads == [("bunkerity/bunkerweb-templates", TAG)]
    assert len(ctx.imported) == 1


def test_an_api_refusal_is_passed_through(ctx):
    from app.api_client import ApiClientError  # type: ignore

    error = ApiClientError("Template name WordPress is already used by template other")
    error.status_code = 409
    ctx.client.import_template.side_effect = error
    body, status = _post(ctx)
    assert status == 409 and "already used" in body["message"]
    assert ctx.flashed == []


def test_the_update_route_is_login_and_cors_protected(ctx):
    view = ctx.module.templates_catalog_update
    assert getattr(getattr(view, "__wrapped__", None), "__wrapped__", None) is not None
    with ctx.app.test_client() as http:
        assert http.post("/templates/catalog/update", data={"id": "wordpress", "confirm": CONFIRM}).status_code in (302, 401, 403)
    assert ctx.imported == []


def test_services_using_a_template_are_listed_by_id(ctx):
    ctx.client.get_services.return_value = [
        {"id": "a.example", "template": "wordpress"},
        {"id": "b.example", "template": "low wordpress"},
        {"id": "c.example", "template": "low"},
        {"id": "default-server", "method": "wizard", "template": "wordpress"},
    ]
    assert ctx.module._template_services({"wordpress": {}, "low": {}}) == {"wordpress": ["a.example", "b.example"], "low": ["b.example", "c.example"]}


def test_the_page_canon_matches_what_the_db_stores(ctx):
    # The size rule behind jellyfin's "20M" -> "20m", and a boolean alias.
    canon = ctx.module._setting_canon(
        [{"key": "MAX_CLIENT_SIZE", "type": "size"}, {"key": "USE_GZIP", "type": "check"}, {"key": "REVERSE_PROXY_URL", "type": "text"}]
    )
    assert canon("MAX_CLIENT_SIZE", "20M") == "20m"
    assert canon("USE_GZIP", "true") == "yes"
    assert canon("REVERSE_PROXY_URL_1", " /api ") == canon("REVERSE_PROXY_URL_1", " /api ")
    assert canon("NOT_A_SETTING", "Keep") == "Keep"


# ── The catalogue grid (templates.html) ─────────────────────────────────────


def _render(**context):
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

    env = Environment(
        loader=ChoiceLoader([DictLoader({"dashboard.html": "{% block content %}{% endblock %}"}), FileSystemLoader(ROUTE_PATH.parents[1] / "templates")]),
        autoescape=True,
    )
    env.globals.update(
        _=lambda key, **kwargs: key + ("|" + ",".join(f"{k}={v}" for k, v in sorted(kwargs.items())) if kwargs else ""),
        plugin_text=lambda plugin_id, key, fallback="": fallback,
        setting_text=lambda setting_id, field, fallback="": fallback,
        csrf_token=lambda: "t",
        url_for=lambda endpoint, **kwargs: f"/{endpoint}",
    )
    base = dict(
        templates={},
        template_usage={},
        template_badges={},
        template_users={},
        is_readonly=False,
        user_readonly=False,
        user_admin=True,
        theme="light",
        script_nonce="n",
        catalog_enabled=True,
        catalog_available=True,
        catalog_stale=False,
        catalog_tag=TAG,
    )
    return env.get_template("templates.html").render(**(base | context))


def _card(html, template_id):
    """One catalogue card's markup: up to the next card, or to the notice under the grid."""
    start = html.index(f'data-catalog-template-id="{template_id}"')
    end = html.find('data-catalog-template-id="', start + 1)
    return html[start : end if end != -1 else html.index('id="templates-catalog-notice"')]


def _view(state, **over):
    return _item() | {"compatible": True, "bw_version": "1.7.0", "state": state, "managed_by": "", "diff": None, "confirm": ""} | over


def test_each_state_offers_its_own_actions():
    diff = {"settings_changed": [["USE_ANTIBOT", "no", "captcha"]], "configs_added": ["modsec_crs/wp_fp.conf"]}
    items = [
        _view("available", id="drupal"),
        _view("installed", id="nextcloud", diff={}),
        _view("update", id="wordpress", diff=diff, confirm="c" * 64),
        _view("managed", id="jellyfin", managed_by="scheduler"),
    ]
    html = _render(catalog_items=items, template_users={"wordpress": ["a.example", "b.example"]})
    drupal, nextcloud, wordpress, jellyfin = (_card(html, i["id"]) for i in items)
    assert "templates-catalog-install" in drupal and "delete-template" not in drupal
    assert "templates.catalog.state_installed" in nextcloud and "delete-template" in nextcloud and "templates-catalog-install" not in nextcloud
    assert 'data-bs-target="#modal-catalog-template-update-wordpress"' in wordpress and "delete-template" in wordpress
    assert "templates.catalog.state_managed|owner=scheduler" in jellyfin
    assert "delete-template" not in jellyfin and "templates-catalog-install" not in jellyfin

    modal = html[html.index('id="modal-catalog-template-update-wordpress"') :]
    modal = modal[: modal.index("</form>")]
    assert 'name="confirm" value="' + "c" * 64 + '"' in modal and 'name="id" value="wordpress"' in modal
    assert "USE_ANTIBOT" in modal and "captcha" in modal and "modsec_crs/wp_fp.conf" in modal
    assert "a.example" in modal and "b.example" in modal
    assert 'id="modal-catalog-template-update-nextcloud"' not in html


def test_an_unknown_preview_offers_no_update_and_says_why():
    html = _render(catalog_items=[_view("installed", diff=None)])
    card = _card(html, "wordpress")
    assert "templates.catalog.update_preview_unknown" in card
    assert "modal-catalog-template-update" not in html


def test_a_writer_sees_states_but_no_actions():
    html = _render(catalog_items=[_view("update", diff={"settings_removed": [["USE_GZIP", "yes"]]}, confirm="c" * 64)], user_admin=False)
    card = _card(html, "wordpress")
    assert "templates.catalog.state_update" in card
    assert "modal-catalog-template-update" not in html and "delete-template" not in card
