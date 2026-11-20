"""Include/ignore URI policy through the antibot lifecycle and real regex error wrapper."""

import json
from pathlib import Path

import pytest
from _lua_plugin_helpers import LUA, to_lua
from test_antibot_request_coverage_lua import run
from test_regex_match_memoize import regex_match_source

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def policy_run(body):
    # Only the engine is stubbed: these simple patterns agree with Lua patterns.
    setup = r"""
do
    local ERR = 'ERR'
    local var = { server_name = 'www.example.com' }
    local logger = { log = function(_, level, msg) LOGS[#LOGS + 1] = { level, msg } end }
    local re_match = function(subject, pattern, options)
        assert(options == 'o', 'URI matching must remain case-sensitive PCRE with o only')
        if pattern == '[' then return nil, 'pcre_compile() failed: missing ]' end
        if pattern == 'runtime' and subject ~= '' then return nil, 'pcre_exec() failed: match limit' end
        return subject:find(pattern) and {} or nil
    end
""" + regex_match_source() + "\nend\n"
    return run(body, setup)


@pytest.mark.parametrize(
    "include, ignore, uri, request_uri, challenged",
    [
        ("", "", "/about", "/about", True),
        ("   ", "", "/about", "/about", True),
        ("^/search", "", "/search", "/search", True),
        ("^/search", "", "/about", "/about", False),
        ("^/search", "", "/Search", "/Search", False),
        ("search", "", "/deep/search", "/deep/search", True),
        ("^/search", "^/search/public", "/search/public", "/search/public", False),
        ("^/search", "^/search", "/search", "/search", False),
        ("[?]q=1$", "", "/search", "/search?q=1", True),
        ("[?]q=1$", "", "/search", "/search?q=2", False),
        ("[?]q=1$", "[?]q=1$", "/search", "/search?q=1", False),
        ("^/other", "", "/search", "//search", False),
        ("^/other", "", "/search", "/%73earch", False),
        ("^/other", "", "/search", "/./search", False),
        ("^/search", "", "/search", "//search", True),
        ("^/search", "", "/search", "/%73earch", True),
        ("^/search", "", "/search", "/./search", True),
        ("^//search", "", "/search", "//search", False),
        ("^/%%73earch", "", "/search", "/%73earch", False),
        ("^/other", "", "/search", "//search?q=1", False),
        ("", "[", "/search", "/search", True),
        ("[", "^/search", "/search", "/search", False),
    ],
)
def test_include_ignore_uri_policy(include, ignore, uri, request_uri, challenged):
    out = policy_run(f"""
VARIABLES.ANTIBOT_INCLUDE_URI = {to_lua(include)}
VARIABLES.ANTIBOT_IGNORE_URI = {to_lua(ignore)}
local a = new_plugin(PLUGIN, {{ uri = {to_lua(uri)}, request_uri = {to_lua(request_uri)} }})
emit({{ result = a:access(), logs = LOGS }})
""")
    assert ("redirect" in out["result"]) is challenged
    assert out["result"]["ret"] is True
    if not challenged and not ignore:
        assert "not included" in out["result"]["msg"]
    if ignore == "[":
        assert any("invalid regex for ANTIBOT_IGNORE_URI" in msg for _, msg in out["logs"])


@pytest.mark.parametrize("pattern", ["[", "^/other [", "runtime"])
def test_invalid_include_fails_closed_and_compile_error_logs_once(pattern):
    out = policy_run(f"""
VARIABLES.ANTIBOT_INCLUDE_URI = {to_lua(pattern)}
local results = {{}}
for _, uri in ipairs({{ '/search', '/about' }}) do
    results[#results + 1] = new_plugin(PLUGIN, {{ uri = uri, request_uri = uri }}):access()
end
emit({{ results = results, logs = LOGS }})
""")
    assert all("redirect" in result for result in out["results"])
    errors = [msg for _, msg in out["logs"] if "invalid regex for ANTIBOT_INCLUDE_URI" in msg]
    assert len(errors) == (2 if pattern == "runtime" else 1)


