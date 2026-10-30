"""Package upgrades repair old lock modes without replacing the lock inode."""

import stat
import subprocess
from pathlib import Path

import pytest

POSTINSTALL = Path(__file__).resolve().parents[3] / "src/linux/scripts/postinstall.sh"


def _run_permissions(tmp_path):
    script = POSTINSTALL.read_text()
    helper = script.split("# Decompress deps directory", 1)[0]
    permissions = script.split("# Give all the permissions", 1)[1].split("chmod 550 -R /usr/share/bunkerweb/", 1)[0]
    for path in (
        "/usr/share/bunkerweb",
        "/var/cache/bunkerweb",
        "/var/lib/bunkerweb",
        "/etc/bunkerweb",
        "/var/tmp/bunkerweb",
        "/var/run/bunkerweb",
        "/var/log/bunkerweb",
    ):
        (tmp_path / path.lstrip("/")).mkdir(parents=True, exist_ok=True)
    # No host nginx account needed; exercise the real chmod commands on scratch paths.
    harness = (
        helper
        + "\nchown() { :; }\n"
        + permissions.replace("/var/", f"{tmp_path}/var/").replace("/etc/", f"{tmp_path}/etc/").replace("/usr/", f"{tmp_path}/usr/")
    )
    result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644])
def test_upgrade_repairs_existing_lock_without_replacing_it(tmp_path, mode):
    lock = tmp_path / "var/lib/bunkerweb/db.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("1234\n")
    lock.chmod(mode)
    before = lock.stat()

    for _ in range(2):
        _run_permissions(tmp_path)
        after = lock.stat()
        assert stat.S_IMODE(after.st_mode) == 0o644
        assert (after.st_ino, after.st_uid, after.st_gid) == (before.st_ino, before.st_uid, before.st_gid)
        assert lock.read_text() == "1234\n"


def test_upgrade_does_not_create_an_absent_lock(tmp_path):
    _run_permissions(tmp_path)
    assert not (tmp_path / "var/lib/bunkerweb/db.lock").exists()
