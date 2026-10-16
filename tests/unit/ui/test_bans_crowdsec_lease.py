"""CrowdSec leases on the bans page (wave 25, lane X1F).

A lease is a short BunkerWeb ban created from a CrowdSec decision. Three things reach the browser:

* every row says what *kind* of ban it is (the API puts ``kind`` on ``GET /bans``), in the table and
  in the exports;
* a lease younger than the ``sync-bans`` pass is not in the database yet, so the page merges the
  runtime view (``GET /bans/instances``) into the table, by identity, only on request;
* unbanning a lease is a two-step conversation with the API (409 plus a preview, then the same
  request with the flags), carried to the browser by a JSON route. The explicit-ban flow is the
  form POST that already existed and does not change.

Route loading follows ``test_bans_stats.py``'s module-loader pattern.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask, get_flashed_messages

ROOT = Path(__file__).resolve().parents[3]
STATIC = ROOT / "src" / "ui" / "app" / "static"
TEMPLATES = ROOT / "src" / "ui" / "app" / "templates"


@pytest.fixture(scope="module")
def bans_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = None
    openpyxl = ModuleType("openpyxl")
    openpyxl.Workbook = Mock()
    openpyxl_styles = ModuleType("openpyxl.styles")
    openpyxl_styles.Font = Mock()
    openpyxl_styles.PatternFill = Mock()
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._bans_crowdsec_lease_test"
    route_path = ROOT / "src" / "ui" / "app" / "routes" / "bans.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    stubs = {
        "app.dependencies": dependencies,
        "openpyxl": openpyxl,
        "openpyxl.styles": openpyxl_styles,
        "qrcode": qrcode,
        "qrcode.main": qrcode_main,
        module_name: module,
    }
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module


@pytest.fixture(autouse=True)
def _a_writing_session(bans_route, monkeypatch):
    """Nothing logs in here; the permission half of `is_readonly_request` is pinned elsewhere."""
    monkeypatch.setattr(bans_route, "is_readonly_request", lambda api_readonly: api_readonly)
    monkeypatch.setattr(bans_route, "translated", lambda key, **variables: None)
    bans_route.API_CLIENT.reset_mock(side_effect=True, return_value=True)
    bans_route.BW_CONFIG.reset_mock(side_effect=True, return_value=True)
    bans_route.API_CLIENT.readonly = False


@pytest.fixture
def route_app(bans_route):
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(bans_route.bans)
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "", methods=["GET"])
    return bans_route, app


def _lease(ip="203.0.113.7", scope="global", service=None, lease_id="a" * 16, exp=25, **extra):
    return {
        "ip": ip,
        "ban_scope": scope,
        "service": service or ("_" if scope == "global" else "app"),
        "reason": "crowdsec",
        "reason_data": {"lease": True, "version": 1, "lease_id": lease_id, "source": "lapi", "action": "ban"},
        "kind": "crowdsec_lease",
        "date": 1_700_000_000,
        "exp": exp,
        "permanent": False,
        "country": "US",
        **extra,
    }


def _ban(ip="198.51.100.9", scope="global", service=None, exp=3600, **extra):
    return {
        "ip": ip,
        "ban_scope": scope,
        "service": service or ("_" if scope == "global" else "app"),
        "reason": "manual",
        "reason_data": {},
        "kind": "ban",
        "date": 1_700_000_000,
        "exp": exp,
        "permanent": False,
        "country": "FR",
        **extra,
    }


def _runtime_view(**by_instance):
    """The body of ``GET /bans/instances``: one reply per instance, rows under ``data``."""
    return {host: {"status": "success", "data": rows} for host, rows in by_instance.items()}


# ---------------------------------------------------------------------------------------------
# Kind in the table rows and the exports
# ---------------------------------------------------------------------------------------------


def _fetch(module, app, monkeypatch, rows, **form):
    monkeypatch.setattr(module, "_collect_all_bans", lambda **kwargs: [dict(row) for row in rows])
    with app.test_request_context("/bans/fetch", method="POST", data={"draw": "1", "length": "10", **form}):
        return module.bans_fetch.__wrapped__.__wrapped__().get_json()


def test_table_rows_say_what_kind_of_ban_they_are(route_app, monkeypatch):
    module, app = route_app
    body = _fetch(module, app, monkeypatch, [_lease(), _ban()])

    assert sorted(row["kind"] for row in body["data"]) == ["ban", "crowdsec_lease"]


def test_a_row_without_a_kind_is_an_ordinary_ban(route_app, monkeypatch):
    """An older API answers rows without `kind`; the page must not show a half-typed row."""
    module, app = route_app
    row = _ban()
    del row["kind"]

    assert _fetch(module, app, monkeypatch, [row])["data"][0]["kind"] == "ban"


def test_a_lease_keeps_its_verdict_for_the_reason_sentence(route_app, monkeypatch):
    """The Reason column turns `reason_data` into a sentence; a lease must still carry it."""
    module, app = route_app
    body = _fetch(module, app, monkeypatch, [_lease()])

    assert body["data"][0]["reason_data"]["lease"] is True


def test_exports_carry_the_kind(route_app, monkeypatch):
    module, app = route_app
    monkeypatch.setattr(module, "_collect_all_bans", lambda **kwargs: [_lease(), _ban()])
    with app.test_request_context("/bans/export/csv"):
        rows = module._bans_export_rows()
        response = module.bans_export_csv.__wrapped__()

    assert sorted(row["kind"] for row in rows) == ["ban", "crowdsec_lease"]
    header, *lines = response.get_data(as_text=True).strip().splitlines()
    assert header.split(",")[-1].strip('"') == "Kind"
    assert any(line.endswith("crowdsec_lease") for line in lines)


# ---------------------------------------------------------------------------------------------
# R2: live leases from the runtime view, merged by identity
# ---------------------------------------------------------------------------------------------


def test_the_runtime_view_is_not_asked_for_unless_requested(route_app):
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = [_ban()]

    rows = module._collect_all_bans()

    assert [row["ip"] for row in rows] == ["198.51.100.9"]
    module.API_CLIENT.get_instance_bans.assert_not_called()


def test_a_lease_only_the_runtime_knows_appears(route_app):
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = [_ban()]
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[_lease(ip="203.0.113.7")])

    rows = module._collect_all_bans(runtime_leases=True)

    assert sorted(row["ip"] for row in rows) == ["198.51.100.9", "203.0.113.7"]
    live = next(row for row in rows if row["ip"] == "203.0.113.7")
    assert live["kind"] == "crowdsec_lease"
    assert live["remain"] and live["end_date"]  # enriched like any other row


def test_a_lease_the_database_already_learned_is_not_shown_twice(route_app):
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = [_lease(ip="203.0.113.7", exp=300)]
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[_lease(ip="203.0.113.7", exp=25)])

    rows = module._collect_all_bans(runtime_leases=True)

    assert [row["ip"] for row in rows] == ["203.0.113.7"]
    assert rows[0]["exp"] == 300  # the durable row wins


def test_identity_is_ip_scope_and_service(route_app):
    """The same IP under another scope or service is another ban."""
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = [_lease(ip="203.0.113.7", scope="global")]
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(
        bw1=[_lease(ip="203.0.113.7", scope="service", service="app"), _lease(ip="203.0.113.7", scope="service", service="blog")]
    )

    rows = module._collect_all_bans(runtime_leases=True)

    assert sorted((row["ban_scope"], row["service"]) for row in rows) == [("global", "_"), ("service", "app"), ("service", "blog")]


def test_two_instances_report_one_lease_once(route_app):
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = []
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[_lease(lease_id="1" * 16, exp=20)], bw2=[_lease(lease_id="2" * 16, exp=28)])

    rows = module._collect_all_bans(runtime_leases=True)

    assert len(rows) == 1
    assert rows[0]["exp"] == 28  # the longest remaining time


def test_a_runtime_explicit_ban_is_not_added(route_app):
    """Only leases fill the gap before sync-bans. An explicit ban the database lacks is not this page's to invent."""
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = []
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[_ban(ip="192.0.2.1")])

    assert module._collect_all_bans(runtime_leases=True) == []


