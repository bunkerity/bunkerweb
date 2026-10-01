"""RAW editor x secret settings: the placeholder must restore to what the RAW page was rendered from.

The RAW page renders a retained draft value (redacted); posting it back unchanged must keep that
draft byte-identical. Outside a draft the effective value is what is kept (main's behaviour).
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.models.config import Config  # type: ignore
from app.models.secret_settings import SECRET_PLACEHOLDER  # type: ignore

from test_raw_setting_drafts import GLOBAL, SERVICES, _FakeData  # type: ignore

EFFECTIVE, DRAFT = "effective-secret", "draft-secret"
SETTINGS = {
    "SERVER_NAME": {"type": "text", "regex": "^.*$", "context": "multisite"},
    "GLOBAL_SECRET": {"type": "password", "regex": "^.*$", "context": "global"},
    "API_SECRET": {"type": "password", "regex": "^.*$", "context": "multisite"},
}


def _entry(value, **extra):
    return {"value": value, "global": True, "method": "ui", "default": "", "template": None} | extra


def _stored(key, *, drafted):
    effective = {"SERVER_NAME": _entry("svc1", method="scheduler"), key: _entry(EFFECTIVE)}
    raw = deepcopy(effective)
    if drafted:
        raw[key] = _entry(DRAFT, is_draft=True)
    return effective, raw


def _run_global(posted, *, drafted):
    effective, raw = _stored("GLOBAL_SECRET", drafted=drafted)
    data = _FakeData(TO_FLASH=[])
    captured = {}
    config = Config.__new__(Config)
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins_settings = lambda: SETTINGS
    config.get_config = lambda **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
    config.edit_global_conf = lambda variables, **kwargs: (captured.update(payload=variables, **kwargs), ("Saved.", 0))[1]
    with patch.object(GLOBAL, "BW_CONFIG", config), patch.object(GLOBAL, "DATA", data), patch.object(GLOBAL, "wait_applying", lambda: None):
        GLOBAL.update_global_config(dict(posted), False, {}, scope=None, draft_settings={"GLOBAL_SECRET": drafted})
    return captured


def _run_service(posted, *, drafted):
    key = "API_SECRET"
    effective, raw = _stored(key, drafted=drafted)
    effective["SERVER_NAME"] = raw["SERVER_NAME"] = {"value": "app.example.com", "method": "ui", "global": False}
    for snapshot in (effective, raw):
        snapshot[key]["global"] = False
    api = Mock()
    api.get_service.side_effect = lambda *args, **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = SETTINGS
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.edit_service.return_value = ("edited", 0)
    data = _FakeData(TO_FLASH=[])
    with (
        patch.object(SERVICES, "API_CLIENT", api),
        patch.object(SERVICES, "BW_CONFIG", bw_config),
        patch.object(SERVICES, "DATA", data),
        patch.object(SERVICES, "wait_applying", lambda: None),
    ):
        SERVICES.update_service(
            "app.example.com", {"SERVER_NAME": "app.example.com"} | posted, False, "raw", "", {}, draft_settings={f"app.example.com_{key}": drafted}
        )
    edit = bw_config.edit_service
    return {"payload": edit.call_args.args[1], **edit.call_args.kwargs} if edit.called else {}


RUNNERS = [pytest.param(_run_global, "GLOBAL_SECRET", None, id="global"), pytest.param(_run_service, "API_SECRET", "app.example.com_", id="service")]


def _payload_value(captured, key, prefix):
    payload = captured["payload"]
    return payload.get(key, payload.get(f"{prefix or ''}{key}"))


@pytest.mark.parametrize("drafted", [True, False], ids=["draft", "no-draft"])
@pytest.mark.parametrize("run,key,prefix", RUNNERS)
class TestSecretRoundTrip:
    def test_unchanged_post_keeps_the_stored_value(self, run, key, prefix, drafted):
        captured = run({key: SECRET_PLACEHOLDER}, drafted=drafted)
        expected = DRAFT if drafted else EFFECTIVE
        if captured:  # a no-op save writes nothing, which also keeps it
            assert _payload_value(captured, key, prefix) == expected
            assert captured["draft_settings"][f"{prefix or ''}{key}"] is drafted, "a draft stays a draft"

    def test_a_new_clear_value_is_stored(self, run, key, prefix, drafted):
        captured = run({key: "brand-new"}, drafted=drafted)
        assert _payload_value(captured, key, prefix) == "brand-new"
        assert captured["draft_settings"][f"{prefix or ''}{key}"] is drafted


# (a) the RAW page never renders a secret in clear.
def _render(module, view, url, api, bw_config):
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
        view()
    return render.call_args.kwargs


@pytest.mark.parametrize("drafted", [True, False], ids=["draft", "no-draft"])
class TestRawPageRendersNoSecret:
    def test_global(self, drafted):
        effective, raw = _stored("GLOBAL_SECRET", drafted=drafted)
        api = Mock()
        api.get_global_settings.side_effect = lambda **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
        bw_config = Mock()
        bw_config.get_plugins_settings.return_value = SETTINGS
        bw_config.get_plugins.return_value = []
        bw_config.get_config.return_value = deepcopy(effective)
        kwargs = _render(GLOBAL, GLOBAL.global_settings_page.__wrapped__, "/global-settings?mode=raw", api, bw_config)
        rendered = repr((kwargs["raw_draft_config"], kwargs["config"]))
        assert EFFECTIVE not in rendered and DRAFT not in rendered

    def test_service(self, drafted):
        effective, raw = _stored("API_SECRET", drafted=drafted)
        api = Mock()
        api.get_service.side_effect = lambda *args, **kwargs: deepcopy(raw if kwargs.get("with_setting_drafts") else effective)
        api.get_templates.return_value = {}
        api.get_configs.return_value = []
        for getter in ("get_upstreams", "get_certificates", "get_redirects", "get_workflows"):
            getattr(api, getter).return_value = {}
        bw_config = Mock()
        bw_config.get_config.return_value = {"SERVER_NAME": "app.example.com"}
        bw_config.get_plugins_settings.return_value = SETTINGS
        kwargs = _render(SERVICES, lambda: SERVICES.services_service_page.__wrapped__("app.example.com"), "/services/app.example.com?mode=raw", api, bw_config)
        rendered = repr((kwargs["raw_draft_config"], kwargs["config"]))
        assert EFFECTIVE not in rendered and DRAFT not in rendered


# (b) a RAW clone: the new service has no drafts of its own, the placeholder stands for the SOURCE's retained draft.
def _run_raw_clone(posted, *, drafted):
    key, source = "API_SECRET", "src.example.com"
    effective, raw = _stored(key, drafted=drafted)
    for snapshot in (effective, raw):
        snapshot["SERVER_NAME"] = {"value": source, "method": "ui", "global": False}
        snapshot[key]["global"] = False

    def get_service(name, full=False, methods=True, with_drafts=True, with_setting_drafts=False):
        assert name == source
        if not methods:  # plain values under the source's prefix, as the API answers
            return {f"{source}_{k}": v["value"] for k, v in effective.items()}
        return deepcopy(raw if with_setting_drafts else effective)

    api = Mock()
    api.get_service.side_effect = get_service
    api.get_global_settings.return_value = {}
    api.get_configs.return_value = []
    api.get_templates.return_value = {}
    bw_config = Mock()
    bw_config.get_plugins_settings.return_value = SETTINGS
    bw_config.check_variables.side_effect = lambda variables, *args, **kwargs: variables
    bw_config.new_service.return_value = ("created", 0)
    data = _FakeData(TO_FLASH=[])
    with (
        patch.object(SERVICES, "API_CLIENT", api),
        patch.object(SERVICES, "BW_CONFIG", bw_config),
        patch.object(SERVICES, "DATA", data),
        patch.object(SERVICES, "wait_applying", lambda: None),
    ):
        SERVICES.update_service(
            "new", {"SERVER_NAME": "new.example.com"} | posted, False, "raw", source, {}, draft_settings={f"new.example.com_{key}": drafted}
        )
    call = bw_config.new_service
    return {"payload": call.call_args.args[0], **call.call_args.kwargs} if call.called else {}


@pytest.mark.parametrize("drafted", [True, False], ids=["draft", "no-draft"])
def test_a_raw_clone_restores_the_placeholder_from_the_sources_draft(drafted):
    captured = _run_raw_clone({"API_SECRET": SECRET_PLACEHOLDER}, drafted=drafted)
    assert captured, "the clone was created"
    payload = captured["payload"]
    assert payload.get("API_SECRET", payload.get("new.example.com_API_SECRET")) == (DRAFT if drafted else EFFECTIVE)
    assert captured["draft_settings"]["new.example.com_API_SECRET"] is drafted
