"""RAW-editor setting drafts, UI side (1.6.15 #3631 ported to 1.7).

The 1.7 UI has no database access, so the draft map the RAW editor builds travels
route -> ``Config.edit_*`` -> ``api_client.save_config`` -> ``PUT /global_settings/config``.
These tests drive the real route tasks around stubbed collaborators and assert on what reaches
``edit_global_conf`` / ``edit_service``, which is what ``Database.save_config`` receives.
"""

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from app.api_client import BaseApiClient  # type: ignore  (src/ui on path via the ui conftest)
from app.models.config import Config  # type: ignore
from app.raw_drafts import RawDraftSettingsError, freeze_draft_edits, locked_draft_change, parse_raw_draft_settings  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[3]

SETTINGS = {
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
    "USE_TEMPLATE": {"type": "text", "regex": "^.*$", "context": "multisite"},
    "USE_GZIP": {"type": "check", "regex": "^(yes|no)$", "context": "multisite"},
    "USE_CORS": {"type": "check", "regex": "^(yes|no)$", "context": "multisite"},
    "WORKER_PROCESSES": {"type": "text", "regex": "^.*$", "context": "global"},
}


def _load(route: str, module_name: str) -> ModuleType:
    """Same loader as test_global_settings_propagation.py / test_service_save_flash_type.py."""
    dependencies = ModuleType("app.dependencies")
    dependencies.API_CLIENT = Mock()
    dependencies.BW_CONFIG = Mock()
    dependencies.CONFIG_TASKS_EXECUTOR = Mock()
    dependencies.DATA = Mock()
    dependencies.CORE_PLUGINS_PATH = REPO_ROOT / "src" / "common" / "core"
    qrcode = ModuleType("qrcode")
    qrcode_main = ModuleType("qrcode.main")
    qrcode_main.QRCode = Mock()
    qrcode.main = qrcode_main
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / "src" / "ui" / "app" / "routes" / route)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"app.dependencies": dependencies, "qrcode": qrcode, "qrcode.main": qrcode_main, module_name: module}):
        spec.loader.exec_module(module)
    return module


GLOBAL = _load("global_settings.py", "app.routes._global_settings_raw_drafts")
SERVICES = _load("services.py", "app.routes._services_raw_drafts")


class _FakeData(dict):
    def load_from_file(self):
        return None


# ---------------------------------------------------------------------------------------------
# The metadata parser (app/raw_drafts.py), ported verbatim from dev f8b314a93.


class TestParser:
    def test_every_present_key_gets_an_explicit_state(self):
        result = parse_raw_draft_settings(
            '["USE_GZIP"]', posted_keys={"USE_GZIP", "USE_CORS"}, present_value='["USE_GZIP", "USE_CORS"]', settings=SETTINGS, global_config=True
        )

        assert result == {"USE_GZIP": True, "USE_CORS": False}

    def test_a_saved_draft_missing_from_the_editor_is_deleted(self):
        result = parse_raw_draft_settings(
            "[]", posted_keys={"USE_GZIP"}, present_value="[]", existing_draft_keys=("USE_GZIP",), settings=SETTINGS, global_config=True
        )

        assert result == {"USE_GZIP": None}

    def test_service_keys_come_back_prefixed(self):
        result = parse_raw_draft_settings('["USE_CORS"]', posted_keys={"USE_CORS"}, service="app.example.com", present_value='["USE_CORS"]', settings=SETTINGS)

        assert result == {"app.example.com_USE_CORS": True}

    @pytest.mark.parametrize("key", ("USE_TEMPLATE", "SERVER_NAME"))
    def test_a_structural_key_is_refused(self, key):
        with pytest.raises(RawDraftSettingsError):
            parse_raw_draft_settings(f'["{key}"]', posted_keys={key}, present_value=f'["{key}"]', settings=SETTINGS, global_config=True)

    def test_a_global_only_setting_cannot_be_a_service_draft(self):
        with pytest.raises(RawDraftSettingsError):
            parse_raw_draft_settings(
                '["WORKER_PROCESSES"]', posted_keys={"WORKER_PROCESSES"}, service="app.example.com", present_value='["WORKER_PROCESSES"]', settings=SETTINGS
            )

    def test_malformed_metadata_is_refused(self):
        with pytest.raises(RawDraftSettingsError):
            parse_raw_draft_settings("not json", posted_keys=set(), present_value="[]", settings=SETTINGS)


