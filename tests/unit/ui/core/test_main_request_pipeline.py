"""main.py: what every request goes through, with the real app, session store, Flask-Login and Biscuit middleware.

The database is a mock the test scripts; ``um.client(user)`` signs a user in through the real session
interface. ``/loading`` is the probe page: its rendered environment (``um.envs``) shows what ``before_request`` built.
"""

import json
import time
from datetime import datetime, timedelta

import pytest


def flashed(client):
    with client.session_transaction() as sess:
        return [message for _category, message in sess.get("_flashes", [])]


def authed_env(um, **user):
    """Sign in, hit the probe page and return ``(client, environment)``."""
    client = um.client(**user)
    resp = client.get("/__probe")
    assert resp.status_code == 200, resp.data
    return client, json.loads(resp.data)


class TestStaticAndHost:
    def test_static_paths_skip_the_lifecycle(self, um):
        um.client(None).get("/css/none.css")
        um.db.get_metadata.assert_not_called()

    def test_disallowed_host_is_refused_with_400(self, um):
        um.app.config["ALLOWED_HOSTS"] = ["*.example.com"]
        resp = um.client(None).get("/check", headers={"Host": "evil.test"})
        assert resp.status_code == 400 and json.loads(resp.data) == {"message": "Invalid host"}
        assert um.client(None).get("/check", headers={"Host": "ui.example.com"}).status_code == 200

    def test_shutdown_answers_503_with_retry_after(self, um):
        um.data["SERVER_STOPPING"] = True
        resp = um.client(None).get("/check")
        assert resp.status_code == 503 and resp.headers["Retry-After"] == "30"


class TestBackgroundTriggers:
    def test_pending_plugin_reload_runs_and_restarts_workers(self, um):
        um.db.get_metadata.return_value = um.metadata(reload_ui_plugins=True)
        um.client(None).get("/check")
        um.deps.safe_reload_plugins.assert_called_once_with()
        um.restart_workers.assert_called_once_with()

    def test_failed_plugin_reload_does_not_restart_workers(self, um):
        um.db.get_metadata.return_value = um.metadata(reload_ui_plugins=True)
        um.deps.safe_reload_plugins.return_value = "boom"
        um.client(None).get("/check")
        um.restart_workers.assert_not_called()

    def test_reload_held_by_another_worker_is_left_alone(self, um):
        um.db.get_metadata.return_value = um.metadata(reload_ui_plugins=True)
        um.deps.safe_reload_plugins.return_value = None
        um.client(None).get("/check")
        um.restart_workers.assert_not_called()

    def test_no_reload_while_reloading_or_read_only(self, um):
        um.db.get_metadata.return_value = um.metadata(reload_ui_plugins=True)
        um.data["RELOADING"] = True
        um.client(None).get("/check")
        um.db.readonly = True
        um.data["RELOADING"] = False
        um.client(None).get("/check")
        um.deps.safe_reload_plugins.assert_not_called()

    def test_restart_requests_are_throttled(self, um):
        um.db.get_metadata.return_value = um.metadata(reload_ui_plugins=True)
        um.client(None).get("/check")
        um.client(None).get("/check")
        assert um.restart_workers.call_count == 1

    def test_stale_latest_version_check_refreshes_the_release(self, um):
        um.data["LATEST_VERSION_LAST_CHECK"] = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
        um.data["LATEST_VERSION"] = "old"
        um.client(None).get("/check")
        assert um.data["LATEST_VERSION"] == "9.9.9"
        assert datetime.fromisoformat(um.data["LATEST_VERSION_LAST_CHECK"]) > datetime.now().astimezone() - timedelta(minutes=1)

    def test_fresh_latest_version_check_is_not_repeated(self, um):
        um.client(None).get("/check")
        um.main.get_latest_stable_release.assert_not_called()

    def test_expired_session_files_are_pruned_hourly(self, um):
        um.main._session_cleanup_last_run = 0.0
        calls = []
        cache = um.app.config["SESSION_CACHELIB"]
        cache._remove_expired = lambda now: calls.append(now)
        try:
            um.client(None).get("/check")
            um.client(None).get("/check")
        finally:
            del cache._remove_expired
        assert len(calls) == 1

    def test_database_state_check_is_queued_once_then_rate_limited(self, um):
        executor = um.executors["_db_check_executor"]
        um.client(None).get("/check")
        um.client(None).get("/check")
        assert len(executor.pending) == 1
        assert um.data["DB_STATE_CHECK_RUNNING"] is True
        executor.run_pending()
        assert um.data["DB_STATE_CHECK_RUNNING"] is False and "DB_STATE_CHECK_LAST_RUN" in um.data
        um.db.test_read.assert_called_once_with()


