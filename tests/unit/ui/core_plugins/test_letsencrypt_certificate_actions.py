"""Legacy LE action restores only display material and parses real PEM metadata."""

from pathlib import Path
from tarfile import TarInfo
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives import hashes

from _core_ui_helpers import certificate_tree, tar_bytes


def test_display_cache_excludes_account_keys(load_plugin, tmp_path):
    module = load_plugin("letsencrypt")
    data = tar_bytes(
        {"./live/example/fullchain.pem": "pem", "./archive/example/cert1.pem": "pem", "./renewal/example.conf": "config", "./accounts/key.json": "secret"}
    )
    module.extract_cache(tmp_path, [{"file_name": "folder:cache.tgz", "data": data}, {"file_name": "other.txt", "data": b"ignored"}])
    assert (tmp_path / "live/example/fullchain.pem").read_text() == "pem"
    assert (tmp_path / "archive/example/cert1.pem").read_text() == "pem"
    assert (tmp_path / "renewal/example.conf").read_text() == "config"
    assert not (tmp_path / "accounts").exists()


@pytest.mark.parametrize(
    "name,allowed",
    [
        (".", True),
        ("live/site/cert.pem", True),
        ("archive/site/key.pem", True),
        ("renewal/site.conf", True),
        ("accounts/id/key.json", False),
        ("../live/key", False),
    ],
)
def test_display_member_allowlist(load_plugin, name, allowed):
    assert load_plugin("letsencrypt")._is_allowed_member(TarInfo(name)) is allowed


def test_action_parses_certificate_and_renewal_metadata(load_plugin, tmp_path):
    cert = certificate_tree(tmp_path)
    result = load_plugin("letsencrypt").retrieve_certificates_info((tmp_path,))
    assert result == {
        "domain": ["example.test"],
        "common_name": ["example.test"],
        "issuer": ["Unit CA"],
        "issuer_server": ["https://acme.example/directory"],
        "valid_from": ["01-01-2026 00:00:00 UTC"],
        "valid_to": ["01-01-2027 00:00:00 UTC"],
        "serial_number": ["42"],
        "fingerprint": [cert.fingerprint(hashes.SHA256()).hex()],
        "version": ["v3"],
        "preferred_profile": ["shortlived"],
        "challenge": ["dns-01"],
        "authenticator": ["dns-route53"],
        "key_type": ["ecdsa"],
    }


def test_action_invalid_pem_keeps_row_and_defaults(load_plugin, tmp_path, capsys):
    path = tmp_path / "live/example/fullchain.pem"
    path.parent.mkdir(parents=True)
    path.write_text("invalid certificate")
    result = load_plugin("letsencrypt").retrieve_certificates_info((tmp_path,))
    assert result["domain"] == ["example"]
    assert result["common_name"] == ["Unknown"]
    assert result["valid_to"] == [None]
    assert "Error while parsing certificate" in capsys.readouterr().out


def test_action_pre_render_uses_temporary_tree(load_plugin, tmp_path, monkeypatch):
    module = load_plugin("letsencrypt")
    monkeypatch.setattr(module, "Path", lambda *parts: tmp_path if len(parts) > 1 else Path(*parts))
    db = Mock()
    db.get_jobs_cache_files.return_value = [{"file_name": "folder:cache.tgz", "data": tar_bytes({"live/example/fullchain.pem": "bad pem"})}]
    result = module.pre_render(None, db=db)
    assert result["list_certificates"]["data"]["domain"] == ["example"]
    assert list(tmp_path.glob("letsencrypt/*/regular/live/*/fullchain.pem")) == []
    db.get_jobs_cache_files.assert_called_once_with(job_name="certbot-renew")


def test_action_initial_db_failure_returns_error(load_plugin, tmp_path, monkeypatch):
    module = load_plugin("letsencrypt")
    monkeypatch.setattr(module, "Path", lambda *parts: tmp_path if len(parts) > 1 else Path(*parts))
    db = Mock()
    db.get_jobs_cache_files.side_effect = RuntimeError("DB offline")
    assert module.pre_render(None, db=db)["error"] == "DB offline"


def test_action_cleanup_preserves_other_request_scratch(load_plugin, tmp_path, monkeypatch):
    module = load_plugin("letsencrypt")
    monkeypatch.setattr(module, "Path", lambda *parts: tmp_path if len(parts) > 1 else Path(*parts))
    sibling = tmp_path / "another-request/private_key.json"
    sibling.parent.mkdir()
    sibling.write_text("another request still needs this")
    db = Mock()
    db.get_jobs_cache_files.return_value = []
    assert module.pre_render(None, db=db)["list_certificates"]["data"]["domain"] == []
    assert sibling.read_text() == "another request still needs this"
