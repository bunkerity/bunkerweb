"""Classify request IPs with the shipped matcher, including mapped IPv4 clients."""

import os
import subprocess
from pathlib import Path

import pytest

from test_ban_sync import UTILS_PREAMBLE
from test_ipv6_ipmatcher_luajit import IPMATCHER, LUAJIT, PRELUDE

ROOT = Path(__file__).resolve().parents[3]
UTILS = Path(os.environ.get("BW_GEO_UTILS", str(ROOT / "src/bw/lua/bunkerweb/utils.lua")))
HELPERS = Path(os.environ.get("BW_GEO_HELPERS", str(ROOT / "src/bw/lua/bunkerweb/helpers.lua")))

pytestmark = pytest.mark.skipif(not LUAJIT, reason="no LuaJIT on PATH (BW_LUAJIT)")


def run(body):
    script = (
        f'package.path = "{ROOT / "src/bw/lua"}/?.lua;" .. package.path\n'
        + UTILS_PREAMBLE.split("local utils = dofile(arg[1])")[0]
        + f"\nlocal test_ngx = ngx\nIPMATCHER_PATH = {str(IPMATCHER)!r}\n"
        + PRELUDE
        + "\nfor k, v in pairs(test_ngx) do ngx[k] = v end\n"
        + '\npackage.loaded["resty.ipmatcher"] = ipmatcher\n'
        + f"local utils = dofile({str(UTILS)!r})\n"
        + body
    )
    result = subprocess.run([str(LUAJIT), "-", "unused", "http"], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("8.8.8.8", True),
        ("8.0.0.3", True),
        ("::ffff:8.8.8.8", True),
        ("::FFFF:800:3", True),
        ("10.1.2.3", False),
        ("::ffff:10.1.2.3", False),
        ("127.0.0.1", False),
        ("2001:4860:4860::8888", True),
        ("2001:db8::1", False),
    ],
)
def test_global_classification_uses_the_embedded_ipv4(ip, expected):
    run(f'local actual, err = utils.ip_is_global("{ip}")\nassert(actual == {str(expected).lower()}, "{ip}: " .. tostring(actual) .. ", " .. tostring(err))')


@pytest.mark.parametrize("ip", ["8.8.8.8", "8.0.0.3", "::ffff:8.8.8.8"])
def test_fill_ctx_keeps_public_clients_eligible_for_geo_policies(ip):
    run(
        """
package.loaded["bunkerweb.utils"] = utils
package.loaded["resty.core.base"] = {get_request = function() return true end}
package.preload["bunkerweb.ctx"] = function() return {apply_ref = function() end} end
package.preload["bunkerweb.cachestore"] = function() return {new = function() return {} end} end
local mmdb = require "bunkerweb.mmdb"
mmdb.country_db = {lookup = function() return {country = {iso_code = "US"}} end}
mmdb.asn_db = {lookup = function(_, ip) return {autonomous_system_number = ip == "8.0.0.3" and 3356 or 15169} end}
ngx.req = {http_version = function() return 1.1 end, start_time = function() return 0 end}
ngx.var = {scheme = "http", server_name = "www.example.com"}
ngx.ctx = {}
"""
        + f'ngx.var.remote_addr = "{ip}"\nlocal helpers = dofile({str(HELPERS)!r})\n'
        + """
local ok, _, errors, ctx = helpers.fill_ctx(true)
assert(ok and #errors == 0)
print("remote_addr=" .. ctx.bw.remote_addr .. " ip_is_global=" .. tostring(ctx.bw.ip_is_global)
    .. " country=" .. ctx.bw.country .. " asn_number=" .. tostring(ctx.bw.asn_number))
assert(ctx.bw.ip_is_global == true, "public client classified local")
assert(ctx.bw.country == "US", "country lookup skipped")
assert(ctx.bw.asn_number == (ctx.bw.remote_addr == "8.0.0.3" and 3356 or 15169), "ASN lookup skipped")
"""
    )
