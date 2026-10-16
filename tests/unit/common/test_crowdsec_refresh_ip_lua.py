"""``csmod.RefreshIp`` and the two bits of evidence the lease needs from the bouncer.

``refresh_ip`` re-reads one IP's decisions from the Local API and replaces this instance's cached
entries for it. The unban flow calls it after it deleted a decision, so the deleted ban cannot
survive in the cache and be promoted to a lease again by the next request. What can go wrong is
silent: a stale key left behind keeps denying an IP the operator just unbanned.

* ``decision_cache`` and the live query carry the decision's ``remediation`` into the evidence,
  because promotion only counts a decision whose remediation is ``ban``.
* ``HasExcludedLocations`` answers whether the service excludes any location, which forbids a lease
  (the early ban check would deny the excluded locations too).

The shipped ``lib/bouncer.lua`` and ``lib/decision_cache.lua`` are loaded for real; the OpenResty
surface, the Local API and ``iputils`` (which needs ``ffi``) are stubbed. ``cjson`` is a registry that
round-trips tables, because the JSON text is not what is under test.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / "src" / "common" / "core" / "crowdsec" / "lib"
BOUNCER = LIB / "bouncer.lua"
DECISION_CACHE = LIB / "decision_cache.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = r"""
local LOGS, REQUESTS, LOCKS = {}, {}, {}
local NOW = 1000

-- cjson: a registry. encode() hands back a token, decode() the table behind it, so the decision cache
-- round-trips exactly what it stored. Local API bodies are looked up by their text.
local REGISTRY, SEQ = {}, 0
local cjson = { null = setmetatable({}, { __tostring = function() return "null" end }), array_mt = {} }
cjson.encode = function(value) SEQ = SEQ + 1; REGISTRY["#" .. SEQ] = value; return "#" .. SEQ end
cjson.decode = function(text)
  if REGISTRY[text] ~= nil then return REGISTRY[text] end
  error("not json")
end
cjson.new = function()
  return {
    decode_array_with_array_mt = function() end,
    decode = function(text)
      local body = LAPI_BODIES[text]
      if body == nil then error("not json") end
      return setmetatable(body, cjson.array_mt)
    end,
  }
end
package.loaded["cjson"] = cjson
function REGISTRY_DECODE(token) return REGISTRY[token] end
package.loaded["cjson.safe"] = cjson

