"""Behaviour of ``src/common/core/crowdsec/enforcement_state.lua``, the real file run under plain Lua.

The module keeps the CrowdSec bans and captchas in an on-disk checkpoint so they survive a restart,
and lets the request path read them through a small state object (``get``, ``changed``, ``refresh``,
``prepare``, ``save``). What an operator relies on: a saved ban is enforced and survives a restart,
an expired one is dropped, a corrupt or foreign checkpoint is never trusted (``refresh`` fails so the
caller denies), checkpoints are ordered by a global sequence, and a failed save leaves the previous
state untouched.

Plain Lua has no LuaJIT ``ffi``, so ``ffi.C.open/write/close`` are replaced by a stand-in that keeps
the ``O_EXCL`` semantics on a real file in ``tmp_path``; ``cjson`` and ``resty.sha256`` are the
stand-ins from ``_lua_state_helpers.py`` and ``crowdsec.cache_partition`` is the real module.
"""

import pytest
from _lua_state_helpers import BASE_LUA, CORE, LUA, last_json, module_path, run_lua, sha256_hex, to_lua  # type: ignore

pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")

MODULE = module_path("CROWDSEC_ENFORCEMENT_STATE", CORE / "crowdsec" / "enforcement_state.lua")

STUBS = r"""
package.path = CORE_DIR .. "/?.lua;" .. package.path
package.loaded["resty.sha256"] = {
    new = function()
        local parts = {}
        return {
            update = function(_, chunk) parts[#parts + 1] = chunk return true end,
            final = function() return SHA256(table.concat(parts)) end,
        }
    end,
}
package.loaded["resty.string"] = {
    to_hex = function(raw) return (raw:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end,
}
package.loaded["cjson"] = json

-- LuaJIT ffi: only the four libc calls the module declares, on real files, with O_EXCL kept.
local FDS, next_fd = {}, 100
package.loaded["ffi"] = {
    cdef = function() end,
    new = function(_, value) return value end,
    C = {
        getpid = function() return 4242 end,
        open = function(path)
            if FFI_FAIL_OPEN then return -1 end
            local existing = io.open(path, "rb")
            if existing then existing:close() return -1 end
            local handle = io.open(path, "wb")
            if not handle then return -1 end
            next_fd = next_fd + 1
            FDS[next_fd] = handle
            return next_fd
        end,
        write = function(fd, data, count)
            if FFI_SHORT_WRITE then return 0 end
            FDS[fd]:write(data)
            return count
        end,
        close = function(fd) FDS[fd]:close() FDS[fd] = nil return 0 end,
    },
}

LOCK_BUSY = 0
package.loaded["crowdsec.lib.stream_lock"] = {
    run = function(_, fn)
        if LOCK_BUSY > 0 then LOCK_BUSY = LOCK_BUSY - 1 return nil, "busy" end
        if not pcall(fn) then return nil, "Stream synchronization failed" end
        return true
    end,
}

NOW = 1700000000
LOGS = {}
SAFE_SET_FAIL = false
local function new_dict()
    return {
        data = {},
        get = function(self, key) return self.data[key] end,
        safe_add = function(self, key, value)
            if self.data[key] ~= nil then return false, "exists" end
            self.data[key] = value
            return true
        end,
        safe_set = function(self, key, value)
            if SAFE_SET_FAIL then return false, "no memory" end
            self.data[key] = value
            return true
        end,
    }
end
ngx = {
    ERR = "ERR",
    shared = { crowdsec_cache = new_dict() },
    now = function() return NOW end,
    time = function() return math.floor(NOW) end,
    sleep = function(seconds) NOW = NOW + seconds end,
    log = function(level, msg) LOGS[#LOGS + 1] = { level, msg } end,
}
-- A new worker/process: the shared dict is empty again, the files stay.
function restart() ngx.shared.crowdsec_cache = new_dict() end

local function hex(raw) return (raw:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end
function h(text) return hex(SHA256(text)) end
function state_path(prefix) return DIR .. "/crowdsec-state-" .. h(prefix) .. ".json" end
function binding_path(alias) return DIR .. "/crowdsec-binding-" .. h(alias) .. ".json" end
SEQUENCE_PATH = DIR .. "/crowdsec-sequence.json"
function read_json(path)
    local f = assert(io.open(path, "rb"))
    local raw = f:read("*a")
    f:close()
    return json.decode(raw)
end
function write_file(path, content)
    local f = assert(io.open(path, "wb"))
    f:write(content)
    f:close()
end
function write_json(path, value) write_file(path, json.encode(value)) end
function exists(path)
    local f = io.open(path, "rb")
    if f then f:close() return true end
    return false
end
function errors()
    local out = {}
    for _, entry in ipairs(LOGS) do out[#out + 1] = entry[2] end
    return out
end

TARGET = "ipv4_32_16909060"
function ban(ttl) return { NOW + (ttl or 3600), "ban" } end
function captcha(ttl) return { NOW + (ttl or 3600), "captcha" } end
function new_state(prefix, aliases) return ES.new(prefix or "pfx", aliases or { "alias" }, DIR) end
"""