def test_a_runtime_row_without_a_kind_is_classified_by_its_reason_data(route_app):
    """Instances do not send `kind`: the page classifies with the shared helper."""
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = []
    row = _lease()
    del row["kind"]
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[row])

    rows = module._collect_all_bans(runtime_leases=True)

    assert [r["kind"] for r in rows] == ["crowdsec_lease"]


def test_an_unreachable_runtime_view_leaves_the_database_rows(route_app):
    module, _ = route_app
    module.API_CLIENT.get_bans.return_value = [_ban()]
    module.API_CLIENT.get_instance_bans.side_effect = module.ApiUnavailableError("down")

    rows = module._collect_all_bans(runtime_leases=True)

    assert [row["ip"] for row in rows] == ["198.51.100.9"]


def test_fetch_merges_only_when_asked(route_app, monkeypatch):
    module, app = route_app
    seen = []

    def collect(**kwargs):
        seen.append(kwargs)
        return [_ban()]

    monkeypatch.setattr(module, "_collect_all_bans", collect)
    for form in ({}, {"runtime_leases": "1"}):
        with app.test_request_context("/bans/fetch", method="POST", data={"draw": "1", "length": "10", **form}):
            module.bans_fetch.__wrapped__.__wrapped__()

    assert [bool(kwargs.get("runtime_leases")) for kwargs in seen] == [False, True]


