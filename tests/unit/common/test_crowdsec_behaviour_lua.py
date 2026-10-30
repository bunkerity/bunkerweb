"""Behaviour of ``src/common/core/crowdsec/crowdsec.lua``, the real file run under plain Lua.

The plugin builds one CrowdSec bouncer per service in ``init`` and asks it about every client in
``access``: a ban becomes a deny with the evidence attached, a challenge page ends the request, a
bouncer error is reported, and a service without a loaded bouncer fails open. ``api`` answers the
health check and the connection control routes. The vendored bouncer (``crowdsec.lib.bouncer``), its
configuration loader, ``cache_partition`` and ``banlease`` are stand-ins driven by globals (they have
their own tests); OpenResty is stubbed at its boundary (``_lua_plugin_helpers.py``).
"""

import hashlib
import json

import pytest
from _lua_plugin_helpers import CORE, LUA, module_path, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("CROWDSEC", CORE / "crowdsec" / "crowdsec.lua")
CACHE = "/var/cache/bunkerweb/crowdsec/"
GLOBAL_FILE = CACHE + "crowdsec.conf"
LAPI = "http://lapi:8080"

PREAMBLE = r"""
local function hex(raw) return (raw:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end
local function normalize(url) return (url:gsub("/+$", "")) end

package.loaded["crowdsec.cache_partition"] = {
    hash = function(text) return hex(SHA256(text)) end,
    api_url = function(content) return content:match("API_URL=(%S+)") or "" end,
    normalize = normalize,
    fingerprints = function() return {} end,
    prefixes = function(urls)
        if PREFIX_ERR then return nil, PREFIX_ERR end
        local map, seen, count = {}, {}, 0
        for _, url in ipairs(urls) do
            if not seen[normalize(url)] then
                seen[normalize(url)] = true
                count = count + 1
            end
            map[url] = "prefix" .. count
        end
        return map, count
    end,
    challenge_prefix = function(scope) return "challenge:" .. scope end,
}

LEASE_EPOCH_CALLS, BUILT, PROMOTED = {}, {}, {}
package.loaded["bunkerweb.banlease"] = {
    lease_epoch = function(ip) LEASE_EPOCH_CALLS[#LEASE_EPOCH_CALLS + 1] = ip return 7 end,
    build_lease = function(evidence, now, refresh)
        BUILT[#BUILT + 1] = { evidence = evidence, refresh = refresh }
        if BUILD_ERR then return nil, BUILD_ERR end
        return 300, { reason = "crowdsec" }
    end,
    promote_lease = function(ip, service, kind, ttl, reason_data, country, opts)
        if PROMOTE_ERROR then error(PROMOTE_ERROR) end
        PROMOTED[#PROMOTED + 1] = { ip = ip, service = service, kind = kind, ttl = ttl, country = country, lease_epoch = opts.lease_epoch }
        return true, "stored"
    end,
}

package.loaded["crowdsec.lib.config"] = {
    loadConfig = function(file)
        if CONFIG_FAIL and CONFIG_FAIL[file] then return nil end
        return { file = file }
    end,
}

-- One fresh bouncer per require, like the real module: its behaviour is looked up by the file it was initialised with.
BOUNCERS, ALLOW_CALLS, INIT_ERR, ALLOW, HEALTH, CONN_INFO, CONTROL = {}, {}, {}, {}, {}, {}, {}
package.preload["crowdsec.lib.bouncer"] = function()
    if BOUNCER_LOAD_ERR then error(BOUNCER_LOAD_ERR) end
    local b = {}
    BOUNCERS[#BOUNCERS + 1] = b
    function b.init(file, user_agent, prefix, fingerprint, aliases)
        b.file, b.prefix = file, prefix
        local handle = io.open(file, "r")
        b.api = handle and handle:read("*a"):match("API_URL=(%S+)") or ""
        if handle then handle:close() end
        if INIT_ERR[file] then return false, INIT_ERR[file] end
        return true
    end
    function b.ConnectionInfo()
        local info = {}
        for k, v in pairs(CONN_INFO[b.file] or { lapi_url = b.api, appsec_url = "", mode = "live" }) do info[k] = v end
        return info
    end
    function b.GetCaptchaTemplate() return "template" end
    function b.HasExcludedLocations() return EXCLUDED_LOCATIONS or false end
    function b.Allow(ip, prefix)
        ALLOW_CALLS[#ALLOW_CALLS + 1] = { file = b.file, ip = ip, prefix = prefix }
        local result = ALLOW[b.file] or { true, nil, false }
        return table.unpack(result, 1, 4)
    end
    function b.Health()
        local result = HEALTH[b.file] or { true, nil, true }
        return table.unpack(result, 1, 3)
    end
    function b.Control(operation, params)
        CONTROL_CALLS = (CONTROL_CALLS or 0) + 1
        local result = CONTROL[b.file] or { { done = operation }, nil, 200 }
        return table.unpack(result, 1, 3)
    end
    return b
end

ngx.var.hostname = "node-1"

-- A request-phase plugin for ``ctx``; ``vars`` are the service settings.
function request(ctx, vars)
    IS_REQUEST = true
    PHASE = "access"
    VARIABLES = vars or { USE_CROWDSEC = "yes", CROWDSEC_BAN_REFRESH = "0" }
    return new_plugin(PLUGIN, ctx or {})
end
"""


