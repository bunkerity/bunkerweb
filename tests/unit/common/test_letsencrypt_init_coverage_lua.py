"""Let's Encrypt startup certificate loading and published indexes, using the real module."""

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PREAMBLE = r"""
local utils = package.loaded["bunkerweb.utils"]
utils.get_multiple_variables = function(names)
    if names[1] == "LETS_ENCRYPT_DNS_CREDENTIAL_ITEM" then
        if CREDENTIAL_ERROR then return nil, "credentials unavailable" end
        return CREDENTIALS or {}, "success"
    end
    if MULTI_ERR then return nil, MULTI_ERR end
    return MULTI_VARS, "success"
end
utils.read_files = function(paths)
    READS[#READS + 1] = paths
    local ident = paths[1]:match("/live/([^/]+)/fullchain.pem$")
    assert(paths[2] == "/var/cache/bunkerweb/letsencrypt/etc/live/" .. ident .. "/privkey.pem")
    if READ_ERROR then return false, READ_ERROR end
    return true, {"cert:" .. ident, "key:" .. ident}
end
package.loaded["bunkerweb.acme"] = {}
package.loaded["resty.env"] = {set = function() end}
package.loaded["ngx.ssl"] = {
    parse_pem_cert = function(pem)
        if PEM_ERROR == "cert" then return nil, "bad certificate" end
        return "parsed:" .. pem
    end,
    parse_pem_priv_key = function(pem)
        if PEM_ERROR == "key" then return nil, "bad private key" end
        return "parsed:" .. pem
    end,
}
package.loaded["resty.openssl.x509"] = {new = function()
    return {get_subject_alt_name = function()
        return {each = function()
            local i = 0
            return function() i = i + 1; if IP_SANS[i] then return "IP", IP_SANS[i] end end
        end}
    end}
end}
"""


def run_init(setup=""):
    return run_module(
        CORE / "letsencrypt" / "letsencrypt.lua",
        r"""
HAS_VARIABLE = true
GETVAR = {MULTISITE="no", SERVER_NAME="app.example.com alias.example.com",
          USE_LETS_ENCRYPT_WILDCARD="no", LETS_ENCRYPT_CHALLENGE="http"}
READS, IP_SANS = {}, {}
"""
        + setup
        + r"""
local p = new_plugin(PLUGIN)
p.internalstore.get = function(_, key)
    if GET_ERROR == key then return nil, "cache unavailable" end
    if STORE[key] == nil then return nil, "not found" end
    return STORE[key]
end
p.internalstore.set = function(_, key, value)
    if SET_ERROR == key then return false, "cache full" end
    STORE[key] = value
    return true
end
local result = p:init()
emit({result=result, store=STORE, logs=LOGS, reads=READS})
""",
        preamble=PREAMBLE,
    )


def service(names, *, enabled="yes", challenge="http", wildcard="no", provider=""):
    return {
        "SERVER_NAME": names,
        "AUTO_LETS_ENCRYPT": enabled,
        "LETS_ENCRYPT_CHALLENGE": challenge,
        "USE_LETS_ENCRYPT_WILDCARD": wildcard,
        "LETS_ENCRYPT_DNS_PROVIDER": provider,
    }


def mode_setup(multisite, wildcard=False, names="app.example.com alias.example.com"):
    challenge = "dns" if wildcard else "http"
    setup = f"GETVAR.SERVER_NAME={to_lua(names)}\nGETVAR.MULTISITE={to_lua(multisite)}\n"
    setup += f"GETVAR.USE_LETS_ENCRYPT_WILDCARD={to_lua('yes' if wildcard else 'no')}\n"
    setup += f"GETVAR.LETS_ENCRYPT_CHALLENGE={to_lua(challenge)}\n"
    if multisite == "yes":
        setup += "MULTI_VARS=" + to_lua({"service": service(names, challenge=challenge, wildcard="yes" if wildcard else "no", provider="test")}) + "\n"
        setup += 'CREDENTIALS={service={LETS_ENCRYPT_DNS_CREDENTIAL_ITEM="token"}}\n'
    return setup