def run(body: str, tmp_path, **globals_):
    prelude = f"CORE_DIR = {to_lua(str(CORE))}\nDIR = {to_lua(str(tmp_path))}\n"
    prelude += "".join(f"{key} = {to_lua(value)}\n" for key, value in globals_.items())
    script = BASE_LUA + prelude + STUBS + f"\nES = dofile({to_lua(str(MODULE))})\n" + body
    return last_json(run_lua(script))


ERROR_LINE = "CrowdSec enforcement checkpoint unavailable or invalid [cache prefix pfx]"


class TestLifecycle:
    def test_a_fresh_state_enforces_nothing_and_validates_on_the_first_refresh(self, tmp_path):
        out = run(
            """
local state = new_state()
local before = { get = state.get(TARGET) == nil, changed = state.changed() }
local refreshed = state.refresh()
emit({ before = before, refreshed = refreshed, changed_after = state.changed(), errors = errors() })
""",
            tmp_path,
        )
        # a missing key may be an eviction mid-publication, so the first reader must validate under the lock
        assert out["before"] == {"get": True, "changed": True}
        assert out["refreshed"] is True
        assert out["changed_after"] is False
        assert out["errors"] == {}  # nothing reported

    def test_a_saved_ban_is_enforced_with_lapi_metadata(self, tmp_path):
        out = run(
            """
local state = new_state()
local saved = state.save({ [TARGET] = { id1 = ban() } })
local remediation, meta = state.get(TARGET)
emit({ saved = saved, remediation = remediation, source = meta.source, captured_at = meta.captured_at,
       metadata_available = meta.metadata_available, other = state.get("ipv4_32_1") == nil,
       changed = state.changed() })
""",
            tmp_path,
        )
        assert out == {
            "saved": True,
            "remediation": "ban",
            "source": "lapi",
            "captured_at": 1700000000,
            "metadata_available": False,
            "other": True,
            "changed": False,
        }
        # the checkpoint and its binding are named after the SHA-256 of the prefix and of the alias
        assert (tmp_path / f"crowdsec-state-{sha256_hex('pfx')}.json").is_file()
        assert (tmp_path / f"crowdsec-binding-{sha256_hex('alias')}.json").is_file()

    def test_a_captcha_only_target_is_challenged(self, tmp_path):
        out = run(
            "local state = new_state(); state.save({ [TARGET] = { id1 = captcha() } }); emit(state.get(TARGET))",
            tmp_path,
        )
        assert out == "captcha"

    def test_a_ban_wins_over_captchas_whatever_the_record_order(self, tmp_path):
        out = run(
            """
local records = { [TARGET] = {} }
for i = 1, 40 do records[TARGET]["captcha" .. i] = captcha() end
records[TARGET].the_ban = ban()
local state = new_state()
state.save(records)
emit(state.get(TARGET))
""",
            tmp_path,
        )
        assert out == "ban"

    def test_expired_records_are_dropped_when_saving(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({
    [TARGET] = { old = { NOW - 1, "ban" }, live = captcha(), now = { NOW, "ban" } },
    ipv4_32_1 = { stale = { NOW - 10, "ban" } },
})
local checkpoint = read_json(state_path("pfx"))
emit({ remediation = state.get(TARGET), records = checkpoint.records })
""",
            tmp_path,
        )
        assert out["remediation"] == "captcha"
        assert list(out["records"]) == ["ipv4_32_16909060"]
        assert list(out["records"]["ipv4_32_16909060"]) == ["live"]

    def test_a_record_stops_being_enforced_when_it_expires(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { id1 = ban(10) } })
local before = state.get(TARGET)
NOW = NOW + 11
emit({ before = before, after = state.get(TARGET) == nil })
""",
            tmp_path,
        )
        assert out == {"before": "ban", "after": True}


