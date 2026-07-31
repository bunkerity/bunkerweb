"""Three-tier activation resolution, and parity with the tables it replaces."""

import pytest

import app.utils as app_utils
from app.utils import is_plugin_active

# The exact tables that used to live in app/utils.py, kept here as the parity oracle.
LEGACY_SPECIFICS = {
    "COUNTRY": {"BLACKLIST_COUNTRY": "", "WHITELIST_COUNTRY": ""},
    "CUSTOMCERT": {"USE_CUSTOM_SSL": "no"},
    "INJECT": {"INJECT_BODY": "", "INJECT_HEAD": ""},
    "LETSENCRYPT": {"AUTO_LETS_ENCRYPT": "no"},
    "LIMIT": {"USE_LIMIT_REQ": "no", "USE_LIMIT_CONN": "no"},
    "PHP": {"REMOTE_PHP": "", "LOCAL_PHP": ""},
    "REDIRECT": {"REDIRECT_TO": ""},
    "SELFSIGNED": {"GENERATE_SELF_SIGNED_SSL": "no"},
}
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
    # No manifest declaration: these must keep working exactly as before.
    assert is_plugin_active("badbehavior", "Bad behavior", _cfg(USE_BAD_BEHAVIOR="yes")) is True
    assert is_plugin_active("badbehavior", "Bad behavior", _cfg(USE_BAD_BEHAVIOR="no")) is False
    assert is_plugin_active("realip", "Real IP", _cfg(USE_REAL_IP="yes")) is True
    assert is_plugin_active("mtls", "mTLS", _cfg(USE_MTLS="yes")) is True


def test_undeclared_external_plugin_defaults_inactive_not_always_on():
    """A third-party plugin that declares nothing and has no USE_ key must read inactive."""
    assert is_plugin_active("acmeplugin", "Acme Plugin", {}) is False