@pytest.mark.parametrize("multisite", ["yes", "no"])
def test_exact_lineage_loads_all_names_and_ip_sans(multisite):
    out = run_init(mode_setup(multisite, names="App.Example.COM. alias.example.com 192.0.2.10 192.0.2.11") + 'IP_SANS={"192.0.2.10"}\n')
    assert out["result"] == {"ret": True, "msg": "success"}
    store = out["store"]
    cert = ["parsed:cert:App.Example.COM.", "parsed:key:App.Example.COM.", "app.example.com"]
    assert store["plugin_letsencrypt_app.example.com"] == cert
    assert store["plugin_letsencrypt_alias.example.com"] == cert
    assert store["plugin_letsencrypt_192.0.2.11"] == cert
    assert store["plugin_letsencrypt_ipcert_192.0.2.10"] == cert
    assert "plugin_letsencrypt_ipcert_192.0.2.11" not in store
    assert store["plugin_letsencrypt_ip_names"] == {"192.0.2.10": "app.example.com"}
    assert store["plugin_letsencrypt_wildcard_servers"]["alias.example.com"] == "alias.example.com"
    assert out["reads"] == [
        [
            "/var/cache/bunkerweb/letsencrypt/etc/live/App.Example.COM./fullchain.pem",
            "/var/cache/bunkerweb/letsencrypt/etc/live/App.Example.COM./privkey.pem",
        ]
    ]


@pytest.mark.parametrize("multisite", ["yes", "no"])
@pytest.mark.parametrize("wildcard", [False, True])
@pytest.mark.parametrize("failure", ["read", "cert", "key", "store"])
def test_loading_failures_report_error_and_publish_indexes(multisite, wildcard, failure):
    ident = "example.com" if wildcard else "app.example.com"
    setup = mode_setup(multisite, wildcard)
    setup += {
        "read": 'READ_ERROR="missing lineage"\n',
        "cert": 'PEM_ERROR="cert"\n',
        "key": 'PEM_ERROR="key"\n',
        "store": f'SET_ERROR="plugin_letsencrypt_{ident}"\n',
    }[failure]
    out = run_init(setup)
    assert out["result"] == {"ret": False, "msg": "error reading files" if failure == "read" else "error loading data"}
    assert f"plugin_letsencrypt_{ident}" not in out["store"]
    assert out["store"]["plugin_letsencrypt_ip_names"] == {}
    assert "plugin_letsencrypt_wildcard_servers" in out["store"]
    detail = {"read": "missing lineage", "cert": "bad certificate", "key": "bad private key", "store": "cache full"}[failure]
    assert any(detail in line[1] and line[0] == "ERR" for line in out["logs"])


@pytest.mark.parametrize("multisite", ["yes", "no"])
@pytest.mark.parametrize("cached", [False, True])
def test_wildcard_bases_sorted_and_cached_lineages_preserved(multisite, cached):
    names = "*.example.com *.sub.example.com *.another.com App.Example.COM. deep.app.example.com"
    setup = mode_setup(multisite, True, names)
    if cached:
        setup += r"""
for _, base in ipairs({"example.com", "sub.example.com", "another.com", "app.example.com"}) do
    STORE["plugin_letsencrypt_" .. base] = {"cached cert", "cached key", base}
end
READ_ERROR="must not read cached lineage"
"""
    out = run_init(setup)
    assert out["result"] == {"ret": True, "msg": "success"}
    assert out["store"]["plugin_letsencrypt_wildcard_bases"] == ["app.example.com", "sub.example.com", "another.com", "example.com"]
    servers = out["store"]["plugin_letsencrypt_wildcard_servers"]
    assert servers["app.example.com"] == "app.example.com"
    assert servers["deep.app.example.com"] == "app.example.com"
    for base in ("example.com", "sub.example.com", "another.com", "app.example.com"):
        assert servers[base] == base
        expected = ["cached cert", "cached key", base] if cached else [f"parsed:cert:{base}", f"parsed:key:{base}", base]
        assert out["store"][f"plugin_letsencrypt_{base}"] == expected
    assert len(out["reads"]) == (0 if cached else 4)


@pytest.mark.parametrize("missing", ["MULTISITE", "SERVER_NAME", "USE_LETS_ENCRYPT_WILDCARD", "LETS_ENCRYPT_CHALLENGE"])
def test_missing_variable_stops_before_publishing(missing):
    out = run_init(f"GETVAR.{missing}=nil\n")
    assert out["result"] == {"ret": False, "msg": f"can't get {missing} variable : no such variable {missing}"}
    assert out["store"] == {}
    assert out["reads"] == {}