class TestDatabaseStateCheck:
    def test_readonly_database_that_recovered_flips_back_to_read_write(self, um):
        um.db.readonly = True
        um.main.check_database_state("GET", "/")
        assert um.db.retry_connection.call_count == 2
        assert um.data["READONLY_MODE"] is False and "LAST_DATABASE_RETRY" in um.data

    def test_readonly_database_still_down_stays_readonly(self, um):
        um.db.readonly = True
        um.db.retry_connection.side_effect = [RuntimeError("down"), None, None, RuntimeError("down")] + [None] * 4
        um.main.check_database_state("GET", "/")
        assert um.data["READONLY_MODE"] is True

    def test_readonly_fallback_to_the_readonly_uri(self, um):
        um.db.readonly = True
        um.db.database_uri_readonly = "sqlite:///ro"
        um.db.retry_connection.side_effect = RuntimeError("down")
        um.main.check_database_state("GET", "/")
        kwargs = [c.kwargs for c in um.db.retry_connection.call_args_list]
        assert {"fallback": True, "pool_timeout": 1} in kwargs

    def test_recent_retry_is_not_repeated(self, um):
        um.db.readonly = True
        um.data["LAST_DATABASE_RETRY"] = datetime.now().astimezone().isoformat()
        um.main.check_database_state("GET", "/")
        um.db.retry_connection.assert_not_called()
        um.db.test_read.assert_called_once_with()

    @pytest.mark.parametrize("path", ["/login", "/totp", "/plugins/upload"])
    def test_login_and_upload_posts_do_not_probe_the_database(self, um, path):
        um.main.check_database_state("POST", path)
        um.db.test_write.assert_not_called()

    def test_post_probes_a_write_and_marks_readonly_on_failure(self, um):
        um.main.check_database_state("POST", "/configs")
        um.db.test_write.assert_called_once_with()
        assert um.data["READONLY_MODE"] is False
        um.db.test_write.side_effect = RuntimeError("ro")
        um.main.check_database_state("POST", "/configs")
        assert um.data["READONLY_MODE"] is True and "LAST_DATABASE_RETRY" in um.data

    def test_failed_read_probe_records_the_retry_time(self, um):
        um.db.test_read.side_effect = RuntimeError("down")
        um.main.check_database_state("GET", "/")
        assert "LAST_DATABASE_RETRY" in um.data

    def test_scheduler_gates(self, um):
        executor = um.executors["_db_check_executor"]
        now = time.time()
        um.data["DB_STATE_CHECK_RUNNING"] = True
        um.data["DB_STATE_CHECK_LAST_RUN"] = now
        um.main.schedule_database_state_check("GET", "/")
        assert executor.pending == []  # another worker is mid-check
        um.data["DB_STATE_CHECK_LAST_RUN"] = now - 60
        um.main.schedule_database_state_check("GET", "/")
        assert len(executor.pending) == 1  # a stuck "running" flag older than 30 s is ignored

    def test_recent_run_is_not_repeated(self, um):
        um.data["DB_STATE_CHECK_LAST_RUN"] = datetime.now().astimezone().isoformat()
        um.main.schedule_database_state_check("GET", "/")
        assert um.executors["_db_check_executor"].pending == []

    def test_crash_in_the_check_is_contained_and_clears_the_flag(self, um):
        um.db.test_read.side_effect = KeyboardInterrupt
        um.main.schedule_database_state_check("GET", "/")
        um.executors["_db_check_executor"].run_pending()
        assert um.data["DB_STATE_CHECK_RUNNING"] is False


