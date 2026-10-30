"""The /bans blueprint: collecting bans from Redis and the instances, the DataTables feed, exports and the ban,
unban and duration actions (including the CrowdSec administrator gate)."""

import csv
import io
import json
from time import time
from unittest.mock import MagicMock

import pytest

CORS = {"Sec-Fetch-Mode": "cors"}
NOW = int(time())


@pytest.fixture
def bans(h):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com b.example.com"}
    h.instances.get_bans.return_value = []
    h.routes.bans.get_redis_client = lambda: None
    return h.routes.bans


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


def _ban(ip="1.2.3.4", **extra):
    return {"ip": ip, "exp": 3600, "reason": "bad", "date": NOW - 60, "country": "FR", "service": "_", "ban_scope": "global", "permanent": False} | extra


# --------------------------------------------------------------------------------------
# page and DataTables feed
# --------------------------------------------------------------------------------------
def test_page_splits_the_server_name_setting_into_services(h, bans):
    response = h.client().get("/bans")

    assert response.status_code == 200
    assert h.renders[-1] == ("bans.html", {"services": ["a.example.com", "b.example.com"]})


def test_fetch_refuses_a_request_that_is_neither_cors_nor_ajax(h, bans):
    response = h.client().post("/bans/fetch")

    assert response.status_code == 403
    assert response.get_data(as_text=True) == "CORS or AJAX request required"
    h.instances.get_bans.assert_not_called()


def test_fetch_formats_rows_and_escapes_markup_in_a_reason(h, bans):
    h.instances.get_bans.return_value = [_ban(reason="<script>alert(1)</script>", country="FR")]

    body = h.client().post("/bans/fetch", headers=CORS, data={"draw": "3"}).get_json()

    assert body["draw"] == 3
    assert body["recordsTotal"] == body["recordsFiltered"] == 1
    row = body["data"][0]
    assert row["ip"] == "1.2.3.4"
    assert row["reason"] == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert row["scope"] == "global"
    assert row["service"] == "_"
    assert row["time_left"] == "1 hour"


def test_fetch_search_panes_count_the_filtered_and_total_rows(h, bans):
    h.instances.get_bans.return_value = [_ban("1.1.1.1"), _ban("2.2.2.2", ban_scope="service", service="a.example.com"), _ban("3.3.3.3", permanent=True, exp=0)]

    body = h.client().post("/bans/fetch", headers=CORS, data={"searchPanes[scope][0]": "service"}).get_json()

    assert [row["ip"] for row in body["data"]] == ["2.2.2.2"]
    assert body["recordsTotal"] == 3 and body["recordsFiltered"] == 1
    scope = {option["value"]: option for option in body["searchPanes"]["options"]["scope"]}
    assert (scope["global"]["total"], scope["global"]["count"]) == (2, 0)
    assert (scope["service"]["total"], scope["service"]["count"]) == (1, 1)
    end_date = {option["value"]: option for option in body["searchPanes"]["options"]["end_date"]}
    assert end_date["permanent"]["total"] == 1


def test_fetch_global_search_matches_any_column(h, bans):
    h.instances.get_bans.return_value = [_ban("1.1.1.1", reason="scanner"), _ban("2.2.2.2", reason="brute")]

    body = h.client().post("/bans/fetch", headers=CORS, data={"search[value]": "BRUTE"}).get_json()

    assert [row["ip"] for row in body["data"]] == ["2.2.2.2"]


def test_fetch_pagination_and_ordering(h, bans):
    h.instances.get_bans.return_value = [_ban(f"10.0.0.{n}", date=NOW - n) for n in range(1, 6)]

    # DataTables sends two extra leading columns: index 3 is the backend column 1, "ip"
    body = h.client().post("/bans/fetch", headers=CORS, data={"start": "1", "length": "2", "order[0][column]": "3", "order[0][dir]": "asc"}).get_json()

    assert [row["ip"] for row in body["data"]] == ["10.0.0.2", "10.0.0.3"]
    assert body["recordsFiltered"] == 5


