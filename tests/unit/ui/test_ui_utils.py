"""ui/app/utils.py — pure helpers: bcrypt password handling, settings/multisite
expansion, and the CWE-601 / CWE-1236 security guards.

Imported via the ``app`` package (``src/ui`` on path, added by the ui conftest). Every
function here is a pure function of its arguments (or of module-level constants) — no DB,
no running Flask app — so these tests run instantly without any fixture.
"""

import io

import pytest

from app.utils import (  # type: ignore
    ALWAYS_USED_PLUGINS,
    _csv_escape,
    _sanitize_internal_next,
    bcrypt_cost,
    can_delete_service,
    check_password,
    csv_safe,
    csv_writer,
    gen_password_hash,
    get_blacklisted_settings,
    get_filtered_settings,
    get_multiples,
    is_bcrypt_hash,
    is_editable_method,
    is_plugin_active,
    is_ui_api_method,
    password_exceeds_bcrypt_limit,
)


class TestPasswordHashing:
    def test_hash_and_check_roundtrip(self):
        h = gen_password_hash("S3cret!")
        assert isinstance(h, bytes)
        assert check_password("S3cret!", h) is True
        assert check_password("wrong", h) is False

    def test_is_bcrypt_hash(self):
        h = gen_password_hash("x").decode("utf-8")
        assert is_bcrypt_hash(h) is True
        assert is_bcrypt_hash("not-a-hash") is False
        assert is_bcrypt_hash("plaintext-password") is False

    def test_bcrypt_cost_is_13(self):
        h = gen_password_hash("x").decode("utf-8")
        assert bcrypt_cost(h) == 13  # gensalt(rounds=13)

    def test_password_exceeds_limit(self):
        assert password_exceeds_bcrypt_limit("a" * 72) is False
        assert password_exceeds_bcrypt_limit("a" * 73) is True

    def test_72_byte_truncation_symmetry(self):
        # >72 bytes is truncated to 72 for both hashing and verification, so two passwords
        # sharing their first 72 bytes verify against each other's hash (documented contract).
        base = "a" * 72
        h = gen_password_hash(base + "EXTRA")
        assert check_password(base + "DIFFERENT", h) is True


class TestMethodPredicates:
    def test_is_editable_method_default(self):
        assert is_editable_method("default") is False
        assert is_editable_method("default", allow_default=True) is True

    def test_is_ui_api_method(self):
        assert is_ui_api_method("ui") is True
        assert is_ui_api_method("definitely_not_a_method") is False

    def test_can_delete_service(self):
        assert can_delete_service({"method": "ui"}) is True
        assert can_delete_service({"method": "autoconf", "is_draft": True}) is True
        assert can_delete_service({"method": "autoconf", "is_draft": False}) is False


class TestGetMultiples:
    """`get_multiples` expands numbered multisite settings (REVERSE_PROXY_URL_1, …)
    into per-suffix groups. Pure dict-in/dict-out — the bug-prone bits are suffix
    grouping, numeric ordering, and padding a group with the base ("0") defaults."""

    SETTINGS = {
        "REVERSE_PROXY_URL": {"multiple": "reverse-proxy", "default": "", "context": "multisite"},
        "REVERSE_PROXY_HOST": {"multiple": "reverse-proxy", "default": "", "context": "multisite"},
        # no "multiple" key -> must never be grouped, even if a suffixed value exists
        "USE_REVERSE_PROXY": {"default": "no", "context": "multisite"},
    }

    def test_groups_and_suffix_ordering(self):
        config = {
            "REVERSE_PROXY_URL_2": "/api",
            "REVERSE_PROXY_URL_1": "/app",  # deliberately out of order in the dict
            "REVERSE_PROXY_HOST_1": "http://a",
        }
        out = get_multiples(self.SETTINGS, config)
        assert set(out) == {"reverse-proxy"}
        # base "0" plus the suffixes seen in config, sorted numerically (not insertion order)
        assert list(out["reverse-proxy"]) == ["0", "1", "2"]

    def test_base_group_holds_every_member_without_suffix(self):
        out = get_multiples(self.SETTINGS, {})
        group = out["reverse-proxy"]
        assert list(group) == ["0"]
        assert set(group["0"]) == {"REVERSE_PROXY_URL", "REVERSE_PROXY_HOST"}

    def test_suffix_value_carried_from_config(self):
        out = get_multiples(self.SETTINGS, {"REVERSE_PROXY_URL_1": "/app"})
        assert out["reverse-proxy"]["1"]["REVERSE_PROXY_URL_1"]["value"] == "/app"

    def test_missing_member_in_suffix_group_is_padded_in_base_order(self):
        # suffix 1 sets only URL; HOST must still appear, after URL (base order preserved)
        out = get_multiples(self.SETTINGS, {"REVERSE_PROXY_URL_1": "/app"})
        assert list(out["reverse-proxy"]["1"]) == ["REVERSE_PROXY_URL_1", "REVERSE_PROXY_HOST_1"]

    def test_non_multiple_setting_never_grouped(self):
        out = get_multiples(self.SETTINGS, {"USE_REVERSE_PROXY_1": "yes"})
        assert all("USE_REVERSE_PROXY_1" not in members for group in out.values() for members in group.values())


