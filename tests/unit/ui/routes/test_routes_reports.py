"""The /reports blueprint: the DataTables feed, the SearchPanes cache, lazy report data and the exports."""

import csv
import io

import pytest

CORS = {"Sec-Fetch-Mode": "cors"}
REPORT = {
    "id": "req-1",
    "date": 1_700_000_000,
    "ip": "1.2.3.4",
    "country": "FR",
    "method": "GET",
    "url": "/a?b=<x>",
    "status": 403,
    "user_agent": "curl",
    "reason": "waf",
    "server_name": "a.example.com",
    "data": {},
    "security_mode": "block",
}


@pytest.fixture
def reports(h):
    module = h.routes.reports
    module.REPORTS_FILTERS_CACHE.clear()
    h.config.get_config.return_value = {"BAD_BEHAVIOR_BAN_TIME": "2h"}
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [REPORT], "pane_counts": {}}
    return module


def test_reports_page_renders(h, reports):
    assert h.client().get("/reports").status_code == 200
    assert h.renders[-1][0] == "reports.html"


@pytest.mark.parametrize("path", ["/reports/fetch", "/reports/filters", "/reports/data"])
def test_the_json_endpoints_refuse_a_request_that_is_neither_cors_nor_ajax(h, reports, path):
    assert h.client().post(path).status_code == 403
    h.instances.get_reports_query.assert_not_called()


def test_fetch_maps_the_datatables_request_onto_the_query(h, reports):
    form = {
        "draw": "4",
        "start": "20",
        "length": "5000",
        "search[value]": "WAF",
        "order[0][column]": "4",
        "order[0][dir]": "asc",
        "searchPanes[country][0]": "FR",
        "searchPanes[country][1]": "DE",
    }

    body = h.client().post("/reports/fetch", headers=CORS, data=form).get_json()

    kwargs = h.instances.get_reports_query.call_args.kwargs
    assert (kwargs["start"], kwargs["length"], kwargs["search"], kwargs["order_column"], kwargs["order_dir"]) == (20, 1000, "waf", "ip", "asc")
    assert "country:FR,DE" in kwargs["search_panes"] and kwargs["include_pane_counts"] is False
    assert (body["draw"], body["recordsTotal"], body["recordsFiltered"]) == (4, 1, 1)


def test_fetch_escapes_every_report_field_and_adds_the_default_ban_time(h, reports):
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [REPORT | {"reason": "<script>", "user_agent": "<b>ua</b>"}]}

    row = h.client().post("/reports/fetch", headers=CORS).get_json()["data"][0]

    assert row["reason"] == "&lt;script&gt;" and row["user_agent"] == "&lt;b&gt;ua&lt;/b&gt;"
    assert row["url"] == "/a?b=&lt;x&gt;" and row["ban_default_exp"] == 7200
    assert row["date"].startswith("2023-11-1") and row["request_id"] == "req-1"


@pytest.mark.parametrize(
    "data, expected_flag, expected_data",
    [
        ({}, False, ""),
        ({"k": 1}, True, "available"),
        ([1], True, "available"),
        ([], False, ""),
        ("  ", False, ""),
        ("{}", False, ""),
        ('{"a": 1}', True, "available"),
        (5, True, "available"),
        (None, False, ""),
        ({"ban_id": "b1", "counter": 3, "secret": "x"}, True, {"ban_id": "b1", "counter": 3}),
    ],
)
def test_fetch_summarizes_the_report_data_field(h, reports, data, expected_flag, expected_data):
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [REPORT | {"data": data}]}

    row = h.client().post("/reports/fetch", headers=CORS).get_json()["data"][0]

    assert row["has_data"] is expected_flag and row["data"] == expected_data


def test_a_report_that_cannot_be_formatted_becomes_a_safe_placeholder(h, reports):
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [{"ip": "9.9.9.9", "date": "not-a-number"}]}

    row = h.client().post("/reports/fetch", headers=CORS).get_json()["data"][0]

    assert row["ip"] == "9.9.9.9" and row["reason"] == "Error parsing report data" and row["ban_default_exp"] == 86400


