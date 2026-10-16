"""Attaching a reusable resource to a service needs permission on that service as well.

The Biscuit guard derives `resource_id` from the second path segment, so `POST /redirects/{id}/attachments`
is checked for `redirect_assign` on the REDIRECT only. The service the redirect is attached to arrives in
the body (or in the create payload's `service_ids`) and was never authorized: a holder of `redirect_assign`
on one redirect could attach it to any service. Same for upstream pools, certificates and workflows.

The fix calls `authorize_resource(request, "services", "service_update", <service>)` per target service.
Detaching is covered too: removing a rule from a service changes what that service serves just as
attaching it does, so `DELETE .../attachments/{service_id}` needs the service permission as well.

Real Biscuit tokens and the real guard, borrowing the keypair/bootstrap from `test_biscuit_run_limit.py`
(the guard loads its public key once, at import).

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_biscuit_run_limit import VERSION, _KEYPAIR  # noqa: E402  (bootstrap: keypair, version, key file)

from biscuit_auth import BiscuitBuilder, Fact  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.auth.guard as guard_mod  # noqa: E402
import app.routers.certificates as certificates_mod  # noqa: E402
import app.routers.redirects as redirects_mod  # noqa: E402
import app.routers.upstreams as upstreams_mod  # noqa: E402

# Load the router as a package so `.schemas` resolves without exposing every core plugin to imports.
_WORKFLOWS_API = Path(__file__).resolve().parents[3] / "src" / "common" / "core" / "workflows" / "api"
_spec = importlib.util.spec_from_file_location("bw_authz_workflows_api", _WORKFLOWS_API / "router.py", submodule_search_locations=[str(_WORKFLOWS_API)])
workflows_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = workflows_mod
_spec.loader.exec_module(workflows_mod)

ADMIN_TOKEN = "admin-secret-token"
UPDATE = "service_update"


def _token(*perms: tuple[str, str, str], admin: bool = False) -> str:
    """A single-block token with the same facts `POST /auth` mints for a fine-grained user."""
    builder = BiscuitBuilder(
        "user({user}); time({now}); client_ip({ip}); version({version});",
        {"user": "alice", "now": datetime.now(timezone.utc), "ip": "127.0.0.1", "version": VERSION},
    )
    if admin:
        builder.add_code("admin(true);")
    for rtype, rid, pname in perms:
        builder.add_fact(Fact("api_perm({rtype}, {rid}, {pname})", {"rtype": rtype, "rid": rid, "pname": pname}))
    return builder.build(_KEYPAIR.private_key).to_base64()


class FakeDB:
    """Accepts every call, records it. Mutations are the calls whose name starts with attach/detach/create."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def call(*args, **kwargs):
            self.calls.append(name)
            if name.startswith("create_"):
                return "new-id", ""
            if name.startswith("get_"):
                return {"id": "x"}
            return ""

        return call

    @property
    def mutations(self):
        return [call for call in self.calls if call.startswith(("attach_", "detach_", "create_"))]


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    for module in (redirects_mod, upstreams_mod, certificates_mod, workflows_mod):
        monkeypatch.setattr(module, "get_db", lambda: fake)
    # Only the admin-token lookup is stubbed; the Biscuit guard keeps its real api_config.
    monkeypatch.setattr(guard_mod, "api_config", SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None))
    return fake


@pytest.fixture
def client(db):
    app = FastAPI()
    for module in (redirects_mod, upstreams_mod, certificates_mod):
        app.include_router(module.router)
    # What plugin_loader does: the guard is injected at mount time, at the plugin's own prefix.
    app.include_router(workflows_mod.router, prefix="/workflows", dependencies=[Depends(guard_mod.guard)])
    return TestClient(app, client=("127.0.0.1", 50000))


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# (resource type, assign permission, id used in the path, attach/detach URL prefix, attach body)
RESOURCES = {
    "redirect": ("redirects", "redirect_assign", "/redirects/r1/attachments", {}),
    "upstream": ("upstreams", "upstream_assign", "/upstreams/u1/attachments", {"match_path": "/"}),
    "certificate": ("certificates", "certificate_assign", "/certificates/c1/attachments", {}),
    "workflow": ("workflows", "workflow_assign", "/workflows/w1/attachments", {}),
}
IDS = {"redirect": "r1", "upstream": "u1", "certificate": "c1", "workflow": "w1"}


def _grants(kind, *services, assign=True):
    rtype, perm, _, _ = RESOURCES[kind]
    perms = [(rtype, IDS[kind], perm)] if assign else []
    perms += [("services", service, UPDATE) for service in services]
    return _token(*perms)


@pytest.fixture(params=sorted(RESOURCES))
def kind(request):
    return request.param


def _attach(client, kind, token, service):
    _, _, url, extra = RESOURCES[kind]
    return client.post(url, json={"service_id": service, **extra}, headers=_auth(token))


def _detach(client, kind, token, service):
    _, _, url, _ = RESOURCES[kind]
    return client.delete(f"{url}/{service}", headers=_auth(token))


