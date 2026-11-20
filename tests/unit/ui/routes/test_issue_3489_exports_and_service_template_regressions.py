"""UI route regressions around Reports, Bans, exports and service templates.

* #3489: the Bans export ignored the SearchPanes selection and returned every ban.
* #4013: a Reports filter value holding ``,`` ``;`` ``&`` ``<`` ``>`` was split or mangled on its way to the query.
* #2119: a report with missing fields made the Reports feed fail instead of showing ``N/A``.
* #3551: the service and config exports skipped configs supplied by a template and kept their hyphenated type.
* #3241: switching a service to another template carried the old template's defaults forward instead of the new ones.
"""

import csv
import io
import json
import zipfile
from time import time
from urllib.parse import quote

import pytest

CORS = {"Sec-Fetch-Mode": "cors"}
NOW = int(time())
AWKWARD = "/a,b;c&d<e>"
REPORT = {
    "id": "req-1",
    "date": 1_700_000_000,
    "ip": "1.2.3.4",
    "country": "FR",
    "method": "GET",
    "url": "/a",
    "status": 403,
    "user_agent": "curl",
    "reason": "waf",
    "server_name": "a.example.com",
    "data": {},
    "security_mode": "block",
}


def _ban(ip, **extra):
    return {"ip": ip, "exp": 3600, "reason": "bad", "date": NOW - 60, "country": "FR", "service": "_", "ban_scope": "global", "permanent": False} | extra


@pytest.fixture
def bans(h):
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com"}
    h.instances.get_bans.return_value = []
    h.routes.bans.get_redis_client = lambda: None
    return h.routes.bans


@pytest.fixture
def reports(h):
    module = h.routes.reports
    module.REPORTS_FILTERS_CACHE.clear()
    h.config.get_config.return_value = {"BAD_BEHAVIOR_BAN_TIME": "2h"}
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [REPORT], "pane_counts": {}}
    return module


def test_issue_3489_bans_csv_export_honours_the_searchpanes_selection(h, bans):
    """Only the bans of the selected country are exported, not the whole list (#3489)."""
    h.instances.get_bans.return_value = [_ban("1.1.1.1", country="FR"), _ban("2.2.2.2", country="US"), _ban("3.3.3.3", country="FR")]

    response = h.client().get("/bans/export/csv?order_column=ip&order_dir=asc&searchPanes[country][0]=FR")

    ips = [row[1] for row in list(csv.reader(io.StringIO(response.get_data(as_text=True))))[1:]]
    assert ips == ["1.1.1.1", "3.3.3.3"]


def test_issue_3489_bans_excel_export_honours_the_searchpanes_selection(h, bans):
    """The workbook holds only the bans of the selected scope (#3489)."""
    openpyxl = pytest.importorskip("openpyxl")
    h.instances.get_bans.return_value = [_ban("1.1.1.1"), _ban("2.2.2.2", ban_scope="service", service="svc")]

    response = h.client().get("/bans/export/excel?searchPanes[scope][0]=service")

    sheet = openpyxl.load_workbook(io.BytesIO(response.get_data())).active
    assert [row[1].value for row in list(sheet.iter_rows())[1:]] == ["2.2.2.2"]


def test_issue_4013_reports_filter_values_reach_the_query_percent_encoded(h, reports):
    """The value of a pane selection is percent-encoded so ``,`` and ``;`` inside it cannot split it (#4013)."""
    h.client().post("/reports/fetch", headers=CORS, data={"searchPanes[url][0]": AWKWARD, "searchPanes[country][0]": "FR"})

    panes = h.instances.get_reports_query.call_args.kwargs["search_panes"]
    assert "url:" + quote(AWKWARD, safe="") in panes.split(";")
    assert "country:FR" in panes.split(";")
    assert AWKWARD not in panes


def test_issue_2119_a_report_with_missing_fields_is_listed_with_na_defaults(h, reports):
    """A report holding only an id gets ``N/A`` in every other column instead of the error placeholder (#2119)."""
    h.instances.get_reports_query.return_value = {"total": 1, "filtered": 1, "data": [{"id": "only-id"}]}

    row = h.client().post("/reports/fetch", headers=CORS).get_json()["data"][0]

    assert row["request_id"] == "only-id"
    assert (row["ip"], row["country"], row["method"], row["url"], row["status"], row["date"]) == ("N/A",) * 6
    assert row["reason"] == "N/A" and row["server_name"] == "N/A" and row["security_mode"] == "N/A"
    assert row["has_data"] is False


