"""Behaviour of ``src/common/core/blacklist/blacklist.lua``, the real file run under plain Lua.

The header criterion is covered by ``test_header_rules_plugins_lua.py``; this file covers the
decisions an operator relies on: the disabled path, deny and allow for IP / network / ASN / rDNS /
URI / User-Agent, the ignore lists beating the blacklists, the 24h verdict cache, and how
``initialize()`` and ``init()`` assemble the lists. OpenResty is stubbed at its boundary
(``tests/unit/common/_lua_state_helpers.py``); PCRE is replaced by Lua patterns, which agree on
the simple expressions used here.
"""

import pytest
from _lua_state_helpers import CORE, LUA, module_path, run_plugin, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("BLACKLIST", CORE / "blacklist" / "blacklist.lua")
SERVER = "www.example.com"
KINDS = ["IP", "RDNS", "ASN", "USER_AGENT", "URI", "IGNORE_IP", "IGNORE_RDNS", "IGNORE_ASN", "IGNORE_USER_AGENT", "IGNORE_URI"]


def access(lists=None, *, variables=None, ctx=None, cache=None, setup=""):
    """Build a plugin through the real ``initialize`` with ``lists`` in the internalstore, then run ``access``."""
    full_variables = {"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}}
    full_variables.update(variables or {})
    stored = {kind: [] for kind in KINDS}
    stored.update(lists or {})
    body = f"""
VARIABLES = {to_lua(full_variables)}
STORE["plugin_blacklist_lists_{SERVER}"] = {to_lua(stored)}
CACHE = {to_lua(cache or {})}
{setup}
local plugin = new_plugin(PLUGIN, {to_lua(ctx or {})})
local result = plugin:access()
local out = summary(result)
out.metrics, out.cache, out.asn_calls, out.rdns_calls = METRICS, CACHE, ASN_CALLS or 0, RDNS_CALLS or 0
emit(out)
"""
    return {"status": None, "data": None, **run_plugin(MODULE, body)}


class TestDisabledPath:
    def test_access_is_skipped_when_the_service_does_not_use_the_blacklist(self):
        out = access({"IP": ["1.2.3.4"]}, variables={"USE_BLACKLIST": "no"})
        assert out["ret"] is True
        assert out["msg"] == "access not needed"
        assert out["status"] is None

    def test_access_is_skipped_while_loading(self):
        out = access({"IP": ["1.2.3.4"]}, setup="IS_LOADING = true")
        assert (out["msg"], out["status"]) == ("access not needed", None)


class TestIpDecisions:
    def test_a_listed_ip_is_denied_with_the_deny_status_and_counted(self):
        out = access({"IP": ["1.2.3.4"]}, setup="DENY_STATUS = 444")
        assert out["status"] == 444
        assert out["msg"] == "IP is blacklisted (info : ip)"
        assert out["data"] == {"id": "ip"}
        assert out["metrics"] == {"failed_ip": 1}

    def test_a_network_entry_covers_every_address_in_it(self):
        out = access({"IP": ["1.2.3.0/24"]}, ctx={"remote_addr": "1.2.3.77"})
        assert out["status"] == 403
        assert out["data"] == {"id": "ip"}

    def test_an_address_outside_the_network_is_allowed(self):
        out = access({"IP": ["1.2.3.0/24"]}, ctx={"remote_addr": "1.2.4.1"})
        assert (out["ret"], out["msg"], out["status"]) == (True, "not blacklisted", None)
        assert out["metrics"] == {}

    def test_the_ignore_list_beats_the_blacklist(self):
        out = access({"IP": ["1.2.3.0/24"], "IGNORE_IP": ["1.2.3.4"]})
        assert (out["msg"], out["status"]) == ("not blacklisted", None)
        # the exemption is cached as a clean verdict, so the lists are not walked again for 24h
        assert out["cache"]["plugin_blacklist_www.example.comip1.2.3.4"] == "ok"

    def test_entries_from_the_service_variable_are_merged_with_the_stored_lists(self):
        # BLACKLIST_IP is read at request time next to the lists init() stored from the cache files
        for client in ("1.2.3.4", "9.9.9.9", "8.8.8.8"):
            out = access({"IP": ["1.2.3.4"]}, variables={"BLACKLIST_IP": "9.9.9.9 8.8.8.8"}, ctx={"remote_addr": client})
            assert out["status"] == 403, client

    def test_a_missing_stored_list_still_enforces_the_variable_and_logs_the_error(self):
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}, "BLACKLIST_IP": "1.2.3.4"})}
local plugin = new_plugin(PLUGIN)
local result = plugin:access()
local errors = {{}}
for _, entry in ipairs(LOGS) do if entry[1] == "ERR" then errors[#errors + 1] = entry[2] end end
emit({{ status = result.status, errors = errors }})
"""
        out = run_plugin(MODULE, body)
        assert out["status"] == 403
        assert out["errors"] == [f"no such key plugin_blacklist_lists_{SERVER}"]

    def test_initialize_does_not_modify_the_shared_stored_list(self):
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}, "BLACKLIST_IP": "9.9.9.9"})}
local stored = {{ IP = {{ "1.2.3.4" }} }}
STORE["plugin_blacklist_lists_{SERVER}"] = stored
new_plugin(PLUGIN)
emit({{ stored = stored.IP }})
"""
        assert run_plugin(MODULE, body)["stored"] == ["1.2.3.4"]


class TestCachedVerdicts:
    def test_a_cached_deny_is_honoured_without_walking_the_lists(self):
        out = access({}, cache={f"plugin_blacklist_{SERVER}ip1.2.3.4": "ip"})
        assert out["status"] == 403
        assert out["msg"] == "IP is in cached blacklist (info : ip)"
        assert out["metrics"] == {"failed_ip": 1}

    def test_a_cached_clean_verdict_skips_the_list_check(self):
        # the stored list says deny, the cache says ok: the cache is what the 24h shortcut relies on
        out = access({"IP": ["1.2.3.4"]}, cache={f"plugin_blacklist_{SERVER}ip1.2.3.4": "ok"})
        assert (out["msg"], out["status"]) == ("not blacklisted", None)

    def test_a_fresh_verdict_is_cached_for_a_day(self):
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}})}
STORE["plugin_blacklist_lists_{SERVER}"] = {{ IP = {{ "1.2.3.4" }} }}
new_plugin(PLUGIN):access()
emit({{ cached = CACHE["plugin_blacklist_{SERVER}ip1.2.3.4"], ttl = CACHE_TTL }})
"""
        assert run_plugin(MODULE, body) == {"cached": "ip", "ttl": 86400}


class TestUriAndUserAgent:
    def test_a_matching_uri_is_denied_and_named_in_the_data(self):
        out = access({"URI": ["^/admin"]}, ctx={"uri": "/admin/users"})
        assert out["status"] == 403
        assert out["data"] == {"id": "uri", "uri": "^/admin"}
        assert out["metrics"] == {"failed_uri": 1}

    def test_an_ignored_uri_is_allowed_even_when_it_matches_the_blacklist(self):
        out = access({"URI": ["^/admin"], "IGNORE_URI": ["^/admin/public"]}, ctx={"uri": "/admin/public/logo.png"})
        assert (out["msg"], out["status"]) == ("not blacklisted", None)

    def test_an_unlisted_uri_is_allowed(self):
        out = access({"URI": ["^/admin"]}, ctx={"uri": "/index.html"})
        assert out["status"] is None

    def test_a_matching_user_agent_is_denied(self):
        out = access({"USER_AGENT": ["BadBot"]}, ctx={"http_user_agent": "Mozilla BadBot/1.0"})
        assert out["status"] == 403
        assert out["data"] == {"id": "ua", "ua": "BadBot"}
        assert out["metrics"] == {"failed_ua": 1}

    def test_an_ignored_user_agent_is_allowed(self):
        out = access(
            {"USER_AGENT": ["Bot"], "IGNORE_USER_AGENT": ["GoodBot"]},
            ctx={"http_user_agent": "GoodBot/2"},
        )
        assert out["status"] is None

    def test_a_request_without_user_agent_is_not_matched_against_the_user_agent_list(self):
        out = access({"USER_AGENT": [".*"]}, ctx={"http_user_agent": None, "uri": "/"})
        assert out["status"] is None


class TestAsn:
    def test_a_listed_asn_is_denied_for_a_global_client(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = 64496")
        assert out["status"] == 403
        assert out["data"] == {"id": "asn", "asn": "64496"}

    def test_an_ignored_asn_is_allowed(self):
        out = access({"ASN": ["64496"], "IGNORE_ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = 64496")
        assert out["status"] is None

    def test_a_non_global_client_is_never_looked_up(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": False}, setup="ASN = 64496")
        assert (out["status"], out["asn_calls"]) == (None, 0)

    def test_a_failed_asn_lookup_does_not_deny(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = nil")
        assert (out["ret"], out["status"]) == (True, None)


class TestRdns:
    def test_a_listed_rdns_suffix_is_denied(self):
        out = access({"RDNS": [".evil.example"]}, setup='RDNS = { "scan1.evil.example" }')
        assert out["status"] == 403
        assert out["data"] == {"id": "rdns", "rdns": ".evil.example"}

    def test_a_forward_confirmed_ignore_suffix_rescues_the_client(self):
        out = access(
            {"RDNS": [".example"], "IGNORE_RDNS": [".good.example"]},
            setup='RDNS = { "crawler.good.example" }; FCRDNS = true',
        )
        assert out["status"] is None

    def test_an_unconfirmed_ignore_suffix_does_not_rescue_the_client(self):
        # a spoofed PTR record must not buy an exemption: the ignore only counts once forward-confirmed
        out = access(
            {"RDNS": [".example"], "IGNORE_RDNS": [".good.example"]},
            setup='RDNS = { "crawler.good.example" }; FCRDNS = false',
        )
        assert out["status"] == 403

    def test_the_global_only_switch_skips_the_lookup_for_a_private_client(self):
        out = access(
            {"RDNS": [".evil.example"]},
            variables={"BLACKLIST_RDNS_GLOBAL": "yes"},
            ctx={"ip_is_global": False},
            setup='RDNS = { "scan1.evil.example" }',
        )
        assert (out["status"], out["rdns_calls"]) == (None, 0)

    def test_a_failed_rdns_lookup_does_not_deny_and_is_logged(self):
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}})}
STORE["plugin_blacklist_lists_{SERVER}"] = {{ RDNS = {{ ".evil.example" }} }}
RDNS = nil
local result = new_plugin(PLUGIN):access()
local errors = {{}}
for _, entry in ipairs(LOGS) do if entry[1] == "ERR" then errors[#errors + 1] = entry[2] end end
emit({{ status = result.status, errors = errors }})
"""
        out = run_plugin(MODULE, body)
        assert out.get("status") is None
        assert out["errors"] == ["error while getting rdns : rdns lookup failed"]


