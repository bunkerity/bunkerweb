r"""`run_as_nginx` drops a command to the nginx user through the first helper the host has.

The Linux services run as root but start gunicorn and the generator as nginx. Going through `sudo -E` kept
root's environment, so the nginx-uid process hit `Permission denied` on `/root` and the UI never started.
`run_as_nginx` (helpers/utils.sh) picks `setpriv`, then `runuser`, `sudo`, `su`, and runs the command under
`env HOME=/var/lib/bunkerweb` so nothing resolves a dotfile from root's home. Each helper is a recording stub
on an otherwise empty PATH, so the real function runs and no process is actually switched.

Refs #2743.
"""

import pytest
from _t7_helpers import bash, function, source

RUN_AS_NGINX = function(source("src/common/helpers/utils.sh"), "run_as_nginx")
COMMAND = ("python", "-m", "gunicorn", "--chdir", "/some dir")
HELPERS = ("setpriv", "runuser", "sudo", "su")


def _run(tmp_path, available, *, rc=0):
    stubs = tmp_path / "bin"
    stubs.mkdir()
    log = tmp_path / "calls"
    for name in available:
        stub = stubs / name
        stub.write_text(f'#!/bin/bash\necho "{name} $*" >> "{log}"\nexit {rc}\n', encoding="utf-8")
        stub.chmod(0o755)
    result = bash(f'{RUN_AS_NGINX}\nrun_as_nginx "$@"', *COMMAND, env={"PATH": str(stubs)})
    return result, (log.read_text(encoding="utf-8").splitlines() if log.exists() else [])


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (HELPERS, "setpriv --reuid=nginx --regid=nginx --init-groups --inh-caps=-all -- env HOME=/var/lib/bunkerweb python -m gunicorn --chdir /some dir"),
        (HELPERS[1:], "runuser -u nginx -- env HOME=/var/lib/bunkerweb python -m gunicorn --chdir /some dir"),
        (HELPERS[2:], "sudo -n -E -u nginx -g nginx -- env HOME=/var/lib/bunkerweb python -m gunicorn --chdir /some dir"),
    ],
    ids=["setpriv", "runuser", "sudo"],
)
def test_the_first_available_helper_runs_the_command_with_a_clean_home(tmp_path, available, expected):
    result, calls = _run(tmp_path, available)

    assert result.returncode == 0, result.stderr
    assert calls == [expected], f"only the first helper may run, with HOME reset: {calls}"


def test_su_is_the_last_resort_and_quotes_the_arguments(tmp_path):
    result, calls = _run(tmp_path, ("su",))

    assert result.returncode == 0, result.stderr
    assert len(calls) == 1 and calls[0].startswith("su -m nginx -c "), calls
    assert "HOME=/var/lib/bunkerweb" in calls[0]
    assert r"/some\ dir" in calls[0], "an argument with a space must stay one word for the inner shell"


def test_the_helper_exit_status_is_the_commands(tmp_path):
    result, _ = _run(tmp_path, HELPERS, rc=7)

    assert result.returncode == 7


def test_no_helper_means_failure_not_a_root_run(tmp_path):
    """Running the command as root when nobody can drop privileges would be worse than not running it."""
    result, calls = _run(tmp_path, ())

    assert result.returncode == 1
    assert calls == []