class TestPersistence:
    def test_a_ban_survives_a_restart_and_is_validated_by_the_first_refresh(self, tmp_path):
        out = run(
            """
new_state().save({ [TARGET] = { id1 = ban() } })
restart()
local state = new_state()
emit({ remediation = state.get(TARGET), changed = state.changed(), refreshed = state.refresh(),
       changed_after = state.changed(), still = state.get(TARGET) })
""",
            tmp_path,
        )
        assert out == {"remediation": "ban", "changed": True, "refreshed": True, "changed_after": False, "still": "ban"}

    def test_a_reader_built_next_to_a_completed_publication_trusts_it_at_once(self, tmp_path):
        out = run(
            """
new_state().save({ [TARGET] = { id1 = ban() } })
local state = new_state()
emit({ remediation = state.get(TARGET), changed = state.changed() })
""",
            tmp_path,
        )
        assert out == {"remediation": "ban", "changed": False}

    def test_another_writers_publication_is_detected_and_picked_up(self, tmp_path):
        out = run(
            """
local writer, reader = new_state(), new_state()
writer.save({ [TARGET] = { id1 = ban() } })
reader.refresh()
local first = reader.get(TARGET)
writer.save({ ipv4_32_1 = { id2 = captcha() } })
local changed = reader.changed()
local refreshed = reader.refresh()
emit({ first = first, changed = changed, refreshed = refreshed, old_gone = reader.get(TARGET) == nil,
       new = reader.get("ipv4_32_1"), settled = not reader.changed() })
""",
            tmp_path,
        )
        assert out == {
            "first": "ban",
            "changed": True,
            "refreshed": True,
            "old_gone": True,
            "new": "captcha",
            "settled": True,
        }

    def test_expired_records_are_not_restored(self, tmp_path):
        out = run(
            """
new_state().save({ [TARGET] = { id1 = ban(10) } })
NOW = NOW + 11
restart()
emit(new_state().get(TARGET) == nil)
""",
            tmp_path,
        )
        assert out is True


CORRUPT = {
    "not json": "this is not json",
    "a scalar": "5",
    "an unknown version": '{"version":2,"prefix":"pfx","records":{},"seq":1}',
    "records that are not a table": '{"version":1,"prefix":"pfx","records":"x","seq":1}',
    "a target that is not an address key": '{"version":1,"prefix":"pfx","records":{"bad target":{"a":[4102444800,"ban"]}},"seq":1}',
    "an unknown remediation": '{"version":1,"prefix":"pfx","records":{"ipv4_32_1":{"a":[4102444800,"allow"]}},"seq":1}',
    "a non numeric expiry": '{"version":1,"prefix":"pfx","records":{"ipv4_32_1":{"a":["soon","ban"]}},"seq":1}',
}


