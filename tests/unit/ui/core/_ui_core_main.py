"""Loads ``src/ui/main.py`` for real inside the unit venv, with its I/O pointed at ``tmp_path``.

What is replaced, and why it is safe:

* ``app.dependencies``: a stub module (mock ``DB``, dict-backed ``DATA``, tmp plugin directories); the
  real one builds a ``UIDatabase`` and reads ``/usr/share`` and ``/var/tmp`` at import.
* ``psutil``, ``user_agents``, ``flask_wtf``, ``passlib`` (through ``app.models.totp``): third-party
  packages shipped in the UI image but not in the unit pins. ``CSRFProtect`` is a no-op, so CSRF
  *enforcement* is not covered here; the ``CSRFError`` handler is.
* ``app.utils.LIB_DIR`` / ``BISCUIT_PUBLIC_KEY_FILE``: tmp copies holding a real Biscuit key pair and
  Flask secret, so the real session store, Biscuit middleware and Flask-Login all run.

``main`` installs SIGINT/SIGTERM handlers and an ``atexit`` hook at import; both are undone in ``close``.
"""

import atexit
import signal
import sys
from concurrent.futures import Future
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

from flask_login import UserMixin

UI_ROOT = Path(__file__).resolve().parents[4] / "src" / "ui"
STUBBED = ("psutil", "user_agents", "flask_wtf", "flask_wtf.csrf", "passlib", "passlib.totp", "passlib.pwd")
VERSION = "1.6.18"


class InlineExecutor:
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args, **kwargs):
        self.submitted.append(fn)
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            future.set_exception(exc)
        return future

    def shutdown(self, wait=False):
        pass


class DeferredExecutor(InlineExecutor):
    """Queues work instead of running it: ``schedule_database_state_check`` submits while it holds a non-reentrant lock its task also takes."""

    def __init__(self):
        super().__init__()
        self.pending = []

    def submit(self, fn, *args, **kwargs):
        self.submitted.append(fn)
        future = Future()
        self.pending.append((future, fn, args, kwargs))
        return future

    def run_pending(self):
        pending, self.pending = self.pending, []
        for future, fn, args, kwargs in pending:
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as exc:  # noqa: BLE001
                future.set_exception(exc)


class FakeData(dict):
    """``UIData`` without the file."""

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.loads = 0

    def load_from_file(self):
        self.loads += 1

    def write_to_file(self):
        pass


class UiUser(UserMixin):
    def __init__(self, username="alice", *, admin=True, roles=("admin",), permissions=("read", "write"), totp_secret=None, recovery=(), **extra):
        self.username = username
        self.admin = admin
        self.roles = [SimpleNamespace(role_name=role) for role in roles]
        self.permissions = list(permissions)
        self.totp_secret = totp_secret
        self.recovery_codes = [SimpleNamespace(code=code) for code in recovery]
        self.theme, self.language, self.email, self.method = "light", "en", None, "ui"
        self.password = "hash"
        for key, value in extra.items():
            setattr(self, key, value)

    def get_id(self):
        return self.username


def _stub_third_party():
    stubs = {}
    psutil = ModuleType("psutil")
    psutil.virtual_memory = lambda: SimpleNamespace(total=8 * 1024**3, available=4 * 1024**3, percent=50.0, used=4 * 1024**3)
    user_agents = ModuleType("user_agents")
    user_agents.parse = lambda raw: SimpleNamespace(get_browser=lambda: raw, get_os=lambda: raw, get_device=lambda: raw)

    class CSRFError(Exception):
        description = "csrf"

    class CSRFProtect:
        def init_app(self, app):
            app.extensions["csrf"] = self

    flask_wtf = ModuleType("flask_wtf")
    csrf = ModuleType("flask_wtf.csrf")
    csrf.CSRFProtect, csrf.CSRFError = CSRFProtect, CSRFError
    flask_wtf.csrf = csrf
    passlib = ModuleType("passlib")
    plt = ModuleType("passlib.totp")
    for name in ("TOTP", "MalformedTokenError", "TokenError", "TotpMatch"):
        setattr(plt, name, type(name, (Exception,), {}))
    plp = ModuleType("passlib.pwd")
    plp.genword = lambda **kwargs: []
    stubs.update(
        {
            "psutil": psutil,
            "user_agents": user_agents,
            "flask_wtf": flask_wtf,
            "flask_wtf.csrf": csrf,
            "passlib": passlib,
            "passlib.totp": plt,
            "passlib.pwd": plp,
        }
    )
    return {name: module for name, module in stubs.items() if _missing(name)}


