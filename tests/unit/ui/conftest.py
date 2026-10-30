"""Fixtures for UIDatabase tests.

The UI mixins import ``app.models...`` absolutely, so ``UIDatabase`` is imported through the real
``app`` package with ``src/ui`` on the path. Only the UI imports ``app`` in this interpreter (the API
fixture loads its module by file path), so ``import app`` resolves to ``src/ui/app``.
"""

import sys
from pathlib import Path

import pytest

_UI_ROOT = str(Path(__file__).resolve().parents[3] / "src" / "ui")
if _UI_ROOT not in sys.path:
    sys.path.insert(0, _UI_ROOT)

from app.models.ui_database import UIDatabase  # noqa: E402

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402


@pytest.fixture
def ui_db(db_engine, tmp_path, quiet_logger, _clean_env):
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)
    database = UIDatabase(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()