class TestUntrustedCheckpoint:
    @pytest.mark.parametrize("content", list(CORRUPT.values()), ids=list(CORRUPT))
    def test_an_invalid_checkpoint_is_never_trusted_and_is_reported_once(self, tmp_path, content):
        out = run(
            """
write_file(state_path("pfx"), CONTENT)
local state = new_state()
local first = state.refresh()
local second = state.refresh()
emit({ enforced = state.get(TARGET) == nil and state.get("ipv4_32_1") == nil, first = first or false,
       second = second or false, changed = state.changed(), errors = errors() })
""",
            tmp_path,
            CONTENT=content,
        )
        # refresh fails, so the caller denies instead of serving from a stale fallback
        assert out["enforced"] is True
        assert (out["first"], out["second"], out["changed"]) == (False, False, True)
        assert out["errors"] == [ERROR_LINE]

    def test_a_checkpoint_written_for_another_prefix_counts_as_absent(self, tmp_path):
        out = run(
            """
write_json(state_path("pfx"), { version = 1, prefix = "other", records = { [TARGET] = { a = ban() } }, seq = 1 })
local state = new_state()
emit({ enforced = state.get(TARGET) == nil, refreshed = state.refresh() or false, errors = errors() })
""",
            tmp_path,
        )
        assert out["enforced"] is True
        assert out["refreshed"] is True
        assert out["errors"] == [ERROR_LINE]

    def test_an_unreadable_checkpoint_is_an_io_failure_not_an_absent_one(self, tmp_path):
        # a directory where the file should be: opening succeeds, reading fails
        out = run(
            """
os.execute("mkdir '" .. state_path("pfx") .. "'")
local state = new_state()
emit({ refreshed = state.refresh() or false, changed = state.changed(), errors = errors() })
""",
            tmp_path,
        )
        assert out == {"refreshed": False, "changed": True, "errors": [ERROR_LINE]}

    def test_a_restart_clears_the_report_throttle(self, tmp_path):
        out = run(
            """
write_file(state_path("pfx"), "garbage")
new_state().refresh()
new_state().refresh()
local same_window = #errors()
restart()
new_state().refresh()
emit({ same_window = same_window, after_restart = #errors() })
""",
            tmp_path,
        )
        # one report per cache prefix and minute while the shared dict lives
        assert out == {"same_window": 1, "after_restart": 2}


class TestSequenceAndBindings:
    def test_checkpoints_are_ordered_by_one_global_sequence(self, tmp_path):
        out = run(
            """
local a, b = new_state("p1", { "alias-a" }), new_state("p2", { "alias-b" })
a.save({ [TARGET] = { x = ban() } })
b.save({ [TARGET] = { x = ban() } })
a.save({ [TARGET] = { x = ban() } })
emit({ sequence = read_json(SEQUENCE_PATH).seq, p1 = read_json(state_path("p1")).seq,
       p2 = read_json(state_path("p2")).seq, binding_a = read_json(binding_path("alias-a")).prefix,
       binding_b = read_json(binding_path("alias-b")).prefix })
""",
            tmp_path,
        )
        assert out == {"sequence": 3, "p1": 3, "p2": 2, "binding_a": "p1", "binding_b": "p2"}

    def test_every_alias_of_a_prefix_is_bound_to_it(self, tmp_path):
        out = run(
            """
new_state("p1", { "one", "two" }).save({ [TARGET] = { x = ban() } })
emit({ one = read_json(binding_path("one")).prefix, two = read_json(binding_path("two")).prefix })
""",
            tmp_path,
        )
        assert out == {"one": "p1", "two": "p1"}

    def test_a_binding_failing_to_follow_a_newer_checkpoint_does_not_resurrect_the_older_one(self, tmp_path):
        out = run(
            """
new_state("p1", { "alias" }).save({ [TARGET] = { x = captcha() } })
new_state("p2", { "alias" }).save({ [TARGET] = { x = ban() } })
write_json(binding_path("alias"), { prefix = "p1" })   -- the rename that should have moved it failed
emit(new_state("p2", { "alias" }).get(TARGET))
""",
            tmp_path,
        )
        assert out == "ban"

    def test_a_return_to_an_earlier_url_keeps_the_binding_precedence(self, tmp_path):
        out = run(
            """
new_state("p2", { "alias" }).save({ [TARGET] = { x = ban() } })
new_state("p1", { "alias" }).save({ [TARGET] = { x = captcha() } })
emit(new_state("p2", { "alias" }).get(TARGET))
""",
            tmp_path,
        )
        assert out == "captcha"

    def test_two_checkpoints_with_the_same_sequence_cannot_be_ordered_and_fail_the_restore(self, tmp_path):
        out = run(
            """
for _, prefix in ipairs({ "p1", "p2" }) do
    write_json(state_path(prefix), { version = 1, prefix = prefix, records = { [TARGET] = { x = ban() } }, seq = 5 })
end
write_json(binding_path("alias"), { prefix = "p1" })
local state = new_state("p2", { "alias" })
emit({ refreshed = state.refresh() or false, changed = state.changed() })
""",
            tmp_path,
        )
        assert out == {"refreshed": False, "changed": True}

    def test_a_binding_with_an_oversized_prefix_fails_the_restore(self, tmp_path):
        out = run(
            """
write_json(binding_path("alias"), { prefix = string.rep("x", 81) })
local state = new_state()
emit({ refreshed = state.refresh() or false, errors = errors() })
""",
            tmp_path,
        )
        assert out["refreshed"] is False
        assert out["errors"] == [ERROR_LINE]

    def test_the_sequence_floor_is_rebuilt_from_existing_checkpoints_when_the_file_is_lost(self, tmp_path):
        out = run(
            """
local state = new_state("p2", { "alias" })
write_json(state_path("p1"), { version = 1, prefix = "p1", records = {}, seq = 7 })
write_json(binding_path("alias"), { prefix = "p1" })
state.save({ [TARGET] = { x = ban() } })
emit(read_json(state_path("p2")).seq)
""",
            tmp_path,
        )
        # p1 is only visible through the binding; the new publication must still order after it
        assert out == 8