def _missing(name):
    if name in sys.modules:
        return False
    try:
        import_module(name)
    except ImportError:
        return True
    return False


class LoadedMain:
    def __init__(self, tmp_dir):
        from biscuit_auth import KeyPair

        self.tmp = Path(tmp_dir)
        self.lib = self.tmp / "lib"
        self.lib.mkdir()
        keypair = KeyPair()
        (self.lib / ".biscuit_public_key").write_text("ed25519/" + keypair.public_key.to_bytes().hex())
        (self.lib / ".biscuit_private_key").write_text("ed25519-private/" + keypair.private_key.to_bytes().hex())
        (self.lib / ".flask_secret").write_text("unit-test-secret\n")

        self.deps = ModuleType("app.dependencies")
        self.deps.DB = MagicMock(name="DB")
        self.deps.DATA = FakeData(self.tmp / "ui_data.json")
        self.deps.BW_CONFIG = MagicMock(name="BW_CONFIG")
        self.deps.BW_CONFIG.get_config.return_value = {}
        self.deps.BW_INSTANCES_UTILS = MagicMock(name="BW_INSTANCES_UTILS")
        self.deps.CONFIG_TASKS_EXECUTOR = InlineExecutor()
        self.deps.PAGE_TASKS_EXECUTOR = InlineExecutor()
        for name in ("core", "external", "pro"):
            (self.tmp / name).mkdir()
        self.deps.CORE_PLUGINS_PATH = self.tmp / "core"
        self.deps.EXTERNAL_PLUGINS_PATH = self.tmp / "external"
        self.deps.PRO_PLUGINS_PATH = self.tmp / "pro"
        self.deps.reload_plugins = MagicMock(name="reload_plugins", return_value="")
        self.deps.safe_reload_plugins = MagicMock(name="safe_reload_plugins", return_value="")
        self.db, self.data = self.deps.DB, self.deps.DATA

        self._snapshot = {
            name: module for name, module in sys.modules.items() if name == "main" or name.startswith(("app.routes", "app.dependencies", "app.models.totp"))
        }
        self._signals = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        self._stubs = _stub_third_party()
        sys.modules.update(self._stubs)
        for name in [n for n in sys.modules if n == "main" or n.startswith("app.routes")]:
            del sys.modules[name]
        totp_module = ModuleType("app.models.totp")
        totp_module.totp = MagicMock(name="TOTP")
        sys.modules["app.models.totp"] = totp_module
        sys.modules["app.dependencies"] = self.deps

        import common_utils

        self._patches = []

        def patch(target, name, value):
            self._patches.append((target, name, getattr(target, name)))
            setattr(target, name, value)

        utils = import_module("app.utils")
        patch(common_utils, "get_version", lambda: VERSION)
        patch(utils, "LIB_DIR", self.lib)
        patch(utils, "BISCUIT_PUBLIC_KEY_FILE", self.lib / ".biscuit_public_key")
        patch(utils, "BISCUIT_PRIVATE_KEY_FILE", self.lib / ".biscuit_private_key")
        biscuit = import_module("app.models.biscuit")
        patch(biscuit, "BISCUIT_PRIVATE_KEY_FILE", self.lib / ".biscuit_private_key")
        patch(biscuit, "get_version", lambda: VERSION)

        spec = spec_from_file_location("main", UI_ROOT / "main.py")  # by path: src/common/gen/main.py also exists
        self.main = module_from_spec(spec)
        sys.modules["main"] = self.main
        spec.loader.exec_module(self.main)
        atexit.unregister(self.main._shutdown_executors)
        for sig, handler in self._signals.items():
            signal.signal(sig, handler)
        # Before any request: these would otherwise start real threads, hit GitHub, or `kill` a gunicorn pid
        self.restart_workers = MagicMock(name="restart_workers")
        self.stop = MagicMock(name="stop")
        self.main.restart_workers = self.restart_workers
        self.main.stop = self.stop
        self.main.get_latest_stable_release = MagicMock(name="get_latest_stable_release", return_value="9.9.9")
        self.executors = {}
        for name in ("_db_check_executor", "_periodic_tasks_executor", "_user_access_executor", "_config_tasks_executor"):
            self.executors[name] = DeferredExecutor() if name == "_db_check_executor" else InlineExecutor()
            setattr(self.main, name, self.executors[name])
        self.app = self.main.app
        self._add_probe()
        self.app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
        self.renders = []
        self.envs = []
        self.main.render_template = self._render
        self.users = {}
        self.main.login_manager.user_loader(self._load_user_hook)

    def _add_probe(self):
        """``/__probe`` echoes the page environment ``before_request`` built (``g._env``) as JSON."""
        from flask import g, jsonify

        app = self.app
        app.add_url_rule("/__probe", "probe", lambda: jsonify(dict(g._env)) if g.get("_env") else "no-env", methods=["GET", "POST"])

    def _render(self, template, **context):
        from flask import g

        self.renders.append((template, context))
        self.envs.append(dict(getattr(g, "_env", {})))
        return f"rendered:{template}"

    def _load_user_hook(self, username):
        return self.main.load_user(username)

    def close(self):
        for target, name, value in reversed(self._patches):
            setattr(target, name, value)
        for sig, handler in self._signals.items():
            signal.signal(sig, handler)
        for name in [n for n in sys.modules if n == "main" or n.startswith(("app.routes", "app.dependencies", "app.models.totp"))]:
            del sys.modules[name]
        sys.modules.update(self._snapshot)
        for name in self._stubs:
            sys.modules.pop(name, None)

    # ----- per-test state -------------------------------------------------------------------

    def metadata(self, **overrides):
        base = {
            "reload_ui_plugins": False,
            "custom_configs_changed": False,
            "external_plugins_changed": False,
            "pro_plugins_changed": False,
            "plugins_config_changed": False,
            "instances_changed": False,
            "failover": False,
            "failover_message": "",
            "pro_overlapped": False,
            "is_pro": False,
            "pro_services": 0,
            "pro_status": "invalid",
            "pro_expire": None,
            "version": VERSION,
        }
        base.update(overrides)
        return base

    def reset(self):
        from datetime import datetime

        db = self.db
        db.reset_mock(return_value=True, side_effect=True)
        db.database_uri, db.database_uri_readonly, db.readonly, db.last_connection_retry = "sqlite:///unit", None, False, None
        db.get_metadata.return_value = self.metadata()
        db.get_config.return_value = {}
        db.get_services.return_value = []
        db.update_ui_user.return_value = ""
        db.update_ui_user_columns_preferences.return_value = ""
        db.mark_ui_user_access.return_value = ""
        self.users = {}
        db.get_ui_user.side_effect = lambda username=None: self.users.get(username) if username else (next(iter(self.users.values()), None))
        db.get_ui_role_permissions.side_effect = lambda role: ["read", "write"] if role != "reader" else ["read"]
        self.deps.BW_CONFIG.reset_mock(return_value=True, side_effect=True)
        self.deps.BW_CONFIG.get_config.return_value = {}
        self.deps.BW_CONFIG.get_plugins.return_value = {}
        self.deps.safe_reload_plugins.reset_mock(return_value=True, side_effect=True)
        self.deps.safe_reload_plugins.return_value = ""
        self.restart_workers.reset_mock()
        self.stop.reset_mock()
        self.main.get_latest_stable_release.reset_mock()
        for executor in self.executors.values():
            executor.submitted.clear()
        self.executors["_db_check_executor"].pending.clear()
        self.data.clear()
        self.data["LATEST_VERSION_LAST_CHECK"] = datetime.now().astimezone().isoformat()
        self.data["LATEST_VERSION"] = VERSION
        self.renders.clear()
        self.envs.clear()
        main = self.main
        main._db_check_future, main._db_check_next_allowed = None, 0.0
        main._restart_workers_future, main._restart_workers_next_allowed = None, 0.0
        main._session_cleanup_last_run = 0.0
        main._session_cleanup_last_run = __import__("time").time()  # no cleanup submit unless a test asks for it
        self.app.config["ALLOWED_HOSTS"] = []
        for hook_info in main.HOOKS.values():
            self.app.config[hook_info["key"]] = []

    def client(self, user="alice", *, session=None, **user_kwargs):
        """A test client signed in as ``user`` (``None`` stays anonymous); ``session`` seeds extra session keys."""
        client = self.app.test_client()
        if user is not None:
            ui_user = user if isinstance(user, UiUser) else UiUser(user, **user_kwargs)
            self.users[ui_user.username] = ui_user
            with client.session_transaction() as sess:
                sess["_user_id"] = ui_user.username
                sess["_fresh"] = True
                for key, value in (session or {}).items():
                    sess[key] = value
        elif session:
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value
        return client
