"""LXP: execute packaged maintainer scripts against a disposable root, including old callbacks."""

import os
import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path

import pytest
from _t7_helpers import ROOT, retarget

SCRIPTS = Path(os.environ.get("LXP_SCRIPT_ROOT", ROOT / "src/linux/scripts"))
DEFINITIONS = Path(os.environ.get("LXP_DEFINITION_ROOT", ROOT / "src/linux"))
UNITS = ("bunkerweb", "bunkerweb-scheduler", "bunkerweb-ui", "bunkerweb-api")


class Host:
    def __init__(self, root, distro="debian"):
        self.root = root
        self.bin = root / "bin"
        self.bin.mkdir()
        self.calls = root / "calls"
        self.env = {"PATH": f"{self.bin}:{os.defpath}", "ROOT": str(root), "CALLS": str(self.calls)}
        for path in (
            "etc/bunkerweb",
            "var/lib/bunkerweb",
            "var/backups/bunkerweb",
            "var/cache/bunkerweb",
            "var/tmp/bunkerweb",
            "var/run/bunkerweb",
            "var/log/bunkerweb",
            "etc/systemd/system",
            "usr/bin",
        ):
            (root / path).mkdir(parents=True, exist_ok=True)
        for path in ("api", "scheduler", "ui", "cli", "lua", "core", "db/alembic", "gen", "utils", "helpers", "scripts", "deps/python/bin"):
            (root / "usr/share/bunkerweb" / path).mkdir(parents=True, exist_ok=True)
        (root / "usr/share/bunkerweb/VERSION").write_text("1.6.18~rc3\n")
        (root / "usr/share/bunkerweb/db/alembic/env.py").write_text("# trusted package code\n")
        (root / "etc/os-release").write_text(f"ID={distro}\n")
        self.stub("id", "echo 0")
        self.stub("chown", 'echo "chown $*" >> "$CALLS"')
        self.stub("install", f'exec {shutil.which("install")} -m 0600 "${{@: -2:1}}" "${{@: -1}}"')
        self.stub(
            "systemctl",
            """echo "systemctl $*" >> "$CALLS"
unit="${@: -1}"
case "$1" in
    is-active) test -f "$ROOT/active-$unit" ;;
    is-enabled) test -f "$ROOT/enabled-$unit" ;;
    stop) [ "${FAIL_STOP:-}" != "$unit" ] || exit 1; rm -f "$ROOT/active-$unit" ;;
    disable) rm -f "$ROOT/enabled-$unit"; if [ "$2" = --now ]; then rm -f "$ROOT/active-$unit"; fi ;;
    restart|start) [ "${FAIL_RESTART:-}" != "$unit" ] || exit 1; touch "$ROOT/active-$unit" ;;
    enable) touch "$ROOT/enabled-$unit"; if [ "$2" = --now ]; then touch "$ROOT/active-$unit"; fi ;;
esac
exit $?""",
        )

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/bash\n{body}\n")
        path.chmod(0o755)

    def run(self, name, *args, original=None, **env):
        if original:
            text = subprocess.run(["git", "-C", str(ROOT), "show", f"{original}:src/linux/scripts/{name}"], capture_output=True, text=True, check=True).stdout
        else:
            text = (SCRIPTS / name).read_text()
        script = retarget(text, self.root, "/etc/", "/var/", "/usr/", "/lib/")
        result = subprocess.run(["bash", "-c", script, "_", *args], env=self.env | env, capture_output=True, text=True, timeout=30)
        return result

    def ok(self, name, *args, **kwargs):
        result = self.run(name, *args, **kwargs)
        assert result.returncode == 0, result.stdout + result.stderr
        return result

    def active(self, unit, enabled=True):
        (self.root / f"active-{unit}").touch()
        if enabled:
            (self.root / f"enabled-{unit}").touch()

    def wal(self):
        db = sqlite3.connect(self.root / "var/lib/bunkerweb/db.sqlite3")
        db.execute("CREATE TABLE settings (value TEXT)")
        db.commit()
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute("INSERT INTO settings VALUES ('committed in WAL')")
        db.commit()
        return db

    def calls_text(self):
        return self.calls.read_text() if self.calls.exists() else ""


