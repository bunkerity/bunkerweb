"""Plugin instances must never modify the lists the internalstore shares between requests.

The list plugins and ``robotstxt`` assigned the table read from the internalstore to the new plugin instance and then
appended the settings values to it, so every request grew the shared list: ``robots.txt`` repeated its lines more with each
request. This test builds each plugin twice against one stored table and asserts the stored table is untouched and the second
instance is identical to the first.
Refs: #3012.
"""

import pytest
from _t2_helpers import LUA, run_plugin_script

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

HEADER = r"""
PHASE = "access"
VARIABLES = setmetatable({ USE_BLACKLIST = "yes", USE_GREYLIST = "yes", USE_WHITELIST = "yes", USE_DNSBL = "yes", USE_ROBOTSTXT = "yes" }, {
    __index = function(_, key) if key:match("_IP$") and not key:match("IGNORE") then return "203.0.113.5" end return "" end,
})
"""


@pytest.mark.parametrize("plugin", ["blacklist", "greylist", "whitelist"])
def test_list_plugins_work_on_a_copy_of_the_stored_lists(plugin):
    out = run_plugin_script(
        plugin,
        f"""
local key = "plugin_{plugin}_lists_app.example.com"
STORE[key] = {{ IP = {{ "192.0.2.1" }}, IGNORE_IP = {{ "192.0.2.9" }} }}
local ctx = {{ bw = {{ server_name = "app.example.com", remote_addr = "1.2.3.4", uri = "/" }} }}
local first = PLUGIN:new(ctx)
table.insert(first.lists.IP, "leaked-by-first-request")
local second = PLUGIN:new(ctx)
emit({{ stored = STORE[key].IP, stored_ignore = STORE[key].IGNORE_IP, second = second.lists.IP }})
""",
        header=HEADER,
    )
    assert out["stored"] == ["192.0.2.1"]
    assert out["stored_ignore"] == ["192.0.2.9"]
    assert out["second"] == ["192.0.2.1", "203.0.113.5"]


def test_dnsbl_works_on_a_copy_of_the_stored_lists():
    out = run_plugin_script(
        "dnsbl",
        """
local key = "plugin_dnsbl_lists_app.example.com"
VARIABLES.DNSBL_IGNORE_IP = "203.0.113.5"
STORE[key] = { IGNORE_IP = { "192.0.2.9" } }
local ctx = { bw = { server_name = "app.example.com", remote_addr = "1.2.3.4", uri = "/" } }
local first = PLUGIN:new(ctx)
table.insert(first.lists.IGNORE_IP, "leaked-by-first-request")
local second = PLUGIN:new(ctx)
emit({ stored = STORE[key].IGNORE_IP, second = second.lists.IGNORE_IP })
""",
        header=HEADER,
    )
    assert out["stored"] == ["192.0.2.9"]
    assert out["second"] == ["192.0.2.9", "203.0.113.5"]


def test_robotstxt_rules_do_not_pile_up_across_requests():
    out = run_plugin_script(
        "robotstxt",
        """
local key = "plugin_robotstxt_rules_app.example.com"
STORE[key] = { "Disallow: /stored" }
VARIABLES = { USE_ROBOTSTXT = "yes", MULTISITE = "yes" }
MULTI_VARS = { ["app.example.com"] = { ROBOTSTXT_RULE = "Disallow: /env" } }
UTILS = { get_variable = function() return "yes" end }
local ctx = { bw = { server_name = "app.example.com", uri = "/robots.txt" } }
local lengths = {}
for i = 1, 3 do
    local p = PLUGIN:new(ctx)
    lengths[i] = #p.policies.rule
end
emit({ stored = #STORE[key], lengths = lengths })
""",
        header=HEADER,
    )
    assert out["stored"] == 1
    assert out["lengths"] == [2, 2, 2]
