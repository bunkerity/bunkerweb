"""CrowdSec transport errors and investigation results stay within selected scope."""

from hashlib import sha256
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

import CrowdSec as crowdsec

LOCAL_ID = "a" * 64
INSTANCE = {"hostname": "instance.example"}
CONNECTION = crowdsec.encode_connection(INSTANCE["hostname"], LOCAL_ID)


@pytest.fixture
def client():
    db = Mock()
    db.get_instances.return_value = [INSTANCE]
    return crowdsec.CrowdSecClient(db, token="fixture-token")


def test_connection_id_roundtrips_without_exposing_hostname():
    assert crowdsec.decode_connection(CONNECTION) == (sha256(INSTANCE["hostname"].encode()).hexdigest(), LOCAL_ID)
    assert INSTANCE["hostname"] not in CONNECTION


@pytest.mark.parametrize("value", [None, "short", "A" * 64 + "_" + LOCAL_ID, "a" * 64 + "_" + "b" * 63])
def test_connection_ids_reject_invalid_shape(value):
    with pytest.raises(crowdsec.CrowdSecError) as raised:
        crowdsec.decode_connection(value)
    assert raised.value.status == 400


@pytest.mark.parametrize(
    "path,status,payload,expected_status,expected_text",
    [
        ("/crowdsec/decisions", 403, {"msg": "scope denied"}, 403, "scope denied"),
        ("/crowdsec/decisions", 500, {"msg": "controlled error"}, 502, "controlled error"),
        ("/bans", 403, {"msg": "secret backend detail"}, 403, "could not complete"),
        ("/crowdsec/decisions", 200, {"status": "success", "data": "bad shape"}, 502, "unsupported response"),
    ],
)
def test_transport_error_mapping_limits_exposed_details(client, monkeypatch, path, status, payload, expected_status, expected_text):
    api = Mock()
    api.request.return_value = True, "", status, payload
    monkeypatch.setattr(crowdsec.API, "from_instance", Mock(return_value=api))
    with pytest.raises(crowdsec.CrowdSecError) as raised:
        client.instance_request(INSTANCE, "POST", path, {"connection": LOCAL_ID})
    assert raised.value.status == expected_status and expected_text in str(raised.value)
    assert "secret backend detail" not in str(raised.value)
    crowdsec.API.from_instance.assert_called_once_with(INSTANCE, token="fixture-token")
    api.request.assert_called_once_with("POST", path, data={"connection": LOCAL_ID}, timeout=(5, 30))


@pytest.mark.parametrize("reply", [(False, "sensitive transport", None, None), (True, "", 200, None), RuntimeError("sensitive transport")])
def test_unavailable_instance_hides_transport_exception(client, monkeypatch, reply):
    api = Mock()
    if isinstance(reply, Exception):
        api.request.side_effect = reply
    else:
        api.request.return_value = reply
    monkeypatch.setattr(crowdsec.API, "from_instance", lambda *_, **__: api)
    with pytest.raises(crowdsec.CrowdSecError, match="instance is unavailable") as raised:
        client.instance_request(INSTANCE, "GET", "/bans")
    assert "sensitive transport" not in str(raised.value)


def test_empty_bans_success_is_normalized(client, monkeypatch):
    api = Mock()
    api.request.return_value = True, "", 200, {"status": "success", "msg": ""}
    monkeypatch.setattr(crowdsec.API, "from_instance", lambda *_, **__: api)
    assert client.instance_request(INSTANCE, "GET", "/bans") == []


def test_connections_keep_available_rows_and_report_each_failed_instance(client, monkeypatch):
    client.db.get_instances.return_value += [{"hostname": "offline"}, {"hostname": "malformed"}]
    request = Mock(side_effect=[{"connections": [{"id": LOCAL_ID}, {"id": "bad"}, None]}, crowdsec.CrowdSecError("offline"), {"connections": None}])
    monkeypatch.setattr(client, "_request", request)
    result = client.connections()
    assert [item["id"] for item in result["connections"]] == [CONNECTION, None]
    assert result["connections"][0]["local_id"] == LOCAL_ID
    assert result["connections"][0]["instance"] == INSTANCE["hostname"]
    assert result["errors"]["offline"] == "offline"
    assert "invalid CrowdSec connections" in result["errors"]["malformed"]
    assert isinstance(result["observed_at"], (int, float))