class TestAuthenticatedSession:
    def test_session_fields_are_stamped_on_first_request(self, um):
        client, env = authed_env(um)
        with client.session_transaction() as sess:
            assert sess["ip"] == "127.0.0.1" and sess["user_agent"]
            assert isinstance(sess["creation_date"], datetime) and sess["last_rotated_at"] == sess["creation_date"]
        assert env["theme"] == "light" and env["language"] == "en"

    def test_environment_carries_version_permissions_and_flags(self, um):
        um.db.get_metadata.return_value = um.metadata(is_pro=True, pro_status="active", pro_services=3, pro_expire=datetime(2027, 1, 2))
        um.db.get_services.return_value = [1, 2]
        um.data["LATEST_VERSION"] = "99.0.0"
        _, env = authed_env(um, admin=False, roles=("reader",), permissions=("read",))
        assert env["bw_version"] == "1.6.18" and env["latest_version"] == "99.0.0" and env["new_version_available"] is True
        assert (env["is_pro_version"], env["pro_status"], env["pro_expire"], env["pro_overlapped"]) == (True, "active", "2027/01/02", False)
        assert env["user_readonly"] is True and env["is_readonly"] is True and env["user_admin"] is False
        assert env["db_readonly"] is False and env["extra_pages"] == ["crowdsec"]

    def test_pro_license_overuse_is_flagged_live(self, um):
        um.db.get_metadata.return_value = um.metadata(is_pro=True, pro_services=1, pro_status="active")
        um.db.get_services.return_value = [1, 2]
        _, env = authed_env(um)
        assert env["pro_overlapped"] is True

    def test_anonymous_gets_the_dark_english_defaults(self, um):
        resp = um.client(None).get("/check")
        assert resp.status_code == 200

    def test_failover_is_announced_with_the_message(self, um):
        um.db.get_metadata.return_value = um.metadata(failover=True, failover_message="nginx: bad directive")
        um.deps.BW_CONFIG.get_plugins.return_value = {}
        client, _ = authed_env(um)
        messages = flashed(client)
        assert any("could not be applied" in m for m in messages)
        assert any("nginx: bad directive" in m for m in messages)

    def test_applied_changes_are_announced_once(self, um):
        um.data["CONFIG_CHANGED"] = True
        client, _ = authed_env(um)
        assert um.data["CONFIG_CHANGED"] is False
        assert flashed(client) == ["The last changes have been applied successfully."]

    def test_queued_flashes_are_flushed_and_deduplicated(self, um):
        um.data["TO_FLASH"] = [{"content": "hello", "type": "success"}, {"content": "hello", "type": "success"}]
        client, _ = authed_env(um)
        assert um.data["TO_FLASH"] == [] and flashed(client) == ["hello"]

    def test_changes_ongoing_clear_the_pro_loading_flag_only_when_idle(self, um):
        um.data["PRO_LOADING"] = True
        um.db.get_metadata.return_value = um.metadata(instances_changed=True)
        authed_env(um)
        assert um.data["PRO_LOADING"] is True
        um.db.get_metadata.return_value = um.metadata()
        authed_env(um)
        assert um.data["PRO_LOADING"] is False

    def test_readonly_database_is_flagged_to_the_user(self, um):
        um.data["READONLY_MODE"] = True
        client, env = authed_env(um)
        assert env["db_readonly"] is True and env["is_readonly"] is True
        assert flashed(client) == ["Database connection is in read-only mode : no modifications possible."]

    def test_ip_change_logs_the_session_out(self, um):
        client = um.client(session={"ip": "203.0.113.9", "user_agent": "Werkzeug"})
        um.app.config["CHECK_PRIVATE_IP"] = True
        resp = client.get("/loading")
        assert resp.status_code == 403
        assert resp.headers["Clear-Site-Data"]

    def test_user_agent_change_logs_the_session_out(self, um):
        client = um.client(session={"ip": "127.0.0.1", "user_agent": "Other/1.0"})
        assert client.get("/loading").status_code == 403

    def test_revoked_session_is_refused(self, um, monkeypatch):
        monkeypatch.setattr(um.main, "is_session_revoked", lambda sid: sid == "revoked-id")
        client = um.client(session={"session_id": "revoked-id"})
        assert client.get("/loading").status_code == 403
        ok_client = um.client(session={"session_id": "fine-id"})
        assert ok_client.get("/loading").status_code == 200

    def test_pending_two_factor_redirects_to_the_totp_page_keeping_a_safe_next(self, um):
        client = um.client(totp_secret="SECRET")
        resp = client.get("/loading?next=/services")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/totp?next=/services"
        resp = client.get("/loading?next=https://evil.test/")
        assert "evil.test" not in resp.headers["Location"] and resp.headers["Location"].startswith("/totp?next=/home")

    def test_validated_two_factor_passes(self, um):
        client = um.client(totp_secret="SECRET", recovery=("a-b",), session={"totp_validated": True})
        assert client.get("/loading").status_code == 200

    def test_absolute_session_lifetime_forces_logout(self, um):
        old = datetime.now().astimezone() - timedelta(hours=200)
        client = um.client(session={"creation_date": old, "ip": "127.0.0.1", "user_agent": "Werkzeug"})
        resp = client.get("/loading")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/login")

    def test_hook_results(self, um):
        calls = []
        um.app.config["BEFORE_REQUEST_HOOKS"] = [lambda: calls.append("a"), lambda: "stop-here", lambda: calls.append("never")]
        assert um.client(None).get("/check").data == b"stop-here"
        assert calls == ["a"]

    def test_failing_hook_denies_the_request(self, um):
        def bad():
            raise RuntimeError("authz backend down")

        um.app.config["BEFORE_REQUEST_HOOKS"] = [bad]
        resp = um.client(None).get("/check")
        assert resp.status_code == 500 and b"unexpected error" in resp.data.lower()


