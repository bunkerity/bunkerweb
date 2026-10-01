"""Web UI session plumbing: cookie name, backend fallback, error pages, access marking (FIX-B).

H10  A gunicorn max_requests recycle logged the user out. flask-session opens the session before
     before_request runs, and the worker only switched its cookie name from the `__Host-` default to
     `bw_ui_session` inside before_request, on its first request. So the first request of every
     fresh worker was read under the wrong name, came up anonymous, and its response overwrote the
     user's cookie. The name is now chosen per request, at open and at save.
H18  On a first start the worker picked file sessions before the scheduler stored USE_REDIS; the
     next worker boot moved to Redis and found none of them. Redis now reads the sessions it lacks
     from the file store (and drops the file copy on write/delete), and gunicorn waits for the
     scheduler's first saved configuration before forking workers.
H17  Every cookieless request (a /healthcheck probe included) cached per-user state in a new
     session: a 12 h key in the non-evicting broker per hit. Anonymous requests get the neutral env.
M17  mark_user_access got the `current_user` proxy in an executor thread, where it is None.
B5   The Biscuit 403 rendered `unauthorized.html` before main's before_request minted the CSP
     nonce: every `<script nonce="">` was blocked. M14: there was no 404 page at all.

The modules pull in qrcode, Flask-Session and BW_CONFIG at import time, none of which the unit venv
carries, so the shipped definitions are spliced out of the source by name and executed here, as
`test_session_storage_throttle.py` does. Renaming or deleting one fails the extraction.
"""

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from pathlib import Path
from secrets import token_urlsafe
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple
from unittest.mock import Mock

import pytest
from flask import Flask, g, request, session
from flask.sessions import SessionInterface, SessionMixin
from flask_login import LoginManager, UserMixin, current_user, login_user
from werkzeug.datastructures import CallbackDict

_UI = Path(__file__).resolve().parents[3] / "src" / "ui"
UTILS = _UI / "app" / "routes" / "utils.py"
BISCUIT = _UI / "app" / "models" / "biscuit.py"
MAIN = _UI / "main.py"
GUNICORN = _UI / "utils" / "gunicorn.conf.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _shipped(path: Path, names, namespace: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the named top-level definitions of `path` in `namespace`, in source order."""
    wanted = set(names)
    nodes = [
        node
        for node in _tree(path).body
        if (isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted)
        or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in wanted for t in node.targets))
    ]
    found = {node.name if not isinstance(node, ast.Assign) else node.targets[0].id for node in nodes}
    assert found == wanted, f"missing from {path.name}: {sorted(wanted - found)}"
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)  # noqa: S102
    return namespace


def _function(path: Path, name: str) -> ast.FunctionDef:
    return next(node for node in _tree(path).body if isinstance(node, ast.FunctionDef) and node.name == name)


# --------------------------------------------------------------------------------------------
# A stand-in for flask-session 0.8's server-side interface: same storage primitives, and the same
# two cookie reads that matter here, quoted from flask_session/base.py:
#   open_session:  sid = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
#   save_session:  name = self.get_cookie_name(app) ... secure = self.get_cookie_secure(app)
# --------------------------------------------------------------------------------------------
class _Session(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid=None):
        def on_update(self):
            self.modified = True

        super().__init__(initial, on_update)
        self.sid = sid
        self.modified = False


class FakeServerSideInterface(SessionInterface):
    def __init__(self, key_prefix: str):
        self.key_prefix = key_prefix
        self.store: Dict[str, dict] = {}

    def _get_store_id(self, sid: str) -> str:
        return self.key_prefix + sid

    def _retrieve_session_data(self, store_id: str) -> Optional[dict]:
        return self.store.get(store_id)

    def _upsert_session(self, session_lifetime, session, store_id: str) -> None:
        self.store[store_id] = dict(session)

    def _delete_session(self, store_id: str) -> None:
        self.store.pop(store_id, None)

    def open_session(self, app, request):
        sid = request.cookies.get(app.config["SESSION_COOKIE_NAME"])
        if not sid:
            return _Session(sid=token_urlsafe(16))
        data = self._retrieve_session_data(self._get_store_id(sid))
        return _Session(data, sid=sid) if data is not None else _Session(sid=token_urlsafe(16))

    def save_session(self, app, session, response):
        name = self.get_cookie_name(app)
        if not session:
            return
        self._upsert_session(None, session, self._get_store_id(session.sid))
        response.set_cookie(name, session.sid, secure=self.get_cookie_secure(app), httponly=True)


