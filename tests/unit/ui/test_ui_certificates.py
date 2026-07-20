"""Certificate UI client and Flask route contracts."""

import importlib.util
import json
import re
import sys
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader, select_autoescape

from app.api_client import ApiClient, ApiUnavailableError


@pytest.fixture
def api_client():
    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()


@pytest.fixture(scope="module")
def certificates_route():
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    app_utils = ModuleType("app.utils")
    app_utils.flash = Mock()
    module_name = "app.routes._certificates_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "certificates.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "app.dependencies": dependencies,
            "app.utils": app_utils,
            module_name: module,
        },
    ):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def route_app(certificates_route):
    module, client = certificates_route
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.certificates)
    return module, client, app


def test_api_client_paths_and_payloads(api_client, monkeypatch):
    get = Mock(side_effect=[{"certificates": []}, {"certificate": {"id": "cert-1"}}, {"orphans": [{"cert_name": "example"}]}])
    post = Mock(return_value={"status": "success"})
    patch_request = Mock(return_value={"status": "success"})
    delete = Mock(return_value={"status": "success"})
    raw_request = Mock(return_value=object())
    monkeypatch.setattr(api_client, "_get", get)
    monkeypatch.setattr(api_client, "_post", post)
    monkeypatch.setattr(api_client, "_patch", patch_request)
    monkeypatch.setattr(api_client, "_delete", delete)
    monkeypatch.setattr(api_client, "_raw_request", raw_request)

    api_client.get_certificates(search="example", source="selfsigned", status="valid", service_id="svc", offset=10, limit=20)
    assert api_client.get_certificate("cert-1") == {"id": "cert-1"}
    assert api_client.get_letsencrypt_orphans() == [{"cert_name": "example"}]
    api_client.create_certificate(source="selfsigned", name="internal")
    api_client.create_certificate(source="letsencrypt", name="ignored", service_ids=["svc"])
    api_client.update_certificate("cert-1", name="renamed", description="Inventory label")
    api_client.attach_certificate("cert-1", "svc", primary=False)
    api_client.detach_certificate("cert-1", "svc")
    api_client.renew_certificate("cert-1", "selfsigned", valid_days=90)
    api_client.renew_due_certificates()
    api_client.delete_certificate("cert-1")
    api_client.download_certificate("cert-1", part="leaf")

    assert get.call_args_list == [
        call(
            "/certificates",
            params={
                "offset": 10,
                "limit": 20,
                "search": "example",
                "source": "selfsigned",
                "status": "valid",
                "service_id": "svc",
            },
        ),
        call("/certificates/cert-1"),
        call("/letsencrypt/certificates/orphans"),
    ]
    assert post.call_args_list == [
        call("/selfsigned/certificates", json={"name": "internal"}),
        call("/letsencrypt/certificates", json={"service_ids": ["svc"]}),
        call("/certificates/cert-1/attachments", json={"service_id": "svc", "primary": False}),
        call("/selfsigned/certificates/cert-1/renew", json={"valid_days": 90}),
        call("/selfsigned/certificates/renew-due"),
        call("/letsencrypt/certificates/renew-due"),
    ]
    patch_request.assert_called_once_with(
        "/certificates/cert-1",
        json={"name": "renamed", "description": "Inventory label"},
    )
    assert delete.call_args_list == [
        call("/certificates/cert-1/attachments/svc"),
        call("/certificates/cert-1"),
    ]
    raw_request.assert_called_once_with("GET", "/certificates/cert-1/download", params={"part": "leaf"})

    with pytest.raises(ValueError, match="does not support targeted renewal"):
        api_client.renew_certificate("cert-1", "letsencrypt")


