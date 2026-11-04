"""Behaviour of ``src/common/core/greylist/greylist.lua``, the real file run under plain Lua.

The greylist inverts the blacklist: only a client that matches a listed IP / network / ASN / rDNS /
URI / User-Agent passes, everything else is denied. The header criterion lives in
``test_header_rules_plugins_lua.py``; this file covers the list decisions, the 24h verdict cache and
the way ``initialize()`` and ``init()`` assemble the lists. OpenResty is stubbed at its boundary
(``tests/unit/common/_lua_state_helpers.py``); PCRE is replaced by Lua patterns.
"""

import pytest
from _lua_state_helpers import CORE, LUA, module_path, run_plugin, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("GREYLIST", CORE / "greylist" / "greylist.lua")
SERVER = "www.example.com"
KINDS = ["IP", "RDNS", "ASN", "USER_AGENT", "URI"]


def variables(**overrides):
    return {"USE_GREYLIST": "yes", "GREYLIST_RDNS_GLOBAL": "no", **{f"GREYLIST_{k}": "" for k in KINDS}, **overrides}


def access(lists=None, *, extra_variables=None, ctx=None, cache=None, setup=""):
    """Build a plugin through the real ``initialize`` with ``lists`` in the internalstore, then run ``access``."""
    stored = {kind: [] for kind in KINDS}
    stored.update(lists or {})
    body = f"""
VARIABLES = {to_lua(variables(**(extra_variables or {})))}
STORE["plugin_greylist_lists_{SERVER}"] = {to_lua(stored)}
CACHE = {to_lua(cache or {})}
{setup}
local result = new_plugin(PLUGIN, {to_lua(ctx or {})}):access()
local out = summary(result)
out.metrics, out.cache, out.asn_calls, out.rdns_calls = METRICS, CACHE, ASN_CALLS or 0, RDNS_CALLS or 0
emit(out)
"""
    return {"status": None, "data": None, **run_plugin(MODULE, body)}


class TestDisabledPath:
    def test_access_is_skipped_when_the_service_does_not_use_the_greylist(self):
        out = access({}, extra_variables={"USE_GREYLIST": "no"})
        assert (out["ret"], out["msg"], out["status"]) == (True, "access not needed", None)

    def test_access_is_skipped_while_loading(self):
        out = access({}, setup="IS_LOADING = true")
        assert (out["msg"], out["status"]) == ("access not needed", None)


class TestOnlyListedClientsPass:
    def test_an_unlisted_client_is_denied_with_the_deny_status_and_counted(self):
        out = access({"IP": ["9.9.9.9"]}, setup="DENY_STATUS = 444")
        assert out["status"] == 444
        assert out["msg"] == "not in greylist"
        assert out["metrics"] == {"failed_greylist": 1}

    def test_a_listed_ip_passes(self):
        out = access({"IP": ["1.2.3.4"]})
        assert (out["ret"], out["msg"], out["status"]) == (True, "IP is in greylist", None)
        assert out["metrics"] == {}

    def test_a_network_entry_passes_every_address_in_it(self):
        out = access({"IP": ["1.2.3.0/24"]}, ctx={"remote_addr": "1.2.3.200"})
        assert (out["msg"], out["status"]) == ("IP is in greylist", None)

    def test_an_address_outside_the_network_is_denied(self):
        out = access({"IP": ["1.2.3.0/24"]}, ctx={"remote_addr": "1.2.4.1"})
        assert out["status"] == 403

    def test_an_empty_greylist_denies_everybody(self):
        out = access({})
        assert (out["msg"], out["status"]) == ("not in greylist", 403)

    def test_a_matching_uri_passes_even_when_the_ip_is_not_listed(self):
        out = access({"URI": ["^/status"]}, ctx={"uri": "/status/ping"})
        assert (out["msg"], out["status"]) == ("URI is in greylist", None)

    def test_a_matching_user_agent_passes(self):
        out = access({"USER_AGENT": ["Monitor"]}, ctx={"http_user_agent": "UptimeMonitor/1"})
        assert (out["msg"], out["status"]) == ("UA is in greylist", None)

    def test_a_non_matching_uri_and_user_agent_are_denied(self):
        out = access({"URI": ["^/status"], "USER_AGENT": ["Monitor"]}, ctx={"uri": "/", "http_user_agent": "curl"})
        assert out["status"] == 403

    def test_entries_from_the_service_variable_are_merged_with_the_stored_lists(self):
        for client in ("1.2.3.4", "9.9.9.9"):
            out = access({"IP": ["1.2.3.4"]}, extra_variables={"GREYLIST_IP": "9.9.9.9"}, ctx={"remote_addr": client})
            assert out["status"] is None, client

    def test_a_missing_stored_list_still_enforces_the_variable_and_logs_the_error(self):
        body = f"""
VARIABLES = {to_lua(variables(GREYLIST_IP="1.2.3.4"))}
local plugin = new_plugin(PLUGIN)
local result = plugin:access()
local errors = {{}}
for _, entry in ipairs(LOGS) do if entry[1] == "ERR" then errors[#errors + 1] = entry[2] end end
emit({{ msg = result.msg, errors = errors }})
"""
        out = run_plugin(MODULE, body)
        assert out["msg"] == "IP is in greylist"
        assert out["errors"] == [f"no such key plugin_greylist_lists_{SERVER}"]


