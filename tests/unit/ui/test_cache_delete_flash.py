"""M24: `POST /cache/delete`'s success path must not flash a raw `flash.success` toast header.

Same defect and fix as `test_web_cache.py::test_purge_success_uses_the_flash_wrapper_...`:
`flash.html` looks up `flash.<category>` and has no `flash.success` key. `routes/cache.py` calls
`flask_flash(msg, "success")` directly instead of the `app.utils.flash()` wrapper, which is what
omits the category for a success message so Flask defaults it to "message" -- a key the catalog
does have.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask


@pytest.fixture(scope="module")
def cache_route():
    """Load the route without booting container-only `app.dependencies` state, the same pattern
    `test_web_cache.py::web_cache_route` uses."""
    client = Mock()
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = Mock()
    module_name = "app.routes._cache_delete_flash_test"
    route_path = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "cache.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, module_name: module}):
        spec.loader.exec_module(module)
        yield module, client


@pytest.fixture
def route_app(cache_route, monkeypatch):
    module, client = cache_route
    client.reset_mock(return_value=True, side_effect=True)
    client.readonly = False
    monkeypatch.setattr(module, "is_readonly_request", lambda api_readonly: api_readonly)
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.cache)
    return module, client, app


def test_delete_success_uses_the_flash_wrapper_not_a_raw_success_category(route_app, monkeypatch):
    module, client, app = route_app
    client.delete_cache_files.return_value = {"deleted": 2, "errors": []}
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context("/cache/delete", method="POST", data={"cache_files": '["a", "b"]'}):
        response = module.cache_delete_bulk.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("Successfully deleted 2 cache files")


def test_delete_with_errors_still_uses_the_raw_warning_category(route_app, monkeypatch):
    """The `errors` branch keeps its raw `warning` category -- `flash.warning` is a real catalog
    key. It goes through the escaping wrapper like every flash, out of the notification history
    (`save=False`) as it was when it called Flask's own `flash`."""
    module, client, app = route_app
    client.delete_cache_files.return_value = {"deleted": 1, "errors": ["boom"]}
    flash = Mock()
    monkeypatch.setattr(module, "flash", flash)

    with app.test_request_context("/cache/delete", method="POST", data={"cache_files": '["a"]'}):
        response = module.cache_delete_bulk.__wrapped__()

    assert response.status_code == 302
    flash.assert_called_once_with("Deleted 1 files with 1 errors: boom", "warning", save=False)
