"""Behaviour of ``src/common/core/dnsbl/dnsbl.lua``, the real file run under plain Lua.

Covers what an operator relies on: the disabled path, the non-global shortcut, a listed client being
denied, a clean client passing, a resolver failure never denying, the ignore list and the 24h cache.
The resolver boundary (``resty.dns.resolver``, ``utils.get_ips`` and the light threads) is stubbed
in ``tests/unit/common/_lua_state_helpers.py``: a query name maps to the A records the test hands
back, and threads run to completion when they are spawned.
"""

import re

import pytest
from _lua_state_helpers import CORE, LUA, ROOT, build_script, last_json, module_path, run_lua, run_plugin, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("DNSBL", CORE / "dnsbl" / "dnsbl.lua")
SERVER = "www.example.com"
# the client 1.2.3.4 is looked up as 4.3.2.1.<server>
Q = "4.3.2.1."


def variables(**overrides):
    return {"USE_DNSBL": "yes", "DNSBL_LIST": "bl.example.org", "DNSBL_IGNORE_IP": "", **overrides}


def access(*, extra_variables=None, ctx=None, cache=None, dns=None, stored=None, setup="", method="access"):
    body = f"""
VARIABLES = {to_lua(variables(**(extra_variables or {})))}
STORE["plugin_dnsbl_lists_{SERVER}"] = {to_lua(stored or {"IGNORE_IP": []})}
CACHE = {to_lua(cache or {})}
DNS = {to_lua(dns or {})}
{setup}
local result = new_plugin(PLUGIN, {to_lua({"ip_is_global": True, **(ctx or {})})}):{method}()
local out = summary(result)
out.metrics, out.cache, out.queries, out.ttl = METRICS, CACHE, DNS_QUERIES, CACHE_TTL
out.killed = KILLED and #KILLED or 0
local errors = {{}}
for _, entry in ipairs(LOGS) do if entry[1] == "ERR" then errors[#errors + 1] = entry[2] end end
out.errors = errors
emit(out)
"""
    out = {"status": None, "data": None, "ttl": None, **run_plugin(MODULE, body)}
    out["queries"], out["errors"] = out["queries"] or [], out["errors"] or []
    return out


