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


def _serve(h, payload, rows=None):
    """Make the fake DB answer like `Database.get_job_cache_file`: bytes alone, or a dict with the STORED names when
    `with_info=True`. With `rows` ((plugin, job, file, bytes) tuples) it resolves like a `*_general_ci` column, case-insensitive
    and PAD SPACE; without, whatever is asked for is the stored name."""

    def same(left, right):
        return left.casefold().rstrip(" ") == right.casefold().rstrip(" ")

    def lookup(job_name, file_name, *, service_id=None, plugin_id="", with_info=False, with_data=True):
        if rows is None:
            stored = (plugin_id, job_name, file_name, payload)
        else:
            stored = next((row for row in rows if same(row[0], plugin_id) and same(row[1], job_name) and same(row[2], file_name)), None)
        if stored is None:
            return None
        if not with_info:
            return stored[3]
        return {"data": stored[3], "last_update": None, "checksum": "sum", "plugin_id": stored[0], "job_name": stored[1], "file_name": stored[2]}

    h.db.get_job_cache_file.side_effect = lookup


def test_cache_view_sanitizes_the_file_name_and_maps_global_to_no_service(h):
    _serve(h, b"hello")

    h.client().get("/cache/global/plugin/job/..%20etc%20passwd%00.txt")

    args, kwargs = h.db.get_job_cache_file.call_args
    assert args == ("job", "etc_passwd.txt") and kwargs == {"service_id": None, "plugin_id": "plugin", "with_info": True}


def test_cache_view_folder_names_use_slashes(h):
    _serve(h, b"x")

    h.client().get("/cache/svc/plugin/job/folder:a_b_c")

    assert h.db.get_job_cache_file.call_args.args == ("job", "folder:a/b/c")
    assert h.db.get_job_cache_file.call_args.kwargs["service_id"] == "svc"


def test_cache_view_download_serves_the_bytes(h):
    _serve(h, b"payload")

    response = h.client().get("/cache/global/p/j/f.txt?download=1")

    assert response.get_data() == b"payload"
    assert "attachment" in response.headers["Content-Disposition"] and "f.txt" in response.headers["Content-Disposition"]


def test_cache_view_missing_file(h):
    _serve(h, None, rows=[])

    assert h.client().get("/cache/global/p/j/f.txt?download=1").status_code == 404
    client = h.client()
    response = client.get("/cache/svc/p/j/f.txt")
    assert response.status_code == 302 and response.headers["Location"].endswith("/cache")
    assert any("Cache file f.txt from job j, plugin p, service svc not found" in message for message in _flashed(h, client))


def test_cache_view_renders_printable_content(h):
    _serve(h, b"hello")

    h.client().get("/cache/global/p/j/f.txt")

    assert h.renders[-1][0] == "cache_view.html"


# (url path after /cache/global, expected lookup name): entries only a super administrator may read.
SENSITIVE_CACHE_URLS = [
    ("ui_sso/ui-sso-secret/secret", "secret"),
    ("p/j/token.secret", "token.secret"),
    ("p/j/secret.tgz", "secret.tgz"),
    ("p/j/state.secret.tgz", "state.secret.tgz"),
    ("p/j/folder:_var_cache_bunkerweb_p_state.secret.tgz", "folder:/var/cache/bunkerweb/p/state.secret.tgz"),
    ("customcert/custom-cert/key.pem", "key.pem"),
    ("selfsigned/self-signed/key.pem", "key.pem"),
    ("misc/default-server-cert/default-server-cert.key", "default-server-cert.key"),
    ("jobs/api-server-cert/api-server-cert.key", "api-server-cert.key"),
    ("letsencrypt/certbot-new/credentials_0123456789ab.ini", "credentials_0123456789ab.ini"),
    ("letsencrypt/certbot-renew/folder:_var_cache_bunkerweb_letsencrypt_etc.tgz", "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"),
    ("crowdsec/crowdsec-conf/crowdsec.conf", "crowdsec.conf"),
    ("jobs/failover-backup/folder:_var_tmp_bunkerweb_failover.tgz", "folder:/var/tmp/bunkerweb/failover.tgz"),
    ("reverseproxy/trusted-cert/client-key.pem", "client-key.pem"),
    ("grpc/grpc-trusted-cert/client-key.pem", "client-key.pem"),
]
NON_SUPER_ADMINS = [
    {"admin": False, "permissions": ("read",), "list_roles": ["reader"]},
    {"admin": False, "permissions": ("read", "write"), "list_roles": ["writer"]},
    {"admin": False, "permissions": ("read", "write"), "list_roles": ["admin"]},
]


