"""Unit tests for the plugin/phase timing axis of the metrics plugin.

There is no Lua runtime in the unit venv and no OpenResty to load ``metrics.lua`` against,
so this covers the two halves differently:

* ``accumulate_timer`` is pure table arithmetic, so its **real source is extracted from the
  shipped file and executed** under a stand-alone ``lua`` when one is on PATH. That is a
  genuine behavioural test of the code that ships, not a paraphrase of it.
* The wiring (where the clock is read, what gets recorded, how the drain routes it) cannot
  be executed here, so it is pinned structurally — the same approach
  ``tests/unit/api/test_api_web_cache.py`` takes for ``api.lua``.

The structural half always runs; only the executed half is skipped without ``lua``.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"
HELPERS_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "helpers.lua"
PLUGIN_JSON = ROOT / "src" / "common" / "core" / "metrics" / "plugin.json"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# The guard that opens the baseline branch in metrics:log(). It also carries the subsystem test
# added with the Stream reporting work — the baseline models HTTP shape and has no meaning for a
# raw L4 session. Kept as a constant because four tests below slice the function on it.
BASELINE_GUARD = 'if not reason and subsystem == "http" then'


def _extract(name: str) -> str:
    """Return the real source of a pure module-level function from metrics.lua."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _run_lua(body: str) -> str:
    assert LUA is not None
    preamble = "\n".join(_extract(name) for name in ("should_sample", "template_uri", "accumulate_timer", "merge_timer", "parse_timer_key"))
    script = "local MAX_TEMPLATED_URI = 200\n" + preamble + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


def _code_of(source: str, marker: str) -> str:
    """Return one helpers.lua function body with comment lines stripped.

    The comments here explain the clock and the ordering, so they quote the very calls
    these tests count — matching against them would pass on prose alone.
    """
    body = source.split(marker)[1].split("\nhelpers.")[0]
    return "\n".join(line for line in body.split("\n") if not line.strip().startswith("--"))


# --- executed behaviour ------------------------------------------------------------


@needs_lua
def test_a_first_sample_seeds_the_aggregate():
    out = _run_lua("""
        local a = accumulate_timer(nil, 0.25)
        print(a.count, a.sum, a.max)
    """)
    assert out == "1\t0.25\t0.25"


@needs_lua
def test_samples_fold_into_count_sum_and_max():
    out = _run_lua("""
        local a = nil
        for _, s in ipairs({0.1, 0.4, 0.2}) do a = accumulate_timer(a, s) end
        print(a.count, string.format("%.10g", a.sum), a.max)
    """)
    # max must be the largest sample, not the last one.
    assert out == "3\t0.7\t0.4"


@needs_lua
def test_a_negative_sample_is_dropped_not_clamped():
    """A backwards clock must not manufacture a 0 observation that drags the mean down."""
    out = _run_lua("""
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, -1)
        print(a.count, a.sum, a.max)
        print(tostring(accumulate_timer(nil, -1)))
    """)
    assert out == "1\t0.5\t0.5\nnil"


@needs_lua
def test_a_non_number_sample_is_dropped():
    out = _run_lua("""
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, "slow")
        a = accumulate_timer(a, nil)
        print(a.count, a.sum)
    """)
    assert out == "1\t0.5"


@needs_lua
def test_a_nan_sample_is_dropped():
    """NaN would poison sum and max forever — every later comparison against it is false."""
    out = _run_lua("""
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, 0/0)
        print(a.count, a.sum, a.max)
    """)
    assert out == "1\t0.5\t0.5"


@needs_lua
def test_zero_is_a_real_observation():
    out = _run_lua("""
        local a = accumulate_timer(nil, 0)
        print(a.count, a.sum, a.max)
    """)
    assert out == "1\t0\t0"


# --- cross-worker merge ------------------------------------------------------------
# Each worker keeps its own LRU, so the API sees one aggregate per worker per key and has
# to fold them. This is a hash, and the generic table branch in metrics:api() merges with
# ipairs -- which iterates nothing here and would return an empty table for every timer.


@needs_lua
def test_merging_two_workers_adds_counts_and_keeps_the_larger_max():
    out = _run_lua("""
        local a = merge_timer(nil, {count = 2, sum = 0.6, max = 0.4})
        a = merge_timer(a, {count = 3, sum = 0.9, max = 0.7})
        print(a.count, string.format("%.10g", a.sum), a.max)
    """)
    assert out == "5\t1.5\t0.7"


@needs_lua
def test_merging_keeps_the_running_max_when_the_peer_is_lower():
    out = _run_lua("""
        local a = merge_timer(nil, {count = 1, sum = 0.9, max = 0.9})
        a = merge_timer(a, {count = 1, sum = 0.1, max = 0.1})
        print(a.max)
    """)
    assert out == "0.9"


