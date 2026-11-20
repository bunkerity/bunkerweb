r"""The Linux start functions recreate the PID, TMP and LOG directories that a reboot wipes.

`/var/run` is a tmpfs, so after a reboot `/var/run/bunkerweb` is gone and nginx could not write its pid file:
the service failed to start. `start.sh` and the scheduler, UI and API unit scripts now create the three
directories (owned by nginx, TMP setgid `2770`) before anything runs. The three blocks are lifted from each
script and run against a temp root with a recording `chown`.

Refs #615, #2929.
"""

import pytest
from _t7_helpers import bash, block, retarget, source

SCRIPTS = [
    "src/linux/scripts/start.sh",
    "src/linux/scripts/bunkerweb-scheduler.sh",
    "src/linux/scripts/bunkerweb-ui.sh",
    "src/linux/scripts/bunkerweb-api.sh",
]
DIRS = ("var/run/bunkerweb", "var/tmp/bunkerweb", "var/log/bunkerweb")


def _run(tmp_path, script_path):
    lifted = block(source(script_path), r"^\s*# Create PID folder\n.*?^\s*# Create LOG folder\n\s*if .*?^\s*fi\n", "the runtime directory blocks")
    script = 'chown() { echo "$*" >> "$CHOWNS"; }\nCHOWNS="%s/chowns"\n%s\necho done\n' % (
        tmp_path,
        retarget(lifted, tmp_path, "/var/run", "/var/tmp", "/var/log"),
    )
    result = bash(script, env={"PATH": "/usr/bin:/bin"})
    chowns = (tmp_path / "chowns").read_text(encoding="utf-8").splitlines() if (tmp_path / "chowns").exists() else []
    return result, chowns


@pytest.mark.parametrize("script_path", SCRIPTS)
def test_a_rebooted_host_gets_every_runtime_directory(tmp_path, script_path):
    """After a reboot none of the directories exists, and the parents may not either."""
    result, chowns = _run(tmp_path, script_path)

    assert result.returncode == 0, result.stderr
    for directory in DIRS:
        assert (tmp_path / directory).is_dir(), f"{directory} was not recreated"
        assert f"nginx:nginx {tmp_path / directory}" in chowns, f"{directory} was not handed to nginx: {chowns}"
    assert (tmp_path / "var/tmp/bunkerweb").stat().st_mode & 0o7777 == 0o2770, "the TMP directory lost its setgid group-writable mode"


@pytest.mark.parametrize("script_path", SCRIPTS)
def test_existing_directories_and_their_content_are_kept(tmp_path, script_path):
    """Anti-vacuity: a plain restart must not wipe what the directories hold."""
    keep = tmp_path / "var/tmp/bunkerweb/keep.txt"
    keep.parent.mkdir(parents=True)
    keep.write_text("state", encoding="utf-8")

    result, _ = _run(tmp_path, script_path)

    assert result.returncode == 0, result.stderr
    assert keep.read_text(encoding="utf-8") == "state"
    assert (tmp_path / "var/run/bunkerweb").is_dir()
