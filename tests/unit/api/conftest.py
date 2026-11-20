"""Fixtures for APIDatabase tests.

dev's ``APIDatabase`` is one class with absolute imports (``Database``, ``model``), so loading
``src/api/app/models/api_database.py`` by file path gives the shipped class without importing the
``app`` package, which stays free for the UI (``tests/unit/ui/conftest.py``).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_API_APP = Path(__file__).resolve().parents[3] / "src" / "api" / "app"
if str(_API_APP) not in sys.path:
    sys.path.insert(0, str(_API_APP))

_spec = importlib.util.spec_from_file_location("bw_api_database", _API_APP / "models" / "api_database.py")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
APIDatabase = _module.APIDatabase

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402


@pytest.fixture
def api_db(db_engine, tmp_path, quiet_logger, _clean_env):
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)
    database = APIDatabase(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()
