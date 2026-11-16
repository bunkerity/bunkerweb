"""Real CrowdSec bouncer: live lookups, pre-first-pull bootstrap, reload and restart recovery, the refresh epoch fence.

The shipped ``lib/bouncer.lua``, ``decision_cache.lua``, ``enforcement_state.lua`` and ``stream_lock.lua`` are loaded
for real through the harness of ``test_crowdsec_bouncer_stream_coverage_lua.py``; only OpenResty, libc and the Local
API are faked. The fence tests also run a mutated copy of the bouncer to prove they can fail.
"""

import shutil
from pathlib import Path

import pytest
from _crowdsec_lua_helpers import BASE_LUA, LUA, last_json, run_lua, to_lua  # type: ignore
from test_crowdsec_bouncer_stream_coverage_lua import HARNESS as COVERAGE_HARNESS  # type: ignore

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

# The semaphore stub runs the queued timer when the request handler waits; WAIT_HOOK lets a test act just before.
HARNESS = COVERAGE_HARNESS.replace(
    "local t=table.remove(TIMERS,i); t[2](PREMATURE or false)", "local t=table.remove(TIMERS,i); if WAIT_HOOK then WAIT_HOOK() end t[2](PREMATURE or false)"
)
assert "WAIT_HOOK" in HARNESS

BAN = '[{"id":7,"scope":"Ip","value":"192.0.2.1","type":"ban","duration":"3600s"}]'
NO_DECISION = "[]"


def run(tmp_path, body, *, conf=None, setup="", root=ROOT):
    config = {
        "API_URL": "https://lapi.example",
        "API_KEY": "unit-key",
        "BOUNCING_ON_TYPE": "all",
        "FALLBACK_REMEDIATION": "ban",
        "CAPTCHA_PROVIDER": "",
        "CACHE_EXPIRATION": 30,
        **(conf or {}),
    }
    path = tmp_path / "bouncer.conf"
    path.write_text("".join(f"{key}={value}\n" for key, value in config.items()))
    prelude = f"ROOT={to_lua(str(root))}\nDIR={to_lua(str(tmp_path))}\nCONF={to_lua(str(path))}\nIP6={{}}\n"
    return last_json(run_lua(BASE_LUA + prelude + HARNESS + setup + "\n" + body))


HELPERS = r"""
function body(text) RESPONSE={status=200,body=text} end
function decision_keys(dict) local keys={} for k in pairs((dict or CACHE).data) do if k:find('v2_decisions_',1,true) then keys[#keys+1]=k end end table.sort(keys) return keys end
function lookups() local n=0 for _,r in ipairs(REQUESTS) do if r.link:find('/v1/decisions?ip=',1,true) then n=n+1 end end return n end
function wipe(dict) dict.data, dict.deadlines = {}, {} end
"""


class TestLiveMode:
    def test_a_live_ban_is_cached_for_the_next_request(self, tmp_path):
        """Live mode asks the Local API once per CACHE_EXPIRATION: the second request is a cache hit."""
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(BAN)})
local first=allowed(); local second=allowed()
emit({{first=first,second=second,lookups=lookups(),keys=decision_keys()}})
""",
            conf={"MODE": "live"},
        )
        assert out["first"]["kind"] == "ban"
        assert out["second"]["kind"] == "ban"
        assert out["second"]["evidence"]["decisions"][0]["remediation"] == "ban"
        assert out["lookups"] == 1
        # Live records belong to the bootstrap namespace: they must never touch a published stream slot.
        assert out["keys"] and all(key.startswith("p|bootstrap_") for key in out["keys"])

    def test_a_live_decision_is_capped_to_cache_expiration(self, tmp_path):
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(BAN)})
allowed(); NOW=NOW+31
local after=allowed()
emit({{after=after,lookups=lookups()}})
""",
            conf={"MODE": "live"},
        )
        assert out["after"]["kind"] == "ban"
        assert out["lookups"] == 2

    def test_a_live_allow_is_cached_too(self, tmp_path):
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(NO_DECISION)})
local first=allowed(); local second=allowed()
emit({{first=first,second=second,lookups=lookups()}})
""",
            conf={"MODE": "live"},
        )
        assert out["first"]["allowed"] is True
        assert out["second"]["allowed"] is True
        assert out["lookups"] == 1


class TestStreamBootstrap:
    def test_a_request_before_the_first_pull_learns_a_fresh_ban(self, tmp_path):
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(BAN)})
local first=allowed(); local second=allowed()
emit({{first=first,second=second,lookups=lookups(),keys=decision_keys(),generation=CACHE:get('p|v3_generation')}})
""",
        )
        assert out["first"]["kind"] == "ban"
        assert out["second"]["kind"] == "ban"
        assert out["lookups"] == 1
        # No snapshot was published, and the live answer sits outside both stream slots.
        assert out.get("generation") is None
        assert out["keys"] and all(key.startswith("p|bootstrap_") for key in out["keys"])

    def test_a_bootstrap_ban_keeps_the_decision_lifetime(self, tmp_path):
        """Unlike live mode, a bootstrap answer is not capped to CACHE_EXPIRATION: it stands in for the stream."""
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(BAN)})
allowed(); NOW=NOW+600
emit({{after=allowed(),lookups=lookups()}})
""",
        )
        assert out["after"]["kind"] == "ban"
        assert out["lookups"] == 1

    def test_a_bootstrap_failure_backs_off_for_the_update_frequency(self, tmp_path):
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); RESPONSE=nil; HTTP_ERROR='refused'
local first=allowed(); local after_first=lookups()
local second=allowed(); local after_second=lookups()
NOW=NOW+11
local third=allowed()
emit({{first=first,after_first=after_first,after_second=after_second,second=second,third=third,final=lookups()}})
""",
        )
        assert out["first"]["allowed"] is True
        assert out["first"]["error"] == "Local API request failed"
        assert out["after_first"] == 1
        assert out["after_second"] == 1
        assert out["final"] == 2

    def test_the_first_published_snapshot_wins_over_the_bootstrap_answer(self, tmp_path):
        out = run(
            tmp_path,
            f"""
{HELPERS}
assert(boot()); body({to_lua(BAN)}); allowed()
body(json.encode({{new=setmetatable({{}},json.array_mt),deleted=setmetatable({{}},json.array_mt)}}))
poll()
emit({{after=allowed(),generation=CACHE:get('p|v3_generation')}})
""",
        )
        # The empty full snapshot is authoritative; the stale bootstrap record no longer applies.
        assert out["generation"].startswith("policy|")
        assert out["after"] == {"allowed": True}


