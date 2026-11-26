"""Request path of ``mtls.lua``: plain HTTP policy, ACME exemption, detect mode, startup regex report.

The real ``mtls.lua`` runs under plain Lua with OpenResty stubbed (``_lua_request_helpers.py``); the prefix
check of ``bunkerweb.acme`` is the real module, whether a local solver owns a token is the scenario's call.
Covers spec items S1 (``MTLS_HTTP_POLICY``), S6 (``init_worker`` report) and the amendments A1, A2, A3, B1, B2,
B4, C1 and C2 of the mTLS fix wave.
"""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua


def lua(value):
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, dict):
        return "{" + ", ".join(f"[{lua(k)}] = {lua(v)}" for k, v in value.items()) + "}"
    return "{" + ", ".join(lua(v) for v in value) + "}"


def access(
    *,
    mode="on",
    policy=None,
    urls=(),
    scheme="http",
    uri="/",
    method="GET",
    host="www.example.com",
    request_uri=None,
    verify=None,
    acme_local=False,
    getvar=None,
    security_mode="block",
    extra_variables=None,
):
    variables = {"USE_MTLS": "yes", "MTLS_VERIFY_CLIENT": mode, **(extra_variables or {})}
    if policy is not None:
        variables["MTLS_HTTP_POLICY"] = policy
    bw = {"uri": uri, "scheme": scheme, "request_method": method, "request_uri": request_uri if request_uri is not None else uri}
    if host is not None:
        bw["http_host"] = host
    out = run(
        "mtls",
        f"""
VARIABLES = {lua(variables)}
STORE["plugin_mtls_configs"] = {{ global = {lua(list(urls))} }}
GETVAR = {lua(getvar or {})}
ACME_LOCAL = {lua(acme_local)}
SECURITY_MODE = {lua(security_mode)}
{f'ngx.var.ssl_client_verify = {lua(verify)}' if verify else ""}
local r = PLUGIN:new(ctx({lua(bw)})):access()
emit("ret", r.ret) emit("msg", r.msg) emit("status", r.status) emit("redirect", r.redirect)
emit("id", r.data and r.data.id) emit("verify", r.data and r.data.verify) emit("policy", r.data and r.data.policy) emit("error", r.data and r.data.error)
emit("metrics", metric_keys()) emit("logs", table.concat(LOGS, " | "))
""",
    )
    return out


def verdict(out):
    """(status, redirect) as the access dispatcher would see them: ``"nil"`` is no verdict."""
    return out["status"], out["redirect"]


NOTHING = ("nil", "nil")
DENIED = ("403", "nil")
REDIRECTED = ("301", "https://www.example.com/page?x=1")


