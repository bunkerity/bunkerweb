"""Certificate loading failures and SNI isolation, using the complete real plugins."""

import pytest
from _lua_plugin_helpers import CORE, LUA, run_module, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

PREAMBLE = r"""
local utils = package.loaded["bunkerweb.utils"]
utils.read_files = function() if READ_ERROR then return false, READ_ERROR end return true, {"cert", "key"} end
package.loaded["ngx.ssl"] = {
    parse_pem_cert = function(pem) if CERT_ERROR then return nil, CERT_ERROR end return "parsed:" .. pem end,
    parse_pem_priv_key = function(pem) if KEY_ERROR then return nil, KEY_ERROR end return "parsed:" .. pem end,
    server_name = function() return SNI, SNI_ERROR end,
}
local function public_key(which)
    return { tostring = function()
        if META_ERROR == which then return nil, "export failed" end
        return which == "private" and MISMATCH and "other" or "public-der"
    end }
end
package.loaded["resty.openssl.pkey"] = { new = function()
    if META_ERROR == "key" then return nil, "bad key" end return public_key("private")
end }
package.loaded["resty.openssl.x509"] = { new = function()
    if META_ERROR == "cert" then return nil, "bad cert" end
    return {
        get_not_before = function() return FUTURE and os.time() + 100 or 0 end,
        get_not_after = function() return EXPIRED and 0 or os.time() + 100 end,
        get_pubkey = function() if META_ERROR ~= "pubkey" then return public_key("public") end end,
        get_subject_alt_name = function()
            if META_ERROR == "san" then return nil, "bad SAN" end
            if NO_SAN then return nil end
            return { each = function()
                local i = 0
                return function() i = i + 1; if DNS_NAMES[i] then return "DNS", DNS_NAMES[i] end end
            end }
        end,
        get_subject_name = function()
            if NO_SUBJECT then return nil end
            return { find = function() if CN then return {blob = CN} end end }
        end,
    }
end }
"""


def run_cert(name, body, setup=""):
    return run_module(
        CORE / name / f"{name}.lua",
        setup + r"""
local p = new_plugin(PLUGIN)
p.internalstore.get = function(_, key)
    if GET_ERROR == key then return nil, "cache broken" end
    if STORE[key] == nil then return nil, "not found" end
    return STORE[key]
end
p.internalstore.set = function(_, key, value)
    if SET_ERROR == key then return false, "cache full" end
    STORE[key] = value
    return true
end
""" + body,
        preamble=PREAMBLE,
    )


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
@pytest.mark.parametrize("failure, message", [("CERT_ERROR", "pem cert"), ("KEY_ERROR", "pem priv key"), ("SET_ERROR", "internalstore")])
def test_load_failure_does_not_publish_certificate(name, failure, message):
    value = f"plugin_{name}_app.example.com" if failure == "SET_ERROR" else "invalid PEM"
    out = run_cert(
        name,
        'local ok, err = p:load_data({"cert", "key"}, "app.example.com")\nemit({ok=ok, err=err, store=STORE})',
        f"{failure} = {to_lua(value)}\n",
    )
    assert out["ok"] is False
    assert message in out["err"]
    assert f"plugin_{name}_app.example.com" not in out["store"]


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
def test_loaded_aliases_select_only_their_own_certificate(name):
    out = run_cert(
        name,
        r"""
assert(p:load_data({"cert-a", "key-a"}, "app.example.com alias.example.com"))
assert(p:load_data({"cert-b", "key-b"}, "other.example.com"))
SNI = "alias.example.com"; local alias = p:ssl_certificate()
SNI = "other.example.com"; local other = p:ssl_certificate()
SNI = "missing.example.com"; local missing = p:ssl_certificate()
emit({alias=alias, other=other, missing=missing})
""",
    )
    assert out["alias"]["status"] == ["parsed:cert-a", "parsed:key-a"]
    assert out["other"]["status"] == ["parsed:cert-b", "parsed:key-b"]
    assert out["missing"]["ret"] is True
    assert "status" not in out["missing"]


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
@pytest.mark.parametrize("error", [False, True])
def test_no_sni_and_sni_lookup_error(name, error):
    out = run_cert(name, "emit(p:ssl_certificate())", 'SNI_ERROR = "unavailable"\n' if error else "")
    assert out["ret"] is (not error)
    assert out["msg"] == ("can't get server_name : unavailable" if error else "no SNI provided")
    assert "status" not in out


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
def test_certificate_cache_error_stops_selection(name):
    out = run_cert(name, "emit(p:ssl_certificate())", f'SNI="app.example.com"; GET_ERROR="plugin_{name}_app.example.com"\n')
    assert out["ret"] is False
    assert "cache broken" in out["msg"]
    assert "status" not in out


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
@pytest.mark.parametrize("multisite", ["yes", "no"])
@pytest.mark.parametrize("failure", ["read", "load", "none"])
def test_init_loads_service_data_and_reports_io_errors(name, multisite, failure):
    setting = "USE_CUSTOM_SSL" if name == "customcert" else "GENERATE_SELF_SIGNED_SSL"
    setup = f"""
HAS_VARIABLE=true
GETVAR={{MULTISITE={to_lua(multisite)}, SERVER_NAME="app.example.com alias.example.com"}}
MULTI_VARS={{["app.example.com"]={{[{to_lua(setting)}]="yes", SERVER_NAME="app.example.com alias.example.com"}},
 global={{[{to_lua(setting)}]="yes"}}, ["disabled.example.com"]={{[{to_lua(setting)}]="no"}}}}
DNS_NAMES={{}}
"""
    setup += 'READ_ERROR="disk error"\n' if failure == "read" else 'KEY_ERROR="bad key"\n' if failure == "load" else ""
    out = run_cert(name, "local result=p:init(); emit({result=result, store=STORE, logs=LOGS})", setup)
    assert out["result"]["ret"] is (failure == "none")
    if failure == "none":
        assert out["store"][f"plugin_{name}_alias.example.com"] == ["parsed:cert", "parsed:key"]
        assert f"plugin_{name}_disabled.example.com" not in out["store"]
    else:
        assert out["result"]["msg"] == ("error reading files" if failure == "read" else "error loading data")
        assert any("error while" in line[1] for line in out["logs"])


