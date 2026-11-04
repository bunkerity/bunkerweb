"""Bad behavior must never count, and so never ban, a whitelisted or already banned client.

Whitelisted clients got banned by ``badbehavior`` because the log phase compared the whitelist verdict to ``"yes"`` (the
verdict is a boolean), requests served by the default server were never whitelist-checked, and a request that skipped the
access phase was only checked against the ctx flag. Separately the timer re-counted IPs that were already banned. This
test runs the real ``badbehavior.lua`` log and timer phases against recording stand-ins and asserts no counter operation
is queued (or applied) for those clients, and that the counter metrics never carry request data in their key.
Refs: #922, #2907, #275, #3448, #3475, #3758.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
VARIABLES = {
    USE_BAD_BEHAVIOR = "yes", BAD_BEHAVIOR_STATUS_CODES = "400 401 403 404 405 429 444",
    BAD_BEHAVIOR_BAN_SCOPE = "service", BAD_BEHAVIOR_BAN_TIME = "3600", BAD_BEHAVIOR_COUNT_TIME = "60", BAD_BEHAVIOR_THRESHOLD = "10",
}
"""


def log_phase(scenario=""):
    return run_plugin_script(
        "badbehavior",
        scenario + r"""
local ctx = { bw = { remote_addr = "203.0.113.9", server_name = "app.example.com", uri = "/probe", request_uri = "/probe?token=abc",
                    request_method = "GET", start_time = 1, request_id = "rid", ip_is_global = true, is_banned = CTX_BANNED } }
local r = PLUGIN:new(ctx):log()
emit({ msg = r.msg, queued = #RPUSHES, keys = metric_keys(), wl_calls = #WL_CALLS, banned_calls = #BANNED_CALLS })
""",
        header=HEADER,
    )


def test_a_client_flagged_whitelisted_in_ctx_is_not_counted():
    out = log_phase("WHITELISTED = true")
    assert out["msg"] == "client is whitelisted"
    assert out["queued"] == 0


def test_a_whitelisted_ip_found_by_lookup_is_not_counted_even_without_the_ctx_flag():
    out = log_phase("IP_WL = true")
    assert out["msg"].startswith("client is whitelisted (ip lookup")
    assert out["queued"] == 0
    assert out["wl_calls"] == 1


def test_a_lookup_error_does_not_whitelist_and_the_request_is_still_counted():
    out = log_phase('IP_WL_ERR = "cache down"')
    assert out["msg"] == "success"
    assert out["queued"] == 1


@pytest.mark.parametrize("scenario, msg", [("CTX_BANNED = true", "already banned (ctx)"), ("BANNED = true", "already banned")])
def test_an_already_banned_ip_is_not_counted_again_in_the_log_phase(scenario, msg):
    out = log_phase(scenario)
    assert out["msg"] == msg
    assert out["queued"] == 0


def test_counter_metric_keys_never_embed_request_data():
    out = log_phase()
    assert out["msg"] == "success" and out["queued"] == 1
    assert out["keys"] == ["counters:status_403", "tables:increments"]
    assert not any("203.0.113.9" in key or "probe" in key for key in out["keys"])


def timer_phase(banned):
    return run_plugin_script(
        "badbehavior",
        f"""
BANNED = {str(banned).lower()}
local incr = json.encode({{ ip = "203.0.113.9", count_time = 60, ban_time = 3600, threshold = 10, use_redis = false,
    server_name = "app.example.com", security_mode = "block", country = "FR", status = "403", ban_scope = "service" }})
DICT.incr[1] = incr
local plugin = PLUGIN:new({{ bw = {{}} }})
local increased = {{}}
function plugin:increase(ip) increased[#increased + 1] = ip return 1 end
local r = plugin:timer()
emit({{ increased = #increased, first = increased[1] or "none", banned_calls = #BANNED_CALLS, decr = #RPUSHES, logs = LOGS }})
""",
        header=HEADER,
    )


def test_the_timer_skips_the_counter_increase_of_an_already_banned_ip():
    out = timer_phase(True)
    assert out["increased"] == 0
    assert out["decr"] == 0
    assert out["banned_calls"] == 1
    assert any("skipped counter increase for already banned IP 203.0.113.9" in line for line in out["logs"])


def test_the_timer_still_counts_an_ip_that_is_not_banned():
    out = timer_phase(False)
    assert (out["increased"], out["first"]) == (1, "203.0.113.9")
    assert out["decr"] == 1