def test_bulk_renew_reports_provider_failure_after_other_provider_commits(api_client, monkeypatch):
    monkeypatch.setattr(
        api_client,
        "_post",
        Mock(
            side_effect=[
                {
                    "status": "success",
                    "total_due": 1,
                    "results": [{"id": "self-1", "source": "selfsigned", "status": "renewed"}],
                    "message": "Renewed one self-signed certificate",
                },
                ApiUnavailableError("ACME provider unavailable"),
            ]
        ),
    )

    result = api_client.renew_due_certificates()

    assert result["status"] == "partial"
    assert result["total_due"] == 1
    assert result["results"][-1] == {
        "source": "letsencrypt",
        "status": "error",
        "message": "ACME provider unavailable",
    }
    assert "Renewed one self-signed certificate" in result["message"]
    assert "letsencrypt: ACME provider unavailable" in result["message"]


def test_bulk_renew_partial_result_uses_warning_toast(route_app, monkeypatch):
    module, client, app = route_app
    client.readonly = False
    client.renew_due_certificates.return_value = {
        "status": "partial",
        "total_due": 1,
        "message": "Self-signed renewed; ACME unavailable",
    }
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context(
        "/certificates/action",
        method="POST",
        data={"action": "renew_due"},
    ):
        response = module.certificates_action.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("Self-signed renewed; ACME unavailable", "warning")


def test_upload_client_removes_json_content_type(api_client, monkeypatch):
    request = Mock(return_value={"status": "success"})
    monkeypatch.setattr(api_client, "_request", request)
    certificate = ("certificate.pem", BytesIO(b"certificate"), "application/x-pem-file")
    private_key = ("private-key.pem", BytesIO(b"key"), "application/x-pem-file")

    api_client.upload_certificate(certificate, private_key, name="custom", service_ids="[]")

    request.assert_called_once_with(
        "POST",
        "/customcert/certificates/upload",
        files={"certificate": certificate, "private_key": private_key},
        data={"name": "custom", "service_ids": "[]"},
        headers={"Content-Type": None},
    )


def test_page_loads_inventory_and_only_serializes_public_context(route_app, monkeypatch):
    module, client, app = route_app
    certificate = {
        "id": "cert-1",
        "name": "internal",
        "description": "Inventory label",
        "common_name": "internal.example",
        "source": "selfsigned",
        "status": "expiring_soon",
        "issuer": "BunkerWeb",
        "valid_to": "2026-08-01T00:00:00Z",
        "attachments": [{"service_id": "svc", "is_primary": True}],
        "renewal_metadata": {"account": "not-for-the-browser"},
        "private_key": "must-never-be-serialized",
    }
    client.get_certificates.return_value = {"certificates": [certificate], "total": 2}
    client.get_services.return_value = [{"id": "svc"}]
    client.get_letsencrypt_orphans.return_value = []
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/certificates"):
        assert module.certificates_page.__wrapped__() == "rendered"

    client.get_certificates.assert_called_once_with(limit=500)
    client.get_services.assert_called_once_with(with_drafts=True)
    context = render.call_args.kwargs
    assert context["truncated"] is True
    assert context["upcoming"] == [certificate]
    assert context["certificate_context"] == [
        {
            "id": "cert-1",
            "name": "internal",
            "description": "Inventory label",
            "common_name": "internal.example",
            "source": "selfsigned",
            "status": "expiring_soon",
            "is_orphan": False,
            "attachments": [{"service_id": "svc", "is_primary": True}],
        }
    ]
    assert "renewal_metadata" not in context["certificate_context"][0]
    assert "private_key" not in context["certificate_context"][0]


