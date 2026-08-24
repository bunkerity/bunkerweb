"""Dedicated bwcli image capability reporting and backup preflight."""

import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
for source in ("cli", "api", "utils", "db"):
    path = ROOT / "src" / "common" / source
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import CLI as CLI_MODULE  # noqa: E402


def _main_env(**values):
    paths = [ROOT / "src" / "common" / name for name in ("cli", "api", "utils", "db")]
    return os.environ | {"PYTHONPATH": os.pathsep.join(map(str, paths)), **values}


def test_capabilities_detect_a_reachable_api_and_backup_path(tmp_path, monkeypatch):
    detect = getattr(CLI_MODULE, "detect_capabilities", None)
    assert callable(detect), "bwcli needs a capability detector"

    connections = []
    monkeypatch.setattr(CLI_MODULE, "create_connection", lambda address, timeout: connections.append((address, timeout)) or nullcontext())
    monkeypatch.setenv("BWCLI_API_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("BWCLI_TIMEOUT", "0.2")
    monkeypatch.setenv("BACKUP_DIRECTORY", str(tmp_path))
    capabilities = detect()

    assert connections == [(("127.0.0.1", 8765), 0.2)]
    assert capabilities["api"] == {"configured": True, "reachable": True}
    assert set(capabilities["database"]) == {"sqlite", "mysql", "mariadb", "postgresql"}
    assert capabilities["backup"] == {"path": str(tmp_path), "mounted": False, "writable": True}


def test_capabilities_resolve_a_bare_api_hostname(monkeypatch):
    detect = getattr(CLI_MODULE, "detect_capabilities", None)
    assert callable(detect), "bwcli needs a capability detector"

    connections = []
    monkeypatch.delenv("API_HTTP_PORT", raising=False)
    monkeypatch.setattr(CLI_MODULE, "create_connection", lambda address, timeout: connections.append((address, timeout)) or nullcontext())
    monkeypatch.setenv("BWCLI_API_URL", "bw-api")
    capabilities = detect()

    assert connections == [(("bw-api", 5000), 2.0)]
    assert capabilities["api"] == {"configured": True, "reachable": True}


def test_backup_preflight_requires_a_mount_only_when_the_image_requests_it(tmp_path, monkeypatch):
    preflight = getattr(CLI_MODULE, "backup_preflight", None)
    assert callable(preflight), "bwcli needs a backup-volume preflight"

    monkeypatch.delenv("BWCLI_REQUIRE_BACKUP_MOUNT", raising=False)
    assert preflight(tmp_path) == (True, "")

    monkeypatch.setenv("BWCLI_REQUIRE_BACKUP_MOUNT", "yes")
    ok, error = preflight(tmp_path)
    assert ok is False
    assert "not mounted" in error


def test_bind_mounts_are_detected_from_linux_mountinfo(tmp_path):
    is_mounted = getattr(CLI_MODULE, "is_mounted", None)
    assert callable(is_mounted), "bind mounts need mountinfo detection"

    mountinfo = tmp_path / "mountinfo"
    target = tmp_path / "backups"
    target.mkdir()
    mountinfo.write_text(f"36 25 0:32 / {target} rw,relatime - ext4 /dev/sda rw\n", encoding="utf-8")
    assert is_mounted(target, mountinfo) is True


def test_help_advertises_capabilities():
    result = subprocess.run(
        [sys.executable, "src/common/cli/main.py", "--help"],
        cwd=ROOT,
        env=_main_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "capabilities" in result.stdout


def test_backup_mount_is_checked_before_an_invalid_database_is_opened(tmp_path):
    result = subprocess.run(
        [sys.executable, "src/common/cli/main.py", "plugin", "backup", "save"],
        cwd=ROOT,
        env=_main_env(
            BACKUP_DIRECTORY=str(tmp_path),
            BWCLI_REQUIRE_BACKUP_MOUNT="yes",
            DATABASE_URI="not-a-database-uri",
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not mounted" in result.stderr
    assert "Invalid database string" not in result.stderr


def test_backup_long_directory_option_is_preflighted(tmp_path):
    missing = tmp_path / "not-mounted"
    missing.mkdir()
    result = subprocess.run(
        [sys.executable, "src/common/cli/main.py", "plugin", "backup", "save", "--directory", str(missing)],
        cwd=ROOT,
        env=_main_env(BACKUP_DIRECTORY="/unused", BWCLI_REQUIRE_BACKUP_MOUNT="yes", DATABASE_URI="not-a-database-uri"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert f"Backup directory {missing} is not mounted" in result.stderr
    assert "Invalid database string" not in result.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
