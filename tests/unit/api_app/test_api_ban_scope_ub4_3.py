"""UB4-3: ban scope and legacy string bodies reach instances without changing intent."""

import ast
import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from _api_http_helpers import ADMIN_HEADERS, router_client

import app.routers.bans as bans
from app.deps import get_instances_api_caller


@pytest.fixture
def client_and_caller(monkeypatch):
    client = router_client(monkeypatch, bans, object())
    monkeypatch.setattr(bans, "CrowdSecClient", lambda _db: object())
    monkeypatch.setattr(bans, "find_lease", lambda *_: None)
    caller = Mock()
    caller.send_to_apis.return_value = (True, None)
    client.app.dependency_overrides[get_instances_api_caller] = lambda: caller
    return client, caller


@pytest.mark.parametrize("path", ["/bans", "/bans/ban", "/bans/unban"])
@pytest.mark.parametrize("service", [None, "app.example.com", "unknown", "default server", "Web UI", "bwcli", "", " ", " Web UI "])
def test_service_selects_scope_and_reserved_names_never_reach_instances(client_and_caller, path, service):
    client, caller = client_and_caller
    response = client.post(path, json={"ip": "192.0.2.1", "service": service}, headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    caller.send_to_apis.assert_called_once()
    call = caller.send_to_apis.call_args
    assert call.args == ("POST", "/unban" if path.endswith("unban") else "/ban")
    payload = call.kwargs["data"]
    assert payload["ip"] == "192.0.2.1"
    assert payload["ban_scope"] == ("service" if service == "app.example.com" else "global")
    if service == "app.example.com":
        assert payload["service"] == service
    else:
        assert "service" not in payload


@pytest.mark.parametrize("path", ["/bans", "/bans/unban"])
@pytest.mark.parametrize("bulk", [False, True])
def test_stringified_object_and_list_keep_every_target_and_scope(client_and_caller, path, bulk):
    client, caller = client_and_caller
    items = [{"ip": "192.0.2.1", "service": "app.example.com"}, {"ip": "192.0.2.2", "service": "Web UI"}]
    response = client.post(path, json=json.dumps(items if bulk else items[0]), headers=ADMIN_HEADERS)
    assert response.status_code == 200, response.text
    payloads = [call.kwargs["data"] for call in caller.send_to_apis.call_args_list]
    expected = [("192.0.2.1", "service", "app.example.com")]
    if bulk:
        expected.append(("192.0.2.2", "global", None))
    assert [(p["ip"], p["ban_scope"], p.get("service")) for p in payloads] == expected


@pytest.mark.parametrize("path", ["/bans", "/bans/unban"])
@pytest.mark.parametrize("body", ["42", "garbage", "null", '[{"ip":"192.0.2.1"},42]', '{"ip":"bad-ip"}'])
def test_invalid_string_body_is_refused_before_any_instance_write(client_and_caller, path, body):
    client, caller = client_and_caller
    response = client.post(path, json=body, headers=ADMIN_HEADERS)
    assert response.status_code == 422, response.text
    caller.send_to_apis.assert_not_called()


def test_reserved_names_match_ui_and_lua():
    root = Path(__file__).resolve().parents[3]
    expected = {"unknown", "Web UI", "bwcli", "default server", ""}
    tree = ast.parse((root / "src/ui/app/utils.py").read_text())
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "RESERVED_SERVICE_NAMES" for target in node.targets)
    )
    ui_names = ast.literal_eval(assignment.value.args[0])
    lua = (root / "src/bw/lua/bunkerweb/api.lua").read_text()
    table = re.search(r"local RESERVED_SERVICE_NAMES = \{([^}]+)\}", lua).group(1)
    lua_names = set(re.findall(r'\["([^"]*)"\] = true', table))
    assert set(bans.RESERVED_SERVICE_NAMES) == ui_names == lua_names == expected