class TestSettingsFilters:
    SETTINGS = {
        "LOG_LEVEL": {"context": "global"},
        "USE_ANTIBOT": {"context": "multisite"},
    }

    def test_multisite_drops_global_context(self):
        assert set(get_filtered_settings(self.SETTINGS, global_config=False)) == {"USE_ANTIBOT"}

    def test_global_config_keeps_everything(self):
        assert set(get_filtered_settings(self.SETTINGS, global_config=True)) == {"LOG_LEVEL", "USE_ANTIBOT"}

    def test_blacklist_is_a_set_with_core_members(self):
        bl = get_blacklisted_settings()
        assert isinstance(bl, set)
        assert {"DATABASE_URI", "IS_LOADING", "BUNKERWEB_INSTANCES"} <= bl

    def test_blacklist_global_adds_server_name_and_template(self):
        assert "SERVER_NAME" not in get_blacklisted_settings(global_config=False)
        assert {"SERVER_NAME", "USE_TEMPLATE"} <= get_blacklisted_settings(global_config=True)


class TestPluginActive:
    def test_always_used_plugin_is_active_regardless_of_config(self):
        # membership in ALWAYS_USED_PLUGINS short-circuits before any config lookup
        pid = ALWAYS_USED_PLUGINS[0]
        assert is_plugin_active(pid, pid.capitalize(), {}) is True

    def test_use_flag_set_activates(self):
        assert is_plugin_active("antibot", "Antibot", {"USE_ANTIBOT": {"value": "captcha"}}) is True

    def test_unused_plugin_defaults_to_inactive(self):
        assert is_plugin_active("antibot", "Antibot", {}) is False

    def test_plugins_specifics_off_default_is_inactive(self):
        # LETSENCRYPT counts as active only once AUTO_LETS_ENCRYPT differs from its "no" default
        assert is_plugin_active("letsencrypt", "Let's Encrypt", {}) is False
        assert is_plugin_active("letsencrypt", "Let's Encrypt", {"AUTO_LETS_ENCRYPT": {"value": "yes"}}) is True


class TestSanitizeInternalNext:
    """`_sanitize_internal_next` is the open-redirect guard (CWE-601): only same-origin
    absolute paths pass; anything that could redirect off-site must raise ValueError."""

    def test_valid_internal_path_passthrough(self):
        assert _sanitize_internal_next("/home", "/default") == "/home"

    def test_none_returns_default(self):
        assert _sanitize_internal_next(None, "/default") == "/default"

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            _sanitize_internal_next(123, "/default")

    @pytest.mark.parametrize(
        "bad",
        [
            "home",  # no leading slash
            "//evil.com",  # protocol-relative
            "/x://y",  # embedded scheme
            "/" + "a" * 5000,  # exceeds the 4096 length bound
            "/x\x01y",  # control character
            "/%2f%2fevil.com",  # percent-encoded -> decodes to a protocol-relative "//"
        ],
    )
    def test_rejects_unsafe(self, bad):
        with pytest.raises(ValueError):
            _sanitize_internal_next(bad, "/default")


class TestCsvInjection:
    """`_csv_escape` / `csv_safe` / `csv_writer` neutralize spreadsheet formula
    injection (CWE-1236): formula leaders (@ + - = | %) via defusedcsv, plus the
    tab/CR leaders defusedcsv omits."""

    def test_formula_leader_is_neutralized(self):
        out = _csv_escape("=1+1")
        assert isinstance(out, str)
        assert not out.startswith("=")

    @pytest.mark.parametrize("leader", ["\t", "\r"])
    def test_tab_and_cr_leaders_get_quote_prefix(self, leader):
        # defusedcsv ignores \t and \r; the wrapper adds the leading quote itself
        assert _csv_escape(leader + "cmd") == "'" + leader + "cmd"

    def test_safe_value_unchanged(self):
        assert _csv_escape("safe") == "safe"

    def test_non_string_passes_through(self):
        assert _csv_escape(123) == 123

    def test_csv_safe_matches_escape(self):
        assert csv_safe("=evil") == _csv_escape("=evil")

    @pytest.mark.parametrize("payload", ["=1+1", "\tcmd", "\rcmd", "safe"])
    def test_escape_is_idempotent(self, payload):
        once = _csv_escape(payload)
        assert _csv_escape(once) == once

    def test_writer_neutralizes_formula_cell(self):
        buf = io.StringIO()
        csv_writer(buf).writerow(["=evil", "ok"])
        out = buf.getvalue()
        assert not out.startswith("=")  # bare formula leader never reaches the file
        assert "evil" in out and "ok" in out  # data preserved