def _config(**values):
    module_config = {"SERVER_NAME": "www.example.com blog.example.com", **values}
    return module_config


def test_the_probe_does_not_touch_the_instances_when_no_service_turns_leases_on(route_app):
    module, app = route_app
    module.BW_CONFIG.get_config.return_value = _config(CROWDSEC_BAN_REFRESH="0", **{"www.example.com_CROWDSEC_BAN_REFRESH": "0"})

    with app.test_request_context("/bans/runtime_leases", method="POST"):
        body = module.bans_runtime_leases.__wrapped__.__wrapped__().get_json()

    assert body == {"status": "success", "enabled": False, "count": 0}
    module.API_CLIENT.get_instance_bans.assert_not_called()
    module.API_CLIENT.get_bans.assert_not_called()


@pytest.mark.parametrize("key", ["CROWDSEC_BAN_REFRESH", "blog.example.com_CROWDSEC_BAN_REFRESH"])
def test_the_probe_counts_the_leases_the_database_lacks(route_app, key):
    module, app = route_app
    module.BW_CONFIG.get_config.return_value = _config(**{key: "30s"})
    module.API_CLIENT.get_bans.return_value = [_lease(ip="203.0.113.7")]
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[_lease(ip="203.0.113.7"), _lease(ip="203.0.113.8")])

    with app.test_request_context("/bans/runtime_leases", method="POST"):
        body = module.bans_runtime_leases.__wrapped__.__wrapped__().get_json()

    assert body == {"status": "success", "enabled": True, "count": 1}


def test_the_probe_survives_an_unreadable_configuration(route_app):
    module, app = route_app
    module.BW_CONFIG.get_config.side_effect = module.ApiUnavailableError("down")

    with app.test_request_context("/bans/runtime_leases", method="POST"):
        body = module.bans_runtime_leases.__wrapped__.__wrapped__().get_json()

    assert body["enabled"] is False


def test_the_probe_enables_the_merge_for_every_later_draw(route_app):
    """`enabled` with no missing lease still has to switch the flag on: a lease can appear before the next refresh."""
    module, app = route_app
    module.BW_CONFIG.get_config.return_value = _config(CROWDSEC_BAN_REFRESH="1m")
    module.API_CLIENT.get_bans.return_value = []
    module.API_CLIENT.get_instance_bans.return_value = _runtime_view(bw1=[])

    with app.test_request_context("/bans/runtime_leases", method="POST"):
        body = module.bans_runtime_leases.__wrapped__.__wrapped__().get_json()

    assert body == {"status": "success", "enabled": True, "count": 0}


# ---------------------------------------------------------------------------------------------
# Unban of a lease: the JSON conversation
# ---------------------------------------------------------------------------------------------


