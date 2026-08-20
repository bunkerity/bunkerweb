"""The LRU resize must run in the per-worker phase, not the per-instance one.

`metrics.lua` keeps its LRU in a module-level local (`lru`), and `lrucache` is a plain Lua table
structure -- so there is one LRU per Lua VM, which is one per nginx worker. Whatever resizes it to
`MAX_LRU_HISTORY` therefore has to run in every worker.

There are two init hooks and only one of them does:

    init_worker()    init-worker-lua.conf:244, inside a 5s timer, gated on the shared `misc_ready`
                     flag under `worker_lock` -> runs ONCE PER INSTANCE
    init_workers()   init-worker-lua.conf:52, in `init_worker_by_lua*`, ungated -> once per worker

The resize was on `init_worker`. Measured on a 4-worker instance with `MAX_LRU_HISTORY=4242`: one
pid logged "metrics LRU sized to 4242 slots" and the other three silently kept
`DEFAULT_MAX_LRU_HISTORY = 1000`. `WORKER_PROCESSES` defaults to `auto`, so on a 16-core host the
documented setting reached 1 worker in 16 -- and an operator sampling the worker that did resize
sees it working, which makes "partially applied" harder to diagnose than "not applied at all".

**Do not fix a failure here by adding `metrics` to `order.json`.** That file is a *priority prefix*,
not a registry: `helpers.order_plugins` (`helpers.lua:201-211`) appends every plugin implementing a
phase that the prefix did not already name. `metrics` was in the effective `init_worker` list all
along without being written there, which is exactly how this defect got misread once. The phase a
plugin runs in is decided by the name of the method it defines, and nothing else.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"
ORDER_JSON = ROOT / "src" / "common" / "core" / "order.json"


def defines(method: str) -> bool:
    return re.search(rf"^function\s+metrics:{method}\s*\(", METRICS_LUA.read_text(encoding="utf-8"), re.M) is not None


def test_the_resize_runs_once_per_worker_not_once_per_instance():
    assert defines("init_workers"), "metrics must define init_workers() -- the ungated, per-worker hook"
    assert not defines("init_worker"), "metrics:init_worker() is gated on misc_ready and runs once per instance; per-VM state cannot be initialised there"


def test_order_json_does_not_name_metrics_for_either_init_phase():
    """A prefix entry would be a no-op that reads like a registration -- see the module docstring."""
    order = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
    assert "metrics" not in order.get("init_worker", []), "order.json cannot move metrics between phases; the method name does that"
    assert "metrics" not in order.get("init_workers", []), "unnecessary: order_plugins appends the only implementer anyway"


def test_the_lru_is_still_module_level_state():
    """Anti-vacuity: the whole argument rests on the LRU being per-VM. If it ever moves into a
    shared dict or onto `self`, the per-worker requirement changes and this file must be re-read."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert re.search(
        r"^local lru, err_lru = lrucache\.new\(DEFAULT_MAX_LRU_HISTORY\)", source, re.M
    ), "the module-level LRU is gone -- re-derive which phase the resize belongs in"
    assert re.search(r"^\tlru = new_lru$", source, re.M), "the resize no longer reassigns the module-level upvalue"


def test_the_comment_names_the_hook_that_actually_runs():
    """The rename's own explanation is a line of prose that goes stale silently."""
    source = METRICS_LUA.read_text(encoding="utf-8")
    assert "once init_workers() runs" in source, "the DEFAULT_MAX_LRU_HISTORY comment still names the old hook"
