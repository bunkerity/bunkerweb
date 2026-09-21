"""The supported data surface for plugin UI code, and the loud death of the 1.6 ``DB`` handle.

1.7 gave the UI no database connection and exported ``app.dependencies.DB`` as ``None``, so every
plugin still written for 1.6 died with ``AttributeError: 'NoneType' object has no attribute
'get_config'`` at the first call -- inside the plugin, with nothing naming the plugin or the way
forward. ``PLUGIN_API`` is that way forward, and ``RetiredDB`` is what says so.

Everything here is loaded the way ``src/ui/main.py`` and ``routes/plugins.py`` load plugin code:
``bw_ui_blueprint_<plugin>_<file>`` module names for blueprints, ``SourceFileLoader`` for
``ui/actions.py``. The module name is what lets the error name the plugin, so faking it away would
test nothing.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

import pytest

_UI_ROOT = Path(__file__).resolve().parents[3] / "src" / "ui"

import app.plugin_api as plugin_api_module  # noqa: E402
from app.plugin_api import PLUGIN_API_METHODS, PluginApi, RetiredDB, RetiredDBError  # noqa: E402

# --------------------------------------------------------------------------------------
# The surface itself
# --------------------------------------------------------------------------------------


@pytest.fixture
def api_client():
    client = MagicMock()
    client.readonly = False
    return client


@pytest.mark.parametrize("method", sorted(PLUGIN_API_METHODS - {"readonly"}))
def test_every_supported_method_delegates_to_the_api_client(api_client, method):
    """The promise `docs/plugins.md` makes: these names reach the real client, with the args given."""
    plugin_api = PluginApi(api_client)
    result = getattr(plugin_api, method)("arg", kw=1)
    getattr(api_client, method).assert_called_once_with("arg", kw=1)
    assert result is getattr(api_client, method).return_value


def test_readonly_is_read_through_not_called(api_client):
    api_client.readonly = True
    assert PluginApi(api_client).readonly is True


@pytest.mark.parametrize(
    "method",
    ["create_user", "update_user", "get_user_for_auth", "delete_user_sessions", "get_admin_user", "resolve_webauthn_credential"],
)
def test_user_and_session_methods_stay_private(api_client, method):
    """The reason this is a facade and not `API_CLIENT` itself."""
    with pytest.raises(AttributeError) as excinfo:
        getattr(PluginApi(api_client), method)
    assert method in str(excinfo.value)
    assert "docs/plugins.md" in str(excinfo.value)
    getattr(api_client, method).assert_not_called()


def test_supported_methods_all_exist_on_the_real_client():
    """A name dropped from `api_client.py` must not survive in the promise."""
    from app.api_client import ApiClient

    missing = sorted(name for name in PLUGIN_API_METHODS if not hasattr(ApiClient, name))
    assert missing == []


# --------------------------------------------------------------------------------------
# get_cache_file_or_none -- a real method, not a `__getattr__` passthrough
# --------------------------------------------------------------------------------------


def test_get_cache_file_or_none_is_not_a_raw_passthrough_name():
    """It has its own behavior (404 -> None, .content unwrap), so it must not be advertised as
    one of the plain delegated names -- a caller reading `PLUGIN_API_METHODS` for the promise
    `docs/plugins.md` makes would otherwise expect a raw passthrough."""
    assert "get_cache_file_or_none" not in PLUGIN_API_METHODS


def test_get_cache_file_or_none_unwraps_the_response_on_download(api_client):
    api_client.get_cache_file.return_value = SimpleNamespace(content=b"raw-bytes")

    result = PluginApi(api_client).get_cache_file_or_none(None, "backup", "backup-data", "backup.json", download=True)

    assert result == b"raw-bytes"
    api_client.get_cache_file.assert_called_once_with(None, "backup", "backup-data", "backup.json", download=True)


def test_get_cache_file_or_none_passes_through_the_dict_shape_without_download(api_client):
    api_client.get_cache_file.return_value = {"file": {"data": "text"}}

    result = PluginApi(api_client).get_cache_file_or_none(None, "backup", "backup-data", "backup.json")

    assert result == {"file": {"data": "text"}}


def test_get_cache_file_or_none_maps_a_404_to_none(api_client):
    from app.api_client import ApiClientError

    api_client.get_cache_file.side_effect = ApiClientError("Cache file not found", status_code=404)

    result = PluginApi(api_client).get_cache_file_or_none(None, "bunkernet", "bunkernet-register", "instance.id", download=True)

    assert result is None


def test_get_cache_file_or_none_reraises_a_non_404_client_error(api_client):
    from app.api_client import ApiClientError

    api_client.get_cache_file.side_effect = ApiClientError("boom", status_code=500)

    with pytest.raises(ApiClientError):
        PluginApi(api_client).get_cache_file_or_none(None, "bunkernet", "bunkernet-register", "instance.id", download=True)


# --------------------------------------------------------------------------------------
# The retired DB handle
# --------------------------------------------------------------------------------------


def _blueprint_module(tmp_path, plugin, body):
    """Exec a file the way `src/ui/main.py:488-502` execs a plugin blueprint."""
    bp_dir = tmp_path / plugin / "ui" / "blueprints"
    bp_dir.mkdir(parents=True)
    bp_file = bp_dir / f"{plugin}.py"
    bp_file.write_text(body, encoding="utf-8")

    module_name = f"bw_ui_blueprint_{plugin}_{plugin}"
    spec = importlib.util.spec_from_file_location(module_name, bp_file)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {module_name: module}):
        spec.loader.exec_module(module)
    return module


def test_a_16_plugin_blueprint_gets_a_runtime_error_naming_itself(tmp_path, api_client):
    """B1: `DB.get_config()` from a PRO blueprint. The message has to be enough to fix the plugin."""
    dependencies = ModuleType("app.dependencies")
    dependencies.DB = RetiredDB()
    dependencies.PLUGIN_API = PluginApi(api_client)

    with patch.dict(sys.modules, {"app.dependencies": dependencies}):
        module = _blueprint_module(
            tmp_path,
            "saml",
            "from app.dependencies import DB\n\n\ndef page():\n    return DB.get_config(global_only=True)\n",
        )
        with pytest.raises(RuntimeError) as excinfo:
            module.page()

    message = str(excinfo.value)
    assert "'saml'" in message
    assert "DB.get_config" in message
    assert "PLUGIN_API" in message
    assert "docs/plugins.md" in message


def test_the_same_blueprint_works_once_ported_to_the_accessor(tmp_path, api_client):
    api_client.get_global_settings.return_value = {"USE_SAML": {"value": "yes"}}
    dependencies = ModuleType("app.dependencies")
    dependencies.DB = RetiredDB()
    dependencies.PLUGIN_API = PluginApi(api_client)

    with patch.dict(sys.modules, {"app.dependencies": dependencies}):
        module = _blueprint_module(
            tmp_path,
            "saml",
            "from app.dependencies import PLUGIN_API\n\n\ndef page():\n    return PLUGIN_API.get_global_settings(global_only=True)\n",
        )
        assert module.page() == {"USE_SAML": {"value": "yes"}}

    api_client.get_global_settings.assert_called_once_with(global_only=True)


def test_retired_db_is_falsy_so_16_guards_take_the_branch_they_took_under_none():
    """`if DB:` / `if not DB:` guards read the same as when `DB` was `None`.

    Live consumer: `bunkerweb-plugins/syswarden/ui/actions.py:45-51` does
    `db = kwargs.get("db")` then `if not db: return ret`.
    """
    db = RetiredDB()
    assert bool(db) is False
    assert not db


def test_feature_probes_degrade_the_way_they_did_under_none():
    """`hasattr`/`getattr`-with-default are written to degrade; they swallow `AttributeError`
    only, so a plain `RuntimeError` would blow up code that used to survive."""
    db = RetiredDB()
    assert hasattr(db, "get_config") is False
    assert getattr(db, "get_config", None) is None
    # ... and a real call is still the loud failure, catchable as either
    with pytest.raises(RuntimeError):
        db.get_config()
    with pytest.raises(AttributeError):
        db.get_config()
    assert issubclass(RetiredDBError, RuntimeError)
    assert issubclass(RetiredDBError, AttributeError)


@pytest.mark.parametrize(
    ("module", "filename", "expected"),
    [
        # The real module names `src/ui/main.py:377,:492` builds for the PRO plugins this lane
        # unblocks. Both halves contain `_`, which is what a rsplit gets wrong.
        ("bw_ui_blueprint_saml_saml_config", "saml_config.py", "saml"),
        ("bw_ui_blueprint_openidc_openidc_config", "openidc_config.py", "openidc"),
        ("bw_ui_blueprint_ui_sso_ui_sso", "ui_sso.py", "ui_sso"),
        ("bw_ui_blueprint_custom_pages_custom_pages", "custom_pages.py", "custom_pages"),
        ("bw_ui_blueprint_easy_resolve_easy_resolve", "easy_resolve.py", "easy_resolve"),
        ("bw_ui_hooks_user_manager_hooks", "hooks.py", "user_manager"),
        ("bw_ui_hooks_maintenance_hooks", "hooks.py", "maintenance"),
        # `main.py:381-383`, `:488-490` load the `*_proxy.py` file under the NON-proxy module name;
        # 16 such files ship in the PRO tree.
        ("bw_ui_hooks_ui_sso_hooks", "hooks_proxy.py", "ui_sso"),
        ("bw_ui_blueprint_saml_saml_config", "saml_config_proxy.py", "saml"),
        # `routes/plugins.py` loads an actions.py from a database blob under a uuid name
        ("bw_ui_actions_acme_9f2c1d4e8a", "actions.py", "acme"),
        ("bw_ui_actions_custom_pages_9f2c1d4e8a", "actions.py", "custom_pages"),
    ],
)
def test_the_plugin_name_survives_underscores_in_the_plugin_and_the_file(module, filename, expected):
    frame = SimpleNamespace(
        f_globals={"__name__": module},
        f_code=SimpleNamespace(co_filename=f"/tmp/whatever/{filename}"),
        f_lineno=1,
    )
    assert plugin_api_module._caller_plugin(frame) == expected


def test_an_installed_plugin_is_named_from_its_path_not_its_module_name(tmp_path, monkeypatch):
    """The installed location is authoritative: a plugin loaded from disk is named even when the
    module name says nothing (a `*_proxy.py` file, or a plugin renaming its own module)."""
    monkeypatch.setattr(plugin_api_module, "_PLUGIN_ROOTS", (tmp_path,))
    frame = SimpleNamespace(
        f_globals={"__name__": "whatever"},
        f_code=SimpleNamespace(co_filename=str(tmp_path / "user_manager" / "ui" / "hooks_proxy.py")),
        f_lineno=1,
    )
    assert plugin_api_module._caller_plugin(frame) == "user_manager"


def test_unattributable_code_falls_back_to_the_source_location():
    frame = SimpleNamespace(
        f_globals={"__name__": "some_helper"},
        f_code=SimpleNamespace(co_filename="/var/tmp/bunkerweb/ui/action/8f2/ui/helper.py"),
        f_lineno=42,
    )
    assert plugin_api_module._caller_plugin(frame) == "helper.py:42"


def test_retired_db_answers_protocol_probing_with_attributeerror(tmp_path):
    """`hasattr`/`copy`/`pickle` ask for dunders; a RuntimeError there is noise they cannot catch."""
    db = RetiredDB()
    assert not hasattr(db, "__deepcopy__")
    assert not hasattr(db, "__html__")
    with pytest.raises(RuntimeError):
        db.get_config


def test_retired_db_logs_the_plugin_before_raising(tmp_path, caplog):
    dependencies = ModuleType("app.dependencies")
    dependencies.DB = RetiredDB()

    with patch.dict(sys.modules, {"app.dependencies": dependencies}):
        module = _blueprint_module(
            tmp_path,
            "openidc",
            "from app.dependencies import DB\n\n\ndef page():\n    return DB.readonly\n",
        )
        with caplog.at_level("ERROR", logger="UI"), pytest.raises(RuntimeError):
            module.page()

    assert "'openidc'" in caplog.text


# --------------------------------------------------------------------------------------
# ui/actions.py -- the only UI point community plugins use
# --------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def plugins_route():
    """Load `routes/plugins.py` without booting container-only `app.dependencies` state."""
    client = MagicMock()
    client.readonly = False
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = client
    dependencies.BW_CONFIG = Mock()
    dependencies.BW_INSTANCES_UTILS = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.DB = RetiredDB()
    dependencies.PLUGIN_API = PluginApi(client)
    dependencies.CORE_PLUGINS_PATH = Path("/usr/share/bunkerweb/core")
    dependencies.EXTERNAL_PLUGINS_PATH = Path("/etc/bunkerweb/plugins")
    dependencies.PRO_PLUGINS_PATH = Path("/etc/bunkerweb/pro/plugins")

    # `qrcode` is not in the pared-down unit venv and only `routes/utils.py`'s 2FA helpers use it.
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main

    module_name = "app.routes._plugins_surface_test"
    spec = importlib.util.spec_from_file_location(module_name, _UI_ROOT / "app" / "routes" / "plugins.py")
    module = importlib.util.module_from_spec(spec)
    stubs = {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
        yield module, client


def _actions_plugin(tmp_path, plugin, body):
    ui_dir = tmp_path / plugin / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "actions.py").write_text(body, encoding="utf-8")
    return ui_dir


def _run(module, ui_dir, plugin, function_name=""):
    from flask import Flask

    app = Flask(__name__)
    with app.test_request_context("/"):
        return module.run_action(plugin, function_name, tmp_dir=ui_dir)


def test_actions_receive_the_accessor(tmp_path, plugins_route):
    """(a) a plugin page built from the accessor, fed by the API client."""
    module, client = plugins_route
    client.get_services.return_value = [{"id": "www.example.com"}]

    ui_dir = _actions_plugin(
        tmp_path,
        "clamav",
        "def pre_render(**kwargs):\n    return {'services': kwargs['api_client'].get_services(with_drafts=True)}\n",
    )
    result = _run(module, ui_dir, "clamav", "pre_render")

    assert result == {"status": "ok", "code": 200, "data": {"services": [{"id": "www.example.com"}]}}
    client.get_services.assert_called_with(with_drafts=True)


def test_actions_dereferencing_db_fail_with_the_actionable_message(tmp_path, plugins_route, caplog):
    """(b) `kwargs["db"].get_config()` -- what `letsencrypt` and 6 PRO plugins still do."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(
        tmp_path,
        "acme",
        "def pre_render(**kwargs):\n    return {'config': kwargs['db'].get_config()}\n",
    )

    with caplog.at_level("ERROR", logger="UI"):
        result = _run(module, ui_dir, "acme", "pre_render")

    assert result["status"] == "ko"
    assert result["code"] == 500
    assert "PLUGIN_API" in caplog.text
    assert "docs/plugins.md" in caplog.text