def _utils_namespace():
    return _shipped(
        UTILS,
        ("PROXIED_SESSION_COOKIE", "DIRECT_SESSION_COOKIE", "session_cookie_for", "bind_session_cookie_per_request", "chain_session_fallback"),
        {"Any": Any, "Dict": Dict, "Tuple": Tuple, "SimpleNamespace": SimpleNamespace, "request": request},
    )


def _fresh_worker(interface):
    """A just-booted UI worker: main.py's config, and no request served yet."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
    app.config["SESSION_COOKIE_SECURE"] = True
    app.session_interface = interface
    _utils_namespace()["bind_session_cookie_per_request"](interface)

    @app.route("/whoami")
    def whoami():
        return session.get("user", "anonymous")

    return app


# ---------------------------------------------------------------------------------------- H10


def test_the_first_request_of_a_fresh_worker_keeps_a_direct_visitors_session():
    """The H10 logout: the recycled worker's very first request, direct (no proxy)."""
    interface = FakeServerSideInterface("bunkerweb_ui_session:")
    interface.store["bunkerweb_ui_session:SID"] = {"user": "admin"}
    client = _fresh_worker(interface).test_client()
    client.set_cookie("bw_ui_session", "SID")

    response = client.get("/whoami")

    assert response.get_data(as_text=True) == "admin"
    # Written back under the name the browser sent, and not Secure: this visit is plain http.
    [cookie] = response.headers.getlist("Set-Cookie")
    assert cookie.startswith("bw_ui_session=SID;") and "Secure" not in cookie


def test_a_proxied_request_uses_the_host_prefixed_secure_cookie():
    interface = FakeServerSideInterface("bunkerweb_ui_session:")
    interface.store["bunkerweb_ui_session:SID"] = {"user": "admin"}
    client = _fresh_worker(interface).test_client()
    client.set_cookie("__Host-bw_ui_session", "SID")

    response = client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.7"})

    assert response.get_data(as_text=True) == "admin"
    [cookie] = response.headers.getlist("Set-Cookie")
    assert cookie.startswith("__Host-bw_ui_session=SID") and "Secure" in cookie


def test_a_direct_first_request_does_not_choose_the_cookie_of_proxied_users():
    """The old per-worker latch: a direct probe first, then every proxied user was anonymous."""
    interface = FakeServerSideInterface("bunkerweb_ui_session:")
    interface.store["bunkerweb_ui_session:SID"] = {"user": "admin"}
    client = _fresh_worker(interface).test_client()
    client.get("/whoami")  # the probe
    client.set_cookie("__Host-bw_ui_session", "SID")

    assert client.get("/whoami", headers={"X-Forwarded-For": "203.0.113.7"}).get_data(as_text=True) == "admin"


def test_main_no_longer_switches_the_cookie_name_inside_before_request():
    before_request = ast.unparse(_function(MAIN, "before_request"))
    assert "SESSION_COOKIE_NAME" not in before_request
    assert "bind_session_cookie_per_request(app.session_interface)" in MAIN.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------- H18


def _chained():
    redis, files = FakeServerSideInterface("bunkerweb_ui_session:"), FakeServerSideInterface("session:")
    _utils_namespace()["chain_session_fallback"](redis, files)
    return redis, files


def test_redis_reads_a_session_only_the_file_store_has():
    redis, files = _chained()
    files.store["session:SID"] = {"user": "admin"}

    assert redis._retrieve_session_data("bunkerweb_ui_session:SID") == {"user": "admin"}


def test_redis_prefers_its_own_copy():
    redis, files = _chained()
    files.store["session:SID"] = {"user": "stale"}
    redis.store["bunkerweb_ui_session:SID"] = {"user": "admin"}

    assert redis._retrieve_session_data("bunkerweb_ui_session:SID") == {"user": "admin"}


def test_a_write_moves_the_session_to_redis():
    redis, files = _chained()
    files.store["session:SID"] = {"user": "admin"}

    redis._upsert_session(None, {"user": "admin"}, "bunkerweb_ui_session:SID")

    assert redis.store == {"bunkerweb_ui_session:SID": {"user": "admin"}} and files.store == {}


def test_a_logout_leaves_no_copy_to_read_back():
    redis, files = _chained()
    files.store["session:SID"] = {"user": "admin"}

    redis._delete_session("bunkerweb_ui_session:SID")

    assert redis._retrieve_session_data("bunkerweb_ui_session:SID") is None


