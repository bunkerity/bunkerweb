"""app/models/biscuit.py: the authorization middleware, driven through a real Flask app and real Biscuit tokens.

Tokens are minted by ``BiscuitTokenFactory`` and checked by ``BiscuitMiddleware`` with the real
``biscuit_auth`` engine, so a verdict here is the verdict production would reach. Only the page
renderer (no templates in a unit run), the logout view and the version file are replaced.
"""

from datetime import timedelta

import pytest
from biscuit_auth import AuthorizationError, BiscuitBuilder, KeyPair
from flask import Blueprint, Flask
from flask_login import LoginManager, UserMixin

from app.models import biscuit as biscuit_module
from app.models.biscuit import (
    RUN_LIMIT_ERROR,
    BiscuitMiddleware,
    BiscuitTokenFactory,
    _internal_error_response,
    _normalize_path,
    resolve_operation,
)

VERSION = "9.9.9"


class _User(UserMixin):
    def __init__(self, name="alice", admin=False, roles=("reader",)):
        self.name = name
        self.admin = admin
        self.list_roles = list(roles)

    def get_id(self):
        return self.name


def _public_hex(keypair):
    return "ed25519/" + keypair.public_key.to_bytes().hex()


def _private_hex(keypair):
    return "ed25519-private/" + keypair.private_key.to_bytes().hex()


@pytest.fixture
def env(tmp_path, monkeypatch):
    keypair = KeyPair()
    public_file = tmp_path / "public"
    public_file.write_text(_public_hex(keypair) + "\n")
    private_file = tmp_path / "private"
    private_file.write_text(_private_hex(keypair))
    monkeypatch.setattr(biscuit_module, "get_version", lambda: VERSION)
    monkeypatch.setattr(biscuit_module, "BISCUIT_PRIVATE_KEY_FILE", private_file)
    rendered = []
    monkeypatch.setattr(
        biscuit_module, "render_template", lambda template, **context: rendered.append((template, context)) or f"rendered:{template}:{context['error_code']}"
    )
    monkeypatch.setattr(biscuit_module, "logout_page", lambda: "logged-out")

    app = Flask("biscuit_test")
    app.secret_key = "k"
    app.config.update(BISCUIT_PUBLIC_KEY_PATH=str(public_file), CHECK_PRIVATE_IP=False)
    manager = LoginManager(app)
    users = {}
    manager.user_loader(users.get)

    middleware = BiscuitMiddleware(app)

    bans = Blueprint("bans", "bans")
    bans.add_url_rule("/bans/fetch", "bans_fetch", lambda: "fetched", methods=["POST"])
    app.register_blueprint(bans)
    app.add_url_rule("/", "home.home_page", lambda: "home", methods=["GET", "POST"])
    app.add_url_rule("/logout", "logout.logout_page", lambda: "bye")
    app.add_url_rule("/profile/edit", "profile_edit", lambda: "profile", methods=["GET", "POST"])
    app.add_url_rule("/set_theme", "set_theme", lambda: "theme", methods=["POST"])
    app.add_url_rule("/settings", "settings", lambda: "settings", methods=["GET", "POST"])
    app.add_url_rule("/css/site.css", "css", lambda: "css")

    class Env:
        pass

    e = Env()
    e.app, e.keypair, e.rendered, e.users, e.middleware, e.private_file, e.public_file = app, keypair, rendered, users, middleware, private_file, public_file

    def token(role="reader", user="alice", remote="127.0.0.1", key=None):
        factory = BiscuitTokenFactory(key if key is not None else keypair.private_key)
        with app.test_request_context("/", environ_base={"REMOTE_ADDR": remote}):
            return factory.create_token_for_role(role, user).to_base64()

    class _Client:
        """A test client that stamps every request with one REMOTE_ADDR."""

        def __init__(self, inner, remote):
            self.inner, self.remote = inner, remote

        def session_transaction(self):
            return self.inner.session_transaction()

        def get(self, *args, **kwargs):
            return self.inner.get(*args, environ_base={"REMOTE_ADDR": self.remote}, **kwargs)

        def post(self, *args, **kwargs):
            return self.inner.post(*args, environ_base={"REMOTE_ADDR": self.remote}, **kwargs)

    def client(token_str=None, user=None, remote="127.0.0.1"):
        c = _Client(app.test_client(), remote)
        with c.session_transaction() as sess:
            if token_str:
                sess["biscuit_token"] = token_str
            if user is not None:
                users[user.name] = user
                sess["_user_id"] = user.name
                sess["_fresh"] = True
        return c

    e.token, e.client = token, client
    return e


