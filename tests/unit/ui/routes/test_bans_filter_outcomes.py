"""Ban table and CSV share boundary-correct filters; failed duration changes stay visible to operators."""

import csv
import io
import json
from unittest.mock import Mock

import pytest

NOW = 1_700_000_000
CORS = {"Sec-Fetch-Mode": "cors"}


@pytest.fixture
def ban_feed(h, monkeypatch):
    bans = h.routes.bans
    monkeypatch.setattr(bans, "time", lambda: NOW)
    monkeypatch.setattr(bans, "get_redis_client", lambda: None)
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com"}
    h.instances.get_bans.side_effect = lambda: [
        {
            "ip": f"192.0.2.{index}",
            "date": NOW - age,
            "exp": expiry,
            "permanent": expiry == 0,
            "reason": "scanner",
            "country": "FR" if index < 3 else "DE",
            "ban_scope": "service" if index in (2, 4) else "global",
            "service": "ui.example.com" if index in (2, 4) else "_",
        }
        for index, age, expiry in [(1, 86399, 86399), (2, 86400, 86400), (3, 604800, 604800), (4, 2592000, 2592000), (5, 60, 0)]
    ]
    return bans


@pytest.mark.parametrize("transport", ["table", "csv"])
@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("date", "last_24h", [1, 5]),
        ("date", "last_7d", [1, 2, 5]),
        ("date", "last_30d", [1, 2, 3, 5]),
        ("date", "older_30d", [4]),
        ("end_date", "next_24h", [1]),
        ("end_date", "next_7d", [1, 2]),
        ("end_date", "next_30d", [1, 2, 3]),
        ("end_date", "future_30d", [4, 5]),
        ("end_date", "permanent", [5]),
        ("service", "_", [1, 3, 5]),
        ("service", "ui.example.com", [2, 4]),
        ("country", "FR", [1, 2]),
    ],
)
def test_table_and_csv_filters_agree_at_date_and_expiry_boundaries(h, ban_feed, transport, field, value, expected):
    params = {f"searchPanes[{field}][0]": value}
    client = h.client()
    if transport == "table":
        response = client.post("/bans/fetch", data=params | {"length": "100"}, headers=CORS)
        assert response.status_code == 200
        body = response.get_json()
        ips = [row["ip"] for row in body["data"]]
        assert body["recordsTotal"] == 5 and body["recordsFiltered"] == len(expected)
        option = next(item for item in body["searchPanes"]["options"][field] if item["value"] == value)
        assert option["total"] == option["count"] == len(expected)
    else:
        response = client.get("/bans/export/csv", query_string=params)
        assert response.status_code == 200 and response.mimetype == "text/csv"
        ips = [row["IP Address"] for row in csv.DictReader(io.StringIO(response.data.decode("utf-8-sig")))]
    assert set(ips) == {f"192.0.2.{index}" for index in expected}


@pytest.mark.parametrize(
    "column,direction",
    [
        ("end_date", "asc"),
        ("time_left", "asc"),
        ("end_date", "desc"),
        ("time_left", "desc"),
    ],
)
def test_csv_duration_sort_keeps_permanent_ban_last(h, ban_feed, column, direction):
    response = h.client().get("/bans/export/csv", query_string={"order_column": column, "order_dir": direction})
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 5 and rows[-1]["IP Address"] == "192.0.2.5"


def test_permanent_search_and_invalid_order_fall_back_to_valid_csv(h, ban_feed):
    response = h.client().get("/bans/export/csv?search=permanent&order_column=missing&order_dir=invalid")
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert [row["IP Address"] for row in rows] == ["192.0.2.5"]
    assert rows[0]["End Date"] == rows[0]["Time Left"] == "permanent"


