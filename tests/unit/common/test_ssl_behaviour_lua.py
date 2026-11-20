"""Behaviour of ``src/common/core/ssl/ssl.lua``, the real file run under plain Lua.

The plugin's only runtime decision is the HTTP to HTTPS redirect: when it fires, to which URL, and
that the ACME HTTP-01 challenge path is never redirected. ``bunkerweb.acme`` is the real module; the
rest of OpenResty is stubbed at its boundary (``_lua_plugin_helpers.py``). The plugin has no
certificate handling of its own (certificates are served by letsencrypt, customcert and selfsigned),
so there is no missing-certificate path to test here.
"""

import pytest
from _lua_plugin_helpers import CORE, LUA, ROOT, module_path, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("SSL", CORE / "ssl" / "ssl.lua")
ACME = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "acme.lua"
PREAMBLE = f'package.loaded["bunkerweb.acme"] = dofile("{ACME}")\n'


def access(variables=None, **bw):
    ctx = {"scheme": "http", "https_configured": "no", "request_uri": "/page?x=1", "http_host": "www.example.com", "uri": "/page"}
    ctx.update(bw)
    body = f"""
VARIABLES = {to_lua({"REDIRECT_HTTP_TO_HTTPS": "no", "AUTO_REDIRECT_HTTP_TO_HTTPS": "no", **(variables or {})})}
local result = new_plugin(PLUGIN, {to_lua(ctx)}):access()
emit({{ ret = result.ret, msg = result.msg, status = result.status, redirect = result.redirect }})
"""
    return {"status": None, "redirect": None, **run_module(MODULE, body, preamble=PREAMBLE)}


class TestRedirectDecision:
    def test_redirect_setting_sends_http_to_the_same_host_and_uri_over_https(self):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"})
        assert (out["ret"], out["msg"], out["status"]) == (True, "redirect to HTTPS", 301)
        assert out["redirect"] == "https://www.example.com/page?x=1"

    def test_nothing_enabled_means_no_redirect(self):
        out = access()
        assert (out["msg"], out["status"], out["redirect"]) == ("no redirect to HTTPS needed", None, None)

    def test_auto_redirect_needs_https_to_be_configured_on_the_service(self):
        out = access({"AUTO_REDIRECT_HTTP_TO_HTTPS": "yes"}, https_configured="no")
        assert out["msg"] == "no redirect to HTTPS needed"

    def test_auto_redirect_fires_once_https_is_configured(self):
        out = access({"AUTO_REDIRECT_HTTP_TO_HTTPS": "yes"}, https_configured="yes")
        assert (out["status"], out["redirect"]) == (301, "https://www.example.com/page?x=1")

    def test_https_configured_alone_does_not_redirect(self):
        out = access({}, https_configured="yes")
        assert out["status"] is None

    def test_an_https_request_is_never_redirected(self):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"}, scheme="https")
        assert (out["msg"], out["status"]) == ("no redirect to HTTPS needed", None)

    @pytest.mark.parametrize("missing", ["request_uri", "http_host"])
    def test_a_request_without_host_or_uri_cannot_be_redirected(self, missing):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"}, **{missing: None})
        assert (out["msg"], out["status"]) == ("no redirect to HTTPS needed", None)

    def test_the_host_header_port_is_kept_in_the_target(self):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"}, http_host="www.example.com:8080", request_uri="/")
        assert out["redirect"] == "https://www.example.com:8080/"


class TestAcmeChallengeIsExempt:
    @pytest.mark.parametrize("uri", ["/.well-known/acme-challenge/abc_DEF-123", "/.well-known/acme-challenge/"])
    def test_the_challenge_path_is_answered_without_redirect_even_when_redirect_is_on(self, uri):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"}, uri=uri, request_uri=uri)
        assert (out["ret"], out["msg"], out["status"], out["redirect"]) == (True, "no redirect to HTTPS for the ACME challenge", None, None)

    def test_the_exemption_also_holds_for_auto_redirect(self):
        uri = "/.well-known/acme-challenge/tok"
        out = access({"AUTO_REDIRECT_HTTP_TO_HTTPS": "yes"}, https_configured="yes", uri=uri, request_uri=uri)
        assert out["msg"] == "no redirect to HTTPS for the ACME challenge"

    @pytest.mark.parametrize("uri", ["/.well-known/acme-challenge", "/x/.well-known/acme-challenge/tok", "/.well-known/security.txt"])
    def test_only_the_exact_challenge_prefix_is_exempt(self, uri):
        out = access({"REDIRECT_HTTP_TO_HTTPS": "yes"}, uri=uri, request_uri=uri)
        assert (out["msg"], out["status"]) == ("redirect to HTTPS", 301)