# --------------------------------------------------------------------------------------
# exports of template-supplied custom configs (#3551)
# --------------------------------------------------------------------------------------
TEMPLATE_CONFIG = {
    "service_id": "a.example.com",
    "type": "modsec-crs",
    "name": "tuned",
    "data": b"SecRuleRemoveById 949110",
    "template": "low",
    "method": "default",
}


def test_issue_3551_service_export_includes_template_supplied_configs(h):
    """A ModSecurity config that comes from the service's template is exported, with an underscore type (#3551)."""
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com", "a.example.com_USE_TEMPLATE": "low"}
    h.db.get_custom_configs.return_value = [
        TEMPLATE_CONFIG,
        {"service_id": "a.example.com", "type": "server-http", "name": "own", "data": b"x", "method": "ui"},
    ]

    response = h.client().get("/services/export?services=a.example.com&include_configs=yes")

    configs = json.loads(zipfile.ZipFile(io.BytesIO(response.get_data())).read("configs_export.json"))["configs"]
    assert {(item["type"], item["name"]) for item in configs} == {("modsec_crs", "tuned"), ("server_http", "own")}


def test_issue_3551_config_export_includes_template_supplied_configs_and_selects_them_by_type(h):
    """The config export lists a template-supplied config and a selection written with either separator finds it (#3551)."""
    h.config.get_config.return_value = {"SERVER_NAME": "a.example.com"}
    h.db.get_custom_configs.return_value = [TEMPLATE_CONFIG, TEMPLATE_CONFIG | {"name": "other"}]

    everything = h.client().get("/configs/export")
    selected = h.client().get("/configs/export", query_string={"configs": json.dumps([{"name": "tuned", "type": "modsec-crs", "service": "a.example.com"}])})

    assert [(item["type"], item["name"]) for item in json.loads(everything.get_data())["configs"]] == [("modsec_crs", "tuned"), ("modsec_crs", "other")]
    assert [item["name"] for item in json.loads(selected.get_data())["configs"]] == ["tuned"]


# --------------------------------------------------------------------------------------
# template switch (#3241)
# --------------------------------------------------------------------------------------
@pytest.fixture
def editing(h):
    h.db.get_services.return_value = [{"id": "ui.example.com", "method": "ui", "is_draft": False}]
    h.db.get_custom_configs.return_value = {}
    h.db.save_custom_configs.return_value = ""
    h.db.get_templates.return_value = {}
    h.config.get_config.return_value = {"SERVER_NAME": "ui.example.com"}
    state = {
        "service": {
            "SERVER_NAME": {"value": "ui.example.com", "method": "ui", "global": False},
            "IS_DRAFT": {"value": "no", "method": "ui", "global": False},
            "USE_TEMPLATE": {"value": "low", "method": "ui", "global": False},
            "USE_X": {"value": "no", "method": "default", "template": "low", "global": False},
            "USE_Y": {"value": "no", "method": "ui", "global": False},
        },
        "global": {"SERVER_NAME": {"value": "", "method": "default", "global": True}},
    }

    def get_config(**kwargs):
        if kwargs.get("with_setting_drafts"):
            return {}
        return state["service"] if kwargs.get("service") else state["global"]

    h.db.get_config.side_effect = get_config
    h.config.check_variables.side_effect = lambda variables, *a, **kw: dict(variables)
    h.config.edit_service.return_value = ("", False)
    h.config.get_plugins_settings.return_value = {}
    return h


def _save(h, **form):
    data = {"csrf_token": "t", "SERVER_NAME": "ui.example.com", "OLD_SERVER_NAME": "ui.example.com", "USE_Y": "no"} | form
    return h.client().post("/services/ui.example.com?mode=advanced", data=data)


def test_issue_3241_switching_template_does_not_carry_the_old_template_defaults_forward(editing):
    """The old template's value for a setting the new template defines is left out so the new default applies (#3241)."""
    h = editing

    _save(h, USE_TEMPLATE="high")

    _, variables = h.config.edit_service.call_args.args
    assert variables["USE_TEMPLATE"] == "high"
    assert "USE_X" not in variables, "the low template's default was saved as if it were the high template's"


def test_issue_3241_keeping_the_template_still_carries_its_defaults(editing):
    """Without a template switch the stored template default stays in the saved variables (#3241)."""
    h = editing

    _save(h, USE_TEMPLATE="low", USE_Y="yes")

    _, variables = h.config.edit_service.call_args.args
    assert variables["USE_X"] == "no" and variables["USE_Y"] == "yes"
