"""Provider-owned certificate API router contracts."""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import schemas  # type: ignore

ROOT = Path(__file__).resolve().parents[3]


class _Router:
    def __init__(self, **_kwargs):
        self.routes = []

    def post(self, path, **_kwargs):
        def decorator(function):
            self.routes.append(("POST", path, function))
            return function

        return decorator

    def get(self, path, **_kwargs):
        def decorator(function):
            self.routes.append(("GET", path, function))
            return function

        return decorator


class _JSONResponse:
    def __init__(self, *, status_code, content):
        self.status_code = status_code
        self.body = json.dumps(content).encode()


def _load_provider(provider):
    app = ModuleType("app")
    app.__path__ = []
    app_schemas = ModuleType("app.schemas")
    app_schemas.CertificateAttachmentRequest = schemas.CertificateAttachmentRequest
    app_schemas.CertificateCreateRequest = schemas.CertificateCreateRequest
    app_schemas.CertificateRenewRequest = schemas.CertificateRenewRequest
    app_schemas.CertificateUpdateRequest = schemas.CertificateUpdateRequest
    app_utils = ModuleType("app.utils")
    app_utils.get_db = Mock()
    fastapi = ModuleType("fastapi")
    fastapi.APIRouter = _Router
    fastapi.File = lambda default=..., **_kwargs: default
    fastapi.Form = lambda default=..., **_kwargs: default
    fastapi.UploadFile = object
    responses = ModuleType("fastapi.responses")
    responses.JSONResponse = _JSONResponse
    certificate_utils = ModuleType("certificate_utils")
    certificate_utils.MAX_PEM_SIZE = 1024 * 1024
    certificate_utils.generate_self_signed = Mock(return_value=(b"certificate", b"private-key"))
    modules = {
        "app": app,
        "app.schemas": app_schemas,
        "app.utils": app_utils,
        "fastapi": fastapi,
        "fastapi.responses": responses,
        "certificate_utils": certificate_utils,
    }
    path = ROOT / "src" / "common" / "core" / provider / "api" / "router.py"
    name = f"bw_test_{provider}_api"
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def _json(response):
    return json.loads(response.body)


def _certificate(source):
    return {
        "id": "cert-1",
        "name": "example",
        "source": source,
        "status": "valid",
        "renewal_metadata": {},
        "attachments": [],
    }


def test_provider_manifests_and_routes_are_owned_by_each_plugin():
    expected = {
        "selfsigned": {"/certificates", "/certificates/{certificate_id}/renew", "/certificates/renew-due"},
        "customcert": {"/certificates/upload"},
        "letsencrypt": {
            "/certificates",
            "/certificates/orphans",
            "/certificates/renew-due",
        },
    }
    for provider, paths in expected.items():
        manifest = json.loads((ROOT / "src" / "common" / "core" / provider / "plugin.json").read_text())
        assert manifest["extensions"]["api"] == {"module": "api/router.py", "prefix": f"/{provider}"}
        module = _load_provider(provider)
        mounted_paths = {path for _, path, _ in module.router.routes}
        assert mounted_paths == paths
        assert not any("revoke" in path for path in mounted_paths)


def test_selfsigned_create_uses_shared_encrypted_db_boundary():
    module = _load_provider("selfsigned")
    db = Mock()
    db.create_certificate.return_value = ("", "cert-1")
    db.get_certificate_details.return_value = _certificate("selfsigned")
    module.get_db = lambda: db
    payload = module.SelfSignedCreateRequest(name="example", common_name="example.com")

    response = module.create_certificate(payload)

    assert response.status_code == 201
    assert db.create_certificate.call_args.kwargs["source"] == "selfsigned"
    assert db.create_certificate.call_args.kwargs["private_key_pem"] == b"private-key"
    assert "private" not in _json(response)["certificate"]


class _Upload:
    def __init__(self, data):
        self.data = data

    async def read(self, _size):
        return self.data


def test_customcert_upload_validates_then_uses_shared_db_boundary():
    module = _load_provider("customcert")
    db = Mock()
    db.create_certificate.return_value = ("", "cert-1")
    db.get_certificate_details.return_value = _certificate("customcert")
    module.get_db = lambda: db

    response = asyncio.run(
        module.upload_certificate(
            certificate=_Upload(b"certificate"),
            private_key=_Upload(b"private-key"),
            name="example",
            description="uploaded",
            service_ids='["example.com"]',
            primary=True,
            renewal_metadata="{}",
        )
    )

    assert response.status_code == 201
    assert db.create_certificate.call_args.kwargs["source"] == "customcert"
    assert db.create_certificate.call_args.kwargs["service_ids"] == ["example.com"]


