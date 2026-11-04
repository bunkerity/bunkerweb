"""main.py: the routes defined next to the app (index, loading, security.txt, theme/language/columns, reload poll) and its handlers."""

import json
import time
from datetime import datetime

import pytest
from flask import session

from _ui_core_main import UiUser


def body(resp):
    return json.loads(resp.data)


class TestIndex:
    def test_no_admin_yet_goes_to_setup(self, um):
        resp = um.client(None).get("/")
        assert resp.status_code == 303 and resp.headers["Location"].endswith("/setup")

    def test_anonymous_goes_to_login(self, um):
        um.users["root"] = UiUser("root")
        resp = um.client(None).get("/")
        assert resp.status_code == 303 and resp.headers["Location"].endswith("/login")

    def test_signed_in_goes_home(self, um):
        resp = um.client("alice").get("/")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/home")


class TestLoading:
    def test_renders_with_a_sanitised_next(self, um):
        client = um.client()
        assert client.get("/loading?next=/services&message=Wait").data == b"rendered:loading.html"
        template, context = um.renders[-1]
        assert template == "loading.html" and context == {"message": "Wait", "next": "/services"}

    def test_defaults(self, um):
        um.client().get("/loading")
        assert um.renders[-1][1] == {"message": "Loading...", "next": "/home"}

    @pytest.mark.parametrize("target", ["https://evil.test/", "//evil.test", "javascript:alert(1)"])
    def test_external_next_is_a_400(self, um, target):
        assert um.client().get("/loading", query_string={"next": target}).status_code == 400

    def test_requires_login(self, um):
        resp = um.client(None).get("/loading")
        assert resp.status_code == 302 and "/login" in resp.headers["Location"]


class TestWellKnown:
    def test_security_txt_has_a_fresh_expiry_and_no_canonical_by_default(self, um):
        resp = um.client(None).get("/.well-known/security.txt")
        assert resp.status_code == 200 and resp.content_type == "text/plain; charset=utf-8"
        lines = resp.data.decode().splitlines()
        assert "Contact: mailto:security@bunkerity.com" in lines
        expires = datetime.fromisoformat(next(line for line in lines if line.startswith("Expires: "))[9:])
        assert (expires - datetime.now().astimezone()).days >= 364
        assert not any(line.startswith("Canonical:") for line in lines)

    def test_canonical_only_with_a_real_allowlist(self, um):
        um.app.config["ALLOWED_HOSTS"] = ["ui.example.com"]
        resp = um.client(None).get("/.well-known/security.txt", headers={"Host": "ui.example.com"})
        assert "Canonical: http://ui.example.com/.well-known/security.txt" in resp.data.decode()
        um.app.config["ALLOWED_HOSTS"] = ["*"]
        assert "Canonical" not in um.client(None).get("/.well-known/security.txt").data.decode()

    def test_redirects(self, um):
        resp = um.client(None).get("/security.txt")
        assert resp.status_code == 301 and resp.headers["Location"].endswith("/.well-known/security.txt")
        resp = um.client(None).get("/.well-known/change-password")
        assert resp.status_code == 302 and "/profile" in resp.headers["Location"]


class TestCheckReloading:
    def test_idle_clears_the_flag(self, um, monkeypatch):
        um.data.update({"RELOADING": True, "LAST_RELOAD": time.time() - 10})
        monkeypatch.setattr(um.main, "active_config_tasks", lambda: 0)
        assert body(um.client().get("/check_reloading")) == {"reloading": False}

    def test_running_tasks_raise_the_flag(self, um, monkeypatch):
        monkeypatch.setattr(um.main, "active_config_tasks", lambda: 2)
        um.data["LAST_RELOAD"] = time.time()
        assert body(um.client().get("/check_reloading")) == {"reloading": True}

    def test_changes_in_flight_keep_reloading(self, um, monkeypatch):
        monkeypatch.setattr(um.main, "active_config_tasks", lambda: 0)
        um.db.get_metadata.return_value = um.metadata(instances_changed=True)
        um.data.update({"RELOADING": True, "LAST_RELOAD": time.time() - 10})
        assert body(um.client().get("/check_reloading")) == {"reloading": True}

    def test_a_stuck_reload_is_forced_after_a_minute(self, um, monkeypatch):
        monkeypatch.setattr(um.main, "active_config_tasks", lambda: 0)
        um.db.get_metadata.return_value = um.metadata(instances_changed=True)
        um.data.update({"RELOADING": True, "LAST_RELOAD": time.time() - 120})
        assert body(um.client().get("/check_reloading")) == {"reloading": False}