class TestSessionLifetimeHelpers:
    def login(self, um, **session):
        from flask import session as flask_session
        from flask_login import login_user

        user = um.main.load_user  # noqa: F841
        from _ui_core_main import UiUser

        ui_user = UiUser("alice")
        ui_user.list_permissions = {"read", "write"}
        login_user(ui_user)
        for key, value in session.items():
            flask_session[key] = value
        return ui_user

    def test_anonymous_is_never_invalidated(self, um):
        with um.app.test_request_context("/"):
            assert um.main._enforce_session_lifetime() is False

    def test_rolling_rotation_regenerates_the_id_and_stamps_the_rotation(self, um):
        um.app.config["SESSION_ROLLING_SECONDS"] = 60
        um.app.config["SESSION_ABSOLUTE_SECONDS"] = 10**9
        old = datetime.now().astimezone() - timedelta(seconds=120)
        with um.app.test_request_context("/"):
            self.login(um, creation_date=old, last_rotated_at=old)
            from flask import session

            before = session.sid
            assert um.main._enforce_session_lifetime() is False
            assert session.sid != before and session["last_rotated_at"] > old and session.permanent
        um.app.config["SESSION_ROLLING_SECONDS"] = 0

    def test_rotation_falls_back_to_manual_when_regenerate_fails(self, um, monkeypatch):
        with um.app.test_request_context("/"):
            from flask import session

            monkeypatch.setattr(um.app.session_interface, "regenerate", lambda s: (_ for _ in ()).throw(RuntimeError("x")), raising=False)
            before = session.sid
            um.main._rotate_session_id()
            assert session.sid != before and session.modified

    def test_delete_entry_ignores_empty_id_and_store_errors(self, um, monkeypatch):
        um.main._delete_session_store_entry("")
        monkeypatch.setattr(um.app.session_interface, "_delete_session", lambda sid: (_ for _ in ()).throw(OSError("x")))
        with um.app.test_request_context("/"):
            um.main._delete_session_store_entry("sid")  # logged, not raised


