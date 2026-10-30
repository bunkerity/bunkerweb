"""Path-loaded core UI plugins with request-scoped, isolated dependencies."""

import sys
from contextlib import nullcontext
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def load_plugin(monkeypatch):
    def load(name, relative="actions.py"):
        path = ROOT / "src/common/core" / name / "ui" / relative
        module_name = f"core_ui_{name}_{relative.replace('/', '_').replace('.', '_')}"
        spec = spec_from_file_location(module_name, path)
        module = module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        return module

    return load


@pytest.fixture
def ui_env(monkeypatch):
    deps = ModuleType("app.dependencies")
    deps.DB = Mock()
    deps.DATA = {}
    utils = ModuleType("app.utils")
    utils.LOGGER = Mock()
    utils.flash = Mock()
    routes_utils = ModuleType("app.routes.utils")
    routes_utils.cors_required = lambda function: function
    for name, module in (("app.dependencies", deps), ("app.utils", utils), ("app.routes.utils", routes_utils)):
        monkeypatch.setitem(sys.modules, name, module)
    app = Flask("core_ui_plugins")
    app.config.update(TESTING=True, SECRET_KEY="unit-test")
    login = LoginManager(app)

    class User(UserMixin):
        id = "writer"
        list_permissions = ["read", "write"]

    user = User()
    login.user_loader(lambda _id: user)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user.id
        session["_fresh"] = True
    return SimpleNamespace(app=app, client=client, db=deps.DB, utils=utils, user=user)


@pytest.fixture
def le(ui_env, load_plugin, tmp_path, monkeypatch):
    module = load_plugin("letsencrypt", "blueprints/letsencrypt.py")
    monkeypatch.setattr(module, "SCRATCH_ROOT", str(tmp_path / "scratch"))
    monkeypatch.setattr(module, "LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(module, "LE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(module, "_le_cache_write_lock", nullcontext)
    monkeypatch.setattr(module, "run", Mock(side_effect=AssertionError("certbot must be stubbed")))
    ui_env.db.get_jobs_cache_files.return_value = []
    ui_env.db.upsert_job_cache.return_value = ""
    ui_env.db.checked_changes.return_value = ""
    ui_env.app.register_blueprint(module.letsencrypt)
    return module
