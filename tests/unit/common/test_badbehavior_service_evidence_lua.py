"""Service bans must never include another service's events for the same IP."""

import pytest

from test_badbehavior_ban_clears_counter import _run, needs_lua


@needs_lua
@pytest.mark.parametrize("subsystem", ["http", "stream"])
@pytest.mark.parametrize("scope", ["service", "global"])
@pytest.mark.parametrize("matching_event", [True, False])
def test_evidence_scope_and_evicted_event_fallback(subsystem, scope, matching_event):
    _run(
        """
local bb = new_plugin()
bb.increase = function() return 10 end
metric_tables.increments = {
    { ip = "192.0.2.1", server_name = "b.example.com", url = "/foreign" },
}
if MATCHING then
    table.insert(metric_tables.increments, { ip = "192.0.2.1", server_name = "a.example.com", url = "/own" })
end
queue_offence({ threshold = 10, server_name = "a.example.com", ban_scope = "SCOPE" })
assert(bb:timer())
assert(#add_ban_calls == 1)
local evidence = add_ban_calls[1].reason_data
if "SCOPE" == "service" then
    assert(#evidence == 1, "service ban included another service's events")
    assert(evidence[1].server_name == "a.example.com", "service ban used foreign evidence instead of fallback")
    assert(evidence[1].url == (MATCHING and "/own" or nil))
else
    assert(#evidence == (MATCHING and 2 or 1), "global ban lost cross-service evidence")
end
""".replace("MATCHING", "true" if matching_event else "false").replace("SCOPE", scope),
        subsystem,
    )
