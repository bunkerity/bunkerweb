"""Behaviour of ``src/common/core/errors/errors.lua``, the real file run under plain Lua.

The plugin counts every response status in the ``log`` phase and renders the default error page
(``render_template``) for the codes nginx intercepts: it sets hardened response headers, picks the
title / text / solution of the status (with a default solution) and classifies the error as client or
server. Which codes are intercepted and the custom pages per status are nginx configuration
(``ERRORS`` setting), not Lua. OpenResty and ``resty.template`` are stubbed at their boundary
(``_lua_plugin_helpers.py``); ``os.date`` is the real one.
"""

import json
import re

import pytest
from _lua_plugin_helpers import CORE, LUA, module_path, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("ERRORS", CORE / "errors" / "errors.lua")

# code -> (title, solution or None for the plugin default), straight from the plugin's table
TITLES = {
    "301": "Moved Permanently",
    "302": "Found",
    "400": "Bad Request",
    "401": "Not Authorized",
    "403": "Forbidden",
    "404": "Not Found",
    "405": "Method Not Allowed",
    "413": "Request Entity Too Large",
    "429": "Too Many Requests",
    "500": "Internal Server Error",
    "501": "Not Implemented",
    "502": "Bad Gateway",
    "503": "Service Unavailable",
    "504": "Gateway Timeout",
}
OWN_SOLUTION = {
    "400": "Please check the request and try again",
    "401": "Please check that you're authenticated and try again",
    "404": "Please check the URL and try again",
    "405": "Please check the request method and try again",
    "413": "Please reduce the size of the request and try again",
}
DEFAULT_SOLUTION = "Please try again in a few minutes"


def render(code, *, ctx=None, setup=""):
    """Run ``render_template(code)`` and return the page data, the response headers and the render count."""
    unset = "".join(f"plugin.ctx.bw.{key} = nil\n" for key, value in (ctx or {}).items() if value is None)
    body = f"""
ngx.header["Server"] = "nginx"
ngx.var.scheme = "http"
{setup}
local plugin = new_plugin(PLUGIN, {to_lua(ctx or {})})
{unset}plugin:render_template({json.dumps(code)})
local page = RENDERS[1] and RENDERS[1].data or {{}}
local data = {{}}
for k, v in pairs(page) do data[k] = v end
emit({{ name = RENDERS[1] and RENDERS[1].name, data = data, headers = ngx.header, renders = TEMPLATE_CALLS }})
"""
    return run_module(MODULE, body)


class TestLogPhase:
    def test_every_response_status_is_counted(self):
        body = """
ngx.status = 404
local plugin = new_plugin(PLUGIN, {})
local result = plugin:log()
emit({ ret = result.ret, msg = result.msg, metrics = METRICS })
"""
        out = run_module(MODULE, body)
        assert (out["ret"], out["msg"]) == (True, "success")
        assert out["metrics"] == {"404": 1}


class TestPageContent:
    @pytest.mark.parametrize("code", sorted(TITLES))
    def test_each_status_renders_its_own_title_and_text(self, code):
        out = render(code)
        assert out["name"] == "error.html"
        assert out["data"]["title"] == f"{code} | {TITLES[code]}"
        assert out["data"]["error_title"] == TITLES[code]
        assert out["data"]["error_code"] == code
        assert out["data"]["error_text"]

    @pytest.mark.parametrize("code", sorted(OWN_SOLUTION))
    def test_statuses_with_advice_show_it(self, code):
        assert render(code)["data"]["error_solution"] == OWN_SOLUTION[code]

    @pytest.mark.parametrize("code", sorted(set(TITLES) - set(OWN_SOLUTION)))
    def test_statuses_without_advice_get_the_default_solution(self, code):
        assert render(code)["data"]["error_solution"] == DEFAULT_SOLUTION

    @pytest.mark.parametrize(
        ("code", "kind"), [("301", "unknown"), ("302", "unknown"), ("404", "client"), ("429", "client"), ("500", "server"), ("504", "server")]
    )
    def test_error_type_follows_the_status_class(self, code, kind):
        assert render(code)["data"]["error_type"] == kind

    def test_an_unknown_status_is_not_rendered(self):
        # the page table only covers the codes nginx intercepts; anything else must fail loudly, not render junk
        body = """
local plugin = new_plugin(PLUGIN, {})
local ok = pcall(plugin.render_template, plugin, "418")
emit({ ok = ok, renders = TEMPLATE_CALLS })
"""
        assert run_module(MODULE, body) == {"ok": False, "renders": 0}