class TestHelpers:
    def test_a_never_set_setting_may_be_drafted(self):
        """cf76f5bb7e: no stored row means no method yet, which is a default, which is editable."""
        assert locked_draft_change({"USE_GZIP": True}, {}) is None

    def test_a_method_the_ui_cannot_edit_cannot_change_state(self):
        error = locked_draft_change({"USE_GZIP": True}, {"USE_GZIP": {"value": "yes", "method": "autoconf"}})

        assert error and "autoconf" in error

    def test_outside_raw_a_drafted_field_goes_back_to_its_effective_value(self):
        variables = {"USE_GZIP": "maybe", "USE_CORS": "yes"}
        discarded = freeze_draft_edits(variables, {"USE_GZIP": {"value": "yes", "is_draft": True}}, {"USE_GZIP": {"value": "no"}})

        assert variables == {"USE_GZIP": "no", "USE_CORS": "yes"}
        assert discarded == {"USE_GZIP"}


# ---------------------------------------------------------------------------------------------
# The global page: the draft map reaches the save, and a draft is never copied onto services.


def _global_stored(*, drafted: bool):
    """``svc1`` inherits USE_GZIP (it shares the global entry object, as get_config returns it)."""
    effective = {"value": "no", "global": True, "method": "default", "default": "no", "template": None}
    config = {
        "SERVER_NAME": {"value": "svc1", "global": True, "method": "scheduler", "default": "", "template": None},
        "USE_GZIP": effective,
        "svc1_USE_GZIP": effective,
    }
    raw = deepcopy(config)
    if drafted:
        raw["USE_GZIP"] = {"value": "yes", "global": True, "method": "ui", "default": "no", "template": None, "is_draft": True}
    return config, raw


def _run_global(posted, *, draft_settings, drafted, override=True):
    effective, raw = _global_stored(drafted=drafted)
    data = _FakeData(TO_FLASH=[])
    captured = {}

    config = Config.__new__(Config)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
    config.edit_global_conf = lambda variables, **kwargs: (captured.update(payload=variables, **kwargs), ("Saved.", 0))[1]

    with patch.object(GLOBAL, "BW_CONFIG", config), patch.object(GLOBAL, "DATA", data), patch.object(GLOBAL, "wait_applying", lambda: None):
        GLOBAL.update_global_config(dict(posted), override, {}, scope=None, draft_settings=draft_settings)

    return captured, [entry["content"] for entry in data["TO_FLASH"]]


class TestGlobalSave:
    def test_drafting_a_value_sends_the_map_and_writes_nothing_onto_services(self):
        captured, _ = _run_global({"USE_GZIP": "yes"}, draft_settings={"USE_GZIP": True}, drafted=False)

        assert captured["draft_settings"] == {"USE_GZIP": True}
        assert captured["payload"]["USE_GZIP"] == "yes"
        assert "svc1_USE_GZIP" not in captured["payload"], "a draft is never applied, so it must not be propagated either"

    def test_activating_a_draft_propagates_like_any_change(self):
        captured, _ = _run_global({"USE_GZIP": "yes"}, draft_settings={"USE_GZIP": False}, drafted=True)

        assert captured["draft_settings"] == {"USE_GZIP": False}
        assert captured["payload"]["svc1_USE_GZIP"] == "yes"

    def test_an_unchanged_draft_is_not_a_change(self):
        captured, flashed = _run_global({"USE_GZIP": "yes"}, draft_settings={"USE_GZIP": True}, drafted=True)

        assert "payload" not in captured
        assert any("no values were changed" in message for message in flashed), flashed

    def test_outside_raw_an_edit_to_a_draft_is_discarded_and_said_so(self):
        captured, flashed = _run_global({"USE_GZIP": "yes"}, draft_settings=None, drafted=True)

        assert "payload" not in captured, "the only posted key was the draft, so nothing is left to save"
        assert any("Draft settings remain unchanged" in message for message in flashed), flashed


# ---------------------------------------------------------------------------------------------
# The service page.


