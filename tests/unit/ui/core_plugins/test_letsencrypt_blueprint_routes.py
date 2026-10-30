"""Certificate management responses, cache writeback and scratch lifetimes."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from tarfile import open as tar_open
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes

from _core_ui_helpers import certificate_tree, tar_bytes


def test_scratch_directories_are_unique_and_removed(le):
    with le._ui_scratch_dir() as first, le._ui_scratch_dir() as second:
        assert first != second
        assert Path(first).parent == Path(le.SCRATCH_ROOT)
        (Path(first) / "private_key.json").write_text("sensitive fixture")
        assert Path(second).exists()
    assert not Path(first).exists()
    assert not Path(second).exists()


def test_cache_download_preserves_accounts_and_hooks(le, ui_env, tmp_path):
    ui_env.db.get_jobs_cache_files.return_value = [
        {"file_name": "unrelated.tgz", "data": b"ignored"},
        {
            "file_name": "folder:cache.tgz",
            "data": tar_bytes({"./accounts/id/key.json": "key", "./renewal-hooks/deploy.sh": "hook", "./live/site/fullchain.pem": "pem"}),
        },
    ]
    target = tmp_path / "restored"
    le.download_certificates(target)
    assert (target / "accounts/id/key.json").read_text() == "key"
    assert (target / "renewal-hooks/deploy.sh").read_text() == "hook"
    assert (target / "live/site/fullchain.pem").read_text() == "pem"
    ui_env.db.get_jobs_cache_files.assert_called_once_with(job_name="certbot-renew")


def test_cache_persistence_tars_full_tree_and_notifies_scheduler(le, ui_env, tmp_path):
    source = tmp_path / "source"
    (source / "accounts/id").mkdir(parents=True)
    (source / "accounts/id/private_key.json").write_text("key")
    assert le._persist_le_cache_dir(source) is None
    args, kwargs = ui_env.db.upsert_job_cache.call_args
    assert args[:2] == ("", f"folder:{le.LE_CACHE_DIR}.tgz")
    assert kwargs == {"job_name": "certbot-renew"}
    with tar_open(fileobj=BytesIO(args[2]), mode="r:gz") as archive:
        assert archive.extractfile("./accounts/id/private_key.json").read() == b"key"
    ui_env.db.checked_changes.assert_called_once_with(["plugins"], ["letsencrypt"], True)


def test_inconsistent_cache_is_not_written(le, ui_env, tmp_path, monkeypatch):
    monkeypatch.setattr(le, "_le_cache_consistent", lambda path: (False, "missing account"))
    assert le._persist_le_cache_dir(tmp_path) == "cache state inconsistent (missing account)"
    ui_env.db.upsert_job_cache.assert_not_called()
    ui_env.db.checked_changes.assert_not_called()
    assert le._persist_le_cache_dir(tmp_path, bypass_gate=True) is None


@pytest.mark.parametrize(
    "operation,expected", [("upsert_job_cache", "upsert_job_cache failed: offline"), ("checked_changes", "checked_changes failed: offline")]
)
def test_persistence_error_is_returned(le, ui_env, tmp_path, operation, expected):
    getattr(ui_env.db, operation).return_value = "offline"
    assert le._persist_le_cache_dir(tmp_path, bypass_gate=True) == expected
    if operation == "upsert_job_cache":
        ui_env.db.checked_changes.assert_not_called()


def test_retrieve_real_certificate_and_renewal(le, tmp_path):
    cert = certificate_tree(tmp_path)
    result = le.retrieve_certificates(tmp_path)
    assert result["domain"] == result["common_name"] == ["example.test"]
    assert result["issuer"] == ["Unit CA"]
    assert result["serial_number"] == ["42"]
    assert result["fingerprint"] == [cert.fingerprint(hashes.SHA256()).hex()]
    assert datetime.fromisoformat(result["valid_from"][0]) == cert.not_valid_before_utc
    assert datetime.fromisoformat(result["valid_to"][0]) == cert.not_valid_after_utc
    assert result["version"] == ["v3"]
    assert result["preferred_profile"] == ["shortlived"]
    assert result["challenge"] == ["dns-01"]
    assert result["authenticator"] == ["dns-route53"]
    assert result["key_type"] == ["ecdsa"]
    assert result["issuer_server"] == ["https://acme.example/directory"]


def test_invalid_certificate_retains_domain_defaults(le, tmp_path, ui_env):
    path = tmp_path / "live/broken.test/fullchain.pem"
    path.parent.mkdir(parents=True)
    path.write_text("broken")
    result = le.retrieve_certificates(tmp_path)
    assert result["common_name"] == ["broken.test"]
    assert result["issuer"] == ["Unknown"]
    assert result["valid_to"] == [None]
    assert "Error while parsing certificate" in ui_env.utils.LOGGER.error.call_args.args[0]


@pytest.fixture
def fetch_rows(le, monkeypatch):
    rows = [
        dict(domain="b.test", issuer="<CA>", preferred_profile="classic", challenge="dns-01", key_type="ecdsa", valid_to="2027-01-01T00:00:00+00:00"),
        dict(domain="a.test", issuer="Other CA", preferred_profile="shortlived", challenge="http-01", key_type="rsa", valid_to="2026-01-01T00:00:00+00:00"),
        dict(domain="c.test", issuer=None, preferred_profile="classic", challenge="dns-01", key_type="ecdsa", valid_to=None),
    ]
    fields = (
        "domain",
        "common_name",
        "issuer",
        "issuer_server",
        "valid_from",
        "valid_to",
        "serial_number",
        "fingerprint",
        "version",
        "preferred_profile",
        "challenge",
        "authenticator",
        "key_type",
    )
    monkeypatch.setattr(le, "retrieve_certificates", lambda path: {field: [row.get(field, "") for row in rows] for field in fields})
    monkeypatch.setattr(le, "_detect_orphan_renewals", lambda path: [{"cert_name": "b.test"}])
    monkeypatch.setattr(le, "_detect_broken_lineages", lambda path: [{"lineage_names": ["a.test", "alias.test"]}])
    return rows


def test_fetch_filters_search_and_panels_before_pagination(le, ui_env, fetch_rows):
    response = ui_env.client.post(
        "/letsencrypt/fetch",
        data={
            "draw": "5",
            "search[value]": "DNS",
            "searchPanes[key_type][0]": "ecdsa",
            "order[0][column]": "2",
            "order[0][dir]": "desc",
            "start": "1",
            "length": "1",
        },
    )
    assert response.status_code == 200
    body = response.json
    assert body["draw"] == 5
    assert body["recordsTotal"] == 3
    assert body["recordsFiltered"] == 2
    assert [row["domain"] for row in body["data"]] == ["b.test"]
    assert body["data"][0]["is_orphan"] is True
    assert body["searchPanes"]["options"]["issuer"] == [
        {"label": "&lt;CA&gt;", "value": "<CA>", "total": 1, "count": 1},
        {"label": "N/A", "value": "N/A", "total": 1, "count": 1},
        {"label": "Other CA", "value": "Other CA", "total": 1, "count": 0},
    ]
    assert list(Path(le.SCRATCH_ROOT).iterdir()) == []


def test_fetch_column_search_or_terms_and_invalid_numbers(le, ui_env, fetch_rows):
    body = ui_env.client.post(
        "/letsencrypt/fetch",
        data={"draw": "invalid", "start": "invalid", "length": "invalid", "order[0][column]": "invalid", "columns[2][search][value]": " A.TEST | b.TEST "},
    ).json
    assert body["draw"] == 1
    assert body["recordsFiltered"] == 2
    assert [row["domain"] for row in body["data"]] == ["b.test", "a.test"]
    assert all(row["is_orphan"] for row in body["data"])
    assert ui_env.client.post("/letsencrypt/fetch", data={"start": "-1", "length": "-2"}).json["data"] == []


def test_fetch_null_pane_values_and_empty_column_terms(le, ui_env, fetch_rows):
    body = ui_env.client.post(
        "/letsencrypt/fetch", data={"columns[2][search][value]": " | ", "searchPanes[issuer][0]": "N/A", "searchPanes[issuer][1]": ""}
    ).json
    assert body["recordsFiltered"] == 1
    assert body["data"][0]["domain"] == "c.test"
    assert body["data"][0]["is_orphan"] is False


def test_fetch_handles_cache_failure(le, ui_env):
    ui_env.db.get_jobs_cache_files.side_effect = RuntimeError("offline")
    response = ui_env.client.post("/letsencrypt/fetch")
    assert response.status_code == 200
    assert response.json == {"data": [], "recordsTotal": 0, "recordsFiltered": 0, "draw": 1, "searchPanes": {"options": {}}}
    assert list(Path(le.SCRATCH_ROOT).iterdir()) == []


def test_fetch_orders_valid_expiry_dates(le, ui_env, fetch_rows):
    body = ui_env.client.post("/letsencrypt/fetch", data={"columns[2][search][value]": "a.test|b.test", "order[0][column]": "6", "order[0][dir]": "asc"}).json
    assert [row["domain"] for row in body["data"]] == ["a.test", "b.test"]


def test_fetch_orders_expiry_dates_with_invalid_certificate(le, ui_env, fetch_rows):
    response = ui_env.client.post("/letsencrypt/fetch", data={"order[0][column]": "6", "order[0][dir]": "asc"})
    assert response.status_code == 200
    assert {row["domain"] for row in response.json["data"]} == {"a.test", "b.test", "c.test"}


@pytest.mark.parametrize("route", ["delete", "heal"])
@pytest.mark.parametrize(
    "payload,message",
    [
        ({}, "Missing cert_name"),
        ({"cert_name": ".."}, "Invalid cert_name"),
        ({"cert_name": "../outside"}, "Invalid cert_name"),
        ({"cert_name": "/absolute"}, "Invalid cert_name"),
    ],
)
def test_mutation_routes_validate_name_before_io(le, ui_env, route, payload, message):
    response = ui_env.client.post(f"/letsencrypt/{route}", json=payload)
    assert response.status_code == 400
    assert response.json == {"status": "ko", "message": message}
    ui_env.db.get_jobs_cache_files.assert_not_called()
    le.run.assert_not_called()


@pytest.mark.parametrize("route", ["delete", "heal"])
def test_readonly_user_cannot_mutate(le, ui_env, route):
    ui_env.user.list_permissions = ["read"]
    response = ui_env.client.post(f"/letsencrypt/{route}", json={"cert_name": "example.test"})
    assert response.status_code == 403
    assert response.json == {"status": "ko", "message": "User is read-only"}
    ui_env.db.get_jobs_cache_files.assert_not_called()


def test_anonymous_user_cannot_read_certificates(le, ui_env):
    response = ui_env.app.test_client().get("/letsencrypt/accounts")
    assert response.status_code == 401
    ui_env.db.get_jobs_cache_files.assert_not_called()


@pytest.mark.parametrize("value,expected", [("bad", "50"), (" -5 ", "0"), (" 7 ", "7")])
def test_delete_runs_certbot_then_persists_cleanup(le, ui_env, monkeypatch, value, expected):
    monkeypatch.setenv("LETS_ENCRYPT_MAX_LOG_BACKUPS", value)
    monkeypatch.setenv("PYTHONPATH", "test-path")
    monkeypatch.setattr(le, "_detect_broken_lineages", lambda path: [])

    def populate(path):
        (path / "live/example.test").mkdir(parents=True)
        (path / "archive/example.test").mkdir(parents=True)
        (path / "renewal").mkdir()
        (path / "renewal/example.test.conf").write_text("renewal")
        (path / "accounts/id").mkdir(parents=True)
        (path / "accounts/id/private_key.json").write_text("retain")

    monkeypatch.setattr(le, "download_certificates", populate)
    le.run.side_effect = None
    le.run.return_value = SimpleNamespace(returncode=0)
    response = ui_env.client.post("/letsencrypt/delete", json={"cert_name": "example.test"})
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    args, kwargs = le.run.call_args
    command = args[0]
    assert command[:2] == [le.CERTBOT_BIN, "delete"]
    assert command[command.index("--max-log-backups") + 1] == expected
    assert command[-3:] == ["--cert-name", "example.test", "-n"]
    assert kwargs["check"] is False
    assert kwargs["env"]["PYTHONPATH"] == f"test-path:{le.DEPS_PATH}"
    with tar_open(fileobj=BytesIO(ui_env.db.upsert_job_cache.call_args.args[2]), mode="r:gz") as archive:
        assert archive.extractfile("./accounts/id/private_key.json").read() == b"retain"
        assert not any("example.test" in name for name in archive.getnames())
    assert list(Path(le.SCRATCH_ROOT).iterdir()) == []


def test_delete_certbot_failure_does_not_persist(le, ui_env):
    le.run.side_effect = None
    le.run.return_value = SimpleNamespace(returncode=1, stdout="certbot failed")
    response = ui_env.client.post("/letsencrypt/delete", json={"cert_name": "example.test"})
    assert response.status_code == 500
    assert response.json == {"status": "ko", "message": "Failed to delete certificate example.test"}
    ui_env.db.upsert_job_cache.assert_not_called()


@pytest.mark.parametrize("route", ["heal", "delete"])
def test_mutation_rejects_resolved_path_escape(le, ui_env, monkeypatch, route):
    monkeypatch.setattr(le, "_detect_orphan_renewals", lambda path: [{"cert_name": "example.test", "account": "missing", "server": "acme"}])
    monkeypatch.setattr(le, "_path_is_inside", lambda child, parent: False)
    response = ui_env.client.post(f"/letsencrypt/{route}", json={"cert_name": "example.test"})
    assert response.status_code == 400
    assert response.json == {"status": "ko", "message": "Invalid cert_name"}
    le.run.assert_not_called()
    ui_env.db.upsert_job_cache.assert_not_called()


@pytest.mark.parametrize("route", ["heal", "delete"])
def test_broken_alias_uses_original_renewal_path(le, ui_env, monkeypatch, route):
    target = {"cert_name": "original.test", "lineage_names": ["original.test", "alias.test"], "reason": "mismatch", "renewal_conf": ""}

    def broken(path):
        target["renewal_conf"] = str(path / "renewal/original.test.conf")
        return [target]

    monkeypatch.setattr(le, "_detect_broken_lineages", broken)
    purge = Mock(return_value=["renewal/original.test.conf", "live/alias.test"])
    persist = Mock(return_value=None)
    monkeypatch.setattr(le, "_purge_lineage", purge)
    monkeypatch.setattr(le, "_persist_le_cache_dir", persist)
    response = ui_env.client.post(f"/letsencrypt/{route}", json={"cert_name": "alias.test"})
    assert response.status_code == 200
    assert response.json["removed"] == ["renewal/original.test.conf", "live/alias.test"]
    assert purge.call_args.args[1] == Path(target["renewal_conf"])
    assert persist.call_args.kwargs == {"bypass_gate": True}
    le.run.assert_not_called()


@pytest.mark.parametrize("failure", ["cache offline", RuntimeError("DB failed")])
def test_broken_delete_reports_writeback_failure(le, ui_env, monkeypatch, failure):
    monkeypatch.setattr(
        le,
        "_detect_broken_lineages",
        lambda path: [{"cert_name": "example.test", "lineage_names": [], "reason": "broken", "renewal_conf": str(path / "renewal/example.test.conf")}],
    )
    monkeypatch.setattr(le, "_purge_lineage", Mock(return_value=["removed"]))
    persist = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    monkeypatch.setattr(le, "_persist_le_cache_dir", persist)
    response = ui_env.client.post("/letsencrypt/delete", json={"cert_name": "example.test"})
    assert response.status_code == 500
    assert "cache update failed" in response.json["message"]
    le.run.assert_not_called()


def test_heal_orphan_removes_conf_and_material(le, ui_env):
    ui_env.db.get_jobs_cache_files.return_value = [
        {
            "file_name": "folder:cache.tgz",
            "data": tar_bytes(
                {
                    "renewal/example.test.conf": "account = missing\nserver = https://acme.example/directory\n",
                    "live/example.test/fullchain.pem": "pem",
                    "archive/example.test/cert1.pem": "pem",
                    "accounts/keep/key.json": "retain",
                }
            ),
        }
    ]
    response = ui_env.client.post("/letsencrypt/heal", json={"cert_name": "example.test"})
    assert response.status_code == 200
    assert response.json["target"]["account"] == "missing"
    assert len(response.json["removed"]) == 3
    with tar_open(fileobj=BytesIO(ui_env.db.upsert_job_cache.call_args.args[2]), mode="r:gz") as archive:
        assert not any("example.test" in name for name in archive.getnames())
        assert archive.extractfile("./accounts/keep/key.json").read() == b"retain"


def test_heal_refuses_healthy_certificate(le, ui_env):
    response = ui_env.client.post("/letsencrypt/heal", json={"cert_name": "example.test"})
    assert response.status_code == 400
    assert "neither orphaned nor broken" in response.json["message"]
    ui_env.db.upsert_job_cache.assert_not_called()


@pytest.mark.parametrize("route", ["heal", "delete"])
@pytest.mark.parametrize("failure", ["error string", RuntimeError("DB failed")])
def test_mutation_persistence_failure_returns_500(le, ui_env, monkeypatch, route, failure):
    monkeypatch.setattr(le, "_detect_orphan_renewals", lambda path: [{"cert_name": "example.test", "account": "missing", "server": "acme"}])
    monkeypatch.setattr(le, "_purge_lineage", Mock(return_value=["removed"]))
    persist = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    monkeypatch.setattr(le, "_persist_le_cache_dir", persist)
    le.run.side_effect = None
    le.run.return_value = SimpleNamespace(returncode=0)
    response = ui_env.client.post(f"/letsencrypt/{route}", json={"cert_name": "example.test"})
    assert response.status_code == 500
    assert response.json["status"] == "ko"
    assert "cache update failed:" in response.json["message"]


def test_accounts_parse_emails_and_tolerate_bad_metadata(le, ui_env):
    ui_env.db.get_jobs_cache_files.return_value = [
        {
            "file_name": "folder:cache.tgz",
            "data": tar_bytes(
                {
                    "accounts/acme.test/directory/good/regr.json": "{}",
                    "accounts/acme.test/directory/good/meta.json": '{"email":"owner@example.test"}',
                    "accounts/acme.test/directory/bad/regr.json": "{}",
                    "accounts/acme.test/directory/bad/meta.json": "not json",
                }
            ),
        }
    ]
    response = ui_env.client.get("/letsencrypt/accounts")
    assert response.status_code == 200
    assert response.json["count"] == 2
    accounts = {row["account_id"]: row for row in response.json["accounts"]}
    assert accounts["good"] == {
        "account_id": "good",
        "email": "owner@example.test",
        "path": "acme.test/directory/good",
        "server_url": "https://acme.test/directory",
    }
    assert accounts["bad"]["email"] == ""
    assert list(Path(le.SCRATCH_ROOT).iterdir()) == []


def test_orphan_and_integrity_routes_report_cache_state(le, ui_env):
    ui_env.db.get_jobs_cache_files.return_value = [
        {"file_name": "folder:cache.tgz", "data": tar_bytes({"renewal/orphan.test.conf": "account = missing\nserver = https://acme.test/directory\n"})}
    ]
    body = ui_env.client.get("/letsencrypt/orphans").json
    assert body["status"] == "ok"
    assert body["count"] == 1
    assert body["orphans"] == [{"cert_name": "orphan.test", "account": "missing", "server": "https://acme.test/directory"}]
    status = ui_env.client.get("/letsencrypt/cache-status").json
    assert status["consistent"] is False
    assert status["orphan_count"] == 1
    assert status["orphans"] == body["orphans"]
    assert status["reason"]


def test_page_and_static_delegate_to_blueprint(le, ui_env, monkeypatch):
    render = Mock(return_value="certificate page")
    static = Mock(return_value="static asset")
    monkeypatch.setattr(le, "render_template", render)
    monkeypatch.setattr(le.letsencrypt, "send_static_file", static)
    assert ui_env.client.get("/letsencrypt").data == b"certificate page"
    render.assert_called_once_with("letsencrypt.html")
    assert ui_env.client.get("/letsencrypt/panel.js").data == b"static asset"
    static.assert_called_once_with("panel.js")