def conf(api=LAPI):
    return f"API_URL={api}\n"


def run(tmp_path, action, *, confs=None, multisite="no", setup="", boot_enabled=True):
    """Write the conf files, run the real ``init`` (booting the bouncers), then run ``action`` (Lua).

    ``confs`` maps a scope (``global`` for single site) to its file content, or ``None`` for a missing file.
    """
    confs = {"global": conf()} if confs is None else confs
    for scope, content in confs.items():
        if content is None:
            continue
        path = tmp_path / "crowdsec" / ("" if scope == "global" else scope) / "crowdsec.conf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    scoped = {scope: {"USE_CROWDSEC": "yes"} for scope in confs}
    body = f"""
GETVAR = {to_lua({"MULTISITE": multisite})}
MULTI_VARS = {to_lua(scoped)}
HAS_VARIABLE = {"true" if boot_enabled else "false"}
{setup}
PHASE = "init"
IS_REQUEST = false
boot = new_plugin(PLUGIN, {{}}):init()
{action}
"""
    return run_module(MODULE, body, fs_root=tmp_path, preamble=PREAMBLE)


def flat(value):
    """A request body as the stand-in JSON decoder reads it (flat, no spaces)."""
    return json.dumps(value, separators=(",", ":"))


def conn_id(scope="global", lapi=LAPI, appsec=""):
    return hashlib.sha256(f"{scope}\0{lapi}\0{appsec}".encode()).hexdigest()


ACCESS = """
local result = request({ remote_addr = "203.0.113.5", server_name = "%s" }, %s):access()
emit({ ret = result.ret, msg = result.msg, status = result.status, data = result.data,
       allow_calls = ALLOW_CALLS, promoted = PROMOTED, epochs = LEASE_EPOCH_CALLS, logs = LOGS })
"""


def access(tmp_path, *, server="www.example.com", vars_=None, **kwargs):
    variables = to_lua({"USE_CROWDSEC": "yes", "CROWDSEC_BAN_REFRESH": "0", **(vars_ or {})})
    out = run(tmp_path, ACCESS % (server, variables), **kwargs)
    return {"status": None, "data": None, **out}


