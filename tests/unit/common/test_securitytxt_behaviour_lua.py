"""Behaviour of ``securitytxt.lua``: which request it claims, and what it renders."""

import re

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

URI = "/.well-known/security.txt"


def content(policies, *, uri=URI, use="yes", pre=""):
    return run(
        "securitytxt",
        f"""
VARIABLES = {{ USE_SECURITYTXT = "{use}", SECURITYTXT_URI = "{URI}" }}
STORE["plugin_securitytxt_security_policies"] = {{ global = {policies} }}
{pre}
local r = PLUGIN:new(ctx({{ uri = "{uri}" }})):content()
emit("msg", r.msg) emit("ret", r.ret) emit("rendered", RENDERED.name)
local d = RENDERED.data or {{}}
emit("contact", d.contact and table.concat(d.contact, ",")) emit("policy", d.policy and table.concat(d.policy, ","))
emit("expires", d.expires) emit("server_name", d.server_name) emit("sets", #SET_CALLS)
""",
    )


class TestAccess:
    @pytest.mark.parametrize("uri", [URI, "/security.txt"])
    def test_the_security_txt_paths_are_claimed(self, uri):
        out = run(
            "securitytxt",
            f"""
VARIABLES = {{ SECURITYTXT_URI = "{URI}" }}
local r = PLUGIN:new(ctx({{ uri = "{uri}" }})):access()
emit("msg", r.msg) emit("status", r.status)
""",
        )
        assert out["msg"] == "security.txt requested"
        assert out["status"] == "0"

    def test_other_paths_are_left_to_the_next_plugin(self):
        out = run(
            "securitytxt",
            f"""
VARIABLES = {{ SECURITYTXT_URI = "{URI}" }}
local r = PLUGIN:new(ctx({{ uri = "/index.html" }})):access()
emit("msg", r.msg) emit("status", r.status)
""",
        )
        assert out["msg"] == "success"
        assert out["status"] == "nil"


class TestContent:
    def test_disabled_renders_nothing(self):
        out = content('{ contact = { "mailto:a@b.c" } }', use="no")
        assert out["msg"] == "securitytxt not activated"
        assert out["rendered"] == "nil"

    def test_a_request_for_another_path_renders_nothing(self):
        out = content('{ contact = { "mailto:a@b.c" } }', uri="/other")
        assert out["msg"] == "securitytxt not requested"
        assert out["rendered"] == "nil"

    def test_a_contact_is_mandatory(self):
        out = content("{ contact = {} }")
        assert out["ret"] == "false"
        assert out["msg"] == "no contact key set"
        assert out["rendered"] == "nil"

    def test_http_urls_are_upgraded_to_https_but_other_schemes_are_not(self):
        out = content('{ contact = { "http://example.com/c", "mailto:a@b.c" }, policy = { "http://example.com/p" }, expires = "2030-01-01T00:00:00Z" }')
        assert out["rendered"] == "security.txt"
        assert out["contact"] == "https://example.com/c,mailto:a@b.c"
        assert out["policy"] == "https://example.com/p"
        assert out["server_name"] == "www.example.com"
        assert out["expires"] == "2030-01-01T00:00:00Z"
        assert out["sets"] == "0"

    def test_missing_expires_is_generated_once_and_then_reused(self):
        first = content('{ contact = { "mailto:a@b.c" }, expires = "" }')
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", first["expires"])
        assert first["sets"] == "1"
        reused = content(
            '{ contact = { "mailto:a@b.c" }, expires = "" }',
            pre='STORE["plugin_securitytxt_auto_expires_www.example.com"] = "2031-02-03T04:05:06Z"',
        )
        assert reused["expires"] == "2031-02-03T04:05:06Z"
        assert reused["sets"] == "0"


def test_init_groups_numbered_variables_under_their_key():
    out = run(
        "securitytxt",
        r"""
MULTI_VARS = { global = { SECURITYTXT_URI = "/.well-known/security.txt", SECURITYTXT_CONTACT = "mailto:a@b.c",
                          SECURITYTXT_CONTACT_2 = "https://x/c", SECURITYTXT_EXPIRES = "2030-01-01T00:00:00Z",
                          SECURITYTXT_HIRING = "" } }
local r = PLUGIN:new(ctx()):init()
local g = STORE["plugin_securitytxt_security_policies"].global
local contact = { table.unpack(g.contact) }
table.sort(contact)
emit("msg", r.msg) emit("contact", table.concat(contact, ",")) emit("expires", g.expires) emit("uri", g.uri)
emit("hiring", #g.hiring)
""",
    )
    assert out["msg"] == "successfully loaded security policies"
    assert out["contact"] == "https://x/c,mailto:a@b.c"
    assert out["expires"] == "2030-01-01T00:00:00Z"
    assert out["uri"] == "/.well-known/security.txt"
    assert out["hiring"] == "0"
