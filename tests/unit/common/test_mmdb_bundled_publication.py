"""Bundled ASN/Country publication is all-or-nothing on local disk."""

from unittest.mock import Mock

import pytest

import mmdb


@pytest.fixture
def bundled(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    verified = {}
    for descriptor in mmdb.DESCRIPTORS:
        candidate = tmp_path / descriptor.local_name
        candidate.write_bytes(f"new-{descriptor.key}".encode())
        verified[descriptor] = mmdb.VerifiedCandidate(candidate, mmdb.DBIPMetadata("a" * 40, "unused"), "a" * 40, mmdb.file_hash(candidate))
        (target / descriptor.local_name).write_bytes(f"old-{descriptor.key}".encode())
        (target / descriptor.local_name).chmod(0o640)
    return target, verified


def test_bundled_publication_preserves_modes_and_skips_unchanged(bundled):
    target, verified = bundled
    assert mmdb._publish_bundled(verified, target, mmdb.LOGGER) is True
    for descriptor in mmdb.DESCRIPTORS:
        path = target / descriptor.local_name
        assert path.read_bytes() == f"new-{descriptor.key}".encode()
        assert path.stat().st_mode & 0o777 == 0o640
    assert mmdb._publish_bundled(verified, target, mmdb.LOGGER) is False
    assert sorted(p.name for p in target.iterdir()) == ["asn.mmdb", "country.mmdb"]


@pytest.mark.parametrize("preexisting", [True, False])
def test_second_publication_failure_rolls_back_first(bundled, monkeypatch, preexisting):
    target, verified = bundled
    if not preexisting:
        for path in target.iterdir():
            path.unlink()
    replace = mmdb.os.replace

    def fail_country(source, destination):
        if destination == target / "country.mmdb":
            raise OSError("publication failed")
        replace(source, destination)

    monkeypatch.setattr(mmdb.os, "replace", fail_country)
    with pytest.raises(OSError, match="publication failed"):
        mmdb._publish_bundled(verified, target, mmdb.LOGGER)
    if preexisting:
        assert (target / "asn.mmdb").read_bytes() == b"old-asn"
        assert (target / "country.mmdb").read_bytes() == b"old-country"
    else:
        assert list(target.iterdir()) == []
    assert not list(target.glob(".*"))


def test_update_verifies_both_candidates_before_touching_targets(bundled, tmp_path, monkeypatch):
    target, verified = bundled
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata("a" * 40, "unused"))
    monkeypatch.setattr(mmdb, "download_verified_candidate", Mock(side_effect=[verified[mmdb.ASN], mmdb.IntegrityError("expected", "actual")]))
    assert mmdb.update_bundled_mmdbs(target, tmp_path / "work") is False
    assert (target / "asn.mmdb").read_bytes() == b"old-asn"
    assert (target / "country.mmdb").read_bytes() == b"old-country"


def test_update_bundled_returns_success_after_verified_publication(bundled, tmp_path, monkeypatch):
    target, verified = bundled
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata("a" * 40, "unused"))
    monkeypatch.setattr(mmdb, "download_verified_candidate", lambda descriptor, *_, **__: verified[descriptor])
    assert mmdb.update_bundled_mmdbs(target, tmp_path / "work") is True
    assert (target / "country.mmdb").read_bytes() == b"new-country"


def test_update_bundled_reports_disk_publication_error(bundled, tmp_path, monkeypatch):
    target, verified = bundled
    monkeypatch.setattr(mmdb, "fetch_metadata", lambda *_, **__: mmdb.DBIPMetadata("a" * 40, "unused"))
    monkeypatch.setattr(mmdb, "download_verified_candidate", lambda descriptor, *_, **__: verified[descriptor])
    monkeypatch.setattr(mmdb, "_publish_bundled", Mock(side_effect=OSError("read-only disk")))
    assert mmdb.update_bundled_mmdbs(target, tmp_path / "work") is False
    assert (target / "country.mmdb").read_bytes() == b"old-country"