class TestRequestDetails:
    def test_request_id_and_client_ip_come_from_the_request_context(self):
        out = render("403", ctx={"request_id": "rid-1", "remote_addr": "203.0.113.9"})
        assert (out["data"]["request_id"], out["data"]["client_ip"]) == ("rid-1", "203.0.113.9")

    def test_they_fall_back_to_the_nginx_variables(self):
        out = render("403", ctx={"request_id": None, "remote_addr": None}, setup='ngx.var.request_id = "var-id"; ngx.var.remote_addr = "198.51.100.7"')
        assert (out["data"]["request_id"], out["data"]["client_ip"]) == ("var-id", "198.51.100.7")

    def test_the_request_time_is_the_request_start_in_utc_format(self):
        out = render("403", ctx={"start_time": 86400 * 365})
        stamp = out["data"]["request_time"]
        assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", stamp)
        assert stamp.startswith("1971-01-0")

    def test_without_a_start_time_the_current_time_is_used(self):
        stamp = render("403")["data"]["request_time"]
        assert re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC", stamp)
        assert not stamp.startswith("1971")


class TestHardenedHeaders:
    def test_the_page_never_leaks_the_server_header_and_is_not_cached(self):
        headers = render("500")["headers"]
        assert "Server" not in headers
        assert headers["Cache-Control"] == "no-cache, no-store, must-revalidate"
        assert headers["Content-Type"] == "text/html; charset=utf-8"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "no-referrer"

    def test_the_csp_uses_the_nonces_handed_to_the_template(self):
        out = render("404")
        csp = out["headers"]["Content-Security-Policy"]
        assert f"script-src 'strict-dynamic' 'nonce-{out['data']['nonce_script']}'" in csp
        assert f"style-src 'nonce-{out['data']['nonce_style']}'" in csp
        assert csp.startswith("default-src 'none';")
        assert "frame-ancestors 'none'" in csp
        assert "upgrade-insecure-requests" not in csp

    def test_https_adds_hsts_and_upgrade_insecure_requests(self):
        headers = render("404", ctx={"scheme": "https"})["headers"]
        assert headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains; preload"
        assert headers["Content-Security-Policy"].endswith(" upgrade-insecure-requests;")

    def test_https_is_also_detected_from_the_nginx_scheme_variable(self):
        headers = render("404", ctx={"scheme": None}, setup='ngx.var.scheme = "https"')["headers"]
        assert "Strict-Transport-Security" in headers

    def test_http_never_sends_hsts(self):
        assert "Strict-Transport-Security" not in render("404", ctx={"scheme": "http"})["headers"]

    def test_the_permissions_policy_is_set_and_denies_the_camera(self):
        policy = render("404")["headers"]["Permissions-Policy"]
        assert "camera=()" in policy and "geolocation=()" in policy


class TestStreamSubsystem:
    def test_the_stream_subsystem_does_not_load_the_template_engine(self):
        body = """
package.loaded["resty.template"] = nil
package.preload["resty.template"] = function() error("must not be required in stream") end
ngx.config.subsystem = "stream"
local errors = dofile(MODULE_FILE)
local plugin = new_plugin(errors, {})
emit({ log = plugin:log().ret })
"""
        script = body.replace("MODULE_FILE", json.dumps(str(MODULE)))
        # the module is loaded a second time with the stream subsystem: SUBSYSTEM is read when the plugin is first built
        assert run_module(MODULE, script) == {"log": True}