class TestResolveOperation:
    @pytest.mark.parametrize(
        ("method", "endpoint", "rule", "expected"),
        [
            ("GET", None, None, "read"),
            ("POST", None, "/settings", "write"),
            ("POST", "bans.bans_fetch", "/whatever", "read"),
            ("POST", "reports.report_data_fetch", None, "read"),
            ("POST", None, "/reports//fetch/", "read"),
            ("POST", None, "/reports/data", "read"),
            ("POST", "bans.bans_ban", "/bans/ban", "write"),
            ("DELETE", None, "/x", "read"),
            ("OPTIONS", None, None, "read"),
        ],
    )
    def test_operation_table(self, method, endpoint, rule, expected):
        assert resolve_operation(method, "/p", endpoint, rule) == expected

    def test_normalize_path_collapses_slashes(self):
        assert _normalize_path("//reports///fetch/") == "/reports/fetch"
        assert _normalize_path("") == "/"


class TestTokenFactory:
    @pytest.mark.parametrize("role", ["super_admin", "admin", "writer", "reader"])
    def test_known_roles_build_tokens(self, env, role):
        assert env.token(role)

    def test_unknown_role_is_refused(self, env):
        with pytest.raises(ValueError, match="Unknown role: root"):
            env.token("root")

    def test_token_carries_client_ip_and_user(self, env):
        factory = BiscuitTokenFactory(env.keypair.private_key)
        with env.app.test_request_context("/", environ_base={"REMOTE_ADDR": "10.1.2.3"}, headers={"Host": "h" * 400}):
            token = factory.create_token_for_role("reader", 'ev"il')
        text = str(token)
        assert "10.1.2.3" in text and "h" * 255 in text and "h" * 256 not in text
        assert VERSION in text and 'ev\\"il' in text


class TestInitApp:
    def test_missing_config_key_is_refused(self):
        app = Flask("x")
        with pytest.raises(ValueError, match="BISCUIT_PUBLIC_KEY_PATH must be set"):
            BiscuitMiddleware(app)

    def test_unreadable_key_file_is_refused(self, tmp_path):
        bad = tmp_path / "pub"
        bad.write_text("not-a-key")
        app = Flask("x")
        app.config["BISCUIT_PUBLIC_KEY_PATH"] = str(bad)
        with pytest.raises(ValueError, match="Failed to load public key"):
            BiscuitMiddleware(app)

    def test_absent_key_file_leaves_no_root_key(self, tmp_path):
        app = Flask("x")
        app.config["BISCUIT_PUBLIC_KEY_PATH"] = str(tmp_path / "missing")
        assert BiscuitMiddleware(app).root_public_key is None

    def test_middleware_registers_itself_and_the_hook(self, env):
        assert env.app.biscuit_middleware is env.middleware
        assert env.middleware._check_authorization in env.app.before_request_funcs[None]