class TestReloadAndRestart:
    def test_a_reload_keeps_the_snapshot_and_polls_incrementally(self, tmp_path):
        out = run(
            tmp_path,
            """
assert(boot()); local d=decision(7); stream({d}); poll()
assert(boot()); RESPONSE=nil; HTTP_ERROR='refused'
local right_after=allowed()
HTTP_ERROR=nil; advance(); stream({}); poll()
emit({right_after=right_after,links=REQUESTS})
""",
        )
        assert out["right_after"]["kind"] == "ban"
        assert out["links"][0]["link"].endswith("startup=true")
        assert out["links"][-1]["link"].endswith("startup=false")

    def test_a_policy_change_reconciles_fully_without_dropping_known_bans(self, tmp_path):
        out = run(
            tmp_path,
            """
assert(boot()); stream({decision(7)}); poll()
assert(boot(nil, 'policy-2')); RESPONSE=nil; HTTP_ERROR='refused'
local during_outage=allowed()
HTTP_ERROR=nil; advance(); stream({decision(7)}); poll()
emit({during_outage=during_outage,last=REQUESTS[#REQUESTS].link,generation=CACHE:get('p|v3_generation')})
""",
        )
        assert out["during_outage"]["kind"] == "ban"
        assert out["last"].endswith("startup=true")
        assert out["generation"].startswith("policy-2|")

    def test_a_restart_during_a_local_api_outage_restores_known_bans(self, tmp_path):
        """Same container filesystem, empty shared memory (resize or restart), Local API down."""
        out = run(
            tmp_path,
            """
assert(boot()); stream({decision(7)}); poll()
wipe(CACHE); wipe(META)
RESPONSE=nil; HTTP_ERROR='refused'
assert(boot())
emit({known=allowed(), unknown=allowed('192.0.2.77')})
""",
            setup=HELPERS,
        )
        assert out["known"]["kind"] == "ban"
        assert out["unknown"]["allowed"] is True

    def test_a_fresh_filesystem_starts_empty(self, tmp_path):
        out = run(
            tmp_path,
            """
RESPONSE=nil; HTTP_ERROR='refused'
assert(boot())
emit(allowed())
""",
        )
        assert out == {"allowed": True, "error": "Local API request failed"}

    def test_an_expired_checkpoint_record_does_not_ban(self, tmp_path):
        out = run(
            tmp_path,
            """
assert(boot()); stream({decision(7,nil,nil,nil,'60s')}); poll()
wipe(CACHE); wipe(META); NOW=NOW+61
RESPONSE=nil; HTTP_ERROR='refused'
assert(boot())
emit(allowed())
""",
            setup=HELPERS,
        )
        assert out["allowed"] is True

    def test_a_worker_killed_mid_poll_forces_a_full_resync(self, tmp_path):
        out = run(
            tmp_path,
            """
assert(boot()); stream({decision(7)}); poll(); advance()
BEFORE_RESPONSE=function() BEFORE_RESPONSE=nil; error('worker killed') end
pcall(poll)
local marker=CACHE:get('p|stream_inflight')
advance(); stream({}); poll()
emit({marker=marker,last=REQUESTS[#REQUESTS].link,after=CACHE:get('p|stream_inflight')})
""",
        )
        assert out["marker"] is True
        assert out["last"].endswith("startup=true")
        assert out["after"] is False

    def test_three_full_polls_use_only_the_two_slots(self, tmp_path):
        out = run(
            tmp_path,
            """
assert(boot())
local slots = {}
for round = 1, 3 do
  stream({decision(round, '192.0.2.' .. round)})
  CACHE:set('p|startup', true); poll(); advance()
  slots[#slots + 1] = CACHE:get('p|v3_generation'):sub(-1)
end
local keys = {}
for k in pairs(CACHE.data) do
  local slot = k:match('v2_decisions_[^|]*|%d+:(%u)|')
  if slot then keys[slot] = true end
end
local names = {}
for slot in pairs(keys) do names[#names + 1] = slot end
table.sort(names)
emit({slots = slots, names = names, active = allowed('192.0.2.3'), stale = allowed('192.0.2.1')})
""",
        )
        # The first full poll leaves the default slot A to the next one.
        assert out["slots"] == ["B", "A", "B"]
        assert set(out["names"]) <= {"A", "B"}
        assert out["active"]["kind"] == "ban"
        assert out["stale"] == {"allowed": True}