def rows(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        return db.execute("SELECT value FROM settings").fetchall()


@pytest.fixture
def host(tmp_path):
    instance = Host(tmp_path)
    yield instance
    # Real permission repairs deliberately remove directory write bits.
    for directory, _, _ in os.walk(tmp_path):
        Path(directory).chmod(0o700)


@pytest.mark.parametrize("rpm", [False, True])
def test_preinstall_snapshots_committed_wal_and_stops_database_users(host, rpm):
    for unit in UNITS:
        host.active(unit)
    db = host.wal()
    try:
        raw = host.root / "raw.sqlite3"
        shutil.copyfile(host.root / "var/lib/bunkerweb/db.sqlite3", raw)
        assert rows(raw) == [], "fixture must keep committed row only in WAL"
        host.ok("beforeInstall.sh", *(("2",) if rpm else ("upgrade", "1.6.18~rc3")))
        snapshot = host.root / "var/backups/bunkerweb/transaction/db.sqlite3"
        assert rows(snapshot) == [("committed in WAL",)]
        assert snapshot.stat().st_mode & 0o777 == 0o600
        assert snapshot.parent.stat().st_mode & 0o777 == 0o700
        for unit in UNITS:
            assert f"systemctl stop {unit}\n" in host.calls_text()
            assert not (host.root / f"active-{unit}").exists()
            assert (host.root / f"enabled-{unit}").exists()
    finally:
        db.close()


@pytest.mark.parametrize("rpm", [False, True])
@pytest.mark.parametrize("old_revision", ["v1.6.18-rc3", "3a9c1381f84f248cbb6c5210d22bafebdf0ab941"])
def test_first_fixed_upgrade_uses_current_transaction_after_old_postrm(host, rpm, old_revision):
    (host.root / "etc/os-release").write_text("ID=rhel\n" if rpm else "ID=debian\n")
    (host.root / "etc/bunkerweb/variables.env").write_text("CURRENT=yes\n")
    (host.root / "var/backups/bunkerweb/variables.env").write_text("STALE=yes\n")
    (host.root / "var/tmp/variables.env").write_text("OLDER=yes\n")
    (host.root / "var/tmp/bunkerweb_upgrade").touch()
    host.active("bunkerweb-api")
    db = host.wal()
    try:
        # Released DEB had no prerm. New preinst/%pre is the first mutation.
        host.ok("beforeInstall.sh", *(("2",) if rpm else ("upgrade", "1.6.18~rc3")))
        db.close()
        if rpm:
            # New %post intentionally does no service work; old %postun still writes flat backups.
            host.ok("afterRemoveRPM.sh", "1", original=old_revision)
        else:
            host.ok("afterRemoveDEB.sh", "upgrade", "1.6.18~rc4", original=old_revision)
        (host.root / "etc/bunkerweb/variables.env").write_text("PAYLOAD=yes\n")
        host.ok("postinstall.sh", *(("1",) if rpm else ("configure", "1.6.18~rc3")))
        assert (host.root / "etc/bunkerweb/variables.env").read_text() == "CURRENT=yes\n"
        assert rows(host.root / "var/lib/bunkerweb/db.sqlite3") == [("committed in WAL",)]
        assert (host.root / "active-bunkerweb-api").exists()
        assert (host.root / "enabled-bunkerweb-api").exists()
        assert "systemctl disable --now bunkerweb-api\n" not in host.calls_text()
        assert not (host.root / "var/tmp/bunkerweb_upgrade").exists()
        assert not (host.root / "var/backups/bunkerweb/transaction").exists()
        backups = host.root / "var/backups/bunkerweb"
        assert any(p.read_text() == "OLDER=yes\n" for p in backups.rglob("legacy-variables.env"))
        assert any(p.read_text() == "STALE=yes\n" for p in backups.rglob("variables.env"))
        # Second upgrade must snapshot subsequent operator changes, never the preceding transaction.
        (host.root / "etc/bunkerweb/variables.env").write_text("NEWER=yes\n")
        if not rpm:
            host.ok("beforeRemove.sh", "upgrade", "1.6.18~rc4")
        host.ok("beforeInstall.sh", *(("2",) if rpm else ("upgrade", "1.6.18~rc4")))
        if rpm:
            host.ok("beforeRemove.sh", "1")
        host.ok("afterRemoveRPM.sh" if rpm else "afterRemoveDEB.sh", "1" if rpm else "upgrade")
        host.ok("postinstall.sh", *(("1",) if rpm else ("configure", "1.6.18~rc4")))
        assert (host.root / "etc/bunkerweb/variables.env").read_text() == "NEWER=yes\n"
    finally:
        db.close()


def test_postinstall_never_restores_retained_backup_without_transaction(host):
    (host.root / "etc/bunkerweb/variables.env").write_text("CURRENT=yes\n")
    (host.root / "var/backups/bunkerweb/variables.env").write_text("STALE=yes\n")
    (host.root / "var/tmp/bunkerweb_upgrade").touch()
    host.active("bunkerweb-api")
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    assert (host.root / "etc/bunkerweb/variables.env").read_text() == "CURRENT=yes\n"
    assert (host.root / "active-bunkerweb-api").exists()


def test_postinstall_repairs_packaged_code_modes(host):
    code = host.root / "usr/share/bunkerweb/db/alembic/env.py"
    code.chmod(0o770)
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    assert code.stat().st_mode & 0o022 == 0
    assert f"chown -R root:nginx {host.root}/usr/share/bunkerweb\n" in host.calls_text()


def test_postinstall_repairs_log_modes_without_replacing_inodes(host):
    logs = []
    for name, mode in (("access.log", 0o644), ("modsec_audit.log.1.gz", 0o666), ("private.log", 0o600), ("hidden.log", 0o400)):
        log = host.root / "var/log/bunkerweb" / name
        log.write_text("sensitive\n")
        log.chmod(mode)
        logs.append((log, log.stat().st_ino, mode & 0o640))
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    for log, inode, expected in logs:
        assert log.stat().st_ino == inode
        assert log.stat().st_mode & 0o777 == expected
        assert log.read_text() == "sensitive\n"


@pytest.mark.parametrize("rpm", [False, True])
def test_remove_stops_before_payload_and_preserves_admin_units(host, rpm):
    (host.root / "etc/os-release").write_text("ID=rhel\n" if rpm else "ID=debian\n")
    for name in ("bunkerweb.service", "bunkerweb-monitor.service"):
        (host.root / "etc/systemd/system" / name).write_text("admin unit\n")
    for unit in UNITS:
        host.active(unit)
    host.ok("beforeRemove.sh", "0" if rpm else "remove")
    for unit in UNITS:
        assert not (host.root / f"active-{unit}").exists()
        assert not (host.root / f"enabled-{unit}").exists()
    assert (host.root / "usr/share/bunkerweb/scripts").exists(), "stop must precede payload removal"
    shutil.rmtree(host.root / "usr/share/bunkerweb")
    host.ok("afterRemoveRPM.sh" if rpm else "afterRemoveDEB.sh", "0" if rpm else "remove")
    for name in ("bunkerweb.service", "bunkerweb-monitor.service"):
        assert (host.root / "etc/systemd/system" / name).read_text() == "admin unit\n"
    assert "systemctl daemon-reload\n" in host.calls_text()


@pytest.mark.parametrize("argument", ["upgrade", "1", "failed-upgrade", "deconfigure"])
def test_preremove_upgrade_does_not_stop_or_disable(host, argument):
    host.active("bunkerweb-api")
    host.ok("beforeRemove.sh", argument)
    assert host.calls_text() == ""
    assert (host.root / "active-bunkerweb-api").exists()


def test_removal_stop_failure_aborts_before_payload_removal(host):
    host.active("bunkerweb-api")
    result = host.run("beforeRemove.sh", "remove", FAIL_STOP="bunkerweb-api")
    assert result.returncode != 0
    assert (host.root / "usr/share/bunkerweb/scripts").exists()


@pytest.mark.parametrize("rpm", [False, True])
def test_postremove_preserves_admin_units_and_archived_snapshots(host, rpm):
    (host.root / "etc/os-release").write_text("ID=rhel\n" if rpm else "ID=debian\n")
    unit = host.root / "etc/systemd/system/bunkerweb-monitor.service"
    unit.write_text("admin unit\n")
    archive = host.root / "var/backups/bunkerweb/completed.previous"
    archive.mkdir(mode=0o700)
    (archive / "db.sqlite3").write_bytes(b"recovery snapshot")
    host.ok("afterRemoveRPM.sh" if rpm else "afterRemoveDEB.sh", "0" if rpm else "remove")
    assert unit.read_text() == "admin unit\n"
    assert archive.stat().st_mode & 0o777 == 0o700
    assert (archive / "db.sqlite3").read_bytes() == b"recovery snapshot"


def test_failed_extraction_keeps_archive_and_previous_dependencies(host):
    share = host.root / "usr/share/bunkerweb"
    (share / "deps/usable").write_text("working\n")
    (share / "deps.tar.gz").write_bytes(b"broken archive")
    result = host.run("postinstall.sh", "configure", "1.6.18~rc3")
    assert result.returncode != 0
    assert (share / "deps/usable").read_text() == "working\n"
    assert (share / "deps.tar.gz").exists()
    assert "Decompression completed successfully" not in result.stdout


def test_successful_extraction_publishes_dependencies(host):
    share = host.root / "usr/share/bunkerweb"
    fixture = host.root / "archive/deps"
    fixture.mkdir(parents=True)
    (fixture / "new").write_text("new deps\n")
    with tarfile.open(share / "deps.tar.gz", "w:gz") as archive:
        archive.add(fixture, arcname="deps")
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    assert (share / "deps/new").read_text() == "new deps\n"
    assert not (share / "deps.tar.gz").exists()


def test_failed_restore_preserves_transaction_and_never_uses_stale_fallback(host):
    config = host.root / "etc/bunkerweb/variables.env"
    config.write_text("CURRENT=yes\n")
    host.ok("beforeInstall.sh", "upgrade", "1.6.18~rc3")
    (host.root / "var/tmp/variables.env").write_text("STALE=yes\n")
    host.stub("cp", "exit 13")
    result = host.run("postinstall.sh", "configure", "1.6.18~rc3")
    assert result.returncode != 0
    assert config.read_text() == "CURRENT=yes\n"
    assert (host.root / "var/backups/bunkerweb/transaction/variables.env").read_text() == "CURRENT=yes\n"
    assert (host.root / "var/tmp/variables.env").read_text() == "STALE=yes\n"
    assert "successfully upgraded" not in result.stdout


def test_failed_snapshot_keeps_previous_snapshot_and_fails_preinstall(host):
    transaction = host.root / "var/backups/bunkerweb/transaction"
    transaction.mkdir()
    (transaction / "db.sqlite3").write_bytes(b"previous recovery snapshot")
    (host.root / "var/lib/bunkerweb/db.sqlite3").write_bytes(b"corrupt database")
    result = host.run("beforeInstall.sh", "upgrade", "1.6.18~rc3")
    assert result.returncode != 0
    assert (transaction / "db.sqlite3").read_bytes() == b"previous recovery snapshot"


def test_all_package_definitions_wire_removal_and_rpm_posttrans():
    paths = sorted(DEFINITIONS.glob("fpm-*"))
    assert len(paths) == 10
    for path in paths:
        text = path.read_text()
        assert "--before-remove /usr/share/bunkerweb/scripts/beforeRemove.sh" in text, path
        if "rhel" in path.name or "fedora" in path.name:
            assert "--rpm-posttrans /usr/share/bunkerweb/scripts/postinstall.sh" in text, path
            assert "--after-install " not in text, path
            assert "--depends logrotate" in text, path


@pytest.mark.parametrize("distro", ["rhel-8", "rhel-9", "rhel-10", "fedora-43", "fedora-44"])
def test_rpm_packages_require_logrotate(distro):
    assert "--depends logrotate" in (DEFINITIONS / f"fpm-{distro}").read_text()


@pytest.mark.parametrize("state", ["running", "enabled-stopped", "disabled"])
def test_bare_upgrade_preserves_api_enablement_and_activity(host, state):
    if state == "running":
        host.active("bunkerweb-api")
    elif state == "enabled-stopped":
        (host.root / "enabled-bunkerweb-api").touch()
    host.ok("beforeInstall.sh", "upgrade", "1.6.18~rc3")
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    assert (host.root / "enabled-bunkerweb-api").exists() == (state != "disabled")
    assert (host.root / "active-bunkerweb-api").exists() == (state == "running")


def test_explicit_api_disable_survives_upgrade(host):
    host.active("bunkerweb-api")
    host.ok("beforeInstall.sh", "upgrade", "1.6.18~rc3")
    host.ok("postinstall.sh", "configure", "1.6.18~rc3", SERVICE_API="no")
    assert not (host.root / "active-bunkerweb-api").exists()
    assert not (host.root / "enabled-bunkerweb-api").exists()


@pytest.mark.parametrize("rpm", [False, True])
@pytest.mark.parametrize("active", [False, True], ids=["inactive", "active"])
@pytest.mark.parametrize(
    "unit,setting",
    [("bunkerweb", "SERVICE_BUNKERWEB"), ("bunkerweb-scheduler", "SERVICE_SCHEDULER"), ("bunkerweb-ui", "SERVICE_UI")],
)
def test_explicit_service_disable_uses_preupgrade_activity(host, rpm, active, unit, setting):
    (host.root / "etc/os-release").write_text("ID=rhel\n" if rpm else "ID=debian\n")
    if active:
        host.active(unit)
    else:
        (host.root / f"enabled-{unit}").touch()
    host.ok("beforeInstall.sh", *(("2",) if rpm else ("upgrade", "1.6.18~rc3")))
    assert not (host.root / f"active-{unit}").exists()
    host.ok("postinstall.sh", *(("1",) if rpm else ("configure", "1.6.18~rc3")), **{setting: "no"})
    assert not (host.root / f"active-{unit}").exists()
    assert (host.root / f"enabled-{unit}").exists() == (not active)
    assert (f"systemctl disable --now {unit}\n" in host.calls_text()) == active
    assert not (host.root / "usr/share/bunkerweb/INSTALL_TYPE").exists()


def test_postinstall_retry_after_service_failure_never_replays_snapshot(host):
    for unit in UNITS:
        host.active(unit)
    db = host.wal()
    db.close()
    host.ok("beforeInstall.sh", "upgrade", "1.6.18~rc3")
    result = host.run("postinstall.sh", "configure", "1.6.18~rc3", FAIL_RESTART="bunkerweb-ui")
    assert result.returncode != 0
    live = host.root / "var/lib/bunkerweb/db.sqlite3"
    with sqlite3.connect(live) as connection:
        connection.execute("INSERT INTO settings VALUES ('new service write')")
    host.ok("postinstall.sh", "configure", "1.6.18~rc3")
    assert rows(live) == [("committed in WAL",), ("new service write",)]
