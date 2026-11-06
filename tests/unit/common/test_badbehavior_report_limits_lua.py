"""UB1-6: configured evidence limits bound the events sent by the real log/timer path.

Only OpenResty/storage boundaries are stand-ins. Counter increment, setting normalization,
event selection and UTF-8 truncation execute the shipped badbehavior module.
"""

import json

import pytest
from _t2_helpers import requires_lua, run_plugin_script

pytestmark = requires_lua


def report(*, max_events='"2"', max_string_size='"8"', event_count=5, threshold=5, url="/probe", method="GET", source="settings"):
    settings = f"BAD_BEHAVIOR_REPORT_MAX_EVENTS = {max_events}, BAD_BEHAVIOR_REPORT_MAX_STRING_SIZE = {max_string_size}," if source == "settings" else ""
    queued = f"queued.report_max_events = {max_events}\nqueued.report_max_string_size = {max_string_size}" if source == "queue" else ""
    out = run_plugin_script(
        "badbehavior",
        f"""
VARIABLES = {{
    USE_BAD_BEHAVIOR = "yes", BAD_BEHAVIOR_STATUS_CODES = "403", BAD_BEHAVIOR_BAN_SCOPE = "service",
    BAD_BEHAVIOR_BAN_TIME = "3600", BAD_BEHAVIOR_COUNT_TIME = "60", BAD_BEHAVIOR_THRESHOLD = "{threshold}",
    {settings}
}}
local ring = {{}}
for i = 1, {event_count} do
    ring[i] = {{ date = i, ip = "203.0.113.9", server_name = "app.example.com",
        url = {json.dumps(url, ensure_ascii=False)}, method = {json.dumps(method, ensure_ascii=False)} }}
end
local evidence
package.loaded["metrics/metrics"] = {{ new = function() return {{
    store_ban_evidence = function(_, events) evidence = events return {{ stored = #events }} end
}} end }}
local p = PLUGIN:new({{ bw = {{ remote_addr = "203.0.113.9", server_name = "app.example.com", request_uri = "/probe" }} }})
p.datastore.delete = function(_, key) DS[key] = nil return true, "success" end
function p:get_metric(kind, key)
    assert(kind == "tables" and key == "increments")
    return ring
end
DS = {{}}
DS["plugin_badbehavior_count_app.example.com_203.0.113.9"] = {threshold - 1}
local logged = p:log()
assert(logged.ret and logged.msg == "success", tostring(logged.msg))
assert(#RPUSHES == 1 and RPUSHES[1].key == "plugin_badbehavior_incr")
local queued = json.decode(RPUSHES[1].value)
{queued}
DICT.incr = {{ json.encode(queued) }}
local result = p:timer()
emit({{ ok = result.ret, msg = result.msg, bans = #BANS, events = evidence,
    original_url = ring[1].url, original_method = ring[1].method }})
""",
    )
    assert out["ok"] is True, out
    assert out["msg"] == "success"
    assert out["bans"] == 1
    return out


@pytest.mark.parametrize(("max_events", "threshold", "dates"), [('"2"', 5, [5, 4]), ('"5"', 3, [5, 4, 3]), ('"10"', 5, [5, 4, 3, 2, 1])])
def test_event_limit_keeps_newest_events_bounded_by_threshold_and_available_history(max_events, threshold, dates):
    out = report(max_events=max_events, threshold=threshold)
    assert [event["date"] for event in out["events"]] == dates
    assert all(event["counter"] == threshold for event in out["events"])


@pytest.mark.parametrize("field", ["url", "method"])
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("short", "short"),
        ("abcdefgh", "abcdefgh"),
        ("abcdefghi", "abcde..."),
        ("aaaaéxyz", "aaaa..."),
        ("aaa€xyz", "aaa..."),
        ("aa😀xyz", "aa..."),
        ("a😀wxyz", "a😀..."),
    ],
)
def test_string_limit_preserves_utf8_and_only_truncates_over_budget_values(field, value, expected):
    out = report(**{field: value})
    assert [event[field] for event in out["events"]] == [expected, expected]
    assert all(len(event[field].encode("utf-8")) <= 8 for event in out["events"])
    assert out[f"original_{field}"] == value


@pytest.mark.parametrize("source", ["settings", "queue"])
@pytest.mark.parametrize(
    ("max_events", "max_string_size"),
    [("nil", "nil"), ("0", "3"), ("-1", "-1"), ("10001", "65537"), ('"invalid"', '"invalid"'), ("false", "false")],
)
def test_invalid_or_missing_limits_use_100_events_and_512_bytes(source, max_events, max_string_size):
    out = report(source=source, max_events=max_events, max_string_size=max_string_size, event_count=103, threshold=103, url="x" * 520)
    assert [event["date"] for event in out["events"]] == list(range(103, 3, -1))
    assert all(event["url"] == "x" * 509 + "..." for event in out["events"])


@pytest.mark.parametrize("source", ["settings", "queue"])
def test_fractional_limits_round_down_before_bounding_evidence(source):
    out = report(source=source, max_events="2.9", max_string_size="8.9", url="abcdefghi")
    assert [event["date"] for event in out["events"]] == [5, 4]
    assert [event["url"] for event in out["events"]] == ["abcde...", "abcde..."]
