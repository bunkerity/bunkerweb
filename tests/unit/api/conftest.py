"""Fixtures for APIDatabase tests.

The API user/permission mixins use only absolute imports (``model``,
``db_methods.common``), so we recompose ``APIDatabase`` here from
``src/api/app/models`` rather than importing it as ``app.models.api_database`` — that
avoids pulling in the ``app`` package (which the UI also defines). The recomposed class
is byte-identical in MRO and ``external=True`` behavior to the shipped one.
"""

import sys
from pathlib import Path

import pytest

_API_APP = Path(__file__).resolve().parents[3] / "src" / "api" / "app"
for _p in (str(_API_APP), str(_API_APP / "models")):  # app/ for `schemas`, models/ for `api_db_methods`
    if _p not in sys.path:
        sys.path.insert(0, _p)

from Database import Database  # noqa: E402
from api_db_methods.users import APIUsersMethodsMixin  # noqa: E402
from api_db_methods.permissions import APIPermissionsMethodsMixin  # noqa: E402

from fixtures.db_factory import resolve_uri  # noqa: E402
from fixtures.engines import reset_schema  # noqa: E402


class _APIDatabase(APIUsersMethodsMixin, APIPermissionsMethodsMixin, Database):
    """Mirror of app.models.api_database.APIDatabase (same MRO + external=True)."""

    def __init__(self, logger, sqlalchemy_string=None, *, pool=None, log=True, **kwargs):
        super().__init__(logger, sqlalchemy_string, external=True, pool=pool, log=log, **kwargs)


@pytest.fixture
def api_db(db_engine, tmp_path, quiet_logger, _clean_env):
    uri = resolve_uri(db_engine, tmp_path)
    reset_schema(uri)
    database = _APIDatabase(quiet_logger, sqlalchemy_string=uri, log=False)
    try:
        yield database
    finally:
        database.close()
