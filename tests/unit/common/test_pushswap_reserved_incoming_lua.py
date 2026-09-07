"""An archive that carries a reserved ``.bw-`` entry must never have it placed.

Port of dev ``32a2985ab``'s swap half. The reserved prefix is ``pushswap``'s own bookkeeping:
``.bw-staging`` is the tree being swapped in, ``.bw-trash`` holds the parked originals and
``.bw-rescue.<epoch>`` (this tree's row 19) holds the copies a stuck rollback preserved. The
stale-entry sweep is REQUIRED to skip that prefix, so anything reserved that gets placed into a
destination is never cleared again.

On Linux and all-in-one the archived source directory and the receiver destination are the same
path, so a rescue copy -- or a staging directory left by a worker killed mid-push -- travels back
inside the next archive. Before this fix the incoming loop placed it: one accumulating copy of the
tree per incident, in the very directory NGINX reads, and ``cp -R destination/. backup/`` then
copies the pile into every later backup.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PUSHSWAP_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "pushswap.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua binary is not installed")

SCRIPT = """
package.path = "{lua_dir}/?.lua;" .. package.path
local pushswap = require("bunkerweb.pushswap")
local root = "{root}"
local ok, err = pushswap.swap(root .. "/dest", root .. "/dest/.bw-staging")
print("swap:", tostring(ok), tostring(err))
"""


def _swap(tmp_path: Path):
    assert PUSHSWAP_LUA.is_file(), f"{PUSHSWAP_LUA} is gone"
    dest = tmp_path / "dest"
    staging = dest / ".bw-staging"
    (staging / ".bw-rescue.1788000000").mkdir(parents=True)
    (staging / ".bw-rescue.1788000000" / "old.conf").write_text("rescued", encoding="utf-8")
    (staging / "server.conf").write_text("new", encoding="utf-8")
    (dest / "server.conf").write_text("old", encoding="utf-8")
    # A rescue already parked in the destination by an earlier incomplete rollback.
    (dest / ".bw-rescue.1787000000").mkdir()
    (dest / ".bw-rescue.1787000000" / "kept.conf").write_text("kept", encoding="utf-8")

    result = subprocess.run(
        ["lua", "-e", SCRIPT.format(lua_dir=(ROOT / "src" / "bw" / "lua").as_posix(), root=tmp_path.as_posix())],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "swap:\ttrue" in result.stdout, result.stdout
    return dest


def test_a_reserved_entry_inside_the_archive_is_never_placed(tmp_path):
    dest = _swap(tmp_path)

    assert (dest / "server.conf").read_text(encoding="utf-8") == "new", "the real entry must still swap in"
    assert not (dest / ".bw-rescue.1788000000").exists(), "a reserved name the sweep skips must never be placed"


def test_a_rescue_already_parked_in_the_destination_survives_the_swap(tmp_path):
    """Row 19's guarantee, re-pinned here: the sweep skips the prefix in BOTH directions."""
    dest = _swap(tmp_path)

    assert (dest / ".bw-rescue.1787000000" / "kept.conf").read_text(encoding="utf-8") == "kept"
