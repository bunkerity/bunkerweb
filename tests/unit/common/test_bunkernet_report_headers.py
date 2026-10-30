"""A BunkerNet report carries only the allowlisted request headers.

``bunkernet:log()`` pushes one JSON report per blocked client onto ``plugin_bunkernet_reports``.
Its ``headers`` field is what ``ngx.req.get_headers`` returns once filtered through the plugin's
allowlist: ``cookie``, ``authorization`` and any custom token header never leave the instance.
The real ``bunkernet.lua`` runs under plain ``lua`` with OpenResty stubbed at its boundary; the
test decodes the payload pushed to the shared dict, so an assertion is about what would be sent.
"""

import json

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

from _lua_core_helpers import ROOT, module_path  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("BUNKERNET", ROOT / "src" / "common" / "core" / "bunkernet" / "bunkernet.lua")
IP = "203.0.113.5"

STUBS = r"""
REPORTS, GET_HEADERS_MAX = {}, nil

ngx = {
    ERR = "ERR", WARN = "WARN", NOTICE = "NOTICE", INFO = "INFO",
    HTTP_OK = 200, HTTP_INTERNAL_SERVER_ERROR = 500,
    var = {},
    get_phase = function() return "log" end,
    time = function() return 1000000 end,
    req = {
        -- Like the real call: lowercase keys, and a lookup that normalizes case and underscores.
        get_headers = function(max)
            GET_HEADERS_MAX = max
            local out = setmetatable({}, { __index = function(t, k)
                if type(k) == "string" then return rawget(t, k:lower():gsub("_", "-")) end
            end })
            for name, value in pairs(HEADERS) do rawset(out, name:lower(), value) end
            return out
        end,
    },
}

package.loaded["cjson"] = { encode = json_encode, decode = json_decode }
package.loaded["middleclass"] = function(name, parent)
    local klass = { name = name }
    klass.__index = klass
    setmetatable(klass, { __index = parent })
    return klass
end
package.loaded["resty.http"] = { new = function() return nil, "stub" end }
package.loaded["bunkerweb.plugin"] = {
    initialize = function(self, name, ctx)
        self.ctx = ctx
        self.variables = { USE_BUNKERNET = "yes" }
        self.is_loading = false
        self.is_request = true
        self.logger = { log = function() end }
        self.internalstore = { get = function() return "instance-id" end }
        self.datastore = {
            get = function() return nil, "not found" end,
            set_with_retries = function() return true end,
            dict = { rpush = function(_, key, value) REPORTS[#REPORTS + 1] = { key = key, value = value } return 1 end },
        }
    end,
    ret = function(_, ok, msg) return { ret = ok, msg = msg } end,
}
package.loaded["bunkerweb.utils"] = {
    get_version = function() return "1.6" end,
    get_integration = function() return "docker" end,
    get_deny_status = function() return 403 end,
    is_ipv4 = function() return true end,
    is_ipv6 = function() return false end,
    ip_is_global = function() return true end,
    has_variable = function() return true end,
    is_whitelisted = function() return false end,
    is_ip_in_networks = function() return false end,
    get_reason = function() return "blacklist", { id = "ua", ua = "curl" } end,
    get_variable = function() return nil, "unset" end,
}

local bunkernet = dofile(MODULE)
local ctx = { bw = CTX }
local instance = setmetatable({}, bunkernet)
bunkernet.initialize(instance, ctx)
local result = instance[LOG_METHOD](instance)
local report = REPORTS[1] and package.loaded["cjson"].decode(REPORTS[1].value)
emit({ ret = result.ret, msg = result.msg, key = REPORTS[1] and REPORTS[1].key, report = report, max = GET_HEADERS_MAX })
"""


def send(headers, *, kind="http"):
    ctx = {
        "kind": kind,
        "remote_addr": IP,
        "ip_is_global": True,
        "request_method": "POST",
        "request_uri": "/login?next=%2Fadmin",
        "server_name": "www.example.com",
    }
    script = (
        BASE_LUA.replace("function emit(v)", "json_encode, json_decode = json.encode, json.decode\nfunction emit(v)")
        + f"MODULE = {json.dumps(str(MODULE))}\nHEADERS = {to_lua(headers)}\nCTX = {to_lua(ctx)}\nLOG_METHOD = {json.dumps('log_stream' if kind == 'stream' else 'log')}\n"
        + STUBS
    )
    out = last_json(run_lua(script))
    assert out["ret"] is True and out["key"] == "plugin_bunkernet_reports", out
    return out


ALLOWED = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
    "Accept-Encoding": "gzip",
    "Accept-Language": "fr-FR",
    "Content-Type": "application/x-www-form-urlencoded",
    "Content-Length": "12",
}
SECRETS = {
    "Cookie": "session=abc",
    "Authorization": "Bearer t0ken",
    "Proxy-Authorization": "Basic Zm9v",
    "X-Api-Key": "k",
    "X-Forwarded-For": "10.0.0.1",
    "Referer": "https://example.com/private",
    "X-Custom-Token": "s3cret",
    "Host": "www.example.com",
}


def test_allowlisted_headers_are_kept_with_their_values():
    headers = send(ALLOWED)["report"]["headers"]
    assert headers == {name.lower(): value for name, value in ALLOWED.items()}


def test_everything_else_is_dropped():
    headers = send({**ALLOWED, **SECRETS})["report"]["headers"]
    assert set(headers) == {name.lower() for name in ALLOWED}
    for name in SECRETS:
        assert name.lower() not in headers


def test_a_multi_value_allowlisted_header_stays_a_table():
    headers = send({"Accept": ["text/html", "application/json"], "Cookie": ["a=1", "b=2"]})["report"]["headers"]
    assert headers == {"accept": ["text/html", "application/json"]}


def test_mixed_case_names_come_out_lowercase():
    headers = send({"USER-AGENT": "curl/8", "aCcEpT-LaNgUaGe": "en", "COOKIE": "x"})["report"]["headers"]
    assert headers == {"user-agent": "curl/8", "accept-language": "en"}


def test_no_headers_gives_an_empty_object():
    assert send({"Cookie": "x"})["report"]["headers"] == {}


def test_the_headers_read_stays_capped():
    assert send(ALLOWED)["max"] == 100


def test_stream_reports_carry_no_headers():
    out = send({**ALLOWED, **SECRETS}, kind="stream")
    assert out["report"]["headers"] == {}
    assert out.get("max") is None


def test_the_other_report_fields_are_unchanged():
    report = send({**ALLOWED, **SECRETS})["report"]
    assert report["ip"] == IP
    assert report["reason"] == "blacklist"
    assert report["data"] == {"id": "ua", "ua": "curl"}
    assert report["method"] == "POST"
    assert report["url"] == "/login?next=%2Fadmin"
    assert report["server_name"] == "www.example.com"
    assert report["date"] == "1970-01-12T13:46:40Z"