class TestAuthorization:
    def test_static_and_logout_paths_skip_the_check(self, env):
        client = env.client("garbage-token")
        assert client.get("/css/site.css").status_code == 200
        assert client.get("/logout").status_code == 200

    def test_anonymous_without_token_passes_through(self, env):
        assert env.client().get("/").data == b"home"

    def test_reader_may_read_but_not_write(self, env):
        client = env.client(env.token("reader"))
        assert client.get("/settings").data == b"settings"
        denied = client.post("/settings")
        assert denied.status_code == 403
        assert denied.data == b"rendered:unauthorized.html:403"
        assert env.rendered[-1][1]["message"] == "You are not authorized to perform this action."

    def test_denied_read_uses_the_read_message(self, env):
        no_read = BiscuitBuilder('user({user}); client_ip({ip}); version({version}); role("nobody", []);', {"user": "u", "ip": "127.0.0.1", "version": VERSION})
        token = no_read.build(env.keypair.private_key).to_base64()
        denied = env.client(token).get("/settings")
        assert denied.status_code == 403
        assert env.rendered[-1][1]["message"] == "You are not authorized to access this resource."

    @pytest.mark.parametrize("role", ["super_admin", "admin", "writer"])
    def test_writers_may_write(self, env, role):
        assert env.client(env.token(role)).post("/settings").data == b"settings"

    def test_profile_and_theme_are_open_to_readers_for_writes(self, env):
        client = env.client(env.token("reader"))
        assert client.post("/profile/edit").status_code == 200
        assert client.post("/set_theme").status_code == 200

    def test_read_only_post_endpoint_is_a_read(self, env):
        assert env.client(env.token("reader")).post("/bans/fetch").data == b"fetched"

    def test_garbage_token_redirects_to_logout(self, env):
        resp = env.client("not-base64!!").get("/settings")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/logout")

    def test_token_from_another_key_is_rejected(self, env):
        foreign = env.token("admin", key=KeyPair().private_key)
        resp = env.client(foreign).get("/settings")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/logout")

    def test_stale_version_redirects_to_logout(self, env, monkeypatch):
        token = env.token("admin")
        monkeypatch.setattr(biscuit_module, "get_version", lambda: "10.0.0")
        resp = env.client(token).get("/settings")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/logout")

    def test_client_ip_mismatch_is_rejected_for_public_addresses(self, env):
        token = env.token("admin", remote="8.8.8.8")
        resp = env.client(token, remote="1.1.1.1").get("/settings")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/logout")
        assert env.client(token, remote="8.8.8.8").get("/settings").status_code == 200

    def test_private_addresses_skip_ip_pinning_unless_configured(self, env):
        token = env.token("admin", remote="10.0.0.1")
        assert env.client(token, remote="10.0.0.2").get("/settings").status_code == 200
        env.app.config["CHECK_PRIVATE_IP"] = True
        assert env.client(token, remote="10.0.0.2").get("/settings").status_code == 302

    def test_run_limit_in_version_check_keeps_the_session(self, env, monkeypatch):
        monkeypatch.setattr(biscuit_module, "AUTHORIZE_MAX_TIME", timedelta(0))
        resp = env.client(env.token("admin")).get("/settings")
        assert resp.status_code == 500
        assert resp.data == b"rendered:unauthorized.html:500"

    def test_run_limit_in_policy_check_is_a_500_not_a_403(self, env, monkeypatch):
        real = biscuit_module._raise_limits
        calls = []

        def only_second(authorizer):
            calls.append(1)
            if len(calls) == 2:
                monkeypatch.setattr(biscuit_module, "AUTHORIZE_MAX_TIME", timedelta(0))
            real(authorizer)

        monkeypatch.setattr(biscuit_module, "_raise_limits", only_second)
        resp = env.client(env.token("admin")).get("/settings")
        assert (resp.status_code, len(calls)) == (500, 2)

    def test_run_limit_error_text_is_the_engine_message(self, env, monkeypatch):
        monkeypatch.setattr(biscuit_module, "AUTHORIZE_MAX_TIME", timedelta(0))
        builder = biscuit_module.AuthorizerBuilder()
        builder.add_policy(biscuit_module.Policy("allow if true"))
        biscuit_module._raise_limits(builder)
        token = biscuit_module.Biscuit.from_base64(env.token("admin"), env.middleware.root_public_key)
        with pytest.raises(AuthorizationError) as excinfo:
            builder.build(token).authorize()
        assert str(excinfo.value) == RUN_LIMIT_ERROR

    def test_unexpected_error_in_version_check_redirects(self, env, monkeypatch):
        token = env.token("admin")
        monkeypatch.setattr(biscuit_module, "get_version", lambda: (_ for _ in ()).throw(OSError("no VERSION")))
        resp = env.client(token).get("/settings")
        assert resp.status_code == 302 and resp.headers["Location"].endswith("/logout")

    def test_unexpected_error_in_policy_check_is_a_500_not_a_logout(self, env, monkeypatch):
        calls = {"n": 0}
        real = biscuit_module.Fact

        def flaky(*args, **kwargs):
            calls["n"] += 1
            raise RuntimeError("boom")

        monkeypatch.setattr(biscuit_module, "Fact", flaky)
        resp = env.client(env.token("admin")).get("/settings")
        assert resp.status_code == 500 and calls["n"] == 1
        monkeypatch.setattr(biscuit_module, "Fact", real)

    def test_internal_error_response_shape(self, env):
        with env.app.test_request_context("/"):
            body, status = _internal_error_response()
        assert status == 500 and body == "rendered:unauthorized.html:500"
        context = env.rendered[-1][1]
        assert context["auto_redirect"] is False and context["next"] == "/"


class TestTokenRegeneration:
    def test_missing_token_for_authenticated_user_is_regenerated(self, env):
        client = env.client(user=_User("alice", roles=("reader",)))
        assert client.get("/settings").status_code == 200
        with client.session_transaction() as sess:
            assert sess["biscuit_token"]
        assert client.post("/settings").status_code == 403  # the regenerated token carries the reader role

    def test_admin_regenerates_super_admin(self, env):
        client = env.client(user=_User("root", admin=True))
        assert client.post("/settings").status_code == 200

    def test_no_private_key_file_logs_out_with_403(self, env):
        env.private_file.unlink()
        resp = env.client(user=_User()).get("/settings")
        assert (resp.status_code, resp.data) == (403, b"logged-out")

    def test_unusable_private_key_logs_out_with_403(self, env):
        env.private_file.write_text("garbage")
        resp = env.client(user=_User()).get("/settings")
        assert (resp.status_code, resp.data) == (403, b"logged-out")

    def test_user_without_roles_logs_out_with_403(self, env):
        resp = env.client(user=_User(roles=())).get("/settings")
        assert (resp.status_code, resp.data) == (403, b"logged-out")
