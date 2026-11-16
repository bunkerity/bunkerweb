"""Dependency upgrades must preserve draft uploads and prefixed API startup."""

import warnings
from types import SimpleNamespace

import pytest

from test_biscuit_run_limit import VERSION  # noqa: F401 (API import bootstrap)
from test_openapi_schema import app  # noqa: F401 (real application fixture)

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.configs as configs_mod


@pytest.mark.parametrize("field, expected", [(None, True), ("false", False), ("true", True)])
def test_upload_preserves_draft_unless_explicitly_changed(monkeypatch, field, expected):
    writes = []
    current = {"service_id": None, "type": "http", "name": "snip", "data": "old", "method": "api", "is_draft": True}

    def save(config_type, name, config, *, service_id=None):
        writes.append(config)
        return ""

    monkeypatch.setattr(configs_mod, "get_db", lambda: SimpleNamespace(get_custom_config=lambda *args, **kwargs: dict(current), upsert_custom_config=save))
    application = FastAPI()
    application.dependency_overrides[configs_mod.guard] = lambda: None
    application.include_router(configs_mod.router)
    response = TestClient(application).patch(
        "/configs/global/http/snip/upload",
        files={"file": ("snip.conf", b"new content", "text/plain")},
        data={} if field is None else {"new_is_draft": field},
    )
    assert response.status_code == 200, response.text
    assert len(writes) == 1
    assert writes[0]["is_draft"] is expected
    assert writes[0]["data"] == "new content"


@pytest.mark.usefixtures("app")
def test_prefixed_api_starts_without_root_path_deprecation(monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(main_mod.api_config, "API_ROOT_PATH", "/control")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        application = main_mod.create_app()
    assert application.root_path == "/control"
    assert not [warning for warning in caught if "root_path" in str(warning.message)]