PREVIEW = {
    "lease": {"ip": "203.0.113.7", "ban_scope": "global", "service": None, "exp": 25},
    "leases": [{"lease_id": "a" * 16, "source": "bw-1", "exp": 25}],
    "decisions": [
        {
            "key": "conn:7",
            "connection_id": "conn",
            "id": 7,
            "scope": "Ip",
            "value": "203.0.113.7",
            "type": "ban",
            "origin": "crowdsec",
            "scenario": "crowdsecurity/ssh-bf",
            "remediation": "ban",
        }
    ],
    "warnings": {"list_origin": False, "range": False},
    "unavailable": [],
    "connections": ["conn"],
}


def _unban(module, app, items, **kwargs):
    with app.test_request_context("/bans/crowdsec_unban", method="POST", json={"unbans": items}, **kwargs):
        response = module.bans_crowdsec_unban.__wrapped__.__wrapped__()
        return response.status_code, response.get_json()


def test_a_409_preview_reaches_the_browser(route_app):
    module, app = route_app
    body = {
        "status": "error",
        "message": "review it",
        "preview": PREVIEW,
        "previews": [{"ip": "203.0.113.7", "ban_scope": "global", "service": None, "preview": PREVIEW}],
    }
    module.API_CLIENT.unban_crowdsec.return_value = (409, body)

    status, answer = _unban(module, app, [{"ip": "203.0.113.7", "ban_scope": "global"}])

    assert status == 409
    assert answer["preview"] == PREVIEW
    assert answer["previews"][0]["preview"] == PREVIEW
    module.API_CLIENT.unban_crowdsec.assert_called_once_with([{"ip": "203.0.113.7"}])


def test_confirming_resends_the_three_flags(route_app):
    module, app = route_app
    module.API_CLIENT.unban_crowdsec.return_value = (200, {"status": "success", "results": [{"kind": "crowdsec_lease", "status": "success"}]})

    status, answer = _unban(
        module,
        app,
        [{"ip": "203.0.113.7", "ban_scope": "global", "remove_crowdsec_decisions": True, "confirmed": True, "decision_keys": ["conn:7"]}],
    )

    assert status == 200 and answer["status"] == "success"
    module.API_CLIENT.unban_crowdsec.assert_called_once_with(
        [{"ip": "203.0.113.7", "remove_crowdsec_decisions": True, "confirmed": True, "decision_keys": ["conn:7"]}]
    )


def test_the_flags_are_only_forwarded_for_a_service_scoped_item_with_its_service(route_app):
    module, app = route_app
    module.API_CLIENT.unban_crowdsec.return_value = (200, {"status": "success"})

    _unban(module, app, [{"ip": "203.0.113.7", "ban_scope": "service", "service": "app", "confirmed": True}])

    module.API_CLIENT.unban_crowdsec.assert_called_once_with([{"ip": "203.0.113.7", "service": "app", "confirmed": True}])


def test_decision_keys_must_be_a_list_of_strings(route_app):
    module, app = route_app

    status, answer = _unban(module, app, [{"ip": "203.0.113.7", "decision_keys": "conn:7"}])

    assert status == 400 and answer["status"] == "error"
    module.API_CLIENT.unban_crowdsec.assert_not_called()


def test_a_403_names_the_missing_permission(route_app):
    module, app = route_app
    module.API_CLIENT.unban_crowdsec.return_value = (403, {"status": "error", "message": "Forbidden"})

    status, answer = _unban(module, app, [{"ip": "203.0.113.7"}])

    assert status == 403
    assert "crowdsec_delete" in answer["message"]
    assert answer["missing_permission"] == "crowdsec_delete"


def test_a_502_partial_result_is_reported_per_item(route_app):
    module, app = route_app
    results = [{"kind": "crowdsec_lease", "ip": "203.0.113.7", "status": "partial", "failed": [{"key": "conn:7", "error": "boom"}]}]
    module.API_CLIENT.unban_crowdsec.return_value = (502, {"status": "error", "results": results})

    status, answer = _unban(module, app, [{"ip": "203.0.113.7", "confirmed": True}])

    assert status == 502
    assert answer["results"] == results


def test_a_changed_result_is_reported(route_app):
    module, app = route_app
    results = [{"kind": "crowdsec_lease", "ip": "203.0.113.7", "status": "changed", "lease_changed": [{"instance": "bw-1", "lease_id": "x"}]}]
    module.API_CLIENT.unban_crowdsec.return_value = (502, {"status": "error", "results": results})

    status, answer = _unban(module, app, [{"ip": "203.0.113.7", "confirmed": True}])

    assert status == 502 and answer["results"][0]["status"] == "changed"


