"""Creating a certificate for services needs permission on each of those services.

The certificate creation routes live in three plugin routers (`selfsigned`, `customcert`, `letsencrypt`).
The Biscuit guard strips the plugin segment and sees `POST /certificates`, so it checks `certificate_create`
with no resource id; the `service_ids` in the payload were never authorized, and a `certificate_create`
holder could attach the new certificate to (or start an issuance for) any service.

The routers now call `authorize_resource(request, "services", "service_update", <service>)` for every
target service, as their first statement, so a refusal happens before anything is written or scheduled.
Same pattern as `test_attachments_authz.py`.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_attachments_authz import ADMIN_TOKEN, UPDATE, _auth, _token  # noqa: E402  (also boots the guard's keypair)

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.guard as guard_mod  # noqa: E402

_CORE = Path(__file__).resolve().parents[3] / "src" / "common" / "core"


def _load(provider: str):
    spec = importlib.util.spec_from_file_location(f"bw_authz_{provider}_api", _CORE / provider / "api" / "router.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


selfsigned_mod = _load("selfsigned")
customcert_mod = _load("customcert")
letsencrypt_mod = _load("letsencrypt")
PROVIDERS = (selfsigned_mod, customcert_mod, letsencrypt_mod)


class FakeDB:
    """Accepts every call a certificate route makes, and records the ones that write or schedule."""

    def __init__(self):
        self.calls = []

    def create_certificate(self, **kwargs):
        self.calls.append("create_certificate")
        return "", "new-id"

    def get_certificate_details(self, _certificate_id):
        return {"id": "new-id"}

    def get_services(self, **_kwargs):
        return [{"id": "a.example.com"}, {"id": "b.example.com"}]

    def get_config(self, **_kwargs):
        return {"AUTO_LETS_ENCRYPT": "yes"}

    def checked_changes(self, *_args, **_kwargs):
        self.calls.append("checked_changes")
        return ""

    @property
    def writes(self):
        return self.calls


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    for module in PROVIDERS:
        monkeypatch.setattr(module, "get_db", lambda: fake)
    monkeypatch.setattr(selfsigned_mod, "generate_self_signed", lambda *_args, **_kwargs: (b"certificate", b"private-key"))
    monkeypatch.setattr(guard_mod, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    return fake


@pytest.fixture
def client(db):
    app = FastAPI()
    # What plugin_loader does: the guard is injected at mount time, at the plugin's own prefix.
    for module, prefix in zip(PROVIDERS, ("/selfsigned", "/customcert", "/letsencrypt")):
        app.include_router(module.router, prefix=prefix, dependencies=[Depends(guard_mod.guard)])
    return TestClient(app, client=("127.0.0.1", 50000))


def _selfsigned(client, token, services):
    body = {"name": "n", "common_name": "a.example.com", "service_ids": list(services)}
    return client.post("/selfsigned/certificates", json=body, headers=_auth(token))


def _customcert(client, token, services):
    files = {"certificate": ("c.pem", b"certificate"), "private_key": ("k.pem", b"private-key")}
    return client.post("/customcert/certificates/upload", files=files, data={"name": "n", "service_ids": json.dumps(list(services))}, headers=_auth(token))


def _letsencrypt(client, token, services):
    return client.post("/letsencrypt/certificates", json={"service_ids": list(services)}, headers=_auth(token))


# route name -> (request helper, status of a successful call, can the service list be empty)
ROUTES = {
    "selfsigned": (_selfsigned, 201, True),
    "customcert": (_customcert, 201, True),
    "letsencrypt": (_letsencrypt, 202, False),
}


@pytest.fixture(params=sorted(ROUTES))
def route(request):
    return ROUTES[request.param]


def _create_token(*services):
    return _token(("certificates", "*", "certificate_create"), *(("services", service, UPDATE) for service in services))


class TestCertificateCreateNeedsEachService:
    def test_create_grant_alone_is_refused(self, client, db, route):
        call, _, _ = route
        response = call(client, _create_token(), ["a.example.com"])
        assert response.status_code == 403, response.text
        assert db.writes == []

    def test_a_grant_on_another_service_is_refused(self, client, db, route):
        call, _, _ = route
        response = call(client, _create_token("b.example.com"), ["a.example.com"])
        assert response.status_code == 403, response.text
        assert db.writes == []

    def test_one_missing_service_refuses_the_whole_request(self, client, db, route):
        call, _, _ = route
        response = call(client, _create_token("a.example.com"), ["a.example.com", "b.example.com"])
        assert response.status_code == 403, response.text
        # Refused before anything is written or any issuance is scheduled.
        assert db.writes == []

    def test_both_grants_create(self, client, db, route):
        call, ok, _ = route
        response = call(client, _create_token("a.example.com"), ["a.example.com"])
        assert response.status_code == ok, response.text
        assert db.writes

    def test_every_service_granted_creates(self, client, db, route):
        call, ok, _ = route
        response = call(client, _create_token("a.example.com", "b.example.com"), ["a.example.com", "b.example.com"])
        assert response.status_code == ok, response.text

    def test_wildcard_service_grant_covers_every_service(self, client, db, route):
        call, ok, _ = route
        assert call(client, _create_token("*"), ["a.example.com", "b.example.com"]).status_code == ok

    def test_api_token_admin_creates_for_any_service(self, client, db, route):
        call, ok, _ = route
        assert call(client, ADMIN_TOKEN, ["a.example.com", "b.example.com"]).status_code == ok

    def test_biscuit_admin_creates_for_any_service(self, client, db, route):
        call, ok, _ = route
        assert call(client, _token(admin=True), ["a.example.com", "b.example.com"]).status_code == ok

    def test_a_refusal_is_not_an_existence_oracle(self, client, db, route):
        # Without the service grant an unknown id is a 403, never the 404 that would reveal it does not exist.
        call, _, _ = route
        assert call(client, _create_token(), ["no-such-service"]).status_code == 403
        assert db.writes == []

    def test_creating_without_services_needs_only_the_create_grant(self, client, db, route):
        call, ok, can_be_empty = route
        if not can_be_empty:
            pytest.skip("Let's Encrypt issuance requires at least one service")
        assert call(client, _create_token(), []).status_code == ok
