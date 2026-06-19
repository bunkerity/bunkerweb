"""Pure-logic tests for resource-group value validation and @name expansion.

No database — exercises src/common/utils/resource_validation.py and
src/common/utils/resource_group_resolver.py directly.
"""

from resource_group_resolver import (  # type: ignore
    expand_config_groups,
    expand_resource_group_refs,
    kind_for_key,
    value_for_validation,
)
from resource_validation import validate_resource_value  # type: ignore


# A group index as produced by build_group_index(): {name: {kind: [values]}}
INDEX = {
    "office": {"ip": ["203.0.113.5", "198.51.100.0/24"], "country": ["FR"], "asn": ["32934"]},
    "cdn": {"ip": ["192.0.2.0/24"]},
}


class TestValidateResourceValue:
    def test_ip(self):
        assert validate_resource_value("ip", "203.0.113.5") == (True, "203.0.113.5")
        assert validate_resource_value("ip", "198.51.100.0/24") == (True, "198.51.100.0/24")
        assert validate_resource_value("ip", "nope")[0] is False

    def test_country_uppercased(self):
        assert validate_resource_value("country", "fr") == (True, "FR")
        assert validate_resource_value("country", "FRA")[0] is False

    def test_asn_strips_prefix(self):
        assert validate_resource_value("asn", "AS32934") == (True, "32934")
        assert validate_resource_value("asn", "32934") == (True, "32934")
        assert validate_resource_value("asn", "abc")[0] is False

    def test_rdns_lowercased(self):
        assert validate_resource_value("rdns", ".GoogleBot.com") == (True, ".googlebot.com")
        assert validate_resource_value("rdns", "has space")[0] is False

    def test_user_agent_and_uri_free_form(self):
        assert validate_resource_value("user_agent", "(?i)bad") == (True, "(?i)bad")
        assert validate_resource_value("uri", "^/admin") == (True, "^/admin")

    def test_unknown_kind(self):
        assert validate_resource_value("port", "80")[0] is False

    def test_empty_rejected(self):
        assert validate_resource_value("ip", "   ")[0] is False


class TestKindForKey:
    def test_exact_and_multisite(self):
        assert kind_for_key("WHITELIST_IP") == "ip"
        assert kind_for_key("www.example.com_WHITELIST_IP") == "ip"
        assert kind_for_key("BLACKLIST_COUNTRY") == "country"

    def test_ignore_variant_distinct_from_base(self):
        assert kind_for_key("BLACKLIST_IGNORE_IP") == "ip"
        assert kind_for_key("svc_BLACKLIST_IGNORE_ASN") == "asn"

    def test_urls_variant_not_matched(self):
        assert kind_for_key("WHITELIST_IP_URLS") is None

    def test_non_list_setting(self):
        assert kind_for_key("USE_WHITELIST") is None


class TestExpandResourceGroupRefs:
    def test_expands_known_group_by_kind(self):
        out = expand_resource_group_refs({"WHITELIST_IP": "@office 1.2.3.4"}, INDEX)
        # only the ip entries of @office, then the literal, deduped & order-preserving
        assert out["WHITELIST_IP"] == "203.0.113.5 198.51.100.0/24 1.2.3.4"

    def test_kind_filtering_in_mixed_group(self):
        # @office has ip + country + asn; in a COUNTRY setting only its country entries apply
        out = expand_resource_group_refs({"WHITELIST_COUNTRY": "@office DE"}, INDEX)
        assert out["WHITELIST_COUNTRY"] == "FR DE"

    def test_unknown_token_kept_literal(self):
        # @EU is not a resource group (built-in country group expanded later in Lua) -> kept as-is
        out = expand_resource_group_refs({"BLACKLIST_COUNTRY": "@EU FR"}, INDEX)
        assert out["BLACKLIST_COUNTRY"] == "@EU FR"

    def test_multisite_prefixed_key(self):
        out = expand_resource_group_refs({"app.example.com_WHITELIST_IP": "@cdn"}, INDEX)
        assert out["app.example.com_WHITELIST_IP"] == "192.0.2.0/24"

    def test_non_list_setting_untouched(self):
        out = expand_resource_group_refs({"SERVER_NAME": "@office"}, INDEX)
        assert out["SERVER_NAME"] == "@office"

    def test_value_without_at_is_fast_path(self):
        cfg = {"WHITELIST_IP": "1.2.3.4 5.6.7.8"}
        assert expand_resource_group_refs(cfg, INDEX)["WHITELIST_IP"] == "1.2.3.4 5.6.7.8"

    def test_empty_index_returns_config(self):
        cfg = {"WHITELIST_IP": "@office"}
        assert expand_resource_group_refs(cfg, {}) is cfg

    def test_dedupes_across_group_and_literal(self):
        out = expand_resource_group_refs({"WHITELIST_IP": "@cdn 192.0.2.0/24"}, INDEX)
        assert out["WHITELIST_IP"] == "192.0.2.0/24"


class TestExpandConfigGroups:
    def test_fail_open_on_db_error(self):
        class BadDB:
            def get_resource_groups(self):
                raise RuntimeError("db down")

        cfg = {"WHITELIST_IP": "@office"}
        # never raises; returns config unchanged
        assert expand_config_groups(cfg, BadDB()) == cfg

    def test_none_db_returns_config(self):
        cfg = {"WHITELIST_IP": "@office"}
        assert expand_config_groups(cfg, None) is cfg

    def test_end_to_end_with_fake_db(self):
        class FakeDB:
            def get_resource_groups(self):
                return {
                    "office": {
                        "name": "office",
                        "entries": [
                            {"kind": "ip", "value": "203.0.113.5"},
                            {"kind": "country", "value": "FR"},
                        ],
                    }
                }

        out = expand_config_groups({"WHITELIST_IP": "@office 1.1.1.1"}, FakeDB())
        assert out["WHITELIST_IP"] == "203.0.113.5 1.1.1.1"


class TestValueForValidation:
    def test_strips_tokens_for_list_setting(self):
        assert value_for_validation("WHITELIST_IP", "@office 1.2.3.4") == " 1.2.3.4"
        assert value_for_validation("WHITELIST_IP", "@office") == ""

    def test_untouched_for_non_list_setting(self):
        assert value_for_validation("SERVER_NAME", "@office") == "@office"
