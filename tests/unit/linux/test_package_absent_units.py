"""S16-F1: absent units do not abort package callbacks or suppress reinstall startup."""

import os
import sqlite3

import pytest
from test_lxp_package_lifecycle import Host, UNITS, rows


@pytest.fixture
def host(tmp_path):
    instance = Host(tmp_path)
    # Model missing units explicitly; the original lifecycle stub assumes all units exist.
    instance.stub(
        "systemctl",
        r"""echo "systemctl $*" >> "$CALLS"
unit="${@: -1}"
unit="${unit%.service}"
case "$1" in
    show)
        if [ -f "$ROOT/present-$unit" ]; then echo loaded; else echo not-found; fi ;;
    is-active) test -f "$ROOT/active-$unit" ;;
    is-enabled) test -f "$ROOT/enabled-$unit" ;;
    stop)
        [ -f "$ROOT/present-$unit" ] || exit 5
        [ "${FAIL_STOP:-}" != "$unit" ] || exit "${FAIL_CODE:-1}"
        rm -f "$ROOT/active-$unit" ;;
    disable)
        [ "$unit" = nginx ] || [ -f "$ROOT/present-$unit" ] || exit 5
        rm -f "$ROOT/enabled-$unit"
        if [ "$2" = --now ]; then rm -f "$ROOT/active-$unit"; fi ;;
    enable|start|restart)
        [ -f "$ROOT/present-$unit" ] || exit 5
        [ "${FAIL_START:-}" != "$unit" ] || exit 1
        touch "$ROOT/active-$unit"
        if [ "$1" = enable ]; then touch "$ROOT/enabled-$unit"; fi ;;
    daemon-reload|reset-failed) ;;
    *) exit 9 ;;
esac
exit $?""",
    )
    for unit in UNITS:
        (tmp_path / f"present-{unit}").touch()
    yield instance
    for directory, _, _ in os.walk(tmp_path):
        os.chmod(directory, 0o700)


@pytest.mark.parametrize("args", [("upgrade", "1.6.4"), ("2",), ("install", "1.6.14", "1.6.18")])
@pytest.mark.parametrize("missing", [UNITS, ("bunkerweb-api",)])
def test_preinstall_skips_absent_units_and_keeps_snapshot(host, args, missing):
    for unit in UNITS:
        if unit in missing:
            (host.root / f"present-{unit}").unlink()
        else:
            host.active(unit)
    config = host.root / "etc/bunkerweb/variables.env"
    config.write_text("RETAINED=yes\n")
    db = host.wal()
    try:
        host.ok("beforeInstall.sh", *args)
    finally:
        db.close()
    transaction = host.root / "var/backups/bunkerweb/transaction"
    assert (transaction / "upgrade").read_text() == "yes\n"
    assert (transaction / "variables.env").read_text() == "RETAINED=yes\n"
    assert rows(transaction / "db.sqlite3") == [("committed in WAL",)]
    active = (transaction / "active").read_text().splitlines() if (transaction / "active").exists() else []
    assert active == [unit for unit in UNITS if unit not in missing]
    for unit in UNITS:
        assert (f"systemctl stop {unit}\n" in host.calls_text()) == (unit not in missing)


@pytest.mark.parametrize(
    "hook,args", [("beforeInstall.sh", ("upgrade", "1.6.14")), ("beforeRemove.sh", ("remove",)), ("postinstall.sh", ("configure", "1.6.14"))]
)
@pytest.mark.parametrize("code", [1, 5])
def test_present_stop_failure_aborts_before_snapshot_restore_or_removal(host, hook, args, code):
    transaction = host.root / "var/backups/bunkerweb/transaction"
    transaction.mkdir()
    (transaction / "upgrade").write_text("yes\n")
    (transaction / "variables.env").write_text("SNAPSHOT=yes\n")
    config = host.root / "etc/bunkerweb/variables.env"
    config.write_text("LIVE=yes\n")
    host.active("bunkerweb-api")
    result = host.run(hook, *args, FAIL_STOP="bunkerweb-api", FAIL_CODE=str(code))
    assert result.returncode != 0, result.stdout + result.stderr
    assert (host.root / "active-bunkerweb-api").exists()
    assert config.read_text() == "LIVE=yes\n"
    assert (transaction / "variables.env").read_text() == "SNAPSHOT=yes\n"
    assert not (transaction / "restored").exists()
    assert (host.root / "usr/share/bunkerweb/scripts").exists()