class TestDisabledPath:
    def test_a_service_without_dnsbl_is_not_checked(self):
        out = access(extra_variables={"USE_DNSBL": "no"}, dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert (out["ret"], out["msg"], out["status"], out["queries"]) == (True, "dnsbl not activated", None, [])

    def test_an_empty_dnsbl_list_is_not_checked(self):
        out = access(extra_variables={"DNSBL_LIST": ""})
        assert (out["msg"], out["status"], out["queries"]) == ("dnsbl list is empty", None, [])

    def test_a_non_global_client_never_reaches_a_lookup(self):
        out = access(ctx={"ip_is_global": False}, dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert (out["msg"], out["status"], out["queries"]) == ("client IP is not global, skipping DNSBL check", None, [])


class TestListedAndClean:
    def test_a_listed_client_is_denied_with_the_deny_status_and_the_list_name(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]}, setup="DENY_STATUS = 444")
        assert out["status"] == 444
        assert out["msg"] == "IP is blacklisted by bl.example.org"
        assert out["data"] == {"id": "dnsbl", "dnsbl": "bl.example.org"}
        assert out["queries"] == [Q + "bl.example.org"]

    def test_the_listing_is_cached_for_a_day(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert out["cache"] == {f"plugin_dnsbl_{SERVER}1.2.3.4": "bl.example.org"}
        assert out["ttl"] == 86400

    def test_a_clean_client_passes_and_the_verdict_is_cached(self):
        out = access(dns={Q + "bl.example.org": []})
        assert (out["ret"], out["msg"], out["status"]) == (True, "IP is not in DNSBL", None)
        assert out["cache"] == {f"plugin_dnsbl_{SERVER}1.2.3.4": "ok"}

    def test_an_answer_outside_127_0_0_x_does_not_count_as_a_listing(self):
        # DNSBL providers answer 127.0.0.x for a hit; anything else (a wildcard or sinkhole answer) is not one
        out = access(dns={Q + "bl.example.org": ["192.0.2.55"]})
        assert (out["msg"], out["status"]) == ("IP is not in DNSBL", None)

    def test_a_listing_on_the_second_server_denies(self):
        out = access(
            extra_variables={"DNSBL_LIST": "a.bl b.bl"},
            dns={Q + "a.bl": [], Q + "b.bl": ["127.0.0.4"]},
        )
        assert (out["status"], out["msg"]) == (403, "IP is blacklisted by b.bl")

    def test_the_first_denial_of_an_ip_is_counted_like_a_cached_one(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert out["metrics"] == {"failed_dnsbl": 1}

    def test_the_other_lookups_are_killed_once_a_server_reports_the_ip(self):
        out = access(
            extra_variables={"DNSBL_LIST": "a.bl b.bl"},
            dns={Q + "a.bl": ["127.0.0.2"], Q + "b.bl": []},
        )
        assert out["status"] == 403
        assert out["killed"] == 1


class TestResolverFailure:
    @pytest.mark.parametrize("errcode", [2, 5])
    def test_real_get_ips_rcode_outage_retries_and_denies_after_recovery(self, errcode):
        source = re.search(r"^utils.get_ips = function.*?^end$", (ROOT / "src/bw/lua/bunkerweb/utils.lua").read_text(), re.M | re.S)
        assert source
        setup = f"""
do
    local utils = require 'bunkerweb.utils'
    local resolver = require 'resty.dns.resolver'
    local encode, decode, ERR = json.encode, json.decode, ngx.ERR
    local logger = {{log = function(_, level, msg) LOGS[#LOGS + 1] = {{level, msg}} end}}
    utils.get_resolvers = function() return {{'127.0.0.1'}} end
    utils.new_cachestore = function()
        return {{
            get = function(_, key) return true, CACHE[key] end,
            set = function(_, key, value) CACHE[key] = value; return true end,
        }}
    end
    resolver.new = function()
        return {{TYPE_A = 1, TYPE_AAAA = 28, query = function(_, name)
            DNS_QUERIES[#DNS_QUERIES + 1] = name
            if not RECOVERED then return {{errcode = {errcode}, errstr = 'resolver failure'}} end
            return {{{{address = '127.0.0.2'}}}}
        end}}
    end
""" + source.group(0) + "\nend\n"
        body = f"""
VARIABLES = {to_lua(variables())}
STORE['plugin_dnsbl_lists_{SERVER}'] = {{IGNORE_IP = {{}}}}
local first = summary(new_plugin(PLUGIN, {{ip_is_global = true}}):access())
local first_cache = json.encode(CACHE)
RECOVERED = true
local second = summary(new_plugin(PLUGIN, {{ip_is_global = true}}):access())
emit({{first = first, first_cache = json.decode(first_cache), second = second,
    cache = CACHE, queries = DNS_QUERIES, logs = LOGS}})
"""
        script = build_script(MODULE, body).replace("PLUGIN = dofile(", setup + "PLUGIN = dofile(", 1)
        out = last_json(run_lua(script))
        assert out["second"].get("status") == 403, out
        assert out["second"]["msg"] == "IP is blacklisted by bl.example.org"
        assert out["first_cache"] == {}
        assert out["first"]["ret"] is True
        assert "status" not in out["first"]
        assert out["queries"] == [Q + "bl.example.org"] * 2
        assert out["cache"][f"plugin_dnsbl_{SERVER}1.2.3.4"] == "bl.example.org"
        assert ["ERR", 'error while sending DNS request to bl.example.org : {} {"A":"resolver failure"}'] in out["logs"]

    def test_real_get_ips_timeout_never_caches_dns_or_clean_verdict(self):
        source = re.search(r"^utils.get_ips = function.*?^end$", (ROOT / "src/bw/lua/bunkerweb/utils.lua").read_text(), re.M | re.S)
        assert source
        setup = """
do
    local utils = require 'bunkerweb.utils'
    local resolver = require 'resty.dns.resolver'
    local encode, decode, ERR = json.encode, json.decode, ngx.ERR
    local logger = {log = function(_, level, msg) LOGS[#LOGS + 1] = {level, msg} end}
    utils.get_resolvers = function() return {'127.0.0.1'} end
    utils.new_cachestore = function()
        return {
            get = function(_, key) return true, CACHE[key] end,
            set = function(_, key, value) CACHE[key] = value; return true end,
        }
    end
    resolver.new = function()
        return {TYPE_A = 1, TYPE_AAAA = 28, query = function(_, name)
            DNS_QUERIES[#DNS_QUERIES + 1] = name
            return nil, 'timeout'
        end}
    end
""" + source.group(0) + "\nend\n"
        body = f"""
VARIABLES = {to_lua(variables())}
STORE['plugin_dnsbl_lists_{SERVER}'] = {{IGNORE_IP = {{}}}}
local result = new_plugin(PLUGIN, {{ip_is_global = true}}):access()
local second = new_plugin(PLUGIN, {{ip_is_global = true}}):access()
emit({{ret = result.ret, status = result.status, second_ret = second.ret,
    cache = CACHE, queries = DNS_QUERIES, logs = LOGS}})
"""
        script = build_script(MODULE, body).replace("PLUGIN = dofile(", setup + "PLUGIN = dofile(", 1)
        out = last_json(run_lua(script))
        assert out["cache"] == {}, out
        assert (out["ret"], out["second_ret"]) == (True, True)
        assert "status" not in out
        assert out["queries"] == [Q + "bl.example.org"] * 2
        assert ["ERR", 'error while sending DNS request to bl.example.org : {"A":"timeout"} {}'] in out["logs"]

    def test_a_resolver_failure_never_denies_and_is_logged(self):
        out = access()  # no DNS record at all: the stub reports a lookup failure
        assert (out["ret"], out["status"]) == (True, None)
        assert out["errors"] == [f"error while sending DNS request to bl.example.org : dns failure for {Q}bl.example.org"]
        assert out["cache"] == {}

    def test_one_clean_answer_during_a_partial_outage_is_cached_for_a_day(self):
        out = access(
            extra_variables={"DNSBL_LIST": "a.bl b.bl"},
            dns={Q + "b.bl": []},
        )
        assert (out["ret"], out["status"]) == (True, None)
        assert out["errors"] == [f"error while sending DNS request to a.bl : dns failure for {Q}a.bl"]
        assert out["cache"] == {f"plugin_dnsbl_{SERVER}1.2.3.4": "ok"}
        assert out["ttl"] == 86400

    def test_one_failing_server_does_not_hide_a_listing_on_another(self):
        out = access(
            extra_variables={"DNSBL_LIST": "a.bl b.bl"},
            dns={Q + "b.bl": ["127.0.0.2"]},  # a.bl: lookup failure
        )
        assert (out["status"], out["msg"]) == (403, "IP is blacklisted by b.bl")
        assert out["errors"] == [f"error while sending DNS request to a.bl : dns failure for {Q}a.bl"]

    def test_a_thread_error_is_reported_without_denying_or_caching(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]}, setup='WAIT_ERROR = "thread died"')
        assert (out["ret"], out["msg"], out["status"]) == (False, "error while waiting thread : thread died", None)
        assert out["cache"] == {}

    def test_a_cache_backend_error_is_reported_without_denying(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]}, setup='CACHE_ERROR = "cache down"')
        assert (out["ret"], out["msg"], out["status"]) == (False, "error while checking cache : cache down", None)
        assert out["queries"] == []


