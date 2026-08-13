"""The two client-controlled strings stored per blocked request must be truncated at write.

NGINX accepts an 8k request line and an 8k header by default, and both the URL and the User-Agent
used to be stored verbatim in every record. METRICS_MAX_BLOCKED_REQUESTS keeps 1000 of them per
worker, mirrored into the Redis list and into every scrape payload — so a client choosing its own
User-Agent could inflate that buffer into megabytes against a datastore capped at 256mb in every
shipped stack. The count was bounded; the size of each record was not.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
METRICS_LUA = ROOT / "src" / "common" / "core" / "metrics" / "metrics.lua"

LUA = shutil.which("lua") or shutil.which("luajit")
needs_lua = pytest.mark.skipif(LUA is None, reason="no stand-alone lua/luajit on PATH")


def _source() -> str:
    return METRICS_LUA.read_text(encoding="utf-8")


def _extract(name: str) -> str:
    match = re.search(rf"^local function {name}\(.*?^end$", _source(), re.S | re.M)
    assert match, f"{name} not found in metrics.lua — did it get renamed?"
    return match.group(0)


def _limit(name: str) -> int:
    match = re.search(rf"^local {name} = (\d+)$", _source(), re.M)
    assert match, f"{name} not found in metrics.lua"
    return int(match.group(1))


def _run(body: str) -> str:
    assert LUA is not None
    script = _extract("bound") + "\n" + body
    result = subprocess.run([LUA, "-"], input=script, capture_output=True, text=True)
    assert result.returncode == 0, f"lua failed:\n{result.stdout}\n{result.stderr}"
    return result.stdout.strip()


@needs_lua
def test_long_values_are_truncated_with_a_marker():
    assert _run('print(bound(string.rep("a", 5000), 2048))') == "a" * 2048 + "..."


@needs_lua
def test_short_values_pass_through_untouched():
    # Byte-identical, not merely short enough: an unconditional sub() would strip nothing but
    # would still allocate a copy of every URL on the hot log path.
    assert _run('print(bound("/login?next=/admin", 2048))') == "/login?next=/admin"
    assert _run('print(bound(string.rep("b", 2048), 2048))') == "b" * 2048


@needs_lua
def test_non_strings_survive():
    # http_user_agent is nil when the header is absent, and the baseline record passes it
    # straight through. Returning "" or erroring there would change what gets persisted.
    assert _run("print(tostring(bound(nil, 512)))") == "nil"
    assert _run("print(bound(42, 512))") == "42"


def test_both_client_controlled_fields_are_bounded():
    """A new field copied from ctx.bw without bound() is the way this regresses."""
    source = _source()
    for field, limit in (("url", "MAX_STORED_URL"), ("user_agent", "MAX_STORED_USER_AGENT")):
        assignments = re.findall(rf"^\s*(?:request\.)?{field} = (.+?),?$", source, re.M)
        assert assignments, f"no {field} assignment found in metrics.lua"
        unbounded = [a for a in assignments if "bound(" not in a]
        assert not unbounded, f"{field} stored without bound(): {unbounded}"
        assert f"local {limit} = " in source


def test_the_caps_stay_sane():
    # Big enough to keep real traffic intact (URLs over 2k are already pathological, and the
    # longest real User-Agent strings sit near 256), small enough that 1000 records stay in
    # single-digit megabytes.
    assert 512 <= _limit("MAX_STORED_URL") <= 8192
    assert 128 <= _limit("MAX_STORED_USER_AGENT") <= 2048
