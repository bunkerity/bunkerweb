"""`/configs`: Export on a selected template config exports it, and a broken import file is
reported in words rather than with the JSON parser's message (QA-UI M29, M28).

M29: `configs_export` skipped every template-provided config, so selecting one (Export stays
enabled on its row) ended on "No custom configurations to export.". M28: `{not json` came back as
"File is not valid JSON: Expecting property name enclosed in double quotes".

Loader: `test_configs_write_permission.py`'s.
"""

import importlib.util
import sys
from json import dumps, loads
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

ROUTE_PATH = Path(__file__).resolve().parents[3] / "src" / "ui" / "app" / "routes" / "configs.py"


@pytest.fixture
def configs_route():
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = {}
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._configs_export_import_feedback_test"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
        yield module


CONFIGS = [
    # Template-provided rows carry the hyphenated type (routes/configs.py, the import path's note).
    {"service": "app.example.com", "type": "modsec", "name": "api", "data": b"SecRule x", "template": "api", "method": "default"},
    {"service": "app.example.com", "type": "server-http", "name": "tpl", "data": b"# tpl", "template": "low", "method": "default"},
    {"service": "app.example.com", "type": "server_http", "name": "mine", "data": b"# mine", "template": None, "method": "ui"},
]


def _export(module, monkeypatch, selection=None):
    module.API_CLIENT.get_configs.return_value = [dict(row) for row in CONFIGS]
    monkeypatch.setattr(module, "handle_error", lambda message, *args, **kwargs: ("refused", message))
    app = Flask(__name__)
    args = {"configs": dumps(selection)} if selection is not None else {}
    with app.test_request_context("/configs/export", query_string=args):
        response = module.configs_export.__wrapped__()
    if isinstance(response, tuple):
        return response
    response.direct_passthrough = False
    return [(row["type"], row["name"]) for row in loads(response.get_data())["configs"]]


@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        ({"service": "app.example.com", "type": "modsec", "name": "api"}, ("modsec", "api")),
        ({"service": "app.example.com", "type": "server_http", "name": "tpl"}, ("server-http", "tpl")),
    ],
)
def test_a_selected_template_config_is_exported(configs_route, monkeypatch, selected, expected):
    assert _export(configs_route, monkeypatch, [selected]) == [expected]


def test_the_whole_inventory_export_still_leaves_template_configs_out(configs_route, monkeypatch):
    assert _export(configs_route, monkeypatch) == [("server_http", "mine")]


def test_a_broken_import_file_is_reported_in_words(configs_route):
    configs, errors = configs_route.parse_configs_export("{not json")
    assert configs == []
    assert errors == ["The file is not valid JSON (line 1, column 2)."]
