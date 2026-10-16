"""Template JSON errors preserve hostile identifiers as text; flashes escape only once."""

from io import BytesIO
from json import dumps

import pytest
import test_templates_catalog_routes as catalog_routes
from flask import session
from flask_babel import Babel
from requests.exceptions import RequestException

from app.api_client import ApiClientError, ApiUnavailableError
from test_templates_catalog_routes import ROUTE_PATH, _cache, _entry, route_module  # noqa: F401 -- shared route fixture

ctx = catalog_routes.ctx

PAYLOAD = "<img src=x onerror=alert(1)>"
ESCAPED = "&lt;img src=x onerror=alert(1)&gt;"
TEMPLATE = {"id": PAYLOAD, "name": PAYLOAD, "settings": {}, "steps": [], "configs": []}


def _call(ctx, view, data=None, args=()):
    with ctx.app.test_request_context("/templates/test", method="POST", data=data or {}):
        result = getattr(ctx.module, view).__wrapped__.__wrapped__(*args)
        response, status = result if isinstance(result, tuple) else (result, 200)
        return response.get_json(), status


def _assert_escaped(message):
    assert ESCAPED in message
    assert PAYLOAD not in message
    assert "&amp;lt;img" not in message


def _assert_raw(message):
    assert PAYLOAD in message
    assert ESCAPED not in message


@pytest.mark.parametrize("translated", [False, True], ids=["fallback", "catalog"])
def test_import_parser_refusal_keeps_text_for_the_plain_text_modal(ctx, translated):
    if translated:
        ctx.app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(ROUTE_PATH.parents[2] / "translations")
        Babel(ctx.app)
    package = {"format": "bunkerweb-template/1", **TEMPLATE}
    body, status = _call(ctx, "templates_import", {"template_file": (BytesIO(dumps(package).encode()), "hostile.json")})
    assert status == 400
    assert "invalid template id" in body["message"]
    assert PAYLOAD in body["message"]
    assert ESCAPED not in body["message"]


@pytest.mark.parametrize("error_type", [ApiClientError, ApiUnavailableError])
def test_import_api_refusal_keeps_text_for_the_plain_text_modal(ctx, error_type):
    ctx.client.import_template.side_effect = error_type(f"Invalid template name: {PAYLOAD}")
    package = {"format": "bunkerweb-template/1", **TEMPLATE, "id": "valid"}
    body, status = _call(ctx, "templates_import", {"template_file": (BytesIO(dumps(package).encode()), "valid.json")})
    assert status in (400, 503)
    assert PAYLOAD in body["message"]
    assert ESCAPED not in body["message"]


@pytest.mark.parametrize("error_type", [ApiClientError, ApiUnavailableError])
@pytest.mark.parametrize(
    "view,method,data,args",
    [
        ("templates_create", "create_template", {}, ()),
        ("templates_update", "update_template", {}, (PAYLOAD,)),
        ("templates_delete", "delete_template", {}, (PAYLOAD,)),
        ("templates_catalog_install", "get_templates", {"id": "wordpress"}, ()),
        ("templates_catalog_install", "create_template", {"id": "wordpress"}, ()),
        ("templates_catalog_update", "get_templates", {"id": "wordpress"}, ()),
        ("templates_catalog_update", "import_template", {"id": "wordpress", "confirm": "confirmed"}, ()),
        ("templates_catalog_install", "get_metadata", {"id": "wordpress"}, ()),
    ],
)
def test_api_refusals_match_the_consumers_html_or_text_contract(ctx, monkeypatch, error_type, view, method, data, args):
    # These values may be echoed by API validation, even when the template id itself is valid.
    getattr(ctx.client, method).side_effect = error_type(f"Invalid template, name, step or setting: {PAYLOAD}")
    ctx.client.get_template.return_value = TEMPLATE
    form = {"template": dumps(TEMPLATE), **data}
    if view == "templates_catalog_update" and method == "import_template":
        ctx.client.get_templates.return_value = {"wordpress": {"method": "ui", "plugin_id": None}}
        monkeypatch.setattr(ctx.module, "template_fingerprint", lambda row: row.get("name", "installed"))
        monkeypatch.setattr(ctx.module, "update_token", lambda *args: "confirmed")
    body, status = _call(ctx, view, form, args)
    assert status in (400, 503)
    if view in ("templates_create", "templates_update"):
        _assert_escaped(body["message"])
    else:
        _assert_raw(body["message"])


