"""`GET /redis/stats` reports the datastore's memory posture, not just a key count.

A key count cannot tell an operator that the datastore is silently evicting. `evicted_keys`
climbing means bans and rate-limit counters are being dropped to make room -- the one failure
this chantier's `volatile-lru` / `noeviction` split exists to prevent, and it is invisible
everywhere else in the product.

The parsing is the fragile part: Redis `INFO` ships `used_memory` next to `used_memory_human`,
and `maxmemory` next to both `maxmemory_human` and `maxmemory_policy`, so a sloppy pattern
silently returns the wrong field.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
REDIS_LUA = ROOT / "src" / "common" / "core" / "redis" / "redis.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")

# Real `INFO memory` / `INFO stats` shape: CRLF-terminated, section header first, and every
# trap field present.
INFO_MEMORY = r"# Memory\r\nused_memory:1048576\r\nused_memory_human:1.00M\r\nmaxmemory:268435456\r\nmaxmemory_human:256.00M\r\nmaxmemory_policy:noeviction\r\n"
INFO_STATS = r"# Stats\r\nexpired_keys:12\r\nevicted_keys:7\r\n"


def _info_field_source() -> str:
    """The real info_field() out of redis.lua, de-indented so stand-alone Lua accepts it."""
    source = REDIS_LUA.read_text(encoding="utf-8")
    match = re.search(r"^\t\tlocal function info_field\(.*?^\t\tend$", source, re.S | re.M)
    assert match, "info_field() not found in redis.lua -- did it get renamed or reindented?"
    return "\n".join(line[2:] if line.startswith("\t\t") else line for line in match.group(0).splitlines())


def _run(body: str) -> str:
    assert LUA is not None
    result = subprocess.run([LUA, "-"], input=_info_field_source() + "\n" + body, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@needs_lua
@pytest.mark.parametrize(
    ("payload", "field", "expected"),
    [
        (INFO_MEMORY, "used_memory", "1048576"),
        (INFO_MEMORY, "maxmemory", "268435456"),
        (INFO_MEMORY, "maxmemory_policy", "noeviction"),
        (INFO_STATS, "evicted_keys", "7"),
    ],
)
def test_info_field_picks_the_exact_field(payload, field, expected):
    assert _run(f'print(info_field("{payload}", "{field}"))') == expected


@needs_lua
def test_a_failed_info_call_does_not_break_the_stats_response():
    # clusterstore:call() returns nil on error and the handler keeps going on purpose: INFO is
    # best-effort and must never turn a working stats call into a 500.
    assert _run('print(tostring(info_field(nil, "used_memory")))') == "nil"
    assert _run('print(tostring(info_field(false, "used_memory")))') == "nil"
    assert _run(f'print(tostring(info_field("{INFO_MEMORY}", "not_a_field")))') == "nil"


def test_the_stats_handler_reports_the_eviction_fields():
    source = REDIS_LUA.read_text(encoding="utf-8")
    for field in ("redis_used_memory", "redis_maxmemory", "redis_maxmemory_policy", "redis_evicted_keys"):
        assert f"data.{field} = " in source, f"{field} missing from the /redis/stats payload"
    assert "redis_nb_keys = nb_keys" in source, "the original key count must survive"


def test_the_connection_is_closed_on_every_path():
    """dbsize used to close before its own error branches ran; the INFO calls added more."""
    source = REDIS_LUA.read_text(encoding="utf-8")
    stats = source.split('if self.ctx.bw.uri == "/redis/stats"')[1]
    returns = len(re.findall(r"return self:ret\(", stats))
    closes = len(re.findall(r"self\.clusterstore:close\(\)", stats))
    # One close per error return that happens after connect(), plus the success path.
    assert closes >= 3, f"/redis/stats has {returns} returns but only {closes} close() calls"