def test_main_chains_the_file_store_behind_redis_and_deletes_through_the_interface():
    source = MAIN.read_text(encoding="utf-8")
    assert 'chain_session_fallback(app.session_interface, CacheLibSessionInterface(client=app.config["SESSION_CACHELIB"]))' in source
    assert "interface._delete_session(interface._get_store_id(sid))" in ast.unparse(_function(MAIN, "_delete_session_store_entry"))


def _wait_for_first_config():
    class ApiClientError(Exception):
        pass

    class ApiUnavailableError(Exception):
        pass

    sleeps = []
    namespace = _shipped(
        GUNICORN, ("_wait_for_first_config",), {"ApiClientError": ApiClientError, "ApiUnavailableError": ApiUnavailableError, "sleep": sleeps.append}
    )
    return namespace["_wait_for_first_config"], ApiUnavailableError, sleeps


def test_gunicorn_waits_for_the_first_saved_configuration():
    wait, unavailable, sleeps = _wait_for_first_config()
    answers = iter([unavailable("down"), {"metadata": {"first_config_saved": False}}, {"metadata": {"first_config_saved": True}}])

    def get(path):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    assert wait(SimpleNamespace(_get=get), Mock()) is True
    assert len(sleeps) == 2


def test_gunicorn_gives_up_rather_than_keeping_the_ui_down():
    wait, _, sleeps = _wait_for_first_config()
    api = SimpleNamespace(_get=lambda path: {"metadata": {"first_config_saved": False}})

    assert wait(api, Mock(), max_retries=3, delay=0) is False
    assert len(sleeps) == 2


def test_on_starting_waits_before_workers_read_use_redis():
    on_starting = ast.unparse(_function(GUNICORN, "on_starting"))
    assert "_wait_for_first_config(api_client, LOGGER)" in on_starting
    assert on_starting.index("_wait_for_first_config(") < on_starting.index("UI_SESSIONS_CACHE.mkdir")


# ---------------------------------------------------------------------------------------- H17


def test_anonymous_requests_get_the_neutral_env_and_cache_nothing_in_the_session():
    gate = next(
        node
        for node in ast.walk(_function(MAIN, "before_request"))
        if isinstance(node, ast.If) and "'/login'" in ast.unparse(node.test) and "g._env = base_env" in ast.unparse(node.body[0])
    )
    assert "not current_user.is_authenticated" in ast.unparse(gate.test)
    # Every per-user session write lives in the authenticated branch.
    for key in ("onboarding_active", "whatsnew_pending"):
        assert f"session['{key}'] =" in ast.unparse(ast.Module(body=gate.orelse, type_ignores=[]))


def test_login_page_env_carries_bw_version_for_the_catalog_cache_buster():
    """QA-UI-5 item 7: /locales/en.js?v=.d7624961b4a2 -- an empty version part. `base_env`

    (the neutral env the branch above sends to /login, /setup, /loading, /totp and every
    anonymous request) never set `bw_version`, so `inject_variables`'s
    `i18n_catalog_version = f"{app_env.get('bw_version', '')}.{fingerprint}"` always fell back
    to an empty string on exactly those pages, one being the highest-traffic anonymous page in
    the app. `metadata` is already fetched unconditionally for every non-static path a few
    lines above `base_env`, so this costs no extra API call.
    """
    before_request = _function(MAIN, "before_request")
    assign = next(
        node for node in ast.walk(before_request) if isinstance(node, ast.Assign) and len(node.targets) == 1 and ast.unparse(node.targets[0]) == "base_env"
    )
    keywords = {kw.arg: ast.unparse(kw.value) for kw in assign.value.keywords}
    assert keywords.get("bw_version") == "metadata.get('version', 'unknown')"


@pytest.mark.parametrize("authenticated", [False, True])
def test_plugin_context_processors_run_for_logged_in_renders_only(authenticated):
    """An anonymous 404 ran letsencrypt's hook, which stamped its orphan check into a new session."""
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", SCRIPTS_HOOKS=[], STYLES_HOOKS=[])

    def plugin_hook():
        session["_le_orphan_check_at"] = 1.0
        return {"plugin_value": 1}

    app.config["CONTEXT_PROCESSOR_HOOKS"] = [plugin_hook]
    user = SimpleNamespace(is_authenticated=authenticated)
    namespace = _shipped(MAIN, ("inject_variables",), {"app": app, "g": g, "current_user": user, "LOGGER": Mock(), "plugin_catalog_fingerprint": lambda: "fp"})

    with app.test_request_context("/nonexistent"):
        env = namespace["inject_variables"]()
        assert ("plugin_value" in env) is authenticated
        assert ("_le_orphan_check_at" in session) is authenticated