@pytest.mark.parametrize("user", NON_SUPER_ADMINS, ids=["reader", "writer", "assigned-admin"])
@pytest.mark.parametrize("suffix", ["", "?download=1"])
@pytest.mark.parametrize("path,name", SENSITIVE_CACHE_URLS)
def test_cache_view_refuses_sensitive_entries_to_everyone_but_the_super_admin(h, user, suffix, path, name):
    _serve(h, b"PLACEHOLDER-BYTES")
    renders = len(h.renders)

    response = h.client(**user).get(f"/cache/global/{path}{suffix}")

    assert response.status_code == 403
    assert b"PLACEHOLDER-BYTES" not in response.get_data()
    h.db.get_job_cache_file.assert_not_called()
    assert len(h.renders) == renders


@pytest.mark.parametrize("path,name", SENSITIVE_CACHE_URLS)
def test_cache_view_gives_the_super_admin_sensitive_entries(h, path, name):
    _serve(h, b"PLACEHOLDER-BYTES")

    download = h.client(admin=True).get(f"/cache/global/{path}?download=1")
    view = h.client(admin=True).get(f"/cache/global/{path}")

    assert download.status_code == 200 and download.get_data() == b"PLACEHOLDER-BYTES"
    assert h.renders[-1][0] == "cache_view.html"
    assert view.status_code == 200
    assert h.db.get_job_cache_file.call_args.args[1] == name


@pytest.mark.parametrize("user", NON_SUPER_ADMINS, ids=["reader", "writer", "assigned-admin"])
@pytest.mark.parametrize(
    "path",
    [
        "p/j/backup.json",
        "p/j/SECRET",
        "p/j/secret.txt",
        "other/other-job/key.pem",
        "customcert/custom-cert/cert.pem",
        "other/other-job/folder:_var_cache_bunkerweb_letsencrypt_etc.tgz",
    ],
)
def test_cache_view_keeps_ordinary_entries_open_to_every_signed_in_user(h, user, path):
    _serve(h, b"hello")

    download = h.client(**user).get(f"/cache/global/{path}?download=1")
    view = h.client(**user).get(f"/cache/global/{path}")

    assert download.status_code == 200 and download.get_data() == b"hello"
    assert view.status_code == 200 and h.renders[-1][0] == "cache_view.html"


def test_cache_view_classifies_the_name_after_sanitising_it(h):
    _serve(h, b"PLACEHOLDER-BYTES")

    response = h.client(admin=False).get("/cache/global/p/j/..%20token.secret%00")

    assert response.status_code == 403
    h.db.get_job_cache_file.assert_not_called()


def test_cache_list_and_delete_still_reach_non_super_admins(h, delete_rows):
    h.db.get_jobs_cache_files.return_value = [{"file_name": "secret"}]
    h.config.get_config.return_value = {"SERVER_NAME": ""}
    client = h.client(admin=False)

    assert client.get("/cache").status_code == 200
    assert h.renders[-1][1]["caches"] == [{"file_name": "secret"}]
    files = json.dumps([{"fileName": "notes.txt", "jobName": "j", "service": "global", "plugin": "p"}])
    assert client.post("/cache/delete", data={"cache_files": files}).status_code == 302
    assert delete_rows.call_args.args == ("notes.txt",)