RACE = """
assert(boot()); body({ban})
-- The unban lands while the live query is in flight: the Local API now reports nothing, then the stale answer returns.
BEFORE_RESPONSE=function()
  BEFORE_RESPONSE=nil
  body({gone}); assert(b.Control('refresh_ip', {{ip='192.0.2.1'}}))
  body({ban})
end
local raced=allowed()
body({gone})
local later=allowed()
local cached=decision_keys()
wipe(CACHE); wipe(META)
RESPONSE=nil; HTTP_ERROR='refused'
assert(boot())
emit({{raced=raced,later=later,cached=cached,restored=allowed()}})
"""

# The unban lands after the answer was decoded, while the checkpoint write waits for the poller lock.
RACE_AT_CHECKPOINT = """
assert(boot()); body({ban})
WAIT_HOOK=function()
  WAIT_HOOK=nil; BEFORE_RESPONSE=nil
  body({gone}); assert(b.Control('refresh_ip', {{ip='192.0.2.1'}}))
  body({ban})
end
local raced=allowed()
body({gone})
local later=allowed()
local cached=decision_keys()
wipe(CACHE); wipe(META)
RESPONSE=nil; HTTP_ERROR='refused'
assert(boot())
emit({{raced=raced,later=later,cached=cached,restored=allowed()}})
"""


def race_script(template):
    return HELPERS + template.format(ban=to_lua(BAN), gone=to_lua(NO_DECISION)).replace("{{", "{").replace("}}", "}")


def mutated_root(tmp_path, needle, replacement):
    """A copy of the shipped plugin whose bouncer lost (some of) its refresh-epoch checks."""
    root = tmp_path / "mutated"
    core = root / "src" / "common" / "core"
    core.mkdir(parents=True)
    shutil.copytree(ROOT / "src" / "common" / "core" / "crowdsec", core / "crowdsec")
    (root / "src" / "bw").mkdir()
    (root / "src" / "bw" / "lua").symlink_to(ROOT / "src" / "bw" / "lua")
    bouncer = core / "crowdsec" / "lib" / "bouncer.lua"
    source = bouncer.read_text()
    assert needle in source
    bouncer.write_text(source.replace(needle, replacement))
    return root


@pytest.mark.parametrize("scenario", [RACE, RACE_AT_CHECKPOINT], ids=["during-request", "during-checkpoint-wait"])
class TestRefreshEpochFence:
    def test_an_unban_during_a_live_query_is_not_cached_or_checkpointed(self, tmp_path, scenario):
        out = run(tmp_path, race_script(scenario), conf={"MODE": "live"})
        assert out["raced"]["allowed"] is True
        assert out["raced"]["error"] == "invalidated"
        assert out["later"]["allowed"] is True
        assert not out["cached"]
        # Nothing reached the checkpoint either: a restart during an outage does not resurrect the ban.
        assert out["restored"]["allowed"] is True

    def test_the_same_race_without_the_fence_publishes_the_stale_ban(self, tmp_path, scenario):
        """Mutation: with every epoch comparison removed the unbanned IP is cached and checkpointed again."""
        root = mutated_root(tmp_path / "m", "refresh_epoch(key) ~= epoch", "false")
        out = run(tmp_path, race_script(scenario), conf={"MODE": "live"}, root=root)
        assert out["raced"]["kind"] == "ban"
        assert out["cached"]
        assert out["restored"]["kind"] == "ban"


def test_a_refresh_that_cannot_store_its_epoch_is_refused(tmp_path):
    """RefreshIp must not run unfenced: a full dict is a 502, and nothing is read or changed."""
    out = run(
        tmp_path,
        """
assert(boot()); CACHE.fail['p|refresh_epoch|' .. 'x']=nil
local real_incr = CACHE.incr
function CACHE:incr(k, ...) if k:find('refresh_epoch|', 1, true) then return nil, 'no memory' end return real_incr(self, k, ...) end
local data, err, status = b.Control('refresh_ip', {ip='192.0.2.1'})
emit({data=data, err=err, status=status, lookups=lookups()})
""",
        setup=HELPERS,
        conf={"MODE": "live"},
    )
    assert out == {"err": "Local decision cache is full", "status": 502, "lookups": 0}
