"""``utils.regex_match``'s memoization of uncompilable regexes (port of dev a369147da).

Before this port, every request that hit a bad setting regex re-ran ``ngx.re.match`` and logged an
ERR line, one per request, unbounded. The fix separates "give up compiling" from "log about it":
once a ``(options, regex)`` pair is known bad, the compile engine is never called again for it, and
the log line is throttled to once per ``RELOG_INTERVAL``. A grep cannot tell "always recompiles" from
"remembers and skips" — the engine call count is what proves it, so ``ngx.re.match`` is stubbed with a
call counter here instead of asserted only by source inspection.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "utils.lua"

LUA = shutil.which("lua") or shutil.which("lua5.4") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(LUA is None, reason="no lua interpreter on PATH")


def regex_match_source() -> str:
    text = UTILS_LUA.read_text(encoding="utf-8")
    chunk = re.search(r"^local RELOG_INTERVAL = 3600$.*?^utils\.regex_match = function.*?^end$", text, re.S | re.M)
    assert chunk, "regex_match block not found in utils.lua -- renamed or restructured?"
    return chunk.group(0)


PREAMBLE = r"""
local utils = {}
local ERR = "ERR"
local var = { server_name = "test.example.com" }

local log_calls = {}
local logger = { log = function(self, lvl, msg) table.insert(log_calls, msg) end }

local match_calls = 0
local BAD = "BAD_REGEX"
local FLAKY = "FLAKY_REGEX"
local re_match = function(str, regex, options)
    match_calls = match_calls + 1
    if regex == BAD then
        return nil, "pcre_compile() failed: fake error"
    end
    -- Compiles fine (the empty-subject probe never errors), but this particular subject
    -- trips a runtime failure (e.g. PCRE_ERROR_MATCHLIMIT) -- a compile-valid regex must
    -- never be memoized just because one subject made it error.
    if regex == FLAKY and str ~= "" then
        return nil, "pcre_exec() failed: fake runtime error"
    end
    return {}, nil
end

local fake_now = 1000
os.time = function() return fake_now end
"""


def run(body: str) -> str:
    script = PREAMBLE + "\n" + regex_match_source() + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


class TestMemoizationSkipsTheEngine:
    def test_first_bad_call_hits_the_engine_and_logs_once(self):
        out = run("""
            local m = utils.regex_match("x", BAD, nil, "SOME_SETTING")
            assert(m == nil, "expected nil for a bad regex")
            -- main call + the empty-subject probe that isolates a compile failure
            assert(match_calls == 2, "expected 2 engine calls, got " .. match_calls)
            assert(#log_calls == 1, "expected 1 log line, got " .. #log_calls)
            assert(log_calls[1]:find("SOME_SETTING", 1, true), "log line missing the setting name: " .. log_calls[1])
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_second_call_within_the_interval_never_touches_the_engine(self):
        """Mutation check: dropping the `if bad then ... return nil end` early-return in
        utils.lua makes this red (match_calls climbs to 4), proving the assertion is load-bearing."""
        out = run("""
            utils.regex_match("x", BAD, nil, "SOME_SETTING")
            utils.regex_match("y", BAD, nil, "SOME_SETTING")
            assert(match_calls == 2, "second call must not reach the engine, got " .. match_calls .. " calls")
            assert(#log_calls == 1, "second call must not re-log within RELOG_INTERVAL, got " .. #log_calls)
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_relog_after_the_interval_still_skips_the_engine(self):
        out = run("""
            utils.regex_match("x", BAD, nil, "SOME_SETTING")
            fake_now = fake_now + 3600
            utils.regex_match("x", BAD, nil, "SOME_SETTING")
            assert(match_calls == 2, "relog must not reach the engine either, got " .. match_calls .. " calls")
            assert(#log_calls == 2, "expected a second log line after RELOG_INTERVAL, got " .. #log_calls)
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_a_good_regex_is_never_memoized(self):
        out = run("""
            utils.regex_match("x", "GOOD", nil, "SOME_SETTING")
            utils.regex_match("y", "GOOD", nil, "SOME_SETTING")
            assert(match_calls == 2, "a working regex must hit the engine every call, got " .. match_calls)
            assert(#log_calls == 0, "a working regex must never log, got " .. #log_calls)
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_options_are_part_of_the_memo_key(self):
        """Same regex string, different options -- must not share a memo slot, since compile
        validity depends on the flags."""
        out = run("""
            utils.regex_match("x", BAD, nil, "S1")
            utils.regex_match("x", BAD, "i", "S2")
            assert(match_calls == 4, "different options must not share a memo key, got " .. match_calls)
            print("ok")
            """)
        assert out.strip() == "ok"

    def test_a_runtime_failure_on_one_subject_is_never_memoized(self):
        """A regex that compiles (the empty-subject probe succeeds) but errors on a specific
        subject must be retried on the engine every time, not treated as permanently bad --
        that would silently disable a working regex for every other subject it is ever called
        with, for the life of the worker.

        Mutation check: dropping utils.lua's `if probe_err then` guard (memoizing
        unconditionally on any error) makes this red -- the second call's engine calls would
        stay at 2 instead of reaching 4, and the second log would never fire."""
        out = run("""
            local m = utils.regex_match("bad subject", FLAKY, nil, "SOME_SETTING")
            assert(m == nil, "expected nil for a runtime failure")
            assert(match_calls == 2, "expected main call + probe, got " .. match_calls)
            assert(#log_calls == 1, "expected 1 log line, got " .. #log_calls)

            utils.regex_match("another bad subject", FLAKY, nil, "SOME_SETTING")
            assert(match_calls == 4, "a runtime failure must not be memoized, got " .. match_calls .. " engine calls")
            assert(#log_calls == 2, "a non-memoized failure must log every time, got " .. #log_calls)
            print("ok")
            """)
        assert out.strip() == "ok"