# Rework 1: the database compares plugin id, job name and file name with its collation (MariaDB/MySQL `_ci`: case-insensitive,
# trailing spaces ignored), so a spelling the classifier does not recognise can still resolve a stored sensitive row. The
# gate must classify the STORED names. `secure_filename` turns a trailing space into `_`, so that variant is only reachable
# through the plugin id, the job name and `folder:` names.
LE_ARCHIVE_TOKEN = "folder:_var_cache_bunkerweb_letsencrypt_etc.tgz"
STORED_SENSITIVE_ROWS = [
    ("ui_sso", "ui-sso-secret", "secret", b"PLACEHOLDER-BYTES"),
    ("p", "j", "token.secret", b"PLACEHOLDER-BYTES"),
    ("customcert", "custom-cert", "key.pem", b"PLACEHOLDER-BYTES"),
    ("letsencrypt", "certbot-new", "credentials_0123456789ab.ini", b"PLACEHOLDER-BYTES"),
    ("letsencrypt", "certbot-renew", "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz", b"PLACEHOLDER-BYTES"),
    ("crowdsec", "crowdsec-conf", "crowdsec.conf", b"PLACEHOLDER-BYTES"),
    ("jobs", "failover-backup", "folder:/var/tmp/bunkerweb/failover.tgz", b"PLACEHOLDER-BYTES"),
    ("reverseproxy", "trusted-cert", "client-key.pem", b"PLACEHOLDER-BYTES"),
    ("grpc", "grpc-trusted-cert", "client-key.pem", b"PLACEHOLDER-BYTES"),
]
UI_COLLATION_VARIANTS = [
    "ui_sso/ui-sso-secret/SECRET",
    "ui_sso/ui-sso-secret/Secret",
    "ui_sso%20/ui-sso-secret/secret",
    "ui_sso/ui-sso-secret%20/secret",
    "UI_SSO/UI-SSO-SECRET/secret",
    "p/j/TOKEN.SECRET",
    "p/j/token.SECRET",
    "p%20/j/token.secret",
    "p/j%20%20/token.secret",
    "customcert/custom-cert/KEY.PEM",
    "customcert%20/custom-cert/key.pem",
    "customcert/custom-cert%20/key.pem",
    "CustomCert/Custom-Cert/key.pem",
    "letsencrypt/certbot-new/CREDENTIALS_0123456789AB.INI",
    "letsencrypt%20/certbot-new/credentials_0123456789ab.ini",
    "letsencrypt/certbot-new%20/credentials_0123456789ab.ini",
    f"letsencrypt/certbot-renew/{LE_ARCHIVE_TOKEN}%20",
    f"letsencrypt/certbot-renew%20/{LE_ARCHIVE_TOKEN}",
    "letsencrypt/certbot-renew/folder:_VAR_CACHE_BUNKERWEB_LETSENCRYPT_ETC.TGZ",
    "crowdsec/crowdsec-conf/CrowdSec.conf",
    "crowdsec%20/crowdsec-conf/crowdsec.conf",
    "crowdsec/crowdsec-conf%20/crowdsec.conf",
    "Jobs/Failover-Backup/folder:_var_tmp_bunkerweb_failover.tgz",
    "jobs/failover-backup%20/folder:_var_tmp_bunkerweb_failover.tgz",
    "ReverseProxy/Trusted-Cert/CLIENT-KEY.PEM",
    "grpc/grpc-trusted-cert%20/client-key.pem",
]


