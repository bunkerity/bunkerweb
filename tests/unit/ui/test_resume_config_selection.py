"""Malformed config selections must be refused before they reach background writes."""

import importlib.util
import sys
from json import dumps
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def route(monkeypatch):
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = type("Data", (dict,), {"load_from_file": lambda self: None})(TO_FLASH=[])
    utils = ModuleType("app.routes.utils")
    utils.handle_error = lambda *args, **kwargs: ("invalid", 400)
    utils.verify_data_in_form = lambda **kwargs: True
    utils.wait_applying = Mock()
    utils.submit_config_task = dependencies.CONFIG_TASKS_EXECUTOR.submit
    spec = importlib.util.spec_from_file_location("app.routes._resume_configs", ROOT / "src/ui/app/routes/configs.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "app.routes.utils": utils}):
        spec.loader.exec_module(module)
    monkeypatch.setattr(module, "is_readonly_request", lambda *_args: False)
    monkeypatch.setattr(module, "translated", lambda *_args, **_kwargs: None)
    app = Flask(__name__)
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    app.add_url_rule("/configs", endpoint="configs.configs_page", view_func=lambda: "configs")
    for operation in ("delete", "convert"):
        app.add_url_rule(f"/configs/{operation}", view_func=getattr(module, f"configs_{operation}").__wrapped__, methods=["POST"])
    return module, app


@pytest.mark.parametrize("operation", ["delete", "convert"])
@pytest.mark.parametrize(
    "selection",
    [[], {}, None, [0], [{"name": 0, "type": "http", "service": None}], [{"name": "ok", "type": "bogus"}], [{"name": "ok", "type": "http", "service": 0}]],
)
def test_invalid_selection_does_not_submit_background_work(route, operation, selection):
    module, app = route
    response = app.test_client().post(f"/configs/{operation}", data={"configs": dumps(selection), "convert_to": "draft"})
    assert response.status_code == 400
    module.submit_config_task.assert_not_called()
