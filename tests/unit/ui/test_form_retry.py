"""A refused modal form comes back open, with its input (QA-UI M22, M28).

/instances, /groups and /certificates post their modal forms natively and answer a refusal with a
flash and a redirect: the page came back with the modal closed and everything typed gone. The
route now keeps the posted fields (`app/form_retry.py`), the page's GET hands them to the template
as `form_retry`, and `static/js/components/form-retry.js` refills the form and reopens its modal.

Also M28's other half: a bogus PEM is refused in words before the upload, instead of passing the
`cryptography` exception text ("Unable to load PEM file. See https://cryptography.io/...") through.
"""

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, session

from app.form_retry import SESSION_KEY, keep_form, take_form_retry

ROUTES = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes"
TEMPLATES = ROUTES.parent / "templates"


def _app():
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    return app


def _load(relative, **dependencies):
    module_dependencies = ModuleType("app.dependencies")
    defaults = {"API_CLIENT": Mock(readonly=False), "BW_CONFIG": Mock(), "BW_INSTANCES_UTILS": Mock(), "CONFIG_TASKS_EXECUTOR": Mock(), "DATA": {}}
    for key, value in (defaults | dependencies).items():
        setattr(module_dependencies, key, value)
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = f"app.routes._form_retry_{relative.removesuffix('.py')}_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTES / relative)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": module_dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
    return module


def test_keep_then_take_hands_the_form_back_once():
    app = _app()
    form = {"csrf_token": "secret", "name": "web", "service_ids": ["a", "b"]}
    with app.test_request_context("/x", method="POST", data=form):
        keep_form("some-form", "Refused.")
        assert take_form_retry() == {"form": "some-form", "error": "Refused.", "fields": {"name": "web", "service_ids": ["a", "b"]}}
        assert take_form_retry() == {}, "a second render must open the page clean"


# --------------------------------------------------------------------------------------
# /certificates
# --------------------------------------------------------------------------------------


@pytest.fixture
def certificates():
    module = _load("certificates.py", API_CLIENT=Mock(readonly=False))
    module.flash = Mock()
    module.is_readonly_request = lambda api_readonly: api_readonly
    module.translated = lambda key, **variables: None  # a catalog miss: the English fallback
    app = _app()
    app.register_blueprint(module.certificates)
    return module, app


def test_a_bogus_pem_is_refused_in_words_and_the_upload_form_is_kept(certificates):
    module, app = certificates
    data = {
        "name": "custom",
        "description": "Imported",
        "certificate": (BytesIO(b"-----BEGIN CERTIFICATE-----\nnot base64\n"), "cert.pem"),
        "private_key": (BytesIO(b"nope"), "key.pem"),
    }
    with app.test_request_context("/certificates/upload", method="POST", data=data, content_type="multipart/form-data"):
        module.certificates_upload.__wrapped__()
        kept = session.get(SESSION_KEY)

    assert not module.API_CLIENT.upload_certificate.called, "a pair `cryptography` cannot load was still uploaded"
    assert kept["form"] == "certificate-upload"
    assert kept["fields"] == {"name": "custom", "description": "Imported"}
    assert "cryptography" not in kept["error"] and "PEM" in kept["error"]
    module.flash.assert_called_once_with(kept["error"], "error")


def test_an_api_refusal_keeps_the_self_signed_form(certificates):
    module, app = certificates
    module.API_CLIENT.create_certificate.side_effect = module.ApiClientError("Invalid common name", status_code=400)
    data = {"source": "selfsigned", "name": "self", "common_name": "bad name!", "valid_days": "30", "key_type": "ec"}
    with app.test_request_context("/certificates/create", method="POST", data=data):
        module.certificates_create.__wrapped__()
        kept = session.get(SESSION_KEY)

    assert kept["form"] == "certificate-selfsigned"
    assert kept["fields"]["common_name"] == "bad name!" and kept["fields"]["valid_days"] == "30"