def test_fetch_reads_redis_global_service_and_lease_keys(h, bans):
    redis = h.FakeRedis(
        {
            b"bans_ip_9.9.9.9": json.dumps({"reason": "waf", "date": NOW - 10, "country": "US", "service": "_"}).encode(),
            b"bans_service_my%7Bsvc%7D_ip_8.8.8.8": json.dumps({"reason": "limit", "date": NOW - 10, "country": "DE"}).encode(),
            b"bans_ip_7.7.7.7": b"not json at all",
            b"bans_cs_ip_6.6.6.6": json.dumps(
                {"reason": "crowdsec", "date": NOW - 5, "country": "FR", "reason_data": {"instance": "bw-1", "connection": "main"}}
            ).encode(),
            b"bans_cs_service_site_ip_5.5.5.5": json.dumps({"reason": "crowdsec", "date": NOW - 5, "country": "FR"}).encode(),
            b"bans_cs_ip_4.4.4.4": b"{broken",
        },
        {
            b"bans_ip_9.9.9.9": 120,
            b"bans_service_my%7Bsvc%7D_ip_8.8.8.8": 0,
            b"bans_ip_7.7.7.7": 60,
            b"bans_cs_ip_6.6.6.6": 30,
            b"bans_cs_service_site_ip_5.5.5.5": 30,
        },
    )
    bans.get_redis_client = lambda: redis

    rows = {row["ip"]: row for row in h.client().post("/bans/fetch", headers=CORS, data={"length": "100"}).get_json()["data"]}

    assert set(rows) == {"9.9.9.9", "8.8.8.8", "7.7.7.7", "6.6.6.6", "5.5.5.5"}
    assert rows["9.9.9.9"]["scope"] == "global"
    assert rows["8.8.8.8"]["scope"] == "service" and rows["8.8.8.8"]["service"] == "my{svc}"
    assert rows["8.8.8.8"]["permanent"] is True and rows["8.8.8.8"]["time_left"] == "permanent"
    assert rows["7.7.7.7"]["reason"] == "not json at all"
    assert rows["6.6.6.6"]["kind"] == "crowdsec_lease"
    assert (rows["6.6.6.6"]["cs_node"], rows["6.6.6.6"]["cs_connection"]) == ("bw-1", "main")
    assert rows["5.5.5.5"]["scope"] == "service" and rows["5.5.5.5"]["service"] == "site"


def test_redis_ban_wins_over_the_same_ban_reported_by_an_instance(h, bans):
    redis = h.FakeRedis({b"bans_ip_9.9.9.9": json.dumps({"reason": "from-redis", "date": NOW - 10}).encode()}, {b"bans_ip_9.9.9.9": 120})
    bans.get_redis_client = lambda: redis
    h.instances.get_bans.return_value = [_ban("9.9.9.9", reason="from-instance")]

    body = h.client().post("/bans/fetch", headers=CORS).get_json()

    assert [row["reason"] for row in body["data"]] == ["from-redis"]


def test_a_redis_failure_falls_back_to_the_instances(h, bans):
    class Broken(h.FakeRedis):
        def scan_iter(self, *a, **kw):
            raise RuntimeError("redis down")

    bans.get_redis_client = lambda: Broken()
    h.instances.get_bans.return_value = [_ban("1.1.1.1")]

    body = h.client().post("/bans/fetch", headers=CORS).get_json()

    assert [row["ip"] for row in body["data"]] == ["1.1.1.1"]


def test_fetch_reports_a_collection_failure_to_the_user(h, bans):
    h.instances.get_bans.side_effect = RuntimeError("boom")
    client = h.client()

    body = client.post("/bans/fetch", headers=CORS).get_json()

    assert body["data"] == [] and body["recordsTotal"] == 0
    assert any("Failed to fetch bans" in message for message in _flashed(h, client))


