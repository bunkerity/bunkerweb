"""Behaviour of ``src/common/core/country/country.lua``, the real file run under plain Lua.

The plugin allows or denies a client by the country its public IP resolves to. A whitelist is
exclusive (only listed countries pass), a blacklist denies the listed ones; ``@GROUP`` tokens expand
to country sets; private addresses, ignored URIs and ignored headers skip the check; the verdict is
cached for 24h per service and client. OpenResty is stubbed at its boundary
(``_lua_plugin_helpers.py``); PCRE is replaced by Lua patterns and the GeoIP lookup by ``COUNTRY``.
"""

import json

import pytest
from _lua_plugin_helpers import CORE, LUA, module_path, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("COUNTRY", CORE / "country" / "country.lua")
SERVER = "www.example.com"
IP = "203.0.113.5"
CACHE_KEY = f"plugin_country_{SERVER}{IP}"
DENIED = {"id": "country"}


def variables(**overrides):
    return {"WHITELIST_COUNTRY": "", "BLACKLIST_COUNTRY": "", "COUNTRY_IGNORE_URI": "", **overrides}


def access(vars_=None, *, country="FR", ctx=None, cache=None, setup="", phase="access"):
    ctx = {"remote_addr": IP, "ip_is_global": True, **(ctx or {})}
    body = f"""
VARIABLES = {to_lua(variables(**(vars_ or {})))}
COUNTRY = {to_lua(country)}
CACHE = {to_lua(cache or {})}
{setup}
local result = new_plugin(PLUGIN, {to_lua(ctx)}):{phase}()
emit({{
    ret = result.ret, msg = result.msg, status = result.status, data = result.data,
    metrics = METRICS, cache = CACHE, ttl = CACHE_TTL, country_calls = COUNTRY_CALLS or 0, logs = LOGS,
}})
"""
    out = {"status": None, "data": None, "ttl": None, **run_module(MODULE, body)}
    return out


def verdict(country, result):
    """The cached value as the plugin writes it (flat JSON, no spaces)."""
    return json.dumps({"country": country, "result": result}, separators=(",", ":"))


def cached(out):
    return json.loads(out["cache"][CACHE_KEY])


class TestDisabled:
    def test_nothing_configured_means_the_check_is_off(self):
        out = access()
        assert (out["ret"], out["msg"], out["status"]) == (True, "country not activated", None)
        assert out["country_calls"] == 0 and out["cache"] == {}


