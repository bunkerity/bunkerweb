"""A push-swap whose rollback got stuck must keep the parked copy REACHABLE.

Port of dev ``a0a2bb427``. 1.7 already diverged from dev here — dev removed ``.bw-trash``
unconditionally after a rollback, destroying the only surviving copy of a parked entry, and this
tree keeps the trash whenever anything is stuck. That divergence is half the answer:

* ``.bw-trash`` is a FIXED name and every swap opens with ``rm -rf`` on it, so the copy the
  divergence preserved is destroyed by the very NEXT push — a delay, not a rescue.
* the message named ``<destination>/<entry>``, which is precisely where the entry is NOT: a park
  that could not be restored left it in the parked tree, so the operator was handed a path that
  does not exist.

Both reproduce on the unfixed tree (see the module's git history / the lane report). The fix moves
the whole trash to ``.bw-rescue.<epoch>`` — reserved-prefixed, so no later swap, include glob or
stale-entry sweep touches it — and reports that path.

Runs the real module through the ``lua`` binary against a real temporary tree; ``pushswap.lua`` is
deliberately free of any ngx dependency, so nothing is stubbed but the two libc calls the failure
needs to fake. They are patched BEFORE ``require``: the module captures ``os.rename`` and
``os.execute`` into locals at load time.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PUSHSWAP_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "pushswap.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua binary is not installed")


def _guard():
    """Fail loudly if the module moved, rather than passing on a stub."""
    assert PUSHSWAP_LUA.is_file(), f"{PUSHSWAP_LUA} is gone"
    source = PUSHSWAP_LUA.read_text(encoding="utf-8")
    assert 'pushswap.RESERVED_PREFIX = ".bw-"' in source, "the reserved prefix moved"
    return source


SCRIPT = """
package.path = "{lua_dir}/?.lua;" .. package.path
local root = "{root}"
local dest, staging = root .. "/dest", root .. "/staging"
local blocked = dest .. "/old.conf"

-- Before require: the module binds os.rename / os.execute into locals at load time.
local real_rename, real_execute = os.rename, os.execute
os.rename = function(from, to)
    if to == blocked then return nil, "simulated ENOSPC" end
    return real_rename(from, to)
end
os.execute = function(cmd)
    -- Kill move_entry's copy fallback for this one entry, so the rollback is really stuck.
    if cmd:find("cp %-a ") and cmd:find(blocked, 1, true) then return 1 end
    return real_execute(cmd)
end
local pushswap = require("bunkerweb.pushswap")

local ok, msg, incomplete = pushswap.swap(dest, staging)
print("OK=" .. tostring(ok))
print("INCOMPLETE=" .. tostring(incomplete))
print("MSG=" .. tostring(msg))

os.rename, os.execute = real_rename, real_execute
real_execute("mkdir -p '" .. root .. "/staging2' && echo new2 > '" .. root .. "/staging2/b.conf'")
print("SWAP2=" .. tostring(pushswap.swap(dest, root .. "/staging2")))

local pipe = io.popen("find '" .. dest .. "' -name old.conf -exec cat {{}} +")
print("SURVIVOR=" .. pipe:read("*a"):gsub("\\n", ""))
pipe:close()
"""


@pytest.fixture
def outcome(tmp_path):
    _guard()
    (tmp_path / "dest").mkdir()
    (tmp_path / "staging").mkdir()
    (tmp_path / "dest" / "old.conf").write_text("the only copy")
    (tmp_path / "staging" / "old.conf").write_text("the incoming one")

    script = SCRIPT.format(lua_dir=(ROOT / "src" / "bw" / "lua").as_posix(), root=tmp_path.as_posix())
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_the_swap_reports_the_rollback_as_incomplete(outcome):
    """The floor: without a stuck rollback the rest of this file asserts nothing."""
    assert outcome["OK"] == "false"
    assert outcome["INCOMPLETE"] == "true"


def test_the_parked_copy_survives_the_next_swap(outcome):
    """`.bw-trash` is a fixed name every swap opens by removing; the rescue name is not."""
    assert outcome["SWAP2"] == "true"
    assert outcome["SURVIVOR"] == "the only copy", "the last copy of the parked entry was destroyed by the next push"


def test_the_message_names_where_the_copy_actually_is(outcome):
    """A message pointing at `<destination>/<entry>` sends the operator to a path that is empty."""
    assert "copy kept at " in outcome["MSG"]
    assert ".bw-rescue." in outcome["MSG"]
    assert "/old.conf (copy kept at " in outcome["MSG"]


def test_the_rescue_carries_the_reserved_prefix(outcome):
    """Without it the next swap's stale-entry sweep deletes the rescue as a foreign entry."""
    assert "/.bw-rescue." in outcome["MSG"]
