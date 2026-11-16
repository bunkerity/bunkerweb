"""Global compose saves preserve service settings, including the reserved default server."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask
from starlette.responses import JSONResponse
from werkzeug.datastructures import MultiDict

from app.models.config import Config
from fixtures.seed import FIXED_DT, add_service_setting, session
from model import Template_settings, Templates
from test_global_settings_propagation import _FakeData, _MODULE, _real_plugins

ROOT = Path(__file__).resolve().parents[3]
# Successful controls in DOM order: a checked switch precedes its hidden "no" fallback.
SWITCHES = {
    "USE_ANTIBOT": "no",
    "USE_AUTH_BASIC": "no",
    "USE_BACKUP": "yes",
    "USE_BAD_BEHAVIOR": "yes",
    "USE_BROTLI": "no",
    "USE_CORS": "no",
    "USE_CROWDSEC": "no",
    "USE_CUSTOM_SSL": "no",
    "USE_DNSBL": "yes",
    "USE_GREYLIST": "no",
    "USE_GRPC": "no",
    "AUTO_LETS_ENCRYPT": "no",
    "USE_LIMIT_REQ": "yes",
    "USE_LIMIT_REQ_GLOBAL": "no",
    "USE_LIMIT_CONN": "yes",
    "USE_METRICS": "yes",
    "USE_MODSECURITY": "yes",
    "USE_MTLS": "no",
    "USE_REAL_IP": "no",
    "USE_REVERSE_PROXY": "no",
    "USE_REVERSE_SCAN": "no",
    "USE_ROBOTSTXT": "no",
    "USE_SECURITYTXT": "no",
    "GENERATE_SELF_SIGNED_SSL": "no",
    "USE_UI": "no",
}


@pytest.fixture
def saved(db, monkeypatch):
    plugins = _real_plugins()
    general = json.loads((ROOT / "src/common/settings.json").read_text())
    db.init_tables([deepcopy(general), *deepcopy(list(plugins.values()))])
    db.initialize_db("1.7.0", "Docker")
    names = ["www.example.com", "api.example.com", "app1.example.com"]
    initial = {"MULTISITE": "yes", "SERVER_NAME": " ".join(names), "USE_BLACKLIST": "no", "USE_WHITELIST": "no"}
    initial.update({f"{name}_SERVER_NAME": name for name in names})
    assert not isinstance(db.save_config(initial, "scheduler"), str)
    with session(db) as s:
        s.add(Templates(id="api", name="API", method="manual", creation_date=FIXED_DT, last_update=FIXED_DT))
        s.flush()
        s.add(Template_settings(template_id="api", setting_id="AUTO_REDIRECT_HTTP_TO_HTTPS", step_id=1, default="no", suffix=0, order=0))
    # A service template supplies this value without a stored override.
    add_service_setting(db, service_id="api.example.com", setting_id="USE_TEMPLATE", value="api", method="ui")

    # Reuse the API suite's isolated router loader to avoid colliding with the UI's app package.
    monkeypatch.syspath_prepend(str(ROOT / "src/api/app"))
    spec = importlib.util.spec_from_file_location("roundtrip_api", ROOT / "tests/unit/api/test_reportable_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    router = module.GLOBAL_SETTINGS
    monkeypatch.setattr(router, "get_db", lambda: db)
    monkeypatch.setattr(router, "JSONResponse", JSONResponse)

    class Client:
        def get_global_settings(self, **kwargs):
            kwargs.setdefault("filtered_settings", None)
            return json.loads(router.read_global_settings(**kwargs).body)["settings"]

        def save_config(self, conf, method, **kwargs):
            result = db.save_config(conf, method, **kwargs)
            assert not isinstance(result, str), result
            return {"changed_plugins": list(result)}

    data = _FakeData(TO_FLASH=[])
    config = Config.__new__(Config)
    config._Config__api_client = Client()
    config._Config__settings = general
    config._Config__data = data
    config._Config__ignore_regex_check = False
    config.get_plugins = lambda **kwargs: plugins
    monkeypatch.setattr(_MODULE, "BW_CONFIG", config)
    monkeypatch.setattr(_MODULE, "DATA", data)
    monkeypatch.setattr(_MODULE, "wait_applying", lambda: None)
    return db, config, router


def _compose_save(config, edits=None):
    form = MultiDict([("OVERRIDE_NON_GLOBAL_SERVICES", "no")])
    for key, value in (SWITCHES | (edits or {})).items():
        form.add(key, value)
        if value == "yes":
            form.add(key, "no")
    values = form.to_dict()
    override = values.pop("OVERRIDE_NON_GLOBAL_SERVICES") == "yes"
    scope = _MODULE.postable_shelf_scope(
        config.get_plugins(), config.get_config(), global_page=True, is_pro_version=False, blacklisted=_MODULE.get_blacklisted_settings(True), is_readonly=False
    )
    with Flask(__name__).app_context():
        _MODULE.update_global_config(values, override, {}, scope=scope)


def _snapshot(router):
    return router.read_global_settings(methods=True, with_drafts=True, global_only=False, filtered_settings=None).body


def test_compose_noop_preserves_global_and_service_settings_byte_for_byte(saved):
    db, config, router = saved
    before = _snapshot(router)
    assert "default-server_AUTO_REDIRECT_HTTP_TO_HTTPS" in json.loads(before)["settings"]
    assert "api.example.com_AUTO_REDIRECT_HTTP_TO_HTTPS" not in db.get_non_default_settings()
    _compose_save(config)
    assert _snapshot(router) == before


def test_real_global_edit_preserves_default_server_redirect_pins(saved):
    db, config, router = saved
    before = json.loads(_snapshot(router))["settings"]
    _compose_save(config, {"USE_CORS": "yes"})
    after = json.loads(_snapshot(router))["settings"]
    assert db.get_config(global_only=True)["USE_CORS"] == "yes"
    for key in ("AUTO_REDIRECT_HTTP_TO_HTTPS", "REDIRECT_HTTP_TO_HTTPS"):
        assert after[f"default-server_{key}"] == before[f"default-server_{key}"]
