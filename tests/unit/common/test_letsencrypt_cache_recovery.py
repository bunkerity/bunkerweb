"""Exercise account repair and lineage quarantine against disposable Certbot trees."""

import os
from pathlib import Path
from unittest.mock import Mock

import pytest

import letsencrypt_consistency as le

PRODUCTION = "https://acme-v02.api.letsencrypt.org/directory"
STAGING = "https://acme-staging-v02.api.letsencrypt.org/directory"


def account(root, name="current", server=PRODUCTION, mtime=100):
    directory = root / "accounts" / le._server_subpath(server) / name
    directory.mkdir(parents=True)
    for filename in ("regr.json", "private_key.json", "meta.json"):
        (directory / filename).write_text("{}")
    os.utime(directory, (mtime, mtime))
    return directory


def lineage(root, name="example.com", account_id="current", server=PRODUCTION, body_name=None):
    body_name = body_name or name
    renewal = root / "renewal"
    renewal.mkdir(exist_ok=True)
    live = root / "live" / body_name
    archive = root / "archive" / body_name
    live.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    conf = renewal / f"{name}.conf"
    lines = [f"archive_dir = {archive}"]
    for kind in ("cert", "privkey", "chain", "fullchain"):
        (archive / f"{kind}1.pem").write_text(f"{name}-{kind}")
        (live / f"{kind}.pem").symlink_to(Path("../../archive") / body_name / f"{kind}1.pem")
        lines.append(f"{kind} = {live / (kind + '.pem')}")
    conf.write_text("\n".join(lines + ["[renewalparams]", f"account = {account_id}", f"server = {server}"]) + "\n")
    return conf


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(le, "QUARANTINE_ROOT", tmp_path / "quarantine")
    monkeypatch.setattr(le, "LE_CACHE_LOCK_PATH", tmp_path / "locks" / "cache.lock")


@pytest.mark.parametrize("account_id", ["", "None", "current"])
def test_consistency_requires_only_referenced_accounts(tmp_path, account_id):
    assert le.letsencrypt_cache_consistent(tmp_path) == (True, "")
    lineage(tmp_path, account_id=account_id)
    ok, reason = le.letsencrypt_cache_consistent(tmp_path)
    assert ok is (account_id != "current")
    if account_id == "current":
        assert "accounts/ dir is missing" in reason
        account(tmp_path)
    assert le.letsencrypt_cache_consistent(tmp_path) == (True, "")
    assert le.detect_orphan_renewals(tmp_path) == []


def test_missing_account_report_identifies_lineage_and_ca(tmp_path):
    lineage(tmp_path, account_id="missing")
    account(tmp_path, name="other")
    ok, reason = le.letsencrypt_cache_consistent(tmp_path)
    assert ok is False
    assert "missing" in reason and "other" in reason
    assert le.detect_orphan_renewals(tmp_path) == [{"cert_name": "example.com", "account": "missing", "server": PRODUCTION}]


def test_usable_accounts_are_ca_scoped_and_newest_first(tmp_path):
    old = account(tmp_path, "old", mtime=10)
    newest = account(tmp_path, "new", mtime=20)
    account(tmp_path, "staging", STAGING, mtime=30)
    incomplete = account(tmp_path, "incomplete", mtime=40)
    (incomplete / "private_key.json").unlink()
    assert le.usable_accounts_for_server(tmp_path, PRODUCTION) == [newest, old]
    assert le.usable_accounts_for_server(tmp_path, "") == []


def test_production_falls_back_to_v1_accounts_without_using_staging(tmp_path):
    old = account(tmp_path, "legacy", "https://acme-v01.api.letsencrypt.org/directory")
    account(tmp_path, "staging", STAGING)
    assert le.usable_accounts_for_server(tmp_path, PRODUCTION) == [old]
    assert le._searched_subpaths(PRODUCTION) == ["acme-v02.api.letsencrypt.org/directory", "acme-v01.api.letsencrypt.org/directory"]


def test_repoint_orphan_preserves_mode_and_unrelated_config(tmp_path):
    conf = lineage(tmp_path, account_id="gone")
    conf.chmod(0o640)
    before = conf.read_text()
    account(tmp_path, "replacement")
    assert le.repoint_orphan_renewals(tmp_path, Mock()) == ["example.com"]
    assert conf.read_text() == before.replace("account = gone", "account = replacement")
    assert conf.stat().st_mode & 0o777 == 0o640
    assert le.repoint_orphan_renewals(tmp_path) == []
    assert le.detect_broken_lineages(tmp_path) == []


@pytest.mark.parametrize("server", ["", STAGING])
def test_repoint_does_not_guess_ca_or_cross_ca_boundary(tmp_path, server):
    conf = lineage(tmp_path, account_id="gone", server=server)
    before = conf.read_bytes()
    account(tmp_path)
    assert le.repoint_orphan_renewals(tmp_path, Mock()) == []
    assert conf.read_bytes() == before


