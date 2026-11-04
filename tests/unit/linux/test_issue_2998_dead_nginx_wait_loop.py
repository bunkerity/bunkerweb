r"""The supervisor loop ends when nginx dies without removing its pid file.

An nginx killed by the OOM killer leaves `/var/run/bunkerweb/nginx.pid` behind. The Docker entrypoint then
called `wait` on the dead child in a tight loop (100% CPU, container never exits), and the Linux start script
polled a pid file that no longer meant anything. Both loops now check the pid with `kill -0`, drop the stale
file and fall out so the container or service restarts. The loops are lifted from `src/bw/entrypoint.sh` and
`src/linux/scripts/start.sh` and run against a temp pid file; a hang is a failure, not a timeout error.

Refs #2998.
"""

import subprocess
import time

import pytest
from _t7_helpers import bash, block, retarget, source

DOCKER_LOOP = block(source("src/bw/entrypoint.sh"), r'^# wait while nginx is running\nwait "\$pid"\nwhile .*?^done\n', "the entrypoint wait loop")
LINUX_LOOP = block(source("src/linux/scripts/start.sh"), r"^\s*while \[ -f /var/run/bunkerweb/nginx\.pid \] ; do\n.*?^\s*done\n", "the start.sh wait loop")

# `sleep` is shortened so a loop that does run finishes fast; nothing else is stubbed.
HARNESS = """
sleep() {{ command sleep 0.05; }}
pidfile="{pidfile}"
{setup}
{loop}
echo ended
"""


def _run(tmp_path, loop, setup):
    (tmp_path / "var/run/bunkerweb").mkdir(parents=True)
    pidfile = tmp_path / "var/run/bunkerweb/nginx.pid"
    script = HARNESS.format(pidfile=pidfile, setup=setup, loop=retarget(loop, tmp_path, "/var/run"))
    try:
        result = bash(script, env={"PATH": "/usr/bin:/bin"}, timeout=10)
    except subprocess.TimeoutExpired:
        pytest.fail("the wait loop never ended: a stale pid file keeps the supervisor spinning")
    return result, pidfile


DEAD_CHILD = 'command sleep 300 & pid=$!; echo "$pid" > "$pidfile"; kill -9 "$pid"; wait "$pid" 2>/dev/null'


@pytest.mark.parametrize("loop", [DOCKER_LOOP, LINUX_LOOP], ids=["docker", "linux"])
def test_a_dead_nginx_with_a_stale_pid_file_ends_the_loop_and_clears_the_file(tmp_path, loop):
    result, pidfile = _run(tmp_path, loop, DEAD_CHILD)

    assert result.returncode == 0, result.stderr
    assert "ended" in result.stdout
    assert not pidfile.exists(), "the stale pid file must be removed so the next start is not confused"


def test_a_live_nginx_keeps_the_linux_loop_waiting_until_it_exits(tmp_path):
    """Anti-vacuity: the loop must still wait while nginx runs, or the test above passes trivially."""
    setup = 'command sleep 300 & pid=$!; echo "$pid" > "$pidfile"; ( command sleep 0.4; kill -9 "$pid" ) &'
    started = time.monotonic()
    result, pidfile = _run(tmp_path, LINUX_LOOP, setup)

    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started >= 0.35, "the loop gave up while nginx was still running"
    assert "ended" in result.stdout
    assert not pidfile.exists()