class TestPlainHttpPolicy:
    """S1: server-wide ``on`` is not reachable over plain HTTP; MTLS_URL paths follow the same policy."""

    @pytest.mark.parametrize(("policy", "expected"), [(None, REDIRECTED), ("redirect", REDIRECTED), ("deny", DENIED), ("allow", NOTHING)])
    def test_server_wide_mode_without_rules(self, policy, expected):
        out = access(mode="on", policy=policy, uri="/page", request_uri="/page?x=1")
        assert verdict(out) == expected
        if expected == DENIED:
            assert out["id"] == "mtls" and out["policy"] == "deny"
            assert out["metrics"] == "counters:failed_mtls"

    def test_every_path_is_in_scope_under_server_wide_mode(self):
        for uri in ("/", "/public/logo.png", "/admin"):
            assert verdict(access(policy="deny", uri=uri)) == DENIED

    @pytest.mark.parametrize(("policy", "expected"), [("redirect", REDIRECTED), ("deny", DENIED), ("allow", NOTHING)])
    def test_server_wide_mode_with_rules_still_covers_the_other_paths(self, policy, expected):
        out = access(mode="on", policy=policy, urls=["^/admin"], uri="/page", request_uri="/page?x=1")
        assert verdict(out) == expected

    @pytest.mark.parametrize("mode", ["optional", "optional_no_ca"])
    @pytest.mark.parametrize("policy", ["redirect", "deny", "allow"])
    def test_optional_modes_without_rules_enforce_nothing_on_http(self, mode, policy):
        out = access(mode=mode, policy=policy, urls=[])
        assert out["msg"] == "no per-path mTLS rules"
        assert verdict(out) == NOTHING

    @pytest.mark.parametrize("mode", ["optional", "optional_no_ca"])
    @pytest.mark.parametrize(("policy", "expected"), [("redirect", REDIRECTED), ("deny", DENIED), ("allow", DENIED)])
    def test_a_rule_match_follows_the_policy_and_stays_denied_under_allow(self, mode, policy, expected):
        out = access(mode=mode, policy=policy, urls=["^/page"], uri="/page", request_uri="/page?x=1")
        assert verdict(out) == expected

    @pytest.mark.parametrize("policy", ["redirect", "deny", "allow"])
    def test_a_path_outside_the_rules_is_untouched(self, policy):
        out = access(mode="optional", policy=policy, urls=["^/admin"], uri="/public")
        assert out["msg"] == "URI outside mTLS scope"
        assert verdict(out) == NOTHING

    @pytest.mark.parametrize("policy", ["redirect", "deny", "allow"])
    def test_a_rule_that_does_not_compile_still_fails_closed_over_http(self, policy):
        out = access(mode="optional", policy=policy, urls=["("], uri="/anything")
        assert verdict(out) == DENIED
        assert out["error"] == "invalid_regex"

    def test_a_missing_or_unknown_policy_is_the_secure_default(self):
        for policy in (None, "", "bogus", "REDIRECT"):
            assert verdict(access(policy=policy, uri="/page", request_uri="/page?x=1")) == REDIRECTED

    def test_a_missing_verify_mode_is_treated_as_on(self):
        variables = {"USE_MTLS": "yes"}
        out = run(
            "mtls",
            f"""
VARIABLES = {lua(variables)}
STORE["plugin_mtls_configs"] = {{}}
local r = PLUGIN:new(ctx({{ scheme = "http", uri = "/", request_uri = "/", http_host = "www.example.com" }})):access()
emit("status", r.status) emit("redirect", r.redirect)
""",
        )
        assert (out["status"], out["redirect"]) == ("301", "https://www.example.com/")

    @pytest.mark.parametrize(
        "bw",
        [
            {"host": None},
            {"host": ""},
            {"host": "a@evil.example"},
            {"host": "evil.example/x"},
            {"host": "evil.example\\x"},
            {"host": "a b"},
            {"host": "x" * 256},
            {"request_uri": "http://evil.example/"},
            {"request_uri": ""},
        ],
    )
    def test_redirect_without_a_usable_host_or_uri_denies_instead(self, bw):
        out = access(policy="redirect", uri="/page", **bw)
        assert verdict(out) == DENIED
        assert out["policy"] == "redirect"
        assert "without a usable Host or URI" in out["msg"]

    def test_the_redirect_keeps_the_host_port_the_ssl_plugin_does_too(self):
        out = access(policy="redirect", uri="/p", request_uri="/p?q=1", host="[::1]:8080")
        assert verdict(out) == ("301", "https://[::1]:8080/p?q=1")

    @pytest.mark.parametrize("mode", ["on", "optional", "optional_no_ca"])
    @pytest.mark.parametrize("policy", ["redirect", "deny", "allow"])
    def test_https_requests_are_unchanged(self, mode, policy):
        out = access(mode=mode, policy=policy, scheme="https", urls=[], uri="/page")
        assert out["msg"] == "no per-path mTLS rules"
        assert verdict(out) == NOTHING
        out = access(mode=mode, policy=policy, scheme="https", urls=["^/page"], uri="/page", verify="SUCCESS")
        assert out["msg"] == "valid client certificate for /page"
        out = access(mode=mode, policy=policy, scheme="https", urls=["^/page"], uri="/page", verify="NONE")
        assert verdict(out) == DENIED and out["verify"] == "NONE"

    def test_a_request_that_is_not_plain_http_gets_no_http_policy(self):
        out = access(policy="deny", scheme="", urls=[], uri="/page")
        assert verdict(out) == NOTHING

    def test_a_service_without_mtls_is_not_touched(self):
        out = access(extra_variables={"USE_MTLS": "no"}, policy="deny")
        assert out["msg"] == "mTLS not enabled" and verdict(out) == NOTHING


