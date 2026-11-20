"""Run the whole DEB postrm in a temp root; rollback must not overwrite backups (UB5-4)."""

import shutil

import pytest
from _t7_helpers import bash, retarget, source

BACKUPS = ("variables.env", "ui.env", "scheduler.env", "api.env", "api.yml", "db.sqlite3")
CLEANED = ("usr/share/bunkerweb", "var/tmp/bunkerweb", "var/run/bunkerweb", "var/cache/bunkerweb", "usr/bin/bwcli")


def _run(tmp_path, argument, *, missing_config=False):
    for path in ("etc/bunkerweb", "var/lib/bunkerweb", "var/backups/bunkerweb", "var/log/bunkerweb", *CLEANED[:-1]):
        directory = tmp_path / path
        directory.mkdir(parents=True)
        (directory / "sentinel").write_bytes(path.encode())
    (tmp_path / "usr/bin").mkdir(parents=True)
    (tmp_path / "usr/bin/bwcli").write_bytes(b"cli")
    for name in BACKUPS:
        (tmp_path / "var/backups/bunkerweb" / name).write_text(f"old {name}")
        live = tmp_path / ("var/lib/bunkerweb" if name == "db.sqlite3" else "etc/bunkerweb") / name
        if not missing_config:
            live.write_text(f"live {name}")
    (tmp_path / "etc/os-release").write_text("ID=debian\n")
    services = tmp_path / "etc/systemd/system"
    services.mkdir(parents=True)
    (services / "bunkerweb.service").write_text("service")
    (services / "unrelated.service").write_text("keep")
    stubs = tmp_path / "bin"
    stubs.mkdir()
    for tool in ("tr", "find", "basename", "rm", "mkdir", "chmod", "touch", "install", "cp"):
        if tool == "install":
            body = f'exec {shutil.which(tool)} -m 0600 "$7" "$8"'
        else:
            body = f'exec {shutil.which(tool)} "$@"'
        stub = stubs / tool
        stub.write_text(f"#!/bin/sh\n{body}\n")
        stub.chmod(0o755)
    for tool, body in (("id", "echo 0"), ("systemctl", 'echo "$*" >> "$CALLS"'), ("chown", ":")):
        stub = stubs / tool
        stub.write_text(f"#!/bin/sh\n{body}\n")
        stub.chmod(0o755)
    script = retarget(source("src/linux/scripts/afterRemoveDEB.sh"), tmp_path, "/etc/", "/var/", "/usr/", "/lib/")
    args = (argument, "1.6.9", "1.6.10") if argument == "failed-upgrade" else (argument, "1.6.10")
    return bash(script, *args, env={"PATH": str(stubs), "CALLS": str(tmp_path / "systemctl-calls")})


@pytest.mark.parametrize("argument", ["remove", "purge", "upgrade", "abort-install", "failed-upgrade", "abort-upgrade", "disappear"])
def test_lifecycle_preserves_data_except_explicit_purge(tmp_path, argument):
    result = _run(tmp_path, argument)
    assert result.returncode == 0, result.stdout + result.stderr
    for path in ("etc/bunkerweb", "var/lib/bunkerweb"):
        if argument == "purge":
            assert not (tmp_path / path).exists()
        else:
            assert (tmp_path / path / "sentinel").read_bytes() == path.encode()
    assert (tmp_path / "var/log/bunkerweb/sentinel").read_bytes() == b"var/log/bunkerweb"
    assert (tmp_path / "var/backups/bunkerweb/sentinel").exists()
    for name in BACKUPS:
        assert (tmp_path / "var/backups/bunkerweb" / name).read_text() == f"old {name}"
    for path in CLEANED:
        assert (tmp_path / path).exists() == (argument not in ("remove", "purge"))
    assert not (tmp_path / "var/tmp/bunkerweb_upgrade").exists()
    assert (tmp_path / "etc/systemd/system/bunkerweb.service").read_text() == "service"
    assert (tmp_path / "etc/systemd/system/unrelated.service").read_text() == "keep"
    assert (tmp_path / "systemctl-calls").exists() == (argument in ("remove", "purge"))


@pytest.mark.parametrize("argument", ["", "bogus"])
def test_unknown_argument_fails_without_modifying_backups(tmp_path, argument):
    result = _run(tmp_path, argument)
    assert result.returncode != 0
    assert (tmp_path / "var/backups/bunkerweb/db.sqlite3").read_text() == "old db.sqlite3"
    assert (tmp_path / "etc/bunkerweb/sentinel").exists()


@pytest.mark.parametrize("argument", ["abort-install", "abort-upgrade", "disappear"])
def test_rollback_with_missing_live_config_keeps_existing_backups(tmp_path, argument):
    result = _run(tmp_path, argument, missing_config=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert all((tmp_path / "var/backups/bunkerweb" / name).read_text() == f"old {name}" for name in BACKUPS)


@pytest.mark.parametrize("argument", ["upgrade", "failed-upgrade"])
def test_upgrade_callbacks_leave_snapshotting_to_new_preinstall(tmp_path, argument):
    result = _run(tmp_path, argument)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "var/lib/bunkerweb/db.sqlite3").read_text() == "live db.sqlite3"
    assert (tmp_path / "var/backups/bunkerweb/db.sqlite3").read_text() == "old db.sqlite3"
    assert not (tmp_path / "systemctl-calls").exists()