class TestAccessDecisions:
    def test_a_service_without_crowdsec_is_not_checked(self, tmp_path):
        out = access(tmp_path, vars_={"USE_CROWDSEC": "no"})
        assert (out["ret"], out["msg"], out["allow_calls"]) == (True, "CrowdSec plugin not enabled", {})

    def test_no_decision_lets_the_request_through(self, tmp_path):
        out = access(tmp_path)
        assert (out["ret"], out["msg"], out["status"]) == (True, "Not denied by CrowdSec bouncer", None)
        assert out["allow_calls"] == [{"file": GLOBAL_FILE, "ip": "203.0.113.5", "prefix": "challenge:global"}]

    def test_a_ban_denies_with_the_deny_status_and_the_evidence(self, tmp_path):
        setup = f'ALLOW["{GLOBAL_FILE}"] = {{ true, nil, true, {{ reason = "crowdsecurity/ssh-bf" }} }}\nDENY_STATUS = 444'
        out = access(tmp_path, setup=setup)
        assert (out["ret"], out["msg"], out["status"]) == (True, "CrowdSec bouncer denied request", 444)
        assert out["data"]["reason"] == "crowdsecurity/ssh-bf"
        assert out["data"]["service_scope"] == "global"
        assert out["data"]["instance"] == "node-1"
        assert out["data"]["connection"] == conn_id()

    def test_a_ban_without_evidence_still_denies(self, tmp_path):
        out = access(tmp_path, setup=f'ALLOW["{GLOBAL_FILE}"] = {{ true, nil, true }}')
        assert (out["msg"], out["status"], out["data"]) == ("CrowdSec bouncer denied request", 403, None)

    def test_a_served_challenge_ends_the_request_with_200(self, tmp_path):
        out = access(tmp_path, setup=f'ALLOW["{GLOBAL_FILE}"] = {{ false, nil }}')
        assert (out["ret"], out["msg"], out["status"]) == (True, "CrowdSec challenge served", 200)

    def test_a_bouncer_error_is_reported_as_an_error_not_a_deny(self, tmp_path):
        out = access(tmp_path, setup=f'ALLOW["{GLOBAL_FILE}"] = {{ false, "lapi down" }}')
        assert (out["ret"], out["msg"], out["status"]) == (False, "Error while executing CrowdSec bouncer : lapi down", None)

    def test_a_service_whose_configuration_is_missing_fails_open(self, tmp_path):
        out = access(tmp_path, confs={"global": None})
        assert (out["ret"], out["msg"], out["allow_calls"]) == (True, "no CrowdSec bouncer loaded for this service", {})


class TestPerServiceBouncer:
    CONFS = {"a.example.com": conf("http://lapi-a:8080"), "b.example.com": conf("http://lapi-b:8080")}

    def test_a_multisite_request_uses_the_bouncer_of_its_own_service(self, tmp_path):
        out = access(tmp_path, server="b.example.com", confs=self.CONFS, multisite="yes")
        assert out["allow_calls"] == [{"file": CACHE + "b.example.com/crowdsec.conf", "ip": "203.0.113.5", "prefix": "challenge:b.example.com"}]

    def test_an_unconfigured_service_does_not_borrow_another_services_bouncer(self, tmp_path):
        out = access(tmp_path, server="c.example.com", confs=self.CONFS, multisite="yes")
        assert (out["msg"], out["allow_calls"]) == ("no CrowdSec bouncer loaded for this service", {})

    def test_the_ban_evidence_names_the_service_that_banned(self, tmp_path):
        setup = f'ALLOW["{CACHE}a.example.com/crowdsec.conf"] = {{ true, nil, true, {{ reason = "x" }} }}'
        out = access(tmp_path, server="a.example.com", confs=self.CONFS, multisite="yes", setup=setup)
        assert out["data"]["service_scope"] == "a.example.com"
        assert out["data"]["connection"] == conn_id("a.example.com", "http://lapi-a:8080")


class TestBanLease:
    BAN = f'ALLOW["{GLOBAL_FILE}"] = {{ true, nil, true, {{ reason = "x" }} }}\n'

    def test_a_ban_with_a_refresh_interval_promotes_a_lease_without_changing_the_deny(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=self.BAN)
        assert out["status"] == 403
        assert out["epochs"] == ["203.0.113.5"]
        assert out["promoted"] == [{"ip": "203.0.113.5", "kind": "global", "ttl": 300, "country": "unknown", "lease_epoch": 7}]

    def test_a_service_scoped_ban_promotes_a_service_lease(self, tmp_path):
        setup = f'ALLOW["{CACHE}a.example.com/crowdsec.conf"] = {{ true, nil, true, {{ reason = "x" }} }}'
        out = access(tmp_path, server="a.example.com", confs={"a.example.com": conf()}, multisite="yes", vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=setup)
        assert out["promoted"][0]["service"] == "a.example.com"
        assert out["promoted"][0]["kind"] == "service"

    def test_no_refresh_interval_means_no_lease_and_no_epoch_read(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "0"}, setup=self.BAN)
        assert (out["status"], out["epochs"], out["promoted"]) == (403, {}, {})

    def test_detect_mode_never_promotes_a_lease(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=self.BAN + 'SECURITY_MODE = "detect"')
        assert (out["status"], out["promoted"]) == (403, {})
        assert ["INFO", "no CrowdSec ban lease : security mode is not block"] in out["logs"]

    def test_a_service_with_excluded_locations_never_promotes(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=self.BAN + "EXCLUDED_LOCATIONS = true")
        assert out["promoted"] == {}
        assert ["INFO", "no CrowdSec ban lease : the service has excluded locations"] in out["logs"]

    def test_a_lease_that_cannot_be_built_is_logged_and_the_deny_stands(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=self.BAN + 'BUILD_ERR = "no expiry"')
        assert (out["status"], out["promoted"]) == (403, {})
        assert ["INFO", "no CrowdSec ban lease : no expiry"] in out["logs"]

    def test_a_promotion_crash_is_logged_and_the_deny_stands(self, tmp_path):
        out = access(tmp_path, vars_={"CROWDSEC_BAN_REFRESH": "60"}, setup=self.BAN + 'PROMOTE_ERROR = "redis down"')
        assert (out["ret"], out["status"]) == (True, 403)
        assert any(level == "ERR" and msg.startswith("can't promote the CrowdSec ban to a lease") and "redis down" in msg for level, msg in out["logs"])


