"""Plugin activation contracts shared with dev."""

import pytest

from app.utils import is_plugin_active

LEGACY_ALWAYS = ("general", "errors", "headers", "misc", "pro", "sessions", "ssl")


def _cfg(**pairs):
    return {key: {"value": value} for key, value in pairs.items()}


@pytest.mark.parametrize("plugin_id", LEGACY_ALWAYS)
def test_always_on_plugins_stay_active_with_empty_config(plugin_id):
    assert is_plugin_active(plugin_id, plugin_id.capitalize(), {}) is True


def test_declared_map_any_key_differing_means_active():
    assert is_plugin_active("limit", "Limit", _cfg(USE_LIMIT_REQ="no", USE_LIMIT_CONN="yes")) is True
    assert is_plugin_active("limit", "Limit", _cfg(USE_LIMIT_REQ="yes", USE_LIMIT_CONN="no")) is True
    assert is_plugin_active("limit", "Limit", _cfg(USE_LIMIT_REQ="no", USE_LIMIT_CONN="no")) is False


def test_empty_string_inactive_value():
    assert is_plugin_active("redirect", "Redirect", _cfg(REDIRECT_TO="")) is False
    assert is_plugin_active("redirect", "Redirect", _cfg(REDIRECT_TO="https://x")) is True


def test_non_boolean_select_activation():
    assert is_plugin_active("antibot", "Antibot", _cfg(USE_ANTIBOT="no")) is False
    assert is_plugin_active("antibot", "Antibot", _cfg(USE_ANTIBOT="captcha")) is True


def test_heuristic_tier_still_resolves_by_id_and_by_name():
    assert is_plugin_active("badbehavior", "Bad behavior", _cfg(USE_BAD_BEHAVIOR="yes")) is True
    assert is_plugin_active("badbehavior", "Bad behavior", _cfg(USE_BAD_BEHAVIOR="no")) is False
    assert is_plugin_active("realip", "Real IP", _cfg(USE_REAL_IP="yes")) is True
    assert is_plugin_active("mtls", "mTLS", _cfg(USE_MTLS="yes")) is True


def test_undeclared_external_plugin_defaults_inactive_not_always_on():
    """A third-party plugin that declares nothing and has no USE_ key must read inactive."""
    assert is_plugin_active("acmeplugin", "Acme Plugin", {}) is False


def test_every_core_plugin_resolves_without_error_on_an_empty_config():
    """Smoke: no core plugin id raises or returns a non-bool, whichever tier it lands in."""
    import json
    from pathlib import Path

    core = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
    for plugin_json in sorted(core.glob("*/plugin.json")):
        manifest = json.loads(plugin_json.read_text(encoding="utf-8"))
        plugin_id = manifest.get("id") or plugin_json.parent.name
        verdict = is_plugin_active(plugin_id, manifest.get("name", plugin_id), {})
        assert isinstance(verdict, bool), plugin_id
