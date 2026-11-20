"""`run_as_nginx` must give the nginx user a writable HOME, on every branch it can take.

The BunkerWeb services start as root and drop to the nginx uid through whichever of four helpers
exists on the host. None of them resets `HOME`: `setpriv` and `runuser` leave the environment
alone, and `sudo -E` / `su -m` preserve it deliberately. So the dropped process inherited
`HOME=/root`, and anything resolving a dotfile from it failed on permissions -- libpq reading
`$HOME/.postgresql/postgresql.crt` being the one that broke database connections outright.

The bug is per-branch, which is why this file tests four branches rather than one: a fix applied to
`setpriv` alone would look correct on the developer's box and fail on a host that only has `su`.
Each branch is exercised by putting a stub helper first on `PATH` that echoes its argv, so the test
needs neither root nor a real nginx user.

The `export_env_file` cases at the end pin a guard that is ALREADY in the tree (1.7 validates the
key before `export`). They exist because dev carries the same fix in a terser form
(`[[ ... ]] || continue`), so a verbatim port would replace a documented block -- including the
comment explaining why dotted multisite keys are skipped -- with a one-liner. A test makes that
attempt fail loudly instead of silently deleting the reasoning.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "common" / "helpers" / "utils.sh"

# `/var/lib/bunkerweb` is `chown -R nginx:nginx` at src/linux/scripts/postinstall.sh:70, which is
# what makes it a valid HOME rather than merely a writable-looking path.
EXPECTED_HOME = "HOME=/var/lib/bunkerweb"

HELPERS = ("setpriv", "runuser", "sudo", "su")


def test_helpers_covers_every_branch_of_run_as_nginx():
    """RULE 13 + 14b: the parametrized cases below are only as wide as this tuple.

    Two failures this catches, and they need different comparators, so both are here:

    * `>=`, a floor -- an emptied HELPERS makes every parametrized case *vanish*. Pytest reports
      that as success, not as failure: "0 failed" and "nothing ran" are the same output.
    * `==` against the branches derived from the shell -- a fifth helper added to `run_as_nginx`
      without `HOME=` is the exact regression these tests exist for, and a hardcoded four-tuple
      cannot see it. Growth is the defect *here* (an uncovered branch), so this one is exact:
      add the branch to HELPERS and the HOME assertion covers it automatically.

    The floor is not redundant with the equality: `set() == ()` passes vacuously.
    """
    body = UTILS.read_text(encoding="utf-8").split("function run_as_nginx()", 1)[1].split("\n}", 1)[0]
    branches = re.findall(r"command -v (\w+)", body)

    assert len(HELPERS) >= 4, f"HELPERS shrank to {len(HELPERS)} -- the cases below silently stopped running"
    assert set(branches) == set(HELPERS), (
        f"run_as_nginx dispatches on {sorted(branches)} but HELPERS covers {sorted(HELPERS)}; "
        "a branch nobody parametrized is a branch nobody proved sets HOME"
    )


def _stub_path(tmp_path: Path, only: str) -> str:
    """A PATH holding exactly one of the four helpers, which echoes the argv it was called with.

    Two traps, both found the hard way:

    * `utils.sh:5-7` REWRITES PATH when it is sourced -- if `/usr/local/bin` is not already in it,
      the file prepends the whole standard set. A test that trims PATH to isolate a branch has its
      restriction silently undone by the file under test, and the *real* helper runs: the first
      version of this test got `setpriv: failed to parse reuid: 'nginx'` from the system binary.
      Keeping the literal `/usr/local/bin` in PATH satisfies that guard, so PATH is left alone.
    * that guard itself shells out to `grep`, so `grep` has to remain reachable -- hence a second
      directory holding just the tools sourcing needs, and nothing that would satisfy `command -v`
      for the three helpers this branch must not find.
    """
    bin_dir = tmp_path / f"bin_{only}"
    bin_dir.mkdir()
    stub = bin_dir / only
    stub.write_text('#!/bin/sh\necho "ARGV: $*"\n', encoding="utf-8")
    stub.chmod(0o755)

    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    for tool in ("grep",):
        real = shutil.which(tool)
        assert real, f"{tool} is needed to source utils.sh"
        target = tools / tool
        if not target.exists():
            target.symlink_to(real)

    return f"{bin_dir}:{tools}:/usr/local/bin"


def _run_as_nginx(tmp_path: Path, helper: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    # `command -v` then finds this helper and none of the other three, so the branch under test
    # is the one that runs.
    env["PATH"] = _stub_path(tmp_path, helper)
    env["UTILS"] = str(UTILS)
    return subprocess.run(
        # /bin/bash by absolute path: PATH holds only the stub directory, so `bash` itself would
        # not be found there. Same reason `/usr/bin/true` is absolute below.
        ["/bin/bash", "-c", 'source "$UTILS"; run_as_nginx /usr/bin/true --marker'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("helper", HELPERS)
def test_every_branch_sets_a_writable_home(tmp_path, helper):
    result = _run_as_nginx(tmp_path, helper)

    assert "ARGV:" in result.stdout, f"the {helper} branch did not run: {result.stdout!r} {result.stderr!r}"
    assert EXPECTED_HOME in result.stdout, f"the {helper} branch drops to nginx with the caller's HOME: {result.stdout.strip()!r}"


@pytest.mark.parametrize("helper", HELPERS)
def test_every_branch_still_passes_the_command_through(tmp_path, helper):
    """A HOME that arrives instead of the command would be worse than the bug."""
    result = _run_as_nginx(tmp_path, helper)

    assert "/usr/bin/true" in result.stdout, result.stdout
    assert "--marker" in result.stdout, f"the {helper} branch lost the command's arguments: {result.stdout.strip()!r}"


def test_the_home_is_a_directory_the_nginx_user_owns():
    """Anti-drift: the value is only correct because postinstall chowns that path to nginx."""
    postinstall = (ROOT / "src" / "linux" / "scripts" / "postinstall.sh").read_text(encoding="utf-8")
    home = EXPECTED_HOME.split("=", 1)[1]

    assert home in UTILS.read_text(encoding="utf-8"), "run_as_nginx no longer sets the HOME this test pins"
    chowned = any(home in line and "chown" in line and "nginx" in line for line in postinstall.splitlines())
    assert chowned, f"{home} is no longer chowned to nginx, so it is no longer a writable HOME"


# ---------------------------------------------------------------------------------------------
# export_env_file: the key guard that is already in the tree
# ---------------------------------------------------------------------------------------------


def _export_env_file(tmp_path: Path, contents: str, probe: str) -> subprocess.CompletedProcess:
    env_file = tmp_path / "variables.env"
    env_file.write_text(contents, encoding="utf-8")
    env = os.environ.copy()
    env.update(UTILS=str(UTILS), ENV_FILE=str(env_file))
    return subprocess.run(
        ["bash", "-c", f'source "$UTILS"; export_env_file "$ENV_FILE"; {probe}'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_valid_key_is_exported(tmp_path):
    result = _export_env_file(tmp_path, "USE_REVERSE_PROXY=yes\n", 'echo "GOT=$USE_REVERSE_PROXY"')

    assert "GOT=yes" in result.stdout, result.stdout


def test_a_dotted_multisite_key_is_skipped_without_an_error(tmp_path):
    """`www.example.com_USE_REVERSE_PROXY` is a real variables.env key. Bash cannot export it.

    The Python config layer reads variables.env as a file, so skipping it costs nothing -- and the
    comment in `export_env_file` saying so is the thing this test protects.
    """
    result = _export_env_file(tmp_path, "www.example.com_USE_REVERSE_PROXY=yes\nGOOD=1\n", 'echo "GOOD=$GOOD"')

    assert "GOOD=1" in result.stdout, result.stdout
    assert "not a valid identifier" not in result.stderr, f"the invalid key reached export: {result.stderr.strip()!r}"


def test_a_hostile_key_is_skipped_and_executes_nothing(tmp_path):
    """`export` takes an assignment, not code, so this was never RCE -- but it must still be skipped.

    Both halves are asserted: the marker file proves nothing ran, and the later valid key proves the
    loop was not aborted by the bad line.
    """
    marker = tmp_path / "pwned"
    result = _export_env_file(tmp_path, f"$(touch {marker})=x\nA;B=y\nGOOD=1\n", 'echo "GOOD=$GOOD"')

    assert not marker.exists(), "a key from variables.env was executed"
    assert "GOOD=1" in result.stdout, f"a bad key stopped the loop: {result.stdout!r} {result.stderr!r}"
