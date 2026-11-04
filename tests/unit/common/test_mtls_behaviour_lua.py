"""Behaviour of ``mtls.lua``: per-path client-certificate enforcement and its fail-closed edge."""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua


def access(urls, uri, verify=None, *, enabled="yes", scope="global"):
    lua_urls = ", ".join(f'"{u}"' for u in urls)
    verify_line = f'ngx.var.ssl_client_verify = "{verify}"' if verify else ""
    return run(
        "mtls",
        f"""
VARIABLES = {{ USE_MTLS = "{enabled}" }}
STORE["plugin_mtls_configs"] = {{ ["{scope}"] = {{ {lua_urls} }} }}
{verify_line}
local r = PLUGIN:new(ctx({{ uri = "{uri}" }})):access()
emit("msg", r.msg) emit("status", r.status) emit("id", r.data and r.data.id)
emit("verify", r.data and r.data.verify) emit("error", r.data and r.data.error) emit("metrics", metric_keys())
""",
    )


def test_disabled_service_is_not_enforced():
    out = access(["^/admin"], "/admin", enabled="no")
    assert out["msg"] == "mTLS not enabled"
    assert out["status"] == "nil"


def test_service_without_per_path_rules_leaves_enforcement_to_the_tls_layer():
    out = run(
        "mtls",
        r"""
VARIABLES = { USE_MTLS = "yes" }
STORE["plugin_mtls_configs"] = {}
local r = PLUGIN:new(ctx()):access()
emit("msg", r.msg) emit("status", r.status)
""",
    )
    assert out["msg"] == "no per-path mTLS rules"
    assert out["status"] == "nil"


def test_uri_outside_the_protected_paths_needs_no_certificate():
    out = access(["^/admin"], "/public", verify="NONE")
    assert out["msg"] == "URI outside mTLS scope"
    assert out["status"] == "nil"


def test_valid_certificate_on_a_protected_path_passes():
    out = access(["^/admin"], "/admin/users", verify="SUCCESS")
    assert out["msg"] == "valid client certificate for /admin/users"
    assert out["status"] == "nil"
    assert out["metrics"] == "counters:passed_mtls"


@pytest.mark.parametrize("verify", ["NONE", "FAILED:certificate has expired", None])
def test_missing_or_invalid_certificate_on_a_protected_path_is_denied(verify):
    out = access(["^/admin"], "/admin", verify)
    assert out["status"] == "403"
    assert out["id"] == "mtls"
    shown = verify or "nil"
    assert out["verify"] == shown
    assert out["msg"] == f"client certificate required for /admin (ssl_client_verify={shown})"
    assert out["metrics"] == "counters:failed_mtls"


def test_a_rule_that_does_not_compile_denies_instead_of_leaving_the_path_open():
    out = access(["("], "/admin", verify="SUCCESS")
    assert out["status"] == "403"
    assert out["error"] == "invalid_regex"
    assert out["metrics"] == "counters:failed_mtls"


def test_server_rules_replace_the_global_ones():
    out = run(
        "mtls",
        r"""
VARIABLES = { USE_MTLS = "yes" }
STORE["plugin_mtls_configs"] = { global = { "^/g" }, ["www.example.com"] = { "^/s" } }
local r = PLUGIN:new(ctx({ uri = "/g" })):access()
emit("msg", r.msg) emit("status", r.status)
""",
    )
    assert out["msg"] == "URI outside mTLS scope"
    assert out["status"] == "nil"


class TestInit:
    def test_collects_the_numbered_urls_and_skips_blank_ones(self):
        out = run(
            "mtls",
            r"""
MULTI_VARS = { ["www.example.com"] = { USE_MTLS = "yes", MTLS_URL = "^/a", MTLS_URL_2 = " ^/b ", MTLS_URL_3 = "  ",
                                       MTLS_VERIFY_CLIENT = "optional" },
               off = { USE_MTLS = "no", MTLS_URL = "^/x" } }
local r = PLUGIN:new(ctx()):init()
local urls = STORE["plugin_mtls_configs"]["www.example.com"]
table.sort(urls)
emit("msg", r.msg) emit("urls", table.concat(urls, ",")) emit("off", STORE["plugin_mtls_configs"].off) emit("logs", #LOGS)
""",
        )
        assert out["msg"] == "loaded 2 per-path mTLS rule(s)"
        assert out["urls"] == "^/a,^/b"
        assert out["off"] == "nil"
        assert out["logs"] == "0"

    def test_warns_when_verify_client_on_makes_per_path_rules_moot(self):
        out = run(
            "mtls",
            r"""
MULTI_VARS = { global = { USE_MTLS = "yes", MTLS_URL = "^/a", MTLS_VERIFY_CLIENT = "on" } }
PLUGIN:new(ctx()):init()
emit("log", LOGS[1])
""",
        )
        assert out["log"].startswith("WARN: scope global sets MTLS_URL but MTLS_VERIFY_CLIENT=on")