def test_page_exposes_read_only_letsencrypt_orphan_details(route_app, monkeypatch):
    module, client, app = route_app
    orphan = {"cert_name": "managed", "account": "missing-account", "server": "https://acme.example/directory"}
    certificate = {
        "id": "cert-le",
        "name": "managed",
        "common_name": "managed.example",
        "source": "letsencrypt",
        "status": "valid",
        "issuer": "ACME",
        "valid_to": "2026-08-01T00:00:00Z",
        "attachments": [],
        "renewal_metadata": {"cert_name": "managed"},
    }
    client.get_certificates.return_value = {"certificates": [certificate], "total": 1}
    client.get_services.return_value = []
    client.get_letsencrypt_orphans.return_value = [orphan]
    render = Mock(return_value="rendered")
    monkeypatch.setattr(module, "render_template", render)

    with app.test_request_context("/certificates"):
        assert module.certificates_page.__wrapped__() == "rendered"

    rendered_certificate = render.call_args.kwargs["certificates"][0]
    assert rendered_certificate["is_orphan"] is True
    assert rendered_certificate["orphan_state"] == orphan


def test_update_changes_name_and_description_only(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())

    with app.test_request_context(
        "/certificates/update",
        method="POST",
        data={
            "certificate_id": "cert-1",
            "name": " Renamed ",
            "description": " Inventory metadata ",
            "common_name": "must-not-change.example",
        },
    ):
        response = module.certificates_update.__wrapped__()

    assert response.status_code == 302
    client.update_certificate.assert_called_once_with(
        "cert-1",
        name="Renamed",
        description="Inventory metadata",
    )


def test_create_selfsigned_parses_services_sans_and_validity(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())
    client.create_certificate.return_value = {"message": "created"}

    with app.test_request_context(
        "/certificates/create",
        method="POST",
        data={
            "source": "selfsigned",
            "name": " internal ",
            "description": " Test certificate ",
            "common_name": "internal.example",
            "sans": "internal.example, www.internal.example\ninternal.example",
            "service_ids": ["svc-a", "svc-b", "svc-a"],
            "primary": "on",
            "valid_days": "90",
            "key_type": "rsa",
        },
    ):
        response = module.certificates_create.__wrapped__()

    assert response.status_code == 302
    client.create_certificate.assert_called_once_with(
        source="selfsigned",
        name="internal",
        description="Test certificate",
        common_name="internal.example",
        sans=["internal.example", "www.internal.example"],
        service_ids=["svc-a", "svc-b"],
        primary=True,
        valid_days=90,
        key_type="rsa",
        renewal_metadata={},
    )


def test_create_acme_uses_existing_service_settings_only(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())
    client.create_certificate.return_value = {"message": "scheduled"}

    with app.test_request_context(
        "/certificates/create",
        method="POST",
        data={
            "source": "letsencrypt",
            "service_ids": ["app.example", "api.example"],
            "name": "ignored",
            "description": "ignored",
            "common_name": "ignored.example",
            "sans": "ignored.example",
            "primary": "on",
            "valid_days": "7",
            "key_type": "rsa",
        },
    ):
        response = module.certificates_create.__wrapped__()

    assert response.status_code == 302
    client.create_certificate.assert_called_once_with(
        source="letsencrypt",
        name="Let's Encrypt: app.example",
        description="",
        common_name="app.example",
        sans=[],
        service_ids=["app.example", "api.example"],
        primary=False,
        valid_days=365,
        key_type="ec",
        renewal_metadata={},
    )


def test_upload_forwards_only_files_and_non_secret_metadata(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())

    with app.test_request_context(
        "/certificates/upload",
        method="POST",
        data={
            "name": "custom",
            "description": "Imported",
            "service_ids": ["svc-a", "svc-b"],
            "primary": "on",
            "certificate": (BytesIO(b"public certificate"), "../../certificate.pem"),
            "private_key": (BytesIO(b"private key"), "../../private.key"),
        },
        content_type="multipart/form-data",
    ):
        response = module.certificates_upload.__wrapped__()

    assert response.status_code == 302
    args = client.upload_certificate.call_args.args
    kwargs = client.upload_certificate.call_args.kwargs
    assert args[0][0] == "certificate.pem"
    assert args[1][0] == "private.key"
    assert kwargs == {
        "name": "custom",
        "description": "Imported",
        "service_ids": '["svc-a", "svc-b"]',
        "primary": "true",
        "renewal_metadata": "{}",
    }


