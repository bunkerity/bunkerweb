"""The /crowdsec JSON endpoints, /jobs and /cache."""

import json
from unittest.mock import MagicMock

import pytest

CS_ERROR = None


@pytest.fixture
def cs(h, monkeypatch):
    module = h.routes.crowdsec
    monkeypatch.setattr(module, "CrowdSecClient", MagicMock())
    h.client_obj = module.CrowdSecClient.return_value
    return module


def _flashed(h, client):
    return [message for message, _category in h.flashes(client)]


# --------------------------------------------------------------------------------------
# crowdsec
# --------------------------------------------------------------------------------------
def test_crowdsec_page_renders(h, cs):
    assert h.client().get("/crowdsec").status_code == 200
    assert h.renders[-1][0] == "crowdsec.html"


def test_connections_returns_the_client_payload(h, cs):
    h.client_obj.connections.return_value = {"connections": [{"id": "c"}]}

    assert h.client().get("/crowdsec/connections").get_json() == {"connections": [{"id": "c"}]}


def test_a_client_error_keeps_its_status_and_message(h, cs):
    h.client_obj.connections.side_effect = cs.CrowdSecError("LAPI unreachable", 502)

    response = h.client().get("/crowdsec/connections")

    assert response.status_code == 502 and response.get_json() == {"error": "LAPI unreachable"}


def test_an_unexpected_error_does_not_leak_its_message(h, cs):
    h.client_obj.connections.side_effect = RuntimeError("password=hunter2")

    response = h.client().get("/crowdsec/connections")

    assert response.status_code == 500
    assert "hunter2" not in response.get_data(as_text=True)


def test_decisions_normalizes_the_ip_and_forwards_bounded_paging(h, cs):
    h.client_obj.query.return_value = {"decisions": []}

    h.client().get("/crowdsec/decisions?connection=c1&ip=2001:0db8::1&origin=cscli&scenario=s&offset=5&limit=100")

    h.client_obj.query.assert_called_once_with("c1", "decisions", {"ip": "2001:db8::1", "origin": "cscli", "scenario": "s", "offset": 5, "limit": 100})


@pytest.mark.parametrize("query", ["ip=nope", "limit=0", "limit=201", "offset=-1", "limit=abc", "origin=" + "x" * 513, "scenario=" + "y" * 513])
def test_decisions_rejects_bad_filters_before_querying(h, cs, query):
    response = h.client().get(f"/crowdsec/decisions?{query}")

    assert response.status_code == 400
    h.client_obj.query.assert_not_called()


def test_investigate_and_allowlists_and_alerts(h, cs):
    client = h.client()
    h.client_obj.investigate.return_value = {"ip": "1.2.3.4"}
    h.client_obj.query.return_value = {"ok": True}

    assert client.get("/crowdsec/investigate?connection=c&ip=1.2.3.4").get_json() == {"ip": "1.2.3.4"}
    h.client_obj.investigate.assert_called_once_with("c", "1.2.3.4")
    assert client.get("/crowdsec/allowlists?connection=c&limit=10").get_json() == {"ok": True}
    h.client_obj.query.assert_called_with("c", "allowlists", {"offset": 0, "limit": 10})
    assert client.get("/crowdsec/allowlists?limit=999").status_code == 400
    assert client.get("/crowdsec/alerts/42?connection=c").get_json() == {"ok": True}
    h.client_obj.query.assert_called_with("c", "alerts", {"alert_id": 42})


@pytest.mark.parametrize("alert_id", [0, 9007199254740992])
def test_alert_id_out_of_range_is_refused(h, cs, alert_id):
    response = h.client().get(f"/crowdsec/alerts/{alert_id}")

    assert response.status_code == 400
    h.client_obj.query.assert_not_called()


UNBAN_FORM = {"connection": "c1", "value": "1.2.3.4", "decision_id": "7", "scope": "ip", "decision_type": "ban", "confirmed": "yes"}


def test_unban_is_restricted_to_administrators(h, cs):
    response = h.client("viewer", admin=False).post("/crowdsec/unban", data=UNBAN_FORM)

    assert response.status_code == 403
    cs.CrowdSecClient.assert_not_called()


def test_unban_needs_the_write_permission(h, cs):
    response = h.client("ro", admin=True, permissions=("read",)).post("/crowdsec/unban", data=UNBAN_FORM)

    assert response.status_code == 403
    cs.CrowdSecClient.assert_not_called()