class TestCachedVerdicts:
    def test_a_cached_pass_is_honoured_without_walking_the_lists(self):
        out = access({}, cache={f"plugin_greylist_{SERVER}ip1.2.3.4": "ip"})
        assert (out["msg"], out["status"]) == ("IP is in cached greylist (info : ip)", None)

    def test_a_cached_miss_is_not_re_evaluated(self):
        # the stored list would pass this client, the cache says "ko": the 24h shortcut wins
        out = access({"IP": ["1.2.3.4"]}, cache={f"plugin_greylist_{SERVER}ip1.2.3.4": "ko"})
        assert (out["msg"], out["status"]) == ("not in greylist", 403)

    def test_a_fresh_verdict_is_cached_for_a_day(self):
        body = f"""
VARIABLES = {to_lua(variables())}
STORE["plugin_greylist_lists_{SERVER}"] = {{ IP = {{ "1.2.3.4" }} }}
new_plugin(PLUGIN):access()
emit({{ cached = CACHE["plugin_greylist_{SERVER}ip1.2.3.4"], ttl = CACHE_TTL }})
"""
        assert run_plugin(MODULE, body) == {"cached": "ip", "ttl": 86400}


class TestAsn:
    def test_a_listed_asn_passes_for_a_global_client(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = 64496")
        assert (out["msg"], out["status"]) == ("IP is in greylist", None)

    def test_an_unlisted_asn_is_denied(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = 64511")
        assert out["status"] == 403

    def test_a_non_global_client_is_never_looked_up(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": False}, setup="ASN = 64496")
        assert (out["status"], out["asn_calls"]) == (403, 0)

    def test_a_failed_asn_lookup_does_not_grant_access(self):
        out = access({"ASN": ["64496"]}, ctx={"ip_is_global": True}, setup="ASN = nil")
        assert out["status"] == 403


class TestRdns:
    def test_a_forward_confirmed_listed_suffix_passes(self):
        out = access({"RDNS": [".good.example"]}, setup='RDNS = { "crawler.good.example" }; FCRDNS = true')
        assert (out["msg"], out["status"]) == ("IP is in greylist", None)

    def test_an_unconfirmed_suffix_is_denied(self):
        # a spoofed PTR record must not grant access: the suffix only counts once forward-confirmed
        out = access({"RDNS": [".good.example"]}, setup='RDNS = { "crawler.good.example" }; FCRDNS = false')
        assert out["status"] == 403

    def test_the_global_only_switch_skips_the_lookup_for_a_private_client(self):
        out = access(
            {"RDNS": [".good.example"]},
            extra_variables={"GREYLIST_RDNS_GLOBAL": "yes"},
            ctx={"ip_is_global": False},
            setup='RDNS = { "crawler.good.example" }; FCRDNS = true',
        )
        assert (out["status"], out["rdns_calls"]) == (403, 0)

    def test_a_failed_rdns_lookup_is_logged_and_does_not_grant_access(self):
        body = f"""
VARIABLES = {to_lua(variables())}
STORE["plugin_greylist_lists_{SERVER}"] = {{ RDNS = {{ ".good.example" }} }}
RDNS = nil
local result = new_plugin(PLUGIN):access()
local errors = {{}}
for _, entry in ipairs(LOGS) do if entry[1] == "ERR" then errors[#errors + 1] = entry[2] end end
emit({{ status = result.status, errors = errors }})
"""
        out = run_plugin(MODULE, body)
        assert out["status"] == 403
        assert out["errors"] == ["error while getting rdns : rdns lookup failed"]


class TestStream:
    def test_preread_applies_the_same_decision_as_access(self):
        body = f"""
VARIABLES = {to_lua(variables())}
STORE["plugin_greylist_lists_{SERVER}"] = {{ IP = {{ "9.9.9.9" }} }}
emit(summary(new_plugin(PLUGIN):preread()))
"""
        assert run_plugin(MODULE, body)["status"] == 403


class TestInit:
    def _init(self, tmp_path, *, server_name: str | None = SERVER, files=None, setup=""):
        for name, lines in (files or {}).items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        body = f"""
VARIABLES = {to_lua({"USE_GREYLIST": "yes"})}
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
                "greylist/a.example/IP.list": ["1.1.1.1", "", "1.1.1.1", "2.2.2.2"],
                "greylist/b.example/URI.list": ["^/status"],
            },
        )
        assert out["ret"] is True
        a, b = out["store"]["plugin_greylist_lists_a.example"], out["store"]["plugin_greylist_lists_b.example"]
        assert a["IP"] == ["1.1.1.1", "2.2.2.2"]
        assert not a["URI"]
        assert b["URI"] == ["^/status"]
        assert not b["IP"]

    def test_init_publishes_the_header_rule_set(self, tmp_path):
        out = self._init(tmp_path)
        assert out["store"]["plugin_greylist_header_rules"] == {"name": "GREYLIST_HEADER"}

    def test_init_is_skipped_when_no_service_uses_the_greylist(self, tmp_path):
        out = self._init(tmp_path, setup="HAS_VARIABLE = false")
        assert (out["ret"], out["msg"], out["store"]) == (True, "init not needed", {})

    def test_init_fails_when_server_name_cannot_be_read(self, tmp_path):
        out = self._init(tmp_path, server_name=None)
        assert (out["ret"], out["msg"]) == (False, "can't get SERVER_NAME variable : no such variable")

    def test_init_reports_an_internalstore_write_failure(self, tmp_path):
        out = self._init(tmp_path, setup='STORE_SET_ERROR = "no memory"')
        assert (out["ret"], out["msg"]) == (False, f"can't store greylist {SERVER} list into internalstore : no memory")