class TestShouldPromote:
    @staticmethod
    def check(**params):
        base = {"refresh": 60, "security_mode": "block", "exclude_location": False, "mode": "live", "now": 1000}
        body = f"local ok, why = PLUGIN._should_promote({to_lua({**base, **params})})\nemit({{ ok = ok, why = why }})"
        out = run_module(MODULE, body, preamble=PREAMBLE)
        return out["ok"], out.get("why")

    def test_a_live_block_mode_ban_is_promotable(self):
        assert self.check() == (True, None)

    @pytest.mark.parametrize("refresh", [0, -1])
    def test_a_non_positive_refresh_is_never_promotable(self, refresh):
        assert self.check(refresh=refresh) == (False, "CROWDSEC_BAN_REFRESH is 0")

    def test_a_stream_connection_that_synchronised_recently_is_promotable(self):
        assert self.check(mode="stream", last_successful_sync=990, update_frequency=10) == (True, None)

    @pytest.mark.parametrize("sync", [{"last_successful_sync": 900, "update_frequency": 10}, {"update_frequency": 10}, {"last_successful_sync": 990}])
    def test_a_stale_or_unknown_stream_synchronisation_is_not_promotable(self, sync):
        assert self.check(mode="stream", **sync) == (False, "the stream synchronization is stale")

    def test_the_stream_staleness_limit_is_twice_the_update_frequency(self):
        assert self.check(mode="stream", last_successful_sync=980, update_frequency=10)[0] is True
        assert self.check(mode="stream", last_successful_sync=979, update_frequency=10)[0] is False


