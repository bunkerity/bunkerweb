"""``.bw-rescue.<epoch>`` directories must eventually go, and never the wrong ones.

Lane PS-1 (wave 14), DEV-2b5 residual 2 (raised by Criticos on DEV-2b3 row 19, carried in
``commit-DEV-2b3.md`` §6). A rescue holds the copies a stuck rollback preserved -- for an entry the
ordered undo could not put back, it is the ONLY copy left anywhere. Row 19 made it safe to leave
one behind and row 22 stopped it travelling back inside the next archive, but nothing ever removed
one, and ``api.lua`` opens every push with ``cp -R <destination>/. <backup>/``: every accumulated
rescue is copied into every later backup, so on the disk-full case a rescue exists for, each
incident makes the NEXT push more likely to fail than the one that produced it.

The age is read from the NAME, not from ``stat``. ``swap()`` stamps the name at the moment the
rescue is created, whereas an mtime is whatever last touched the tree: an operator copying a file
out of a rescue would push their own rescue back out of reach for another full window, which is the
opposite of what an operator doing recovery work needs.

Runs the real module through the ``lua`` binary against a real temporary tree -- ``pushswap.lua`` is
deliberately free of any ngx dependency, so nothing here is stubbed at all.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PUSHSWAP_LUA = ROOT / "src" / "bw" / "lua" / "bunkerweb" / "pushswap.lua"

pytestmark = pytest.mark.skipif(shutil.which("lua") is None, reason="the lua binary is not installed")

NOW = 1_800_000_000
DAY = 24 * 3600

SCRIPT = """
package.path = "{lua_dir}/?.lua;" .. package.path
local pushswap = require("bunkerweb.pushswap")
print("MAX_AGE=" .. tostring(pushswap.RESCUE_MAX_AGE))
print("REMOVED=" .. tostring(pushswap.reap_rescues("{dest}", {now})))
"""


@pytest.fixture
def dest(tmp_path):
    assert PUSHSWAP_LUA.is_file(), f"{PUSHSWAP_LUA} is gone"
    tree = tmp_path / "dest"
    tree.mkdir()
    for name in (
        f".bw-rescue.{NOW - 30 * DAY}",  # a month old: gone
        f".bw-rescue.{NOW - 8 * DAY}",  # just past the window: gone
        f".bw-rescue.{NOW - 8 * DAY}.1",  # the collision form of the same: gone
        f".bw-rescue.{NOW - 2 * DAY}",  # inside the window: kept
        # Unreadable age: kept. It carries digits deliberately -- a name with none cannot tell an
        # anchored `^%d+` from a floating `%d+`, and the floating form would read this as epoch
        # 1000000000 and reap it.
        ".bw-rescue.x1000000000",
        ".bw-trash",  # this swap's own bookkeeping: never a rescue
        ".bw-staging",
        "server.conf",  # a real configuration entry
        # A real /var/cache/bunkerweb entry, and the one that makes the prefix guard load-bearing:
        # `.bw-rescue.` is 11 characters, so character 12 onward of THIS name is "2024.mmdb", which
        # reads as an epoch of 2024 -- i.e. 1970 -- if the sweep ever stops checking the prefix.
        "geoip-city-2024.mmdb",
    ):
        (tree / name).mkdir()
        (tree / name / "payload").write_text(name, encoding="utf-8")
    return tree


@pytest.fixture
def outcome(dest):
    script = SCRIPT.format(lua_dir=(ROOT / "src" / "bw" / "lua").as_posix(), dest=dest.as_posix(), now=NOW)
    result = subprocess.run(["lua", "-e", script], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)


def test_the_window_is_a_week(outcome):
    """Not a derivation -- a chosen window. Pinned so shortening it is a deliberate edit."""
    assert outcome["MAX_AGE"] == str(7 * DAY)


def test_the_expired_rescues_are_removed(outcome, dest):
    assert outcome["REMOVED"] == "3"
    assert not (dest / f".bw-rescue.{NOW - 30 * DAY}").exists()
    assert not (dest / f".bw-rescue.{NOW - 8 * DAY}").exists()


def test_the_collision_suffixed_form_is_reaped_too(outcome, dest):
    """Two stuck rollbacks inside one second produce `.bw-rescue.<epoch>.1`; a matcher anchored on
    the whole name would leave every one of those behind forever."""
    assert not (dest / f".bw-rescue.{NOW - 8 * DAY}.1").exists()


def test_a_rescue_inside_the_window_is_kept(outcome, dest):
    """It is the only copy of an entry, and an operator has not had a week to find it yet."""
    assert (dest / f".bw-rescue.{NOW - 2 * DAY}" / "payload").is_file()


def test_a_rescue_whose_stamp_does_not_parse_is_kept(outcome, dest):
    """An unreadable age is not evidence of an old directory. Deleting on a failed parse would make
    a future rename to a non-numeric suffix silently destructive."""
    assert (dest / ".bw-rescue.x1000000000" / "payload").is_file()


def test_nothing_else_reserved_is_touched(outcome, dest):
    """`.bw-trash` is live bookkeeping mid-swap and `.bw-staging` holds the incoming tree: reaping
    either would delete a push out from under itself."""
    assert (dest / ".bw-trash" / "payload").is_file()
    assert (dest / ".bw-staging" / "payload").is_file()


def test_a_real_configuration_entry_is_never_touched(outcome, dest):
    assert (dest / "server.conf" / "payload").is_file()


def test_an_entry_that_only_looks_stamped_past_the_prefix_is_never_touched(dest, outcome):
    """The prefix check is what makes the stamp parse safe to run at all.

    Offset 12 of a name is only an epoch when the first 11 characters are `.bw-rescue.`. Drop that
    guard and `geoip-city-2024.mmdb` yields the stamp 2024 -- fifty years past any window -- and the
    sweep deletes a GeoIP database out of `/var/cache/bunkerweb` on every successful push.
    """
    assert (dest / "geoip-city-2024.mmdb" / "payload").is_file()