@pytest.mark.parametrize("credentials", [False, True])
def test_multisite_lookup_failures_stop_before_publishing(credentials):
    out = run_init('GETVAR.MULTISITE="yes"\n' + ("CREDENTIAL_ERROR=true\n" if credentials else 'MULTI_ERR="db unavailable"\n'))
    assert out["result"] == {
        "ret": False,
        "msg": "can't get credential items : credentials unavailable" if credentials else "can't get required variables : db unavailable",
    }
    assert out["store"] == {}


@pytest.mark.parametrize("key, message", [("wildcard_bases", "wildcard bases"), ("wildcard_servers", "wildcard servers"), ("ip_names", "IP names")])
def test_index_write_failure_is_fatal(key, message):
    out = run_init(f'HAS_VARIABLE=false; SET_ERROR="plugin_letsencrypt_{key}"\n')
    assert out["result"] == {"ret": False, "msg": f"error while setting {message} into internalstore : cache full"}
    assert f"plugin_letsencrypt_{key}" not in out["store"]


@pytest.mark.parametrize("enabled", [False, True])
def test_disabled_or_empty_roster_still_publishes_empty_indexes(enabled):
    out = run_init('GETVAR.SERVER_NAME=""\n' if enabled else "HAS_VARIABLE=false\n")
    assert out["result"] == {"ret": not enabled, "msg": "no server name configured" if enabled else "let's encrypt is not used"}
    assert out["store"] == {f"plugin_letsencrypt_{key}": {} for key in ("wildcard_bases", "wildcard_servers", "ip_names")}
    assert out["reads"] == {}
    if enabled:
        assert "SERVER_NAME is empty" in out["logs"][0][1]


def test_multisite_skips_ineligible_services_and_claims_their_names():
    services = {
        "global": service("global.example.com"),
        "disabled": service("Off.Example.COM. alias.example.com", enabled="no"),
        "no-provider": service("no-provider.example.com", challenge="dns"),
        "no-credentials": service("no-credentials.example.com", challenge="dns", provider="test"),
        "fallback.example.com": {"AUTO_LETS_ENCRYPT": "no"},
        "eligible": service("valid.example.com", challenge="dns", provider="test"),
    }
    out = run_init('GETVAR.MULTISITE="yes"\nMULTI_VARS=' + to_lua(services) + '\nCREDENTIALS={eligible={token="present"}}\n')
    assert out["result"] == {"ret": True, "msg": "success"}
    servers = out["store"]["plugin_letsencrypt_wildcard_servers"]
    assert servers == {
        name: False for name in ("off.example.com", "alias.example.com", "no-provider.example.com", "no-credentials.example.com", "fallback.example.com")
    } | {"valid.example.com": "valid.example.com"}
    assert out["store"]["plugin_letsencrypt_valid.example.com"][2] == "valid.example.com"
    assert len(out["reads"]) == 1


@pytest.mark.parametrize("own_lineage", [False, True])
def test_cached_ip_alias_cannot_suppress_its_own_lineage(own_lineage):
    setup = mode_setup("yes", names="192.0.2.10")
    setup += f'STORE["plugin_letsencrypt_192.0.2.10"]={{"old cert", "old key", {to_lua("192.0.2.10" if own_lineage else "other.example.com")}}}\n'
    setup += 'IP_SANS={"192.0.2.10"}\n'
    if own_lineage:
        setup += 'STORE["plugin_letsencrypt_ipcert_192.0.2.10"]={"old cert", "old key", "192.0.2.10"}\nREAD_ERROR="must not read"\n'
    out = run_init(setup)
    assert out["result"] == {"ret": True, "msg": "success"}
    assert len(out["reads"]) == (0 if own_lineage else 1)
    assert out["store"]["plugin_letsencrypt_ip_names"] == {"192.0.2.10": "192.0.2.10"}
    assert out["store"]["plugin_letsencrypt_192.0.2.10"][0] == ("old cert" if own_lineage else "parsed:cert:192.0.2.10")


def test_cached_hostname_collects_only_verified_ip_indexes_without_disk_io():
    out = run_init(mode_setup("yes", names="app.example.com 192.0.2.10") + r"""
STORE["plugin_letsencrypt_app.example.com"]={"cert", "key", "app.example.com"}
STORE["plugin_letsencrypt_ipcert_192.0.2.10"]={"cert", "key", "app.example.com"}
READ_ERROR="must not read"
""")
    assert out["result"] == {"ret": True, "msg": "success"}
    assert out["reads"] == {}
    assert out["store"]["plugin_letsencrypt_ip_names"] == {"192.0.2.10": "app.example.com"}
