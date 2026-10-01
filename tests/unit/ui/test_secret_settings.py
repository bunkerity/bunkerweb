"""Secret settings never reach a page, and saving a form never clears one by accident (M35, L8).

`/pro` rendered the stored PRO license key into `<input type="password" value="...">`, and the
global settings pages rendered every `type: password` setting the same way (`API_TOKEN` was even
`type: text`). `type=password` hides a value on screen only: it was in the page source for anyone
who could open the page, a reader included.

The routes now render `SECRET_PLACEHOLDER` for a stored secret (`app/models/secret_settings.py`)
and turn an untouched placeholder back into the stored value before saving: a form saved for
another field keeps the secret, a new value replaces it, an emptied field clears it.

Also here: `/pro` states what the license check concluded about the stored key (M34), and clearing
the key is not announced as "Checking license key to upgrade." (L21).

Same harness as `test_global_settings_save_flash_type.py` (real `Config.check_variables`) and
`test_pro_key_save_flash_type.py` (synchronous executor).
"""

import importlib.util
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from app.models.config import Config  # type: ignore  (src/ui on path via the ui conftest)
from app.models.secret_settings import SECRET_PLACEHOLDER, redact_secrets, restore_secrets, secret_setting_names  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTES = REPO_ROOT / "src" / "ui" / "app" / "routes"

SETTINGS = {
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
    "LOG_LEVEL": {"type": "text", "regex": "^.*$", "context": "global"},
    "API_TOKEN": {"type": "password", "regex": "^.*$", "context": "global"},
    "PRO_LICENSE_KEY": {"type": "password", "regex": "^.*$", "context": "global"},
}
NAMES = secret_setting_names(SETTINGS)


def _shipped_settings():
    yield from json.loads((REPO_ROOT / "src" / "common" / "settings.json").read_text(encoding="utf-8")).items()
    for manifest in sorted((REPO_ROOT / "src" / "common" / "core").glob("*/plugin.json")):
        yield from json.loads(manifest.read_text(encoding="utf-8")).get("settings", {}).items()


# --------------------------------------------------------------------------------------
# The helper and the manifests
# --------------------------------------------------------------------------------------


def test_api_token_is_a_secret_setting():
    """L8: it was `type: text`, a plain input showing the instance API token on screen."""
    assert dict(_shipped_settings())["API_TOKEN"]["type"] == "password"


@pytest.mark.parametrize("name,data", [(n, d) for n, d in _shipped_settings() if d.get("type") == "password"])
def test_the_placeholder_passes_every_shipped_secret_regex(name, data):
    """The browser's `pattern=` and the Configurator both check it: a refusal would block every save."""
    assert re.search(data["regex"], SECRET_PLACEHOLDER), name


def test_redact_then_restore_keeps_clears_and_replaces():
    stored = {
        "API_TOKEN": {"value": "tok-secret"},
        "PRO_LICENSE_KEY": {"value": "key-secret"},
        "LOG_LEVEL": {"value": "notice"},
    }
    rendered = redact_secrets(stored, NAMES)
    assert rendered["API_TOKEN"]["value"] == rendered["PRO_LICENSE_KEY"]["value"] == SECRET_PLACEHOLDER
    assert rendered["LOG_LEVEL"]["value"] == "notice"
    assert stored["API_TOKEN"]["value"] == "tok-secret", "the stored config must not be mutated"

    posted = {"API_TOKEN": SECRET_PLACEHOLDER, "PRO_LICENSE_KEY": "", "LOG_LEVEL": SECRET_PLACEHOLDER}
    assert restore_secrets(posted, stored, NAMES) == {"API_TOKEN": "tok-secret", "PRO_LICENSE_KEY": "", "LOG_LEVEL": SECRET_PLACEHOLDER}


def test_an_unset_secret_renders_as_unset():
    assert redact_secrets({"API_TOKEN": {"value": ""}}, NAMES)["API_TOKEN"]["value"] == ""


def test_the_setting_macro_says_a_secret_is_stored():
    """The form shows set / not set: the placeholder is what tells the macro a value is stored."""
    macro = (REPO_ROOT / "src" / "ui" / "app" / "templates" / "models" / "input_setting.html").read_text(encoding="utf-8")
    assert f'setting_value == "{SECRET_PLACEHOLDER}"' in macro
    assert "form.help.secret_stored" in macro


# --------------------------------------------------------------------------------------
# Global settings: render and save
# --------------------------------------------------------------------------------------