class TestInit:
    @staticmethod
    def init(tmp_path, **kwargs):
        action = "emit({ ret = boot.ret, msg = boot.msg, created = #BOUNCERS, logs = LOGS })"
        return run(tmp_path, action, **kwargs)

    def test_init_is_skipped_when_no_service_uses_crowdsec(self, tmp_path):
        out = self.init(tmp_path, boot_enabled=False)
        assert (out["ret"], out["msg"]) == (True, "init not needed")
        assert out["created"] == 0

    def test_a_single_site_boots_one_bouncer(self, tmp_path):
        out = self.init(tmp_path)
        assert (out["ret"], out["msg"], out["created"]) == (True, "1 bouncer(s) initialized for 1 service(s)", 1)

    def test_services_with_the_same_rendered_configuration_share_one_bouncer(self, tmp_path):
        out = self.init(tmp_path, confs={"a.example.com": conf(), "b.example.com": conf()}, multisite="yes")
        assert (out["msg"], out["created"]) == ("1 bouncer(s) initialized for 2 service(s)", 1)

    def test_distinct_local_apis_each_get_a_bouncer_and_a_partitioned_cache(self, tmp_path):
        confs = {"a.example.com": conf("http://lapi-a:8080"), "b.example.com": conf("http://lapi-b:8080")}
        out = self.init(tmp_path, confs=confs, multisite="yes")
        assert out["msg"] == "2 bouncer(s) initialized for 2 service(s), decision cache partitioned across 2 local API(s)"
        assert out["created"] == 2

    def test_a_service_without_configuration_is_skipped_and_the_others_still_load(self, tmp_path):
        out = self.init(tmp_path, confs={"a.example.com": conf(), "b.example.com": None}, multisite="yes")
        assert (out["ret"], out["msg"]) == (True, "1 bouncer(s) initialized for 1 service(s), skipping service(s) b.example.com")
        assert any(level == "ERR" and "missing CrowdSec configuration" in msg and "b.example.com" in msg for level, msg in out["logs"])

    def test_no_configuration_at_all_is_an_error(self, tmp_path):
        out = self.init(tmp_path, confs={"global": None})
        assert (out["ret"], out["msg"]) == (False, "no CrowdSec configuration could be loaded for service(s) global")

    def test_a_bouncer_that_fails_to_initialise_is_skipped(self, tmp_path):
        confs = {"a.example.com": conf("http://lapi-a:8080"), "b.example.com": conf("http://lapi-b:8080")}
        setup = f'INIT_ERR["{CACHE}b.example.com/crowdsec.conf"] = "bad api key"'
        out = self.init(tmp_path, confs=confs, multisite="yes", setup=setup)
        assert out["msg"] == "1 bouncer(s) initialized for 1 service(s), decision cache partitioned across 2 local API(s), skipping service(s) b.example.com"
        assert any(level == "ERR" and "error while initializing bouncer for service b.example.com : bad api key" in msg for level, msg in out["logs"])

    def test_a_bouncer_module_that_cannot_be_loaded_is_an_error(self, tmp_path):
        out = self.init(tmp_path, setup='BOUNCER_LOAD_ERR = "syntax error"')
        assert out["ret"] is False
        assert out["msg"] == "no CrowdSec configuration could be loaded for service(s) global"
        assert any(level == "ERR" and "can't create bouncer for service global" in msg for level, msg in out["logs"])

    def test_an_unreadable_multisite_setting_is_an_error(self, tmp_path):
        out = self.init(tmp_path, setup="GETVAR = {}")
        assert (out["ret"], out["msg"]) == (False, "can't get MULTISITE variable : no such variable MULTISITE")

    def test_a_cache_partition_refusal_aborts_init(self, tmp_path):
        out = self.init(tmp_path, setup='PREFIX_ERR = "prefix collision"')
        assert (out["ret"], out["msg"], out["created"]) == (False, "prefix collision", 0)

    def test_an_unloadable_configuration_still_boots_its_bouncer(self, tmp_path):
        out = self.init(tmp_path, setup=f'CONFIG_FAIL = {{ ["{GLOBAL_FILE}"] = true }}')
        assert (out["ret"], out["created"]) == (True, 1)
        assert any(level == "ERR" and "can't load CrowdSec configuration" in msg for level, msg in out["logs"])


PING = """
local plugin = request({ uri = "/crowdsec/ping", request_method = "POST" })
local result = plugin:api()
emit({ ret = result.ret, msg = result.msg, status = result.status })
"""


