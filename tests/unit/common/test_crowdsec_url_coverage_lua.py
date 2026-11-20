"""Vendored CrowdSec URL parser/builder contracts; load complete library without stubs."""

from pathlib import Path

import pytest
from _lua_state_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore

MODULE = Path(__file__).resolve().parents[3] / "src/common/core/crowdsec/lib/url.lua"
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def run(body):
    return last_json(run_lua(BASE_LUA + f"\nlocal url = dofile({to_lua(str(MODULE))})\n" + body))


def test_parse_build_and_url_metamethods():
    out = run(r"""
local u = url.parse('HTTPS://bob:pass@EXAMPLE.COM:443/a%20b/%7e?q=hello+world#frag')
local before = tostring(u)
local same = u:addSegment('///next/part') == u
u:addSegment(false)
emit({scheme=u.scheme, userinfo=u.userinfo, user=u.user, password=u.password,
    authority=u.authority, host=u.host, port=u.port, path=u.path, query=u.query,
    fragment=u.fragment, before=before, same=same, left='prefix:' .. u, right=u .. ':suffix'})
""")
    assert out == {
        "scheme": "https",
        "userinfo": "bob:pass",
        "user": "bob",
        "password": "pass",
        "authority": "bob:pass@EXAMPLE.COM:443",
        "host": "example.com",
        "port": 443,
        "path": "/a%20b/~/next%2Fpart",
        "query": {"q": "hello world"},
        "fragment": "frag",
        "before": "https://bob:pass@example.com/a%20b/~?q=hello%20world#frag",
        "same": True,
        "left": "prefix:https://bob:pass@example.com/a%20b/~/next%2Fpart?q=hello%20world#frag",
        "right": "https://bob:pass@example.com/a%20b/~/next%2Fpart?q=hello%20world#frag:suffix",
    }


@pytest.mark.parametrize(
    "text,host,port,user,password,built",
    [
        ("http://192.0.2.1:8080", "192.0.2.1", 8080, None, None, "http://192.0.2.1:8080"),
        ("http://[2001:db8::1]:80/", "[2001:db8::1]", 80, None, None, "http://[2001:db8::1]/"),
        ("https://[1:2:3:4:5:6:7:8]:8443", "[1:2:3:4:5:6:7:8]", 8443, None, None, "https://[1:2:3:4:5:6:7:8]:8443"),
        ("ftp://bob@HOST", "host", None, "bob", None, "ftp://bob@host"),
        ("http://bob:@HOST", "host", None, "bob", "", "http://bob:@host"),
        ("http://bad_user:secret@host", "host", None, None, None, "http://host"),
        ("//HOST/path", "host", None, None, None, "//host/path"),
        ("http://256.1.2.3/x", None, None, None, None, "http:/x"),
        ("http://.host/x", None, None, None, None, "http:/x"),
        ("http://host./x", None, None, None, None, "http:/x"),
        ("http://bad..host/x", None, None, None, None, "http:/x"),
        ("http://bad_host/x", None, None, None, None, "http:/x"),
        ("http://[10000:2:3:4:5:6:7:8]/x", None, None, None, None, "http:/x"),
        ("http://[1::2::3]/x", None, None, None, None, "http:/x"),
    ],
)
def test_authority_validation_and_build(text, host, port, user, password, built):
    out = run(f"local u = url.parse({to_lua(text)}); emit({{host=u.host, port=u.port, user=u.user, password=u.password, built=tostring(u)}})")
    assert [out.get(key) for key in ("host", "port", "user", "password", "built")] == [host, port, user, password, built]


def test_setters_clear_old_authority_and_accept_query_tables():
    out = run(r"""
local u = url.parse('http://bob:pass@host:8080/one')
local remaining = u:setAuthority('NEW.EXAMPLE')
local query = u:setQuery({z='', a={second='two', first='one'}, ['x y']='a+b'})
local divided = u / 'two words'
emit({remaining=remaining, authority=u.authority, host=u.host, port=u.port,
    user=u.user, password=u.password, query=query, parsed=u.query, built=tostring(divided), same=u==divided})
""")
    assert out == {
        "remaining": "NEW.EXAMPLE",
        "authority": "NEW.EXAMPLE",
        "host": "new.example",
        "query": "a[first]=one&a[second]=two&x%20y=a%2Bb&z",
        "parsed": {"a": {"first": "one", "second": "two"}, "x_y": "a+b", "z": ""},
        "built": "http://new.example/one/two%20words?a[first]=one&a[second]=two&x_y=a%2Bb&z",
        "same": True,
    }


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, ""),
        (False, ""),
        (123, "123"),
        ("mailto:bob@example.com", "mailto:bob@example.com"),
        ("/a%2fb/%zz?empty=#", "/a%2Fb/%25zz?empty#"),
        ("http://host?x=1", "http://host/?x=1"),
    ],
)
def test_parse_empty_relative_and_opaque_urls(value, expected):
    assert run(f"emit(tostring(url.parse({to_lua(value)})))") == expected


