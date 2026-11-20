"""Long service timeouts must not lengthen the default server's TLS handshake timer."""

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from fixtures.seed import make_core_plugin


def timeouts(text):
    return re.findall(r"^\s*(client_(?:body|header)_timeout\s+[^;]+;)", text, re.M)


def assert_service_timeouts(tree):
    assert timeouts(tree["http.conf"]) == ["client_body_timeout 12s;", "client_header_timeout 13s;"]
    assert timeouts(tree["grpc.example.com/server.conf"]) == ["client_body_timeout 2d;", "client_header_timeout 1d;"]
    assert timeouts(tree["web.example.com/server.conf"]) == []
    assert timeouts(tree["default-server-http.conf"]) == []


def test_service_overrides_leave_global_and_default_server_timeouts_unchanged(render_tree):
    tree = render_tree(
        MULTISITE="yes",
        SERVER_NAME="grpc.example.com web.example.com",
        CLIENT_BODY_TIMEOUT="12s",
        CLIENT_HEADER_TIMEOUT="13s",
        **{"grpc.example.com_CLIENT_BODY_TIMEOUT": "2d", "grpc.example.com_CLIENT_HEADER_TIMEOUT": "1d"},
    )
    assert_service_timeouts(tree)


def test_scheduler_database_path_keeps_service_overrides_and_global_fallback(render_db_tree):
    tree = render_db_tree(
        {"CLIENT_BODY_TIMEOUT": "12s", "CLIENT_HEADER_TIMEOUT": "13s"},
        {"grpc.example.com": {"CLIENT_BODY_TIMEOUT": "2d", "CLIENT_HEADER_TIMEOUT": "1d"}, "web.example.com": {}},
    )
    assert_service_timeouts(tree)


def test_single_site_keeps_global_timeouts(render_tree):
    tree = render_tree(MULTISITE="no", SERVER_NAME="app.example.com", CLIENT_BODY_TIMEOUT="12s", CLIENT_HEADER_TIMEOUT="13s")
    assert timeouts(tree["server.conf"]) == []
    assert timeouts(tree["http.conf"]) == ["client_body_timeout 12s;", "client_header_timeout 13s;"]


def test_service_values_equal_to_global_inherit_without_duplicate_directives(render_tree):
    tree = render_tree(
        MULTISITE="yes",
        SERVER_NAME="app.example.com",
        CLIENT_BODY_TIMEOUT="12s",
        CLIENT_HEADER_TIMEOUT="13s",
        **{"app.example.com_CLIENT_BODY_TIMEOUT": "12s", "app.example.com_CLIENT_HEADER_TIMEOUT": "13s"},
    )
    assert timeouts(tree["app.example.com/server.conf"]) == []
    assert timeouts(tree["default-server-http.conf"]) == []


@pytest.mark.parametrize("setting", ["CLIENT_BODY_TIMEOUT", "CLIENT_HEADER_TIMEOUT"])
def test_only_overridden_timeout_is_emitted(render_tree, setting):
    tree = render_tree(MULTISITE="yes", SERVER_NAME="app.example.com", **{f"app.example.com_{setting}": "1d"})
    assert timeouts(tree["app.example.com/server.conf"]) == [f"{setting.lower()} 1d;"]
    assert timeouts(tree["http.conf"]) == ["client_body_timeout 10s;", "client_header_timeout 10s;"]


def test_database_default_globals_do_not_emit_server_timeouts(render_db_tree):
    tree = render_db_tree({}, {"app.example.com": {}})
    assert timeouts(tree["http.conf"]) == ["client_body_timeout 10s;", "client_header_timeout 10s;"]
    assert timeouts(tree["app.example.com/server.conf"]) == []


def test_database_override_compares_with_default_global_value(render_db_tree):
    tree = render_db_tree({}, {"grpc.example.com": {"CLIENT_HEADER_TIMEOUT": "1d"}})
    assert timeouts(tree["http.conf"]) == ["client_body_timeout 10s;", "client_header_timeout 10s;"]
    assert timeouts(tree["grpc.example.com/server.conf"]) == ["client_header_timeout 1d;"]


@pytest.mark.parametrize("setting", ["CLIENT_BODY_TIMEOUT", "CLIENT_HEADER_TIMEOUT"])
def test_invalid_service_timeout_still_falls_back_to_global(render_tree, setting):
    tree = render_tree(MULTISITE="yes", SERVER_NAME="app.example.com", **{setting: "12s", f"app.example.com_{setting}": "invalid"})
    assert timeouts(tree["app.example.com/server.conf"]) == []
    assert f"{setting.lower()} 12s;" in timeouts(tree["http.conf"])


def test_settings_sync_upgrades_context_without_losing_global_values(db):
    settings = json.loads((Path(__file__).resolve().parents[3] / "src/common/settings.json").read_text())
    old_settings = deepcopy(settings)
    for name in ("CLIENT_BODY_TIMEOUT", "CLIENT_HEADER_TIMEOUT"):
        old_settings[name]["context"] = "global"
    ok, err = db.init_tables([make_core_plugin("general", settings=old_settings)])
    assert ok, err
    assert not isinstance(db.save_config({"CLIENT_BODY_TIMEOUT": "12s", "CLIENT_HEADER_TIMEOUT": "13s"}, "scheduler"), str)

    ok, err = db.init_tables([make_core_plugin("general", settings=settings)])
    assert ok, err
    catalog = {plugin["id"]: plugin for plugin in db.get_plugins()}
    assert catalog["general"]["settings"]["CLIENT_BODY_TIMEOUT"]["context"] == "multisite"
    assert catalog["general"]["settings"]["CLIENT_HEADER_TIMEOUT"]["context"] == "multisite"
    config = db.get_config()
    assert config["CLIENT_BODY_TIMEOUT"] == "12s"
    assert config["CLIENT_HEADER_TIMEOUT"] == "13s"
