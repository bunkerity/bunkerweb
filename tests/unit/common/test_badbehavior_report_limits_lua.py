"""Evidence is bounded independently of ban enforcement and shared event history."""

import json
import re
from pathlib import Path

import pytest

from test_badbehavior_ban_clears_counter import _run, needs_lua

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "src/common/core/badbehavior"


@needs_lua
@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_custom_limits_keep_newest_matching_events_without_mutating_history(subsystem):
    _run(
        """
local bb = new_plugin()
bb.increase = function() return 12 end
local url = string.rep("雪", 10)
local method = string.rep("X", 20)
for _, n in ipairs({1, 3, 2}) do
    table.insert(metric_tables.increments, {
        ip = "192.0.2.1", server_name = "a.example.com", date = n, url = url, method = method,
    })
end
table.insert(metric_tables.increments, { ip = "192.0.2.1", server_name = "b.example.com", date = 99 })
queue_offence({ threshold = 10, server_name = "a.example.com", ban_scope = "service" })
local queued = json.decode(lists.plugin_badbehavior_incr[1])
queued.report_max_events, queued.report_max_string_size = 2, 8
assert(bb:timer())
assert(#add_ban_calls == 1, "report limits prevented the ban")
local events = add_ban_calls[1].reason_data
assert(#events == 2, "event cap was not applied after service filtering")
assert(events[1].date == 3 and events[2].date == 2, "newest events were not retained")
for _, event in ipairs(events) do
    assert(event.counter == 12, "real ban counter was lost")
    assert(event.url == "雪...", "UTF-8 was split or truncation marker exceeded byte cap")
    assert(event.method == "XXXXX...")
end
assert(metric_tables.increments[1].url == url and metric_tables.increments[1].method == method)
""",
        subsystem,
    )


@needs_lua
@pytest.mark.parametrize("limit_fields", ["", "queued.report_max_events = 0; queued.report_max_string_size = 65537"])
def test_old_or_invalid_queued_limits_use_defaults(limit_fields):
    _run("""
local bb = new_plugin()
bb.increase = function() return 200 end
for n = 1, 160 do
    table.insert(metric_tables.increments, { ip = "192.0.2.1", date = n, url = string.rep("x", 600) })
end
queue_offence({ threshold = 150, ban_scope = "global" })
local queued = json.decode(lists.plugin_badbehavior_incr[1])
LIMIT_FIELDS
assert(bb:timer())
local events = add_ban_calls[1].reason_data
assert(#events == 100, "old/invalid queue did not fall back to 100 events")
assert(events[1].date == 160 and events[100].date == 61)
assert(#events[1].url == 512)
""".replace("LIMIT_FIELDS", limit_fields))


@pytest.mark.parametrize("name,default,minimum,maximum", [("MAX_EVENTS", "100", 1, 10000), ("MAX_STRING_SIZE", "512", 4, 65536)])
def test_settings_bounds_and_all_readmes(name, default, minimum, maximum):
    key = "BAD_BEHAVIOR_REPORT_" + name
    setting = json.loads((PLUGIN / "plugin.json").read_text())["settings"][key]
    assert setting["default"] == default
    assert setting["context"] == "multisite"
    for value in (str(minimum), default, str(maximum)):
        assert re.fullmatch(setting["regex"], value), value
    for value in (str(minimum - 1), str(maximum + 1), "-1", "1.5", "01", "", "1e3"):
        assert re.fullmatch(setting["regex"], value) is None, value
    readmes = list(PLUGIN.glob("README*.md"))
    assert len(readmes) == 5
    for readme in readmes:
        assert key in readme.read_text(), readme