def test_upload_rejects_oversized_body_before_parsing_files(route_app, monkeypatch):
    module, client, app = route_app
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context(
        "/certificates/upload",
        method="POST",
        environ_overrides={"CONTENT_LENGTH": str(module.CERTIFICATE_UPLOAD_MAX_BODY_SIZE + 1)},
    ):
        response = module.certificates_upload.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("Certificate upload exceeds the 2 MiB request limit", "error")
    client.upload_certificate.assert_not_called()


@pytest.mark.parametrize(
    ("action", "method", "expected"),
    [
        ("delete", "delete_certificate", call("cert-1")),
    ],
)
def test_certificate_actions_use_explicit_client_methods(route_app, monkeypatch, action, method, expected):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())
    getattr(client, method).return_value = {"message": "done"}

    with app.test_request_context(
        "/certificates/action",
        method="POST",
        data={"action": action, "certificate_id": "cert-1", "source": "selfsigned"},
    ):
        response = module.certificates_action.__wrapped__()

    assert response.status_code == 302
    assert getattr(client, method).call_args == expected


def test_renew_action_routes_to_certificate_provider(route_app, monkeypatch):
    module, client, app = route_app
    monkeypatch.setattr(module, "flash", Mock())
    client.renew_certificate.return_value = {"message": "renewed"}

    with app.test_request_context(
        "/certificates/action",
        method="POST",
        data={"action": "renew", "certificate_id": "cert-1", "source": "selfsigned", "valid_days": "90"},
    ):
        response = module.certificates_action.__wrapped__()

    assert response.status_code == 302
    client.renew_certificate.assert_called_once_with("cert-1", "selfsigned", valid_days=90)


def test_readonly_blocks_mutation(route_app, monkeypatch):
    module, client, app = route_app
    client.readonly = True
    monkeypatch.setattr(module, "flash", Mock())

    with app.test_request_context(
        "/certificates/action",
        method="POST",
        data={"action": "delete", "certificate_id": "cert-1"},
    ):
        response = module.certificates_action.__wrapped__()

    assert response.status_code == 302
    client.delete_certificate.assert_not_called()


def test_download_only_proxies_public_leaf_or_chain(route_app):
    module, client, app = route_app
    client.download_certificate.return_value = SimpleNamespace(
        content=b"public pem",
        headers={"Content-Disposition": 'attachment; filename="public.pem"'},
    )

    with app.test_request_context("/certificates/cert-1/download/leaf"):
        response = module.certificates_download.__wrapped__("cert-1", "leaf")

    assert response.status_code == 200
    assert response.data == b"public pem"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    client.download_certificate.assert_called_once_with("cert-1", part="leaf")

    client.download_certificate.reset_mock()
    with app.test_request_context("/certificates/cert-1/download/private_key"):
        response = module.certificates_download.__wrapped__("cert-1", "private_key")

    assert response.status_code == 400
    client.download_certificate.assert_not_called()


