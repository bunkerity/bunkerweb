"""A degraded instance recovers complete credentials without opening a tokenless repair path."""

import shutil

import pytest

from test_api_empty_internalstore_lua import _variables, run

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua interpreter is not installed")

CHECK_ACCESS = """
local self = {}
api.initialize(self, { bw = { remote_addr = "127.0.0.1" } })
local token_ok = api.is_allowed_token(self)
local ip_ok = api.is_allowed_ip(self)
print(tostring(token_ok and ip_ok))
"""


@pytest.mark.parametrize(
    ("content", "store", "headers", "expected"),
    [
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=t\n", {}, {"authorization": "Bearer t"}, "true"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=\n", {}, {}, "true"),
        ("API_WHITELIST_IP=127.0.0.1\n", {}, {}, "false"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=", {}, {}, "false"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=t\n", {}, {}, "false"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=t\n", {}, {"authorization": "Bearer wrong"}, "false"),
        ("API_WHITELIST_IP=10.0.0.1\nAPI_TOKEN=t\n", {}, {"authorization": "Bearer t"}, "false"),
        ("API_TOKEN=t\n", {}, {"authorization": "Bearer t"}, "false"),
        ("", {}, {}, "false"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=stale\n", {"API_TOKEN": "live"}, {"authorization": "Bearer live"}, "true"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=stale\n", {"API_TOKEN": "live"}, {"authorization": "Bearer stale"}, "false"),
        ("API_WHITELIST_IP=127.0.0.1\nAPI_TOKEN=stale\n", {"API_TOKEN": ""}, {}, "true"),
    ],
    ids=[
        "complete",
        "explicit-empty-token",
        "missing-token",
        "partial-token-line",
        "missing-bearer",
        "wrong-bearer",
        "outside-whitelist",
        "missing-whitelist",
        "empty-file",
        "live-token",
        "stale-disk-token",
        "live-empty-token",
    ],
)
def test_disk_recovery_preserves_both_access_controls(tmp_path, content, store, headers, expected):
    path = _variables(tmp_path, content)
    assert run(CHECK_ACCESS, variables_path=path, store=store, headers=headers) == expected