def test_an_invalid_ip_is_refused_before_the_api(route_app):
    module, app = route_app

    status, answer = _unban(module, app, [{"ip": "not-an-ip"}])

    assert status == 400 and answer["status"] == "error"
    module.API_CLIENT.unban_crowdsec.assert_not_called()


def test_a_read_only_database_refuses(route_app):
    module, app = route_app
    module.API_CLIENT.readonly = True

    status, answer = _unban(module, app, [{"ip": "203.0.113.7"}])

    assert status == 403 and answer["status"] == "error"
    module.API_CLIENT.unban_crowdsec.assert_not_called()


def test_the_reserved_service_names_mean_global_like_the_form_route(route_app):
    module, app = route_app
    module.API_CLIENT.unban_crowdsec.return_value = (200, {"status": "success"})

    _unban(module, app, [{"ip": "203.0.113.7", "ban_scope": "service", "service": "Web UI"}])

    module.API_CLIENT.unban_crowdsec.assert_called_once_with([{"ip": "203.0.113.7"}])


def test_an_unreachable_api_is_a_502_with_a_message(route_app):
    module, app = route_app
    module.API_CLIENT.unban_crowdsec.side_effect = module.ApiUnavailableError("API returned 500")

    status, answer = _unban(module, app, [{"ip": "203.0.113.7"}])

    assert status == 502 and answer["status"] == "error"


def test_the_json_route_demands_an_ajax_call(route_app):
    module, app = route_app
    with app.test_request_context("/bans/crowdsec_unban", method="POST", json={"unbans": []}):
        response = module.bans_crowdsec_unban.__wrapped__()

    assert response.status_code == 403


# ---------------------------------------------------------------------------------------------
# The explicit-ban flow is the form POST that already existed
# ---------------------------------------------------------------------------------------------


def _form_unban(module, app, ips):
    module.API_CLIENT.unban.reset_mock()
    with app.test_request_context("/bans/unban", method="POST", data={"selection_mode": "explicit", "ips": ips}):
        module.bans_unban.__wrapped__()
        return get_flashed_messages(with_categories=True)


def test_an_explicit_unban_posts_the_bare_identity_and_flashes_success(route_app):
    module, app = route_app
    module.API_CLIENT.unban.return_value = {"status": "success"}

    messages = _form_unban(module, app, '[{"ip": "198.51.100.9", "ban_scope": "service", "service": "app"}]')

    module.API_CLIENT.unban.assert_called_once_with([{"ip": "198.51.100.9", "service": "app"}])
    assert messages == [("message", "Unbanned 198.51.100.9 successfully.")]  # flask's name for the default (success) category


def test_the_form_route_explains_a_409_instead_of_printing_the_api_sentence(route_app):
    """The filtered "unban all matching" button cannot show a preview: a lease in the selection must say where to unban it."""
    module, app = route_app
    module.API_CLIENT.unban.side_effect = module.ApiClientError("This IP is blocked by a CrowdSec ban. Unbanning it also deletes ...", status_code=409)

    messages = _form_unban(module, app, '[{"ip": "203.0.113.7"}]')

    assert len(messages) == 1 and messages[0][0] == "error"
    assert "203.0.113.7" in messages[0][1] and "CrowdSec" in messages[0][1]
    assert "resend" not in messages[0][1]


def test_a_403_on_the_form_route_is_reported_as_before(route_app):
    """The form route cannot tell which permission was missing: the explicit flow keeps the API's own word."""
    module, app = route_app
    module.API_CLIENT.unban.side_effect = module.ApiClientError("Forbidden", status_code=403)

    messages = _form_unban(module, app, '[{"ip": "203.0.113.7"}]')

    assert messages == [("error", "Failed to unban 203.0.113.7: Forbidden")]


def test_any_other_form_failure_is_reported_as_before(route_app):
    module, app = route_app
    module.API_CLIENT.unban.side_effect = module.ApiClientError("Not found", status_code=404)

    messages = _form_unban(module, app, '[{"ip": "198.51.100.9"}]')

    assert messages == [("error", "Failed to unban 198.51.100.9: Not found")]


