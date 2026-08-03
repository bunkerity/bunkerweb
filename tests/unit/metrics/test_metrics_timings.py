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


def _extract(name: str) -> str:
    """Return the real source of a pure module-level function from metrics.lua."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local function {name}\(.*?^end$", source, re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _run_lua(body: str) -> str:
    assert LUA is not None
    script = _extract("accumulate_timer") + "\n" + _extract("merge_timer") + "\n" + body
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
    out = _run_lua(
        """
        local a = accumulate_timer(nil, 0.25)
        print(a.count, a.sum, a.max)
    """
    )
    assert out == "1\t0.25\t0.25"


@needs_lua
def test_samples_fold_into_count_sum_and_max():
    out = _run_lua(
        """
        local a = nil
        for _, s in ipairs({0.1, 0.4, 0.2}) do a = accumulate_timer(a, s) end
        print(a.count, string.format("%.10g", a.sum), a.max)
    """
    )
    # max must be the largest sample, not the last one.
    assert out == "3\t0.7\t0.4"


@needs_lua
def test_a_negative_sample_is_dropped_not_clamped():
    """A backwards clock must not manufacture a 0 observation that drags the mean down."""
    out = _run_lua(
        """
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, -1)
        print(a.count, a.sum, a.max)
        print(tostring(accumulate_timer(nil, -1)))
    """
    )
    assert out == "1\t0.5\t0.5\nnil"


@needs_lua
def test_a_non_number_sample_is_dropped():
    out = _run_lua(
        """
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, "slow")
        a = accumulate_timer(a, nil)
        print(a.count, a.sum)
    """
    )
    assert out == "1\t0.5"


@needs_lua
def test_a_nan_sample_is_dropped():
    """NaN would poison sum and max forever — every later comparison against it is false."""
    out = _run_lua(
        """
        local a = accumulate_timer(nil, 0.5)
        a = accumulate_timer(a, 0/0)
        print(a.count, a.sum, a.max)
    """
    )
    assert out == "1\t0.5\t0.5"


@needs_lua
def test_zero_is_a_real_observation():
    out = _run_lua(
        """
        local a = accumulate_timer(nil, 0)
        print(a.count, a.sum, a.max)
    """
    )
    assert out == "1\t0\t0"


# --- cross-worker merge ------------------------------------------------------------
# Each worker keeps its own LRU, so the API sees one aggregate per worker per key and has
# to fold them. This is a hash, and the generic table branch in metrics:api() merges with
# ipairs -- which iterates nothing here and would return an empty table for every timer.


@needs_lua
def test_merging_two_workers_adds_counts_and_keeps_the_larger_max():
    out = _run_lua(
        """
        local a = merge_timer(nil, {count = 2, sum = 0.6, max = 0.4})
        a = merge_timer(a, {count = 3, sum = 0.9, max = 0.7})
        print(a.count, string.format("%.10g", a.sum), a.max)
    """
    )
    assert out == "5\t1.5\t0.7"


@needs_lua
def test_merging_keeps_the_running_max_when_the_peer_is_lower():
    out = _run_lua(
        """
        local a = merge_timer(nil, {count = 1, sum = 0.9, max = 0.9})
        a = merge_timer(a, {count = 1, sum = 0.1, max = 0.1})
        print(a.max)
    """
    )
    assert out == "0.9"


@needs_lua
def test_a_corrupt_peer_aggregate_does_not_break_the_merge():
    """A truncated or half-written shm entry must not take the whole endpoint down."""
    out = _run_lua(
        """
        local a = merge_timer(nil, {count = 2, sum = 0.6, max = 0.4})
        a = merge_timer(a, {})
        a = merge_timer(a, "garbage")
        print(a.count, string.format("%.10g", a.sum), a.max)
    """
    )
    assert out == "2\t0.6\t0.4"


def test_the_api_merges_timer_keys_on_their_own_terms():
    metrics = METRICS_LUA.read_text(encoding="utf-8")
    api_body = metrics.split("function metrics:api()")[1].split("\nfunction metrics:")[0]
    assert 'key:match("_timer_")' in api_body, "timer keys must not fall into the ipairs branch"
    assert "merge_timer(metrics_data[metric_key], data)" in api_body
    # The generic array merge must still exist for the `tables` kind.
    assert "for _, metric_value in ipairs(data) do" in api_body


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


def test_the_setting_is_declared_as_a_global_check():
    plugin = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    setting = plugin["settings"]["METRICS_COLLECT_TIMINGS"]
    assert setting["context"] == "global", "call_plugin memoizes it per worker, so it cannot be per-site"
    assert setting["type"] == "check"
    assert setting["regex"] == "^(yes|no)$"
    assert setting["default"] in ("yes", "no")