# --------------------------------------------------------------------------------------
# exports
# --------------------------------------------------------------------------------------
def test_csv_export_neutralizes_a_formula_in_the_reason(h, bans):
    h.instances.get_bans.return_value = [_ban("1.1.1.1", reason='=HYPERLINK("http://evil")')]

    response = h.client().get("/bans/export/csv")

    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"].startswith("attachment; filename=bunkerweb_bans_")
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows[0] == ["Date", "IP Address", "Country", "Reason", "Scope", "Service", "End Date", "Time Left"]
    assert rows[1][1] == "1.1.1.1"
    assert not rows[1][3].startswith("="), "a spreadsheet would execute this cell"


def test_csv_export_honours_search_and_order_parameters(h, bans):
    h.instances.get_bans.return_value = [_ban("1.1.1.1", reason="a"), _ban("2.2.2.2", reason="b"), _ban("3.3.3.3", reason="b")]

    response = h.client().get("/bans/export/csv?search=b&order_column=ip&order_dir=asc")

    ips = [row[1] for row in list(csv.reader(io.StringIO(response.get_data(as_text=True))))[1:]]
    assert ips == ["2.2.2.2", "3.3.3.3"]


def test_csv_export_failure_is_a_json_500(h, bans):
    h.instances.get_bans.side_effect = RuntimeError("boom")

    response = h.client().get("/bans/export/csv")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Failed to export bans"}


def test_excel_export_is_a_workbook_with_one_row_per_ban(h, bans):
    openpyxl = pytest.importorskip("openpyxl")
    h.instances.get_bans.return_value = [_ban("1.1.1.1"), _ban("2.2.2.2", permanent=True, exp=0)]

    response = h.client().get("/bans/export/excel")

    assert response.status_code == 200
    sheet = openpyxl.load_workbook(io.BytesIO(response.get_data())).active
    assert sheet.title == "Bans"
    values = [[cell.value for cell in row] for row in sheet.iter_rows()]
    assert values[0][:2] == ["Date", "IP Address"]
    assert {row[1] for row in values[1:]} == {"1.1.1.1", "2.2.2.2"}
    assert sheet["G3"].value == "permanent" or sheet["G2"].value == "permanent"


def test_excel_export_failure_is_a_json_500(h, bans):
    h.instances.get_bans.side_effect = RuntimeError("boom")

    assert h.client().get("/bans/export/excel").status_code == 500


# --------------------------------------------------------------------------------------
# ban
# --------------------------------------------------------------------------------------
def test_ban_in_read_only_mode_changes_nothing(h, bans):
    h.db.readonly = True
    client = h.client()

    response = client.post("/bans/ban", data={"bans": json.dumps([{"ip": "1.2.3.4"}])})

    assert response.status_code == 302 and response.headers["Location"].endswith("/bans")
    h.instances.ban.assert_not_called()
    assert "Database is in read-only mode" in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({}, "No bans."),
        ({"bans": "{not json"}, "Invalid bans parameter on /bans/ban."),
        ({"selection_mode": "weird"}, "Invalid ban selection mode."),
        ({"selection_mode": "filtered", "source": "bans"}, "Invalid filtered ban source."),
        ({"bans": "[]"}, "No matching reports."),
    ],
)
def test_ban_rejects_malformed_requests(h, bans, form, message):
    client = h.client()

    response = client.post("/bans/ban", data=form)

    assert response.status_code == 302
    h.instances.ban.assert_not_called()
    assert message in _flashed(h, client)