@pytest.mark.parametrize("name", ["customcert", "selfsigned"])
@pytest.mark.parametrize("failure", ["disabled", "multisite", "multiple", "server"])
def test_init_variable_failures_and_disabled_feature(name, failure):
    setup = 'HAS_VARIABLE=true; GETVAR={MULTISITE="no", SERVER_NAME="app.example.com"}\n'
    setup += {
        "disabled": "HAS_VARIABLE=false\n",
        "multisite": "GETVAR.MULTISITE=nil\n",
        "multiple": 'GETVAR.MULTISITE="yes"; MULTI_ERR="db error"\n',
        "server": "GETVAR.SERVER_NAME=nil\n",
    }[failure]
    out = run_cert(name, "emit(p:init())", setup)
    assert out["ret"] is (failure == "disabled")
    assert ("not used" if failure == "disabled" else "can't get") in out["msg"]


@pytest.mark.parametrize("key", ["excluded", "bases", "certificates"])
def test_customcert_metadata_cache_write_errors(key):
    out = run_cert(name="customcert", body="emit(p:init())", setup=f'HAS_VARIABLE=false; SET_ERROR="plugin_customcert_wildcard_{key}"\n')
    assert out["ret"] is False
    assert "cache full" in out["msg"]


@pytest.mark.parametrize("key", ["excluded", "bases", "certificates"])
def test_customcert_metadata_cache_read_errors(key):
    out = run_cert(
        "customcert",
        "emit(p:ssl_certificate())",
        f'SNI="app.example.com"; STORE.plugin_customcert_wildcard_bases={{"example.com"}}; GET_ERROR="plugin_customcert_wildcard_{key}"\n',
    )
    assert out["ret"] is False
    assert "cache broken" in out["msg"]
    assert "status" not in out


@pytest.mark.parametrize(
    "sni, selected",
    [("App.Example.COM.", True), ("deep.app.example.com", False), ("example.com", False), ("badexample.com", False), ("disabled.example.com", False)],
)
def test_wildcard_selection_respects_label_boundary_and_opt_out(sni, selected):
    out = run_cert(
        "customcert",
        'assert(p:load_data({"wild", "key"}, "owner.example.com", wildcards)); STORE.plugin_customcert_wildcard_certificates=wildcards; emit(p:ssl_certificate())',
        f'SNI={to_lua(sni)}; DNS_NAMES={{"*.example.com"}}; local wildcards={{}}; STORE.plugin_customcert_wildcard_bases={{"example.com"}}; STORE.plugin_customcert_wildcard_excluded={{["disabled.example.com"]=true}}\n',
    )
    assert out["ret"] is True
    assert out.get("status") == (["parsed:wild", "parsed:key"] if selected else None)


@pytest.mark.parametrize(
    "setup, warning",
    [
        ('META_ERROR="cert"', "certificate metadata"),
        ('META_ERROR="key"', "private key metadata"),
        ('META_ERROR="pubkey"', "certificate public key"),
        ('META_ERROR="public"', "export certificate"),
        ('META_ERROR="private"', "export private key"),
        ('META_ERROR="san"', "DNS names"),
        ("MISMATCH=true", "do not match"),
        ("FUTURE=true", "not currently valid"),
        ("EXPIRED=true", "not currently valid"),
    ],
)
def test_invalid_wildcard_metadata_keeps_exact_cert_but_cannot_borrow_it(setup, warning):
    out = run_cert(
        "customcert",
        'local wildcards={}; assert(p:load_data({"cert", "key"}, "owner.example.com", wildcards)); emit({wildcards=wildcards, store=STORE, logs=LOGS})',
        setup + '; DNS_NAMES={"*.example.com"}\n',
    )
    assert out["wildcards"] == {}
    assert out["store"]["plugin_customcert_owner.example.com"] == ["parsed:cert", "parsed:key"]
    assert any(warning in line[1] for line in out["logs"])


@pytest.mark.parametrize(
    "setup, wildcard",
    [('NO_SAN=true; CN="*.Example.COM."', True), ("NO_SAN=true; NO_SUBJECT=true", False), ('DNS_NAMES={"app.example.com"}; CN="*.example.com"', False)],
)
def test_wildcard_metadata_uses_cn_only_without_dns_san(setup, wildcard):
    out = run_cert(
        "customcert",
        'local wildcards={}; assert(p:load_data({"cert", "key"}, "owner.example.com", wildcards)); emit(wildcards)',
        setup + "\n",
    )
    assert ("example.com" in out) is wildcard