TOKEN = "/.well-known/acme-challenge/abc_DEF-123"


class TestAcmeChallengeExemption:
    """B1, C1, C2: only a challenge a solver owns is exempt; everything else gets the policy."""

    @pytest.mark.parametrize("policy", ["redirect", "deny", "allow"])
    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    def test_a_token_the_local_solver_owns_reaches_it(self, policy, method):
        out = access(policy=policy, uri=TOKEN, method=method, acme_local=True)
        assert out["msg"] == "ACME HTTP-01 challenge reaches its solver without mTLS"
        assert verdict(out) == NOTHING

    @pytest.mark.parametrize("variable", ["LETS_ENCRYPT_PASSTHROUGH", "ACME_PASSTHROUGH"])
    @pytest.mark.parametrize("method", ["GET", "HEAD"])
    def test_a_passthrough_switch_exempts_one_token_segment(self, variable, method):
        out = access(policy="deny", uri=TOKEN, method=method, getvar={variable: "yes"})
        assert verdict(out) == NOTHING
        assert out["msg"].startswith("ACME HTTP-01 challenge")

    @pytest.mark.parametrize("variable", ["LETS_ENCRYPT_PASSTHROUGH", "ACME_PASSTHROUGH"])
    def test_a_passthrough_switch_that_is_off_exempts_nothing(self, variable):
        assert verdict(access(policy="deny", uri=TOKEN, getvar={variable: "no"})) == DENIED

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "OPTIONS", "get"])
    @pytest.mark.parametrize("solver", [{"acme_local": True}, {"getvar": {"LETS_ENCRYPT_PASSTHROUGH": "yes"}}, {"getvar": {"ACME_PASSTHROUGH": "yes"}}])
    def test_the_method_is_checked_on_every_branch(self, method, solver):
        # a POST to an existing token (file present) or on a passthrough service is not exempted
        assert verdict(access(policy="deny", uri=TOKEN, method=method, **solver)) == DENIED

    @pytest.mark.parametrize(
        "uri",
        [
            "/.well-known/acme-challenge/x/y",
            "/.well-known/acme-challenge/",
            "/.well-known/acme-challenge",
            "/.well-known/acme-challenge/tok%2f",
            "/.well-known/acme-challenge/tok.txt",
            "/.well-known/acme-challenge/../admin",
            "/x/.well-known/acme-challenge/tok",
            "/.well-known/security.txt",
        ],
    )
    @pytest.mark.parametrize("solver", [{"acme_local": True}, {"getvar": {"LETS_ENCRYPT_PASSTHROUGH": "yes", "ACME_PASSTHROUGH": "yes"}}])
    def test_only_one_token_shaped_segment_is_exempt(self, uri, solver):
        assert verdict(access(policy="deny", uri=uri, **solver)) == DENIED

    def test_a_token_shaped_path_with_no_solver_gets_the_policy(self):
        assert verdict(access(policy="deny", uri=TOKEN)) == DENIED
        assert verdict(access(policy="redirect", uri=TOKEN, request_uri=TOKEN)) == ("301", "https://www.example.com" + TOKEN)

    def test_an_application_path_never_gets_the_exemption(self):
        out = access(policy="deny", uri="/app/data", acme_local=True, getvar={"LETS_ENCRYPT_PASSTHROUGH": "yes", "ACME_PASSTHROUGH": "yes"})
        assert verdict(out) == DENIED

    def test_the_exemption_is_http_only(self):
        # over HTTPS the TLS layer, not this policy, decides; the exemption must not widen the per-path check
        out = access(mode="optional", scheme="https", urls=["^/%.well"], uri=TOKEN, acme_local=True, verify="NONE")
        assert verdict(out) == DENIED

    def test_the_exemption_also_covers_a_challenge_under_an_mtls_rule(self):
        # the solvers answered before mtls moved up in the order, so the challenge was never denied by it
        out = access(mode="optional", policy="allow", urls=["^/"], uri=TOKEN, acme_local=True)
        assert verdict(out) == NOTHING