@pytest.mark.parametrize("user", NON_SUPER_ADMINS, ids=["reader", "writer", "assigned-admin"])
@pytest.mark.parametrize("suffix", ["", "?download=1"])
@pytest.mark.parametrize("path", UI_COLLATION_VARIANTS)
def test_cache_view_refuses_a_collation_variant_of_a_sensitive_entry(h, user, suffix, path):
    _serve(h, None, rows=STORED_SENSITIVE_ROWS)

    response = h.client(**user).get(f"/cache/global/{path}{suffix}")

    assert response.status_code == 403
    assert b"PLACEHOLDER-BYTES" not in response.get_data()
    assert [name for name, _context in h.renders if name == "cache_view.html"] == []


@pytest.mark.parametrize("path", UI_COLLATION_VARIANTS)
def test_the_super_admin_still_reads_a_collation_variant(h, path):
    _serve(h, None, rows=STORED_SENSITIVE_ROWS)

    response = h.client(admin=True).get(f"/cache/global/{path}?download=1")

    assert response.status_code == 200 and response.get_data() == b"PLACEHOLDER-BYTES"


@pytest.mark.parametrize("path", ["P/J/NOTES.TXT", "p%20/j/notes.txt", "p/j%20/notes.txt", "customcert/custom-cert/CERT.PEM"])
def test_a_collation_variant_of_an_ordinary_entry_stays_readable(h, path):
    _serve(
        h,
        None,
        rows=[("p", "j", "notes.txt", b"hello"), ("customcert", "custom-cert", "cert.pem", b"hello")],
    )

    response = h.client(admin=False, permissions=("read",)).get(f"/cache/global/{path}?download=1")

    assert response.status_code == 200 and response.get_data() == b"hello"


def _delete(h, client, path, service="global"):
    plugin, job, token = path.split("/")
    files = json.dumps([{"fileName": token, "jobName": job, "service": service, "plugin": plugin}])
    return client.post("/cache/delete", data={"cache_files": files})


@pytest.fixture
def delete_rows(h, monkeypatch):
    """The route's one database call, replaced: what it is called with decides what the route does before and after it."""
    module = h.routes.cache
    mock = MagicMock(return_value="")
    monkeypatch.setattr(module, "_delete_cache_rows", mock)
    h.db.checked_changes.return_value = ""
    return mock


@pytest.mark.parametrize("user", NON_SUPER_ADMINS, ids=["reader", "writer", "assigned-admin"])
@pytest.mark.parametrize("path,name", SENSITIVE_CACHE_URLS)
def test_cache_bulk_delete_refuses_sensitive_entries_to_everyone_but_the_super_admin(h, delete_rows, user, path, name):
    client = h.client(**user)

    response = _delete(h, client, path)

    assert response.status_code == 302
    delete_rows.assert_not_called()
    h.db.checked_changes.assert_not_called()
    assert "Deleted 0 files with 1 errors: " in _flashed(h, client)[0] and "restricted to administrators" in _flashed(h, client)[0]


@pytest.mark.parametrize("path,name", SENSITIVE_CACHE_URLS)
def test_cache_bulk_delete_still_deletes_sensitive_entries_for_the_super_admin(h, delete_rows, path, name):
    _delete(h, h.client(admin=True), path)

    assert delete_rows.call_args.args == (name,) and delete_rows.call_args.kwargs["admin"] is True


def test_cache_bulk_delete_reports_a_stored_sensitive_row_as_restricted(h, delete_rows):
    delete_rows.return_value = h.routes.cache.RESTRICTED
    client = h.client(admin=False)

    _delete(h, client, "p/j/notes.txt")

    assert delete_rows.call_args.kwargs["admin"] is False
    h.db.checked_changes.assert_not_called()
    assert "Deleted 0 files with 1 errors: Cache file notes.txt is restricted to administrators" in _flashed(h, client)


def test_cache_bulk_delete_keeps_going_after_a_refused_entry(h, delete_rows):
    files = [
        {"fileName": "token.secret", "jobName": "j", "service": "global", "plugin": "p"},
        {"fileName": "notes.txt", "jobName": "j", "service": "global", "plugin": "p"},
    ]

    h.client(admin=False).post("/cache/delete", data={"cache_files": json.dumps(files)})

    assert [call.args for call in delete_rows.call_args_list] == [("notes.txt",)]


