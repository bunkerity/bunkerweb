"""The CrowdSec 1.8 ``challenge`` remediation is relayed, and the three mines around it are gone.

Everything pinned here is invisible from the outside and every one of them failed in the direction
that serves traffic:

* the fallback guard in ``csmod.Allow`` must accept ``challenge``. It did not, so a CrowdSec 1.8
  bot-detection verdict fell through to ``FALLBACK_REMEDIATION`` -- ``ban`` in BunkerWeb's shipped
  template -- and every legitimate browser was denied instead of challenged. That is the whole
  point of the lane; upstream lua-cs-bouncer fixed it by widening that same condition (v1.0.18,
  ``lib/crowdsec.lua:895``).
* the challenge envelope must be served exactly as CrowdSec sent it (status, headers, cookies,
  body) with the origin never reached, or the operator gets a blank page and no explanation.
* a challenge verdict carrying no usable body must fall back to the configured remediation with an
  ERR line, never a silent 200 with an empty body.
* ``CROWDSEC_EXCLUDE_LOCATION``'s prefix arm must return. It logged and fell through, so the
  documented prefix form excluded nothing and the setting only ever worked as an exact match.
* the captcha branch must not end on a bare ``return``: ``crowdsec:access()`` concatenates the
  second return value into a message, so ``nil`` raised under ``helpers.lua``'s pcall and the
  dispatcher then served the request UNCHECKED.

Runs the *shipped* ``lib/bouncer.lua`` and ``lib/challenge.lua`` through the ``lua`` binary with
OpenResty stubbed, splicing the real function bodies the way ``test_instance_credential_lua.py``
does -- so narrowing any of these conditions in the plugin fails the extraction or the assertion
here rather than passing against a copy.

``cjson.decode`` is stubbed to hand back a table the test supplies: what is under test is the
branching on the decoded ``BodyResponse``, not cjson's parser.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LIB = ROOT / "src" / "common" / "core" / "crowdsec" / "lib"
BOUNCER_LUA = CROWDSEC_LIB / "bouncer.lua"
CHALLENGE_LUA = CROWDSEC_LIB / "challenge.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

SOURCE = BOUNCER_LUA.read_text(encoding="utf-8")


def real_local(name: str, source: str | None = None) -> str:
    body = re.search(rf"^local function {name}\(.*?^end$", source or SOURCE, re.M | re.S)
    assert body, f"{name}() is gone from {BOUNCER_LUA}"
    return body.group(0)


def real_csmod(name: str, source: str | None = None) -> str:
    body = re.search(rf"^function csmod\.{name}\(.*?^end$", source or SOURCE, re.M | re.S)
    assert body, f"csmod.{name}() is gone from {BOUNCER_LUA}"
    return body.group(0)


# Stubs for everything the spliced functions reach that is not the logic under test. `challenge` is
# NOT stubbed: the real lib/challenge.lua is loaded, so the envelope assertions exercise the shipped
# renderer.
HARNESS = """
local LOGS = {}
local PRINTED = {}
local CAPTURED = { headers = {} }

