"""Failed Basic auth attempts must never mint metric keys from the client address or the attempted user name.

``authbasic`` counted ``failed_ip_<address>`` and ``failed_user_<name>``: both values come from the client, so every probing
address or guessed user name created a new cache slot, which grew the metrics cache until the UI ran out of memory. Those
values now stay fields of the event record. This test runs the real ``authbasic:access`` with wrong passwords and unknown
users and asserts the metric keys are the fixed ones. (``badbehavior`` has the same rule in
``test_issue_922_badbehavior_whitelist_regression.py``; ``limit`` is pinned by ``test_limit_behaviour_lua.py``.)
Refs: #3475.
"""

import pytest
from _t2_helpers import requires_lua, run_plugin

pytestmark = requires_lua

SCOPE = r"""
VARIABLES = { USE_AUTH_BASIC = "yes" }
MULTI_VARS = { global = { USE_AUTH_BASIC = "yes", AUTH_BASIC_LOCATION = "sitewide", AUTH_BASIC_TEXT = "",
                          AUTH_BASIC_USER = "alice", AUTH_BASIC_PASSWORD = "secret" } }
PLUGIN:new(ctx()):init()
"""


@pytest.mark.parametrize("user, password", [("alice", "wrong"), ("mallory-12345", "whatever"), ("a" * 40, "x")])
@pytest.mark.parametrize("remote_addr", ["203.0.113.77", "2001:db8::77"])
def test_a_failed_attempt_only_bumps_fixed_metric_keys(user, password, remote_addr):
    out = run_plugin(
        "authbasic",
        SCOPE + f"""
HEADERS = {{ authorization = basic_auth("{user}", "{password}") }}
local r = PLUGIN:new(ctx({{ uri = "/", remote_addr = "{remote_addr}" }})):access()
emit("status", r.status) emit("metrics", metric_keys())
""",
    )
    assert out["status"] == "401"
    assert out["metrics"] == "counters:failed_authbasic,tables:authentications"
    assert remote_addr not in out["metrics"] and user not in out["metrics"]