def test_cache_bulk_delete_reports_each_outcome(h, delete_rows):
    delete_rows.side_effect = ["", None, "disk error"]
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


def test_cache_bulk_delete_success_message(h, delete_rows):
    client = h.client()

    client.post("/cache/delete", data={"cache_files": json.dumps([{"fileName": "a", "jobName": "j", "plugin": "p"}])})

    assert "Successfully deleted 1 cache file" in _flashed(h, client)


def test_cache_bulk_delete_commit_failure_is_reported(h, delete_rows):
    h.db.checked_changes.return_value = "nope"
    client = h.client()

    client.post("/cache/delete", data={"cache_files": json.dumps([{"fileName": "a", "jobName": "j", "plugin": "p"}])})

    assert any("Changes were not committed to the database" in message for message in _flashed(h, client))


# The rows are resolved, authorized and deleted by id in one transaction, on a real database. SQLite compares `=` as binary unless the
# column says otherwise, so the cache table is rebuilt with the NOCASE collation MariaDB/MySQL give every string column.
@pytest.fixture
def nocase_db(h, db, monkeypatch):
    from sqlalchemy import text

    from fixtures.seed import add_jobs_cache_row, session

    from model import Jobs, Plugins  # type: ignore

    with session(db) as s:
        s.add(Plugins(id="ui_sso", name="SSO", description="d", version="1.0"))
        s.add(Plugins(id="p", name="P", description="d", version="1.0"))
        s.flush()
        s.add_all(
            [Jobs(name="ui-sso-secret", plugin_id="ui_sso", file_name="x.py", every="hour"), Jobs(name="j", plugin_id="p", file_name="j.py", every="hour")]
        )
    with db.sql_engine.begin() as connection:
        connection.execute(text("DROP TABLE bw_jobs_cache"))
        connection.execute(
            text(
                "CREATE TABLE bw_jobs_cache (id INTEGER PRIMARY KEY AUTOINCREMENT, job_name VARCHAR(128) NOT NULL, service_id VARCHAR(256), "
                "file_name VARCHAR(256) COLLATE NOCASE NOT NULL, data BLOB, last_update DATETIME, checksum VARCHAR(128))"
            )
        )
    monkeypatch.setattr(h.routes.cache, "DB", db)
    db.add_row = add_jobs_cache_row
    return db


def _names(db):
    from sqlalchemy import text

    with db.sql_engine.connect() as connection:
        return sorted(row[0] for row in connection.execute(text("SELECT file_name FROM bw_jobs_cache")))


def test_a_collation_match_cannot_carry_a_sensitive_row_along(h, nocase_db):
    # The request names `Secret` (not sensitive: the classifier is exact), the NOCASE column matches `secret` too, which is.
    nocase_db.add_row(nocase_db, job_name="ui-sso-secret", file_name="Secret", data=b"public")
    nocase_db.add_row(nocase_db, job_name="ui-sso-secret", file_name="secret", data=b"PLACEHOLDER-BYTES")

    result = h.routes.cache._delete_cache_rows("Secret", job_name="ui-sso-secret", service_id=None, plugin_id="ui_sso", admin=False)

    assert result is h.routes.cache.RESTRICTED
    assert _names(nocase_db) == ["Secret", "secret"]


def test_the_super_admin_deletes_every_collation_match(h, nocase_db):
    nocase_db.add_row(nocase_db, job_name="ui-sso-secret", file_name="Secret", data=b"public")
    nocase_db.add_row(nocase_db, job_name="ui-sso-secret", file_name="secret", data=b"PLACEHOLDER-BYTES")

    assert h.routes.cache._delete_cache_rows("Secret", job_name="ui-sso-secret", service_id=None, plugin_id="ui_sso", admin=True) == ""

    assert _names(nocase_db) == []


