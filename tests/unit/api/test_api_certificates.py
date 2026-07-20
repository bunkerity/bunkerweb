"""Certificate router response and source-behaviour contracts."""

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
        pass

    def get(self, *_args, **_kwargs):
        return lambda function: function

    post = get
    patch = get
    delete = get


class _Response:
    def __init__(self, content=b"", *, status_code=200, media_type=None, headers=None):
        self.status_code = status_code
        self.body = content if isinstance(content, bytes) else str(content).encode()
        self.media_type = media_type
        self.headers = {key.lower(): value for key, value in (headers or {}).items()}


class _JSONResponse(_Response):
    def __init__(self, *, status_code, content):
        super().__init__(json.dumps(content).encode(), status_code=status_code, media_type="application/json")


def _load_router():
    modules = {
        "fastapi": ModuleType("fastapi"),
        "fastapi.responses": ModuleType("fastapi.responses"),
        "bw_certificates": ModuleType("bw_certificates"),
        "bw_certificates.routers": ModuleType("bw_certificates.routers"),
        "bw_certificates.auth": ModuleType("bw_certificates.auth"),
        "bw_certificates.auth.guard": ModuleType("bw_certificates.auth.guard"),
        "bw_certificates.schemas": schemas,
        "bw_certificates.utils": ModuleType("bw_certificates.utils"),
    }
    modules["bw_certificates"].__path__ = []
    modules["bw_certificates.routers"].__path__ = []
    modules["bw_certificates.auth"].__path__ = []
    modules["bw_certificates.auth.guard"].guard = lambda: None
    modules["fastapi"].APIRouter = _Router
    modules["fastapi"].Depends = lambda dependency: dependency
    modules["fastapi"].File = lambda default=..., **_kwargs: default
    modules["fastapi"].Form = lambda default=..., **_kwargs: default
    modules["fastapi"].Query = lambda default=..., **_kwargs: default
    modules["fastapi"].UploadFile = object
    modules["fastapi.responses"].JSONResponse = _JSONResponse
    modules["fastapi.responses"].Response = _Response
    modules["bw_certificates.utils"].LOGGER = Mock()
    modules["bw_certificates.utils"].get_db = Mock()
    with patch.dict(sys.modules, modules):
        path = ROOT / "src" / "api" / "app" / "routers" / "certificates.py"
        spec = importlib.util.spec_from_file_location("bw_certificates.routers.certificates", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ROUTER = _load_router()


def _json(response):
    return json.loads(response.body)


def _certificate(source="selfsigned", attachments=None):
    return {
        "id": "cert-1",
        "name": "example",
        "source": source,
        "common_name": "example.com",
        "sans": ["example.com"],
        "fingerprint": "a" * 64,
        "status": "valid",
        "attachments": attachments or [],
        "renewal_metadata": {},
    }


def test_list_contract_has_no_private_key_fields(monkeypatch):
    db = Mock()
    db.get_certificates.return_value = {"items": [_certificate()], "total": 1, "offset": 0, "limit": 100}
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.list_certificates(search="", source="", status="", service_id="", offset=0, limit=100)

    body = _json(response)
    assert response.status_code == 200
    assert body["total"] == 1
    assert not any("private" in key for key in body["certificates"][0])
    db.import_legacy_certbot_certificates.assert_not_called()


def test_startup_import_is_best_effort(monkeypatch):
    db = Mock()
    db.import_legacy_certbot_certificates.side_effect = RuntimeError("missing keyring")
    logger = Mock()
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)
    monkeypatch.setattr(ROUTER, "LOGGER", logger)

    ROUTER.import_legacy_certificates()

    logger.warning.assert_called_once()


def test_lifespan_runs_legacy_import_before_serving():
    source = (ROOT / "src" / "api" / "app" / "main.py").read_text()
    lifespan = source.partition("async def lifespan")[2].partition("def create_app")[0]

    assert lifespan.index("import_legacy_certificates()") < lifespan.index("yield")


def test_attach_and_delete_guard(monkeypatch):
    db = Mock()
    db.attach_certificate.return_value = ""
    db.get_certificate_details.return_value = _certificate(attachments=[{"service_id": "example.com", "is_primary": True}])
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    attached = ROUTER.attach_certificate("cert-1", schemas.CertificateAttachmentRequest(service_id="example.com"))
    blocked = ROUTER.delete_certificate("cert-1")

    assert attached.status_code == 200
    assert blocked.status_code == 409
    db.delete_certificate.assert_not_called()


def test_download_returns_public_pem_only(monkeypatch):
    db = Mock()
    db.get_certificate_details.return_value = _certificate()
    db.get_certificate_public_data.return_value = b"-----BEGIN CERTIFICATE-----\npublic\n-----END CERTIFICATE-----\n"
    monkeypatch.setattr(ROUTER, "get_db", lambda: db)

    response = ROUTER.download_certificate("cert-1", "chain")

    assert response.status_code == 200
    assert b"PRIVATE KEY" not in response.body
    assert response.headers["x-content-type-options"] == "nosniff"
    db.get_certificate_public_data.assert_called_once_with("cert-1", "chain")