@pytest.mark.parametrize("branch", ["unknown", "incomplete", "unsupported", "exists"])
def test_catalogue_text_refusals_preserve_the_requested_id(ctx, monkeypatch, branch):
    ctx.data["PLUGIN_CATALOG"] = _cache(items=[_entry(id=PAYLOAD)])
    if branch == "unknown":
        ctx.data["PLUGIN_CATALOG"] = _cache(items=[])
    elif branch == "incomplete":
        ctx.data["PLUGIN_CATALOG"]["catalog"]["templates"]["tag"] = ""
    elif branch == "unsupported":
        monkeypatch.setattr(ctx.module, "item_compatible", lambda *args: False)
        ctx.data["PLUGIN_CATALOG"]["catalog"]["templates"]["items"][0]["supported"] = [PAYLOAD]
        ctx.client.get_metadata.return_value = {"version": PAYLOAD}
    else:
        ctx.client.get_templates.return_value = {PAYLOAD: {}}
    body, status = _call(ctx, "templates_catalog_install", {"id": PAYLOAD})
    assert status == {"unknown": 404, "incomplete": 409, "unsupported": 422, "exists": 409}[branch]
    _assert_raw(body["message"])


@pytest.mark.parametrize("branch", ["refused_download", "failed_download", "payload"])
def test_catalogue_archive_text_refusals_preserve_user_and_archive_data(ctx, monkeypatch, branch):
    ctx.data["PLUGIN_CATALOG"] = _cache(items=[_entry(id=PAYLOAD)])
    if branch in ("refused_download", "failed_download"):
        error = ValueError if branch == "refused_download" else RequestException

        def fail(*args):
            raise error(PAYLOAD)

        monkeypatch.setattr(ctx.module, "fetch_archive", fail)
    body, status = _call(ctx, "templates_catalog_install", {"id": PAYLOAD})
    assert status == 502
    _assert_raw(body["message"])


@pytest.mark.parametrize("translated", [False, True], ids=["fallback", "catalog"])
@pytest.mark.parametrize("branch", ["not_installed", "managed", "up_to_date", "changed"])
def test_catalogue_update_text_refusals_preserve_ids_and_owners(ctx, monkeypatch, translated, branch):
    if translated:
        ctx.app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(ROUTE_PATH.parents[2] / "translations")
        Babel(ctx.app)
    ctx.data["PLUGIN_CATALOG"] = _cache(items=[_entry(id=PAYLOAD)])
    row = {**TEMPLATE, "method": "ui", "plugin_id": None}
    ctx.client.get_templates.return_value = {} if branch == "not_installed" else {PAYLOAD: row}
    if branch == "managed":
        row["plugin_id"] = PAYLOAD
    monkeypatch.setattr(ctx.module, "_verified_catalog_template", lambda *args: TEMPLATE)
    if branch == "changed":
        row["name"] = "different"
    body, status = _call(ctx, "templates_catalog_update", {"id": PAYLOAD})
    assert status == 409
    _assert_raw(body["message"])
    assert {"not_installed": "not installed", "managed": "managed by", "up_to_date": "already matches", "changed": "changed since"}[branch] in body["message"]


@pytest.mark.parametrize("translated", [False, True], ids=["fallback", "catalog"])
@pytest.mark.parametrize("view,args", [("templates_create", ()), ("templates_update", (PAYLOAD,)), ("templates_delete", (PAYLOAD,))])
def test_editor_success_flashes_are_plain_strings_escaped_once(ctx, translated, view, args):
    if translated:
        ctx.app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(ROUTE_PATH.parents[2] / "translations")
        Babel(ctx.app)
    ctx.client.get_template.return_value = TEMPLATE
    with ctx.app.test_request_context("/templates/test", method="POST", data={"template": dumps(TEMPLATE)}):
        result = getattr(ctx.module, view).__wrapped__.__wrapped__(*args)
        assert result.get_json()["status"] == "success"
        message = session["_flashes"][0][1]
        assert type(message) is str
        _assert_escaped(message)