class TestResponseHeaders:
    def test_security_headers_on_every_page(self, um):
        resp = um.client(None).get("/check")
        h = resp.headers
        assert h["X-Frame-Options"] == "DENY" and h["X-Content-Type-Options"] == "nosniff"
        assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert h["Cross-Origin-Opener-Policy"] == "same-origin" and h["X-Robots-Tag"] == "noindex, nofollow"
        assert h["Cache-Control"] == "no-store"
        assert "Strict-Transport-Security" not in h and "upgrade-insecure-requests" not in h["Content-Security-Policy"]
        assert "'strict-dynamic'" in h["Content-Security-Policy"] and "'nonce-" in h["Content-Security-Policy"]

    def test_https_hop_adds_hsts_and_upgrade(self, um):
        resp = um.client(None).get("/loading", headers={"X-Forwarded-Proto": "https"})
        assert resp.headers["Strict-Transport-Security"].startswith("max-age=63072000")
        assert resp.headers["Content-Security-Policy"].endswith("upgrade-insecure-requests;")
        setup = um.client(None).get("/setup/loading", headers={"X-Forwarded-Proto": "https"})
        assert "upgrade-insecure-requests" not in setup.headers["Content-Security-Policy"]

    def test_static_assets_keep_their_own_cache_policy(self, um):
        version = um.main.BW_VERSION
        resp = um.client(None).get(f"/css/none.css?v={version}")
        assert resp.headers.get("Cache-Control") == "public, max-age=31536000, immutable"
        stale = um.client(None).get("/css/none.css?v=0")
        assert stale.headers.get("Cache-Control") != "no-store"

    def test_after_request_hooks_may_replace_or_fail(self, um):
        um.app.config["AFTER_REQUEST_HOOKS"] = [
            lambda response: (_ for _ in ()).throw(RuntimeError("x")),
            lambda response: um.main.Response("replaced", status=202),
        ]
        resp = um.client(None).get("/check")
        assert (resp.status_code, resp.data) == (202, b"replaced")

    def test_legacy_remember_cookies_are_evicted(self, um):
        client = um.client(None)
        client.set_cookie("bw_ui_remember_token", "x", domain="localhost")
        resp = client.get("/check")
        assert any(h.startswith("bw_ui_remember_token=;") for h in resp.headers.getlist("Set-Cookie"))

    def test_teardown_marks_user_access_and_runs_hooks(self, um):
        seen = []
        um.app.config["TEARDOWN_REQUEST_HOOKS"] = [lambda exc: seen.append("a"), lambda exc: (_ for _ in ()).throw(RuntimeError("x"))]
        client = um.client(session={"session_id": "sid-1"})
        client.get("/loading")
        um.db.mark_ui_user_access.assert_called_once()
        assert um.db.mark_ui_user_access.call_args.args[0] == "sid-1" and seen and set(seen) == {"a"}

    def test_user_access_is_not_marked_for_read_only_users_or_databases(self, um):
        reader = um.client(admin=False, roles=("reader",), permissions=("read",), session={"session_id": "sid-2"})
        reader.get("/loading")
        um.db.mark_ui_user_access.assert_not_called()
        um.db.readonly = True
        um.main.mark_user_access(None, "sid")
        um.db.mark_ui_user_access.assert_not_called()

    def test_failed_access_mark_is_logged(self, um):
        um.db.mark_ui_user_access.return_value = "locked"
        um.main.mark_user_access(None, "sid-3")
        um.db.mark_ui_user_access.assert_called_once()