class TestDetectMode:
    """A3, B2: in SECURITY_MODE=detect the plugin logs the verdict and lets the chain go on."""

    @pytest.mark.parametrize("policy", ["redirect", "deny"])
    def test_http_policy_is_not_enforced_but_logged(self, policy):
        out = access(policy=policy, uri="/page", request_uri="/page?x=1", security_mode="detect")
        assert out["ret"] == "true" and verdict(out) == NOTHING
        assert out["msg"].startswith("detect mode, not enforced")
        kind = "redirect" if policy == "redirect" else "deny"
        assert f"WARN: detected {kind} access from mtls" in out["logs"]

    @pytest.mark.parametrize("policy", ["redirect", "deny"])
    def test_the_same_request_is_enforced_in_block_mode(self, policy):
        out = access(policy=policy, uri="/page", request_uri="/page?x=1", security_mode="block")
        assert verdict(out) == (REDIRECTED if policy == "redirect" else DENIED)
        assert "detected" not in out["logs"]

    def test_a_per_path_denial_does_not_stop_the_later_plugins_either(self):
        out = access(mode="optional", scheme="https", urls=["^/admin"], uri="/admin", verify="NONE", security_mode="detect")
        assert verdict(out) == NOTHING
        assert "WARN: detected deny access from mtls" in out["logs"]
        assert out["metrics"] == "counters:failed_mtls"

    def test_an_invalid_rule_is_not_enforced_in_detect_mode_but_is_logged(self):
        out = access(mode="optional", scheme="https", urls=["("], uri="/x", security_mode="detect")
        assert verdict(out) == NOTHING
        assert "invalid MTLS_URL regex" in out["logs"]

    def test_a_valid_certificate_is_not_affected(self):
        out = access(mode="optional", scheme="https", urls=["^/admin"], uri="/admin", verify="SUCCESS", security_mode="detect")
        assert out["msg"] == "valid client certificate for /admin"


class TestInitWorkerRegexReport:
    """S6, B4: every MTLS_URL rule is compiled at worker start and a broken one is reported by name."""

    @staticmethod
    def report(configs, *, subsystem="http"):
        return run(
            "mtls",
            f"""
STORE["plugin_mtls_configs"] = {lua(configs)}
PHASE = "timer"
local r = PLUGIN:new():init_worker()
emit("ret", r.ret) emit("msg", r.msg) emit("status", r.status) emit("logs", table.concat(LOGS, " | "))
emit("count", #LOGS)
""",
            subsystem=subsystem,
        )

    def test_a_broken_rule_is_reported_with_its_service_and_pattern(self):
        out = self.report({"www.example.com": ["^/ok", "("], "global": ["^/fine"]})
        assert out["ret"] == "true" and out["status"] == "nil"
        assert out["count"] == "1"
        assert out["logs"].startswith("ERR: invalid MTLS_URL regex for service www.example.com (() : bad pattern")
        assert out["msg"] == "1 invalid MTLS_URL regex(es)"

    def test_the_global_scope_is_named_as_such(self):
        out = self.report({"global": ["("]})
        assert "for the global scope (()" in out["logs"]

    def test_every_broken_rule_is_reported_once_in_a_stable_order(self):
        out = self.report({"b.example.com": ["("], "a.example.com": ["("]})
        lines = out["logs"].split(" | ")
        assert len(lines) == 2 and "a.example.com" in lines[0] and "b.example.com" in lines[1]

    def test_valid_rules_log_nothing(self):
        out = self.report({"global": ["^/a", "^/b"]})
        assert out["count"] == "0" and out["msg"] == "all MTLS_URL regexes compile"

    def test_nothing_to_check_is_not_an_error(self):
        out = run("mtls", 'PHASE = "timer"\nlocal r = PLUGIN:new():init_worker()\nemit("ret", r.ret) emit("count", #LOGS)')
        assert out["ret"] == "true" and out["count"] == "0"

    def test_the_stream_vm_does_not_report_a_second_time(self):
        out = self.report({"global": ["("]}, subsystem="stream")
        assert out["count"] == "0" and out["msg"] == "MTLS_URL rules are HTTP only"