def test_table_invalid_sort_and_negative_page_start_keep_first_row(h, ban_feed):
    response = h.client().post("/bans/fetch", headers=CORS, data={"order[0][column]": "invalid", "start": "-9", "length": "0"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["recordsTotal"] == 5
    assert [row["ip"] for row in body["data"]] == ["192.0.2.5"]


def test_empty_redis_keys_are_skipped_and_legacy_service_reason_survives(h, ban_feed, monkeypatch):
    redis = h.FakeRedis(
        {b"bans_ip_192.0.2.9": None, b"bans_service_site_ip_192.0.2.8": b"legacy reason", b"bans_service_site_ip_192.0.2.7": None},
        {b"bans_service_site_ip_192.0.2.8": 0},
    )
    monkeypatch.setattr(ban_feed, "get_redis_client", lambda: redis)
    h.instances.get_bans.side_effect = None
    h.instances.get_bans.return_value = []
    response = h.client().post("/bans/fetch", headers=CORS)
    assert response.status_code == 200
    (row,) = response.get_json()["data"]
    assert (row["ip"], row["reason"], row["scope"], row["service"], row["time_left"]) == ("192.0.2.8", "legacy reason", "service", "site", "permanent")


@pytest.mark.parametrize("end_date,message", [("bad date", "Invalid custom ban end date for 192.0.2.1"), (None, "Missing custom ban end date for 192.0.2.1")])
def test_bad_custom_end_date_flashes_error_without_updating_instances(h, ban_feed, end_date, message):
    client = h.client()
    response = client.post("/bans/update_duration", data={"updates": json.dumps([{"ip": "192.0.2.1", "duration": "custom", "end_date": end_date}])})
    assert response.status_code == 302 and "/loading?next=/bans&" in response.headers["Location"]
    h.instances.ban.assert_not_called()
    assert (message, "error") in h.flashes(client)


def test_duration_update_surfaces_instance_failure_and_retains_original_reason(h, ban_feed):
    h.instances.ban.return_value = "worker unavailable"
    client = h.client()
    response = client.post("/bans/update_duration", data={"updates": json.dumps([{"ip": "192.0.2.1", "duration": "1h"}])})
    assert response.status_code == 302 and "/loading?next=/bans&" in response.headers["Location"]
    h.instances.ban.assert_called_once_with("192.0.2.1", 3600, "scanner", "", "global")
    assert ("Failed to update ban duration for 192.0.2.1 on some instances: worker unavailable", "error") in h.flashes(client)


def test_crowdsec_revalidation_exception_preserves_every_selected_ban(h, ban_feed, monkeypatch):
    monkeypatch.setattr(ban_feed, "CrowdSecClient", Mock())
    apply = Mock()
    monkeypatch.setattr(ban_feed, "crowdsec_apply", apply)
    monkeypatch.setattr(ban_feed, "crowdsec_revalidate", Mock(side_effect=RuntimeError("offline")))
    client = h.client()
    response = client.post(
        "/bans/unban", data={"ips": json.dumps([{"ip": "192.0.2.1"}, {"ip": "192.0.2.2", "kind": "crowdsec_lease"}]), "crowdsec_confirmed": "yes"}
    )
    assert response.status_code == 302 and response.headers["Location"].endswith("/bans")
    h.instances.unban.assert_not_called()
    apply.assert_not_called()
    assert ("Unable to check the CrowdSec ban of 192.0.2.2, see logs for more information.", "error") in h.flashes(client)


@pytest.mark.parametrize("transport", ["table", "csv"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_time_left_sort_orders_finite_bans_numerically(h, ban_feed, transport, direction):
    feed = h.instances.get_bans.side_effect()
    h.instances.get_bans.side_effect = lambda: [dict(feed[index]) for index in (3, 1, 0, 2, 4)]
    client = h.client()
    if transport == "table":
        response = client.post("/bans/fetch", headers=CORS, data={"order[0][column]": "9", "order[0][dir]": direction, "length": "100"})
        assert response.status_code == 200
        ips = [row["ip"] for row in response.get_json()["data"]]
    else:
        response = client.get("/bans/export/csv", query_string={"order_column": "time_left", "order_dir": direction})
        assert response.status_code == 200
        ips = [row["IP Address"] for row in csv.DictReader(io.StringIO(response.data.decode("utf-8-sig")))]
    expected = [1, 2, 3, 4] if direction == "asc" else [4, 3, 2, 1]
    assert ips == [f"192.0.2.{index}" for index in expected + [5]]
