"""Q8 F-1: the instance reload/stop success flash is written in the language of the request.

`instances_action` queues `execute_actions` on `CONFIG_TASKS_EXECUTOR`, which fans out one
`execute_action` per instance on a nested pool. That nested pool ran outside any app context, so
`translated()` returned nothing and the English fallback was flashed in every locale.

This runs the real route through the real `LocaleThreadPoolExecutor` from a French request.
"""

import importlib.util
import sys
from json import loads
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from flask import Flask, session

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "ui"))

from app.i18n import LocaleThreadPoolExecutor, init_i18n  # noqa: E402

ROUTE_PATH = REPO / "src" / "ui" / "app" / "routes" / "instances.py"


def _import_route_module() -> ModuleType:
    dependencies = ModuleType("app.dependencies")
    for name in ("API_CLIENT", "BW_CONFIG", "BW_INSTANCES_UTILS", "CONFIG_TASKS_EXECUTOR", "DATA"):
        setattr(dependencies, name, Mock())
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = "app.routes._instances_test_action_flash_locale"
    spec = importlib.util.spec_from_file_location(module_name, ROUTE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
    return module


MODULE = _import_route_module()


class _FakeData(dict):
    def load_from_file(self):
        return None


def _catalog_value(language: str, key: str) -> str:
    node = loads((REPO / "src" / "ui" / "app" / "static" / "locales" / f"{language}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        node = node[part]
    return node


def _run_action(language: str, action: str) -> list:
    app = Flask("bw_ui_instance_action_locale_test", root_path=str(REPO / "src" / "ui"))
    app.config["SECRET_KEY"] = "test"
    init_i18n(app)
    app.add_url_rule("/loading", "loading", lambda: "")
    app.add_url_rule("/instances", "instances.instances_page", lambda: "")
    app.add_url_rule("/instances/<action>", "instances_action_stub", lambda action: "", methods=["POST"])

    data = _FakeData(TO_FLASH=[])
    executor = LocaleThreadPoolExecutor(max_workers=1)
    api_client = Mock(readonly=False)
    instance = Mock()
    getattr(instance, action).return_value = "ok"
    try:
        with (
            patch.object(MODULE, "API_CLIENT", api_client),
            patch.object(MODULE, "DATA", data),
            patch.object(MODULE, "CONFIG_TASKS_EXECUTOR", executor),
            patch.object(MODULE, "is_readonly_request", lambda readonly: False),
            patch.object(MODULE.Instance, "from_hostname", lambda hostname, client: instance),
        ):
            with app.test_request_context(f"/instances/{action}", method="POST", data={"instances": "bunkerweb,other"}):
                session["language"] = language
                MODULE.instances_action.__wrapped__(action)
            executor.shutdown(wait=True)  # the task and its nested pool finish after the request is gone
    finally:
        executor.shutdown(wait=True)
    return [entry["content"] for entry in data["TO_FLASH"]]


def test_reload_flash_is_french_from_a_french_request():
    flashed = _run_action("fr", "reload")
    expected = _catalog_value("fr", "instances.flash.instance_reloaded").replace("{{instance}}", "bunkerweb")

    assert len(flashed) == 2, flashed
    assert expected in flashed, flashed
    assert not any("Reloaded successfully" in entry for entry in flashed), flashed


def test_stop_flash_is_german_from_a_german_request():
    flashed = _run_action("de", "stop")

    assert _catalog_value("de", "instances.flash.instance_stopped").replace("{{instance}}", "bunkerweb") in flashed, flashed
