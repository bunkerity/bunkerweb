"""The custom certificate wildcard fallback must never serve a service that did not enable custom SSL.

A global ``*.example.com`` custom certificate was served for every sub-domain, including services with
``USE_CUSTOM_SSL=no`` that get their certificate from another plugin (for example Let's Encrypt), shadowing it. ``init`` now
records the opted-out hosts and ``ssl_certificate`` declines for them while still serving the wildcard to other hosts.
This test runs the real ``customcert.lua`` ``init`` and ``ssl_certificate`` against stand-ins.
Refs: #3841.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
SNI = SNI
package.loaded["ngx.ssl"] = {
    server_name = function() return SNI, nil end,
    parse_pem_cert = function() return {} end,
    parse_pem_priv_key = function() return {} end,
}
package.loaded["resty.openssl.pkey"] = {}
package.loaded["resty.openssl.x509"] = {}
"""

SERVE = r"""
STORE.plugin_customcert_wildcard_bases = { "example.com" }
STORE.plugin_customcert_wildcard_certificates = { ["example.com"] = { "WILDCARD-CERT", "WILDCARD-KEY" } }
STORE.plugin_customcert_wildcard_excluded = { ["opted-out.example.com"] = true }
STORE["plugin_customcert_exact.example.com"] = { "EXACT-CERT", "EXACT-KEY" }
local r = PLUGIN:new({ bw = {} }):ssl_certificate()
emit({ msg = r.msg, cert = type(r.status) == "table" and r.status[1] or "none" })  -- ssl phases return the cert pair as the 3rd ret argument
"""


def serve(sni):
    return run_plugin_script("customcert", f'SNI = "{sni}"\n' + SERVE, header=HEADER)


def test_a_service_that_opted_out_of_custom_ssl_is_not_served_the_wildcard_certificate():
    out = serve("opted-out.example.com")
    assert out["cert"] == "none"
    assert out["msg"] == "custom certificate is not used (service did not enable USE_CUSTOM_SSL)"


def test_another_host_under_the_wildcard_still_gets_the_wildcard_certificate():
    out = serve("other.example.com")
    assert out["cert"] == "WILDCARD-CERT"


def test_an_exact_custom_certificate_wins_over_both_the_wildcard_and_the_exclusion_list():
    assert serve("exact.example.com")["cert"] == "EXACT-CERT"


def test_init_records_the_hosts_of_services_that_did_not_enable_custom_ssl():
    out = run_plugin_script(
        "customcert",
        r"""
local r = PLUGIN:new({ bw = {} }):init()
local excluded = STORE.plugin_customcert_wildcard_excluded or {}
local hosts = {}
for host in pairs(excluded) do hosts[#hosts + 1] = host end
table.sort(hosts)
emit({ ret = r.ret, hosts = hosts })
""",
        header=HEADER + r"""
VARIABLES = { MULTISITE = "yes" }
UTILS = {
    get_variable = function(name) return VARIABLES[name] end,
    get_multiple_variables = function()
        return {
            global = { USE_CUSTOM_SSL = "yes" },
            ["plain.example.com"] = { USE_CUSTOM_SSL = "no", SERVER_NAME = "plain.example.com WWW.Plain.example.com" },
        }, "success"
    end,
}
""",
    )
    assert out["ret"] is True
    assert out["hosts"] == ["plain.example.com", "www.plain.example.com"]