def _run_service(posted, *, draft_settings, mode="raw"):
    api = Mock()
    effective = {"SERVER_NAME": {"value": "app.example.com", "method": "ui", "global": False}, "USE_CORS": {"value": "no", "method": "default", "global": True}}
    raw = effective | {"USE_CORS": {"value": "yes", "method": "ui", "global": False, "is_draft": True}}
    api.get_service.side_effect = lambda *args, **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
    api.get_configs.return_value = []
    api.get_templates.return_value = {}

    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = SETTINGS
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("Configuration for app.example.com has been edited.", 0)
    data = _FakeData(TO_FLASH=[])

    with (
        patch.object(SERVICES, "API_CLIENT", api),
        patch.object(SERVICES, "BW_CONFIG", bw_config),
        patch.object(SERVICES, "DATA", data),
        patch.object(SERVICES, "wait_applying", lambda: None),
    ):
        SERVICES.update_service("app.example.com", {"SERVER_NAME": "app.example.com"} | posted, False, mode, "", {}, draft_settings=draft_settings)

    return bw_config.edit_service, [entry["content"] for entry in data["TO_FLASH"]]


class TestServiceSave:
    def test_activating_a_draft_reaches_edit_service(self):
        edit_service, _ = _run_service({"USE_CORS": "yes"}, draft_settings={"app.example.com_USE_CORS": False})

        assert edit_service.called
        assert edit_service.call_args.kwargs["draft_settings"] == {"app.example.com_USE_CORS": False}

    def test_a_state_change_on_a_locked_setting_is_refused(self):
        api = Mock()
        locked = {"SERVER_NAME": {"value": "app.example.com", "method": "ui"}, "USE_CORS": {"value": "yes", "method": "autoconf", "is_draft": True}}
        api.get_service.side_effect = lambda *args, **kwargs: deepcopy(locked)
        api.get_configs.return_value = []
        for getter in ("get_upstreams", "get_certificates", "get_redirects", "get_workflows"):
            getattr(api, getter).return_value = {}
        bw_config = Mock()
        bw_config.get_plugins_settings.return_value = SETTINGS
        data = _FakeData(TO_FLASH=[])
        with (
            patch.object(SERVICES, "API_CLIENT", api),
            patch.object(SERVICES, "BW_CONFIG", bw_config),
            patch.object(SERVICES, "DATA", data),
            patch.object(SERVICES, "wait_applying", lambda: None),
        ):
            SERVICES.update_service(
                "app.example.com",
                {"SERVER_NAME": "app.example.com", "USE_CORS": "yes"},
                False,
                "raw",
                "",
                {},
                draft_settings={"app.example.com_USE_CORS": False},
            )

        assert not bw_config.edit_service.called
        assert any("autoconf" in entry["content"] for entry in data["TO_FLASH"])

    def test_outside_raw_the_drafted_field_is_frozen(self):
        # USE_GZIP is the unrelated edit that keeps the save going once the draft edit is dropped.
        edit_service, flashed = _run_service({"USE_CORS": "maybe", "USE_GZIP": "yes"}, draft_settings=None, mode="compose")

        assert edit_service.call_args.args[1]["USE_CORS"] == "no"
        assert edit_service.call_args.kwargs["draft_settings"] is None
        assert any("Draft settings remain unchanged" in message for message in flashed), flashed


# ---------------------------------------------------------------------------------------------
# The client: additive, so every save that is not a RAW one stays byte-identical.


class TestApiClient:
    @pytest.fixture
    def client(self):
        from app.api_client import ApiClient  # type: ignore

        client = ApiClient.__new__(ApiClient)
        client._put = Mock(return_value={})
        return client

    def test_no_map_no_field(self, client):
        client.save_config({"A": "b"}, "ui")

        assert "draft_settings" not in client._put.call_args.kwargs["json"]

    def test_the_map_is_sent_verbatim(self, client):
        client.save_config({"A": "b"}, "ui", draft_settings={"A": None})

        assert client._put.call_args.kwargs["json"]["draft_settings"] == {"A": None}


def test_the_client_class_is_the_one_the_ui_uses():
    assert issubclass(__import__("app.api_client", fromlist=["ApiClient"]).ApiClient, BaseApiClient)


# ---------------------------------------------------------------------------------------------
# The POST: only the RAW pane may carry draft metadata, and what it carries reaches the task.