def test_mtls_runs_right_after_ssl_and_before_the_whitelist():
    """S2: a whitelist match must not skip mTLS; PLUGINS_ORDER_ACCESS restores the old precedence."""
    import json

    from _lua_request_helpers import ROOT

    access = json.loads((ROOT / "src" / "common" / "core" / "order.json").read_text())["access"]
    assert access.index("mtls") == access.index("ssl") + 1
    assert access.index("mtls") < access.index("whitelist") < access.index("letsencrypt")


_ORDER_SETUP = r"""
package.loaded["resty.core.base"] = { get_request = function() end }
package.loaded["bunkerweb.ctx"] = { apply_ref = function() end, stash_ref = function() end }
package.loaded["bunkerweb.utils"] = { get_phases = function() return PHASES end }
local real_open = io.open
io.open = function(path, mode)
    if path == "/usr/share/bunkerweb/core/order.json" then return real_open(ORDER_JSON, mode) end
    return real_open(path, mode)
end
local helpers = dofile(BW_LUA .. "/bunkerweb/helpers.lua")
io.open = real_open
local plugins = {}
for _, id in ipairs(IDS) do plugins[#plugins + 1] = { id = id, phases = { "access" } } end
local ok, orders = helpers.order_plugins(plugins, { global = GLOBALS })
assert(ok, orders)
emit(orders.access)
"""


def _access_order(overrides=None):
    """The access order the Lua core computes from the shipped order.json and the shipped setting defaults.

    ``variables.env`` carries every setting, defaults included, and ``helpers.load_variables`` copies each one
    to ``variables.global``: so a non-empty ``PLUGINS_ORDER_*`` default reaches ``order_plugins`` as an override.
    """
    import json
    import re

    from _lua_core_helpers import run_core  # type: ignore
    from _lua_request_helpers import ROOT

    order_json = ROOT / "src" / "common" / "core" / "order.json"
    settings = json.loads((ROOT / "src" / "common" / "settings.json").read_text())
    defaults = {key: data["default"] for key, data in settings.items() if key.startswith("PLUGINS_ORDER_")}
    defaults.update(overrides or {})
    phases = re.search(r"utils\.get_phases = function\(\)\s*return (\{.*?\})", (ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua").read_text(), re.S)
    ids = json.loads(order_json.read_text())["access"]
    # The phase list is a Lua table literal of strings: a JSON list once the braces are swapped.
    return run_core(
        ROOT / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua",
        _ORDER_SETUP,
        PHASES=json.loads("[" + phases.group(1)[1:-1].rstrip().rstrip(",") + "]"),
        ORDER_JSON=str(order_json),
        IDS=ids,
        GLOBALS=defaults,
    )


def test_default_plugins_order_access_keeps_mtls_before_the_whitelist():
    """The shipped PLUGINS_ORDER_ACCESS default is an override: it must not push mtls behind the whitelist."""
    order = _access_order()
    assert order.index("mtls") == order.index("ssl") + 1
    assert order.index("mtls") < order.index("whitelist")


def test_an_explicit_plugins_order_access_still_restores_the_old_precedence():
    order = _access_order({"PLUGINS_ORDER_ACCESS": "ssl whitelist mtls"})
    assert order.index("whitelist") < order.index("mtls")