class TestWhitelist:
    def test_a_listed_country_passes_and_is_cached(self):
        out = access({"WHITELIST_COUNTRY": "FR DE"}, country="FR")
        assert (out["ret"], out["status"]) == (True, None)
        assert out["msg"] == f"client IP {IP} is whitelisted (country = FR)"
        assert cached(out) == {"country": "FR", "result": "ok"}
        assert out["ttl"] == 86400
        assert out["metrics"] == {}

    def test_an_unlisted_country_is_denied_counted_and_cached(self):
        out = access({"WHITELIST_COUNTRY": "FR DE"}, country="CN", setup="DENY_STATUS = 444")
        assert out["status"] == 444
        assert out["msg"] == f"client IP {IP} is not whitelisted (country = CN)"
        assert out["data"] == {**DENIED, "country": "CN"}
        assert out["metrics"] == {"failed_country": 1}
        assert cached(out) == {"country": "CN", "result": "ko"}

    def test_the_whitelist_wins_over_a_blacklist_naming_the_same_country(self):
        out = access({"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "FR"}, country="FR")
        assert (out["status"], out["msg"]) == (None, f"client IP {IP} is whitelisted (country = FR)")

    def test_when_both_are_set_the_blacklist_is_not_consulted_for_other_countries(self):
        out = access({"WHITELIST_COUNTRY": "FR", "BLACKLIST_COUNTRY": "CN"}, country="US")
        assert out["status"] == 403

    def test_country_codes_are_case_insensitive(self):
        out = access({"WHITELIST_COUNTRY": "fr de"}, country="FR")
        assert out["status"] is None


class TestBlacklist:
    def test_a_listed_country_is_denied_counted_and_cached(self):
        out = access({"BLACKLIST_COUNTRY": "CN RU"}, country="RU")
        assert out["status"] == 403
        assert out["msg"] == f"client IP {IP} is blacklisted (country = RU)"
        assert out["data"] == {**DENIED, "country": "RU"}
        assert out["metrics"] == {"failed_country": 1}
        assert cached(out) == {"country": "RU", "result": "ko"}

    def test_an_unlisted_country_passes_and_is_cached(self):
        out = access({"BLACKLIST_COUNTRY": "CN RU"}, country="FR")
        assert (out["ret"], out["status"]) == (True, None)
        assert out["msg"] == f"client IP {IP} is not blacklisted (country = FR)"
        assert cached(out) == {"country": "FR", "result": "ok"}


class TestGroups:
    @pytest.mark.parametrize(("group", "member", "outsider"), [("EU", "DE", "US"), ("BENELUX", "NL", "FR"), ("FIVE_EYES", "GB", "DE"), ("@eu", "FR", "CN")])
    def test_a_group_token_blacklists_every_member(self, group, member, outsider):
        token = group if group.startswith("@") else f"@{group}"
        assert access({"BLACKLIST_COUNTRY": token}, country=member)["status"] == 403
        assert access({"BLACKLIST_COUNTRY": token}, country=outsider)["status"] is None

    def test_a_group_whitelist_admits_only_its_members(self):
        assert access({"WHITELIST_COUNTRY": "@DACH"}, country="CH")["status"] is None
        assert access({"WHITELIST_COUNTRY": "@DACH"}, country="FR")["status"] == 403

    def test_a_group_and_a_plain_code_combine(self):
        assert access({"BLACKLIST_COUNTRY": "@BENELUX CN"}, country="CN")["status"] == 403
        assert access({"BLACKLIST_COUNTRY": "@BENELUX CN"}, country="LU")["status"] == 403

    def test_an_unknown_group_warns_and_matches_nothing(self):
        out = access({"BLACKLIST_COUNTRY": "@NOPE"}, country="FR")
        assert out["status"] is None
        assert ["WARN", "unknown country group @NOPE in country setting"] in out["logs"]


class TestSkippedClients:
    def test_a_private_address_is_not_looked_up_and_is_cached_as_unknown(self):
        out = access({"BLACKLIST_COUNTRY": "FR"}, ctx={"ip_is_global": False}, country="FR")
        assert (out["ret"], out["status"]) == (True, None)
        assert out["msg"] == f"client IP {IP} is not global, skipping check"
        assert out["country_calls"] == 0
        assert cached(out) == {"country": "unknown", "result": "ok"}

    def test_an_ignored_uri_skips_the_check_even_for_a_blacklisted_country(self):
        out = access({"BLACKLIST_COUNTRY": "FR", "COUNTRY_IGNORE_URI": "^/health"}, ctx={"uri": "/healthz"})
        assert (out["status"], out["country_calls"], out["cache"]) == (None, 0, {})
        assert out["msg"] == "URI /healthz is ignored (pattern = ^/health)"

    def test_an_ignore_pattern_also_matches_the_full_request_uri(self):
        out = access({"BLACKLIST_COUNTRY": "FR", "COUNTRY_IGNORE_URI": "debug=1"}, ctx={"uri": "/page", "request_uri": "/page?debug=1"})
        assert (out["status"], out["country_calls"]) == (None, 0)

    def test_a_non_matching_uri_is_still_checked(self):
        out = access({"BLACKLIST_COUNTRY": "FR", "COUNTRY_IGNORE_URI": "^/health"}, ctx={"uri": "/shop"})
        assert out["status"] == 403

    def test_an_ignored_header_skips_the_check_and_is_never_cached(self):
        out = access({"BLACKLIST_COUNTRY": "FR"}, setup='HEADER_MATCH = "X-Monitor"')
        assert (out["status"], out["msg"]) == (None, "header X-Monitor is ignored")
        assert (out["country_calls"], out["cache"]) == (0, {})


class TestCache:
    def test_a_cached_ok_verdict_passes_without_a_lookup(self):
        cache = {CACHE_KEY: verdict("FR", "ok")}
        out = access({"BLACKLIST_COUNTRY": "FR"}, cache=cache, country="FR")
        assert out["status"] is None
        assert out["msg"] == f"client IP {IP} is in country cache (not blacklisted, country = FR)"
        assert out["country_calls"] == 0

    def test_a_cached_ko_verdict_denies_counts_and_skips_the_lookup(self):
        cache = {CACHE_KEY: verdict("CN", "ko")}
        out = access({"BLACKLIST_COUNTRY": "CN"}, cache=cache, country="FR")
        assert out["status"] == 403
        assert out["msg"] == f"client IP {IP} is in country cache (blacklisted, country = CN)"
        assert out["data"] == {**DENIED, "country": "CN"}
        assert out["metrics"] == {"failed_country": 1}
        assert out["country_calls"] == 0

    def test_the_cache_is_per_service(self):
        cache = {f"plugin_country_other.example.com{IP}": verdict("CN", "ko")}
        assert access({"BLACKLIST_COUNTRY": "CN"}, cache=cache, country="FR")["status"] is None


class TestFailures:
    def test_a_failed_country_lookup_is_an_error_not_a_verdict(self):
        out = access({"BLACKLIST_COUNTRY": "FR"}, setup="COUNTRY = nil")
        assert out["ret"] is False
        assert out["msg"] == f"can't get country of client IP {IP} : country lookup failed"
        assert out["cache"] == {}

    @pytest.mark.parametrize(
        ("vars_", "country", "fragment"),
        [
            ({"WHITELIST_COUNTRY": "FR"}, "FR", "error while adding item to cache"),
            ({"WHITELIST_COUNTRY": "FR"}, "CN", "error while adding item to cache"),
            ({"BLACKLIST_COUNTRY": "CN"}, "CN", "error while adding item to cache"),
            ({"BLACKLIST_COUNTRY": "CN"}, "FR", "error while caching IP"),
        ],
    )
    def test_a_cache_write_failure_is_reported(self, vars_, country, fragment):
        out = access(vars_, country=country, setup='CACHE_SET_ERROR = "no memory"')
        assert out["ret"] is False
        assert out["msg"].startswith(fragment) and out["msg"].endswith("no memory")


class TestPrereadAndInit:
    def test_preread_applies_the_same_decision_as_access(self):
        assert access({"BLACKLIST_COUNTRY": "CN"}, country="CN", phase="preread")["status"] == 403

    def test_init_stores_the_ignore_header_rules(self):
        body = """
PHASE = "init"
IS_REQUEST = false
local result = new_plugin(PLUGIN, {}):init()
emit({ ret = result.ret, msg = result.msg, store = STORE, written = STORE_SET_LOG })
"""
        out = run_module(MODULE, body)
        assert (out["ret"], out["msg"]) == (True, "successfully loaded country ignore header rules")
        assert out["written"] == ["plugin_country_header_rules"]
        assert out["store"]["plugin_country_header_rules"] == {"name": "COUNTRY_IGNORE_HEADER"}

    def test_init_fails_when_the_store_rejects_the_rules(self):
        body = """
PHASE = "init"
IS_REQUEST = false
STORE_SET_ERROR = "shared dict full"
local result = new_plugin(PLUGIN, {}):init()
emit({ ret = result.ret, msg = result.msg })
"""
        assert run_module(MODULE, body) == {"ret": False, "msg": "shared dict full"}