ngx = {
  ERR = "ERR", DEBUG = "DEBUG", ALERT = "ALERT", WARN = "WARN", NOTICE = "NOTICE",
  OK = 0, HTTP_OK = 200, HTTP_FORBIDDEN = 403, HTTP_GET = "GET",
  status = nil,
  log = function(level, msg) LOGS[#LOGS + 1] = level .. " " .. tostring(msg) end,
  print = function(b) PRINTED[#PRINTED + 1] = tostring(b) end,
  say = function(b) PRINTED[#PRINTED + 1] = tostring(b) .. "\\n" end,
  redirect = function(uri) error("ngx.redirect(" .. tostring(uri) .. ") must not be reached") end,
  var = { uri = URI, request_uri = URI, request_method = "GET", http_host = "app.example.com",
          http_user_agent = "Mozilla/5.0", http_content_length = nil, no_appsec = nil },
  req = {
    is_internal = function() return false end,
    http_version = function() return 1.1 end,
    read_body = function() end,
    get_body_data = function() return REQUEST_BODY end,
    get_body_file = function() return nil end,
    get_headers = function() return {} end,
    get_method = function() return "GET" end,
    get_post_args = function() return {} end,
    set_method = function() end,
  },
}
ngx.header = setmetatable({}, {
  __newindex = function(_, k, v) CAPTURED.headers[#CAPTURED.headers + 1] = { k, v } end,
  __index = function() return nil end,
})

-- module-level constants and helpers of bouncer.lua the spliced bodies close over
DENY = "deny"
APPSEC_API_KEY_HEADER = "x-crowdsec-appsec-api-key"
APPSEC_IP_HEADER = "x-crowdsec-appsec-ip"
APPSEC_HOST_HEADER = "x-crowdsec-appsec-host"
APPSEC_VERB_HEADER = "x-crowdsec-appsec-verb"
APPSEC_URI_HEADER = "x-crowdsec-appsec-uri"
APPSEC_USER_AGENT_HEADER = "x-crowdsec-appsec-user-agent"

bw_utils = { get_variable = function() return "100" end }
bit = { bor = function(a, b) return a + b end }
cjson = { decode = function() if APPSEC_JSON == nil then error("not json") end return APPSEC_JSON end }

flag = {
  BOUNCER_SOURCE = 1, APPSEC_SOURCE = 2,
  VERIFY_STATE = 4, VALIDATED_STATE = 8,
  Flags = { [1] = "bouncer", [2] = "appsec" },
  GetFlags = function(flags)
    if flags == nil then return nil, nil, nil end
    local source = flags % 4
    return source, flags - source, nil
  end,
}

utils = {
  table_len = function(t) local n = 0 for _ in pairs(t) do n = n + 1 end return n end,
  ends_with = function(s, suffix) return s:sub(-#suffix) == suffix end,
  starts_with = function(s, prefix) return s:sub(1, #prefix) == prefix end,
}

local CACHE = CACHE_CONTENT
runtime = {
  conf = CONF,
  fallback = CONF["FALLBACK_REMEDIATION"],
  cache = {
    get = function(_, key)
      local entry = CACHE[key]
      if entry == nil then return nil end
      if type(entry) == "table" then return entry[1], entry[2] end
      return entry
    end,
    set = function(_, key, value, _exp, flags) CACHE[key] = { value, flags } return true end,
    delete = function(_, key) CACHE[key] = nil end,
  },
}

challenge = assert(loadfile(CHALLENGE_PATH))()

csmod = {}
csmod.allowIp = function() ALLOWIP_CALLS = ALLOWIP_CALLS + 1 return ALLOWIP_OK, ALLOWIP_REMEDIATION, nil, ALLOWIP_DECISION end
csmod.GetCaptchaTemplate = function() return "<captcha/>" end
csmod.GetCaptchaBackendKey = function() return "g-recaptcha-response" end
csmod.validateCaptcha = function() return false, nil end
http = { new = function()
  return {
    set_timeouts = function() end,
    close = function() end,
    request_uri = function(_, _, opts)
      APPSEC_SENT = opts
      return APPSEC_HTTP_RESPONSE, APPSEC_HTTP_ERR
    end,
  }
end }

--@@GET_BODY@@

--@@APPSEC_CHECK@@

--@@ALLOW@@

function dump()
  print("STATUS=" .. tostring(ngx.status))
  print("BODY=" .. table.concat(PRINTED, ""))
  for _, h in ipairs(CAPTURED.headers) do
    if type(h[2]) == "table" then
      print("HEADER=" .. h[1] .. "=[" .. table.concat(h[2], "||") .. "]")
    else
      print("HEADER=" .. h[1] .. "=" .. tostring(h[2]))
    end
  end
  for _, line in ipairs(LOGS) do print("LOG=" .. line) end
  print("ALLOWIP_CALLS=" .. tostring(ALLOWIP_CALLS))
  print("SENT_METHOD=" .. tostring(APPSEC_SENT and APPSEC_SENT.method or nil))
  print("SENT_BODY=" .. tostring(APPSEC_SENT and APPSEC_SENT.body or nil))
end

--@@BODY@@
"""

DEFAULT_CONF = {
    "ENABLED": "true",
    "ENABLE_INTERNAL": "false",
    "EXCLUDE_LOCATION": [],
    "FALLBACK_REMEDIATION": "ban",
    "ALWAYS_SEND_TO_APPSEC": False,
    "APPSEC_ENABLED": True,
    "APPSEC_URL": "http://127.0.0.1:7422",
    "APPSEC_HOST": "127.0.0.1:7422",
    "APPSEC_FAILURE_ACTION": "passthrough",
    "APPSEC_CONNECT_TIMEOUT": 100,
    "APPSEC_SEND_TIMEOUT": 100,
    "APPSEC_PROCESS_TIMEOUT": 500,
    "API_KEY": "key",
    "SSL_VERIFY": False,
    "CAPTCHA_EXPIRATION": 3600,
}

CHALLENGE_BODY = "<html><body>solve me</body></html>"
CHALLENGE_JSON = {
    "action": "challenge",
    "http_status": 200,
    "user_body_content": CHALLENGE_BODY,
    "user_headers": {"Content-Type": ["text/html"], "Content-Security-Policy": ["default-src 'self'"]},
    "user_cookies": ["cs_challenge=abc123; Path=/; HttpOnly"],
}


# `None` is a meaningful value for `appsec_json` (it makes the cjson stub raise), so the
# "caller said nothing" case needs a sentinel of its own.
_DEFAULT = object()


def to_lua(value) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return "[==[" + value + "]==]"
    if isinstance(value, list):
        return "{" + ", ".join(to_lua(v) for v in value) + "}"
    if isinstance(value, dict):
        # the spaces inside the brackets matter: `[[==[k]==]]` would lex as a long bracket
        return "{" + ", ".join(f"[ {to_lua(k)} ] = {to_lua(v)}" for k, v in value.items()) + "}"
    raise TypeError(value)


def run(
    body: str,
    *,
    source: str | None = None,
    uri: str = "/",
    conf: dict | None = None,
    appsec_json: dict | None = _DEFAULT,
    appsec_status: int = 403,
    appsec_err: str | None = None,
    allowip_ok: bool = True,
    allowip_remediation: str | None = None,
    cache: dict | None = None,
    request_body: str | None = None,
    antibot_provider: str | None = None,
    allowip_decision: dict | None = None,
):
    src = source if source is not None else SOURCE
    full_conf = dict(DEFAULT_CONF)
    full_conf.update(conf or {})
    http_response = "nil" if appsec_err is not None else "{ status = " + str(appsec_status) + ", body = [==[{}]==] }"

    preamble = "\n".join(
        [
            f"URI = {to_lua(uri)}",
            f"CONF = {to_lua(full_conf)}",
            f"CACHE_CONTENT = {to_lua(cache or {})}",
            f"CHALLENGE_PATH = {to_lua(str(CHALLENGE_LUA))}",
            f"APPSEC_JSON = {to_lua(CHALLENGE_JSON if appsec_json is _DEFAULT else appsec_json)}",
            f"APPSEC_HTTP_RESPONSE = {http_response}",
            f"APPSEC_HTTP_ERR = {to_lua(appsec_err)}",
            f"REQUEST_BODY = {to_lua(request_body)}",
            f"ALLOWIP_OK = {to_lua(allowip_ok)}",
            f"ALLOWIP_REMEDIATION = {to_lua(allowip_remediation)}",
            f"ALLOWIP_DECISION = {to_lua(allowip_decision)}",
            f"ANTIBOT_PROVIDER = {to_lua(antibot_provider)}",
            "ALLOWIP_CALLS = 0",
            "APPSEC_SENT = nil",
        ]
    )
    script = (
        preamble
        + "\n"
        + HARNESS.replace("--@@GET_BODY@@", real_local("get_body", src))
        .replace("--@@APPSEC_CHECK@@", real_csmod("AppSecCheck", src))
        .replace("--@@ALLOW@@", real_csmod("Allow", src))
        .replace("--@@BODY@@", body)
    )
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


ALLOW = """
local ok, msg, banned, served = csmod.Allow("1.2.3.4")
print("RET=" .. tostring(ok) .. "|" .. tostring(msg) .. "|" .. tostring(banned) .. "|" .. tostring(served))
dump()
"""

NO_RENDER = """
local ok, msg, banned, served = csmod.Allow("1.2.3.4", true)
print("RET=" .. tostring(ok) .. "|" .. tostring(msg) .. "|" .. tostring(banned) .. "|" .. tostring(served))
dump()
"""

DELEGATE = """
local ok, msg, banned, served, verdict, provider = csmod.Allow("1.2.3.4", nil, ANTIBOT_PROVIDER)
print("RET=" .. tostring(ok) .. "|" .. tostring(msg) .. "|" .. tostring(banned) .. "|" .. tostring(served))
print("PROVIDER=" .. tostring(provider))
print("VERDICT=" .. tostring(verdict and verdict.source) .. "|" .. tostring(verdict and verdict.action) ..
      "|" .. tostring(verdict and verdict.scenario))
dump()
"""

DELEGATE_NO_RENDER = """
local ok, msg, banned, served, verdict, provider = csmod.Allow("1.2.3.4", true, ANTIBOT_PROVIDER)
print("RET=" .. tostring(ok) .. "|" .. tostring(msg) .. "|" .. tostring(banned) .. "|" .. tostring(served))
print("PROVIDER=" .. tostring(provider))
print("VERDICT=" .. tostring(verdict and verdict.source) .. "|" .. tostring(verdict and verdict.action) ..
      "|" .. tostring(verdict and verdict.scenario))
dump()
"""

CHECK = """
local ok, remediation, status, resp, err = csmod.AppSecCheck("1.2.3.4")
print("CHECK=" .. tostring(ok) .. "|" .. tostring(remediation) .. "|" .. tostring(status) .. "|" ..
      tostring(resp ~= nil and resp.body or nil) .. "|" .. tostring(err))
dump()
"""


def field(out: str, key: str) -> str:
    for line in out.splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1]
    raise AssertionError(f"{key} missing from:\n{out}")


def fields(out: str, key: str) -> list:
    return [line.split("=", 1)[1] for line in out.splitlines() if line.startswith(key + "=")]


class TestChallengeIsRelayed:
    def test_a_challenge_verdict_serves_the_crowdsec_page(self):
        out = run(ALLOW)
        assert field(out, "RET") == "true|challenged|false|true"
        assert field(out, "BODY") == CHALLENGE_BODY
        assert field(out, "STATUS") == "200"

    def test_the_guard_is_what_makes_it_work(self):
        """Mutation: drop `challenge` from the fallback guard and the browser is banned instead."""
        mutated = SOURCE.replace(
            'if remediation ~= "captcha" and remediation ~= "ban" and remediation ~= "challenge" then',
            'if remediation ~= "captcha" and remediation ~= "ban" then',
        )
        assert mutated != SOURCE, "the guard no longer reads as expected -- update this mutation"
        out = run(ALLOW, source=mutated)
        assert field(out, "RET") == "true|denied|true|nil"
        assert field(out, "BODY") == ""

    def test_the_log_line_names_the_remediation_source(self):
        """An operator seeing a challenge body must be able to tell where it came from."""
        logs = fields(run(ALLOW), "LOG")
        assert any("appsec challenge" in line and "1.2.3.4" in line for line in logs), logs

    def test_the_origin_is_not_reached(self):
        """`served` is what stops crowdsec:access() returning a deny status or falling through."""
        assert field(run(ALLOW), "RET").endswith("|false|true")


class TestChallengeEnvelope:
    def test_the_status_comes_from_the_appsec_payload(self):
        out = run(ALLOW, appsec_json=dict(CHALLENGE_JSON, http_status=307))
        assert field(out, "STATUS") == "307"

    def test_a_single_valued_header_is_flattened_to_a_scalar(self):
        headers = fields(run(ALLOW), "HEADER")
        assert "Content-Type=text/html" in headers, headers
        assert "Content-Security-Policy=default-src 'self'" in headers, headers

    def test_a_multi_valued_header_stays_a_list(self):
        out = run(ALLOW, appsec_json=dict(CHALLENGE_JSON, user_headers={"Vary": ["Cookie", "Accept-Encoding"]}))
        assert "Vary=[Cookie||Accept-Encoding]" in fields(out, "HEADER")

    def test_the_challenge_cookie_is_set(self):
        headers = fields(run(ALLOW), "HEADER")
        assert "Set-Cookie=cs_challenge=abc123; Path=/; HttpOnly" in headers, headers

    def test_several_cookies_stay_a_list(self):
        out = run(ALLOW, appsec_json=dict(CHALLENGE_JSON, user_cookies=["a=1; Path=/", "b=2; Path=/"]))
        assert "Set-Cookie=[a=1; Path=/||b=2; Path=/]" in fields(out, "HEADER")

    def test_an_envelope_without_cookies_or_headers_still_serves_the_body(self):
        out = run(ALLOW, appsec_json={"action": "challenge", "http_status": 200, "user_body_content": CHALLENGE_BODY})
        assert field(out, "BODY") == CHALLENGE_BODY
        assert field(out, "RET") == "true|challenged|false|true"


class TestMalformedChallengeNeverFailsOpen:
    def test_a_challenge_without_a_body_falls_back_to_the_configured_remediation(self):
        out = run(ALLOW, appsec_json={"action": "challenge", "http_status": 200})
        assert field(out, "RET") == "true|denied|true|nil"
        assert field(out, "BODY") == ""
        assert any("carried no challenge body" in line for line in fields(out, "LOG"))

    def test_an_empty_body_is_treated_as_missing(self):
        out = run(ALLOW, appsec_json=dict(CHALLENGE_JSON, user_body_content=""))
        assert field(out, "RET") == "true|denied|true|nil"

    def test_a_body_that_is_not_a_string_is_treated_as_missing(self):
        out = run(ALLOW, appsec_json=dict(CHALLENGE_JSON, user_body_content=42))
        assert field(out, "RET") == "true|denied|true|nil"

    def test_the_floor_is_ban_even_when_the_operator_configured_captcha(self):
        """`captcha` is a valid FALLBACK_REMEDIATION (lib/config.lua). Honouring it here would
        fall through every arm -- captcha_ok is false in BunkerWeb -- to `return true, "allow"`,
        i.e. a fail-open inside the branch that exists to prevent one."""
        out = run(
            ALLOW,
            conf={"FALLBACK_REMEDIATION": "captcha"},
            appsec_json={"action": "challenge", "http_status": 200},
        )
        assert field(out, "RET") == "true|denied|true|nil"
        assert field(out, "BODY") == ""


class TestAppSecCheckReturnsTheEnvelope:
    """The 4th return value is the whole plumbing change in AppSecCheck (upstream v1.0.18)."""

    def test_a_challenge_403_carries_body_headers_and_cookies(self):
        assert field(run(CHECK), "CHECK") == "false|challenge|200|" + CHALLENGE_BODY + "|nil"

    def test_a_ban_403_carries_no_envelope(self):
        out = run(CHECK, appsec_json={"action": "ban", "http_status": 403})
        assert field(out, "CHECK") == "false|ban|403|nil|nil"

    def test_a_transport_error_keeps_err_in_the_fifth_slot(self):
        """It used to be the fourth: a caller reading position 4 would take the error for a body."""
        out = run(CHECK, appsec_err="connection refused")
        assert field(out, "CHECK") == "true|allow|200|nil|connection refused"

    def test_a_200_is_an_allow(self):
        assert field(run(CHECK, appsec_status=200), "CHECK") == "true|allow|200|nil|nil"

    def test_an_unparsable_403_body_falls_back_instead_of_raising(self):
        """It used to raise out of AppSecCheck, through Allow, into helpers.lua's pcall -- which
        logs an ERR and serves the request UNCHECKED. CrowdSec 1.8 adds new 403 shapes."""
        out = run(CHECK, appsec_json=None)
        assert field(out, "CHECK") == "false|ban|403|nil|nil"
        assert any("Unparsable AppSec response body" in line for line in fields(out, "LOG"))

    def test_a_post_body_is_forwarded_to_appsec(self):
        """claim 4.19: the /submit POST must reach AppSec or the challenge can never be solved."""
        out = run(CHECK, request_body="answer=42")
        assert field(out, "SENT_METHOD") == "POST"
        assert field(out, "SENT_BODY") == "answer=42"


class TestExcludeLocationPrefixArm:
    def test_a_prefix_entry_excludes_the_subtree(self):
        out = run(ALLOW, uri="/api/v1/things", conf={"EXCLUDE_LOCATION": ["/api"]})
        assert field(out, "RET") == "true|whitelisted /api/|nil|nil"
        assert field(out, "ALLOWIP_CALLS") == "0"

    def test_the_prefix_arm_is_what_does_it(self):
        """Mutation: drop the `return` and the prefix entry stops excluding anything."""
        mutated = SOURCE.replace(
            '        ngx.log(ngx.ERR,  "whitelisted location: " .. uri_to_check)\n' '        return true, "whitelisted " .. uri_to_check\n',
            '        ngx.log(ngx.ERR,  "whitelisted location: " .. uri_to_check)\n',
        )
        assert mutated != SOURCE, "the prefix arm no longer reads as expected -- update this mutation"
        out = run(ALLOW, source=mutated, uri="/api/v1/things", conf={"EXCLUDE_LOCATION": ["/api"]})
        assert field(out, "RET") == "true|challenged|false|true"
        assert field(out, "ALLOWIP_CALLS") == "1"

    def test_the_exact_arm_still_works(self):
        out = run(ALLOW, uri="/api", conf={"EXCLUDE_LOCATION": ["/api"]})
        assert field(out, "RET") == "true|whitelisted /api|nil|nil"

    def test_a_sibling_path_is_not_excluded(self):
        """`/api` must not exclude `/apidocs`: the arm appends a slash before comparing."""
        out = run(ALLOW, uri="/apidocs", conf={"EXCLUDE_LOCATION": ["/api"]})
        assert field(out, "RET") == "true|challenged|false|true"

    def test_excluding_the_challenge_paths_disables_the_challenge(self):
        """claim 5.5: this is the documented footgun, pinned so the docs stay true."""
        out = run(ALLOW, uri="/crowdsec-internal/challenge/challenge.js", conf={"EXCLUDE_LOCATION": ["/crowdsec-internal"]})
        assert field(out, "RET").startswith("true|whitelisted /crowdsec-internal/")
        assert field(out, "ALLOWIP_CALLS") == "0"


class TestCaptchaBranchNoLongerReturnsNil:
    """The captcha branch is dead in BunkerWeb (no CAPTCHA_PROVIDER), but its bare `return` was a
    fail-open mine: crowdsec:access() concatenated the nil message and raised under the pcall."""

    CONF = {"FALLBACK_REMEDIATION": "captcha"}
    CACHE = {"captcha_ok": True}

    def test_the_captcha_page_is_reported_as_served(self):
        out = run(ALLOW, conf=self.CONF, cache=self.CACHE, appsec_json={"action": "captcha", "http_status": 403})
        assert field(out, "RET") == "true|CrowdSec captcha served|false|true"
        assert field(out, "BODY") == "<captcha/>"

    def test_a_validated_appsec_captcha_is_not_re_served(self):
        """The infinite loop upstream fixed in v1.0.18: the state now counts per source."""
        cache = dict(self.CACHE)
        cache["captcha_1.2.3.4"] = ["/previous", 10]  # VALIDATED_STATE(8) | APPSEC_SOURCE(2)
        out = run(ALLOW, conf=self.CONF, cache=cache, appsec_json={"action": "captcha", "http_status": 403})
        assert field(out, "RET") == "true|allow|nil|nil"
        assert field(out, "BODY") == ""

    def test_the_loop_fix_is_what_does_it(self):
        """Mutation: restore the pre-v1.0.18 condition and the captcha is re-served forever."""
        mutated = SOURCE.replace(
            "or source ~= remediationSource then",
            "or remediationSource == flag.APPSEC_SOURCE then",
        )
        assert mutated != SOURCE, "the loop guard no longer reads as expected -- update this mutation"
        cache = dict(self.CACHE)
        cache["captcha_1.2.3.4"] = ["/previous", 10]
        out = run(ALLOW, source=mutated, conf=self.CONF, cache=cache, appsec_json={"action": "captcha", "http_status": 403})
        assert field(out, "RET") == "true|CrowdSec captcha served|false|true"

    def test_the_appsec_state_survives_an_ip_with_no_lapi_decision(self):
        """Second half of the same upstream fix: wiping the state every request re-served the
        captcha forever no matter what the :748 condition said."""
        mutated = SOURCE.replace(
            '    local _, cached_flags = runtime.cache:get("captcha_" .. ip)\n'
            "    local cached_source = flag.GetFlags(cached_flags)\n"
            "    if cached_source ~= flag.APPSEC_SOURCE then\n"
            '      runtime.cache:delete("captcha_" .. ip)\n'
            "    end\n",
            '    runtime.cache:delete("captcha_" .. ip)\n',
        )
        assert mutated != SOURCE, "the cache-delete guard no longer reads as expected -- update this mutation"
        cache = dict(self.CACHE)
        cache["captcha_1.2.3.4"] = ["/previous", 10]
        out = run(ALLOW, source=mutated, conf=self.CONF, cache=cache, appsec_json={"action": "captcha", "http_status": 403})
        assert field(out, "RET") == "true|CrowdSec captcha served|false|true"

    def test_a_validated_lapi_captcha_does_not_excuse_an_appsec_one(self):
        """The other half of the same condition: a validated state only counts for its source."""
        cache = dict(self.CACHE)
        cache["captcha_1.2.3.4"] = ["/previous", 9]  # VALIDATED_STATE(8) | BOUNCER_SOURCE(1)
        out = run(ALLOW, conf=self.CONF, cache=cache, appsec_json={"action": "captcha", "http_status": 403})
        assert field(out, "RET") == "true|CrowdSec captcha served|false|true"


class TestNoRenderNeverWritesABody:
    """Two callers pass it, for the same reason. crowdsec:api()'s /crowdsec/ping reuses Allow() on
    the live request, so rendering would splice the challenge page into the API's JSON answer; and
    SECURITY_MODE=detect must not block, which a written body does regardless of what status the
    plugin returns -- the dispatcher can drop a deny status, it cannot un-send a page."""

    def test_a_challenge_is_reported_instead_of_rendered(self):
        out = run(NO_RENDER)
        assert field(out, "BODY") == ""
        assert field(out, "RET") == "true|not rendered, remediation was 'challenge'|true|nil"

    def test_the_third_value_is_truthy_so_the_caller_still_records_a_reason(self):
        """`banned` is what crowdsec:access() turns into get_deny_status(); in detect mode the
        dispatcher then records the reason and lets the request through."""
        out = run(NO_RENDER, appsec_json={"action": "ban", "http_status": 403})
        assert field(out, "RET") == "true|not rendered, remediation was 'ban'|true|nil"
        assert field(out, "BODY") == ""

    def test_a_captcha_is_not_rendered_either(self):
        out = run(
            NO_RENDER,
            conf={"FALLBACK_REMEDIATION": "captcha"},
            cache={"captcha_ok": True},
            appsec_json={"action": "captcha", "http_status": 403},
        )
        assert field(out, "BODY") == ""
        assert field(out, "RET") == "true|not rendered, remediation was 'captcha'|true|nil"

    def test_an_allowed_request_is_untouched(self):
        """Suppression must not turn a clean request into a reported one."""
        out = run(NO_RENDER, appsec_status=200)
        assert field(out, "RET") == "true|allow|nil|nil"
        assert field(out, "BODY") == ""

    def test_the_guard_is_what_stops_the_write(self):
        """Mutation: remove the suppression and detect mode silently serves the challenge."""
        mutated = SOURCE.replace(
            "  if no_render and not ok then\n"
            "    return true,\n"
            '      "not rendered, remediation was \'" .. tostring(remediation) .. "\'",\n'
            '      remediation ~= "allow",\n'
            "      nil,\n"
            "      verdict\n"
            "  end\n",
            "",
        )
        assert mutated != SOURCE, "the suppression guard no longer reads as expected -- update this mutation"
        out = run(NO_RENDER, source=mutated)
        assert field(out, "BODY") == CHALLENGE_BODY


# The AppSec answer for a `captcha` verdict: same envelope as a challenge, different action, and no
# page of its own -- CrowdSec expects the bouncer to render one.
CAPTCHA_JSON = {"action": "captcha", "http_status": 403}

# A LAPI `captcha` decision. `csmod.allowIp` hands the decision back as its fourth value, which is
# what puts the scenario into the verdict -- the only thing that tells an operator reading Reports
# WHY the visitor was challenged.
# `captcha_ok` is what `captcha.New()` wrote at init. It is FALSE in every BunkerWeb deployment --
# there is no SITE_KEY / SECRET_KEY setting to give it -- and that is the whole reason upstream's
# captcha branch is dead here. Spelled out in every case below because leaving it unset would test
# a configuration BunkerWeb cannot produce.
NO_CROWDSEC_CAPTCHA = {"captcha_ok": False}

LAPI_CAPTCHA = {
    "allowip_ok": False,
    "allowip_remediation": "captcha",
    "allowip_decision": {"scenario": "crowdsecurity/http-probing", "origin": "CAPI", "duration": "4h"},
    "cache": NO_CROWDSEC_CAPTCHA,
}


class TestCaptchaIsDelegatedToTheBunkerWebAntibot:
    """A `captcha` remediation is rendered by BunkerWeb's own antibot, not by CrowdSec's template.

    BunkerWeb exposes no SITE_KEY / SECRET_KEY, so `captcha.New()` fails at init and `captcha_ok` is
    false on every request. That leaves upstream's captcha branch permanently dead: before this, a
    `captcha` decision was silently rewritten into FALLBACK_REMEDIATION -- `ban` in the shipped
    template -- and a visitor CrowdSec wanted to *challenge* was blocked outright instead.
    """

    def test_a_lapi_captcha_decision_is_handed_to_the_antibot(self):
        out = run(DELEGATE, antibot_provider="captcha", **LAPI_CAPTCHA)
        assert field(out, "RET") == "true|captcha delegated to the BunkerWeb antibot|false|false"
        assert field(out, "PROVIDER") == "captcha"
        assert field(out, "BODY") == "", "nothing may be written: the antibot renders the challenge"

    def test_the_verdict_carries_the_decision_behind_the_challenge(self):
        """`crowdsec:access()` records this as the report reason before the antibot answers, so the
        Reports row names the scenario instead of reading as a bare antibot challenge."""
        out = run(DELEGATE, antibot_provider="captcha", **LAPI_CAPTCHA)
        assert field(out, "VERDICT") == "lapi|captcha|crowdsecurity/http-probing"

    def test_an_appsec_captcha_verdict_is_delegated_too(self):
        out = run(DELEGATE, antibot_provider="javascript", appsec_json=CAPTCHA_JSON, cache=NO_CROWDSEC_CAPTCHA)
        assert field(out, "RET") == "true|captcha delegated to the BunkerWeb antibot|false|false"
        assert field(out, "PROVIDER") == "javascript"
        assert field(out, "VERDICT") == "appsec|captcha|nil"

    def test_the_log_line_names_the_provider_and_the_source(self):
        """An operator seeing an antibot challenge on a service with USE_ANTIBOT=no needs one line
        saying CrowdSec asked for it, with which provider and from which source."""
        logs = fields(run(DELEGATE, antibot_provider="captcha", **LAPI_CAPTCHA), "LOG")
        assert any("BunkerWeb antibot" in line and "'captcha'" in line and "1.2.3.4" in line and "bouncer" in line for line in logs), logs


class TestDelegationIsScopedToCaptcha:
    def test_a_ban_decision_is_still_a_ban(self):
        """The flag is set on `captcha` only. A `ban` that started rendering a challenge would turn
        every blocked attacker into a challenged visitor -- and CS-C3's guards read the recorded
        remediation, so it would also stop being reported to BunkerNet."""
        out = run(
            DELEGATE,
            antibot_provider="captcha",
            allowip_ok=False,
            allowip_remediation="ban",
            cache=NO_CROWDSEC_CAPTCHA,
        )
        assert field(out, "RET") == "true|denied|true|nil"
        assert field(out, "PROVIDER") == "nil"

    def test_an_appsec_challenge_is_still_served_by_crowdsec(self):
        """CrowdSec 1.8 bot detection ships its own page (lane CS-A); only `captcha` has no page."""
        out = run(DELEGATE, antibot_provider="captcha", cache=NO_CROWDSEC_CAPTCHA)
        assert field(out, "RET") == "true|challenged|false|true"
        assert field(out, "PROVIDER") == "nil"
        assert field(out, "BODY") == CHALLENGE_BODY

    def test_an_allowed_ip_is_still_allowed(self):
        out = run(
            DELEGATE,
            antibot_provider="captcha",
            conf={"APPSEC_ENABLED": False},
            cache=NO_CROWDSEC_CAPTCHA,
        )
        assert field(out, "RET") == "true|allow|nil|nil"
        assert field(out, "PROVIDER") == "nil"

    @pytest.mark.parametrize("provider", [None, "no", ""])
    def test_without_the_setting_a_captcha_is_downgraded_to_a_ban_exactly_as_before(self, provider):
        """`CROWDSEC_CAPTCHA_PROVIDER=no` is the documented opt-out and has to reproduce the old
        behaviour byte for byte, or the upgrade note is a lie."""
        out = run(DELEGATE, antibot_provider=provider, **LAPI_CAPTCHA)
        assert field(out, "RET") == "true|denied|true|nil"
        assert field(out, "PROVIDER") == "nil"

    def test_the_opt_out_bans_even_when_the_captcha_state_key_is_missing(self):
        """`captcha_ok` is nil, not false, when the key is absent from the shared dict -- an
        eviction, or a worker that started before init wrote it. Upstream compared it with
        `== false`, so the fallback did not fire, every arm below missed and the request fell out
        to `return true, "allow"`: **served**, on a decision that asked for a captcha. Only AppSec
        could reach that before; `BOUNCING_ON_TYPE=all` routes every LAPI captcha decision into it.
        """
        missing = dict(LAPI_CAPTCHA, cache={})
        out = run(DELEGATE, antibot_provider="no", **missing)
        assert field(out, "RET") == "true|denied|true|nil", "fail-open: the visitor was served"

    def test_the_delegation_is_unaffected_by_the_missing_state_key(self):
        out = run(DELEGATE, antibot_provider="captcha", **dict(LAPI_CAPTCHA, cache={}))
        assert field(out, "PROVIDER") == "captcha"


class TestDetectModeNeverChallenges:
    def test_a_delegated_captcha_is_recorded_and_not_rendered(self):
        """SECURITY_MODE=detect and the /crowdsec/ping probe both pass `no_render`. A challenge
        rendered there would replace the origin's response -- detect silently blocking."""
        out = run(DELEGATE_NO_RENDER, antibot_provider="captcha", **LAPI_CAPTCHA)
        assert field(out, "RET").startswith("true|not rendered, remediation was 'captcha'|true|")
        assert field(out, "PROVIDER") == "nil", "the flag must not be set: the antibot would render"
        assert field(out, "VERDICT") == "lapi|captcha|crowdsecurity/http-probing"
        assert field(out, "BODY") == ""


class TestTheTwoGuardsAreWhatMakeItWork:
    def test_the_fallback_exemption_is_what_keeps_the_captcha_alive(self):
        """Mutation: let the fallback rewrite a delegated captcha and the decision becomes a ban
        again before anything downstream can see it. Mutates the spliced copy, never the file."""
        mutated = SOURCE.replace(
            'if remediation == "captcha" and not captcha_ok and not delegate_captcha then',
            'if remediation == "captcha" and not captcha_ok then',
        )
        assert mutated != SOURCE, "the fallback guard no longer reads as expected -- update this mutation"
        out = run(DELEGATE, source=mutated, antibot_provider="captcha", **LAPI_CAPTCHA)
        assert field(out, "RET") == "true|denied|true|nil"

    def test_removing_the_delegation_arm_fails_the_request_open(self):
        """Mutation: drop the arm and the request falls past the (dead) captcha branch, out of
        `if not ok`, into `return true, "allow"` -- CrowdSec asked for a captcha and the visitor is
        served. That fail-open is why the arm is first."""
        mutated = re.sub(
            r"\n      if delegate_captcha and remediation == \"captcha\" then\n.*?\n      end\n",
            "\n",
            SOURCE,
            flags=re.S,
        )
        assert mutated != SOURCE, "the delegation arm no longer reads as expected -- update this mutation"
        assert "delegated to the BunkerWeb antibot" not in mutated
        out = run(DELEGATE, source=mutated, antibot_provider="captcha", **LAPI_CAPTCHA)
        assert field(out, "RET") == "true|allow|nil|nil"
