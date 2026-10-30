"""Harness for the UI route blueprints.

``app.dependencies`` builds a real ``UIDatabase`` at import time (it waits for a SQLite file that
never appears), so it is replaced by a stub module for the duration of one test module's imports.
Every blueprint is then registered on a bare Flask app next to Flask-Login, with the database, the
shared ``DATA`` dict and the configuration objects as mocks the tests script and inspect.

Templates are not rendered: ``render_template`` is swapped for a recorder, so an assertion reads the
template name and the context the route built rather than HTML shaped by the main app's context
processors.
"""

import sys
from html import unescape
from importlib import import_module
from pathlib import Path
from types import GeneratorType, ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

flask = pytest.importorskip("flask")
flask_login = pytest.importorskip("flask_login")

from _ui_routes_helpers import FakeData, FakeRedis, FakeUser, InlineExecutor  # noqa: E402

ROUTE_NAMES = (
    "about",
    "bans",
    "cache",
    "configs",
    "crowdsec",
    "global_settings",
    "home",
    "instances",
    "jobs",
    "login",
    "logout",
    "logs",
    "plugins",
    "pro",
    "profile",
    "reports",
    "services",
    "setup",
    "support",
    "templates",
    "totp",
)


def _stub_missing_third_party():
    """``psutil`` and ``user_agents`` ship in the UI image but not in the unit pins; return the names stubbed."""
    stubbed = []
    try:
        import psutil  # noqa: F401
    except ImportError:
        stub = ModuleType("psutil")
        stub.virtual_memory = lambda: SimpleNamespace(total=8 * 1024**3, available=4 * 1024**3, percent=50.0, used=4 * 1024**3)
        sys.modules["psutil"] = stub
        stubbed.append("psutil")
    try:
        import user_agents  # noqa: F401
    except ImportError:
        stub = ModuleType("user_agents")
        stub.parse = lambda raw: SimpleNamespace(get_browser=lambda: f"browser({raw})", get_os=lambda: f"os({raw})", get_device=lambda: f"device({raw})")
        sys.modules["user_agents"] = stub
        stubbed.append("user_agents")
    return stubbed


def _stub_dependencies(tmp_dir):
    deps = ModuleType("app.dependencies")
    deps.DB = MagicMock(name="DB")
    deps.DATA = FakeData(Path(tmp_dir) / "ui_data.json")
    deps.BW_CONFIG = MagicMock(name="BW_CONFIG")
    deps.BW_INSTANCES_UTILS = MagicMock(name="BW_INSTANCES_UTILS")
    deps.CONFIG_TASKS_EXECUTOR = InlineExecutor()
    deps.PAGE_TASKS_EXECUTOR = InlineExecutor()
    deps.CORE_PLUGINS_PATH = Path(tmp_dir) / "core"
    deps.EXTERNAL_PLUGINS_PATH = Path(tmp_dir) / "external"
    deps.PRO_PLUGINS_PATH = Path(tmp_dir) / "pro"
    deps.reload_plugins = MagicMock(name="reload_plugins", return_value="")
    deps.safe_reload_plugins = MagicMock(name="safe_reload_plugins", return_value="")
    return deps


class Harness:
    FakeRedis = FakeRedis

    def __init__(self, tmp_dir):
        self.deps = _stub_dependencies(tmp_dir)
        self.db, self.data, self.config, self.instances = self.deps.DB, self.deps.DATA, self.deps.BW_CONFIG, self.deps.BW_INSTANCES_UTILS
        self.renders = []
        self.users = {}
        self.tmp_dir = Path(tmp_dir)
        self.public_endpoints = set()

        previous = {name: sys.modules.get(name) for name in ("app.dependencies",)}
        self._previous = previous
        for name in [n for n in sys.modules if n.startswith("app.routes")]:
            self._previous.setdefault(name, sys.modules.pop(name))
        self._stubbed = _stub_missing_third_party()
        # The routes drive the TOTP object through five methods; passlib behind the real one is not a unit-pin dependency
        self.totp = MagicMock(name="TOTP")
        totp_module = ModuleType("app.models.totp")
        totp_module.totp = self.totp
        self._previous["app.models.totp"] = sys.modules.get("app.models.totp")
        sys.modules["app.models.totp"] = totp_module
        sys.modules["app.dependencies"] = self.deps
        self.routes = SimpleNamespace()
        for name in ROUTE_NAMES:
            module = import_module(f"app.routes.{name}")
            module.render_template = self._render
            setattr(self.routes, name, module)
        self.utils = import_module("app.routes.utils")
        self.app = self._build_app()

    def close(self):
        for name in self._stubbed:
            sys.modules.pop(name, None)
        for name in [n for n in sys.modules if n.startswith("app.routes")]:
            del sys.modules[name]
        for name, module in self._previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def _render(self, template, **context):
        # a lazy generator would run after the request context is gone: read it while it is still open
        self.renders.append((template, {key: list(value) if isinstance(value, GeneratorType) else value for key, value in context.items()}))
        return f"rendered:{template}"

    def _build_app(self):
        app = flask.Flask("bw_ui_routes_test")
        app.secret_key = "test"
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PROPAGATE_EXCEPTIONS=False)
        manager = flask_login.LoginManager()
        manager.login_view = "login.login_page"
        manager.anonymous_user = import_module("app.models.models").AnonymousUser
        manager.init_app(app)
        manager.user_loader(lambda username: self.users.get(username))
        # the app's session interface (flask-session) rotates ids; the default cookie one has nothing to rotate
        app.session_interface.regenerate = lambda session: None
        app.add_url_rule("/loading", "loading", lambda: "loading")
        for name in ROUTE_NAMES:
            app.register_blueprint(getattr(getattr(self.routes, name), name))
        return app

    def reset(self):
        self.db.reset_mock(return_value=True, side_effect=True)
        self.config.reset_mock(return_value=True, side_effect=True)
        self.instances.reset_mock(return_value=True, side_effect=True)
        self.db.readonly = False
        self.totp.reset_mock(return_value=True, side_effect=True)
        self.data.clear()
        self.data.update({"TO_FLASH": [], "RELOADING": False, "CONFIG_CHANGED": False})
        self.renders.clear()
        self.users.clear()

    def client(self, user="alice", **user_kwargs):
        """A test client signed in as ``user`` (a ``FakeUser`` is built from ``user_kwargs``); ``None`` stays anonymous."""
        client = self.app.test_client()
        if user is not None:
            fake = user if isinstance(user, FakeUser) else FakeUser(user, **user_kwargs)
            self.users[fake.username] = fake
            with client.session_transaction() as sess:
                sess["_user_id"] = fake.username
                sess["_fresh"] = True
                sess["flash_messages"] = []
        return client

    def flashes(self, client):
        with client.session_transaction() as sess:
            return [(unescape(message), category) for category, message in sess.get("_flashes", [])]


@pytest.fixture(scope="module")
def _harness(tmp_path_factory):
    harness = Harness(tmp_path_factory.mktemp("ui_routes"))
    try:
        yield harness
    finally:
        harness.close()


@pytest.fixture
def h(_harness):
    _harness.reset()
    return _harness