# ---------------------------------------------------------------------------------------------
# The API client keeps the body of the statuses that carry one
# ---------------------------------------------------------------------------------------------


@pytest.fixture
def api_client():
    from app.api_client import ApiClient

    client = ApiClient("http://api.test", "token")
    try:
        yield client
    finally:
        client.session.close()
        client._no_retry_session.close()


def _reply(status, body):
    response = Mock()
    response.status_code = status
    response.json.return_value = body
    response.text = str(body)
    response.content = b"x"
    return response


@pytest.mark.parametrize("status", [200, 403, 409, 502])
def test_the_client_returns_status_and_body_for_the_statuses_that_carry_a_result(api_client, status):
    body = {"status": "error" if status != 200 else "success", "preview": PREVIEW}
    api_client._no_retry_session.request = Mock(return_value=_reply(status, body))

    assert api_client.unban_crowdsec([{"ip": "203.0.113.7"}]) == (status, body)
    method, url = api_client._no_retry_session.request.call_args.args[:2]
    assert (method, url) == ("POST", "http://api.test/bans/unban")
    assert api_client._no_retry_session.request.call_args.kwargs["json"] == [{"ip": "203.0.113.7"}]


def test_the_client_still_raises_for_the_other_statuses(api_client):
    from app.api_client import ApiClientError, ApiUnavailableError

    api_client._no_retry_session.request = Mock(return_value=_reply(422, {"detail": "bad"}))
    with pytest.raises(ApiClientError) as caught:
        api_client.unban_crowdsec([{"ip": "x"}])
    assert caught.value.status_code == 422

    api_client._no_retry_session.request = Mock(return_value=_reply(500, {"message": "boom"}))
    with pytest.raises(ApiUnavailableError):
        api_client.unban_crowdsec([{"ip": "x"}])


def test_the_client_waits_for_a_slow_unban(api_client):
    api_client._no_retry_session.request = Mock(return_value=_reply(200, {"status": "success"}))

    api_client.unban_crowdsec([{"ip": "203.0.113.7"}])

    assert api_client._no_retry_session.request.call_args.kwargs["timeout"][1] >= 60


def test_the_client_reads_the_runtime_view(api_client, monkeypatch):
    monkeypatch.setattr(api_client, "_get", Mock(return_value={"bw1": {"data": []}}))

    assert api_client.get_instance_bans() == {"bw1": {"data": []}}
    api_client._get.assert_called_once_with("/bans/instances")


# ---------------------------------------------------------------------------------------------
# The page: markup and script
# ---------------------------------------------------------------------------------------------


def test_the_script_asks_the_runtime_view_after_the_page_loaded():
    script = (STATIC / "js" / "pages" / "bans.js").read_text(encoding="utf-8")

    assert "/runtime_leases" in script
    assert "runtime_leases" in script.split("ajax: {", 1)[1].split("error:", 1)[0], "every later draw carries the flag"


def test_the_stats_script_carries_the_runtime_leases_flag_and_refreshes_after_the_check():
    stats = (STATIC / "js" / "pages" / "bans-stats.js").read_text(encoding="utf-8")
    page = (STATIC / "js" / "pages" / "bans.js").read_text(encoding="utf-8")

    assert "runtime_leases" in stats.split("function fetchStats", 1)[1].split("function emptyStateNode", 1)[0]
    assert "BWBansStats.runtimeLeases = true" in page
    assert "BWBansStats.refresh()" in page.split("/runtime_leases", 1)[1][:600]


def test_the_script_sends_a_lease_through_the_json_route_with_the_csrf_header():
    script = (STATIC / "js" / "pages" / "bans.js").read_text(encoding="utf-8")

    assert "/crowdsec_unban" in script
    assert '"X-CSRFToken"' in script
    for flag in ("remove_crowdsec_decisions", "confirmed", "decision_keys"):
        assert flag in script


def test_the_modal_exists_beside_the_other_bans_modals():
    template = (TEMPLATES / "bans.html").read_text(encoding="utf-8")

    assert 'id="modal-crowdsec-unban"' in template
    assert "data-i18n" not in template.split('id="modal-crowdsec-unban"', 1)[1].split("modal-update-duration", 1)[0]
