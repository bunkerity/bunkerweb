r"""The pre-upgrade database backup is skipped on hosts that run no scheduler.

Upgrading a separate worker (or UI/API-only) host with the easy-install script tried to back up a database it
does not own, and failed or demanded a confirmation. `perform_upgrade_backup` now skips the backup for the
worker, ui and api install types, and for any host whose `bunkerweb-scheduler` unit is missing, disabled and
inactive; a full or manager host with a scheduler still backs up. The functions are lifted from
`misc/install-bunkerweb.sh` and run with a stubbed `systemctl` and `bwcli`.

Refs #3052.
"""

import pytest
from _t7_helpers import bash, function, source

TEXT = source("misc/install-bunkerweb.sh")
FUNCTIONS = "\n".join(function(TEXT, name) for name in ("_skip_backup_for_type", "should_skip_upgrade_backup", "perform_upgrade_backup"))

HARNESS = """
print_step() {{ echo "STEP $*"; }}
print_status() {{ echo "STATUS $*"; }}
print_warning() {{ echo "WARN $*"; }}
print_error() {{ echo "ERROR $*"; }}
_upgrade_backup_database_uri() {{ :; }}
systemctl() {{
    case "$1" in
        list-unit-files) if [ "{listed}" = yes ]; then echo "bunkerweb-scheduler.service enabled enabled"; fi ;;
        is-enabled) [ "{enabled}" = yes ] ;;
        is-active) [ "{active}" = yes ] ;;
        *) echo "systemctl $*" >> "{root}/systemctl-calls" ;;
    esac
}}
UPGRADE_SCENARIO=yes
AUTO_BACKUP=yes
INTERACTIVE_MODE=no
INSTALL_TYPE="{install_type}"
BACKUP_DIRECTORY="{root}/backup"
{functions}
perform_upgrade_backup
echo "rc=$?"
"""


def _run(tmp_path, install_type, *, listed=True, enabled=True, active=True):
    stubs = tmp_path / "bin"
    stubs.mkdir()
    bwcli = stubs / "bwcli"
    bwcli.write_text(f'#!/bin/bash\necho "bwcli $*" >> "{tmp_path}/bwcli-calls"\n', encoding="utf-8")
    bwcli.chmod(0o755)
    script = HARNESS.format(
        root=tmp_path,
        install_type=install_type,
        listed="yes" if listed else "no",
        enabled="yes" if enabled else "no",
        active="yes" if active else "no",
        functions=FUNCTIONS,
    )
    result = bash(script, env={"PATH": f"{stubs}:/usr/bin:/bin"})
    return result, (tmp_path / "bwcli-calls").exists()


def test_a_full_install_with_a_scheduler_is_backed_up(tmp_path):
    """Anti-vacuity: the skip rules must not swallow the case the backup exists for."""
    result, backed_up = _run(tmp_path, "full")

    assert "rc=0" in result.stdout, result.stdout + result.stderr
    assert backed_up, "the backup was skipped on a host that owns the database"
    assert "STATUS Backup completed" in result.stdout


@pytest.mark.parametrize("install_type", ["worker", "ui", "api"])
def test_a_type_that_owns_no_database_is_never_backed_up(tmp_path, install_type):
    """Even when a scheduler unit happens to be enabled on the host."""
    result, backed_up = _run(tmp_path, install_type)

    assert "rc=0" in result.stdout, result.stdout + result.stderr
    assert not backed_up, f"a {install_type} host ran a database backup"
    assert not (tmp_path / "systemctl-calls").exists(), "the scheduler was started for a backup nobody needs"


@pytest.mark.parametrize(
    "unit",
    [{"listed": False, "enabled": False, "active": False}, {"listed": True, "enabled": False, "active": False}],
    ids=["no-scheduler-unit", "scheduler-disabled-and-stopped"],
)
def test_a_host_without_a_running_or_enabled_scheduler_is_not_backed_up(tmp_path, unit):
    result, backed_up = _run(tmp_path, "full", **unit)

    assert "rc=0" in result.stdout, result.stdout + result.stderr
    assert not backed_up
    assert not (tmp_path / "systemctl-calls").exists(), "the scheduler was started temporarily on a host that does not run one"