def test_fetch_survives_a_failing_query_and_a_failing_config(h, reports):
    h.instances.get_reports_query.side_effect = RuntimeError("boom")
    h.config.get_config.side_effect = RuntimeError("config boom")

    body = h.client().post("/reports/fetch", headers=CORS).get_json()

    assert body["data"] == [] and body["recordsTotal"] == 0


# --------------------------------------------------------------------------------------
# filters
# --------------------------------------------------------------------------------------
PANES = {
    "country": {"FR": {"total": 3, "count": 2}, "unknown": {"total": 1, "count": 1}},
    "server_name": {"_": {"total": 4, "count": 3}, "a<b": {"total": 1, "count": 0}},
    "status": {403: {"total": 5, "count": 5}},
}


def test_filters_build_labelled_options_for_each_pane(h, reports):
    h.instances.get_reports_query.return_value = {"pane_counts": PANES}

    options = h.client().post("/reports/filters", headers=CORS).get_json()["searchPanes"]["options"]

    country = {option["value"]: option for option in options["country"]}
    assert "flags/fr.svg" in country["FR"]["label"] and "flags/zz.svg" in country["unknown"]["label"]
    assert (country["FR"]["total"], country["FR"]["count"]) == (3, 2)
    names = {option["value"]: option["label"] for option in options["server_name"]}
    assert "default server" in names["_"] and "a&lt;b" in names["a<b"]
    assert options["status"] == [{"label": "403", "value": "403", "total": 5, "count": 5}]


def test_filters_are_cached_for_a_few_seconds_unless_forced(h, reports):
    h.instances.get_reports_query.return_value = {"pane_counts": PANES}
    client = h.client()

    client.post("/reports/filters", headers=CORS)
    client.post("/reports/filters", headers=CORS)
    assert h.instances.get_reports_query.call_count == 1

    client.post("/reports/filters", headers=CORS, data={"force": "yes"})
    assert h.instances.get_reports_query.call_count == 2


def test_active_panes_always_recompute_the_counts(h, reports):
    h.instances.get_reports_query.return_value = {"pane_counts": PANES}
    client = h.client()

    client.post("/reports/filters", headers=CORS, data={"searchPanes[country][0]": "FR"})
    client.post("/reports/filters", headers=CORS, data={"searchPanes[country][0]": "FR"})

    assert h.instances.get_reports_query.call_count == 2


def test_empty_pane_counts_retry_through_the_slow_path_and_are_not_cached(h, reports):
    h.instances.get_reports_query.side_effect = [{"pane_counts": {}}, {"pane_counts": PANES}]
    client = h.client()

    body = client.post("/reports/filters", headers=CORS).get_json()

    assert [call.kwargs["count_only"] for call in h.instances.get_reports_query.call_args_list] == [True, False]
    assert body["searchPanes"]["options"]["status"]

    h.instances.get_reports_query.side_effect = [{"pane_counts": {}}, {"pane_counts": {}}]
    reports.REPORTS_FILTERS_CACHE.clear()
    client.post("/reports/filters", headers=CORS)
    assert reports.REPORTS_FILTERS_CACHE == {}


def test_filters_survive_a_failing_query(h, reports):
    h.instances.get_reports_query.side_effect = RuntimeError("boom")

    assert h.client().post("/reports/filters", headers=CORS).get_json() == {"searchPanes": {"options": {}}}


def test_the_filters_cache_drops_expired_entries_and_bounds_its_size(h, reports, monkeypatch):
    monkeypatch.setattr(reports, "REPORTS_FILTERS_CACHE_MAX_ENTRIES", 3)
    reports.REPORTS_FILTERS_CACHE.update({f"k{n}": {"expires_at": 100.0 + n, "created_at": float(n)} for n in range(6)})
    reports.REPORTS_FILTERS_CACHE["expired"] = {"expires_at": 1.0, "created_at": 0.0}

    reports.prune_reports_filters_cache(50.0)

    assert "expired" not in reports.REPORTS_FILTERS_CACHE
    assert sorted(reports.REPORTS_FILTERS_CACHE) == ["k3", "k4", "k5"], "the oldest entries go first"