def test_ban_validates_ips_and_clamps_scope_and_service(h, bans):
    h.instances.ban.return_value = ""
    payload = [
        {"ip": "1.2.3.4", "exp": 0, "reason": "manual"},
        {"ip": "not-an-ip"},
        {"ip": "5.6.7.8", "exp": 60, "ban_scope": "service", "service": "Web UI"},
        {"ip": "9.9.9.9", "ban_scope": "nonsense", "exp": 30},
        {"no_ip": True},
        "garbage",
    ]
    client = h.client()

    response = client.post("/bans/ban", data={"bans": json.dumps(payload)})

    assert response.status_code == 302 and "/loading" in response.headers["Location"]
    assert [call.args for call in h.instances.ban.call_args_list] == [
        ("1.2.3.4", 0, "manual", "", "global"),
        ("5.6.7.8", 60, "ui", "unknown", "global"),  # a reserved service name downgrades the ban to the global scope
        ("9.9.9.9", 30, "ui", "", "global"),
    ]
    flashed = _flashed(h, client)
    assert "Invalid IP address: not-an-ip" in flashed
    assert "Banned 1.2.3.4 successfully." in flashed


def test_ban_surfaces_an_instance_failure(h, bans):
    h.instances.ban.return_value = "instance down"
    client = h.client()

    client.post("/bans/ban", data={"bans": json.dumps([{"ip": "1.2.3.4"}])})

    assert "Failed to ban 1.2.3.4 on some instances: instance down" in _flashed(h, client)


def test_ban_from_filtered_reports_bans_each_distinct_target_once(h, bans):
    h.instances.ban.return_value = ""
    h.instances.get_reports_query.return_value = {
        "data": [
            {"ip": "1.1.1.1", "server_name": "_", "reason": "waf"},
            {"ip": "1.1.1.1", "server_name": "_", "reason": "waf"},
            {"ip": "2.2.2.2", "server_name": "site.example.com"},
        ]
    }
    h.config.get_config.return_value = {"BAD_BEHAVIOR_BAN_TIME": "2h", "site.example.com_BAD_BEHAVIOR_BAN_TIME": "10m"}

    h.client().post("/bans/ban", data={"selection_mode": "filtered", "source": "reports"})

    assert [call.args for call in h.instances.ban.call_args_list] == [
        ("1.1.1.1", 7200, "waf", "", "global"),
        ("2.2.2.2", 600, "ui", "site.example.com", "service"),
    ]


# --------------------------------------------------------------------------------------
# unban
# --------------------------------------------------------------------------------------
def test_unban_explicit_selection_unbans_on_the_instances(h, bans):
    h.instances.unban.return_value = ""
    payload = [
        {"ip": "1.2.3.4"},
        {"ip": "5.6.7.8", "ban_scope": "service", "service": "Web UI"},
        {"ip": "bad"},
        {"ip": "7.7.7.7", "ban_scope": "service", "service": "s"},
    ]
    client = h.client()

    response = client.post("/bans/unban", data={"ips": json.dumps(payload)})

    assert "/loading" in response.headers["Location"]
    assert [call.args for call in h.instances.unban.call_args_list] == [("1.2.3.4", None, "global"), ("5.6.7.8", None, "global"), ("7.7.7.7", "s", "service")]
    assert "Invalid IP address: bad" in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({}, "No bans."),
        ({"ips": "{"}, "Invalid ips parameter on /bans/unban."),
        ({"selection_mode": "x"}, "Invalid unban selection mode."),
        ({"selection_mode": "filtered", "source": "reports"}, "Invalid filtered unban source."),
        ({"ips": "[]"}, "No matching bans."),
    ],
)
def test_unban_rejects_malformed_requests(h, bans, form, message):
    client = h.client()

    client.post("/bans/unban", data=form)

    h.instances.unban.assert_not_called()
    assert message in _flashed(h, client)


def test_unban_filtered_skips_crowdsec_leases(h, bans):
    h.instances.unban.return_value = ""
    h.instances.get_bans.return_value = [_ban("1.1.1.1"), _ban("2.2.2.2", kind="crowdsec_lease")]
    client = h.client()

    client.post("/bans/unban", data={"selection_mode": "filtered", "source": "bans"})

    assert [call.args[0] for call in h.instances.unban.call_args_list] == ["1.1.1.1"]
    assert "CrowdSec bans were skipped, unban them from their own row." in _flashed(h, client)


LEASE = {"ip": "1.2.3.4", "ban_scope": "global", "kind": "crowdsec_lease"}


