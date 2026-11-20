"""The HTTP to HTTPS redirect must run before the whitelist short-circuits the access phase.

The redirect used to live in the ``misc`` plugin, which runs after ``whitelist``: a whitelisted client was served over
plain HTTP even with the redirect enabled. It moved to the ``ssl`` plugin, ordered first in the access chain. This test
pins the shipped access order, that ``ssl`` still redirects a whitelisted client, and that ``misc`` no longer redirects.
Refs: #1889.
"""

import json

import pytest
from _lua_plugin_helpers import LUA, run_module, to_lua  # type: ignore
from _t2_helpers import BW_MODULES, CORE

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

ACME = BW_MODULES / "acme.lua"
PREAMBLE = f'package.loaded["bunkerweb.acme"] = dofile("{ACME}")\nngx.HTTP_MOVED_PERMANENTLY = 301\nngx.HTTP_NOT_ALLOWED = 405\nngx.HTTP_BAD_REQUEST = 400\n'
REQUEST = {
    "scheme": "http",
    "https_configured": "yes",
    "request_uri": "/page?x=1",
    "http_host": "www.example.com",
    "uri": "/page",
    "request_method": "GET",
    "is_whitelisted": "yes",
}
SETTINGS = {"REDIRECT_HTTP_TO_HTTPS": "yes", "AUTO_REDIRECT_HTTP_TO_HTTPS": "no", "ALLOWED_METHODS": "GET|POST|HEAD"}


def _access(plugin):
    body = f"""
VARIABLES = {to_lua(SETTINGS)}
local result = new_plugin(PLUGIN, {to_lua(REQUEST)}):access()
emit({{ msg = result.msg, status = result.status, redirect = result.redirect }})
"""
    return {"status": None, "redirect": None, **run_module(CORE / plugin / f"{plugin}.lua", body, preamble=PREAMBLE)}


def test_access_chain_runs_ssl_before_whitelist():
    order = json.loads((CORE / "order.json").read_text())["access"]
    assert "ssl" in order and "whitelist" in order
    assert order.index("ssl") < order.index("whitelist")
    assert order.index("ssl") < order.index("misc")


def test_ssl_redirects_a_whitelisted_client():
    out = _access("ssl")
    assert (out["msg"], out["status"], out["redirect"]) == ("redirect to HTTPS", 301, "https://www.example.com/page?x=1")


def test_misc_does_not_redirect_so_it_cannot_be_the_one_skipped_by_the_whitelist():
    out = _access("misc")
    assert out["msg"] != "redirect to HTTPS"
    assert out["redirect"] is None