class TestActivationMapUnreadable:
    """get_activation_map()'s try/except is meant for a broken/unreadable plugin tree (disk I/O,
    permissions), not per-plugin bad JSON (iter_plugin_activations already isolates that). Pins
    down the accepted, documented ceiling: on that failure every non-``general`` always-on
    plugin (errors/headers/misc/pro/sessions/ssl — none declare a USE_* setting) silently reads
    as inactive rather than crashing the plugins page. See the ``# ponytail`` comment on
    ``get_activation_map`` for the upgrade path if this ever needs to be safer."""

    def setup_method(self):
        app_utils.get_activation_map.cache_clear()

    def teardown_method(self):
        app_utils.get_activation_map.cache_clear()

    def test_scan_failure_falls_back_to_conventions_not_a_crash(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise OSError("plugin tree unreadable")

        monkeypatch.setattr(app_utils, "iter_plugin_activations", _boom)
        assert app_utils.get_activation_map() == {}

    @pytest.mark.parametrize("plugin_id", ("errors", "headers", "misc", "pro", "sessions", "ssl"))
    def test_normally_always_on_plugins_silently_read_inactive_on_scan_failure(self, monkeypatch, plugin_id):
        monkeypatch.setattr(app_utils, "iter_plugin_activations", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
        assert is_plugin_active(plugin_id, plugin_id.capitalize(), {}) is False

    def test_general_is_unaffected_by_scan_failure(self, monkeypatch):
        # `general` is hardcoded (_SYNTHESIZED_ALWAYS_ON), checked before get_activation_map is
        # ever consulted, so it must stay active even while the manifest scan is broken.
        monkeypatch.setattr(app_utils, "iter_plugin_activations", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
        assert is_plugin_active("general", "General", {}) is True


# --- Task 7: attachment-aware activation -----------------------------------------


def test_redirect_reads_active_when_a_redirect_resource_is_attached():
    from app.models.plugin_activation import is_plugin_active_for_service

    attachments = {
        "upstream": {"items": [], "error": None},
        "certificate": {"items": [], "error": None},
        "redirect": {"items": [{"id": "r1"}], "error": None},
        "workflow": {"items": [], "error": None},
    }
    # REDIRECT_TO is empty, so settings alone say inactive — the attachment is what makes it active.
    assert is_plugin_active_for_service("redirect", "Redirect", {"REDIRECT_TO": {"value": ""}}, attachments) is True


def test_no_attachment_falls_back_to_the_settings_verdict():
    from app.models.plugin_activation import is_plugin_active_for_service

    empty = {family: {"items": [], "error": None} for family in ("upstream", "certificate", "redirect", "workflow")}
    assert is_plugin_active_for_service("redirect", "Redirect", {"REDIRECT_TO": {"value": ""}}, empty) is False
    assert is_plugin_active_for_service("redirect", "Redirect", {"REDIRECT_TO": {"value": "https://x"}}, empty) is True


def test_unrelated_plugin_is_unaffected_by_attachments():
    from app.models.plugin_activation import is_plugin_active_for_service

    attachments = {"redirect": {"items": [{"id": "r1"}], "error": None}}
    assert is_plugin_active_for_service("limit", "Limit", {"USE_LIMIT_REQ": {"value": "no"}, "USE_LIMIT_CONN": {"value": "no"}}, attachments) is False


def test_failed_family_read_is_treated_as_no_attachments():
    """A dead resource API (non-null error, empty items) must not flip the verdict."""
    from app.models.plugin_activation import is_plugin_active_for_service

    attachments = {
        "upstream": {"items": [], "error": None},
        "certificate": {"items": [], "error": None},
        "redirect": {"items": [], "error": "upstream unavailable"},
        "workflow": {"items": [], "error": None},
    }
    assert is_plugin_active_for_service("redirect", "Redirect", {"REDIRECT_TO": {"value": ""}}, attachments) is False


def test_certificate_family_is_not_wired_to_any_plugin():
    """Certificates are deliberately excluded (open-ended set of owning plugins,
    discovered at runtime via extensions.certificate_source) -- an attached certificate
    must not flip customcert/letsencrypt/selfsigned active on its own."""
    from app.models.plugin_activation import is_plugin_active_for_service

    attachments = {
        "upstream": {"items": [], "error": None},
        "certificate": {"items": [{"id": "c1"}], "error": None},
        "redirect": {"items": [], "error": None},
        "workflow": {"items": [], "error": None},
    }
    assert is_plugin_active_for_service("customcert", "Custom SSL Certificate", {"USE_CUSTOM_SSL": {"value": "no"}}, attachments) is False
    assert is_plugin_active_for_service("letsencrypt", "Let's Encrypt", {"AUTO_LETS_ENCRYPT": {"value": "no"}}, attachments) is False
    assert is_plugin_active_for_service("selfsigned", "Self-signed certificate", {"GENERATE_SELF_SIGNED_SSL": {"value": "no"}}, attachments) is False


# --- Task 8: parity guard ---------------------------------------------------------


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


def test_declared_plugins_are_inactive_on_an_empty_config_unless_always():
    """A declared map with an empty config must read inactive — not accidentally always-on."""
    import json
    from pathlib import Path

    # NOTE: the task brief's import (`from utils.plugin_extensions import ...`) does not
    # resolve in this repo's test layout: tests/unit/conftest.py puts src/common/utils
    # directly on sys.path (bare-import layout), so the module is importable as the
    # top-level `plugin_extensions`, not as a submodule of a `utils` package. Verified
    # empirically: `from utils.plugin_extensions import iter_plugin_activations` raises
    # `ModuleNotFoundError: No module named 'utils.plugin_extensions'`. This matches how
    # both app/utils.py and this directory's conftest.py already import it.
    from plugin_extensions import iter_plugin_activations

    core = Path(__file__).resolve().parents[3] / "src" / "common" / "core"
    for plugin_id, declaration in iter_plugin_activations(paths=[(core, "core")]).items():
        if declaration == "always":
            continue
        manifest = json.loads((core / plugin_id / "plugin.json").read_text(encoding="utf-8"))
        assert is_plugin_active(plugin_id, manifest.get("name", plugin_id), {}) is False, plugin_id


# --- Task 7 wiring: the plugin-activated nav icon ---------------------------------------------
#
# Removed in S3.4 T9. It rendered `{{ ... is_plugin_active_for_service(..., attachments|default({})) }}`
# as a standalone Jinja string, mirroring `models/plugins_settings.html:157` -- a file T8 deleted.
# No template uses that expression any more: `models/compose_shelf.html:228` and
# `models/request_path_strip.html:131` pass `shelf_attachments` / `rp_attachments`, deliberately
# WITHOUT a `|default` (a missing one must raise, and the host-page contract test in
# `test_compose_page_assembly.py` derives the required names from the partials themselves). The
# attachment-aware behaviour it covered is exercised through real renders by
# `test_compose_shelf.py::test_attachment_makes_a_resource_backed_plugin_read_live` and
# `::test_an_attachment_outranks_every_per_key_rung`, and at function level above (Task 7 block).