class _FakeData(dict):
    def load_from_file(self):
        return None


class _SyncExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)
        return Mock()


def _load(route: str, name: str, **extra_dependencies) -> ModuleType:
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock(readonly=False)
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = _SyncExecutor()
    dependencies.DATA = _FakeData(TO_FLASH=[])
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    for key, value in extra_dependencies.items():
        setattr(dependencies, key, value)
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    module_name = f"app.routes._secret_settings_test_{name}"
    spec = importlib.util.spec_from_file_location(module_name, ROUTES / route)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
    return module


GLOBAL = _load("global_settings.py", "global")


def _stored_global() -> dict:
    return {
        "SERVER_NAME": {"value": "", "global": True, "method": "scheduler", "default": "", "template": None},
        "LOG_LEVEL": {"value": "notice", "global": True, "method": "ui", "default": "notice", "template": None},
        "API_TOKEN": {"value": "tok-secret", "global": True, "method": "ui", "default": "", "template": None},
        "PRO_LICENSE_KEY": {"value": "key-secret", "global": True, "method": "ui", "default": "", "template": None},
    }


def _save_global(posted: dict):
    """Run the real `update_global_config`; return (what reached edit_global_conf, flashes)."""
    data = _FakeData(TO_FLASH=[])
    saved = {}

    def edit_global_conf(variables, **_kwargs):
        saved.update(variables)
        return "Global settings successfully saved.", 0

    config = Config.__new__(Config)  # skip __init__ (hardcoded settings.json read)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(_stored_global())
    config.edit_global_conf = edit_global_conf

    with patch.object(GLOBAL, "BW_CONFIG", config), patch.object(GLOBAL, "DATA", data), patch.object(GLOBAL, "wait_applying", lambda: None):
        GLOBAL.update_global_config(dict(posted), False, {}, scope=None)

    return saved, [entry["content"] for entry in data["TO_FLASH"]]


def _full_post(**overrides):
    return {"LOG_LEVEL": "notice", "API_TOKEN": SECRET_PLACEHOLDER, "PRO_LICENSE_KEY": SECRET_PLACEHOLDER} | overrides


def test_saving_the_form_untouched_keeps_every_secret_and_changes_nothing():
    saved, flashed = _save_global(_full_post())
    assert not saved, "an untouched form must not write anything"
    assert "The global settings were not edited because no values were changed." in flashed


def test_saving_another_field_keeps_the_secrets():
    saved, _ = _save_global(_full_post(LOG_LEVEL="info"))
    assert saved["LOG_LEVEL"] == "info"
    assert saved["API_TOKEN"] == "tok-secret"
    assert saved["PRO_LICENSE_KEY"] == "key-secret"


def test_a_new_value_replaces_the_secret_and_an_emptied_field_clears_it():
    saved, _ = _save_global(_full_post(API_TOKEN="new-token", PRO_LICENSE_KEY=""))
    assert saved["API_TOKEN"] == "new-token"
    assert saved["PRO_LICENSE_KEY"] == ""


def test_clearing_the_pro_key_is_not_announced_as_a_license_check():
    """L21."""
    _, flashed = _save_global(_full_post(PRO_LICENSE_KEY=""))
    assert "Checking license key to upgrade." not in flashed


def test_setting_a_new_pro_key_still_announces_the_check():
    _, flashed = _save_global(_full_post(PRO_LICENSE_KEY="new-key"))
    assert "Checking license key to upgrade." in flashed


@pytest.fixture
def global_app():
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    app.add_url_rule("/global-settings", view_func=GLOBAL.global_settings_page.__wrapped__)
    app.add_url_rule("/global-settings/plugins/<string:plugin>", view_func=GLOBAL.global_settings_plugin_page.__wrapped__)
    render = Mock(return_value="page")
    config = Mock()
    config.get_plugins_settings.return_value = SETTINGS
    with (
        patch.object(GLOBAL, "API_CLIENT", Mock(**{"get_global_settings.return_value": _stored_global()})),
        patch.object(GLOBAL, "BW_CONFIG", config),
        patch.object(GLOBAL, "render_template", render),
        patch.object(GLOBAL, "resolve_plugin", lambda plugin, plugins: {"name": "Pro"}),
        patch.object(GLOBAL, "plugin_settings_body", lambda plugin: None),
        patch.object(GLOBAL, "plugin_settings_body_script", lambda plugin: None),
        patch.object(GLOBAL, "get_activation_map", lambda: {}),
    ):
        app.render = render
        yield app