@needs_lua
def test_a_corrupt_peer_aggregate_does_not_break_the_merge():
    """A truncated or half-written shm entry must not take the whole endpoint down."""
    out = _run_lua("""
        local a = merge_timer(nil, {count = 2, sum = 0.6, max = 0.4})
        a = merge_timer(a, {})
        a = merge_timer(a, "garbage")
        print(a.count, string.format("%.10g", a.sum), a.max)
    """)
    assert out == "2\t0.6\t0.4"


def test_the_api_merges_timer_keys_on_their_own_terms():
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    api_body = metrics.split("function metrics:api()")[1].split("\nfunction metrics:")[0]
    assert 'key:match("_timer_")' in api_body, "timer keys must not fall into the ipairs branch"
    assert "merge_timer(metrics_data[metric_key], data)" in api_body
    # The generic array merge must still exist for the `tables` kind.
    assert "for _, metric_value in ipairs(data) do" in api_body


# --- baseline sampling -------------------------------------------------------------


@needs_lua
def test_sampling_is_disabled_at_rate_zero():
    """The default. Nothing may be recorded until an operator opts in."""
    out = _run_lua("""
        print(tostring(should_sample(0, 0)), tostring(should_sample(50, 0)),
              tostring(should_sample(99, "0")), tostring(should_sample(1, nil)))
    """)
    assert out == "false\tfalse\tfalse\tfalse"


@needs_lua
def test_the_rate_is_read_from_a_string():
    """Settings arrive from self.variables as strings, never as numbers."""
    out = _run_lua("""
        print(tostring(should_sample(0, "100")), tostring(should_sample(50, "1")))
    """)
    assert out == "true\tfalse"


@needs_lua
def test_a_full_rate_takes_everything_and_a_negative_rate_takes_nothing():
    out = _run_lua("""
        print(tostring(should_sample(0, 100)), tostring(should_sample(999, 150)),
              tostring(should_sample(0, -1)))
    """)
    assert out == "true\ttrue\tfalse"


@needs_lua
def test_sampling_is_deterministic_for_a_given_hash():
    """Same request id must land on the same side every time, or subrequests of one
    request would disagree about whether they are being sampled."""
    out = _run_lua("""
        local a = should_sample(12345, 10)
        local b = should_sample(12345, 10)
        print(tostring(a == b), tostring(should_sample(4, 5)), tostring(should_sample(7, 5)))
    """)
    # 4 % 100 = 4 < 5 -> sampled; 7 % 100 = 7 >= 5 -> not sampled.
    assert out == "true\ttrue\tfalse"


@needs_lua
def test_the_sample_rate_is_honoured_across_the_hash_space():
    out = _run_lua("""
        local n = 0
        for h = 0, 9999 do if should_sample(h, 7) then n = n + 1 end end
        print(n)
    """)
    assert out == "700", "7% of 10000 evenly-spread hashes"


@needs_lua
def test_a_missing_hash_is_never_sampled():
    out = _run_lua("""
        print(tostring(should_sample(nil, 50)), tostring(should_sample("abc", 50)))
    """)
    assert out == "false\tfalse"


@needs_lua
def test_a_full_rate_samples_even_without_a_usable_hash():
    """This is what the rate >= 100 short-circuit is for: at 100% a request with no id
    must still be recorded rather than silently dropped."""
    out = _run_lua("""
        print(tostring(should_sample(nil, 100)), tostring(should_sample("abc", 100)))
    """)
    assert out == "true\ttrue"


# --- URI templating ----------------------------------------------------------------


@needs_lua
def test_identifiers_are_collapsed_out_of_the_path():
    """Raw URIs are one distinct value per request — a cardinality bomb and a poor
    feature. The model should learn "/api/user/<n>" is ordinary, not memorise every id."""
    out = _run_lua("""
        print(template_uri("/api/user/12345/posts"))
        print(template_uri("/o/3f2504e0-4f89-11d3-9a0c-0305e82c3301/edit"))
        print(template_uri("/dl/a1b2c3d4e5f6a7b8c9d0/file"))
    """)
    assert out.split("\n") == ["/api/user/<n>/posts", "/o/<uuid>/edit", "/dl/<hex>/file"]


@needs_lua
def test_an_ordinary_path_survives_untouched():
    out = _run_lua("""
        print(template_uri("/login"))
        print(template_uri("/health"))
    """)
    assert out.split("\n") == ["/login", "/health"]


