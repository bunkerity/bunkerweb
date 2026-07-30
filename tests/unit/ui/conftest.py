"""Fixtures for UIDatabase tests.

Unlike the API mixins, the UI mixins use absolute ``app.models...`` imports (e.g.
``from app.models.models import UiUsers``), so we must import the real ``UIDatabase``
via the ``app`` package with ``src/ui`` on the path. Only the UI imports ``app`` (the
API tests recompose without it), so ``import app`` resolves uniquely to ``src/ui/app``
and there's no collision in a combined run.
"""

import sys
from pathlib import Path

import pytest

_UI_ROOT = str(Path(__file__).resolve().parents[3] / "src" / "ui")
if _UI_ROOT not in sys.path:
    sys.path.insert(0, _UI_ROOT)

import plugin_extensions  # type: ignore  # noqa: E402 — on sys.path via the root conftest

from app.models.ui_database import UIDatabase  # noqa: E402
from app.utils import get_activation_map  # noqa: E402

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402

# `is_plugin_active`'s manifest tier reads plugin.json files through
# `plugin_extensions.iter_plugin_activations()`, which (by design — see plugin_extensions.py)
# scans the hardcoded, non-overridable container path `/usr/share/bunkerweb/core`. That path
# only exists inside a built image (the Dockerfiles `COPY src/common/core core` there); a bare
# checkout has nothing there. Point the scan at the real manifests in this repo for every UI
# test, and clear `get_activation_map`'s cache so each test re-reads them under the patched path.
_REAL_CORE_PLUGINS_PATH = str(Path(__file__).resolve().parents[3] / "src" / "common" / "core")


@pytest.fixture(autouse=True)
def _real_plugin_activation_manifests(monkeypatch):
    monkeypatch.setattr(plugin_extensions, "CORE_PLUGINS_PATH", _REAL_CORE_PLUGINS_PATH)
    get_activation_map.cache_clear()
    yield
    get_activation_map.cache_clear()


@pytest.fixture
def ui_db(db_engine, tmp_path, quiet_logger, _clean_env):
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)
    database = UIDatabase(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()