@pytest.mark.parametrize("path", ["/global-settings", "/global-settings?mode=raw", "/global-settings/plugins/pro"])
def test_the_global_pages_render_no_secret(global_app, path):
    global_app.test_client().get(path)
    rendered = global_app.render.call_args.kwargs["config"]
    assert rendered["API_TOKEN"]["value"] == rendered["PRO_LICENSE_KEY"]["value"] == SECRET_PLACEHOLDER
    assert rendered["LOG_LEVEL"]["value"] == "notice"


def test_the_json_view_carries_no_secret(global_app):
    """template-settings-page.js copies these values into a template's inputs: a secret is left out
    entirely, so no placeholder can land in a template either."""
    body = global_app.test_client().get("/global-settings?as_json=true").get_json()
    assert "API_TOKEN" not in body and "PRO_LICENSE_KEY" not in body
    assert body["LOG_LEVEL"]["value"] == "notice"


# --------------------------------------------------------------------------------------
# /pro
# --------------------------------------------------------------------------------------


@pytest.fixture
def pro():
    module = _load("pro.py", "pro")
    module.API_CLIENT.get_services.return_value = []
    module.BW_CONFIG.get_config.return_value = {"PRO_LICENSE_KEY": "key-secret"}
    module.billable_service_count = Mock(return_value=0)
    module.render_template = Mock(return_value="page")
    module.flash = Mock()
    # No logged-in user here: the permission half of the gate is pinned by test_configs_write_permission.py.
    module.is_readonly_request = lambda api_readonly: False
    module.verify_data_in_form = Mock()
    app = Flask(__name__)
    app.secret_key = "test"  # nosec B105 - unit test
    app.add_url_rule("/pro", endpoint="pro.pro_page", view_func=module.pro_page.__wrapped__)
    app.add_url_rule("/pro/key", view_func=module.pro_key.__wrapped__, methods=["POST"])
    app.add_url_rule("/loading", endpoint="loading", view_func=lambda: "loading")
    module.app = app
    return module


def _metadata(**overrides):
    return {"pro_expire": None, "pro_license": "", "pro_status": "invalid", "is_pro": False} | overrides


def _render_pro(pro, **metadata):
    pro.API_CLIENT.get_metadata.return_value = _metadata(**metadata)
    pro.app.test_client().get("/pro")
    return pro.render_template.call_args.kwargs


def test_pro_renders_no_license_key(pro):
    assert _render_pro(pro)["pro_license_key"] == SECRET_PLACEHOLDER


def test_pro_renders_an_unset_key_as_unset(pro):
    pro.BW_CONFIG.get_config.return_value = {"PRO_LICENSE_KEY": ""}
    rendered = _render_pro(pro)
    assert rendered["pro_license_key"] == ""
    assert rendered["license_key_state"] == "unset"


@pytest.mark.parametrize(
    "metadata,state",
    [
        # M34: the check ran on this very key and the server said it is not valid.
        ({"pro_license": "key-secret", "pro_status": "invalid"}, "invalid"),
        # The check has not run on this key yet (it last ran on another one, or never).
        ({"pro_license": "older-key", "pro_status": "active", "is_pro": True}, "pending"),
        ({"pro_license": "key-secret", "pro_status": "active", "is_pro": True}, "checked"),
        ({"pro_license": "key-secret", "pro_status": "expired"}, "checked"),
    ],
)
def test_pro_states_what_the_check_concluded_about_the_stored_key(pro, metadata, state):
    assert _render_pro(pro, **metadata)["license_key_state"] == state


def test_posting_the_placeholder_back_changes_nothing(pro):
    response = pro.app.test_client().post("/pro/key", data={"PRO_LICENSE_KEY": SECRET_PLACEHOLDER})
    assert response.status_code == 302
    pro.BW_CONFIG.check_variables.assert_not_called()
    pro.BW_CONFIG.edit_global_conf.assert_not_called()
    pro.flash.assert_called_once_with("The license key is the same as the current one.", "warning")


def test_the_pro_template_shows_the_invalid_state():
    template = (REPO_ROOT / "src" / "ui" / "app" / "templates" / "pro.html").read_text(encoding="utf-8")
    assert 'license_key_state == "invalid"' in template
    assert "pro.status.invalid" in template
