"""HTTP references capped evidence; stream and storage failures keep bounded inline data."""

import pytest

from test_badbehavior_ban_clears_counter import _run, needs_lua


@needs_lua
@pytest.mark.parametrize("subsystem", ["http", "stream"])
def test_http_shares_capped_evidence_while_stream_keeps_it_inline(subsystem):
    _run(
        """
local stored={}
package.preload["metrics/metrics"]=function() return {new=function() return {
  store_ban_evidence=function(_,events,summary)
    stored[#stored+1]=events
    summary.ban_id="http:"..string.rep("x",32); summary.event_count=#events
    return summary
  end} end} end
local bb=new_plugin(); bb.increase=function() return 12 end
for n=1,5 do table.insert(metric_tables.increments,{ip="192.0.2.1",server_name="a.example",date=n,url=string.rep("雪",9)}) end
table.insert(metric_tables.increments,{ip="192.0.2.1",server_name="b.example",date=99,url="/foreign"})
queue_offence({threshold=4,server_name="a.example",ban_scope="service"})
local queued=json.decode(lists.plugin_badbehavior_incr[1])
queued.report_max_events=2; queued.report_max_string_size=8
assert(bb:timer())
local data=add_ban_calls[1].reason_data
local events=data
if subsystem=="http" then
  assert(data.ban_id and data.counter==12 and data.event_count==2 and data[1]==nil,"HTTP still copies evidence")
  assert(#stored==1); events=stored[1]
else
  assert(#stored==0 and data.ban_id==nil,"stream unexpectedly requires a shared evidence channel")
end
assert(#events==2 and events[1].date==5 and events[2].date==4)
assert(events[1].url=="雪..." and events[1].counter==12 and events[1].server_name=="a.example")
""",
        subsystem,
    )


@needs_lua
def test_unexpected_store_failure_never_prevents_the_ban():
    _run("""
local attempted=false
package.preload["metrics/metrics"]=function() return {new=function() return {
  store_ban_evidence=function() attempted=true; error("store failed") end} end} end
local bb=new_plugin(); queue_offence({threshold=1})
assert(bb:timer())
assert(attempted and #add_ban_calls==1 and #add_ban_calls[1].reason_data==1)
""")
