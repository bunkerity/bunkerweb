"""PEM resolution for the upstream trusted CA and the mutual-TLS client pair.

This is the gate that decides what gets cached and handed to NGINX as a certificate or as a
private key, so the kind check — not merely "does this look like PEM" — is the point.
"""

from base64 import b64encode
from pathlib import Path

import pytest

from reverseproxy_pem import is_pem, process_pem_data  # type: ignore

CERT = b"-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n"
KEY = b"-----BEGIN PRIVATE KEY-----\nMIIE\n-----END PRIVATE KEY-----\n"


def test_is_pem_matches_the_requested_kind():
    assert is_pem(CERT, "certificate") and not is_pem(CERT, "key")
    assert is_pem(KEY, "key") and not is_pem(KEY, "certificate")


def test_every_private_key_banner_is_accepted():
    # Keys come out of OpenSSL under several banners depending on algorithm and encryption.
    for banner in (b"PRIVATE KEY", b"RSA PRIVATE KEY", b"EC PRIVATE KEY", b"ENCRYPTED PRIVATE KEY"):
        assert is_pem(b"-----BEGIN " + banner + b"-----\nx\n-----END " + banner + b"-----\n", "key"), banner


def test_non_pem_is_rejected():
    for blob in (b"", b"   ", b"not pem at all", b"-----BEGIN", b"-----BEGIN SOMETHING ELSE-----\nx\n"):
        assert not is_pem(blob, "key")
        assert not is_pem(blob, "certificate")


def test_plain_pem_data_passes_through():
    assert process_pem_data(CERT.decode(), None, "app1") == CERT
    assert process_pem_data(KEY.decode(), None, "app1", kind="key", label="client key") == KEY


def test_base64_data_is_decoded():
    assert process_pem_data(b64encode(KEY).decode(), None, "app1", kind="key", label="client key") == KEY
    # Padding is restored, so a stripped base64 blob still decodes.
    assert process_pem_data(b64encode(CERT).decode().rstrip("="), None, "app1") == CERT


def test_material_of_the_wrong_kind_is_refused():
    # A certificate pasted into the key field must never reach NGINX as a key, and vice versa.
    assert process_pem_data(CERT.decode(), None, "app1", kind="key", label="client key") is None
    assert process_pem_data(KEY.decode(), None, "app1", kind="certificate", label="client certificate") is None
    assert process_pem_data(b64encode(CERT).decode(), None, "app1", kind="key", label="client key") is None


def test_missing_file_remains_distinct_from_invalid_or_empty_data():
    assert process_pem_data("", "/nope/missing.pem", "app1") == Path("/nope/missing.pem")
    assert process_pem_data("", None, "app1") is None


def test_an_existing_file_is_returned_as_a_path(tmp_path):
    # A file path is handed on untouched; the caller reads and validates it with OpenSSL.
    target = tmp_path / "client-cert.pem"
    target.write_bytes(CERT)
    assert process_pem_data("", str(target), "app1") == target


CRL = b"-----BEGIN X509 CRL-----\nMIIB\n-----END X509 CRL-----\n"


def test_crl_kind_is_distinct_from_certificate_and_key():
    assert is_pem(CRL, "crl")
    assert not is_pem(CERT, "crl")
    assert not is_pem(KEY, "crl")
    assert not is_pem(CRL, "certificate")
    assert not is_pem(CRL, "key")
    assert not is_pem(b"not pem", "crl")


def test_plain_and_base64_crl_data():
    for data in (CRL.decode(), b64encode(CRL).decode()):
        assert process_pem_data(data, None, "app1", kind="crl", label="CRL") == CRL
    assert process_pem_data(CERT.decode(), None, "app1", kind="crl", label="CRL") is None


def test_invalid_certificate_bundle_raises():
    from reverseproxy_pem import validate_certificate_bundle

    with pytest.raises(ValueError):
        validate_certificate_bundle(CERT + CERT)