def test_the_certificates_template_tags_every_modal_form_the_routes_name():
    page = (TEMPLATES / "certificates.html").read_text(encoding="utf-8")
    for form_id in ("certificate-selfsigned", "certificate-letsencrypt", "certificate-upload", "certificate-edit", "certificate-attach"):
        assert f'data-form-retry="{form_id}"' in page, form_id
    assert 'id="form-retry"' in page and "js/components/form-retry.js" in page


# --------------------------------------------------------------------------------------
# /groups
# --------------------------------------------------------------------------------------


def test_a_refused_group_save_keeps_the_editor_input():
    module = _load("resource_groups.py", API_CLIENT=Mock(readonly=False))
    module.flash = Mock()
    module.is_readonly_request = lambda api_readonly: api_readonly
    module.API_CLIENT.create_resource_group.side_effect = module.ApiClientError("Invalid ip value: 'not-an-ip'", status_code=400)
    app = _app()
    app.register_blueprint(module.resource_groups)
    entries = '[{"kind": "ip", "value": "not-an-ip", "comment": ""}]'
    with app.test_request_context("/groups/save", method="POST", data={"alias": "office", "description": "HQ", "entries": entries, "group_id": ""}):
        module.resource_groups_save.__wrapped__()
        kept = session.get(SESSION_KEY)

    assert kept["form"] == "resource-group"
    assert kept["fields"] == {"alias": "office", "description": "HQ", "entries": entries, "group_id": ""}
    page = (TEMPLATES / "groups.html").read_text(encoding="utf-8")
    assert 'data-form-retry="resource-group"' in page and 'data-form-retry="resource-group-clone"' in page
    assert "bw:form-retry" in (ROUTES.parent / "static" / "js" / "pages" / "groups.js").read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# /instances
# --------------------------------------------------------------------------------------


class _Data(dict):
    load_from_file = Mock()


def test_a_refused_instance_keeps_the_create_modal_input(monkeypatch):
    module = _load("instances.py", API_CLIENT=Mock(readonly=False), BW_CONFIG=Mock(), BW_INSTANCES_UTILS=Mock(), CONFIG_TASKS_EXECUTOR=Mock(), DATA=_Data())
    monkeypatch.setattr(module, "is_readonly_request", lambda api_readonly: api_readonly)
    monkeypatch.setattr(module, "handle_error", lambda message, *args, **kwargs: ("refused", message))
    module.BW_CONFIG.get_config.return_value = {}
    app = _app()
    with app.test_request_context("/instances/new", method="POST", data={"hostname": "bad host!", "name": "Edge"}):
        refused = module.instances_new.__wrapped__()
        kept = session.get(SESSION_KEY)

    assert refused[0] == "refused"
    assert kept == {"form": "instance-create", "error": refused[1], "fields": {"hostname": "bad host!", "name": "Edge"}}
    assert 'data-form-retry="instance-create"' in (TEMPLATES / "instances.html").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("relative", "view", "template"),
    [("instances.py", "instances_page", "instances.html"), ("resource_groups.py", "resource_groups_page", "groups.html")],
)
def test_the_page_hands_the_kept_form_to_its_template(relative, view, template, monkeypatch):
    module = _load(
        relative,
        API_CLIENT=Mock(readonly=False),
        BW_CONFIG=Mock(),
        BW_INSTANCES_UTILS=Mock(get_instances=Mock(return_value=[])),
        CONFIG_TASKS_EXECUTOR=Mock(),
        DATA=_Data(),
    )
    module.API_CLIENT.get_resource_groups.return_value = {}
    rendered = {}
    monkeypatch.setattr(module, "render_template", lambda name, **context: rendered.update(context, name=name) or "")
    app = _app()
    with app.test_request_context("/"):
        session[SESSION_KEY] = {"form": "f", "error": "e", "fields": {}}
        getattr(module, view).__wrapped__()

    assert rendered["name"] == template
    assert rendered["form_retry"] == {"form": "f", "error": "e", "fields": {}}