@needs_lua
def test_a_very_long_path_is_truncated():
    out = _run_lua("""
        local long = "/" .. string.rep("z", 400)
        local t = template_uri(long)
        print(#t, t:sub(-3))
    """)
    assert out == "203\t..."


@needs_lua
def test_a_missing_uri_yields_nil():
    out = _run_lua("print(tostring(template_uri(nil)))")
    assert out == "nil"


# --- reading timings back out ------------------------------------------------------


@needs_lua
def test_a_timing_key_splits_into_plugin_and_phase():
    out = _run_lua("""
        print(parse_timer_key("blacklist_timer_access_0"))
        print(parse_timer_key("metrics_timer_request_3"))
    """)
    assert out.split("\n") == ["blacklist\taccess", "metrics\trequest"]


@needs_lua
def test_a_phase_name_containing_an_underscore_survives():
    """`header_filter` is a real phase. Splitting on the last underscore would return
    'header' and silently merge two different phases together."""
    out = _run_lua('print(parse_timer_key("errors_timer_header_filter_12"))')
    assert out == "errors\theader_filter"


@needs_lua
def test_non_timing_keys_are_ignored():
    """The same shm holds counters, tables and the request buffers."""
    out = _run_lua("""
        print(tostring(parse_timer_key("blacklist_counter_foo_0")))
        print(tostring(parse_timer_key("requests_0")))
        print(tostring(parse_timer_key("baseline_0")))
        print(tostring(parse_timer_key(nil)))
    """)
    assert out.split("\n") == ["nil", "nil", "nil", "nil"]


def test_timings_have_their_own_endpoint():
    """A prefix filter can only reach one plugin at a time, so the grouped view needs a
    dedicated route rather than the generic /metrics/<prefix> one."""
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    api_body = metrics.split("function metrics:api()")[1].split("\nfunction metrics:")[0]
    assert 'if filter == "timings" then' in api_body
    assert "return self:api_timings()" in api_body


def test_the_timings_endpoint_merges_workers_and_nests_by_plugin_and_phase():
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    body = metrics.split("function metrics:api_timings()")[1].split("\nfunction metrics:")[0]
    assert "parse_timer_key(key)" in body
    assert "merge_timer(timings[plugin_id][phase], decoded)" in body


# --- structural wiring -------------------------------------------------------------


def test_the_clock_is_refreshed_around_every_plugin_call():
    """ngx.now() alone reads a cached time that only advances when the event loop yields,
    so without update_time() every CPU-bound plugin would measure exactly 0."""
    call_plugin = _code_of(HELPERS_LUA.read_text(encoding="utf-8"), "helpers.call_plugin = function")
    assert call_plugin.count("update_time()") == 2, "need a refresh on both sides of the call"
    assert 'set_metric("timers", method,' in call_plugin


def test_timings_are_recorded_even_when_the_plugin_call_fails():
    """A plugin that blows up after a slow upstream is the one worth seeing in the timings."""
    call_plugin = _code_of(HELPERS_LUA.read_text(encoding="utf-8"), "helpers.call_plugin = function")
    record = call_plugin.index('set_metric("timers"')
    failure_return = call_plugin.index("() failed : ")
    assert record < failure_return, "the timing must be recorded before the error return"


def test_timing_is_skipped_outside_a_request():
    """init/init_worker also route through call_plugin and have no ctx to record into."""
    gate = _code_of(HELPERS_LUA.read_text(encoding="utf-8"), "helpers.timings_enabled = function")
    assert "if not (plugin.ctx and plugin.ctx.bw) then" in gate
    assert "return false" in gate


def test_the_setting_is_resolved_once_per_worker():
    """A datastore read per plugin per phase would cost more than the measurement itself."""
    helpers = HELPERS_LUA.read_text(encoding="utf-8")
    assert "local collect_timings = nil" in helpers
    gate = _code_of(helpers, "helpers.timings_enabled = function")
    assert "if collect_timings == nil then" in gate
    assert gate.count("get_variable(") == 1


def test_the_drain_routes_timers_to_bounded_per_phase_slots():
    """One LRU slot per (plugin, phase) — not one per observation."""
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    assert 'elseif kind == "timers" then' in metrics
    assert 'plugin_id .. "_timer_" .. metric_key' in metrics
    assert "accumulate_timer(lru:get(lru_key), metric_value)" in metrics


def test_request_duration_is_collected_unconditionally():
    """$request_time is free from NGINX and needs no update_time(), so the per-plugin
    setting must not gate it — it is the feature the anomaly baseline needs most."""
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    log_body = metrics.split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    assert "tonumber(ngx.var.request_time)" in log_body
    assert 'lru:set("metrics_timer_request"' in log_body
    assert "METRICS_COLLECT_TIMINGS" not in log_body