class TestApiPing:
    def ping(self, tmp_path, **kwargs):
        return {"status": None, **run(tmp_path, PING, **kwargs)}

    def test_a_healthy_bouncer_with_a_local_api_answers_200(self, tmp_path):
        out = self.ping(tmp_path)
        assert (out["ret"], out["status"]) == (True, 200)
        assert out["msg"] == "Authenticated Local API checks succeeded; AppSec health is not checked"

    def test_an_unhealthy_bouncer_answers_500_with_its_service(self, tmp_path):
        out = self.ping(tmp_path, setup=f'HEALTH["{GLOBAL_FILE}"] = {{ false, "401 unauthorized" }}')
        assert out["status"] == 500
        assert out["msg"] == "Error while executing CrowdSec bouncer for service global : 401 unauthorized"

    def test_a_configuration_without_a_local_api_answers_200_with_a_note(self, tmp_path):
        out = self.ping(tmp_path, setup=f'HEALTH["{GLOBAL_FILE}"] = {{ true, nil, false }}')
        assert out["status"] == 200
        assert out["msg"] == "CrowdSec configuration loaded; no Local API configured; AppSec health is not checked"

    def test_no_service_using_crowdsec_answers_200(self, tmp_path):
        body = PING.replace("local plugin", "HAS_VARIABLE = false\nlocal plugin")
        out = run(tmp_path, body)
        assert (out["status"], out["msg"]) == (200, "CrowdSec plugin is not enabled")

    def test_an_enablement_lookup_failure_answers_500(self, tmp_path):
        body = PING.replace("local plugin", "HAS_VARIABLE = nil\nlocal plugin")
        out = run(tmp_path, body)
        assert (out["status"], out["msg"]) == (500, "Can't check CrowdSec enablement : lookup failed")

    def test_a_missing_configuration_is_reported_and_answers_500(self, tmp_path):
        out = self.ping(tmp_path, confs={"a.example.com": conf(), "b.example.com": None}, multisite="yes")
        assert out["status"] == 500
        assert out["msg"] == "No CrowdSec configuration loaded for service(s) b.example.com; their requests bypass CrowdSec until the next reload"

    def test_a_missing_configuration_and_an_unhealthy_api_are_reported_together(self, tmp_path):
        setup = f'HEALTH["{CACHE}a.example.com/crowdsec.conf"] = {{ false, "timeout" }}'
        out = self.ping(tmp_path, confs={"a.example.com": conf(), "b.example.com": None}, multisite="yes", setup=setup)
        assert out["msg"].endswith("until the next reload. Error while executing CrowdSec bouncer for service a.example.com : timeout")

    def test_a_single_site_without_configuration_answers_500_naming_it(self, tmp_path):
        out = self.ping(tmp_path, confs={"global": None})
        assert (out["status"], out["msg"]) == (
            500,
            "No CrowdSec configuration loaded for service(s) global; their requests bypass CrowdSec until the next reload",
        )

    def test_no_loaded_bouncer_answers_500(self, tmp_path):
        # init never ran for CrowdSec (not needed at boot), yet a service enables it by the time of the check
        body = PING.replace("local plugin", "HAS_VARIABLE = true\nlocal plugin")
        out = run(tmp_path, body, boot_enabled=False)
        assert (out["status"], out["msg"]) == (500, "No CrowdSec bouncer loaded")


def connections(tmp_path, body=None, **kwargs):
    action = f"""
BODY = {to_lua(flat(body) if body is not None else None)}
local result = request({{ uri = "/crowdsec/connections", request_method = "POST" }}):api()
emit({{ ret = result.ret, msg = result.msg, status = result.status, data = result.data }})
"""
    return {"status": None, "data": None, **run(tmp_path, action, **kwargs)}


class TestApiConnections:
    def test_connections_are_listed_with_id_node_service_and_status(self, tmp_path):
        out = connections(tmp_path)
        assert (out["ret"], out["msg"], out["status"]) == (True, "CrowdSec connections", 200)
        [info] = out["data"]["connections"]
        assert (info["id"], info["node"], info["services"], info["status"]) == (conn_id(), "node-1", ["global"], "success")

    def test_credentials_embedded_in_the_urls_are_redacted(self, tmp_path):
        setup = f'CONN_INFO["{GLOBAL_FILE}"] = {{ lapi_url = "https://bob:s3cret@lapi:8080", appsec_url = "http://u:p@appsec:7422", mode = "live" }}'
        [info] = connections(tmp_path, setup=setup)["data"]["connections"]
        assert info["lapi_url"] == "https://[redacted]@lapi:8080"
        assert info["appsec_url"] == "http://[redacted]@appsec:7422"
        assert "s3cret" not in json.dumps(info)

    def test_an_unhealthy_bouncer_is_listed_with_an_error(self, tmp_path):
        [info] = connections(tmp_path, setup=f'HEALTH["{GLOBAL_FILE}"] = {{ false, "x" }}')["data"]["connections"]
        assert (info["status"], info["error"]) == ("error", "Authenticated Local API check failed")

    @pytest.mark.parametrize(
        ("info", "expected"),
        [
            ({"mode": "live"}, "not_synchronized"),
            ({"mode": "live", "last_successful_sync": 1}, "current"),
            ({"mode": "stream", "last_successful_sync": 999990, "update_frequency": 10}, "current"),
            ({"mode": "stream", "last_successful_sync": 999900, "update_frequency": 10}, "stale"),
        ],
    )
    def test_the_sync_status_follows_the_last_successful_sync(self, tmp_path, info, expected):
        setup = f'CONN_INFO["{GLOBAL_FILE}"] = {to_lua({"lapi_url": LAPI, "appsec_url": "", **info})}'
        [conn] = connections(tmp_path, setup=setup)["data"]["connections"]
        assert conn["sync_status"] == expected

    def test_connections_are_sorted_by_service_and_failed_services_are_listed(self, tmp_path):
        confs = {"b.example.com": conf("http://lapi-b:8080"), "a.example.com": conf("http://lapi-a:8080"), "c.example.com": None}
        out = connections(tmp_path, confs=confs, multisite="yes")
        assert [c["services"] for c in out["data"]["connections"]] == [["a.example.com"], ["b.example.com"], ["c.example.com"]]
        assert out["data"]["connections"][2]["error"] == "CrowdSec configuration is not loaded"

    def test_a_connection_filter_returns_only_that_connection(self, tmp_path):
        confs = {"a.example.com": conf("http://lapi-a:8080"), "b.example.com": conf("http://lapi-b:8080")}
        wanted = conn_id("b.example.com", "http://lapi-b:8080")
        out = connections(tmp_path, {"connection": wanted}, confs=confs, multisite="yes")
        assert [c["services"] for c in out["data"]["connections"]] == [["b.example.com"]]

    def test_a_filter_on_a_connection_that_is_gone_answers_404(self, tmp_path):
        out = connections(tmp_path, {"connection": "0" * 64})
        assert (out["status"], out["msg"]) == (404, "CrowdSec connection is no longer configured")

    def test_a_malformed_connection_id_answers_400(self, tmp_path):
        out = connections(tmp_path, {"connection": "short"})
        assert (out["status"], out["msg"]) == (400, "Invalid CrowdSec connection")


