"""`GET /openapi.json` serializes: no route or model may leave a value JSON cannot carry in the schema.

CI run 39401254968 answered 500 there on the wave-26 pins (``PydanticSerializationError: Unable to
serialize unknown type: <class 'ellipsis'>``) while every other API test stayed green, because none of
them built the whole schema. This one builds the real app, core routers and the plugin routers the
loader mounts included.

Run with:

    BW_API_APP_LANE=1 .venv-unit/bin/python -m pytest tests/unit/api_app
"""

from json import loads
from pathlib import Path
from sys import path as sys_path

import pytest

from test_biscuit_run_limit import VERSION  # noqa: F401  (bootstrap: sys.path, key file, get_version)

from fastapi.testclient import TestClient  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
# The routers import the instance client (`from API import API`), which the image finds under /usr/share/bunkerweb.
sys_path.append(str(_ROOT / "src" / "common" / "api"))


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    # `app.main` builds the app at import and opens the database doing so (an unreachable one exits the
    # process), so point it at a throwaway SQLite file. The core plugins live in the checkout, not in
    # the image; core plugins skip the checksum lookup, so the empty database is enough.
    import plugin_extensions  # type: ignore

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URI", f"sqlite:///{tmp_path_factory.mktemp('openapi') / 'db.sqlite3'}")
        mp.setattr(plugin_extensions, "CORE_PLUGINS_PATH", str(_ROOT / "src" / "common" / "core"))
        from app.main import create_app

        return create_app()


def test_openapi_json_is_served(app):
    response = TestClient(app, raise_server_exceptions=False, client=("127.0.0.1", 50000)).get("/openapi.json")
    assert response.status_code == 200, response.text

    paths = loads(response.text)["paths"]
    assert any(path.startswith("/workflows") for path in paths), "plugin routers were not mounted: the schema under test is incomplete"
