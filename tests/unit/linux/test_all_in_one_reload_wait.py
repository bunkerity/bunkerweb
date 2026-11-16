"""The all-in-one HUP waits for a configuration install before it restarts the services.

The shipped trap functions run in a bash with stub ``supervisorctl`` and ``pgrep``, paths confined to tmp_path.
The stub models the services the entrypoint configured (``autostart`` in the ini files) and the state and exit status supervisord reports for each.
The entrypoint reads them over XML-RPC through the Python interpreter ``supervisor_python`` names: the tests point it at a stub that prints what the real helper would.
``ENTRYPOINT_UNDER_TEST`` points at another copy of the script (the RED proof runs the pre-fix one).
"""

import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = Path(os.environ.get("ENTRYPOINT_UNDER_TEST", ROOT / "src/all-in-one/entrypoint.sh"))

DRIVER = r"""
SANDBOX="$1"
log() { echo "log: $*" >> "$SANDBOX/calls.log"; }
pgrep() { [ ! -f "$SANDBOX/supervisord.down" ]; }
pkill() { :; }
supervisorctl() {
    if [ -e "$SANDBOX/etc/nginx/.bw-install-incomplete" ]; then state=install-in-progress; else state=no-install; fi
    echo "supervisorctl $* ($state)" >> "$SANDBOX/calls.log"
    case "$1" in
    shutdown) touch "$SANDBOX/supervisord.down" ;;
    update) [ -e "$SANDBOX/ctl/fail-update" ] && return 1 ;;
    restart) [ -e "$SANDBOX/ctl/fail-restart" ] && return 1 ;;
    status) PROCESS_INFO_QUIET=1 "$SANDBOX/ctl/process-info" | awk '{ print $1, $2 }' ;;
    esac
    return 0
}
%(slice)s
%(scenario)s
# the handler reports a refused reload through its status; the driver only reads the calls
exit 0
"""


def _slice():
    text = ENTRYPOINT.read_text()
    begin = text.find("# A stop requested while a reload waits")
    if begin < 0:
        begin = text.index("# trap SIGTERM and SIGINT")
    end = text.index("trap trap_reload HUP") + len("trap trap_reload HUP")
    return text[begin:end]


# name -> (enabled, state after the restart[, extra ini lines]): bunkerweb is always on, ui is disabled and its start spawn-errors
BENIGN = {"bunkerweb": (True, "RUNNING"), "ui": (False, "FATAL")}
# the shipped worker-heavy.ini declares exit 3 intentional: supervisord restarts any other exit
HEAVY_INI = "autorestart=unexpected\nexitcodes=3\n"


# the stub standing in for the Python interpreter: what the helper prints, ``<name> <state> <exitstatus>`` per program, changing across calls
PROCESS_INFO_STUB = """#!/bin/bash
SANDBOX="${0%/ctl/process-info}"
if [ -e "$SANDBOX/ctl/info-unreadable" ]; then
    echo "supervisor getAllProcessInfo (unreadable)" >> "$SANDBOX/calls.log"
    echo "ConnectionRefusedError: [Errno 111] Connection refused" >&2
    exit 1
fi
if [ -e "$SANDBOX/etc/nginx/.bw-install-incomplete" ]; then state=install-in-progress; else state=no-install; fi
[ -n "$PROCESS_INFO_QUIET" ] || echo "supervisor getAllProcessInfo ($state)" >> "$SANDBOX/calls.log"
n=$(cat "$SANDBOX/ctl/n" 2>/dev/null || echo 0)
echo $((n + 1)) > "$SANDBOX/ctl/n"
if [ -e "$SANDBOX/ctl/status.$n" ]; then cat "$SANDBOX/ctl/status.$n"; else cat "$SANDBOX/ctl/status"; fi
"""


def _status(states):
    """``EXITED:3`` is the state EXITED with exit status 3 (0 without a suffix); an empty state leaves the program out, as an absent one."""
    rows = []
    for name, state in states.items():
        state, _, exitstatus = state.partition(":")
        if state:
            rows.append(f"{name} {state} {exitstatus or 0}\n")
    return "".join(rows)