ngx = { ERR = "ERR", DEBUG = "DEBUG", ALERT = "ALERT", NOTICE = "NOTICE", HTTP_FORBIDDEN = 403,
  time = function() return NOW end, -- sleeping moves the clock, or the lock-retry deadline of RefreshIp would never be reached
  sleep = function(seconds) NOW = NOW + seconds end, now = function() return NOW end,
  worker = { id = function() return 0 end }, timer = { at = function() return true end },
  log = function(level, ...) LOGS[#LOGS + 1] = level .. " " .. table.concat({ ... }, "") end,
  req = { is_internal = function() return false end } }

-- A shared dict that records the deletes, so "no stale key" is a statement about keys and not about
-- what a read happens to return.
local function dict()
  local values = {}
  return {
    values = values,
    get = function(_, key) return values[key] end,
    set = function(_, key, value) values[key] = value; return true end,
    safe_set = function(_, key, value) values[key] = value; return true end,
    delete = function(_, key) values[key] = nil end,
    incr = function(_, key, by, initial) values[key] = (values[key] or initial) + by; return values[key] end,
  }
end
CACHE, METADATA = dict(), dict()
ngx.shared = { crowdsec_cache = CACHE, crowdsec_metadata = METADATA }

package.loaded["crowdsec.cache_partition"] = { hash = function(value) return value end }
package.loaded["crowdsec.lib.config"] = { loadConfig = function() return CONF end }
package.loaded["crowdsec.lib.stream_lock"] = { run = function(path, callback)
  LOCKS[#LOCKS + 1] = path
  if LOCK_BUSY then return nil, "busy" end
  callback()
  return true
end }
-- ipv4 only: the real module needs ffi. Masks run /32 down to /0, as the real list does.
local MASKS = {}
for bits = 32, 0, -1 do MASKS[#MASKS + 1] = (0xFFFFFFFF << (32 - bits)) & 0xFFFFFFFF end
package.loaded["crowdsec.lib.iputils"] = {
  netmasks_by_key_type = { ipv4 = MASKS },
  parseIPAddress = function(ip)
    local a, b, c, d = ip:match("^(%d+)%.(%d+)%.(%d+)%.(%d+)$")
    if not a then return nil end
    return (tonumber(a) << 24) | (tonumber(b) << 16) | (tonumber(c) << 8) | tonumber(d), true
  end,
  splitRange = function(item) local ip, cidr = item:match("^([^/]+)/(%d+)$") return ip, tonumber(cidr) end,
  cidrToInt = function(cidr) return (0xFFFFFFFF << (32 - cidr)) & 0xFFFFFFFF end,
  ipv4_band = function(a, b) return (tonumber(a) & tonumber(b)) end,
}
package.loaded["resty.http"] = { new = function()
  return {
    set_timeouts = function() end,
    set_timeout = function() end,
    close = function() end,
    request_uri = function(_, uri)
      REQUESTS[#REQUESTS + 1] = uri
      if LAPI_ERR then return nil, LAPI_ERR end
      return LAPI_RESPONSE
    end,
  }
end }
for _, name in ipairs({ "captcha", "challenge", "flag", "utils", "ban", "url", "template" }) do
  package.loaded["crowdsec.lib." .. name] = package.loaded["crowdsec.lib." .. name] or {
    table_len = function(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end,
    New = function() return nil end,
  }
end
package.loaded["bunkerweb.utils"] = { get_variable = function() return "100" end }
package.loaded["bit32"] = {}

package.loaded["crowdsec.lib.decision_cache"] = dofile("@@DECISION_CACHE@@")
csmod = dofile("@@BOUNCER@@")

CONF = CONF_FOR_INIT
local initialised, err = csmod.init("/dev/null", "ua", "v2|a|")
assert(initialised, err)

function lapi(body, status)
  local text = "body" .. tostring(#REQUESTS) .. tostring(os.clock())
  LAPI_BODIES[text] = body
  LAPI_RESPONSE = { status = status or 200, body = text }
  return text
end

function decision(id, value, kind, duration, scope)
  return { id = id, origin = "crowdsec", scenario = "crowdsecurity/http-probing", type = kind or "ban",
    scope = scope or "Ip", value = value, duration = duration or "1h" }
end

function cached_keys()
  local keys = {}
  for key in pairs(CACHE.values) do
    if key:find("v2_decisions_", 1, true) then keys[#keys + 1] = key end
  end
  table.sort(keys)
  return keys
end

@@BODY@@
"""

CONF = (
    '{ ENABLED = "true", MODE = "%s", API_URL = "http://lapi:8080", APPSEC_URL = "", REDIRECT_LOCATION = "", '
    'EXCLUDE_LOCATION = %s, SSL_VERIFY = "true", ALWAYS_SEND_TO_APPSEC = "false", FALLBACK_REMEDIATION = "ban", '
    'BOUNCING_ON_TYPE = "all", CACHE_EXPIRATION = 1, UPDATE_FREQUENCY = 10, REQUEST_TIMEOUT = 1, STREAM_REQUEST_TIMEOUT = 1, '
    'CAPTCHA_PROVIDER = "" }'
)


def run(body: str, *, mode: str = "live", exclude: str = "{}", cache_expiration: int | None = None, lock_busy: bool = False):
    conf = CONF % (mode, exclude)
    if cache_expiration is not None:
        conf = conf.replace("CACHE_EXPIRATION = 1,", f"CACHE_EXPIRATION = {cache_expiration},")
    script = f"LAPI_BODIES = {{}}\nLOCK_BUSY = {'true' if lock_busy else 'false'}\nCONF_FOR_INIT = {conf}\n" + HARNESS.replace(
        "@@BOUNCER@@", str(BOUNCER)
    ).replace("@@DECISION_CACHE@@", str(DECISION_CACHE)).replace("@@BODY@@", body)
    return subprocess.run(["lua", "-e", script], capture_output=True, text=True)


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


class TestHasExcludedLocations:
    def test_none(self):
        res = run("print('R=' .. tostring(csmod.HasExcludedLocations()))")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "false"

    def test_some(self):
        res = run("print('R=' .. tostring(csmod.HasExcludedLocations()))", exclude='{ "/health" }')
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "true"

    def test_a_redirect_location_the_plugin_appended_counts(self):
        """init() adds REDIRECT_LOCATION to the exclude list: those requests are never judged, so a lease
        (denied before any plugin runs) would deny them as well."""
        script_conf = 'REDIRECT_LOCATION = ""'
        assert script_conf in CONF
        conf = CONF.replace(script_conf, 'REDIRECT_LOCATION = "/denied"')
        res = subprocess.run(
            [
                "lua",
                "-e",
                "LAPI_BODIES = {}\nLOCK_BUSY=false\nCONF_FOR_INIT = "
                + conf % ("live", "{}")
                + HARNESS.replace("@@BOUNCER@@", str(BOUNCER))
                .replace("@@DECISION_CACHE@@", str(DECISION_CACHE))
                .replace("@@BODY@@", "print('R=' .. tostring(csmod.HasExcludedLocations()))"),
            ],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "true"


class TestTheEvidenceCarriesTheRemediation:
    def test_a_live_query_names_each_decision_remediation(self):
        res = run("""
lapi({ decision(1, "1.2.3.4", "ban"), decision(2, "1.2.3.4", "captcha"), decision(3, "1.2.3.4", "throttle") })
local ok, remediation, err, evidence = csmod.allowIp("1.2.3.4")
print("OK=" .. tostring(ok) .. "|" .. tostring(remediation))
local seen = {}
for _, d in ipairs(evidence.decisions) do seen[#seen + 1] = d.id .. ":" .. tostring(d.remediation) end
print("DECISIONS=" .. table.concat(seen, ","))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "OK") == "false|ban"
        # `throttle` is not a CrowdSec remediation this plugin knows: it is enforced as FALLBACK_REMEDIATION.
        assert field(res.stdout, "DECISIONS") == "1:ban,2:captcha,3:ban"

    def test_a_cache_hit_keeps_it_too(self):
        res = run("""
lapi({ decision(1, "1.2.3.4", "ban") })
csmod.allowIp("1.2.3.4")
local ok, remediation, _, evidence = csmod.allowIp("1.2.3.4")
print("REQUESTS=" .. #REQUESTS)
print("REMEDIATION=" .. tostring(remediation) .. "|" .. tostring(evidence.decisions[1].remediation))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "REQUESTS") == "1"
        assert field(res.stdout, "REMEDIATION") == "ban|ban"

    def test_the_decision_cache_stores_and_returns_it(self):
        res = run("""
local store = package.loaded["crowdsec.lib.decision_cache"].new(CACHE, METADATA)
assert(store.update("ipv4_k", decision(7, "1.2.3.4", "ban"), "ban", 3600))
local remediation, evidence = store.get("ipv4_k")
print("R=" .. remediation .. "|" .. tostring(evidence.decisions[1].remediation))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "ban|ban"

    def test_evidence_stored_before_the_upgrade_gets_it_from_the_record(self):
        """Metadata written by an older version has no remediation; the cache record still knows it."""
        res = run("""
local store = package.loaded["crowdsec.lib.decision_cache"].new(CACHE, METADATA)
assert(store.update("ipv4_k", decision(7, "1.2.3.4", "ban"), "ban", 3600))
for _, token in pairs(METADATA.values) do REGISTRY_DECODE(token).remediation = nil end
local _, evidence = store.get("ipv4_k")
print("R=" .. tostring(evidence.decisions[1].remediation))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "ban"


class TestRefreshIp:
    def test_an_invalid_ip_is_refused_before_any_request(self):
        res = run("""
for _, bad in ipairs({ "not-an-ip", "1.2.3", "" }) do
  local data, err, status = csmod.RefreshIp({ ip = bad })
  print("R=" .. tostring(data) .. "|" .. tostring(err) .. "|" .. tostring(status))
end
local data, err, status = csmod.RefreshIp(nil)
print("NIL=" .. tostring(status))
print("REQUESTS=" .. #REQUESTS)
""")
        assert res.returncode == 0, res.stderr
        assert [line for line in res.stdout.splitlines() if line.startswith("R=")] == ["R=nil|invalid ip|400"] * 3
        assert field(res.stdout, "NIL") == "400"
        assert field(res.stdout, "REQUESTS") == "0"

    def test_it_replaces_the_cache_and_leaves_no_stale_key(self):
        """The IP had a ban decision; CrowdSec no longer reports it. After the refresh nothing for that
        IP is cached, so the next request is not denied from a stale entry."""
        res = run("""
lapi({ decision(1, "1.2.3.4", "ban") })
csmod.allowIp("1.2.3.4")
print("BEFORE=" .. #cached_keys())
lapi({})
local data, err, status = csmod.RefreshIp({ ip = "1.2.3.4" })
print("STATUS=" .. tostring(status))
print("REMEDIATION=" .. tostring(data.remediation))
print("IDS=" .. #data.decision_ids)
print("AFTER=" .. #cached_keys())
local allowed = csmod.allowIp("1.2.3.4")
print("ALLOWED_AFTER=" .. tostring(allowed))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "BEFORE") == "1"
        assert field(res.stdout, "STATUS") == "200"
        assert field(res.stdout, "REMEDIATION") == "nil"
        assert field(res.stdout, "IDS") == "0"
        assert field(res.stdout, "AFTER") == "0"
        assert field(res.stdout, "ALLOWED_AFTER") == "true"

    def test_it_drops_the_cached_allowed_marker(self):
        """A live query that found nothing marks the IP allowed for CACHE_EXPIRATION; a decision that
        appeared since must not hide behind it."""
        res = run("""
lapi({})
csmod.allowIp("1.2.3.4")
local marker = "v2_allowed_ipv4_4294967295_16909060"
print("MARKED=" .. tostring(CACHE.values["v2|a|" .. marker]))
lapi({ decision(1, "1.2.3.4", "ban") })
local data = csmod.RefreshIp({ ip = "1.2.3.4" })
print("MARKER_AFTER=" .. tostring(CACHE.values["v2|a|" .. marker]))
print("REMEDIATION=" .. tostring(data.remediation))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "MARKED") == "true"
        assert field(res.stdout, "MARKER_AFTER") == "nil"
        assert field(res.stdout, "REMEDIATION") == "ban"

    def test_it_applies_what_the_local_api_reports_now(self):
        res = run("""
lapi({ decision(5, "1.2.3.4", "ban"), decision(6, "1.2.3.4", "captcha") })
local data, err, status = csmod.RefreshIp({ ip = "1.2.3.4" })
print("STATUS=" .. tostring(status))
print("REMEDIATION=" .. data.remediation)
table.sort(data.decision_ids)
print("IDS=" .. table.concat(data.decision_ids, ","))
print("OBSERVED=" .. data.observed_at)
print("URL=" .. REQUESTS[1])
local remediation = csmod.allowIp("1.2.3.4")
print("DENIED_FROM_CACHE=" .. tostring(remediation == false) .. "|" .. #REQUESTS)
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "200"
        assert field(res.stdout, "REMEDIATION") == "ban"
        assert field(res.stdout, "IDS") == "5,6"
        assert field(res.stdout, "OBSERVED") == "1000"
        assert field(res.stdout, "URL") == "http://lapi:8080/v1/decisions?ip=1.2.3.4&contains=true"
        # The refresh filled the cache: the next check does not call the Local API again.
        assert field(res.stdout, "DENIED_FROM_CACHE") == "true|1"

    def test_a_range_decision_covering_the_ip_is_replaced_too(self):
        res = run("""
lapi({ decision(1, "1.2.3.0/24", "ban", "1h", "Range") })
csmod.allowIp("1.2.3.4")
print("BEFORE=" .. #cached_keys())
lapi({})
csmod.RefreshIp({ ip = "1.2.3.4" })
print("AFTER=" .. #cached_keys())
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "BEFORE") == "1"
        assert field(res.stdout, "AFTER") == "0"

    def test_a_local_api_failure_changes_nothing(self):
        res = run("""
lapi({ decision(1, "1.2.3.4", "ban") })
csmod.allowIp("1.2.3.4")
LAPI_ERR = "connection refused"
local data, err, status = csmod.RefreshIp({ ip = "1.2.3.4" })
print("R=" .. tostring(data) .. "|" .. tostring(err) .. "|" .. tostring(status))
print("KEYS=" .. #cached_keys())
LAPI_ERR = nil
LAPI_RESPONSE = { status = 500, body = "" }
local _, err2, status2 = csmod.RefreshIp({ ip = "1.2.3.4" })
print("HTTP=" .. tostring(err2) .. "|" .. tostring(status2))
print("KEYS2=" .. #cached_keys())
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "nil|Local API request failed|502"
        assert field(res.stdout, "KEYS") == "1"
        assert field(res.stdout, "HTTP") == "Local API returned HTTP 500|502"
        assert field(res.stdout, "KEYS2") == "1"

    def test_live_mode_does_not_take_the_stream_lock(self):
        res = run("lapi({})\ncsmod.RefreshIp({ ip = '1.2.3.4' })\nprint('LOCKS=' .. #LOCKS)")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "LOCKS") == "0"

    def test_stream_mode_runs_under_the_poller_lock(self):
        res = run(
            """
lapi({ decision(1, "1.2.3.4", "ban") })
local data, err, status = csmod.RefreshIp({ ip = "1.2.3.4" })
print("STATUS=" .. tostring(status))
print("LOCKS=" .. #LOCKS)
print("REMEDIATION=" .. tostring(data.remediation))
""",
            mode="stream",
        )
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "200"
        assert field(res.stdout, "LOCKS") == "1"
        assert field(res.stdout, "REMEDIATION") == "ban"

    def test_a_busy_poller_lock_is_a_503_and_changes_nothing(self):
        res = run(
            """
lapi({ decision(1, "1.2.3.4", "ban") })
local data, err, status = csmod.RefreshIp({ ip = "1.2.3.4" })
print("R=" .. tostring(data) .. "|" .. tostring(err) .. "|" .. tostring(status))
print("REQUESTS=" .. #REQUESTS)
""",
            mode="stream",
            lock_busy=True,
        )
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "R") == "nil|busy|503"
        assert field(res.stdout, "REQUESTS") == "0"

    def test_control_routes_the_action(self):
        res = run("""
lapi({})
local data, err, status = csmod.Control("refresh_ip", { ip = "1.2.3.4" })
print("STATUS=" .. tostring(status) .. "|" .. tostring(data and data.ip))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "200|1.2.3.4"
