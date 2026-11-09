"""The CrowdSec stream poller must be armed in the per-worker phase (init_workers).

In CROWDSEC_MODE=stream, the bouncer uses an NGINX worker timer to periodically pull decisions from
the CrowdSec Local API (LAPI). When NGINX reloads, exiting workers cancel their timers.

The crowdsec plugin must arm the stream poller during worker initialization so the poller does not
depend on incoming HTTP requests reaching crowdsec:access() (which can be delayed or bypassed by
earlier access phases like whitelist and dnsbl on quiet or LAN-administered instances, Issue #4151).

Because timer state (runtime.timer_started) and ngx.timer.at are per-worker Lua VM state, the setup
must run in every worker (init_workers), while stream_lock.lua coordinates execution via flock.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CROWDSEC_LUA = ROOT / "src" / "common" / "core" / "crowdsec" / "crowdsec.lua"
ORDER_JSON = ROOT / "src" / "common" / "core" / "order.json"


def defines(method: str) -> bool:
    return re.search(rf"^function\s+crowdsec:{method}\s*\(", CROWDSEC_LUA.read_text(encoding="utf-8"), re.M) is not None


def test_crowdsec_stream_poller_runs_per_worker_not_once_per_instance():
    assert defines("init_workers"), "crowdsec must define init_workers() -- the ungated, per-worker hook"
    assert not defines("init_worker"), "crowdsec:init_worker() is gated on misc_ready and runs once per instance; per-worker timers cannot be initialised there"


def test_order_json_does_not_name_crowdsec_for_init_workers():
    """helpers.order_plugins appends any plugin defining init_workers, so order.json is untouched."""
    order = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
    assert "crowdsec" not in order.get("init_worker", []), "crowdsec should not be registered under single-instance init_worker"
    assert "crowdsec" not in order.get("init_workers", []), "unnecessary: order_plugins appends the implementer automatically"


def test_crowdsec_init_workers_invokes_setup_stream():
    """Verify crowdsec:init_workers iterates over bouncers and calls SetupStream."""
    source = CROWDSEC_LUA.read_text(encoding="utf-8")
    init_workers_match = re.search(r"function\s+crowdsec:init_workers\(\)(.*?)(?=\nfunction|\nreturn|\Z)", source, re.S)
    assert init_workers_match is not None, "crowdsec:init_workers() method block not found"
    block = init_workers_match.group(1)
    assert "SetupStream" in block, "crowdsec:init_workers() must invoke bouncer.SetupStream"
    assert "is_needed" in block, "crowdsec:init_workers() must verify self:is_needed()"
