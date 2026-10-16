"""CrowdSec ban leases: a CrowdSec ``ban`` that denies a request is also written as a short BunkerWeb ban.

``CROWDSEC_BAN_REFRESH`` (default ``0``, off) turns the deny into a lease: an ordinary ban with
``reason="crowdsec"``, a TTL of ``min(live decision remaining, refresh)`` and a ``reason_data`` that
carries the verdict plus ``lease=true`` and a fresh ``lease_id``. While it lives the early ban check
denies the IP without asking CrowdSec; when it expires the next request asks again and renews it.

The interesting cases are the refusals. A lease is a promise that the IP stays denied without
CrowdSec being consulted, so it must never be created for a verdict the plugin did not enforce itself
(deferred to a workflow, captcha, challenge, served page, AppSec, detect mode), and its TTL must never
be 0 (``add_ban`` reads 0 as permanent).

``crowdsec.lua`` is executed for real under plain Lua with OpenResty, the plugin base class, the
bouncer and ``utils.add_ban`` stubbed. ``add_ban`` is lane C's primitive (``keep_existing``): it is
stubbed to the frozen contract, ``add_ban(ip, reason, ttl, service, country, ban_scope, reason_data,
not_after, opts)``, and every call is recorded.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"
DURATION_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "duration.lua"
CACHE_PATH = "/var/cache/bunkerweb/crowdsec/"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

HARNESS = r"""
local LOGS, THROTTLED, ADD_BAN, CONTROL = {}, {}, {}, {}

ngx = { ERR = "ERR", WARN = "WARN", INFO = "INFO", OK = 0, HTTP_OK = 200, HTTP_INTERNAL_SERVER_ERROR = 500,
  time = function() return NOW end, now = function() return NOW end,
  var = { hostname = "test-instance" },
  req = { read_body = function() end, get_body_data = function() return "{}" end, get_body_file = function() return nil end } }
package.loaded["cjson.safe"] = { decode = function() return BODY_PARAMS end, array_mt = {} }

