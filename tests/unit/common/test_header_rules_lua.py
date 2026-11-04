"""``utils.get_header_rules`` / ``pick_header_rules`` / ``match_header_rules`` (port of dev f61c03838).

These three are the whole of the "match a request header as an ignore or list criterion"
mechanism, and every one of them is a WAF bypass when it is wrong:

* ``get_header_rules`` pairs ``<PREFIX>_NAME_<n>`` with ``<PREFIX>_VALUE_<n>`` **at init**. Pairing
  the wrong suffixes silently binds a secret to the wrong header name; compiling the value later,
  on the request path, would echo that secret into ``error.log`` on the first bad pattern.
* ``pick_header_rules`` decides which service a rule applies to. Falling back to ``global`` for a
  service that declared its own (empty) set would leak one service's bypass to every other.
* ``match_header_rules`` is the request-time matcher. It must return the header **name** and never
  its value, must honour a repeated header, must cap ``get_headers()`` at ``MAX_HEADERS`` (a
  client that pads a request past the cap would otherwise push the matching header out of reach,
  i.e. slip past a blacklist rule), and must be inert in the stream subsystem where there are no
  request headers at all.

Runs the real block out of ``src/bw/lua/bunkerweb/utils.lua`` through the ``lua`` binary with
OpenResty stubbed, the way ``test_regex_match_memoize.py`` does.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def header_rules_source(path: Path | None = None) -> str:
    """The three functions plus the local helper between them, verbatim from utils.lua.

    ``path`` is resolved at call time on purpose: the failed-first run points it at a pre-port
    copy of utils.lua to prove these assertions can actually see the defect.
    """
    text = (path or UTILS_LUA).read_text(encoding="utf-8")
    chunk = re.search(
        r"^utils\.get_header_rules = function\(prefix\)$.*?^utils\.match_header_rules = function.*?\n^end$",
        text,
        re.S | re.M,
    )
    assert chunk, "the header-rule block was not found in utils.lua -- not ported, renamed or restructured?"
    return chunk.group(0)


PREAMBLE = r"""
local utils = {}
local ERR = "ERR"