def test_customcert_upload_reports_cross_provider_owner_as_conflict():
    module = _load_provider("customcert")
    db = Mock()
    db.create_certificate.return_value = ("Certificate fingerprint is already owned by letsencrypt", None)
    module.get_db = lambda: db

    response = asyncio.run(
        module.upload_certificate(
            certificate=_Upload(b"certificate"),
            private_key=_Upload(b"private-key"),
            name="example",
            description="uploaded",
            service_ids="[]",
            primary=True,
            renewal_metadata="{}",
        )
    )

    assert response.status_code == 409
    assert _json(response)["message"] == "Certificate fingerprint is already owned by letsencrypt"


def test_letsencrypt_issuance_reads_service_settings_and_only_schedules():
    module = _load_provider("letsencrypt")
    db = Mock()
    db.get_services.return_value = [{"id": "example.com"}]
    db.get_config.return_value = {"example.com_AUTO_LETS_ENCRYPT": "yes"}
    db.checked_changes.return_value = ""
    module.get_db = lambda: db

    response = module.issue_certificate(module.LetsEncryptCreateRequest(service_ids=["example.com"]))

    assert response.status_code == 202
    db.checked_changes.assert_called_once_with(["config"], plugins_changes=["letsencrypt"], value=True)
    db.create_certificate.assert_not_called()


def test_letsencrypt_issuance_falls_back_to_global_single_site_setting():
    module = _load_provider("letsencrypt")
    db = Mock()
    db.get_services.return_value = [{"id": "example.com"}]
    db.get_config.return_value = {"AUTO_LETS_ENCRYPT": "yes"}
    db.checked_changes.return_value = ""
    module.get_db = lambda: db

    response = module.issue_certificate(module.LetsEncryptCreateRequest(service_ids=["example.com"]))

    assert response.status_code == 202


def test_letsencrypt_renew_due_reports_inventory_and_schedules_once():
    module = _load_provider("letsencrypt")
    db = Mock()
    db.get_certificates.side_effect = [
        {
            "items": [
                {"id": "due", "name": "due.example", "status": "expired"},
                {"id": "valid", "name": "valid.example", "status": "valid"},
            ],
            "total": 3,
        },
        {"items": [{"id": "soon", "name": "soon.example", "status": "expiring_soon"}], "total": 3},
    ]
    db.checked_changes.return_value = ""
    module.get_db = lambda: db

    response = module.renew_due_certificates()

    assert response.status_code == 202
    assert _json(response)["total_due"] == 2
    assert [item["id"] for item in _json(response)["results"]] == ["due", "soon"]
    assert db.get_certificates.call_args_list[1].kwargs["offset"] == 2
    db.checked_changes.assert_called_once_with(["config"], plugins_changes=["letsencrypt"], value=True)


def test_letsencrypt_orphans_are_read_only():
    module = _load_provider("letsencrypt")
    db = Mock()
    module.get_db = lambda: db
    module.list_letsencrypt_orphans = Mock(return_value=[{"cert_name": "example", "account": "missing", "server": "acme"}])

    response = module.get_orphan_certificates()

    assert response.status_code == 200
    assert _json(response)["count"] == 1
    module.list_letsencrypt_orphans.assert_called_once_with(db)
    db.checked_changes.assert_not_called()


def test_selfsigned_renew_due_paginates_and_uses_shared_contract():
    module = _load_provider("selfsigned")
    db = Mock()
    db.get_certificates.side_effect = [
        {"items": [{"id": "due", "name": "due.example", "status": "expired"}], "total": 2},
        {"items": [{"id": "valid", "name": "valid.example", "status": "valid"}], "total": 2},
    ]
    db.renew_self_signed_certificate.return_value = ""
    module.get_db = lambda: db

    response = module.renew_due_certificates()

    assert response.status_code == 200
    assert _json(response) == {
        "status": "success",
        "total_due": 1,
        "results": [{"id": "due", "name": "due.example", "source": "selfsigned", "status": "renewed"}],
        "message": "Renewed 1 due self-signed certificate",
    }
    assert db.get_certificates.call_args_list[1].kwargs["offset"] == 1