def test_core_catalog_content_changes_the_catalog_cache_version(tmp_path):
    from app.i18n import init_i18n

    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    catalog = locale_dir / "fr.json"
    catalog.write_text('{"delete":"Supprimer"}', encoding="utf-8")

    app = Flask(__name__, static_folder=str(tmp_path))
    app.config["SECRET_KEY"] = "test"
    init_i18n(app)
    namespace = _shipped(
        MAIN,
        ("inject_variables",),
        {
            "app": app,
            "g": g,
            "current_user": SimpleNamespace(is_authenticated=False),
            "LOGGER": Mock(),
            "plugin_catalog_fingerprint": lambda: "plugin-fp",
        },
    )

    with app.test_request_context("/"):
        session["language"] = "fr"
        g._env = {"bw_version": "1.7.0"}
        before = namespace["inject_variables"]()["i18n_catalog_version"]
        catalog.write_text('{"delete":"Supprimez maintenant"}', encoding="utf-8")
        after = namespace["inject_variables"]()["i18n_catalog_version"]

    assert after != before


# ---------------------------------------------------------------------------------------- M17


class _User(UserMixin):
    def __init__(self, username):
        self.id = username


def test_the_access_mark_reaches_the_api_from_the_executor_thread():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", TEARDOWN_REQUEST_HOOKS=[])
    LoginManager(app).user_loader(_User)
    executor = ThreadPoolExecutor(max_workers=1)
    api = Mock()
    namespace = _shipped(
        MAIN,
        ("mark_user_access", "teardown_request"),
        {
            "API_CLIENT": api,
            "DATA": {},
            "LOGGER": Mock(),
            "app": app,
            "perf": Mock(),
            "suppress": suppress,
            "is_static_path": lambda path: False,
            "current_user": current_user,
            "session": session,
            "request": request,
            "_user_access_executor": executor,
        },
    )

    assert namespace["teardown_request"] in app.teardown_request_funcs[None]  # registered by its own decorator
    with app.test_request_context("/home"):
        login_user(_User("admin"))
        session["session_id"] = 42
    executor.shutdown(wait=True)

    api.mark_user_access.assert_called_once_with("admin", 42)


# ---------------------------------------------------------------------------------- B5 / M14


def _biscuit(rendered):
    def render_template(name, **context):
        rendered.append((name, context))
        return "page"

    return _shipped(
        BISCUIT,
        ("render_error_page", "_internal_error_response"),
        {"Optional": Optional, "g": g, "token_urlsafe": token_urlsafe, "render_template": render_template, "url_for": lambda endpoint: "/home"},
    )


@pytest.mark.parametrize("call", ["render_error_page_403", "render_error_page_404", "_internal_error_response"])
def test_an_error_page_rendered_before_before_request_carries_the_csp_nonce(call):
    rendered = []
    namespace = _biscuit(rendered)
    with Flask(__name__).test_request_context("/instances/reload", method="POST"):
        assert "script_nonce" not in g  # the Biscuit check runs before main's before_request
        if call == "_internal_error_response":
            _, status = namespace["_internal_error_response"]()
        else:
            status_wanted = int(call.rsplit("_", 1)[1])
            _, status = namespace["render_error_page"](status_wanted)
            assert status == status_wanted
        [(template, context)] = rendered
        assert template == "unauthorized.html"
        # after_request puts g.script_nonce in the CSP header: page and header must agree.
        assert context["script_nonce"] and context["script_nonce"] == g.script_nonce


def test_an_error_page_reuses_the_nonce_before_request_minted():
    rendered = []
    with Flask(__name__).test_request_context("/nope"):
        g.script_nonce = "minted-by-before-request"
        _biscuit(rendered)["render_error_page"](404)
    assert rendered[0][1]["script_nonce"] == "minted-by-before-request"


def test_every_error_page_goes_through_the_one_helper():
    for path in sorted(_UI.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "unauthorized.html" in source:
            assert path == BISCUIT, f"{path} renders unauthorized.html itself"
    assert BISCUIT.read_text(encoding="utf-8").count("render_template(") == 1
    handler = next(
        node
        for node in _tree(MAIN).body
        if isinstance(node, ast.FunctionDef) and any("errorhandler(404)" in ast.unparse(decorator) for decorator in node.decorator_list)
    )
    assert "render_error_page(404)" in ast.unparse(handler)
