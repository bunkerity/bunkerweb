"""Harness for the UI core tests (``app.dependencies``, ``main`` and the models that need them).

``app.dependencies`` builds a ``UIDatabase`` and reads files under ``/usr/share``, ``/var/tmp`` and
``/etc`` at import time, so every import of it here goes through ``import_dependencies``: the
database class is a mock, the data file lives in ``tmp_path`` and the plugin directories are
patched afterwards. The module is removed from ``sys.modules`` again at teardown so a sibling
harness never inherits these fakes.
"""

import sys
from importlib import import_module
from types import ModuleType
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _ui_core_helpers import FakeApiCaller, FakeRedis

_GEN = str(Path(__file__).resolve().parents[4] / "src" / "common" / "gen")
if _GEN not in sys.path:
    sys.path.append(_GEN)


@pytest.fixture
def import_dependencies(tmp_path, monkeypatch):
    """Import a fresh ``app.dependencies`` with a mocked database; returns ``(module, fake_db)``."""
    previous = sys.modules.pop("app.dependencies", None)
    ui_data = import_module("app.models.ui_data")
    ui_database = import_module("app.models.ui_database")
    config_module = import_module("app.models.config")

    fake_db = MagicMock(name="UIDatabase")
    fake_db.logger = MagicMock(name="db_logger")
    real_ui_data = ui_data.UIData
    monkeypatch.setattr(ui_database, "UIDatabase", MagicMock(return_value=fake_db))
    monkeypatch.setattr(ui_data, "UIData", lambda _path: real_ui_data(tmp_path / "ui_data.json"))
    monkeypatch.setattr(config_module.Config, "__init__", lambda self, db, data: setattr(self, "args", (db, data)))
    module = import_module("app.dependencies")
    monkeypatch.setattr(module, "EXTERNAL_PLUGINS_PATH", tmp_path / "external")
    monkeypatch.setattr(module, "PRO_PLUGINS_PATH", tmp_path / "pro")
    (tmp_path / "external").mkdir()
    (tmp_path / "pro").mkdir()
    try:
        yield module, fake_db
    finally:
        sys.modules.pop("app.dependencies", None)
        if previous is not None:
            sys.modules["app.dependencies"] = previous


@pytest.fixture
def fake_caller():
    return FakeApiCaller


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def routes_utils(monkeypatch):
    """Stand-in ``app.routes.utils`` (the real one needs ``app.dependencies``); ``.client`` is what ``get_redis_client`` returns."""
    module = ModuleType("app.routes.utils")
    module.client = None
    module.get_redis_client = lambda: module.client
    monkeypatch.setitem(sys.modules, "app.routes.utils", module)
    return module


@pytest.fixture(scope="module")
def _loaded_main(tmp_path_factory):
    from _ui_core_main import LoadedMain

    loaded = LoadedMain(tmp_path_factory.mktemp("ui_main"))
    try:
        yield loaded
    finally:
        loaded.close()


@pytest.fixture
def um(_loaded_main):
    """The real ``main.py`` app with mocked database; state is reset for every test."""
    _loaded_main.reset()
    config = _loaded_main.app.config
    saved = {key: value.copy() if isinstance(value, (list, dict, set)) else value for key, value in config.items()}
    try:
        yield _loaded_main
    finally:
        config.clear()
        config.update(saved)
