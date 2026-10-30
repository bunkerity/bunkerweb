"""Behaviour of ``misc.lua``: method gate, CORS preflight pass-through, Location, strict SNI, log."""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua


def access(method, *, allowed="GET|POST|HEAD", mode="block", pre=""):
    method_lua = f'"{method}"' if method is not None else "nil"
    # ctx() keeps its default when an override is nil, so a missing method is cleared afterwards.
    clear = "" if method is not None else "c.bw.request_method = nil"
    return run(
        "misc",
        f"""
VARIABLES = {{ ALLOWED_METHODS = "{allowed}" }}
SECURITY_MODE = "{mode}"
{pre}
local c = ctx({{ request_method = {method_lua} }})
{clear}
local r = PLUGIN:new(c):access()
emit("msg", r.msg) emit("status", r.status) emit("metrics", metric_keys())
""",
    )


class TestMethodGate:
    @pytest.mark.parametrize("method", [None, "get", "GE", "G3T"])
    def test_malformed_method_is_400(self, method):
        out = access(method)
        assert out["status"] == "400"
        assert out["msg"] == "method is not valid"

    def test_allowed_method_passes(self):
        out = access("POST")
        assert out["status"] == "nil"
        assert out["msg"] == "method POST is allowed"

    def test_disallowed_method_is_405_in_block_mode(self):
        out = access("DELETE")
        assert out["status"] == "405"
        assert out["msg"] == "method DELETE is not allowed"
        assert out["metrics"] == "counters:failed_method"

    def test_disallowed_method_is_only_reported_in_detect_mode(self):
        out = access("DELETE", mode="detect")
        assert out["status"] == "nil"
        assert out["msg"] == "detected method DELETE not allowed"
        assert out["metrics"] == "counters:failed_method"


class TestCorsPreflight:
    PREFLIGHT = 'ngx.var.http_access_control_request_method = "PUT"'

    def _preflight(self, *, use_cors, origin=True):
        origin_lua = 'ctx_over = { http_origin = "https://a.example" }' if origin else "ctx_over = {}"
        return run(
            "misc",
            f"""
VARIABLES = {{ ALLOWED_METHODS = "GET|POST|HEAD" }}
GETVAR.USE_CORS = "{use_cors}"
{self.PREFLIGHT}
{origin_lua}
ctx_over.request_method = "OPTIONS"
local r = PLUGIN:new(ctx(ctx_over)):access()
emit("msg", r.msg) emit("status", r.status)
""",
        )

    def test_preflight_passes_to_the_cors_plugin_when_cors_is_on(self):
        out = self._preflight(use_cors="yes")
        assert out["msg"] == "CORS preflight request is allowed"
        assert out["status"] == "nil"

    @pytest.mark.parametrize(("use_cors", "origin"), [("no", True), ("yes", False)])
    def test_otherwise_options_is_just_a_disallowed_method(self, use_cors, origin):
        out = self._preflight(use_cors=use_cors, origin=origin)
        assert out["status"] == "405"


class TestLocationHeader:
    def test_location_is_added_when_a_plugin_asked_for_it(self):
        out = run(
            "misc",
            r"""
VARIABLES = {}
local r = PLUGIN:new(ctx({ location_header = "https://www.example.com/" })):header()
emit("msg", r.msg) emit("location", ngx.header["Location"])
""",
        )
        assert out["msg"] == "edited location header"
        assert out["location"] == "https://www.example.com/"

    def test_nothing_is_added_otherwise(self):
        out = run(
            "misc",
            r"""
VARIABLES = {}
local r = PLUGIN:new(ctx()):header()
emit("msg", r.msg) emit("location", ngx.header["Location"])
""",
        )
        assert out["msg"] == "no location header needed"
        assert out["location"] == "nil"


class TestStrictSni:
    def hello(self, *, strict="yes", sni='"www.example.com"', multisite="no", pre=""):
        return run(
            "misc",
            f"""
VARIABLES = {{}}
GETVAR.DISABLE_DEFAULT_SERVER_STRICT_SNI = "{strict}"
GETVAR.MULTISITE = "{multisite}"
GETVAR.SERVER_NAME = "www.example.com api.example.com"
STORE["variables"] = {{ ["blog.example.com"] = {{ SERVER_NAME = "blog.example.com" }} }}
SNI = {sni}
{pre}
local r = PLUGIN:new(ctx()):ssl_client_hello_default()
emit("msg", r.msg) emit("status", r.status) emit("ret", r.ret)
""",
        )

    def test_strict_sni_off_allows_everything(self):
        assert self.hello(strict="no")["msg"] == "strict SNI disabled"

    def test_missing_sni_closes_the_connection(self):
        out = self.hello(sni="nil")
        assert out["status"] == "444"
        assert out["msg"].startswith("can't get SNI host, denying access")

    def test_known_host_is_allowed(self):
        out = self.hello(sni='"api.example.com"')
        assert out["msg"] == "SNI host api.example.com is allowed"
        assert out["status"] == "nil"

    def test_unknown_host_is_closed(self):
        out = self.hello(sni='"evil.example.net"')
        assert out["status"] == "444"
        assert out["msg"] == "unknown SNI host evil.example.net, denying access"

    def test_multisite_reads_the_server_names_from_the_stored_variables(self):
        assert self.hello(multisite="yes", sni='"blog.example.com"')["msg"] == "SNI host blog.example.com is allowed"
        assert self.hello(multisite="yes", sni='"api.example.com"')["status"] == "444"


@pytest.mark.parametrize(("disabled", "metrics"), [("yes", "counters:failed_default"), ("no", "")])
def test_log_default_counts_only_when_the_default_server_is_disabled(disabled, metrics):
    out = run(
        "misc",
        f"""
VARIABLES = {{ DISABLE_DEFAULT_SERVER = "{disabled}" }}
local r = PLUGIN:new(ctx()):log_default()
emit("msg", r.msg) emit("metrics", metric_keys())
""",
    )
    assert out["msg"] == "success"
    assert out["metrics"] == metrics