class TestCache:
    def test_a_cached_listing_is_denied_and_counted_without_a_lookup(self):
        out = access(cache={f"plugin_dnsbl_{SERVER}1.2.3.4": "bl.example.org"})
        assert out["status"] == 403
        assert out["msg"] == "client IP 1.2.3.4 is in DNSBL cache (server = bl.example.org)"
        assert out["data"] == {"id": "dnsbl", "dnsbl": "bl.example.org"}
        assert out["metrics"] == {"failed_dnsbl": 1}
        assert out["queries"] == []

    def test_a_cached_clean_verdict_passes_without_a_lookup(self):
        out = access(cache={f"plugin_dnsbl_{SERVER}1.2.3.4": "ok"}, dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert (out["status"], out["msg"], out["queries"]) == (
            None,
            "client IP 1.2.3.4 is in DNSBL cache (not blacklisted)",
            [],
        )


class TestIgnoreList:
    def test_an_ignored_network_skips_the_lookup_and_is_cached_as_clean(self):
        out = access(stored={"IGNORE_IP": ["1.2.3.0/24"]}, dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert (out["status"], out["msg"]) == (None, "client IP 1.2.3.4 is ignored for DNSBL checks")
        assert out["queries"] == []
        assert out["cache"] == {f"plugin_dnsbl_{SERVER}1.2.3.4": "ok"}

    def test_an_address_outside_the_ignored_network_is_still_checked(self):
        out = access(stored={"IGNORE_IP": ["10.0.0.0/8"]}, dns={Q + "bl.example.org": ["127.0.0.2"]})
        assert out["status"] == 403

    def test_the_service_variable_is_merged_with_the_stored_ignore_list(self):
        out = access(
            extra_variables={"DNSBL_IGNORE_IP": "1.2.3.4"},
            stored={"IGNORE_IP": ["10.0.0.0/8"]},
            dns={Q + "bl.example.org": ["127.0.0.2"]},
        )
        assert (out["status"], out["queries"]) == (None, [])


class TestStream:
    def test_preread_applies_the_same_decision_as_access(self):
        out = access(dns={Q + "bl.example.org": ["127.0.0.2"]}, method="preread")
        assert (out["status"], out["data"]) == (403, {"id": "dnsbl", "dnsbl": "bl.example.org"})


class TestInitWorker:
    def _init_worker(self, dns, *, extra_variables=None, setup=""):
        body = f"""
VARIABLES = {to_lua(variables(**(extra_variables or {})))}
DNS = {to_lua(dns)}
PHASE = "init_worker"
IS_REQUEST = false
{setup}
local result = new_plugin(PLUGIN):init_worker()
emit({{ ret = result.ret, msg = result.msg, logs = LOGS, queries = DNS_QUERIES }})
"""
        out = run_plugin(MODULE, body)
        out["queries"] = out["queries"] or []
        return out

    def test_the_probe_address_is_resolved_against_every_configured_server(self):
        out = self._init_worker({"2.0.0.127.bl.example.org": ["127.0.0.2"]})
        assert (out["ret"], out["msg"]) == (True, "success")
        assert out["queries"] == ["2.0.0.127.bl.example.org"]
        assert ["NOTICE", "dnsbl check for bl.example.org is successful"] in out["logs"]

    def test_a_server_that_does_not_list_the_probe_address_is_reported_as_failing(self):
        out = self._init_worker({"2.0.0.127.bl.example.org": []})
        assert ["ERR", "dnsbl check for bl.example.org failed"] in out["logs"]

    def test_a_resolver_failure_is_reported(self):
        out = self._init_worker({})
        assert ["ERR", "error while sending DNS request to bl.example.org : dns failure for 2.0.0.127.bl.example.org"] in out["logs"]

    def test_nothing_runs_when_no_service_uses_dnsbl(self):
        out = self._init_worker({}, setup="HAS_VARIABLE = false")
        assert (out["ret"], out["msg"], out["queries"]) == (True, "no service uses DNSBL, skipping init_worker", [])

    def test_nothing_runs_while_loading(self):
        out = self._init_worker({}, setup="IS_LOADING = true")
        assert (out["ret"], out["msg"]) == (False, "BW is loading")


class TestInit:
    def _init(self, tmp_path, *, server_name: str | None = SERVER, files=None, setup=""):
        for name, lines in (files or {}).items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        body = f"""
VARIABLES = {to_lua({"USE_DNSBL": "yes"})}
PHASE = "init"
IS_REQUEST = false
SERVER_NAME = {to_lua(server_name)}
{setup}
local result = new_plugin(PLUGIN):init()
emit({{ ret = result.ret, msg = result.msg, store = STORE }})
"""
        return run_plugin(MODULE, body, fs_root=tmp_path)

    def test_init_loads_each_service_ignore_list_into_its_own_internalstore_key(self, tmp_path):
        out = self._init(
            tmp_path,
            server_name="a.example b.example",
            files={"dnsbl/a.example/IGNORE_IP.list": ["10.0.0.0/8", "", "10.0.0.0/8", "192.168.0.1"]},
        )
        assert out["ret"] is True
        assert out["store"]["plugin_dnsbl_lists_a.example"]["IGNORE_IP"] == ["10.0.0.0/8", "192.168.0.1"]
        assert not out["store"]["plugin_dnsbl_lists_b.example"]["IGNORE_IP"]

    def test_init_publishes_the_ignore_header_rules(self, tmp_path):
        out = self._init(tmp_path)
        assert out["store"]["plugin_dnsbl_header_rules"] == {"name": "DNSBL_IGNORE_HEADER"}

    def test_init_is_skipped_when_no_service_uses_dnsbl(self, tmp_path):
        out = self._init(tmp_path, setup="HAS_VARIABLE = false")
        assert (out["ret"], out["msg"], out["store"]) == (True, "init not needed", {})

    def test_init_fails_when_server_name_cannot_be_read(self, tmp_path):
        out = self._init(tmp_path, server_name=None)
        assert (out["ret"], out["msg"]) == (False, "can't get SERVER_NAME variable : no such variable")
