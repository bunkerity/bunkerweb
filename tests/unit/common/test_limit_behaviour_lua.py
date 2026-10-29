"""Behaviour of ``limit.lua``: under vs over the rate, per-URL rules, the global cap, init.

Runs the real plugin under plain Lua (see ``_lua_request_helpers``). The clock is the harness's
``NOW`` and the counters live in a fake datastore, so the windows are deterministic.
"""

import pytest
from _lua_request_helpers import requires_lua, run

pytestmark = requires_lua

SETUP = r"""
VARIABLES = { USE_LIMIT_REQ = "yes" }
STORE["plugin_limit_rules"] = { global = RULES }
STORE["plugin_limit_global_rules"] = { global = GLOBAL_RATE }
"""


def requests(rules, uris, *, global_rate="nil", advance=0, mode="block", pre=""):
    """Send one request per entry of ``uris``; emit ``status<i>``, ``msg<i>`` and ``rate<i>``."""
    quoted = ", ".join(f'"{u}"' for u in uris)
    return run(
        "limit",
        f"""
RULES = {rules}
GLOBAL_RATE = {global_rate}
{SETUP}
SECURITY_MODE = "{mode}"
{pre}
for i, uri in ipairs({{ {quoted} }}) do
    if i == {len(uris)} then NOW = NOW + {advance} end
    local r = PLUGIN:new(ctx({{ uri = uri }})):access()
    emit("status" .. i, r.status) emit("msg" .. i, r.msg) emit("ret" .. i, r.ret)
    emit("rate" .. i, r.data and r.data.current_rate) emit("scope" .. i, r.data and r.data.scope)
end
emit("metrics", metric_keys())
""",
    )


class TestPerUriRate:
    RULES = '{ ["/"] = "2r/s" }'

    def test_requests_within_the_rate_pass(self):
        out = requests(self.RULES, ["/", "/"])
        assert out["status1"] == out["status2"] == "nil"
        assert out["msg2"].startswith("client IP 1.2.3.4 is not limited for URL /")

    def test_request_over_the_rate_is_429_with_the_counted_rate(self):
        out = requests(self.RULES, ["/", "/", "/"])
        assert out["status3"] == "429"
        assert out["rate3"] == "3"
        assert out["msg3"] == "client IP 1.2.3.4 is limited for URL / (current rate = 3r/s and max rate = 2r/s)"
        assert out["metrics"] == "counters:limited_uri_/"

    def test_the_window_slides_so_a_later_request_passes_again(self):
        out = requests(self.RULES, ["/", "/", "/", "/"], advance=5)
        assert out["status3"] == "429"
        assert out["status4"] == "nil"

    def test_detect_mode_reports_instead_of_claiming_a_block(self):
        out = requests(self.RULES, ["/", "/", "/"], mode="detect")
        assert out["msg3"].startswith("detected client IP 1.2.3.4 limit for URL /")

    def test_a_url_rule_beats_the_catch_all(self):
        out = requests('{ ["/"] = "100r/s", ["^/login"] = "1r/s" }', ["/login", "/login", "/other", "/other"])
        assert out["status2"] == "429"
        assert out["status4"] == "nil"
        assert out["metrics"] == "counters:limited_uri_^/login"

    def test_no_matching_rule_and_no_catch_all_lets_the_request_through(self):
        out = requests('{ ["^/login"] = "1r/s" }', ["/other"])
        assert out["status1"] == "nil"
        assert out["msg1"] == "no rule for /other"


class TestGlobalRate:
    def test_the_aggregate_cap_applies_before_any_url_rule(self):
        out = requests('{ ["/"] = "100r/s" }', ["/a", "/b"], global_rate='"1r/s"')
        assert out["status1"] == "nil"
        assert out["status2"] == "429"
        assert out["scope2"] == "global"
        assert out["metrics"] == "counters:limited_global"


class TestGuards:
    def test_whitelisted_client_is_never_counted(self):
        out = requests('{ ["/"] = "1r/s" }', ["/", "/", "/"], pre="WHITELISTED = true")
        assert {out["status1"], out["status2"], out["status3"]} == {"nil"}
        assert out["msg3"] == "client is whitelisted"

    def test_disabled_service_is_not_limited(self):
        out = run(
            "limit",
            r"""
VARIABLES = { USE_LIMIT_REQ = "no", USE_LIMIT_REQ_GLOBAL = "no" }
STORE["plugin_limit_rules"] = { global = { ["/"] = "1r/s" } }
local r = PLUGIN:new(ctx()):access()
emit("msg", r.msg) emit("status", r.status)
""",
        )
        assert out["msg"] == "limit request not enabled"
        assert out["status"] == "nil"

    def test_a_datastore_failure_is_an_error_not_a_pass(self):
        out = requests('{ ["/"] = "1r/s" }', ["/"], pre='DS_ERR = "boom"')
        assert out["ret1"] == "false"
        assert out["msg1"] == "limit_req_local failed : boom"


def test_init_stores_the_rules_per_service():
    out = run(
        "limit",
        r"""
VARIABLES = { USE_LIMIT_REQ = "yes" }
MULTI_VARS = { ["www.example.com"] = { USE_LIMIT_REQ = "yes", LIMIT_REQ_URL = "/api", LIMIT_REQ_RATE = "5r/m",
                                       USE_LIMIT_REQ_GLOBAL = "yes", LIMIT_REQ_GLOBAL_RATE = "50r/s" },
               other = { USE_LIMIT_REQ = "no", LIMIT_REQ_URL = "/x", LIMIT_REQ_RATE = "1r/s" } }
local r = PLUGIN:new(ctx()):init()
emit("msg", r.msg) emit("rate", STORE["plugin_limit_rules"]["www.example.com"]["/api"])
emit("other", STORE["plugin_limit_rules"].other) emit("global", STORE["plugin_limit_global_rules"]["www.example.com"])
""",
    )
    assert out["msg"] == "successfully loaded 1 limit rules for requests"
    assert out["rate"] == "5r/m"
    assert out["other"] == "nil"
    assert out["global"] == "50r/s"


@pytest.mark.parametrize("unit", ["s", "m", "h", "d"])
def test_every_rate_unit_is_a_counted_window(unit):
    out = requests(f'{{ ["/"] = "1r/{unit}" }}', ["/", "/"])
    assert out["status1"] == "nil"
    assert out["status2"] == "429"
