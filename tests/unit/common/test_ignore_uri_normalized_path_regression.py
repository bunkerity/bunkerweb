"""``ANTIBOT_IGNORE_URI`` and ``COUNTRY_IGNORE_URI`` must match the normalized path, never the raw request path.

Both plugins also tested the raw ``request_uri`` (un-normalized path plus query string) against each pattern. With the
documented "challenge only these paths" pattern ``^/(?!search)``, a client skipped the check by sending a raw path that
NGINX still routes to the protected location (``//search``, ``/%73earch``, ``/./search``), and a positive pattern could
over-match the same way. The path is now matched normalized, alone and joined with the query string, so matching a
query string keeps working. This test runs the real ``is_ignored_uri`` of each plugin.
Refs: #3374.
"""

import pytest
from _g5_helpers import PCRE_LUA  # type: ignore
from _lua_plugin_helpers import CORE as COUNTRY_CORE, LUA, module_path, run_module  # type: ignore
from _t2_helpers import run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

COUNTRY_MODULE = module_path("COUNTRY", COUNTRY_CORE / "country" / "country.lua")

LOOKAHEAD = "^/(?!search)"
RAW_ALIASES = ["//search", "/%73earch", "/./search", "/a/../search", "/search"]

# (pattern, normalized uri, raw request_uri, ignored)
CASES = [
    # challenge-only-these-paths: only /search is checked, whatever raw spelling reaches it
    *[(LOOKAHEAD, "/search", raw, False) for raw in RAW_ALIASES],
    (LOOKAHEAD, "/search", "/search?x=1", False),
    (LOOKAHEAD, "/other", "/other", True),
    (LOOKAHEAD, "/other", "//other?x=1", True),
    # a positive pattern cannot be reached through a raw path that normalizes elsewhere
    ("^/static/", "/admin", "/static/../admin", False),
    ("^/static/", "/static/a.css", "/static/a.css", True),
    # query-string matching (#3374) still works on the normalized path
    (r"^/api\?token=", "/api", "/api?token=x", True),
    (r"^/api\?token=", "/api", "/api", False),
    (r"^/api\?token=", "/api", "//api?token=x", True),
    (r"^/api\?token=", "/shop", "/shop?q=/api?token=x", False),
    # a query string cannot make a protected path ignored for a path-anchored pattern
    ("^/health$", "/shop", "/shop?/health", False),
    (LOOKAHEAD, "/search", "/search?/other", False),
    ("debug=1", "/page", "/page?debug=1", True),
]


def lua_string(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def antibot_ignored(pattern, uri, request_uri):
    out = run_plugin_script(
        "antibot",
        f"""
local a = setmetatable({{
    ctx = {{ bw = {{ uri = {lua_string(uri)}, request_uri = {lua_string(request_uri)} }} }},
    lists = {{ IGNORE_URI = {{ {lua_string(pattern)} }} }},
}}, {{ __index = PLUGIN }})
local ignored = a:is_ignored_uri()
emit({{ ignored = ignored }})
""",
        header=PCRE_LUA + "\nUTILS = { regex_match = function(s, p) return pcre_match(s, p) end }\n",
    )
    return out["ignored"]


def country_ignored(pattern, uri, request_uri):
    out = run_module(
        COUNTRY_MODULE,
        f"""
VARIABLES = {{ WHITELIST_COUNTRY = "", BLACKLIST_COUNTRY = "FR", COUNTRY_IGNORE_URI = {lua_string(pattern)} }}
COUNTRY = "FR"
CACHE = {{}}
local p = new_plugin(PLUGIN, {{ remote_addr = "203.0.113.5", ip_is_global = true, uri = {lua_string(uri)}, request_uri = {lua_string(request_uri)} }})
local ignored = p:is_ignored_uri()
emit({{ ignored = ignored and true or false }})
""",
        preamble=PCRE_LUA + '\npackage.loaded["bunkerweb.utils"].regex_match = pcre_match\n',
    )
    return out["ignored"]


@pytest.mark.parametrize("pattern, uri, request_uri, ignored", CASES)
def test_antibot_ignore_uri_matches_the_normalized_path(pattern, uri, request_uri, ignored):
    assert antibot_ignored(pattern, uri, request_uri) is ignored


@pytest.mark.parametrize("pattern, uri, request_uri, ignored", CASES)
def test_country_ignore_uri_matches_the_normalized_path(pattern, uri, request_uri, ignored):
    assert country_ignored(pattern, uri, request_uri) is ignored