def test_atomic_account_rewrite_failure_preserves_original_and_cleans_tmp(tmp_path, monkeypatch):
    conf = lineage(tmp_path, account_id="gone")
    before = conf.read_bytes()
    monkeypatch.setattr(Path, "replace", Mock(side_effect=OSError("read-only")))
    assert le._rewrite_account_reference(conf, "gone", "replacement") is False
    assert conf.read_bytes() == before
    assert not list(conf.parent.glob(".*.tmp"))
    assert le._rewrite_account_reference(conf, "different", "replacement") is False
    assert le._rewrite_account_reference(tmp_path / "absent", "gone", "replacement") is False


@pytest.mark.parametrize(
    "name,expected", [("example.com", True), ("wildcard-example-ecdsa", True), ("", False), (".", False), ("..", False), ("../escape", False), ("x;y", False)]
)
def test_certificate_name_boundary(name, expected):
    assert le.is_safe_cert_name(name) is expected


def test_containment_resolves_symlinks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    assert le.path_is_inside(root / "nested" / "file", root)
    assert not le.path_is_inside(root / "escape" / "file", root)


@pytest.mark.parametrize(
    "damage,reason",
    [
        ("missing-reference", "missing required"),
        ("mismatch", "name mismatch"),
        ("absent-material", "no certificate material"),
        ("regular-file", "not usable symlinks"),
        ("dangling-link", "not usable symlinks"),
    ],
)
def test_broken_lineage_detection_distinguishes_failure_modes(tmp_path, damage, reason):
    conf = lineage(tmp_path, body_name="other" if damage == "mismatch" else None)
    if damage == "missing-reference":
        conf.write_text("account = current\n")
    elif damage == "absent-material":
        (tmp_path / "archive/example.com/fullchain1.pem").unlink()
    elif damage in ("regular-file", "dangling-link"):
        path = tmp_path / "live/example.com/cert.pem"
        path.unlink()
        if damage == "regular-file":
            path.write_text("dereferenced")
        else:
            path.symlink_to("missing.pem")
    broken = le.detect_broken_lineages(tmp_path)
    assert len(broken) == 1
    assert broken[0]["cert_name"] == "example.com"
    assert reason in broken[0]["reason"]
    assert broken[0]["renewal_conf"] == conf.as_posix()


@pytest.mark.parametrize("quarantine", [False, True])
def test_purge_preserves_shared_lineage_material(tmp_path, quarantine):
    root = tmp_path / "cache"
    root.mkdir()
    conf = lineage(root, "broken", body_name="shared")
    (root / "renewal/shared.conf").write_text("account = current\n")
    target = tmp_path / "quarantine" if quarantine else None
    assert le.purge_lineage(root, conf, target) == [conf.as_posix()]
    assert not conf.exists()
    assert (root / "live/shared/cert.pem").read_text() == "broken-cert"
    assert (root / "archive/shared/cert1.pem").exists()
    if quarantine:
        assert len(list(target.glob("*/renewal/broken.conf"))) == 1


def test_purge_rejects_escape_symlink_and_unsafe_body_name(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_bytes(b"safe")
    (root / "live").mkdir()
    (root / "live/example.com").symlink_to(outside, target_is_directory=True)
    (root / "renewal").mkdir()
    conf = root / "renewal/example.com.conf"
    conf.write_text("archive_dir = /somewhere/..\n")
    assert le.purge_lineage(root, conf, None, Mock()) == [conf.as_posix()]
    assert (outside / "keep").read_bytes() == b"safe"
    assert (root / "live/example.com").is_symlink()


def test_sanitize_moves_broken_lineage_and_reaps_expired_quarantine(tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    conf = lineage(root)
    (root / "archive/example.com/fullchain1.pem").unlink()
    quarantine = le.QUARANTINE_ROOT
    quarantine.mkdir()
    old_dir = quarantine / "expired"
    old_dir.mkdir()
    (old_dir / "material").write_text("old")
    old_file = quarantine / "expired-file"
    old_file.write_text("old")
    fresh = quarantine / "recent"
    fresh.write_text("recent")
    for path in (old_dir, old_file):
        os.utime(path, (1, 1))
    assert le.sanitize_le_cache(root, Mock()) == ["example.com"]
    assert not old_dir.exists() and not old_file.exists()
    assert fresh.read_text() == "recent"
    assert not conf.exists()
    assert len(list(quarantine.glob("*-example.com/renewal/example.com.conf"))) == 1
    assert not (root / "live/example.com").exists()
    assert not (root / "archive/example.com").exists()


def test_quarantine_refused_account_keeps_key_material(tmp_path):
    path = account(tmp_path)
    assert le.quarantine_account(path, Mock()) is True
    assert not path.exists()
    assert len(list(le.QUARANTINE_ROOT.glob("*-account-current/private_key.json"))) == 1


def test_cache_lock_is_released_after_exception():
    with pytest.raises(RuntimeError, match="body failed"):
        with le.le_cache_write_lock():
            assert le.LE_CACHE_LOCK_PATH.exists()
            assert le.LE_CACHE_LOCK_PATH.stat().st_mode & 0o777 == 0o600
            raise RuntimeError("body failed")
    # A second acquisition exercises the exception cleanup path.
    with le.le_cache_write_lock():
        assert le.LE_CACHE_LOCK_PATH.is_file()
