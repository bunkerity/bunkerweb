"""A named single-site roster must reach certificate loading and propagate failures.

Init must retain provider indexes even when parsing the service certificate fails.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="lua is required")

HEADER = r"""
VARIABLES = { MULTISITE = "no", SERVER_NAME = "app.example.com alias.example.com" }
READS, PARSES = {}, {}
UTILS = {
    read_files = function(paths)
        READS[#READS + 1] = paths
        return true, { "certificate-pem", "private-key-pem" }
    end,
}
package.loaded["ngx.ssl"] = {
    parse_pem_cert = function(pem)
        PARSES[#PARSES + 1] = pem
        if FAIL_CERT then return nil, "invalid certificate" end
        return "parsed-certificate"
    end,
    parse_pem_priv_key = function(pem)
        PARSES[#PARSES + 1] = pem
        if FAIL_KEY then return nil, "invalid key" end
        return "parsed-key"
    end,
    server_name = function() return "app.example.com" end,
}
local pubkey = { tostring = function() return "same-public-key" end }
package.loaded["resty.openssl.pkey"] = { new = function() return pubkey end }
package.loaded["resty.openssl.x509"] = {
    new = function()
        return {
            get_not_before = function() return os.time() - 60 end,
            get_not_after = function() return os.time() + 3600 end,
            get_pubkey = function() return pubkey end,
            get_subject_alt_name = function()
                return { each = function() return ipairs({}) end }
            end,
            get_subject_name = function()
                return { find = function() return { blob = "*.example.com" } end }
            end,
        }
    end,
}
"""


@pytest.mark.parametrize("provider", ["customcert", "selfsigned"])
@pytest.mark.parametrize("failure", [None, "cert", "key"])
def test_named_roster_loads_both_aliases_or_reports_parse_failure(provider, failure):
    out = run_plugin_script(
        provider,
        r"""
local instance = PLUGIN:new({})
local result = instance:init()
local keys = {}
for key in pairs(STORE) do keys[#keys + 1] = key end
table.sort(keys)
emit({ result = result, reads = READS, parses = PARSES, logs = LOGS, keys = keys,
    primary = STORE["plugin_" .. PROVIDER .. "_app.example.com"],
    alias = STORE["plugin_" .. PROVIDER .. "_alias.example.com"],
    bases = STORE.plugin_customcert_wildcard_bases,
    wildcards = STORE.plugin_customcert_wildcard_certificates,
    excluded = STORE.plugin_customcert_wildcard_excluded })
""",
        header=HEADER + f'\nPROVIDER = "{provider}"\nFAIL_CERT = {str(failure == "cert").lower()}\nFAIL_KEY = {str(failure == "key").lower()}\n',
    )
    assert out["reads"] == [[f"/var/cache/bunkerweb/{provider}/app.example.com/cert.pem", f"/var/cache/bunkerweb/{provider}/app.example.com/key.pem"]]
    assert out["parses"] == (["certificate-pem"] if failure == "cert" else ["certificate-pem", "private-key-pem"])
    assert out["result"]["ret"] is (failure is None)
    if failure:
        assert out["result"]["msg"] == "error loading data"
        assert len(out["logs"]) == 1
        assert out["logs"][0].startswith("ERR: error while loading data : error while parsing pem ")
        assert ("invalid certificate" if failure == "cert" else "invalid key") in out["logs"][0]
        assert "primary" not in out and "alias" not in out
    else:
        assert out["result"]["msg"] == "success"
        assert not out["logs"]
        assert out["primary"] == out["alias"] == ["parsed-certificate", "parsed-key"]
    expected_keys = [] if failure else [f"plugin_{provider}_alias.example.com", f"plugin_{provider}_app.example.com"]
    if provider == "customcert":
        expected_keys += ["plugin_customcert_wildcard_bases", "plugin_customcert_wildcard_certificates", "plugin_customcert_wildcard_excluded"]
        assert out["excluded"] == {}
        assert out["bases"] == ({} if failure else ["example.com"])
        assert out["wildcards"] == ({} if failure else {"example.com": ["parsed-certificate", "parsed-key"]})
    assert sorted(out["keys"]) == sorted(expected_keys)
