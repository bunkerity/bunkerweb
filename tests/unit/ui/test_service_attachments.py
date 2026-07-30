"""Read-side aggregation of resources attached to a service."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(scope="module")
def attachments_module():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    module_name = "app.models._service_attachments_test"
    module_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "models" / "service_attachments.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture
def client():
    api = Mock()
    api.get_upstreams.return_value = {"upstreams": [{"id": "u1", "name": "pool-a"}], "total": 1}
    api.get_certificates.return_value = {"certificates": [{"id": "c1", "common_name": "example.com"}], "total": 1}
    api.get_redirects.return_value = {"redirects": [], "total": 0}
    api.get_workflows.return_value = {"workflows": [{"id": "w1", "name": "block-bots"}], "total": 1}
    return api


def test_returns_one_entry_per_family(attachments_module, client):
    result = attachments_module.get_service_attachments(client, "app.example.com")
    assert set(result) == set(attachments_module.RESOURCE_FAMILIES)
    assert result["upstream"]["items"] == [{"id": "u1", "name": "pool-a"}]
    assert result["redirect"]["items"] == []
    assert all(entry["error"] is None for entry in result.values())


def test_filters_by_service_id(attachments_module, client):
    attachments_module.get_service_attachments(client, "app.example.com")
    for getter in (client.get_upstreams, client.get_certificates, client.get_redirects, client.get_workflows):
        assert getter.call_args.kwargs["service_id"] == "app.example.com"


def test_one_failing_family_does_not_blank_the_others(attachments_module, client):
    from app.api_client import ApiClientError

    client.get_workflows.side_effect = ApiClientError("workflows plugin not loaded", status_code=404)
    result = attachments_module.get_service_attachments(client, "app.example.com")
    assert result["workflow"]["items"] == []
    assert "workflows plugin not loaded" in result["workflow"]["error"]
    assert result["upstream"]["items"] == [{"id": "u1", "name": "pool-a"}]


def test_blank_service_id_queries_nothing(attachments_module, client):
    result = attachments_module.get_service_attachments(client, "")
    assert all(entry["items"] == [] and entry["error"] is None for entry in result.values())
    client.get_upstreams.assert_not_called()