def test_certificate_template_is_valid_jinja_and_uses_shared_components():
    ui_root = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
    template = ui_root / "templates" / "certificates.html"
    source = template.read_text(encoding="utf-8")
    locale = json.loads((ui_root / "static" / "locales" / "en.json").read_text(encoding="utf-8"))

    Environment().parse(source)
    assert 'from "components/file-upload.html" import file_upload' in source
    assert 'from "components/modal.html" import modal' in source
    assert "filename='js/components/file-upload.js'" in source
    assert 'title(label="Certificates", i18n_key="navigation.certificates", level="h1"' in source
    assert "certificates.assignment_notice" in source
    assert "certificate-edit-modal" in source
    assert "used by your services" not in source
    assert "download/private_key" not in source
    assert '{% set certificates_url = url_for("certificates") %}' in source
    assert 'url_for("certificates.certificates_' not in source
    assert 'classes="certificate-heal"' not in source
    acme_start = source.index('{% call modal(id="certificate-acme-modal"')
    acme_end = source.index("{% endcall %}", acme_start)
    acme_modal = source[acme_start:acme_end]
    assert 'service_select("certificate-acme-services", services, true)' in acme_modal
    for ignored_field in ("name", "description", "common_name", "sans", "primary", "valid_days", "key_type"):
        assert f'name="{ignored_field}"' not in acme_modal
    assert locale["navigation"]["certificates"] == "Certificates"
    for key in set(re.findall(r'["\'](certificates\.[a-z_]+(?:\.[a-z_]+)*)["\']', source)):
        if key in {"certificates.css", "certificates.js"}:
            continue
        value = locale
        for segment in key.split("."):
            value = value[segment]
        assert isinstance(value, str)
    assert set(locale["certificates"]["source"]) == {"customcert", "letsencrypt", "selfsigned"}
    assert set(locale["certificates"]["status"]) == {
        "expired",
        "expiring_soon",
        "not_yet_valid",
        "revoked",
        "valid",
    }


def test_legacy_letsencrypt_ui_is_api_only():
    root = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "letsencrypt" / "ui"
    blueprint = (root / "blueprints" / "letsencrypt.py").read_text(encoding="utf-8")
    hooks = (root / "hooks.py").read_text(encoding="utf-8")

    assert 'route("/letsencrypt"' in blueprint
    assert 'url_for("certificates.certificates_page")' in blueprint
    assert 'href="/certificates"' not in hooks
    assert 'url_for("certificates.certificates_page")' in hooks
    assert "DB." not in blueprint
    assert "DB." not in hooks
    assert "API_CLIENT.get_letsencrypt_orphans()" in hooks


def test_certificate_interactions_translate_dynamic_copy_and_restore_focus():
    ui_root = Path(__file__).resolve().parents[3] / "src" / "ui" / "app"
    script = (ui_root / "static" / "js" / "pages" / "certificates.js").read_text(encoding="utf-8")
    locale = json.loads((ui_root / "static" / "locales" / "en.json").read_text(encoding="utf-8"))
    keys = {
        "attach_all",
        "attach_copy",
        "confirm_delete",
        "confirm_generic",
        "confirm_renew",
        "confirm_renew_due",
        "file_extensions",
        "file_select",
        "file_selected",
        "file_size_limit",
        "showing_count",
        "upload_invalid",
    }

    for key in keys:
        assert f'"certificates.{key}"' in script
        assert isinstance(locale["certificates"][key], str)
    assert '"hidden.bs.modal"' in script
    assert "modal.show(trigger)" in script


def test_certificate_template_renders_with_shared_component_contracts():
    templates = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "templates"
    environment = Environment(
        loader=ChoiceLoader(
            [
                DictLoader({"dashboard.html": ("{% block head %}{% endblock %}" "{% block content %}{% endblock %}" "{% block scripts %}{% endblock %}")}),
                FileSystemLoader(templates),
            ]
        ),
        autoescape=select_autoescape(),
    )
    environment.globals.update(
        csrf_token=lambda: "csrf",
        url_for=lambda endpoint, **values: (
            f"/static/{values['filename']}" if endpoint == "static" else "/certificates" if endpoint == "certificates" else "#"
        ),
    )

    rendered = environment.get_template("certificates.html").render(
        certificates=[],
        total=0,
        truncated=False,
        status_counts={},
        issuer_counts=[],
        upcoming=[],
        certificate_context=[],
        services=[{"id": "app.example"}],
        readonly=False,
        style_nonce="style",
        script_nonce="script",
    )

    assert re.search(r"<h1\b", rendered)
    assert '<textarea id="certificates-data" hidden readonly>' in rendered
    assert 'action="/certificates/create"' in rendered
    assert 'action="/certificates/upload"' in rendered
    assert 'id="certificate-acme-services"' in rendered
    assert 'src="/static/js/components/file-upload.js"' in rendered