def test_actions_that_ignore_db_are_untouched(tmp_path, plugins_route):
    """(c) the shape every core and community `actions.py` already has: `**kwargs`, no `db`."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(
        tmp_path,
        "discord",
        "def pre_render(**kwargs):\n    return {'app': kwargs['app'] is not None, 'db_is_falsy': not kwargs['db']}\n",
    )

    assert _run(module, ui_dir, "discord", "pre_render") == {
        "status": "ok",
        "code": 200,
        "data": {"app": True, "db_is_falsy": True},
    }


# --------------------------------------------------------------------------------------
# The wiring in `app/dependencies.py` -- the import path `docs/plugins.md` promises
# --------------------------------------------------------------------------------------


def test_dependencies_wires_the_accessor_and_the_retired_handle():
    """`from app.dependencies import PLUGIN_API` is the path `docs/plugins.md` promises.

    Read statically: importing `app.dependencies` for real needs the container layout
    (`Config` opens `/usr/share/bunkerweb/settings.json`), and stubbing it would assert nothing.
    """
    import ast

    tree = ast.parse((_UI_ROOT / "app" / "dependencies.py").read_text(encoding="utf-8"))
    assigned = {target.id: node.value for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}

    assert isinstance(assigned["DB"], ast.Call) and assigned["DB"].func.id == "RetiredDB"
    plugin_api = assigned["PLUGIN_API"]
    assert isinstance(plugin_api, ast.Call) and plugin_api.func.id == "PluginApi"
    assert [arg.id for arg in plugin_api.args] == ["API_CLIENT"]

    # ... and both names come from `app.plugin_api`, not from a local definition of the same name
    imported = {alias.name for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "app.plugin_api" for alias in node.names}
    assert {"PluginApi", "RetiredDB"} <= imported


def test_an_unsupported_method_is_reported_as_the_plugin_error_it_is(tmp_path, plugins_route, caplog):
    """`run_action`'s `except AttributeError` used to swallow the plugin's own AttributeError and
    answer "the plugin does not have a method" -- which is exactly the wrong thing to tell someone
    who just called a method `PLUGIN_API` does not carry."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(
        tmp_path,
        "rogue",
        "def pre_render(**kwargs):\n    return {'u': kwargs['api_client'].create_user('bob')}\n",
    )

    with caplog.at_level("ERROR", logger="UI"):
        result = _run(module, ui_dir, "rogue", "pre_render")

    assert result["status"] == "ko"
    assert "does not have a method" not in result["message"]
    assert "create_user" in caplog.text
    assert "docs/plugins.md" in caplog.text