def test_pane_counts_has_values(reports):
    assert reports.pane_counts_has_values({"a": {"x": 1}}) is True
    assert reports.pane_counts_has_values({"a": {}}) is False
    assert reports.pane_counts_has_values([]) is False


# --------------------------------------------------------------------------------------
# lazy data
# --------------------------------------------------------------------------------------
def test_report_data_is_loaded_by_request_id(h, reports):
    h.instances.get_report_data.return_value = {"rule": "942100"}

    body = h.client().post("/reports/data", headers=CORS, data={"report_id": " req-1 ", "hostname": "bw-1"}).get_json()

    h.instances.get_report_data.assert_called_once_with(report_id="req-1", hostname="bw-1")
    assert body == {"status": "success", "report_id": "req-1", "data": {"rule": "942100"}}


@pytest.mark.parametrize(
    "form, result, status",
    [({}, None, 400), ({"report_id": "x"}, None, 404)],
)
def test_report_data_refusals(h, reports, form, result, status):
    h.instances.get_report_data.return_value = result

    assert h.client().post("/reports/data", headers=CORS, data=form).status_code == status


def test_report_data_failure_does_not_leak_the_exception(h, reports):
    h.instances.get_report_data.side_effect = RuntimeError("internal path /srv")

    response = h.client().post("/reports/data", headers=CORS, data={"report_id": "x"})

    assert response.status_code == 500 and "/srv" not in response.get_data(as_text=True)


# --------------------------------------------------------------------------------------
# exports
# --------------------------------------------------------------------------------------
def test_csv_export_lists_every_report_and_neutralizes_formulas(h, reports):
    h.instances.get_reports_query.return_value = {
        "data": [REPORT | {"reason": "=cmd|' /C calc'!A0", "data": '{"a": 1}'}, REPORT | {"id": "req-2", "data": "not json"}]
    }

    response = h.client().get("/reports/export/csv?search=Waf&order_column=ip&order_dir=asc&searchPanes[country][0]=FR")

    kwargs = h.instances.get_reports_query.call_args.kwargs
    assert kwargs["length"] == -1 and kwargs["search"] == "waf" and kwargs["order_column"] == "ip" and "country:FR" in kwargs["search_panes"]
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows[0][:3] == ["Date", "Request ID", "IP Address"]
    assert not rows[1][8].startswith("="), "a spreadsheet would execute this cell"
    assert rows[1][10] == '{"a": 1}' and rows[2][10] == "not json" and len(rows) == 3
    assert response.headers["Content-Disposition"].startswith("attachment; filename=bunkerweb_reports_")


def test_excel_export_is_a_workbook(h, reports):
    openpyxl = pytest.importorskip("openpyxl")
    h.instances.get_reports_query.return_value = {"data": [REPORT, REPORT | {"id": "req-2", "ip": "5.6.7.8"}]}

    response = h.client().get("/reports/export/excel")

    sheet = openpyxl.load_workbook(io.BytesIO(response.get_data())).active
    values = [[cell.value for cell in row] for row in sheet.iter_rows()]
    assert sheet.title == "Reports" and values[0][1] == "Request ID"
    assert [row[2] for row in values[1:]] == ["1.2.3.4", "5.6.7.8"]


@pytest.mark.parametrize("path", ["/reports/export/csv", "/reports/export/excel"])
def test_export_failures_are_a_json_500(h, reports, path):
    h.instances.get_reports_query.side_effect = RuntimeError("boom")

    response = h.client().get(path)

    assert response.status_code == 500 and response.get_json() == {"error": "Failed to export reports"}