def test_unban_in_read_only_mode(h, cs):
    h.db.readonly = True

    assert h.client().post("/crowdsec/unban", data=UNBAN_FORM).status_code == 403
    cs.CrowdSecClient.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"confirmed": "no"},
        {"decision_id": "abc"},
        {"decision_id": "0"},
        {"decision_id": "9007199254740992"},
        {"scope": "country"},
        {"decision_type": ""},
        {"decision_type": "x" * 65},
        {"value": "not-an-ip"},
        {"value": "1.2.3.4/99"},
    ],
)
def test_unban_validates_the_request_before_calling_crowdsec(h, cs, change):
    response = h.client().post("/crowdsec/unban", data=UNBAN_FORM | change)

    assert response.status_code == 400
    cs.CrowdSecClient.assert_not_called()


def test_unban_removes_the_decision(h, cs):
    h.client_obj.connections.return_value = {"connections": [{"id": "c1", "management_configured": True}]}
    h.client_obj.query.return_value = {"removed": 1}

    response = h.client().post("/crowdsec/unban", data=UNBAN_FORM | {"value": "10.0.0.0/24", "scope": "Range"})

    assert response.get_json() == {"removed": 1}
    h.client_obj.query.assert_called_once_with("c1", "unban", {"decision_id": 7, "scope": "Range", "value": "10.0.0.0/24", "decision_type": "ban"})


@pytest.mark.parametrize(
    "connections, status",
    [([], 404), ([{"id": "c1", "management_configured": False}], 403)],
)
def test_unban_refuses_a_missing_or_unconfigured_connection(h, cs, connections, status):
    h.client_obj.connections.return_value = {"connections": connections}

    response = h.client().post("/crowdsec/unban", data=UNBAN_FORM)

    assert response.status_code == status
    h.client_obj.query.assert_not_called()


def test_unban_error_mapping(h, cs):
    h.client_obj.connections.return_value = {"connections": [{"id": "c1", "management_configured": True}]}
    h.client_obj.query.side_effect = cs.CrowdSecError("denied", 403)
    assert h.client().post("/crowdsec/unban", data=UNBAN_FORM).get_json() == {"error": "denied"}

    h.client_obj.query.side_effect = RuntimeError("secret")
    response = h.client().post("/crowdsec/unban", data=UNBAN_FORM)
    assert response.status_code == 500 and "secret" not in response.get_data(as_text=True)


# --------------------------------------------------------------------------------------
# jobs
# --------------------------------------------------------------------------------------
def test_jobs_page_lists_the_jobs(h):
    h.db.get_jobs.return_value = {"job": {}}

    h.client().get("/jobs")

    assert h.renders[-1] == ("jobs.html", {"jobs": {"job": {}}})


def test_jobs_run_marks_the_plugins_of_the_selected_jobs_as_changed(h):
    h.db.checked_changes.return_value = ""
    client = h.client()

    response = client.post("/jobs/run", data={"jobs": json.dumps([{"plugin": "letsencrypt", "name": "renew"}, {"plugin": "blacklist", "name": "download"}])})

    h.db.checked_changes.assert_called_once_with(["config"], ["letsencrypt", "blacklist"], True)
    assert "will be run in the background by the scheduler" in _flashed(h, client)[0]
    assert "message=Run+selected+jobs's+plugins:+letsencrypt/renew,+blacklist/download" in response.headers["Location"]


def test_jobs_run_tolerates_an_entry_without_a_plugin(h):
    h.db.checked_changes.return_value = ""

    response = h.client().post("/jobs/run", data={"jobs": json.dumps([{"plugin": "p", "name": "n"}, {"name": "orphan"}])})

    assert response.status_code == 302


@pytest.mark.parametrize("form, message", [({"jobs": ""}, "No jobs selected."), ({"jobs": "{"}, "Invalid jobs parameter on /jobs/run.")])
def test_jobs_run_rejects_a_bad_selection(h, form, message):
    client = h.client()

    client.post("/jobs/run", data=form)

    h.db.checked_changes.assert_not_called()
    assert message in _flashed(h, client)


def test_jobs_run_reports_a_database_error(h):
    h.db.checked_changes.return_value = "locked"
    client = h.client()

    client.post("/jobs/run", data={"jobs": json.dumps([{"plugin": "p", "name": "n"}])})

    assert "locked" in _flashed(h, client)


def test_jobs_run_in_read_only_mode(h):
    h.db.readonly = True

    h.client().post("/jobs/run", data={"jobs": json.dumps([{"plugin": "p", "name": "n"}])})

    h.db.checked_changes.assert_not_called()


