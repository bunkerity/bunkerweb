"""Small authenticated router harness; guards and Biscuit verification stay real."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from test_biscuit_run_limit import VERSION, _KEYPAIR  # noqa: F401 - shared signing-key bootstrap

import app.auth.guard as guard_mod

ADMIN_TOKEN = "c6-test-admin-token"
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def router_client(monkeypatch, module, database):
    monkeypatch.setattr(module, "get_db", lambda **_: database)
    monkeypatch.setattr(
        guard_mod,
        "api_config",
        SimpleNamespace(API_TOKEN=ADMIN_TOKEN, API_ROOT_PATH=None, openapi_url=None, docs_url=None, redoc_url=None),
    )
    application = FastAPI()
    application.include_router(module.router)
    return TestClient(application, client=("127.0.0.1", 50000))
