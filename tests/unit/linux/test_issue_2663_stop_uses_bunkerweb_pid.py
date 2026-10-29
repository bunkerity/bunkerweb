r"""`start.sh stop` follows BunkerWeb's own nginx pid file, never `pgrep nginx`.

`stop()` looked for any process named nginx. On a host that runs another nginx the service never saw
itself stopped (or stopped the wrong one) and failed with a timeout. It now reads
`/var/run/bunkerweb/nginx.pid`, signals that pid, waits on it, and cleans up a stale file. `stop()` is
lifted from `src/linux/scripts/start.sh` and run against a temp pid file next to a decoy process named nginx.

Refs #2663.
"""

import pytest
from _t7_helpers import bash, function, retarget, source

STOP = function(source("src/linux/scripts/start.sh"), "stop")

HARNESS = """
sleep_bin="$(command -v sleep)"
log() {{ echo "$*" >&2; }}
sleep() {{ "$sleep_bin" 0.02; }}
nginx() {{ echo "nginx $*" >> "{root}/nginx-calls"; }}
decoy="{root}/decoy-bin/nginx"
mkdir "{root}/decoy-bin"
printf '#!/bin/bash\nmkfifo "$1"\nexec 3<>"$1"\nread -r -t 300 -u 3 _\n' > "$decoy"
chmod +x "$decoy"
"$decoy" "{root}/decoy.fifo" &
decoy_pid=$!
target=0
{setup}
{stop}
# a subshell: stop() ends with `exit 1` on failure, which must not skip the cleanup below
( stop )
rc=$?
if kill -0 "$decoy_pid" 2>/dev/null; then echo decoy-alive; else echo decoy-dead; fi
if [ "$target" != 0 ] && kill -0 "$target" 2>/dev/null; then echo target-alive; else echo target-dead; fi
kill -9 "$decoy_pid" 2>/dev/null
[ "$target" != 0 ] && kill -9 "$target" 2>/dev/null
exit $rc
"""


# A script named nginx has the process name `nginx` (a renamed coreutils binary refuses to run), which is
# what the old `pgrep nginx` matched. The `nginx` function above keeps the real binary out of reach.
def _run(tmp_path, setup):
    pid_dir = tmp_path / "var/run/bunkerweb"
    pid_dir.mkdir(parents=True)
    script = HARNESS.format(root=tmp_path, setup=setup.format(pidfile=pid_dir / "nginx.pid"), stop=retarget(STOP, tmp_path, "/var/run"))
    return bash(script, env={"PATH": "/usr/bin:/bin"}, timeout=30), pid_dir / "nginx.pid"


def test_the_process_in_the_pid_file_is_stopped_and_the_file_removed(tmp_path):
    result, pidfile = _run(tmp_path, '"$sleep_bin" 300 & target=$!; echo "$target" > "{pidfile}"')

    assert result.returncode == 0, result.stderr
    assert not pidfile.exists()
    assert "target-dead" in result.stdout, "the process named in the pid file was not stopped"
    assert not (tmp_path / "nginx-calls").exists(), "stop() must signal the pid file's process, not shell out to `nginx -s`"
    assert "decoy-alive" in result.stdout, "an unrelated process named nginx must not be touched"


def test_an_unrelated_nginx_does_not_make_stop_wait_or_fail(tmp_path):
    """No pid file: BunkerWeb is not running. A `pgrep nginx` check saw the decoy and waited for it."""
    result, _ = _run(tmp_path, ":")

    assert result.returncode == 0, result.stderr
    assert "nginx is not running" in result.stderr
    assert "decoy-alive" in result.stdout
    assert "Timeout while waiting" not in result.stderr
    assert not (tmp_path / "nginx-calls").exists(), "stop() reached for `nginx -s stop` with no BunkerWeb nginx running"


@pytest.mark.parametrize("content", ["999999", ""])
def test_a_stale_pid_file_is_cleaned_up(tmp_path, content):
    result, pidfile = _run(tmp_path, f'printf "%s" "{content}" > "{{pidfile}}"')

    assert result.returncode == 0, result.stderr
    assert not pidfile.exists(), "a stale pid file would make the next start believe nginx runs"
    assert "decoy-alive" in result.stdout
