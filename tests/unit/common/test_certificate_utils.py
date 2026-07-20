from base64 import b64encode
from datetime import datetime, timedelta, timezone
from io import BytesIO
from tarfile import REGTYPE, SYMTYPE, TarInfo, open as tar_open

import pytest
from cryptography.exceptions import InvalidTag

from certificate_utils import (  # type: ignore
    certificate_status,
    decrypt_private_key,
    encrypt_private_key,
    generate_self_signed,
    load_certificate_keyring,
    parse_certificate,
    read_certbot_cache,
)


def _keyring(key=b"k" * 32):
    return {
        "CERTIFICATE_ENCRYPTION_KEYS": '{"v1":"' + b64encode(key).decode() + '"}',
        "CERTIFICATE_ENCRYPTION_ACTIVE_KEY": "v1",
    }


def test_keyring_encrypts_with_authenticated_resource_id():
    ciphertext, nonce, key_id = encrypt_private_key(b"secret", "cert-1", _keyring())
    assert ciphertext != b"secret"
    assert decrypt_private_key(ciphertext, nonce, key_id, "cert-1", _keyring()) == b"secret"
    with pytest.raises(InvalidTag):
        decrypt_private_key(ciphertext, nonce, key_id, "cert-2", _keyring())


def test_keyring_fails_closed():
    with pytest.raises(ValueError, match="must both be configured"):
        load_certificate_keyring({})
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        load_certificate_keyring(_keyring(b"short"))


def test_parse_and_key_match():
    certificate, private_key = generate_self_signed("example.com", ["www.example.com"])
    parsed = parse_certificate(certificate, private_key)
    assert parsed["common_name"] == "example.com"
    assert parsed["sans"] == ["example.com", "www.example.com"]
    _, other_key = generate_self_signed("other.example.com", [])
    with pytest.raises(ValueError, match="do not match"):
        parse_certificate(certificate, other_key)


def test_status_boundaries():
    now = datetime.now(timezone.utc)
    assert certificate_status(now - timedelta(days=1), now + timedelta(days=31), now=now) == "valid"
    assert certificate_status(now - timedelta(days=1), now + timedelta(days=30), now=now) == "expiring_soon"
    assert certificate_status(now - timedelta(days=2), now - timedelta(days=1), now=now) == "expired"
    assert certificate_status(now + timedelta(days=1), now + timedelta(days=2), now=now) == "not_yet_valid"
    assert certificate_status(now, now + timedelta(days=365), revoked=True, now=now) == "revoked"


def _tar_member(archive, name, data):
    member = TarInfo(name)
    member.type = REGTYPE
    member.size = len(data)
    archive.addfile(member, BytesIO(data))


def test_certbot_cache_reader_resolves_safe_live_symlinks():
    certificate, private_key = generate_self_signed("example.com", [])
    output = BytesIO()
    with tar_open(fileobj=output, mode="w:gz") as archive:
        _tar_member(archive, "archive/example.com/fullchain1.pem", certificate)
        _tar_member(archive, "archive/example.com/privkey1.pem", private_key)
        _tar_member(archive, "renewal/example.com.conf", b"[renewalparams]\nserver = letsencrypt\nauthenticator = webroot\n")
        for filename in ("fullchain", "privkey"):
            member = TarInfo(f"live/example.com/{filename}.pem")
            member.type = SYMTYPE
            member.linkname = f"../../archive/example.com/{filename}1.pem"
            archive.addfile(member)
    records = read_certbot_cache(output.getvalue())
    assert len(records) == 1
    assert records[0]["name"] == "example.com"
    assert records[0]["certificate_pem"] == certificate
    assert records[0]["private_key_pem"] == private_key
    assert records[0]["renewal_metadata"]["server"] == "letsencrypt"


def test_certbot_cache_reader_rejects_traversal():
    output = BytesIO()
    with tar_open(fileobj=output, mode="w:gz") as archive:
        _tar_member(archive, "../../escape", b"bad")
    with pytest.raises(ValueError, match="path traversal"):
        read_certbot_cache(output.getvalue())