class TestAttachNeedsTheService:
    def test_assign_on_the_resource_alone_is_refused(self, client, db, kind):
        response = _attach(client, kind, _grants(kind), "b.example.com")
        assert response.status_code == 403, response.text
        assert db.mutations == []

    def test_a_grant_on_another_service_is_refused(self, client, db, kind):
        response = _attach(client, kind, _grants(kind, "c.example.com"), "b.example.com")
        assert response.status_code == 403, response.text
        assert db.mutations == []

    def test_service_grant_without_assign_on_the_resource_is_refused(self, client, db, kind):
        # The guard itself refuses: nothing grants the assign permission on the resource.
        response = _attach(client, kind, _grants(kind, "b.example.com", assign=False), "b.example.com")
        assert response.status_code == 403, response.text
        assert db.mutations == []

    def test_both_grants_attach(self, client, db, kind):
        response = _attach(client, kind, _grants(kind, "b.example.com"), "b.example.com")
        assert response.status_code == 200, response.text
        assert db.mutations == [f"attach_{kind}"]

    def test_wildcard_service_grant_covers_every_service(self, client, db, kind):
        assert _attach(client, kind, _grants(kind, "*"), "b.example.com").status_code == 200

    def test_api_token_admin_attaches_anywhere(self, client, db, kind):
        assert _attach(client, kind, ADMIN_TOKEN, "b.example.com").status_code == 200

    def test_biscuit_admin_attaches_anywhere(self, client, db, kind):
        assert _attach(client, kind, _token(admin=True), "b.example.com").status_code == 200

    def test_a_refusal_is_not_an_existence_oracle(self, client, db, kind):
        # A caller without the service grant gets 403 for an unknown service id too, never a 404/400
        # that would tell them whether the service exists.
        assert _attach(client, kind, _grants(kind), "no-such-service").status_code == 403


class TestDetachNeedsTheService:
    """Decision: yes. Removing a rule/pool/certificate/policy from a service changes that service's
    behaviour (the redirect stops, the pool stops proxying, the policy stops enforcing)."""

    def test_assign_on_the_resource_alone_is_refused(self, client, db, kind):
        response = _detach(client, kind, _grants(kind), "b.example.com")
        assert response.status_code == 403, response.text
        assert db.mutations == []

    def test_both_grants_detach(self, client, db, kind):
        response = _detach(client, kind, _grants(kind, "b.example.com"), "b.example.com")
        assert response.status_code == 200, response.text
        assert db.mutations == [f"detach_{kind}"]

    def test_admin_detaches_anywhere(self, client, db, kind):
        assert _detach(client, kind, ADMIN_TOKEN, "b.example.com").status_code == 200
        assert _detach(client, kind, _token(admin=True), "b.example.com").status_code == 200


# Create payloads that attach on creation. The guard sees no resource id on `POST /<type>`, so only a
# wildcard create grant passes it: the service grants are what the fix adds.
CREATES = {
    "redirect": ("redirects", "redirect_create", "/redirects", lambda s: {"name": "r", "to_url": "https://x.example", "service_ids": list(s)}),
    "upstream": (
        "upstreams",
        "upstream_create",
        "/upstreams",
        lambda s: {"name": "u", "servers": [{"host": "10.0.0.1:80"}], "services": [{"service_id": x} for x in s]},
    ),
    "workflow": ("workflows", "workflow_create", "/workflows", lambda s: {"name": "w", "service_ids": list(s)}),
}


@pytest.fixture(params=sorted(CREATES))
def create_kind(request):
    return request.param


def _create(client, create_kind, token, services):
    _, _, url, body = CREATES[create_kind]
    return client.post(url, json=body(services), headers=_auth(token))


def _create_token(create_kind, *services):
    rtype, perm, _, _ = CREATES[create_kind]
    return _token((rtype, "*", perm), *(("services", service, UPDATE) for service in services))


class TestCreateWithServicesNeedsEachService:
    def test_create_grant_alone_cannot_attach_on_creation(self, client, db, create_kind):
        response = _create(client, create_kind, _create_token(create_kind), ["a.example.com", "b.example.com"])
        assert response.status_code == 403, response.text
        assert db.mutations == []

    def test_one_missing_service_refuses_the_whole_request(self, client, db, create_kind):
        response = _create(client, create_kind, _create_token(create_kind, "a.example.com"), ["a.example.com", "b.example.com"])
        assert response.status_code == 403, response.text
        # Refused before anything is created, so there is nothing to roll back.
        assert db.mutations == []

    def test_every_service_granted_creates_and_attaches(self, client, db, create_kind):
        response = _create(client, create_kind, _create_token(create_kind, "a.example.com", "b.example.com"), ["a.example.com", "b.example.com"])
        assert response.status_code == 201, response.text
        assert db.mutations == [f"create_{create_kind}", f"attach_{create_kind}", f"attach_{create_kind}"]

    def test_creating_without_services_needs_only_the_create_grant(self, client, db, create_kind):
        assert _create(client, create_kind, _create_token(create_kind), []).status_code == 201

    def test_admin_creates_and_attaches_anywhere(self, client, db, create_kind):
        assert _create(client, create_kind, ADMIN_TOKEN, ["a.example.com"]).status_code == 201
        assert _create(client, create_kind, _token(admin=True), ["a.example.com"]).status_code == 201