LOGS = {}
local logger = { log = function(_, _, msg) LOGS[#LOGS + 1] = msg end }

-- Scoped variable table the harness drives, keyed exactly like internalstore's "variables".
VARIABLES = {}
utils.get_multiple_variables = function(vars)
    local result = {}
    for scope, scoped_vars in pairs(VARIABLES) do
        result[scope] = {}
        for variable, value in pairs(scoped_vars) do
            for _, tvar in ipairs(vars) do
                if variable:find("^" .. tvar .. "_?[0-9]*$") then
                    result[scope][variable] = value
                end
            end
        end
    end
    return result
end

MAX_HEADERS = "100"
utils.get_variable = function(name)
    if name == "MAX_HEADERS" then
        return MAX_HEADERS, "success"
    end
    return nil, "not found"
end

-- Counts every compile/match so a "compiled once at init" claim is provable rather than assumed.
RE_CALLS = 0
BAD_PATTERN = "((("
local re_match = function(subject, pattern, _)
    RE_CALLS = RE_CALLS + 1
    if pattern == BAD_PATTERN then
        return nil, "pcre_compile() failed: missing )"
    end
    -- Anchored-prefix stand-in for PCRE: enough to tell the values apart, and it treats "^" the
    -- way a real anchor does.
    local literal = pattern:gsub("^%^", ""):gsub("%$$", "")
    if pattern:sub(1, 1) == "^" and pattern:sub(-1) == "$" then
        return subject == literal and {} or nil
    end
    return subject:find(literal, 1, true) and {} or nil
end

-- ngx.req.get_headers, with the cap it was called with recorded.
HEADERS = {}
CAP = nil
GET_HEADERS_CALLS = 0
local get_headers = function(cap)
    GET_HEADERS_CALLS = GET_HEADERS_CALLS + 1
    CAP = cap
    return HEADERS
end
STREAM = false
if STREAM then get_headers = nil end
"""

EPILOGUE_HELPERS = r"""
function ctx_of(server)
    return { bw = { server_name = server } }
end
function reset()
    LOGS = {}
    RE_CALLS = 0
    GET_HEADERS_CALLS = 0
    CAP = nil
end
"""


def run(body: str, *, stream: bool = False, source: str | None = None) -> str:
    preamble = PREAMBLE.replace("STREAM = false", "STREAM = true") if stream else PREAMBLE
    script = "\n".join([preamble, source if source is not None else header_rules_source(), EPILOGUE_HELPERS, body])
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


class TestGetHeaderRules:
    def test_bare_and_suffixed_pairs_bind_the_right_value_to_the_right_name(self):
        out = run(r"""
VARIABLES = { global = {
    BL_HEADER_NAME = "X-First", BL_HEADER_VALUE = "^one$",
    BL_HEADER_NAME_2 = "X-Second", BL_HEADER_VALUE_2 = "^two$",
} }
local stored = utils.get_header_rules("BL_HEADER")
local by_name = {}
for _, rule in ipairs(stored.global) do by_name[rule.name] = rule.value end
print(#stored.global, by_name["x-first"], by_name["x-second"])
""")
        assert out.split() == ["2", "^one$", "^two$"]

    def test_the_name_is_lowercased_because_get_headers_keys_are(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Internal-Auth", BL_HEADER_VALUE = "^s3cr3t$" } }
print(utils.get_header_rules("BL_HEADER").global[1].name)
""")
        assert out.strip() == "x-internal-auth"

    def test_an_empty_value_means_match_on_presence(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Probe", BL_HEADER_VALUE = "" } }
print(tostring(utils.get_header_rules("BL_HEADER").global[1].value))
""")
        assert out.strip() == "nil"

    def test_a_nameless_rule_is_dropped(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "", BL_HEADER_VALUE = "^orphan$" } }
print(#utils.get_header_rules("BL_HEADER").global)
""")
        assert out.strip() == "0"

    def test_an_uncompilable_value_is_dropped_at_init_and_never_logs_the_pattern(self):
        # The pattern is the operator's shared secret: the error line may name the header, never
        # the value. Dropping the rule is the fail-closed half -- a pattern that cannot compile
        # must not become "matches everything" on the request path.
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Broken", BL_HEADER_VALUE = BAD_PATTERN } }
local stored = utils.get_header_rules("BL_HEADER")
print(#stored.global, #LOGS)
print(LOGS[1])
""")
        counts, message = out.splitlines()
        assert counts.split() == ["0", "1"]
        assert "X-Broken" in message
        assert "(((" not in message

    def test_a_service_inherits_a_global_pair_it_did_not_declare(self):
        # Without the fallback a non-multisite setup, which only ever has the "global" scope,
        # would silently match nothing.
        out = run(r"""
VARIABLES = {
    global = { BL_HEADER_NAME = "X-Global", BL_HEADER_VALUE = "^g$" },
    ["www.example.com"] = { BL_HEADER_VALUE = "^own$" },
}
local stored = utils.get_header_rules("BL_HEADER")
print(stored["www.example.com"][1].name, stored["www.example.com"][1].value)
""")
        assert out.split() == ["x-global", "^own$"]

    def test_values_are_compiled_once_at_init_and_not_per_request(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-A", BL_HEADER_VALUE = "^a$", BL_HEADER_NAME_2 = "X-B", BL_HEADER_VALUE_2 = "^b$" } }
local stored = utils.get_header_rules("BL_HEADER")
print(RE_CALLS)
reset()
HEADERS = { ["x-a"] = "a" }
utils.match_header_rules(ctx_of("www.example.com"), utils.pick_header_rules(stored, "www.example.com"), "SRC")
print(RE_CALLS)
""")
        init_calls, request_calls = out.split()
        assert init_calls == "2", "each value must be compiled exactly once, at init"
        assert request_calls == "1", "the request path must only match, never recompile the other rule"


class TestPickHeaderRules:
    def test_a_service_that_clears_the_name_gets_no_rules_and_does_not_fall_back_to_global(self):
        # This is the whole reason get_header_rules stores EVERY scope, empty ones included: the
        # stored table for such a service is an empty list, which is truthy in Lua, so pick returns
        # it instead of falling through to `or stored["global"]`. Clearing the name is the only way
        # a service can opt out -- a merge can overwrite a key but never remove one -- and if the
        # fallback fired here, opting out would silently re-grant the global bypass.
        out = run(r"""
VARIABLES = {
    global = { BL_HEADER_NAME = "X-Global", BL_HEADER_VALUE = "^g$" },
    ["quiet.example.com"] = { BL_HEADER_NAME = "" },
}
local stored = utils.get_header_rules("BL_HEADER")
print(#utils.pick_header_rules(stored, "quiet.example.com"), #utils.pick_header_rules(stored, "global"))
""")
        assert out.split() == ["0", "1"]

    def test_a_service_that_declares_nothing_still_gets_the_global_rule(self):
        # The other direction, and the one that makes a single-site setup work at all: a global
        # rule applies to every service that did not override it, exactly like a global
        # WHITELIST_IP does. Scoping it to the "global" pseudo-service would make the setting a
        # no-op on every real service.
        out = run(r"""
VARIABLES = {
    global = { BL_HEADER_NAME = "X-Global", BL_HEADER_VALUE = "^g$" },
    ["plain.example.com"] = { SOMETHING_ELSE = "x" },
}
local stored = utils.get_header_rules("BL_HEADER")
print(#stored["plain.example.com"], stored["plain.example.com"][1].name)
""")
        assert out.split() == ["1", "x-global"]

    def test_an_unknown_server_falls_back_to_global(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Global", BL_HEADER_VALUE = "^g$" } }
local stored = utils.get_header_rules("BL_HEADER")
print(#utils.pick_header_rules(stored, "never.seen"), #utils.pick_header_rules(nil, "x"))
""")
        assert out.split() == ["1", "0"]


class TestMatchHeaderRules:
    def test_it_returns_the_header_name_never_the_value(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Internal-Auth", BL_HEADER_VALUE = "^s3cr3t$" } }
HEADERS = { ["x-internal-auth"] = "s3cr3t" }
local stored = utils.get_header_rules("BL_HEADER")
print(tostring(utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")))
""")
        assert out.strip() == "x-internal-auth"
        assert "s3cr3t" not in out

    def test_a_wrong_value_does_not_match(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Auth", BL_HEADER_VALUE = "^right$" } }
HEADERS = { ["x-auth"] = "wrong" }
local stored = utils.get_header_rules("BL_HEADER")
print(tostring(utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")))
""")
        assert out.strip() == "nil"

    def test_presence_only_rule_matches_whatever_the_header_carries(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Probe", BL_HEADER_VALUE = "" } }
HEADERS = { ["x-probe"] = "anything at all" }
local stored = utils.get_header_rules("BL_HEADER")
print(tostring(utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")))
""")
        assert out.strip() == "x-probe"

    def test_a_repeated_header_matches_on_any_occurrence(self):
        # nginx hands a repeated header over as a list; only checking the first would let an
        # attacker bury a blacklisting value behind a benign one -- or, on a whitelist, let a
        # legitimate client's second value go unrecognised.
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Auth", BL_HEADER_VALUE = "^s3cr3t$" } }
HEADERS = { ["x-auth"] = { "decoy", "s3cr3t" } }
local stored = utils.get_header_rules("BL_HEADER")
print(tostring(utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")))
""")
        assert out.strip() == "x-auth"

    def test_get_headers_is_capped_at_max_headers(self):
        # Without the explicit cap get_headers() stops at 100 whatever MAX_HEADERS says, so a
        # client padding a request with 150 headers pushes the matching one out of reach.
        out = run(r"""
MAX_HEADERS = "250"
VARIABLES = { global = { BL_HEADER_NAME = "X-Auth", BL_HEADER_VALUE = "^s3cr3t$" } }
HEADERS = { ["x-auth"] = "s3cr3t" }
local stored = utils.get_header_rules("BL_HEADER")
utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")
print(tostring(CAP))
""")
        assert out.strip() == "250"

    def test_the_headers_table_is_read_once_per_request(self):
        out = run(r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Auth", BL_HEADER_VALUE = "^nope$" } }
HEADERS = { ["x-other"] = "x" }
local stored = utils.get_header_rules("BL_HEADER")
local rules = utils.pick_header_rules(stored, "global")
local ctx = ctx_of("global")
reset()
utils.match_header_rules(ctx, rules, "SRC")
utils.match_header_rules(ctx, rules, "SRC")
print(GET_HEADERS_CALLS)
""")
        assert out.strip() == "1", "ctx.bw.http_headers must be reused across calls in one request"

    def test_an_empty_rule_set_never_touches_the_headers(self):
        out = run(r"""
print(tostring(utils.match_header_rules(ctx_of("global"), {}, "SRC")), GET_HEADERS_CALLS)
""")
        assert out.split() == ["nil", "0"]

    def test_it_is_inert_in_the_stream_subsystem(self):
        # ngx.req.get_headers does not exist there; calling it would error out the whole phase.
        out = run(
            r"""
VARIABLES = { global = { BL_HEADER_NAME = "X-Auth", BL_HEADER_VALUE = "" } }
HEADERS = { ["x-auth"] = "s3cr3t" }
local stored = utils.get_header_rules("BL_HEADER")
print(tostring(utils.match_header_rules(ctx_of("global"), utils.pick_header_rules(stored, "global"), "SRC")))
""",
            stream=True,
        )
        assert out.strip() == "nil"


class TestPortedIntoUtils:
    def test_the_block_is_wired_into_the_module_not_only_defined(self):
        # The extraction above would still pass on a dead copy of the block. utils.lua must
        # actually export the three names and take get_headers from ngx.req.
        text = UTILS_LUA.read_text(encoding="utf-8")
        for name in ("utils.get_header_rules", "utils.pick_header_rules", "utils.match_header_rules"):
            assert f"{name} = function" in text, f"{name} is missing from utils.lua"
        assert "local get_headers = ngx.req and ngx.req.get_headers" in text