def control(tmp_path, operation, body, **kwargs):
    action = f"""
BODY = {to_lua(body)}
local result = request({{ uri = "/crowdsec/{operation}", request_method = "{kwargs.pop("method", "POST")}" }}):api()
emit({{ ret = result.ret, msg = result.msg, status = result.status, data = result.data, control_calls = CONTROL_CALLS or 0 }})
"""
    return {"status": None, "data": None, **run(tmp_path, action, **kwargs)}


class TestApiControl:
    @pytest.mark.parametrize("operation", ["decisions", "alerts", "unban", "allowlists", "allowlistcheck", "refresh_ip"])
    def test_a_known_connection_gets_the_operation_and_its_answer(self, tmp_path, operation):
        setup = f'CONTROL["{GLOBAL_FILE}"] = {{ {{ rows = "3" }}, nil, 200 }}'
        out = control(tmp_path, operation, flat({"connection": conn_id()}), setup=setup)
        assert (out["ret"], out["status"], out["msg"], out["data"]) == (True, 200, "CrowdSec operation completed", {"rows": "3"})

    def test_a_bouncer_error_and_status_are_passed_through(self, tmp_path):
        setup = f'CONTROL["{GLOBAL_FILE}"] = {{ nil, "unknown ip", 422 }}'
        out = control(tmp_path, "unban", flat({"connection": conn_id()}), setup=setup)
        assert (out["status"], out["msg"]) == (422, "unknown ip")

    def test_a_bouncer_that_gives_no_status_is_a_502(self, tmp_path):
        setup = f'CONTROL["{GLOBAL_FILE}"] = {{ nil, "upstream failed" }}'
        assert control(tmp_path, "alerts", flat({"connection": conn_id()}), setup=setup)["status"] == 502

    def test_a_request_without_a_valid_connection_is_a_400_and_reaches_no_bouncer(self, tmp_path):
        for body in (None, "not json", flat({}), flat({"connection": "short"})):
            out = control(tmp_path, "unban", body)
            assert (out["status"], out["msg"], out["control_calls"]) == (400, "A configured CrowdSec connection is required", 0)

    def test_a_connection_that_is_gone_is_a_404(self, tmp_path):
        out = control(tmp_path, "unban", flat({"connection": "f" * 64}))
        assert (out["status"], out["msg"], out["control_calls"]) == (404, "CrowdSec connection is no longer configured", 0)

    def test_a_non_post_request_is_not_handled(self, tmp_path):
        out = control(tmp_path, "unban", flat({"connection": conn_id()}), method="GET")
        assert (out["ret"], out["msg"], out["control_calls"]) == (False, "success", 0)

    def test_an_unknown_operation_is_not_handled(self, tmp_path):
        out = control(tmp_path, "shutdown", flat({"connection": conn_id()}))
        assert (out["ret"], out["control_calls"]) == (False, 0)
