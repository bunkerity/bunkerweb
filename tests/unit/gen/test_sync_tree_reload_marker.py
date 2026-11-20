"""Reload-marker recovery needs age proof and an unchanged marker token."""

import logging
from pathlib import Path

import pytest

import sync_tree


@pytest.fixture
def marker(tmp_path, monkeypatch):
    marker = tmp_path / "reloading"
    uptime = tmp_path / "uptime"
    uptime.write_bytes(b"1000.20 900.40\n")
    real_path = Path
    monkeypatch.setattr(sync_tree, "Path", lambda *parts: uptime if parts == ("/proc/uptime",) else real_path(*parts))
    return marker


@pytest.mark.parametrize("token,removed", [(b"12.34.699", True), (b"12.34.700", False), (b"12.34.900", False), (b"garbled", False), (b"12.34.0\n", False)])
def test_marker_removal_requires_valid_monotonic_token_older_than_five_minutes(marker, caplog, token, removed):
    marker.write_bytes(token)
    with caplog.at_level(logging.WARNING):
        assert sync_tree._remove_orphaned_marker(marker, logging.getLogger("marker-test")) is removed
    assert marker.exists() is not removed
    if removed:
        assert "Removing orphaned reload marker" in caplog.text
    else:
        assert marker.read_bytes() == token


def test_republished_marker_is_not_unlinked(marker, monkeypatch):
    marker.write_bytes(b"12.34.1")
    original = Path.read_bytes
    reads = 0

    def read(path):
        nonlocal reads
        if path == marker:
            reads += 1
            if reads == 2:
                marker.write_bytes(b"12.34.999")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    assert sync_tree._remove_orphaned_marker(marker, logging.getLogger("marker-test")) is False
    assert marker.read_bytes() == b"12.34.999"


def test_marker_read_failure_keeps_exclusion(marker, monkeypatch):
    marker.write_bytes(b"12.34.1")
    monkeypatch.setattr(Path, "read_bytes", lambda path: (_ for _ in ()).throw(PermissionError("denied")))
    assert sync_tree._remove_orphaned_marker(marker, logging.getLogger("marker-test")) is False
    assert marker.exists()


def test_install_guard_clears_old_marker_and_releases_lock(marker, tmp_path):
    marker.write_bytes(b"12.34.1")
    lock = tmp_path / "generating"
    with sync_tree.install_guard(logging.getLogger("marker-test"), reloading=marker, generating=lock, wait=0, poll=0, nginx_pid=tmp_path / "nginx.pid"):
        assert not marker.exists()
        assert lock.stat().st_mode & 0o777 == 0o644
    with sync_tree.install_guard(logging.getLogger("marker-test"), reloading=marker, generating=lock, wait=0, poll=0, nginx_pid=tmp_path / "nginx.pid"):
        assert lock.exists()