def test_crowdsec_unban_is_refused_to_a_non_administrator(h, bans):
    bans.CrowdSecClient = MagicMock()
    client = h.client("viewer", admin=False)

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes"})

    bans.CrowdSecClient.assert_not_called()
    h.instances.unban.assert_not_called()
    assert "CrowdSec decision removal is restricted to administrators" in _flashed(h, client)


def test_crowdsec_unban_needs_write_permission_even_for_an_administrator(h, bans):
    bans.CrowdSecClient = MagicMock()
    client = h.client("ro-admin", admin=True, permissions=("read",))

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes"})

    bans.CrowdSecClient.assert_not_called()
    assert "CrowdSec decision removal is restricted to administrators" in _flashed(h, client)


def test_crowdsec_unban_needs_the_explicit_confirmation(h, bans):
    bans.CrowdSecClient = MagicMock()
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE])})

    bans.CrowdSecClient.assert_not_called()
    assert "Removing a CrowdSec ban needs an explicit confirmation" in _flashed(h, client)


def test_crowdsec_unban_applies_the_revalidated_preview(h, bans):
    bans.CrowdSecClient = MagicMock(return_value="client")
    bans.crowdsec_revalidate = MagicMock(return_value={"status": "ready", "preview": {"p": 1}})
    bans.crowdsec_apply = MagicMock(return_value={"status": "success"})
    client = h.client()

    response = client.post(
        "/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes", "crowdsec_selection": json.dumps({"1.2.3.4|global|_": ["k1"]})}
    )

    bans.crowdsec_revalidate.assert_called_once_with("client", "1.2.3.4", "global", None, ["k1"])
    bans.crowdsec_apply.assert_called_once_with("client", "1.2.3.4", "global", None, {"p": 1})
    assert "Removed the CrowdSec ban on 1.2.3.4." in _flashed(h, client)
    assert "message=Unbanning+1+IP" in response.headers["Location"]


def test_crowdsec_unban_stops_when_the_decisions_changed(h, bans):
    bans.CrowdSecClient = MagicMock()
    bans.crowdsec_revalidate = MagicMock(return_value={"status": "changed"})
    bans.crowdsec_apply = MagicMock()
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE, {"ip": "9.9.9.9"}]), "crowdsec_confirmed": "yes"})

    bans.crowdsec_apply.assert_not_called()
    h.instances.unban.assert_not_called()  # nothing is removed when any lease changed
    assert "The CrowdSec decisions changed, review the Unban again" in _flashed(h, client)


def test_crowdsec_unban_reports_an_incomplete_removal(h, bans):
    bans.CrowdSecClient = MagicMock()
    bans.crowdsec_revalidate = MagicMock(return_value={"status": "ready", "preview": {}})
    bans.crowdsec_apply = MagicMock(
        return_value={
            "status": "partial",
            "failed": [{"key": "k1", "error": "denied"}],
            "lease_failed": [{"instance": "bw-2", "error": "timeout"}],
            "unavailable": ["lapi"],
            "down": ["bw-3"],
            "lease_removed": True,
        }
    )
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes"})

    message = next(m for m in _flashed(h, client) if "incomplete" in m)
    for fragment in ("decision k1: denied", "lease on bw-2: timeout", "could not check lapi", "instances down: bw-3", "repeat the Unban"):
        assert fragment in message


@pytest.mark.parametrize("selection", ["[1]", json.dumps({"bad-key": []}), json.dumps({"1.2.3.4|global|_": "not-a-list"}), json.dumps({"x|global|_": []})])
def test_crowdsec_unban_rejects_a_malformed_selection(h, bans, selection):
    bans.CrowdSecClient = MagicMock()
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes", "crowdsec_selection": selection})

    bans.CrowdSecClient.assert_not_called()
    assert "Invalid CrowdSec ban selection on /bans/unban." in _flashed(h, client)