def test_a_missing_pre_render_leaves_sys_path_as_it_found_it(tmp_path, plugins_route):
    """The early return popped `sys.path` and then the `finally` popped it again, taking an
    unrelated entry with it."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(tmp_path, "nopre", "def nopre(**kwargs):\n    return {}\n")

    before = list(sys.path)
    result = _run(module, ui_dir, "nopre", "pre_render")

    assert result == {"status": "ok", "code": 200, "message": "The plugin does not have a pre_render method"}
    assert sys.path == before


def test_a_plugin_may_use_ordinary_modern_python(tmp_path, plugins_route):
    """The actions module must be registered in `sys.modules` while its body runs: the stdlib
    resolves a class's module through it (`dataclasses._is_type` dereferences
    `sys.modules.get(cls.__module__)` with no None guard), so an unregistered module turns any
    `@dataclass` in a plugin's actions.py into a 500 at import."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(
        tmp_path,
        "modern",
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "from typing import get_type_hints\n\n\n"
        "@dataclass\n"
        "class Row:\n"
        "    name: str\n\n\n"
        "def pre_render(**kwargs):\n"
        "    return {'row': Row('x').name, 'hints': sorted(get_type_hints(Row))}\n",
    )

    assert _run(module, ui_dir, "modern", "pre_render") == {
        "status": "ok",
        "code": 200,
        "data": {"row": "x", "hints": ["name"]},
    }


