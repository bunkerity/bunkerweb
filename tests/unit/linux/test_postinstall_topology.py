"""A bare package upgrade must not turn a BunkerWeb-instance-only node into a manager.

dpkg/rpm re-run postinstall.sh with none of the installer's WORKER_MODE/MANAGER_MODE/
SERVICE_* in the environment, so before this was fixed every `apt upgrade` of an
instance-only host fell into the standalone branch and `systemctl enable --now`'d both a
Redis/Valkey broker and bunkerweb-worker (the Celery job executor) on a host that must run
neither -- including a distro Redis the operator had deliberately disabled.

Two vocabularies meet here, keep them apart: WORKER_MODE / install type "worker" is a
data-plane BunkerWeb instance node; bunkerweb-worker.service is the Celery job executor,
a peer of the scheduler.

The tests source postinstall.sh in library mode (BW_POSTINSTALL_LIB_ONLY) and drive the
real resolve_topology / manage_scheduler_and_worker against a fake systemctl that records
every invocation, so what is asserted is the shipped decision, not a copy of it.
"""

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
POSTINSTALL = ROOT / "src" / "linux" / "scripts" / "postinstall.sh"

FAKE_SYSTEMCTL = """#!/bin/bash
printf '%s\\n' "$*" >> "$FAKE_SYSTEMCTL_LOG"
verb="$1"
shift
unit=""
for arg in "$@"; do
    case "$arg" in
        --*) ;;
        *) unit="$arg" ;;
    esac
done
case "$verb" in
    is-enabled)
        for u in $FAKE_ENABLED; do [ "$u" = "$unit" ] && exit 0; done
        echo "disabled"
        exit 1
        ;;
    is-active)
        for u in $FAKE_ACTIVE; do [ "$u" = "$unit" ] && exit 0; done
        echo "inactive"
        exit 3
        ;;
    list-unit-files)
        for u in $FAKE_UNIT_FILES; do
            [ "${u}.service" = "$unit" ] && { echo "${u}.service enabled"; exit 0; }
        done
        exit 0
        ;;
esac
exit 0
"""

DRIVER = """
source "$BW_POSTINSTALL"
resolve_topology
printf 'MANAGER_MODE=[%s] WORKER_MODE=[%s] SERVICE_BUNKERWEB=[%s] SERVICE_SCHEDULER=[%s] SERVICE_UI=[%s] SERVICE_API=[%s]\\n' \\
    "$MANAGER_MODE" "$WORKER_MODE" "$SERVICE_BUNKERWEB" "$SERVICE_SCHEDULER" "$SERVICE_UI" "$SERVICE_API"
manage_scheduler_and_worker
"""