def test_crowdsec_unban_maps_client_errors_to_a_refusal(h, bans):
    bans.CrowdSecClient = MagicMock()
    bans.crowdsec_revalidate = MagicMock(side_effect=bans.CrowdSecError("LAPI said no", 403))
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes"})

    assert "CrowdSec Unban of 1.2.3.4 refused: LAPI said no" in _flashed(h, client)


def test_crowdsec_unban_survives_an_unexpected_error_in_apply(h, bans):
    bans.CrowdSecClient = MagicMock()
    bans.crowdsec_revalidate = MagicMock(return_value={"status": "ready", "preview": {}})
    bans.crowdsec_apply = MagicMock(side_effect=RuntimeError("boom"))
    client = h.client()

    client.post("/bans/unban", data={"ips": json.dumps([LEASE]), "crowdsec_confirmed": "yes"})

    assert any("failed unexpectedly" in message for message in _flashed(h, client))


# --------------------------------------------------------------------------------------
# crowdsec preview
# --------------------------------------------------------------------------------------
def test_crowdsec_preview_is_restricted_to_administrators(h, bans):
    bans.crowdsec_preview_data = MagicMock()

    response = h.client("viewer", admin=False).post("/bans/crowdsec_preview", json={"ip": "1.2.3.4"})

    assert response.status_code == 403
    bans.crowdsec_preview_data.assert_not_called()


def test_crowdsec_preview_in_read_only_mode_is_423(h, bans):
    h.db.readonly = True

    assert h.client().post("/bans/crowdsec_preview", json={"ip": "1.2.3.4"}).status_code == 423


@pytest.mark.parametrize("body", [None, ["list"], {"ip": 5}, {"ip": "nope"}, {"ip": "1.2.3.4", "ban_scope": "service"}, {"ip": "1.2.3.4", "service": 7}])
def test_crowdsec_preview_rejects_an_invalid_target(h, bans, body):
    bans.crowdsec_preview_data = MagicMock()

    response = h.client().post("/bans/crowdsec_preview", json=body) if body is not None else h.client().post("/bans/crowdsec_preview", data="x")

    assert response.status_code == 400
    bans.crowdsec_preview_data.assert_not_called()


def test_crowdsec_preview_returns_the_preview(h, bans):
    bans.CrowdSecClient = MagicMock(return_value="client")
    bans.crowdsec_preview_data = MagicMock(return_value={"decisions": []})

    response = h.client().post("/bans/crowdsec_preview", json={"ip": "1.2.3.4", "ban_scope": "service", "service": "site"})

    assert response.get_json() == {"decisions": []}
    bans.crowdsec_preview_data.assert_called_once_with("client", "1.2.3.4", "service", "site")


def test_crowdsec_preview_error_mapping(h, bans):
    bans.CrowdSecClient = MagicMock()
    bans.crowdsec_preview_data = MagicMock(side_effect=bans.CrowdSecError("nope", 404))
    assert h.client().post("/bans/crowdsec_preview", json={"ip": "1.2.3.4"}).status_code == 404

    bans.crowdsec_preview_data = MagicMock(side_effect=RuntimeError("secret detail"))
    response = h.client().post("/bans/crowdsec_preview", json={"ip": "1.2.3.4"})
    assert response.status_code == 500
    assert "secret detail" not in response.get_data(as_text=True)


# --------------------------------------------------------------------------------------
# update_duration
# --------------------------------------------------------------------------------------
def test_update_duration_translates_each_choice_and_keeps_the_original_reason(h, bans):
    h.instances.ban.return_value = ""
    h.instances.get_bans.return_value = [{"ip": "1.1.1.1", "reason": "waf", "service": "_"}]
    updates = [
        {"ip": "1.1.1.1", "duration": "1h"},
        {"ip": "2.2.2.2", "duration": "24h"},
        {"ip": "3.3.3.3", "duration": "1w"},
        {"ip": "4.4.4.4", "duration": "permanent"},
        {"ip": "5.5.5.5", "duration": "custom", "custom_exp": "-5"},
        {"ip": "6.6.6.6", "duration": "custom", "custom_exp": "90"},
    ]

    h.client().post("/bans/update_duration", data={"updates": json.dumps(updates)})

    assert [(call.args[0], call.args[1], call.args[2]) for call in h.instances.ban.call_args_list] == [
        ("1.1.1.1", 3600, "waf"),
        ("2.2.2.2", 86400, "ui"),
        ("3.3.3.3", 604800, "ui"),
        ("4.4.4.4", 0, "ui"),
        ("5.5.5.5", 0, "ui"),
        ("6.6.6.6", 90, "ui"),
    ]