class TestUserPreferences:
    def test_set_theme_updates_the_user(self, um):
        resp = um.client().post("/set_theme", data={"theme": "dark"})
        assert resp.status_code == 200 and body(resp) == {"message": "ok"}
        kwargs = um.db.update_ui_user.call_args.kwargs
        assert kwargs["theme"] == "dark" and kwargs["username"] == "alice" and kwargs["old_username"] == "alice"
        assert kwargs["password"] == b"hash" and kwargs["language"] == "en"

    @pytest.mark.parametrize(("form", "status"), [({"theme": "purple"}, 400)])
    def test_set_theme_validation(self, um, form, status):
        assert um.client().post("/set_theme", data=form).status_code == status
        um.db.update_ui_user.assert_not_called()

    def test_set_theme_readonly_and_failure(self, um):
        um.db.readonly = True
        assert um.client().post("/set_theme", data={"theme": "dark"}).status_code == 423
        um.db.readonly = False
        um.db.update_ui_user.return_value = "locked"
        resp = um.client().post("/set_theme", data={"theme": "dark"})
        assert resp.status_code == 500 and body(resp) == {"message": "Internal server error"}

    def test_set_language(self, um):
        resp = um.client().post("/set_language", data={"language": "FR"})
        assert resp.status_code == 200 and um.db.update_ui_user.call_args.kwargs["language"] == "fr"
        assert um.client().post("/set_language", data={"language": "xx"}).status_code == 400
        um.db.readonly = True
        assert um.client().post("/set_language", data={"language": "fr"}).status_code == 423
        um.db.readonly = False
        um.db.update_ui_user.return_value = "locked"
        assert um.client().post("/set_language", data={"language": "fr"}).status_code == 500

    def test_set_columns_preferences(self, um):
        table = next(iter(um.main.COLUMNS_PREFERENCES_DEFAULTS))
        column = next(iter(um.main.COLUMNS_PREFERENCES_DEFAULTS[table]))
        prefs = json.dumps({column: True})
        resp = um.client().post("/set_columns_preferences", data={"table_name": table, "columns_preferences": prefs})
        assert resp.status_code == 200
        um.db.update_ui_user_columns_preferences.assert_called_once_with("alice", table, {column: True})

    @pytest.mark.parametrize("form", ["bad-json", "unknown-table", "unknown-column"])
    def test_set_columns_preferences_rejections(self, um, form):
        table = next(iter(um.main.COLUMNS_PREFERENCES_DEFAULTS))
        data = {
            "bad-json": {"table_name": table, "columns_preferences": "{nope"},
            "unknown-table": {"table_name": "nope", "columns_preferences": "{}"},
            "unknown-column": {"table_name": table, "columns_preferences": json.dumps({"zzz": True})},
        }[form]
        assert um.client().post("/set_columns_preferences", data=data).status_code == 400
        um.db.update_ui_user_columns_preferences.assert_not_called()

    def test_set_columns_preferences_readonly_and_failure(self, um):
        table = next(iter(um.main.COLUMNS_PREFERENCES_DEFAULTS))
        um.db.readonly = True
        assert um.client().post("/set_columns_preferences", data={"table_name": table}).status_code == 400
        um.db.readonly = False
        um.db.update_ui_user_columns_preferences.return_value = "locked"
        assert um.client().post("/set_columns_preferences", data={"table_name": table}).status_code == 500

    def test_clear_notifications_empties_the_history(self, um):
        client = um.client(session={"flash_messages": [("m", "success", "t")]})
        assert client.post("/clear_notifications").status_code == 200
        with client.session_transaction() as sess:
            assert sess["flash_messages"] == []

    def test_reader_may_still_change_own_preferences_but_not_other_posts(self, um):
        reader = um.client("bob", admin=False, roles=("reader",), permissions=("read",))
        assert reader.post("/set_theme", data={"theme": "dark"}).status_code == 200
        assert reader.post("/set_columns_preferences", data={"table_name": "x"}).status_code in (200, 400)


class TestCsrfHandler:
    def run(self, um, method="POST", path="/services"):
        with um.app.test_request_context(path, method=method):
            return um.main.handle_csrf_error(None)

    def test_wizard_not_finished_lands_on_setup(self, um):
        resp = self.run(um)
        assert resp.status_code == 303 and "/setup?reason=session_expired" in resp.headers["Location"]

    def test_post_after_setup_lands_on_login_with_the_reason(self, um):
        um.users["root"] = UiUser("root")
        resp = self.run(um)
        assert resp.status_code == 303 and "/login?reason=session_expired" in resp.headers["Location"]
        assert resp.headers["Clear-Site-Data"]

    def test_get_keeps_the_plain_logout_redirect(self, um):
        um.users["root"] = UiUser("root")
        resp = self.run(um, method="GET")
        assert resp.status_code == 303 and resp.headers["Location"].endswith("/login")