def _run(tmp_path, *, marker=None, upgrade=True, enabled=(), active=(), unit_files=("bunkerweb-broker",), env=None):
    """Drive the real topology decision, return every recorded systemctl invocation."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "systemctl"
    fake.write_text(FAKE_SYSTEMCTL, encoding="utf-8")
    fake.chmod(0o755)

    log = tmp_path / "systemctl.log"
    log.write_text("", encoding="utf-8")

    marker_path = tmp_path / "INSTALL_TYPE"
    if marker is not None:
        marker_path.write_text(f"{marker}\n", encoding="utf-8")

    upgrade_flag = tmp_path / "bunkerweb_upgrade"
    if upgrade:
        upgrade_flag.write_text("", encoding="utf-8")

    child = os.environ | {
        "BW_POSTINSTALL": str(POSTINSTALL),
        "BW_POSTINSTALL_LIB_ONLY": "1",
        "BW_UPGRADE_FLAG": str(upgrade_flag),
        "BW_ENABLE_SCHEDULER_FLAG": str(tmp_path / "bunkerweb_enable_scheduler"),
        "INSTALL_TYPE_MARKER": str(marker_path),
        "FAKE_SYSTEMCTL_LOG": str(log),
        "FAKE_ENABLED": " ".join(enabled),
        "FAKE_ACTIVE": " ".join(active),
        "FAKE_UNIT_FILES": " ".join(unit_files),
        "PATH": f"{bindir}:{os.environ['PATH']}",
    }
    # The installer's mode/service view: absent on a bare `apt upgrade`, which is the point.
    for var in ("MANAGER_MODE", "WORKER_MODE", "SERVICE_BUNKERWEB", "SERVICE_SCHEDULER", "SERVICE_UI", "SERVICE_API"):
        child.pop(var, None)
    child.update(env or {})

    result = subprocess.run(["bash", "-c", DRIVER], capture_output=True, text=True, env=child)
    assert result.returncode == 0, result.stdout + result.stderr
    return log.read_text(encoding="utf-8").splitlines(), result.stdout


def _enabled_now(calls):
    return [c.split()[-1] for c in calls if c.startswith("enable --now")]


def _restarted(calls):
    return [c.split()[-1] for c in calls if c.startswith("restart ")]


# --- the defect: a bare upgrade must not enable a broker or the Celery worker ------------


@pytest.mark.parametrize("marker", ["worker", "ui", "api"])
def test_bare_upgrade_of_a_non_manager_marker_enables_nothing(tmp_path, marker):
    # The marker is stamped by every declared run; dpkg/rpm carry no env, so it is the only
    # thing that says what this host is.
    calls, _ = _run(tmp_path, marker=marker, active=("bunkerweb",) if marker == "worker" else ())
    assert _enabled_now(calls) == []


def test_bare_upgrade_without_a_marker_and_without_a_scheduler_enables_nothing(tmp_path):
    # Legacy 1.6 host: it predates the marker, so the only evidence is that it never ran a
    # scheduler. Enabling a broker + worker here is the 1.6 -> 1.7 upgrade regression.
    calls, _ = _run(tmp_path, marker=None, active=("bunkerweb",))
    assert _enabled_now(calls) == []


def test_no_distro_redis_is_touched_on_a_bare_instance_only_upgrade(tmp_path):
    # detect_broker_unit falls through to the distro unit, so without the gate an upgrade
    # starts a Redis the operator may have disabled on purpose.
    calls, _ = _run(tmp_path, marker="worker", unit_files=("redis-server",))
    assert "redis-server" not in " ".join(calls)


# --- unchanged where a scheduler really runs ---------------------------------------------


def test_a_negative_marker_still_restarts_a_scheduler_that_is_actually_running(tmp_path):
    # The deciding cell: the marker says this host runs no control plane, but a scheduler and
    # a Celery worker are up on it anyway (hand-added, or left over from a pre-fix upgrade).
    # The marker keeps its negative authority over *enabling* -- no broker, nothing new -- but
    # dpkg just replaced the code under those two units and the scheduler runs its database
    # migration at startup, so refusing to restart them would silently leave the old code
    # running until a reboot.
    calls, _ = _run(
        tmp_path,
        marker="ui",
        enabled=("bunkerweb-scheduler", "bunkerweb-worker"),
        active=("bunkerweb-scheduler", "bunkerweb-worker"),
    )
    assert _enabled_now(calls) == []
    assert _restarted(calls) == ["bunkerweb-scheduler", "bunkerweb-worker"]


def test_bare_upgrade_of_a_manager_host_still_enables_broker_and_worker(tmp_path):
    calls, _ = _run(tmp_path, marker=None, enabled=("bunkerweb-scheduler",), active=("bunkerweb-scheduler",))
    assert _enabled_now(calls) == ["bunkerweb-broker", "bunkerweb-worker"]
    assert "bunkerweb-scheduler" in _restarted(calls)


def test_an_enabled_but_stopped_worker_is_left_alone(tmp_path):
    # Ungated leg, worker enabled but deliberately stopped: neither re-enabled nor started.
    # `enable --now` here would restart a unit the operator took down on purpose.
    calls, _ = _run(
        tmp_path,
        marker=None,
        enabled=("bunkerweb-scheduler", "bunkerweb-worker"),
        active=("bunkerweb-scheduler",),
    )
    assert _enabled_now(calls) == ["bunkerweb-broker"]
    assert _restarted(calls) == ["bunkerweb-scheduler"]


def test_a_manager_marker_wins_over_a_stopped_scheduler(tmp_path):
    # The marker states the topology outright: a manager whose scheduler happens to be down
    # must still get its broker and worker back, or the fix would break recovery.
    calls, _ = _run(tmp_path, marker="manager")
    assert _enabled_now(calls) == ["bunkerweb-broker", "bunkerweb-worker"]


def test_fresh_install_is_unchanged(tmp_path):
    calls, _ = _run(tmp_path, marker=None, upgrade=False)
    assert _enabled_now(calls) == ["bunkerweb-broker", "bunkerweb-scheduler", "bunkerweb-worker"]


def test_explicit_worker_mode_is_unchanged(tmp_path):
    calls, _ = _run(tmp_path, marker=None, env={"MANAGER_MODE": "no", "WORKER_MODE": "yes"})
    assert _enabled_now(calls) == []


def test_explicit_manager_mode_is_unchanged(tmp_path):
    # Declared topology, scheduler not up yet: today's behaviour is to enable both, and the
    # gate must not fire on a declared run.
    calls, _ = _run(tmp_path, marker=None, env={"MANAGER_MODE": "yes", "WORKER_MODE": "no"})
    assert _enabled_now(calls) == ["bunkerweb-broker", "bunkerweb-worker"]


# --- the wiring, so the functions above stay the ones the script actually runs ------------


def test_recovery_never_rewrites_the_mode_view(tmp_path):
    # The marker is stale by construction: only a declared run rewrites it. Folding it into
    # MANAGER_MODE/WORKER_MODE/SERVICE_* would arm the `disable --now` legs of the bunkerweb,
    # UI and API sections against it, so an upgrade could stop a data plane the operator
    # added by hand after the last installer run. Those six stay untouched on a bare upgrade.
    _, view = _run(tmp_path, marker="ui")
    assert "MANAGER_MODE=[] WORKER_MODE=[] SERVICE_BUNKERWEB=[] SERVICE_SCHEDULER=[] SERVICE_UI=[] SERVICE_API=[]" in view


def test_the_script_calls_the_functions_under_test(tmp_path):
    lines = POSTINSTALL.read_text(encoding="utf-8").splitlines()
    guard = lines.index('[ -n "${BW_POSTINSTALL_LIB_ONLY:-}" ] && return 0')
    body = lines[guard:]
    assert body.index("resolve_topology") < body.index("manage_scheduler_and_worker")
    text = POSTINSTALL.read_text(encoding="utf-8")
    assert "read_recorded_install_type" in text.split("function resolve_topology() {")[1].split("\n}\n")[0]