def test_the_baseline_uses_its_own_buffer_not_the_blocked_one():
    """Reusing `requests` would put the O(n) Redis TRIM script and its eight per-entry
    facet HINCRBYs on baseline volume."""
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    log_body = metrics.split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    baseline = log_body.split(BASELINE_GUARD)[1].split("\n\t-- Whole-request")[0]
    assert 'lru:get("baseline")' in baseline and 'lru:set("baseline"' in baseline
    assert '"requests"' not in baseline


def test_only_non_blocked_requests_join_the_baseline():
    """A blocked request already has a row in bw_metrics_requests; sampling it here would
    both double-count it and poison the notion of 'normal'."""
    log_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    assert BASELINE_GUARD in log_body


def test_sampling_is_deterministic_not_random():
    log_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    assert "should_sample(crc32_short(request_id)" in log_body
    assert "math.random" not in log_body


def test_the_baseline_never_records_the_client_ip():
    """A model of traffic shape does not need identity, and recording every ordinary
    visitor's address is a far larger privacy commitment than recording blocked ones."""
    log_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    baseline = log_body.split(BASELINE_GUARD)[1].split("\n\t-- Whole-request")[0]
    assert "remote_addr" not in baseline
    assert "ip =" not in baseline


def test_the_baseline_buffer_is_capped():
    log_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:log(")[1].split("\nfunction metrics:")[0]
    baseline = log_body.split(BASELINE_GUARD)[1].split("\n\t-- Whole-request")[0]
    assert "METRICS_MAX_BASELINE_REQUESTS" in baseline
    assert "table_remove(baseline, 1)" in baseline, "drop oldest first"


def test_timer_aggregates_are_excluded_from_the_redis_list_sync():
    """The list sync iterates table values with ipairs, which yields nothing on a
    {count, sum, max} hash — it would DEL the key and push nothing back."""
    timer_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:timer()")[1]
    assert 'elseif key == "baseline" or key:match("_timer_") then' in timer_body
    sync = timer_body.index('elseif key == "baseline" or key:match("_timer_") then')
    generic = timer_body.index('METRICS_SAVE_TO_REDIS"] == "yes" then')
    assert sync < generic, "the timer skip must come before the generic list sync"


def test_the_baseline_is_never_mirrored_to_redis():
    timer_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:timer()")[1]
    skip = timer_body.index('elseif key == "baseline" or key:match("_timer_") then')
    generic = timer_body.index('METRICS_SAVE_TO_REDIS"] == "yes" then')
    assert skip < generic
    assert 'if key ~= "setup" and key ~= "requests" and key ~= "baseline" then' in METRICS_LUA.read_text(encoding="utf-8")


def test_baseline_shm_writes_cannot_evict_blocked_reports():
    timer_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:timer()")[1]
    shm_write = timer_body.split("-- Push to dict", 1)[1].split("if not ok then", 1)[0]
    assert 'if key == "baseline" then' in shm_write
    assert 'self.metrics_datastore:set(key .. "_" .. wid, value)' in shm_write


def test_metrics_memory_retry_setting_reaches_the_shared_helper():
    timer_body = METRICS_LUA.read_text(encoding="utf-8").split("function metrics:timer()")[1]
    shm_write = timer_body.split("-- Push to dict", 1)[1].split("if not ok then", 1)[0]
    assert 'tonumber(self.variables["METRICS_MEMORY_MAX_RETRIES"]) or 5' in shm_write
    assert "set_with_retries(" in shm_write


def test_the_baseline_settings_are_declared():
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    rate = plugin["settings"]["METRICS_BASELINE_SAMPLE_RATE"]
    assert rate["context"] == "global"
    assert rate["default"] == "0", "must ship disabled: there is no consumer yet and the volume is large"
    # 0-100 only; a typo'd 1000 would sample everything.
    assert re.fullmatch(rate["regex"], "100") and re.fullmatch(rate["regex"], "0")
    assert not re.fullmatch(rate["regex"], "101") and not re.fullmatch(rate["regex"], "1000")
    assert plugin["settings"]["METRICS_MAX_BASELINE_REQUESTS"]["context"] == "global"
    assert "shares METRICS_MEMORY_SIZE" in plugin["settings"]["METRICS_MAX_BASELINE_REQUESTS"]["help"]


def test_the_setting_is_declared_as_a_global_check():
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    setting = plugin["settings"]["METRICS_COLLECT_TIMINGS"]
    assert setting["context"] == "global", "call_plugin memoizes it per worker, so it cannot be per-site"
    assert setting["type"] == "check"
    assert setting["regex"] == "^(yes|no)$"
    assert setting["default"] in ("yes", "no")