def test_include_lists_parse_all_whitespace_once():
    out = policy_run(r"""
VARIABLES.ANTIBOT_INCLUDE_URI = '  ^/search\t^/login\n^/other  '
local a = new_plugin(PLUGIN)
VARIABLES.ANTIBOT_INCLUDE_URI = '^/changed'
emit(a.lists)
""")
    assert out["INCLUDE_URI"] == ["^/search", "^/login", "^/other"]


def test_challenge_endpoint_still_served_with_nonmatching_include_and_matching_ignore():
    out = policy_run(r"""
VARIABLES.ANTIBOT_INCLUDE_URI = '^/search'
VARIABLES.ANTIBOT_IGNORE_URI = '^/challenge'
SESSION_DATA = { prepared = true, resolved = false, time_resolve = NOW, original_uri = '/search', type = 'javascript' }
local a = new_plugin(PLUGIN, { uri = '/challenge', request_uri = '/challenge?next=%2Fsearch', request_method = 'GET' })
local access = a:access()
local content = a:content()
a:header()
emit({ access = access, content = content, renders = RENDERS, headers = ngx.header })
""")
    assert "ignored" not in out["access"]["msg"]
    assert "not included" not in out["access"]["msg"]
    assert out["content"]["ret"] is True
    assert len(out["renders"]) == 1
    assert out["headers"]["Cache-Control"] == "no-store"


@pytest.mark.parametrize("kind", ["include", "ignore"])
def test_uri_cache_isolates_paths_queries_and_servers(kind):
    out = policy_run(f"""
VARIABLES.ANTIBOT_INCLUDE_URI = {to_lua('[?]q=1$' if kind == 'include' else '')}
VARIABLES.ANTIBOT_IGNORE_URI = {to_lua('[?]q=2$' if kind == 'ignore' else '')}
local results, keys = {{}}, {{}}
for _, request in ipairs({{ {{ '/search', '/search?q=2' }}, {{ '/search', '/search?q=1' }}, {{ '/other', '/other' }} }}) do
    local a = new_plugin(PLUGIN, {{ uri = request[1], request_uri = request[2] }})
    keys[#keys + 1] = a:kind_to_ele('URI')
    results[#results + 1] = a:access()
end
local cached = new_plugin(PLUGIN, {{ uri = '/search', request_uri = '/search?q=2' }}):access()
-- A second server must not inherit the first server's bypass entry.
VARIABLES.ANTIBOT_INCLUDE_URI, VARIABLES.ANTIBOT_IGNORE_URI = '', ''
local other_server = new_plugin(PLUGIN, {{ server_name = 'other.example', uri = '/search', request_uri = '/search?q=2' }}):access()
emit({{ results = results, cached = cached, other_server = other_server, keys = keys, ttl = CACHE_TTL }})
""")
    assert "redirect" not in out["results"][0]
    assert "redirect" in out["results"][1]
    assert ("redirect" in out["results"][2]) is (kind == "ignore")
    assert "cached antibot ignored" in out["cached"]["msg"]
    assert "redirect" in out["other_server"]
    assert len(set(out["keys"])) == 3
    assert out["ttl"] == 86400


def test_setting_schema_is_multisite_empty_and_ordered_after_ignore():
    settings = json.loads((Path(__file__).resolve().parents[3] / "src/common/core/antibot/plugin.json").read_text())["settings"]
    include = settings["ANTIBOT_INCLUDE_URI"]
    assert list(settings).index("ANTIBOT_INCLUDE_URI") == list(settings).index("ANTIBOT_IGNORE_URI") + 1
    assert include["default"] == ""
    assert include["context"] == "multisite"
    assert include["type"] == "multivalue"
    assert include["regex"] == "^.*$"
    assert len(include["help"]) <= 512
