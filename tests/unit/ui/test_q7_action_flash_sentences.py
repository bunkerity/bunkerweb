"""Action words in success flashes must be part of translated full sentences."""

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

REPO_ROOT = Path(__file__).resolve().parents[3]


def _translated_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "translated":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        calls.setdefault(node.args[0].value, []).append({keyword.arg for keyword in node.keywords if keyword.arg})
    return calls


def test_action_success_flashes_use_complete_translated_sentences():
    expected = {
        "services.py": {
            "services.flash.configuration_created": {"service"},
            "services.flash.configuration_saved": {"service"},
            "services.flash.configuration_created_with_refusals": {"service", "refused_count"},
            "services.flash.configuration_saved_with_refusals": {"service", "refused_count"},
        },
        "plugins.py": {
            "plugins.flash.plugin_enabled": {"plugin"},
            "plugins.flash.plugin_disabled": {"plugin"},
        },
        "instances.py": {
            "instances.flash.instance_reloaded": {"instance"},
            "instances.flash.instance_stopped": {"instance"},
            "instances.flash.instance_deleted": {"instance"},
            "instances.flash.instances_deleted": {"instance"},
        },
    }
    route_dir = REPO_ROOT / "src" / "ui" / "app" / "routes"

    for filename, messages in expected.items():
        calls = _translated_calls(route_dir / filename)
        for key, variables in messages.items():
            assert calls.get(key) == [variables], f"{filename} must translate {key} with {sorted(variables)}"


class _Data(dict):
    def load_from_file(self):
        pass


@pytest.fixture
def instances_delete_route(monkeypatch):
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = _Data(TO_FLASH=[])
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    module_name = "app.routes._instances_q7_flash_test"
    route_path = REPO_ROOT / "src" / "ui" / "app" / "routes" / "instances.py"
    spec = importlib.util.spec_from_file_location(module_name, route_path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)

    translated_calls = []
    flashes = []
    monkeypatch.setattr(module, "verify_data_in_form", lambda **_kwargs: True)
    monkeypatch.setattr(module, "is_readonly_request", lambda _readonly: False)
    monkeypatch.setattr(module, "is_ui_api_method", lambda _method: True)
    monkeypatch.setattr(module, "translated", lambda key, **variables: translated_calls.append((key, variables)) or key)
    monkeypatch.setattr(module, "flash", lambda message, *_args, **_kwargs: flashes.append(message))

    app = Flask(__name__)
    app.secret_key = "test"
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    app.add_url_rule("/instances", endpoint="instances.instances_page", view_func=lambda: "instances")
    return module, app, translated_calls, flashes


@pytest.mark.parametrize(
    ("names", "expected_key"),
    [
        (["bw-1"], "instances.flash.instance_deleted"),
        (["bw-1", "bw-2"], "instances.flash.instances_deleted"),
    ],
)
def test_instance_delete_selects_singular_or_plural_message_key(instances_delete_route, names, expected_key):
    module, app, translated_calls, flashes = instances_delete_route
    module.API_CLIENT.get_instances.return_value = [{"hostname": name, "method": "ui"} for name in names]

    with app.test_request_context("/instances/delete", method="POST", data={"instances": ",".join(names)}):
        response = module.instances_action.__wrapped__("delete")

    assert response.status_code == 302
    assert module.API_CLIENT.delete_instances.call_count == 1
    success_calls = [call for call in translated_calls if call[0] in {"instances.flash.instance_deleted", "instances.flash.instances_deleted"}]
    assert len(success_calls) == 1
    assert success_calls[0][0] == expected_key
    assert set(success_calls[0][1]["instance"].split(", ")) == set(names)
    assert flashes == [expected_key]