class TestLoadUser:
    def test_unknown_user(self, um):
        with um.app.test_request_context("/"):
            assert um.main.load_user("ghost") is None

    def test_roles_and_permissions_are_attached(self, um):
        um.users["alice"] = UiUser("alice", roles=("admin", "reader"))
        with um.app.test_request_context("/"):
            user = um.main.load_user("alice")
        assert user.list_roles == ["admin", "reader"] and user.list_permissions == {"read", "write"}
        um.db.get_ui_role_permissions.assert_any_call("reader")

    def test_totp_user_gets_recovery_codes(self, um):
        um.users["alice"] = UiUser("alice", totp_secret="S", recovery=("aaaa-bbbb", "cccc-dddd"))
        with um.app.test_request_context("/"):
            assert um.main.load_user("alice").list_recovery_codes == ["aaaa-bbbb", "cccc-dddd"]

    def test_missing_recovery_codes_after_validation_are_flagged(self, um, monkeypatch):
        flashes = []
        monkeypatch.setattr(um.main, "flash", lambda message, category, **kw: flashes.append((str(message), category)))
        um.users["alice"] = UiUser("alice", totp_secret="S", recovery=())
        with um.app.test_request_context("/loading"):
            session["totp_validated"] = True
            um.main.load_user("alice")
        assert len(flashes) == 1 and flashes[0][1] == "error" and "/profile" in flashes[0][0]

    @pytest.mark.parametrize("path", ["/totp-disable", "/totp-refresh"])
    def test_no_reminder_on_the_pages_that_fix_it(self, um, monkeypatch, path):
        flashes = []
        monkeypatch.setattr(um.main, "flash", lambda *a, **k: flashes.append(a))
        um.users["alice"] = UiUser("alice", totp_secret="S", recovery=())
        with um.app.test_request_context(path):
            session["totp_validated"] = True
            um.main.load_user("alice")
        assert flashes == []


class TestContextProcessor:
    def run(self, um, **hooks):
        for key, value in hooks.items():
            um.app.config[key] = value
        with um.app.test_request_context("/"):
            return um.main.inject_variables()

    def test_plugin_scripts_and_styles_are_aggregated(self, um):
        env = self.run(
            um,
            CONTEXT_PROCESSOR_HOOKS=[lambda: {"a": 1}, lambda: None, lambda: {"b": 2}],
            SCRIPTS_HOOKS=[
                lambda: {"src": ["/a.js", {"src": "/m.js", "type": "module"}], "inline": ["x()", "", "y()"]},
                lambda: {"src": "/b.js", "inline": "z()"},
                lambda: None,
            ],
            STYLES_HOOKS=[lambda: {"href": ["/a.css"], "inline": ".x{}"}, lambda: {"href": "/b.css", "inline": [".y{}"]}, lambda: "not-a-dict"],
        )
        assert (env["a"], env["b"]) == (1, 2)
        assert env["extra_scripts"] == ["/a.js", {"src": "/m.js", "type": "module"}, "/b.js"]
        assert env["custom_js"] == ["x()", "y()", "z()"]
        assert env["extra_styles"] == ["/a.css", "/b.css"] and env["custom_css"] == [".x{}", ".y{}"]

    def test_failing_hooks_never_break_the_page(self, um):
        def boom():
            raise RuntimeError("x")

        env = self.run(um, CONTEXT_PROCESSOR_HOOKS=[boom], SCRIPTS_HOOKS=[boom], STYLES_HOOKS=[boom])
        assert env["extra_scripts"] == [] and env["custom_js"] == [] and env["extra_styles"] == [] and env["custom_css"] == []

    def test_environment_built_by_before_request_is_the_base(self, um):
        with um.app.test_request_context("/"):
            from flask import g

            g._env = {"extra_scripts": ["/seed.js"], "keep": True}
            env = um.main.inject_variables()
        assert env["extra_scripts"] == ["/seed.js"] and env["keep"] is True


class TestCustomUrlFor:
    def url(self, um, endpoint, **values):
        with um.app.test_request_context("/"):
            return um.app.jinja_env.globals["url_for"](endpoint, **values)

    def test_page_endpoints_are_resolved_through_their_blueprint(self, um):
        assert self.url(um, "home") == "/home"
        assert self.url(um, "services", x="1") == "/services?x=1"

    def test_plain_endpoints_stay_as_is(self, um):
        assert self.url(um, "check") == "/check"
        assert self.url(um, "loading") == "/loading"

    def test_static_files_are_versioned_but_directories_are_not(self, um):
        assert self.url(um, "static", filename="css/a.css") == f"/css/a.css?v={um.main.BW_VERSION}"
        assert "v=" not in self.url(um, "static", filename="img/flags/")

    def test_unbuildable_or_empty_endpoint_is_a_hash(self, um):
        assert self.url(um, "nonexistent") == "#"
        assert self.url(um, "") == "#"