class TestStream:
    def test_preread_applies_the_same_decision_as_access(self):
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes", "BLACKLIST_RDNS_GLOBAL": "no", **{f"BLACKLIST_{k}": "" for k in KINDS}})}
STORE["plugin_blacklist_lists_{SERVER}"] = {{ IP = {{ "1.2.3.4" }} }}
emit(summary(new_plugin(PLUGIN):preread()))
"""
        out = run_plugin(MODULE, body)
        assert (out["status"], out["data"]) == (403, {"id": "ip"})


class TestInit:
    def _init(self, tmp_path, *, server_name: str | None = SERVER, files=None, setup=""):
        for name, lines in (files or {}).items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        body = f"""
VARIABLES = {to_lua({"USE_BLACKLIST": "yes"})}
PHASE = "init"
IS_REQUEST = false
SERVER_NAME = {to_lua(server_name)}
{setup}
local result = new_plugin(PLUGIN):init()
emit({{ ret = result.ret, msg = result.msg, store = STORE }})
"""
        return run_plugin(MODULE, body, fs_root=tmp_path)

    def test_init_loads_each_service_cache_files_into_its_own_internalstore_key(self, tmp_path):
        out = self._init(
            tmp_path,
            server_name="a.example b.example",
            files={
                "blacklist/a.example/IP.list": ["1.1.1.1", "", "1.1.1.1", "2.2.2.2"],
                "blacklist/a.example/IGNORE_URI.list": ["^/health"],
                "blacklist/b.example/USER_AGENT.list": ["EvilBot"],
            },
        )
        assert out["ret"] is True
        a, b = out["store"]["plugin_blacklist_lists_a.example"], out["store"]["plugin_blacklist_lists_b.example"]
        # blank lines are skipped and duplicates removed, and a service never sees another one's entries
        assert a["IP"] == ["1.1.1.1", "2.2.2.2"]
        assert a["IGNORE_URI"] == ["^/health"]
        assert not a["USER_AGENT"]
        assert b["USER_AGENT"] == ["EvilBot"]
        assert not b["IP"]

    def test_init_publishes_the_header_rule_sets(self, tmp_path):
        out = self._init(tmp_path)
        assert out["store"]["plugin_blacklist_header_rules"] == {"name": "BLACKLIST_HEADER"}
        assert out["store"]["plugin_blacklist_ignore_header_rules"] == {"name": "BLACKLIST_IGNORE_HEADER"}

    def test_init_is_skipped_when_no_service_uses_the_blacklist(self, tmp_path):
        out = self._init(tmp_path, setup="HAS_VARIABLE = false")
        assert (out["ret"], out["msg"], out["store"]) == (True, "init not needed", {})

    def test_init_fails_when_server_name_cannot_be_read(self, tmp_path):
        out = self._init(tmp_path, server_name=None)
        assert out["ret"] is False
        assert out["msg"] == "can't get SERVER_NAME variable : no such variable"

    def test_init_reports_an_internalstore_write_failure(self, tmp_path):
        out = self._init(tmp_path, setup='STORE_SET_ERROR = "no memory"')
        assert out["ret"] is False
        assert out["msg"] == f"can't store blacklist {SERVER} list into internalstore : no memory"