def _post_global(query, form):
    from types import SimpleNamespace

    from flask import Flask

    api = Mock()
    api.readonly = False
    api.get_global_settings.return_value = {"USE_GZIP": {"value": "yes", "method": "ui", "global": True, "is_draft": True}}
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = SETTINGS
    executor = Mock()
    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(GLOBAL.global_settings)
    app.add_url_rule("/loading", "loading", lambda: "")
    with (
        patch.object(GLOBAL, "API_CLIENT", api),
        patch.object(GLOBAL, "BW_CONFIG", bw_config),
        patch.object(GLOBAL, "CONFIG_TASKS_EXECUTOR", executor),
        patch.object(GLOBAL, "DATA", _FakeData(TO_FLASH=[])),
        app.test_request_context(f"/global-settings{query}", method="POST", data={"csrf_token": "x"} | form),
        patch("app.utils.current_user", SimpleNamespace(list_permissions=["read", "write"])),
    ):
        GLOBAL.global_settings_page.__wrapped__()
    return executor.submit


class TestGlobalPost:
    def test_the_raw_pane_hands_the_parsed_map_to_the_task(self):
        submit = _post_global("?mode=raw", {"USE_GZIP": "yes", "USE_CORS": "yes", "RAW_PRESENT_SETTINGS": '["USE_CORS"]', "RAW_DRAFT_SETTINGS": '["USE_CORS"]'})

        assert submit.called
        # USE_GZIP was a saved draft the editor no longer shows: its row is deleted.
        assert submit.call_args.kwargs["draft_settings"] == {"USE_CORS": True, "USE_GZIP": None}
        assert "RAW_DRAFT_SETTINGS" not in submit.call_args.args[1]

    def test_another_pane_posting_draft_metadata_is_refused(self):
        submit = _post_global("", {"USE_CORS": "yes", "RAW_PRESENT_SETTINGS": '["USE_CORS"]', "RAW_DRAFT_SETTINGS": '["USE_CORS"]'})

        assert not submit.called

    def test_a_raw_post_without_metadata_changes_no_draft_state(self):
        submit = _post_global("?mode=raw", {"USE_CORS": "yes"})

        assert submit.called and submit.call_args.kwargs["draft_settings"] is None


# ---------------------------------------------------------------------------------------------
# The RAW page GET fails closed: a failed draft-aware read must never render the effective values
# as the editable state, or a later save would activate, overwrite or delete a retained draft.


def _get_page(module, view, url, api, bw_config):
    from types import SimpleNamespace

    from flask import Flask

    app = Flask(__name__)
    app.secret_key = "test"
    app.register_blueprint(module.global_settings if module is GLOBAL else module.services)
    for endpoint in ("home.home_page", "services.services_page"):
        if endpoint not in app.view_functions:
            app.add_url_rule("/" + endpoint, endpoint, lambda: "")
    render = Mock(return_value="rendered")
    with (
        patch.object(module, "API_CLIENT", api),
        patch.object(module, "BW_CONFIG", bw_config),
        patch.object(module, "render_template", render),
        patch.object(module, "flash", Mock()),
        app.test_request_context(url),
        patch("app.utils.current_user", SimpleNamespace(list_permissions=["read", "write"])),
    ):
        response = view()
    return response, render


class TestRawPageFailsClosed:
    def test_global_page_refuses_when_the_draft_read_fails(self):
        def get_global_settings(**kwargs):
            if kwargs.get("with_setting_drafts"):
                raise GLOBAL.ApiUnavailableError("down")
            return {"USE_GZIP": {"value": "no", "method": "default", "global": True}}

        api = Mock()
        api.get_global_settings.side_effect = get_global_settings
        bw_config = Mock()
        bw_config.get_plugins_settings.return_value = SETTINGS
        response, render = _get_page(GLOBAL, GLOBAL.global_settings_page.__wrapped__, "/global-settings?mode=raw", api, bw_config)

        assert not render.called
        assert getattr(response, "status_code", None) == 302

    def test_service_page_refuses_when_the_draft_read_fails(self):
        def get_service(service, **kwargs):
            if kwargs.get("with_setting_drafts"):
                raise SERVICES.ApiUnavailableError("down")
            return {"USE_GZIP": {"value": "no", "method": "ui", "global": False}}

        api = Mock()
        api.get_service.side_effect = get_service
        api.get_templates.return_value = {}
        api.get_configs.return_value = []
        for getter in ("get_upstreams", "get_certificates", "get_redirects", "get_workflows"):
            getattr(api, getter).return_value = {}
        bw_config = Mock()
        bw_config.get_config.return_value = {"SERVER_NAME": "www.example.com"}
        response, render = _get_page(
            SERVICES, lambda: SERVICES.services_service_page.__wrapped__("www.example.com"), "/services/www.example.com?mode=raw", api, bw_config
        )

        assert not render.called
        assert getattr(response, "status_code", None) == 302