class TestFailedSaves:
    def test_a_busy_sequence_lock_fails_the_save_and_keeps_the_previous_state(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
LOCK_BUSY = 1000000
local saved = state.save({ ipv4_32_1 = { y = captcha() } })
emit({ saved = saved or false, kept = state.get(TARGET), not_applied = state.get("ipv4_32_1") == nil,
       errors = #errors() })
""",
            tmp_path,
        )
        # busy is a retry condition, not a fault: nothing is reported
        assert out == {"saved": False, "kept": "ban", "not_applied": True, "errors": 0}

    def test_an_unwritable_directory_fails_the_save_reports_it_and_keeps_the_previous_state(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
FFI_FAIL_OPEN = true
local saved = state.save({ ipv4_32_1 = { y = captcha() } })
emit({ saved = saved or false, kept = state.get(TARGET), not_applied = state.get("ipv4_32_1") == nil,
       errors = errors() })
""",
            tmp_path,
        )
        assert out["saved"] is False
        assert (out["kept"], out["not_applied"]) == ("ban", True)
        assert out["errors"] == [ERROR_LINE]

    def test_a_short_write_fails_the_save_and_leaves_no_temporary_file(self, tmp_path):
        out = run(
            """
local state = new_state()
FFI_SHORT_WRITE = true
local saved = state.save({ [TARGET] = { x = ban() } })
emit({ saved = saved or false, state_file = exists(state_path("pfx")), enforced = state.get(TARGET) ~= nil })
""",
            tmp_path,
        )
        assert out == {"saved": False, "state_file": False, "enforced": False}
        assert [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")] == []

    def test_a_failed_revision_publication_fails_the_save(self, tmp_path):
        out = run(
            """
local state = new_state()
SAFE_SET_FAIL = true
local saved = state.save({ [TARGET] = { x = ban() } })
emit({ saved = saved or false, enforced = state.get(TARGET) ~= nil, errors = errors() })
""",
            tmp_path,
        )
        assert out["saved"] is False
        assert out["enforced"] is False
        assert out["errors"] == [ERROR_LINE]


class TestPrepare:
    def test_a_startup_run_begins_from_nothing(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
local records = state.prepare(true)
emit({ empty = next(records) == nil })
""",
            tmp_path,
        )
        assert out == {"empty": True}

    def test_a_later_run_continues_from_the_checkpoint(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
emit(state.prepare(false)[TARGET].x[2])
""",
            tmp_path,
        )
        assert out == "ban"

    def test_without_a_checkpoint_bootstrap_copies_the_in_memory_fallback(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
os.remove(state_path("pfx"))
local plain = state.prepare(false, false)
local copy = state.prepare(false, true)
copy[TARGET].x = nil
emit({ plain = plain == nil, copied = copy ~= nil, fallback_intact = state.get(TARGET) })
""",
            tmp_path,
        )
        assert out == {"plain": True, "copied": True, "fallback_intact": "ban"}

    def test_an_unreadable_checkpoint_is_never_replaced_by_the_in_memory_copy(self, tmp_path):
        out = run(
            """
local state = new_state()
state.save({ [TARGET] = { x = ban() } })
os.remove(state_path("pfx"))
os.execute("mkdir '" .. state_path("pfx") .. "'")
emit(state.prepare(false, true) == nil)
""",
            tmp_path,
        )
        assert out is True