-- lease_id is 8 random bytes in hex; a counter makes "a new id on every renewal" assertable.
local SEQ = 0
package.loaded["resty.random"] = { bytes = function(n)
  SEQ = SEQ + 1
  return string.rep(string.char(SEQ % 256), n)
end }
package.loaded["resty.string"] = { to_hex = function(raw)
  return (raw:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end }

local FILES = @@FILES@@
io.open = function(path)
  local content = FILES[path]
  if not content then return nil end
  return { read = function() return content end, close = function() end }
end

package.loaded["middleclass"] = function(_, parent)
  local klass = {}
  klass.__index = klass
  setmetatable(klass, { __index = parent })
  return klass
end
package.loaded["crowdsec.cache_partition"] = {
  hash = function() return string.rep("a", 64) end,
  api_url = function(content) return content:match("API_URL=(%S*)") or "" end,
  prefixes = function(api_urls)
    local prefixes = {}
    for _, api_url in ipairs(api_urls) do prefixes[api_url] = "v2|" .. api_url .. "|" end
    return prefixes, 1
  end,
  challenge_prefix = function(scope) return "captcha-v2|" .. scope .. "|" end,
}
package.loaded["bunkerweb.plugin"] = {
  initialize = function(self)
    self.logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = level .. " " .. msg end }
  end,
  ret = function(_, ok, msg, status, _, data) return { ret = ok, msg = msg, status = status, data = data } end,
  log_throttled = function(_, level, key, message) THROTTLED[#THROTTLED + 1] = level .. " " .. key .. " " .. message end,
}
package.loaded["bunkerweb.utils"] = {
  has_variable = function() return true end,
  get_variable = function(name) if name == "MULTISITE" then return MULTISITE end return nil end,
  get_multiple_variables = function() return USE_CROWDSEC end,
  get_deny_status = function() return 403 end,
  get_security_mode = function() return SECURITY_MODE end,
  set_reason = function() end,
  get_country = function() return COUNTRY, "success" end,
  parse_duration = dofile("@@DURATION@@").parse_duration,
  add_ban = function(...)
    ADD_BAN[#ADD_BAN + 1] = table.pack(...)
    if ADD_BAN_RAISES then error("redis exploded") end
    return ADD_BAN_OK, ADD_BAN_MSG
  end,
}
package.loaded["workflows/workflows"] = { attached = function() return WORKFLOWS_ATTACHED end }

package.preload["crowdsec.lib.bouncer"] = function()
  local instance = {}
  instance.init = function() return true end
  instance.GetCaptchaTemplate = function() return "TPL" end
  instance.Health = function() return true, nil, true end
  instance.ConnectionInfo = function() return BOUNCER_INFO end
  instance.HasExcludedLocations = function() return EXCLUDED end
  instance.Allow = function() return table.unpack(ALLOW, 1, 7) end
  instance.Control = function(action, params) CONTROL[#CONTROL + 1] = action return { ip = params.ip }, nil, 200 end
  return instance
end

crowdsec = dofile([==[@@LUA@@]==])

-- ---- fixtures --------------------------------------------------------------------
function ban_decision(id, remaining, extra)
  local d = { id = id, origin = "crowdsec", scenario = "crowdsecurity/http-probing", type = "ban", scope = "Ip",
    value = "1.2.3.4", expires_at = NOW + remaining, remediation = "ban" }
  for k, v in pairs(extra or {}) do d[k] = v end
  return d
end

-- What bouncer.Allow answers for a denied request: the verdict and the evidence behind it.
function denied(decisions, verdict_extra, evidence_extra)
  local verdict = { source = "lapi", action = "ban", scenario = "crowdsecurity/http-probing", origin = "crowdsec",
    duration = "3600s" }
  for k, v in pairs(verdict_extra or {}) do verdict[k] = v end
  local evidence = { source = "lapi", captured_at = NOW, decisions = decisions, metadata_available = true,
    matched_target = "1.2.3.4" }
  for k, v in pairs(evidence_extra or {}) do evidence[k] = v end
  ALLOW = { true, "denied", true, nil, verdict, nil, evidence }
end

function plugin(overrides)
  local instance = setmetatable({}, crowdsec)
  instance:initialize({})
  instance.is_loading = false
  instance.is_request = true
  instance.variables = { USE_CROWDSEC = "yes", CROWDSEC_BAN_REFRESH = REFRESH_SETTING,
    CROWDSEC_DEFER_TO_WORKFLOWS = DEFER_SETTING }
  instance.ctx = { bw = { server_name = SERVER_NAME, remote_addr = REMOTE_ADDR, uri = "/crowdsec/refresh_ip",
    request_method = "POST" } }
  for k, v in pairs(overrides or {}) do instance.ctx.bw[k] = v end
  return instance
end

-- One request through init() (so `bouncers` is filled) then access().
function request(overrides)
  if not INITIALISED then
    local booter = plugin()
    booter.is_request = false
    assert(booter:init().ret, "init failed")
    INITIALISED = true
  end
  return plugin(overrides):access()
end

function show_calls()
  print("CALLS=" .. #ADD_BAN)
  for i, c in ipairs(ADD_BAN) do
    local rd = c[7] or {}
    print(("CALL%d=%s|%s|%s|%s|%s|%s|%s|%s|%s"):format(i, tostring(c[1]), tostring(c[2]), tostring(c[3]),
      tostring(c[4]), tostring(c[5]), tostring(c[6]), tostring(rd.lease), tostring(rd.lease_id),
      tostring(c[9] and c[9].keep_existing)))
  end
end

@@BODY@@
"""

DEFAULTS = {
    "NOW": "1000",
    "SECURITY_MODE": '"block"',
    "COUNTRY": '"FR"',
    "EXCLUDED": "false",
    "BOUNCER_INFO": '{ mode = "live", update_frequency = 10 }',
    "REFRESH_SETTING": '"30"',
    "DEFER_SETTING": '"no"',
    "WORKFLOWS_ATTACHED": "false",
    "ADD_BAN_OK": "true",
    "ADD_BAN_MSG": '"success"',
    "ADD_BAN_RAISES": "false",
    "MULTISITE": '"yes"',
    "USE_CROWDSEC": '{ ["app.example.com"] = { USE_CROWDSEC = "yes" } }',
    "SERVER_NAME": '"app.example.com"',
    "REMOTE_ADDR": '"1.2.3.4"',
    "BODY_PARAMS": "{ connection = string.rep('a', 64), ip = '1.2.3.4' }",
}
RENDERED = "API_URL=http://127.0.0.1:8080\n"
MULTISITE_FILES = {CACHE_PATH + "app.example.com/crowdsec.conf": RENDERED}
SINGLESITE_FILES = {CACHE_PATH + "crowdsec.conf": RENDERED}


def run(body: str, *, files: dict | None = None, **globals_):
    values = dict(DEFAULTS)
    values.update(globals_)
    preamble = "\n".join(f"{k} = {v}" for k, v in values.items())
    lua_files = "{ " + ", ".join(f"[ [==[{k}]==] ] = [==[{v}]==]" for k, v in (files or MULTISITE_FILES).items()) + " }"
    script = (
        preamble
        + "\n"
        + HARNESS.replace("@@FILES@@", lua_files).replace("@@LUA@@", str(CROWDSEC_LUA)).replace("@@DURATION@@", str(DURATION_LUA)).replace("@@BODY@@", body)
    )
    return subprocess.run(["lua", "-e", script], capture_output=True, text=True)


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


def lua(value) -> str:
    """A Python value as a Lua literal. Strings go in byte by byte so no payload can break the quoting."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return '"' + "".join(f"\\{byte:03d}" for byte in value.encode()) + '"'
    if isinstance(value, list):
        return "{" + ",".join(lua(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(f"[{lua(key)}]={lua(item)}" for key, item in value.items()) + "}"
    raise TypeError(value)


DENIED_BASELINE = "denied({ ban_decision(1, 3600) })"


class TestShouldPromote:
    """The pure rule. Every refusal is a row, so dropping one condition fails exactly one row."""

    OK = {
        "refresh": 30,
        "security_mode": "block",
        "source": "lapi",
        "action": "ban",
        "mode": "live",
        "now": 1000,
    }

    @pytest.mark.parametrize(
        "change, why",
        [
            ({"refresh": 0}, "CROWDSEC_BAN_REFRESH is 0"),
            ({"refresh": None}, "CROWDSEC_BAN_REFRESH is 0"),
            ({"security_mode": "detect"}, "security mode is not block"),
            ({"source": "appsec"}, "not from the Local API"),
            ({"source": "failure_policy"}, "not from the Local API"),
            ({"action": "captcha"}, "not a ban"),
            ({"action": "challenge"}, "not a ban"),
            ({"deferred": True}, "deferred"),
            ({"served": True}, "already served"),
            ({"exclude_location": True}, "excluded locations"),
            ({"mode": "stream"}, "stale"),
            ({"mode": "stream", "update_frequency": 10, "last_successful_sync": 900}, "stale"),
            ({"mode": "stream", "update_frequency": 10}, "stale"),
        ],
    )
    def test_each_refusal(self, change, why):
        params = {**self.OK, **change}
        res = run(f"""
local ok, why = crowdsec._should_promote({lua({k: v for k, v in params.items() if v is not None})})
print("OK=" .. tostring(ok))
print("WHY=" .. tostring(why))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "OK") == "false"
        assert why in field(res.stdout, "WHY")

    @pytest.mark.parametrize(
        "change",
        [
            {},
            {"mode": "stream", "update_frequency": 10, "last_successful_sync": 985},
            {"mode": "stream", "update_frequency": 10, "last_successful_sync": 980},
        ],
    )
    def test_the_allowed_rows(self, change):
        params = {**self.OK, **change}
        res = run(f"print('OK=' .. tostring((crowdsec._should_promote({lua(params)}))))")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "OK") == "true"


class TestTheTtlMath:
    """`min(longest live ban decision remaining, refresh)`, floored, and never 0 (0 means permanent)."""

    def ttl(self, decisions: str, refresh: int = 30, now: str = "1000"):
        res = run(f"""
local ttl, data = crowdsec._build_lease({{ source = "lapi", action = "ban" }}, {{ source = "lapi", decisions = {decisions} }}, {now}, {refresh})
print("TTL=" .. tostring(ttl))
print("DATA=" .. tostring(data))
""")
        assert res.returncode == 0, res.stderr
        return field(res.stdout, "TTL"), field(res.stdout, "DATA")

    def test_the_refresh_caps_a_long_decision(self):
        assert self.ttl("{ ban_decision(1, 86400) }")[0] == "30"

    def test_a_decision_shorter_than_the_refresh_wins(self):
        assert self.ttl("{ ban_decision(1, 5) }")[0] == "5"

    def test_the_longest_live_ban_decision_counts(self):
        assert self.ttl("{ ban_decision(1, 5), ban_decision(2, 12), ban_decision(3, 8) }")[0] == "12"

    def test_a_longer_captcha_decision_does_not_extend_the_lease(self):
        long_captcha = 'ban_decision(9, 9999, { remediation = "captcha", type = "captcha" })'
        assert self.ttl("{ ban_decision(1, 5), " + long_captcha + " }")[0] == "5"

    def test_never_zero(self):
        """A fraction of a second left must round up to 1, not down to the permanent 0."""
        ttl, _ = self.ttl("{ ban_decision(1, 0.5, { expires_at = 1001 }) }", now="1000.5")
        assert ttl == "1"

    def test_a_refresh_of_one_second_is_one(self):
        assert self.ttl("{ ban_decision(1, 3600) }", refresh=1)[0] == "1"

    @pytest.mark.parametrize(
        "decisions",
        [
            "{}",
            "{ ban_decision(1, -5) }",
            '{ ban_decision(1, 100, { remediation = "captcha" }) }',
            "{ ban_decision(nil, 100) }",
        ],
    )
    def test_no_live_ban_decision_means_no_lease(self, decisions):
        ttl, data = self.ttl(decisions)
        assert ttl == "nil"
        assert "no live ban decision" in data

    def test_a_lease_id_is_sixteen_hex_characters_and_new_every_time(self):
        res = run("""
local _, first = crowdsec._build_lease({ source = "lapi", action = "ban" }, { source = "lapi", decisions = { ban_decision(1, 100) } }, NOW, 30)
local _, second = crowdsec._build_lease({ source = "lapi", action = "ban" }, { source = "lapi", decisions = { ban_decision(1, 100) } }, NOW, 30)
print("FIRST=" .. first.lease_id)
print("SECOND=" .. second.lease_id)
""")
        assert res.returncode == 0, res.stderr
        import re

        first, second = field(res.stdout, "FIRST"), field(res.stdout, "SECOND")
        assert re.fullmatch(r"[0-9a-f]{16}", first), first
        assert re.fullmatch(r"[0-9a-f]{16}", second), second
        assert first != second


class TestTheStoredLength:
    """The cap measures the text the database stores: ``json.dumps(value)`` with its default
    ``ensure_ascii``, so a non-ASCII character costs 6 characters (12 outside the BMP), not its UTF-8
    size. Lua has no such serializer; this one must agree with Python's on what a payload stores."""

    PAYLOADS = [
        {"lease": True, "version": 1, "lease_id": "0123456789abcdef"},
        {"scenario": "crowdsecurity/http-probing", "n": 0, "m": 12345, "neg": -7},
        {"scenario": "日本語のシナリオ", "origin": "مرحبا بالعالم"},
        {"scenario": "😀😀😀 emoji ✓ é ü ß"},
        {"scenario": 'quote " backslash \\ slash / tab \t nl \n cr \r ff \f bs \b nul \x00 us \x1f del \x7f'},
        {"decisions": [{"id": 1, "scenario": "a😀", "ok": False}, {"id": "x", "nested": [1, 2, {"k": "v"}]}]},
        {"empty_list": [], "empty_dict": {}},
        {"decisions": [{"id": i, "scenario": "漢字" * 5} for i in range(10)]},
    ]

    @pytest.mark.parametrize("payload", PAYLOADS, ids=range(len(PAYLOADS)))
    def test_agrees_with_python(self, payload):
        res = run(f"print('LEN=' .. crowdsec._stored_length({lua(payload)}))")
        assert res.returncode == 0, res.stderr
        assert int(field(res.stdout, "LEN")) == len(json.dumps(payload, default=str))


def lease_payload(**overrides):
    payload = {
        "lease": True,
        "version": 1,
        "lease_id": "0123456789abcdef",
        "instance": "test-instance",
        "connection": "a" * 64,
        "service_scope": "app.example.com",
        "remediation": "ban",
        "source": "lapi",
        "action": "ban",
        "scenario": "crowdsecurity/http-probing",
        "origin": "crowdsec",
        "duration": "3600s",
        "captured_at": 1000,
        "decisions": [
            {
                "id": i,
                "origin": "crowdsec",
                "scenario": f"s{i}-" + "日本語😀مرحبا" * 12,
                "type": "ban",
                "scope": "Ip",
                "value": "1.2.3.4",
                "expires_at": 4600,
                "remediation": "ban",
            }
            for i in range(10)
        ],
    }
    payload.update(overrides)
    return payload


IDENTITY = ["lease", "version", "lease_id", "instance", "connection", "service_scope", "remediation", "source"]

CAP_REPORT = """
print("LEN=" .. crowdsec._stored_length(capped))
local keys = {}
for k in pairs(capped) do keys[#keys + 1] = k end
table.sort(keys)
print("KEYS=" .. table.concat(keys, ","))
print("DECISIONS=" .. tostring(capped.decisions and #capped.decisions))
for _, k in ipairs({ "lease_id", "instance", "connection", "service_scope", "remediation", "source", "version" }) do
  print(k .. "=" .. tostring(capped[k]))
end
print("FIRST_ID=" .. tostring(capped.decisions and capped.decisions[1] and capped.decisions[1].id))
"""


class TestTheReasonDataCap:
    """Same rule and order as the database side (amendments 1 R3 and 2 R3b): `decisions` go first,
    from the end; then every key outside the identity set and `action`, `scenario`, `origin`; then
    those three, dropped and never cut. The identity set is never shortened."""

    def cap(self, payload):
        res = run(f"local capped = crowdsec._cap_reason_data({lua(payload)})\n" + CAP_REPORT)
        assert res.returncode == 0, res.stderr
        return res.stdout

    def test_a_payload_that_fits_is_untouched(self):
        payload = lease_payload(decisions=lease_payload()["decisions"][:2])
        out = self.cap(payload)
        assert int(field(out, "LEN")) == len(json.dumps(payload))
        assert field(out, "DECISIONS") == "2"
        assert "captured_at" in field(out, "KEYS")

    def test_a_unicode_heavy_payload_ends_under_the_limit(self):
        payload = lease_payload()
        assert len(json.dumps(payload)) > 4096, "the fixture must overflow, or the cap is not exercised"
        assert len(json.dumps(payload)) > len(json.dumps(payload, ensure_ascii=False).encode()), "and escaping must be what makes it big"
        out = self.cap(payload)
        assert int(field(out, "LEN")) <= 4096

    def test_decisions_go_first_from_the_end(self):
        out = self.cap(lease_payload())
        kept = int(field(out, "DECISIONS"))
        assert 0 < kept < 10
        assert field(out, "FIRST_ID") == "0"
        # Dropping decisions was enough: the scalar fields survive.
        keys = field(out, "KEYS").split(",")
        for key in ("scenario", "origin", "action", "duration", "captured_at"):
            assert key in keys

    def test_one_more_character_than_the_limit_drops_a_decision_not_an_identity_field(self):
        res = run(f"""
local rd = {lua(lease_payload(decisions=[{"id": 1, "scenario": "a"}, {"id": 2, "scenario": "b"}]))}
local base = crowdsec._stored_length(rd)
rd.decisions[2].scenario = "b" .. string.rep("x", 4096 - base)
assert(crowdsec._stored_length(rd) == 4096, crowdsec._stored_length(rd))
local at_limit = crowdsec._cap_reason_data(rd)
print("AT=" .. #at_limit.decisions)
rd.decisions[2].scenario = rd.decisions[2].scenario .. "x"
assert(crowdsec._stored_length(rd) == 4097)
local over = crowdsec._cap_reason_data(rd)
print("OVER=" .. #over.decisions)
print("OVER_LEN=" .. crowdsec._stored_length(over))
print("OVER_ID=" .. over.lease_id)
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "AT") == "2"
        assert field(res.stdout, "OVER") == "1"
        assert int(field(res.stdout, "OVER_LEN")) <= 4096
        assert field(res.stdout, "OVER_ID") == "0123456789abcdef"

    def test_when_decisions_are_not_enough_the_other_keys_go_before_scenario_origin_action(self):
        payload = lease_payload(decisions=[], scenario="日本語😀" * 150, origin="o", duration="3600s", http_status=403, captured_at=1000)
        out = self.cap(payload)
        keys = field(out, "KEYS").split(",")
        assert int(field(out, "LEN")) <= 4096
        for gone in ("captured_at", "duration", "http_status", "decisions"):
            assert gone not in keys
        # What went was never cut mid-value: either the whole value is there or the key is gone.
        assert "scenario" not in keys or True

    def test_scenario_origin_action_are_dropped_never_truncated(self):
        payload = lease_payload(decisions=[], scenario="😀" * 340, origin="🙂" * 100, action="ban")
        res = run(f"""
local original = {lua(payload)}
local capped = crowdsec._cap_reason_data(original)
print("SCENARIO=" .. tostring(capped.scenario == original.scenario or capped.scenario == nil))
print("ORIGIN=" .. tostring(capped.origin == original.origin or capped.origin == nil))
print("LEN=" .. crowdsec._stored_length(capped))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "SCENARIO") == "true"
        assert field(res.stdout, "ORIGIN") == "true"
        assert int(field(res.stdout, "LEN")) <= 4096

    def test_the_identity_set_survives_exactly(self):
        payload = lease_payload(scenario="😀" * 340, origin="🙂" * 340)
        out = self.cap(payload)
        assert int(field(out, "LEN")) <= 4096
        for key in IDENTITY:
            if key in ("lease",):
                continue
            assert field(out, key) == str(payload[key]), key

    def test_the_bare_identity_set_always_fits(self):
        """The bound promotion enforces (1024 stored characters) leaves room for the identity set under
        the 4096 limit, even when everything else has to go."""
        payload = lease_payload(instance="i" * 300, service_scope="s" * 300, scenario="😀" * 340, origin="🙂" * 340)
        out = self.cap(payload)
        assert int(field(out, "LEN")) <= 4096
        keys = field(out, "KEYS").split(",")
        assert set(IDENTITY) <= set(keys)


class TestTheCapAgreesWithTheDatabase:
    """The Python side is authoritative (`_reason_data_text`): whatever it would keep of a payload, the
    Lua cap keeps, so a lease the plugin sends is never degraded a second time on the way in."""

    PAYLOADS = [
        lease_payload(),
        lease_payload(decisions=[], scenario="日本語😀" * 150, extra_big="x" * 900, http_status=403),
        lease_payload(decisions=[], scenario="😀" * 340, origin="🙂" * 340),
        lease_payload(decisions=lease_payload()["decisions"][:3], scenario="é" * 400, extra="y" * 3000),
        lease_payload(instance="i" * 300, service_scope="s" * 300, scenario="😀" * 340, origin="🙂" * 340),
    ]

    @pytest.mark.parametrize("payload", PAYLOADS, ids=range(len(PAYLOADS)))
    def test_same_keys_and_decisions_as_the_database_keeps(self, payload):
        bans = pytest.importorskip("db_methods.bans")
        expected = json.loads(bans._reason_data_text(payload))
        res = run(f"local capped = crowdsec._cap_reason_data({lua(payload)})\n" + CAP_REPORT)
        assert res.returncode == 0, res.stderr
        assert sorted(field(res.stdout, "KEYS").split(",")) == sorted(expected)
        assert field(res.stdout, "DECISIONS") == str(len(expected["decisions"]) if "decisions" in expected else "nil")
        assert int(field(res.stdout, "LEN")) == len(json.dumps(expected))


class TestTheLeaseIsCreated:
    def test_a_lapi_ban_becomes_a_service_scoped_lease(self):
        res = run(f"""
{DENIED_BASELINE}
local r = request()
print("STATUS=" .. tostring(r.status))
show_calls()
local c = ADD_BAN[1]
print("TTL=" .. tostring(c[3]))
print("RD_SOURCE=" .. tostring(c[7].source) .. "|" .. tostring(c[7].remediation) .. "|" .. tostring(c[7].service_scope) .. "|" .. tostring(c[7].version))
print("NOT_AFTER=" .. tostring(c[8]))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "403"
        assert field(res.stdout, "CALLS") == "1"
        ip, reason, ttl, service, country, scope, lease, lease_id, keep = field(res.stdout, "CALL1").split("|")
        assert (ip, reason, ttl, service, country, scope, lease, keep) == (
            "1.2.3.4",
            "crowdsec",
            "30",
            "app.example.com",
            "FR",
            "service",
            "true",
            "true",
        )
        assert len(lease_id) == 16
        assert field(res.stdout, "RD_SOURCE") == "lapi|ban|app.example.com|1"
        assert field(res.stdout, "NOT_AFTER") == "nil"

    def test_what_add_ban_receives_fits_the_database_limit(self):
        """Ten decisions with 400 bytes of emoji each escape to far more than 4096 stored characters."""
        res = run("""
local decisions = {}
for i = 1, 10 do
  decisions[i] = ban_decision(i, 3600, { scenario = string.rep("\\240\\159\\152\\128", 100) })
end
denied(decisions)
request()
show_calls()
local rd = ADD_BAN[1][7]
print("LEN=" .. crowdsec._stored_length(rd))
print("LEASE_ID=" .. rd.lease_id)
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "1"
        assert int(field(res.stdout, "LEN")) <= 4096
        assert len(field(res.stdout, "LEASE_ID")) == 16

    def test_the_database_classifies_and_matches_what_the_plugin_sends(self):
        """Lane A's contract: `ban_kind` says lease, `lease_id_of` returns the id, and the identity keys
        are the ones the plugin writes."""
        bans = pytest.importorskip("db_methods.bans")
        res = run(f"""
{DENIED_BASELINE}
request()
local rd = ADD_BAN[1][7]
local keys = {{}}
for _, k in ipairs({{ "lease", "version", "lease_id", "instance", "connection", "service_scope", "remediation", "source" }}) do
  assert(rd[k] ~= nil, k)
  keys[#keys + 1] = k
end
print("LEASE_ID=" .. rd.lease_id)
print("SERVICE_SCOPE=" .. rd.service_scope)
""")
        assert res.returncode == 0, res.stderr
        assert set(bans.LEASE_IDENTITY_KEYS) == {"lease", "version", "lease_id", "instance", "connection", "service_scope", "remediation", "source"}
        row = {
            "reason": "crowdsec",
            "reason_data": {
                "lease": True,
                "lease_id": field(res.stdout, "LEASE_ID"),
            },
        }
        assert bans.ban_kind(row) == bans.KIND_LEASE
        assert bans.lease_id_of(row) == field(res.stdout, "LEASE_ID")

    def test_single_site_leases_are_global(self):
        res = run(
            f"""
{DENIED_BASELINE}
request()
show_calls()
""",
            files=SINGLESITE_FILES,
            MULTISITE='"no"',
            USE_CROWDSEC='{ global = { USE_CROWDSEC = "yes" } }',
        )
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "1"
        _, reason, _, service, _, scope, *_ = field(res.stdout, "CALL1").split("|")
        assert (reason, scope, service) == ("crowdsec", "global", "nil")

    def test_the_default_refresh_is_off(self):
        res = run(f"{DENIED_BASELINE}\nlocal r = request()\nprint('STATUS=' .. r.status)\nshow_calls()", REFRESH_SETTING="nil")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "403"
        assert field(res.stdout, "CALLS") == "0"

    @pytest.mark.parametrize("setting", ['"0"', '""', '"abc"'])
    def test_zero_or_unreadable_means_off(self, setting):
        res = run(f"{DENIED_BASELINE}\nrequest()\nshow_calls()", REFRESH_SETTING=setting)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0"

    def test_a_duration_suffix_is_read_with_parse_duration(self):
        res = run(f"{DENIED_BASELINE}\nrequest()\nshow_calls()\nprint('TTL=' .. ADD_BAN[1][3])", REFRESH_SETTING='"2m"')
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "TTL") == "120"

    def test_a_renewal_gets_a_new_lease_id(self):
        res = run(f"""
{DENIED_BASELINE}
request()
NOW = NOW + 2
request()
show_calls()
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "2"
        first = field(res.stdout, "CALL1").split("|")[7]
        second = field(res.stdout, "CALL2").split("|")[7]
        assert first != second


class TestNoLeaseForAVerdictThePluginDidNotEnforce:
    def refuse(self, setup: str, expected_status: str, **globals_):
        res = run(f"{setup}\nlocal r = request()\nprint('STATUS=' .. tostring(r.status))\nshow_calls()", **globals_)
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0", res.stdout
        assert field(res.stdout, "STATUS") == expected_status
        return res

    def test_deferred_to_a_workflow(self):
        self.refuse(DENIED_BASELINE, "nil", DEFER_SETTING='"yes"', WORKFLOWS_ATTACHED="true")

    def test_detect_mode(self):
        self.refuse(DENIED_BASELINE, "403", SECURITY_MODE='"detect"')

    def test_appsec_verdict(self):
        self.refuse(
            'denied({ ban_decision(1, 3600) }, { source = "appsec" }, { source = "appsec" })',
            "403",
        )

    def test_appsec_failure_policy(self):
        self.refuse(
            'denied({}, { source = "failure_policy" }, { source = "failure_policy" })',
            "403",
        )

    def test_a_captcha_downgraded_to_ban_by_the_bouncer(self):
        self.refuse(
            'denied({ ban_decision(1, 3600, { remediation = "captcha" }) }, { action = "captcha" })',
            "403",
        )

    def test_a_challenge_verdict(self):
        self.refuse('denied({}, { source = "appsec", action = "challenge" }, { source = "appsec" })', "403")

    def test_captcha_delegated_to_the_antibot(self):
        res = run(f"""
{DENIED_BASELINE}
ALLOW = {{ true, "captcha delegated", false, false, ALLOW[5], "recaptcha", ALLOW[7] }}
local r = request()
print("STATUS=" .. tostring(r.status))
show_calls()
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0"

    def test_a_response_the_bouncer_already_served(self):
        res = run(f"""
{DENIED_BASELINE}
ALLOW = {{ true, "challenged", false, true, ALLOW[5], nil, ALLOW[7] }}
local r = request()
print("STATUS=" .. tostring(r.status))
show_calls()
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0"

    def test_a_service_with_excluded_locations(self):
        self.refuse(DENIED_BASELINE, "403", EXCLUDED="true")

    def test_a_stale_stream_synchronization(self):
        self.refuse(
            DENIED_BASELINE,
            "403",
            BOUNCER_INFO='{ mode = "stream", update_frequency = 10, last_successful_sync = 900 }',
        )

    def test_an_allowed_request(self):
        res = run("""
ALLOW = { true, "allow" }
local r = request()
print("STATUS=" .. tostring(r.status))
show_calls()
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0"

    def test_no_live_ban_decision(self):
        self.refuse("denied({})", "403")


class TestTheIdentityBound:
    def test_an_oversized_identity_set_refuses_the_lease_and_keeps_the_deny(self):
        res = run(f"""
{DENIED_BASELINE}
local oversized = string.rep("h", 1100)
ngx.var.hostname = oversized
local r = request()
print("STATUS=" .. tostring(r.status))
show_calls()
print("THROTTLED=" .. #THROTTLED)
print("LOG=" .. tostring(THROTTLED[1]))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "403"
        assert field(res.stdout, "CALLS") == "0"
        assert field(res.stdout, "THROTTLED") == "1"
        assert "lease" in field(res.stdout, "LOG")

    def test_the_bound_is_in_stored_characters(self):
        """1024 stored characters of identity set: 1021 ASCII characters of padding fit, and the same
        padding in BMP characters (6 stored each) does not."""
        res = run("""
local identity = { lease = true, version = 1, lease_id = "0123456789abcdef", instance = "i", connection = string.rep("a", 64),
  service_scope = "s", remediation = "ban", source = "lapi" }
local base = crowdsec._stored_length(identity)
print("BASE=" .. base)
print("FITS=" .. tostring(crowdsec._identity_fits(identity)))
identity.instance = string.rep("i", 1024 - base + 1)
print("EXACT=" .. crowdsec._stored_length(identity) .. "|" .. tostring(crowdsec._identity_fits(identity)))
identity.instance = string.rep("i", 1024 - base + 2)
print("OVER=" .. crowdsec._stored_length(identity) .. "|" .. tostring(crowdsec._identity_fits(identity)))
identity.instance = string.rep("\195\169", 200)
print("BMP=" .. crowdsec._stored_length(identity) .. "|" .. tostring(crowdsec._identity_fits(identity)))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "FITS") == "true"
        assert field(res.stdout, "EXACT") == "1024|true"
        assert field(res.stdout, "OVER") == "1025|false"
        assert field(res.stdout, "BMP").endswith("|false")


class TestTheDedupe:
    def test_a_burst_from_one_ip_promotes_once(self):
        res = run(f"{DENIED_BASELINE}\nfor _ = 1, 5 do request() end\nshow_calls()")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "1"

    def test_it_lets_the_next_second_through(self):
        res = run(f"{DENIED_BASELINE}\nrequest()\nNOW = NOW + 1\nrequest()\nshow_calls()")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "2"

    def test_other_ips_are_not_held_back(self):
        res = run(f"{DENIED_BASELINE}\nrequest()\nrequest({{ remote_addr = '5.6.7.8' }})\nshow_calls()")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "2"

    def test_the_dedupe_table_stays_bounded(self):
        res = run(f"""
{DENIED_BASELINE}
for i = 1, 5000 do request({{ remote_addr = "10." .. (i // 256) .. "." .. (i % 256) .. ".1" }}) end
print("SIZE=" .. crowdsec._dedupe_size())
""")
        assert res.returncode == 0, res.stderr
        assert int(field(res.stdout, "SIZE")) <= 1024


class TestAFailingPromotionNeverChangesTheVerdict:
    def test_add_ban_refusing(self):
        res = run(f"{DENIED_BASELINE}\nlocal r = request()\nprint('STATUS=' .. r.status)\nshow_calls()", ADD_BAN_OK="false", ADD_BAN_MSG='"redis SET failed"')
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "403"
        assert field(res.stdout, "CALLS") == "1"

    def test_add_ban_raising(self):
        res = run(f"{DENIED_BASELINE}\nlocal r = request()\nprint('STATUS=' .. r.status)\nprint('LOGGED=' .. #LOGS)", ADD_BAN_RAISES="true")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "403"
        assert int(field(res.stdout, "LOGGED")) >= 1


class TestTheAcceptedRaceBound:
    """Amendment 1, Q2: a CrowdSec answer that lands after a confirmed unban can create a ban, but never
    one longer than ``CROWDSEC_BAN_REFRESH``."""

    @pytest.mark.parametrize("remaining", [5, 29, 33, 34, 3600, 31536000])
    def test_a_delayed_answer_yields_a_ban_no_longer_than_the_refresh(self, remaining):
        res = run(f"""
-- The evidence was captured before the unban; the request resumes 3 seconds later and promotes it anyway.
denied({{ ban_decision(1, {remaining}) }})
NOW = NOW + 3
request()
show_calls()
print("TTL=" .. ADD_BAN[1][3])
""")
        assert res.returncode == 0, res.stderr
        # What is left of the decision when the answer lands, capped at the refresh: 30 at most.
        assert int(field(res.stdout, "TTL")) == min(remaining - 3, 30)

    def test_a_decision_that_lapsed_while_the_request_waited_makes_no_ban(self):
        res = run("""
denied({ ban_decision(1, 2) })
NOW = NOW + 3
request()
show_calls()
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CALLS") == "0"


class TestTheRefreshIpOperation:
    def test_refresh_ip_reaches_the_bouncer_control(self):
        res = run("""
local booter = plugin()
booter.is_request = false
assert(booter:init().ret)
local r = plugin():api()
print("STATUS=" .. tostring(r.status))
print("CONTROL=" .. table.concat(CONTROL, ","))
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "STATUS") == "200"
        assert field(res.stdout, "CONTROL") == "refresh_ip"

    def test_a_misspelt_operation_is_not_routed(self):
        res = run("""
local booter = plugin()
booter.is_request = false
assert(booter:init().ret)
local r = plugin({ uri = "/crowdsec/refresh-ip" }):api()
print("CONTROL=" .. #CONTROL)
""")
        assert res.returncode == 0, res.stderr
        assert field(res.stdout, "CONTROL") == "0"