def test_update_duration_custom_end_date(h, bans):
    h.instances.ban.return_value = ""
    future = datetime_in(3600)
    client = h.client()

    client.post(
        "/bans/update_duration",
        data={
            "updates": json.dumps(
                [
                    {"ip": "1.1.1.1", "duration": "custom", "end_date": future},
                    {"ip": "2.2.2.2", "duration": "custom", "end_date": "garbage"},
                    {"ip": "3.3.3.3", "duration": "custom"},
                    {"ip": "4.4.4.4", "duration": "custom", "custom_exp": "abc"},
                    {"ip": "5.5.5.5", "duration": "5y"},
                    {"ip": "bad", "duration": "1h"},
                ]
            )
        },
    )

    assert len(h.instances.ban.call_args_list) == 1
    assert 3500 < h.instances.ban.call_args_list[0].args[1] <= 3600
    flashed = _flashed(h, client)
    assert "Invalid custom ban end date for 2.2.2.2" in flashed
    assert "Missing custom ban end date for 3.3.3.3" in flashed
    assert "Invalid custom ban duration for 4.4.4.4" in flashed
    assert "Invalid ban duration: 5y" in flashed
    assert "Invalid IP address: bad" in flashed


def datetime_in(seconds):
    from datetime import datetime, timedelta

    return (datetime.now() + timedelta(seconds=seconds)).isoformat()


def test_update_duration_refuses_to_edit_a_crowdsec_lease(h, bans):
    client = h.client()

    client.post("/bans/update_duration", data={"updates": json.dumps([{"ip": "1.1.1.1", "duration": "1h", "kind": "crowdsec_lease"}])})

    h.instances.ban.assert_not_called()
    assert "CrowdSec bans follow their CrowdSec decision and cannot be edited" in _flashed(h, client)


@pytest.mark.parametrize(
    "form, message",
    [
        ({}, "No updates."),
        ({"updates": "{"}, "Invalid updates parameter on /bans/update_duration."),
        ({"selection_mode": "x"}, "Invalid duration selection mode."),
        ({"selection_mode": "filtered", "source": "reports"}, "Invalid filtered duration source."),
        ({"updates": "[]"}, "No matching bans."),
    ],
)
def test_update_duration_rejects_malformed_requests(h, bans, form, message):
    client = h.client()

    client.post("/bans/update_duration", data=form)

    h.instances.ban.assert_not_called()
    assert message in _flashed(h, client)


def test_update_duration_filtered_skips_leases_and_applies_the_form_duration(h, bans):
    h.instances.ban.return_value = ""
    h.instances.get_bans.return_value = [_ban("1.1.1.1"), _ban("2.2.2.2", kind="crowdsec_lease")]
    client = h.client()

    client.post("/bans/update_duration", data={"selection_mode": "filtered", "source": "bans", "duration": "1h"})

    assert [(c.args[0], c.args[1]) for c in h.instances.ban.call_args_list] == [("1.1.1.1", 3600)]
    assert "CrowdSec bans were skipped, they follow their CrowdSec decision." in _flashed(h, client)


def test_update_duration_in_read_only_mode_changes_nothing(h, bans):
    h.db.readonly = True

    h.client().post("/bans/update_duration", data={"updates": json.dumps([{"ip": "1.1.1.1", "duration": "1h"}])})

    h.instances.ban.assert_not_called()