# --------------------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------------------
def test_cache_page_passes_filters_and_services(h):
    h.db.get_jobs_cache_files.return_value = [{"file": 1}]
    h.config.get_config.return_value = {"SERVER_NAME": "a b"}

    h.client().get("/cache?service=a&plugin=p&job_name=j")

    template, context = h.renders[-1]
    assert template == "cache.html"
    assert (context["caches"], context["services"], context["cache_service"], context["cache_plugin"], context["cache_job_name"]) == (
        [{"file": 1}],
        "a b",
        "a",
        "p",
        "j",
    )


def test_cache_view_sanitizes_the_file_name_and_maps_global_to_no_service(h):
    h.db.get_job_cache_file.return_value = b"hello"

    h.client().get("/cache/global/plugin/job/..%20etc%20passwd%00.txt")

    args, kwargs = h.db.get_job_cache_file.call_args
    assert args == ("job", "etc_passwd.txt") and kwargs == {"service_id": None, "plugin_id": "plugin"}


def test_cache_view_folder_names_use_slashes(h):
    h.db.get_job_cache_file.return_value = b"x"

    h.client().get("/cache/svc/plugin/job/folder:a_b_c")

    assert h.db.get_job_cache_file.call_args.args == ("job", "folder:a/b/c")
    assert h.db.get_job_cache_file.call_args.kwargs["service_id"] == "svc"


def test_cache_view_download_serves_the_bytes(h):
    h.db.get_job_cache_file.return_value = b"payload"

    response = h.client().get("/cache/global/p/j/f.txt?download=1")

    assert response.get_data() == b"payload"
    assert "attachment" in response.headers["Content-Disposition"] and "f.txt" in response.headers["Content-Disposition"]


def test_cache_view_missing_file(h):
    h.db.get_job_cache_file.return_value = None

    assert h.client().get("/cache/global/p/j/f.txt?download=1").status_code == 404
    client = h.client()
    response = client.get("/cache/svc/p/j/f.txt")
    assert response.status_code == 302 and response.headers["Location"].endswith("/cache")
    assert any("Cache file f.txt from job j, plugin p, service svc not found" in message for message in _flashed(h, client))


def test_cache_view_renders_printable_content(h):
    h.db.get_job_cache_file.return_value = b"hello"

    h.client().get("/cache/global/p/j/f.txt")

    assert h.renders[-1][0] == "cache_view.html"


def test_cache_bulk_delete_reports_each_outcome(h):
    h.db.delete_job_cache.side_effect = ["", None, "disk error"]
    h.db.checked_changes.return_value = ""
    files = [
        {"fileName": "a", "jobName": "j", "service": "global", "plugin": "p1"},
        {"fileName": "b", "jobName": "j", "service": "s", "plugin": "p2"},
        {"fileName": "c", "jobName": "j", "plugin": "p2"},
    ]
    client = h.client()

    response = client.post("/cache/delete", data={"cache_files": json.dumps(files)})

    assert response.status_code == 302
    h.db.checked_changes.assert_called_once()
    assert h.db.checked_changes.call_args.kwargs["changes"] == ["config"] and h.db.checked_changes.call_args.kwargs["plugins_changes"] == ["p1"]
    assert "Deleted 1 files with 2 errors: Cache file b not found; Error deleting c: disk error" in _flashed(h, client)


def test_cache_bulk_delete_success_message(h):
    h.db.delete_job_cache.return_value = ""
    h.db.checked_changes.return_value = ""
    client = h.client()

    client.post("/cache/delete", data={"cache_files": json.dumps([{"fileName": "a", "jobName": "j", "plugin": "p"}])})

    assert "Successfully deleted 1 cache file" in _flashed(h, client)


def test_cache_bulk_delete_commit_failure_is_reported(h):
    h.db.delete_job_cache.return_value = ""
    h.db.checked_changes.return_value = "nope"
    client = h.client()

    client.post("/cache/delete", data={"cache_files": json.dumps([{"fileName": "a", "jobName": "j", "plugin": "p"}])})

    assert any("Changes were not committed to the database" in message for message in _flashed(h, client))


@pytest.mark.parametrize(
    "form, status, text",
    [
        ({"cache_files": "{"}, 400, "Invalid cache files parameter"),
        ({"cache_files": "[]"}, 400, "No cache files selected"),
        ({}, 400, "No cache files selected"),
    ],
)
def test_cache_bulk_delete_rejects_bad_input(h, form, status, text):
    response = h.client().post("/cache/delete", data=form)

    assert response.status_code == status and text in response.get_data(as_text=True)
    h.db.delete_job_cache.assert_not_called()


def test_cache_bulk_delete_in_read_only_mode(h):
    h.db.readonly = True

    response = h.client().post("/cache/delete", data={"cache_files": json.dumps([{"fileName": "a"}])})

    assert response.status_code == 403
    h.db.delete_job_cache.assert_not_called()