def test_query_resolves_instance_and_overrides_supplied_connection(client, monkeypatch):
    request = Mock(return_value={"decisions": []})
    monkeypatch.setattr(client, "_request", request)
    assert client.query(CONNECTION, "decisions", {"connection": "injected", "ip": "192.0.2.1"}) == {"decisions": []}
    request.assert_called_once_with(INSTANCE, "POST", "/crowdsec/decisions", {"connection": LOCAL_ID, "ip": "192.0.2.1"})


def test_query_rejects_operation_missing_instance_and_bad_response(client, monkeypatch):
    with pytest.raises(crowdsec.CrowdSecError, match="Invalid CrowdSec operation"):
        client.query(CONNECTION, "arbitrary")
    monkeypatch.setattr(client, "_request", Mock(return_value=[]))
    with pytest.raises(crowdsec.CrowdSecError, match="invalid CrowdSec response"):
        client.query(CONNECTION, "decisions")
    client.db.get_instances.return_value = []
    with pytest.raises(crowdsec.CrowdSecError) as raised:
        client.query(CONNECTION, "decisions")
    assert raised.value.status == 404
    client.db.get_instances.side_effect = RuntimeError("secret DB URI")
    with pytest.raises(crowdsec.CrowdSecError, match="Unable to read configured"):
        client.connections()


@pytest.mark.parametrize("services", [[], None, [""], ["one;two"], ["one,two"], [2]])
def test_investigation_requires_unambiguous_service_scope(client, monkeypatch, services):
    monkeypatch.setattr(client, "_request", Mock(return_value={"connections": [{"id": LOCAL_ID, "services": services}]}))
    with pytest.raises(crowdsec.CrowdSecError) as raised:
        client.investigate(CONNECTION, "192.0.2.1")
    assert raised.value.status == 404


@pytest.mark.parametrize("global_scope", [False, True])
def test_investigation_filters_reports_and_bans_to_selected_service(client, monkeypatch, global_scope):
    services = ["global"] if global_scope else ["example.com"]
    ip = "192.0.2.1"
    reports = [{"ip": ip, "server_name": "example.com"}, {"ip": ip, "server_name": "other"}, {"ip": "192.0.2.2", "server_name": "example.com"}, "bad"]
    bans = [
        {"ip": ip, "ban_scope": "global"},
        {"ip": ip, "ban_scope": "service", "service": "example.com"},
        {"ip": ip, "ban_scope": "service", "service": "other"},
        {"ip": "invalid"},
    ]
    requests = []

    def request(instance, method, path, data=None):
        requests.append(path)
        if path == "/crowdsec/connections":
            return {"connections": [{"id": LOCAL_ID, "services": services}]}
        if path.startswith("/metrics/"):
            return {"data": reports, "filtered": 12}
        if path == "/bans":
            return {"bans": bans}
        return {"decisions": ["decision"], "total": 10, "alerts": ["alert"], "allowed": False}

    monkeypatch.setattr(client, "_request", request)
    result = client.investigate(CONNECTION, ip)
    assert result["reports"] == reports[: 2 if global_scope else 1]
    assert result["bans"] == bans[: 3 if global_scope else 2]
    assert result["decisions_total"] == 10 and result["reports_total"] == 12
    assert result["errors"] == {} and result["allowlist"]["allowed"] is False
    panes = parse_qs(urlsplit(next(path for path in requests if path.startswith("/metrics/"))).query)["search_panes"]
    assert panes == [f"ip:{ip}" + ("" if global_scope else ";server_name:example.com")]


def test_investigation_preserves_partial_results_when_sections_fail(client, monkeypatch):
    def request(instance, method, path, data=None):
        if path == "/crowdsec/connections":
            return {"connections": [{"id": LOCAL_ID, "services": ["global"]}]}
        raise crowdsec.CrowdSecError("section offline")

    monkeypatch.setattr(client, "_request", request)
    result = client.investigate(CONNECTION, "2001:db8::1")
    assert result["ip"] == "2001:db8::1"
    assert result["decisions"] == result["alerts"] == result["reports"] == result["bans"] == []
    assert result["allowlist"] is None
    assert set(result["errors"]) == {"decisions", "alerts", "reports", "bans", "allowlist"}
    with pytest.raises(crowdsec.CrowdSecError) as raised:
        client.investigate(CONNECTION, "not an IP")
    assert raised.value.status == 400