def test_query_encoding_sorting_separators_and_options():
    out = run(r"""
local built = url.buildQuery({['10.x']='ten', ['2.x']='two', ['k +']='a&b=c', flag='', yes=true})
local q = url.parseQuery('a=hello+world;b=%2B;flag', ';')
url.options.query_plus_is_space = false
local plus = url.parseQuery('a=x+y')
url.options.separator = false
local fallback = tostring(url.parseQuery('b=2&a=1'))
url.options.separator = ';'
local configured = tostring(url.parseQuery('b=2;a=1'))
url.options.cumulative_parameters = true
local repeated = url.parseQuery('k=one;k=two')
local cumulative = url.buildQuery({k={'one', 'two'}}, '&')
emit({built=built, q=q, plus=plus, fallback=fallback, configured=configured,
    repeated=repeated, cumulative=cumulative})
""")
    assert out == {
        "built": "2.x=two&10.x=ten&flag&k%20%2B=a%26b%3Dc&yes=true",
        "q": {"a": "hello world", "b": "+", "flag": ""},
        "plus": {"a": "x+y"},
        "fallback": "a=1&b=2",
        "configured": "a=1;b=2",
        "repeated": {"k": ["one", "two"]},
        "cumulative": "k=one&k=two",
    }


@pytest.mark.parametrize(
    "query,expected",
    [
        ("arr[]=one&arr[]=two", {"arr": ["one", "two"]}),
        ("a[-1]=minus&a[2]=two", {"a": {"-1": "minus", "2": "two"}}),
        ("a=old&a[b][c]=new", {"a": {"b": {"c": "new"}}}),
        ("a[b]=old&a=new", {"a": "new"}),
        ("a=first&a=last", {"a": "first"}),
        ("a%20b=hello%20world&x===value", {"a_b": "hello world", "x": "value"}),
    ],
)
def test_query_bracket_shapes_and_scalar_collisions(query, expected):
    assert run(f"emit(url.parseQuery({to_lua(query)}))") == expected


@pytest.mark.parametrize("path,expected", [("", ""), ("/", "/"), ("/a//b/.././c/", "/a/c/"), ("a/../../b", "b"), ("./", "/"), ("/a/..", "/"), ("a/b", "a/b")])
def test_remove_dot_segments(path, expected):
    assert run(f"emit(url.removeDotSegments({to_lua(path)}))") == expected


@pytest.mark.parametrize(
    "relative,expected",
    [
        ("https://other/x", "https://other/x"),
        ("//other/x", "http://other/x"),
        ("", "http://host/a/b/c?base=1"),
        ("#frag", "http://host/a/b/c?base=1#frag"),
        ("?new=2", "http://host/a/b/c?new=2"),
        ("../d", "http://host/a/d"),
        ("./d", "http://host/a/b/d"),
        ("/../d", "http://host/d"),
        ("../../../../d", "http://host/d"),
        ("d/.", "http://host/a/b/d/"),
        ("d/..", "http://host/a/b/"),
        ("d/../e", "http://host/a/b/e"),
    ],
)
def test_resolve_absolute_relative_and_query_references(relative, expected):
    assert run(f"emit(tostring(url.resolve('http://host/a/b/c?base=1', {to_lua(relative)})))") == expected


def test_resolve_table_inputs_and_missing_path_query():
    out = run(r"""
local base = url.parse('http://host/a/b?base=1')
local other = url.parse('#frag')
other.path, other.query = nil, nil
local result = base:resolve(other)
emit({same=result==other, built=tostring(result), relative=tostring(url.resolve('a/b', '../c'))})
""")
    assert out == {"same": True, "built": "http://host/a/b?base=1#frag", "relative": "c"}


@pytest.mark.parametrize(
    "text,expected", [("HTTP://HOST/a//b/.././c", "http://host/a/c"), ("a/../../b", "b"), ("/a/.", "/a/"), ("../..", ".."), ("a/../../b/../c", "c")]
)
def test_normalize(text, expected):
    assert run(f"emit(tostring(url.normalize({to_lua(text)})))") == expected


def test_normalize_without_path_and_invalid_argument_errors():
    out = run(r"""
local u = url.parse('http://host'); u.path = nil
local normalized = u:normalize()
local results = {}
for _, fn in ipairs({function() url.parseQuery(nil) end, function() url.buildQuery(nil) end,
    function() u:setQuery(false) end, function() u:setAuthority(nil) end,
    function() url.removeDotSegments(nil) end, function() u:resolve(false) end}) do
    local ok, err = pcall(fn)
    results[#results+1] = {ok=ok, error=type(err)}
end
emit({same=normalized==u, built=tostring(u), errors=results})
""")
    assert out == {"same": True, "built": "http:", "errors": [{"ok": False, "error": "string"}] * 6}


@pytest.mark.xfail(strict=True, reason="Bundled parseQuery does not decode bracketed values")
def test_nested_query_values_decode_percent_escapes_and_plus():
    assert run("emit(url.parseQuery('a[b]=hello%20world+again'))") == {"a": {"b": "hello world again"}}


@pytest.mark.xfail(strict=True, reason="Bundled cumulative query parsing discards third repeated scalar")
def test_cumulative_query_preserves_three_values():
    assert run("url.options.cumulative_parameters=true; emit(url.parseQuery('k=one&k=two&k=three'))") == {"k": ["one", "two", "three"]}


@pytest.mark.xfail(strict=True, reason="Bundled compressed IPv6 validation accepts nonhex characters")
def test_compressed_ipv6_rejects_nonhex_host():
    assert run("local u=url.parse('http://[zz::1]/'); emit({host=u.host})") == {}


@pytest.mark.xfail(strict=True, reason="Bundled query parser discards nested data after a scalar collision")
def test_nested_scalar_collision_retains_new_subtree():
    assert run("emit(url.parseQuery('a[b]=first&a[b][c]=last'))") == {"a": {"b": {"c": "last"}}}