def test_the_actions_module_is_not_left_behind_in_sys_modules(tmp_path, plugins_route):
    """Registered for the call, removed after it -- a uuid per call would otherwise grow
    `sys.modules` without bound. Proven by mutation: drop the `sys_modules.pop` from `run_action`'s
    `finally` and this fails (`red-PX-UI-round3.txt`)."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(tmp_path, "tidy", "def pre_render(**kwargs):\n    return {}\n")

    before = {name for name in sys.modules if name.startswith("bw_ui_actions_")}
    _run(module, ui_dir, "tidy", "pre_render")
    assert {name for name in sys.modules if name.startswith("bw_ui_actions_")} == before


def test_a_module_level_getattr_that_raises_does_not_leak_the_load(tmp_path, plugins_route):
    """PEP 562: a plugin may define a module-level `__getattr__` (the lazy-import idiom). The
    three-argument `getattr` that looks the handler up swallows only `AttributeError`, so anything
    else it raises must still unwind the load -- the `sys.path` entry, the `sys.modules` entry and,
    for a DB-blob extraction, the temporary directory."""
    module, _ = plugins_route
    ui_dir = _actions_plugin(tmp_path, "lazy", "def __getattr__(name):\n    raise KeyError('boom')\n")

    path_before = list(sys.path)
    modules_before = {name for name in sys.modules if name.startswith("bw_ui_actions_")}

    result = _run(module, ui_dir, "lazy", "pre_render")

    assert result["status"] == "ko"
    assert result["code"] == 500
    assert sys.path == path_before
    assert {name for name in sys.modules if name.startswith("bw_ui_actions_")} == modules_before


def test_one_plugins_pre_render_does_not_leak_into_the_next(tmp_path, plugins_route):
    """Every `actions.py` loads under the module name "actions"; `load_module()` re-executes into
    the module already in `sys.modules` without clearing it, so plugin A's `pre_render` answered
    for plugin B, which has none."""
    module, _ = plugins_route
    first = _actions_plugin(tmp_path / "a", "leaky", "def pre_render(**kwargs):\n    return {'from': 'leaky'}\n")
    second = _actions_plugin(tmp_path / "b", "bare", "def bare(**kwargs):\n    return {}\n")

    assert _run(module, first, "leaky", "pre_render")["data"] == {"from": "leaky"}
    assert _run(module, second, "bare", "pre_render") == {
        "status": "ok",
        "code": 200,
        "message": "The plugin does not have a pre_render method",
    }