@pytest.mark.parametrize("args", [("remove",), ("0",)])
def test_remove_skips_absent_units_but_stops_and_disables_present_units(host, args):
    (host.root / "present-bunkerweb-api").unlink()
    for unit in UNITS[:-1]:
        host.active(unit)
    host.ok("beforeRemove.sh", *args)
    for unit in UNITS[:-1]:
        assert not (host.root / f"active-{unit}").exists()
        assert not (host.root / f"enabled-{unit}").exists()
    assert "systemctl stop bunkerweb-api\n" not in host.calls_text()
    assert "systemctl disable bunkerweb-api\n" not in host.calls_text()


def test_postinstall_restores_snapshot_when_api_unit_absent(host):
    transaction = host.root / "var/backups/bunkerweb/transaction"
    transaction.mkdir()
    (transaction / "upgrade").write_text("yes\n")
    (transaction / "variables.env").write_text("SNAPSHOT=yes\n")
    (host.root / "present-bunkerweb-api").unlink()
    host.active("bunkerweb-scheduler")
    host.ok("postinstall.sh", "configure", "1.6.14")
    assert (host.root / "etc/bunkerweb/variables.env").read_text() == "SNAPSHOT=yes\n"
    assert "systemctl stop bunkerweb-api\n" not in host.calls_text()


@pytest.mark.parametrize("args", [("install",), ("1",)])
def test_fresh_install_does_not_snapshot_and_starts_default_services(host, args):
    host.ok("beforeInstall.sh", *args)
    transaction = host.root / "var/backups/bunkerweb/transaction"
    assert (transaction / "upgrade").read_text() == "no\n"
    assert "systemctl stop " not in host.calls_text()
    host.ok("postinstall.sh", "configure")
    for unit in UNITS[:-1]:
        assert (host.root / f"active-{unit}").exists()
        assert (host.root / f"enabled-{unit}").exists()
    assert not (host.root / "enabled-bunkerweb-api").exists()


@pytest.mark.parametrize("explicit_api", [False, True])
@pytest.mark.parametrize("absent_before", [False, True])
def test_reinstall_restores_data_and_enables_services_even_after_retry(host, explicit_api, absent_before):
    if absent_before:
        for unit in UNITS:
            (host.root / f"present-{unit}").unlink()
    config = host.root / "etc/bunkerweb/variables.env"
    config.write_text("RETAINED=yes\n")
    db = host.wal()
    db.close()
    host.ok("beforeInstall.sh", "install", "1.6.14", "1.6.18")
    # Package unpack restores vendor units and may replace payload files.
    for unit in UNITS:
        (host.root / f"present-{unit}").touch()
    config.write_text("PAYLOAD=yes\n")
    env = {"SERVICE_API": "yes"} if explicit_api else {}
    result = host.run("postinstall.sh", "configure", "1.6.14", FAIL_START="bunkerweb-ui", **env)
    assert result.returncode != 0, "reinstall must attempt to start UI"
    assert config.read_text() == "RETAINED=yes\n"
    assert rows(host.root / "var/lib/bunkerweb/db.sqlite3") == [("committed in WAL",)]
    with sqlite3.connect(host.root / "var/lib/bunkerweb/db.sqlite3") as connection:
        connection.execute("INSERT INTO settings VALUES ('new service write')")
    host.ok("postinstall.sh", "configure", "1.6.14", **env)
    assert rows(host.root / "var/lib/bunkerweb/db.sqlite3") == [("committed in WAL",), ("new service write",)]
    for unit in UNITS[:-1] + (("bunkerweb-api",) if explicit_api else ()):
        assert (host.root / f"enabled-{unit}").exists()
        assert (host.root / f"active-{unit}").exists()
    assert (host.root / "enabled-bunkerweb-api").exists() == explicit_api