def test_an_ordinary_collation_match_is_deleted_for_a_non_admin(h, nocase_db):
    nocase_db.add_row(nocase_db, job_name="j", file_name="Notes.txt", data=b"x")
    nocase_db.add_row(nocase_db, job_name="j", file_name="notes.txt", data=b"x")
    nocase_db.add_row(nocase_db, job_name="j", file_name="other.txt", data=b"x")

    assert h.routes.cache._delete_cache_rows("NOTES.TXT", job_name="j", service_id=None, plugin_id="p", admin=False) == ""

    assert _names(nocase_db) == ["other.txt"]


def test_delete_rows_reports_a_missing_row_and_a_wrong_plugin(h, nocase_db):
    nocase_db.add_row(nocase_db, job_name="j", file_name="notes.txt", data=b"x")

    assert h.routes.cache._delete_cache_rows("zzz", job_name="j", service_id=None, plugin_id="p", admin=False) is None
    assert h.routes.cache._delete_cache_rows("notes.txt", job_name="j", service_id=None, plugin_id="other", admin=False) is None
    assert _names(nocase_db) == ["notes.txt"]


def test_delete_rows_refuses_in_read_only_mode(h, nocase_db):
    nocase_db.add_row(nocase_db, job_name="j", file_name="notes.txt", data=b"x")
    nocase_db.readonly = True

    assert "read-only" in h.routes.cache._delete_cache_rows("notes.txt", job_name="j", service_id=None, plugin_id="p", admin=True)
    assert _names(nocase_db) == ["notes.txt"]


def test_a_row_replaced_between_the_check_and_the_delete_is_not_deleted(h, nocase_db, monkeypatch):
    from sqlalchemy import text

    nocase_db.add_row(nocase_db, job_name="ui-sso-secret", file_name="notes.txt", data=b"public")
    real = h.routes.cache.is_sensitive_job_cache_file

    def classify(*args, **kwargs):
        # SQLite reuses the id: another connection swaps in a sensitive row right after the check read the benign one.
        result = real(*args, **kwargs)
        with nocase_db.sql_engine.begin() as connection:
            row_id = connection.execute(text("SELECT id FROM bw_jobs_cache WHERE file_name = 'notes.txt'")).scalar_one()
            connection.execute(text("DELETE FROM bw_jobs_cache WHERE id = :i"), {"i": row_id})
            connection.execute(
                text("INSERT INTO bw_jobs_cache (id, job_name, service_id, file_name, data) VALUES (:i, 'ui-sso-secret', NULL, 'token.secret', :d)"),
                {"i": row_id, "d": b"PLACEHOLDER-BYTES"},
            )
        monkeypatch.setattr(h.routes.cache, "is_sensitive_job_cache_file", real)
        return result

    monkeypatch.setattr(h.routes.cache, "is_sensitive_job_cache_file", classify)

    assert h.routes.cache._delete_cache_rows("notes.txt", job_name="ui-sso-secret", service_id=None, plugin_id="ui_sso", admin=False) is None
    assert _names(nocase_db) == ["token.secret"]


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


@pytest.mark.parametrize("plugin,job", [("reverseproxy", "trusted-cert"), ("grpc", "grpc-trusted-cert")])
def test_a_service_scoped_upstream_client_key_is_super_admin_only(h, plugin, job):
    _serve(h, b"PLACEHOLDER-BYTES")
    path = f"/cache/www.example.com/{plugin}/{job}/client-key.pem"

    reader = h.client(admin=False, permissions=("read",), list_roles=["reader"]).get(f"{path}?download=1")
    admin = h.client(admin=True).get(f"{path}?download=1")

    assert reader.status_code == 403 and b"PLACEHOLDER-BYTES" not in reader.get_data()
    assert admin.status_code == 200 and admin.get_data() == b"PLACEHOLDER-BYTES"