# The services' settle deadline for a case that never settles: it ends the wait, so it is also the cost of the test.
STUCK = 1


def _run(tmp_path, scenario, *, sentinel=False, timeout=2, settle=30, fail=(), services=BENIGN, earlier=()):
    """``earlier``: one {service: state} override per first read of the process info, the base states after them.

    ``settle`` is the services' settle deadline in seconds, measured by the loop with the whole-second ``SECONDS``. A case that must settle keeps the
    shipped budget, far above what it needs, so host speed cannot expire it; only a case stuck at the deadline shortens it (``STUCK``) to end fast.
    """
    (tmp_path / "etc/nginx").mkdir(parents=True)
    (tmp_path / "etc/supervisor.d").mkdir()
    (tmp_path / "ctl").mkdir()
    stub = tmp_path / "ctl/process-info"
    stub.write_text(PROCESS_INFO_STUB)
    stub.chmod(0o755)
    states = {name: spec[1] for name, spec in services.items()}
    (tmp_path / "ctl/status").write_text(_status(states))
    for index, override in enumerate(earlier):
        (tmp_path / f"ctl/status.{index}").write_text(_status({**states, **override}))
    for name, (enabled, _, *extra) in services.items():
        ini = f"[program:{name}]\nautostart={'true' if enabled else 'false'}\n{extra[0] if extra else 'autorestart=false' + chr(10)}"
        (tmp_path / f"etc/supervisor.d/{name}.ini").write_text(ini)
    (tmp_path / "calls.log").touch()
    if sentinel:
        (tmp_path / "etc/nginx/.bw-install-incomplete").touch()
    for name in fail:
        (tmp_path / "ctl" / name).touch()
    body = _slice()
    body = re.sub(r"(?<![\w.])/etc/nginx", str(tmp_path / "etc/nginx"), body)
    body = re.sub(r"(?<![\w.])/etc/supervisor\.d", str(tmp_path / "etc/supervisor.d"), body)
    body = re.sub(r"reload_install_timeout=\d+", f"reload_install_timeout={timeout}", body)
    # the services' settle deadline and poll interval
    body = re.sub(r"supervisor_python=\S+", f"supervisor_python={stub}", body)
    body = re.sub(r"reload_services_timeout=\d+", f"reload_services_timeout={settle}", body)
    body = re.sub(r"reload_services_poll=\d+", "reload_services_poll=0.2", body)
    script = DRIVER % {"slice": body, "scenario": scenario}
    result = subprocess.run(["bash", "-c", script, "driver", str(tmp_path)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    lines = (tmp_path / "calls.log").read_text().splitlines()
    # the pre-fix entrypoint reads the states with `supervisorctl status`: one name for the read keeps the old calls comparable
    calls = [line.replace("supervisorctl status", "supervisor getAllProcessInfo") for line in lines if line.startswith("supervisor")]
    return calls, [line for line in lines if line.startswith("log: ")]


def test_reload_without_install_updates_then_restarts(tmp_path):
    calls, logs = _run(tmp_path, "trap_reload")
    assert calls == ["supervisorctl update all (no-install)", "supervisorctl restart all (no-install)", "supervisor getAllProcessInfo (no-install)"]
    assert any("Reload successful" in line for line in logs)


def test_reload_waits_for_an_install_in_progress_before_touching_the_services(tmp_path):
    scenario = '( sleep 1; rm -f "$SANDBOX/etc/nginx/.bw-install-incomplete" ) &\ntrap_reload\nwait'
    calls, logs = _run(tmp_path, scenario, sentinel=True, timeout=10)
    # The services are only touched once the install is over
    assert calls == ["supervisorctl update all (no-install)", "supervisorctl restart all (no-install)", "supervisor getAllProcessInfo (no-install)"]
    assert any("waiting for it before reloading" in line for line in logs)
    assert any("Reload successful" in line for line in logs)


def test_reload_keeps_the_services_when_the_install_never_ends(tmp_path):
    calls, logs = _run(tmp_path, "trap_reload", sentinel=True, timeout=2)
    assert calls == []
    assert any("keeping the running services" in line for line in logs)
    assert not any("Reload successful" in line for line in logs)


def test_reload_keeps_the_services_when_the_supervisord_update_fails(tmp_path):
    calls, logs = _run(tmp_path, "trap_reload", fail=["fail-update"])
    assert calls == ["supervisorctl update all (no-install)"]
    assert any("Failed to update supervisord configuration" in line for line in logs)


def test_a_nonzero_restart_status_is_not_a_failed_reload(tmp_path):
    # supervisorctl exits nonzero whenever a listed program is not running, and every disabled service is one
    calls, logs = _run(tmp_path, "trap_reload", fail=["fail-restart"])
    assert calls == ["supervisorctl update all (no-install)", "supervisorctl restart all (no-install)", "supervisor getAllProcessInfo (no-install)"]
    assert any("Reload successful" in line for line in logs)


def _assert_reload_failed(logs, *names):
    assert not any("Reload successful" in line for line in logs)
    failure = [line for line in logs if "Reload failed" in line]
    assert failure and all(name in failure[0] for name in names), logs
    assert "log: status=1" in logs


def test_an_enabled_service_that_fails_to_restart_is_a_failed_reload(tmp_path):
    services = {**BENIGN, "scheduler": (True, "FATAL")}
    _, logs = _run(tmp_path, "trap_reload\nlog status=$?", fail=["fail-restart"], services=services)
    _assert_reload_failed(logs, "scheduler")
    assert not any("ui" in line for line in logs if "Reload failed" in line)


def test_an_enabled_service_that_keeps_backing_off_is_a_failed_reload_even_with_a_zero_restart_status(tmp_path):
    services = {**BENIGN, "api": (True, "BACKOFF")}
    _, logs = _run(tmp_path, "trap_reload\nlog status=$?", services=services, settle=STUCK)
    _assert_reload_failed(logs, "api")


def test_an_enabled_service_that_restarts_fine_is_a_successful_reload_whatever_the_disabled_ones_report(tmp_path):
    services = {**BENIGN, "scheduler": (True, "RUNNING")}
    _, logs = _run(tmp_path, "trap_reload\nlog status=$?", fail=["fail-restart"], services=services)
    assert any("Reload successful" in line for line in logs)
    assert "log: status=0" in logs


def _reload(tmp_path, services, **kwargs):
    return _run(tmp_path, "trap_reload\nlog status=$?", services=services, **kwargs)


def _stuck_reload(tmp_path, services):
    return _reload(tmp_path, services, settle=STUCK)


def test_an_enabled_scheduler_that_ended_in_exited_is_a_failed_reload(tmp_path):
    _, logs = _reload(tmp_path, {**BENIGN, "scheduler": (True, "EXITED")})
    _assert_reload_failed(logs, "scheduler")


def test_an_enabled_scheduler_that_ended_in_stopped_is_a_failed_reload(tmp_path):
    _, logs = _reload(tmp_path, {**BENIGN, "scheduler": (True, "STOPPED")})
    _assert_reload_failed(logs, "scheduler")


def test_an_enabled_service_still_starting_at_the_deadline_is_a_failed_reload(tmp_path):
    _, logs = _stuck_reload(tmp_path, {**BENIGN, "api": (True, "STARTING")})
    _assert_reload_failed(logs, "api")


def test_an_enabled_service_still_stopping_at_the_deadline_is_a_failed_reload(tmp_path):
    _, logs = _stuck_reload(tmp_path, {**BENIGN, "api": (True, "STOPPING")})
    _assert_reload_failed(logs, "api")


def test_an_enabled_service_missing_from_the_status_is_a_failed_reload(tmp_path):
    # the stub lists a service with an empty state column as absent
    _, logs = _reload(tmp_path, {**BENIGN, "scheduler": (True, "")})
    _assert_reload_failed(logs, "scheduler")


def test_a_reload_waits_for_a_starting_service_to_become_running(tmp_path):
    calls, logs = _reload(tmp_path, {**BENIGN, "api": (True, "RUNNING")}, earlier=[{"api": "STARTING"}, {"api": "STARTING"}])
    assert calls.count("supervisor getAllProcessInfo (no-install)") == 3
    assert any("Reload successful" in line for line in logs)
    assert "log: status=0" in logs


def test_a_heavy_worker_stopped_on_its_declared_exit_code_is_a_successful_reload(tmp_path):
    services = {**BENIGN, "scheduler": (True, "RUNNING"), "worker-heavy": (True, "EXITED:3", HEAVY_INI)}
    _, logs = _reload(tmp_path, services)
    assert any("Reload successful" in line for line in logs)
    assert "log: status=0" in logs


def test_a_heavy_worker_restarted_after_an_unexpected_exit_is_not_a_finished_reload(tmp_path):
    # exit codes other than 3 are restarted by supervisord (autorestart=unexpected): the service never rests in EXITED
    services = {**BENIGN, "scheduler": (True, "RUNNING"), "worker-heavy": (True, "STARTING", HEAVY_INI)}
    _, logs = _stuck_reload(tmp_path, services)
    _assert_reload_failed(logs, "worker-heavy")


def test_a_service_whose_ini_does_not_declare_its_exit_intentional_is_failed_in_exited(tmp_path):
    services = {**BENIGN, "worker-heavy": (True, "EXITED:3", "autorestart=false\nexitcodes=3\n")}
    _, logs = _reload(tmp_path, services)
    _assert_reload_failed(logs, "worker-heavy")


def test_a_heavy_worker_exited_on_an_undeclared_exit_status_that_stays_exited_is_a_failed_reload(tmp_path):
    # supervisord records an unexpected exit as EXITED before its restart: the exit status is what tells it from a declared one
    services = {**BENIGN, "worker-heavy": (True, "EXITED:1", HEAVY_INI)}
    _, logs = _stuck_reload(tmp_path, services)
    _assert_reload_failed(logs, "worker-heavy")


def test_a_heavy_worker_exited_on_an_undeclared_exit_status_then_restarted_is_a_successful_reload(tmp_path):
    services = {**BENIGN, "worker-heavy": (True, "RUNNING", HEAVY_INI)}
    calls, logs = _reload(tmp_path, services, earlier=[{"worker-heavy": "EXITED:1"}])
    assert calls.count("supervisor getAllProcessInfo (no-install)") == 2
    assert any("Reload successful" in line for line in logs)
    assert "log: status=0" in logs


def test_process_info_that_cannot_be_read_is_a_failed_reload(tmp_path):
    # no enabled service at all: an unreadable answer must not read as "nothing is wrong"
    _, logs = _reload(tmp_path, {"ui": (False, "FATAL")}, fail=["info-unreadable"])
    _assert_reload_failed(logs, "supervisord")


def test_a_stop_request_ends_the_wait_without_restarting_the_services(tmp_path):
    scenario = "( sleep 0.7; kill -TERM $$ ) &\ntrap_reload\nwait"
    calls, logs = _run(tmp_path, scenario, sentinel=True, timeout=30)
    assert calls == ["supervisorctl shutdown (install-in-progress)"]
    assert any("Reload cancelled by a stop request" in line for line in logs)


def test_every_startup_script_names_the_sentinel_the_writers_create():
    assert 'RESERVED_PREFIX = ".bw-"' in (ROOT / "src/common/gen/sync_tree.py").read_text()
    assert 'INSTALL_SENTINEL = f"{RESERVED_PREFIX}install-incomplete"' in (ROOT / "src/common/gen/sync_tree.py").read_text()
    assert 'pushswap.RESERVED_PREFIX = ".bw-"' in (ROOT / "src/bw/lua/bunkerweb/pushswap.lua").read_text()
    for relative in ("src/all-in-one/entrypoint.sh", "src/bw/entrypoint.sh", "src/linux/scripts/start.sh"):
        assert 'install_sentinel="/etc/nginx/.bw-install-incomplete"' in (ROOT / relative).read_text(), relative
