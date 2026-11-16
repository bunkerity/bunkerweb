"""Real Lua/filesystem proof: interrupted config swaps remain marked across restart."""

from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
LUA = shutil.which("lua") or shutil.which("luajit")
pytestmark = pytest.mark.skipif(not LUA, reason="Lua interpreter unavailable")


@pytest.mark.parametrize(
    "failure,preexisting,expected",
    [("none", False, False), ("none", True, False), ("rollback", False, False), ("rollback", True, True), ("incomplete", False, True), ("raise", False, True)],
)
def test_config_install_sentinel(tmp_path, failure, preexisting, expected):
    dest = tmp_path / "dest"
    stage = dest / ".bw-staging"
    stage.mkdir(parents=True)
    (dest / "policy.conf").write_text("old")
    (stage / "policy.conf").write_text("new")
    sentinel = dest / ".bw-install-incomplete"
    if preexisting:
        sentinel.touch()
    code = r"""
local dest, stage, failure = arg[1], arg[2], arg[3]
local original_rename, original_execute = os.rename, os.execute
local checked = false
local function present()
    local f = io.open(dest .. "/.bw-install-incomplete", "r")
    if f then f:close(); return true end
    return false
end
os.rename = function(from, to)
    if not from:find(".bw-rescue.", 1, true) then
        checked = true
        assert(present(), "install mutated live tree without sentinel")
    end
    if failure == "raise" then error("injected install exception") end
    if failure ~= "none" and from == stage .. "/policy.conf" then return nil, "injected placement failure" end
    if failure == "incomplete" and from:find(".bw-trash/policy.conf", 1, true) then return nil, "injected rollback failure" end
    return original_rename(from, to)
end
os.execute = function(cmd)
    if failure ~= "none" and cmd:match("^cp %-a ") then return false end
    return original_execute(cmd)
end
local pushswap = require "bunkerweb.pushswap"
pushswap.SENTINEL_DESTINATION = dest
local ran, ok, err, incomplete = pcall(pushswap.swap, dest, stage)
assert(checked, "test did not reach installation")
if failure == "none" then assert(ran and ok, tostring(err))
elseif failure == "raise" then assert(not ran and ok:find("injected install exception", 1, true), tostring(ok))
else assert(ran and not ok, "failure incorrectly reported success") end
print("sentinel=" .. tostring(present()))
"""
    result = subprocess.run(
        [LUA, "-e", f'package.path = "{ROOT}/src/bw/lua/?.lua;" .. package.path', "-", str(dest), str(stage), failure],
        input=code,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"sentinel={str(expected).lower()}"
    if failure in ("none", "rollback"):
        assert (dest / "policy.conf").read_text() == ("new" if failure == "none" else "old")
