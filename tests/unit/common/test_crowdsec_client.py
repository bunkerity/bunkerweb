"""CrowdSec API fan-out uses credential-bearing, live BunkerWeb instances."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[3]
CLIENT_PATH = ROOT / "src" / "common" / "utils" / "CrowdSec.py"


class _InstanceAPI:
    def __init__(self, instance):
        self.instance = instance

    def request(self, method, path, data=None, timeout=None):
        if path == "/crowdsec/connections":
            local_id = self.instance["local_id"]
            payload = {"connections": [{"id": local_id, "url": "http://127.0.0.1", "services": ["global"]}]}
        else:
            payload = {"decisions": [], "total": 0, "offset": 0, "limit": 50, "observed_at": 1}
        return True, "", 200, {"status": "success", "data": payload}


class _API:
    dials = []

    @classmethod
    def from_instance(cls, instance, *, token=None):
        cls.dials.append((instance, token))
        return _InstanceAPI(instance)


def _load_client():
    api_module = ModuleType("API")
    api_module.API = _API
    previous_api = sys.modules.get("API")
    sys.modules["API"] = api_module
    try:
        spec = importlib.util.spec_from_file_location("crowdsec_client_under_test", CLIENT_PATH)
        assert spec is not None and spec.loader is not None, "CrowdSec client source is missing"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_api is None:
            sys.modules.pop("API", None)
        else:
            sys.modules["API"] = previous_api


def test_connections_read_credentials_and_report_down_instances(monkeypatch):
    module = _load_client()
    _API.dials.clear()
    monkeypatch.setenv("API_TOKEN", "global-fallback")
    instances = [
        {"hostname": "bw-one", "status": "up", "credential": "one-secret", "local_id": "a" * 64},
        {"hostname": "bw-down", "status": "down", "credential": "down-secret", "local_id": "b" * 64},
        {"hostname": "bw-two", "status": "up", "credential": "two-secret", "local_id": "c" * 64},
    ]
    db = Mock()
    db.get_instances.return_value = instances

    result = module.CrowdSecClient(db).connections()

    db.get_instances.assert_called_once_with(with_credential=True)
    assert [instance["hostname"] for instance, _token in _API.dials] == ["bw-one", "bw-two"]
    assert all(token == "global-fallback" for _instance, token in _API.dials)
    assert [connection["instance"] for connection in result["connections"]] == ["bw-one", "bw-two"]
    assert result["errors"] == {"bw-down": "BunkerWeb instance is down"}
    assert all(len(connection["id"]) == 129 for connection in result["connections"])
    assert "one-secret" not in repr(result) and "two-secret" not in repr(result)


def test_resolve_returns_502_for_down_instance_and_404_for_missing_instance():
    module = _load_client()
    down = {"hostname": "bw-down", "status": "down", "credential": "down-secret"}
    db = Mock()
    db.get_instances.return_value = [down]
    client = module.CrowdSecClient(db)

    with pytest.raises(module.CrowdSecError) as unavailable:
        client._resolve(module.encode_connection("bw-down", "b" * 64))
    with pytest.raises(module.CrowdSecError) as missing:
        client._resolve(module.encode_connection("bw-missing", "c" * 64))

    assert unavailable.value.status == 502
    assert str(unavailable.value) == "BunkerWeb instance is down"
    assert missing.value.status == 404


def test_query_routes_the_local_connection_id_to_its_instance(monkeypatch):
    module = _load_client()
    _API.dials.clear()
    monkeypatch.setenv("API_TOKEN", "global-fallback")
    instance = {"hostname": "bw-one", "status": "up", "credential": "one-secret", "local_id": "a" * 64}
    db = Mock()
    db.get_instances.return_value = [instance]
    connection_id = module.encode_connection("bw-one", "a" * 64)

    result = module.CrowdSecClient(db).query(connection_id, "decisions", {"limit": 50})

    assert result["decisions"] == []
    assert _API.dials == [(instance, "global-fallback")]
