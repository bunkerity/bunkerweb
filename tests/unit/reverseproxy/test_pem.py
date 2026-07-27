"""PEM resolution for the upstream trusted CA and the mutual-TLS client pair.

This is the gate that decides what gets cached and handed to NGINX as a certificate or as a
private key, so the kind check — not merely "does this look like PEM" — is the point.
"""

from base64 import b64encode

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


def test_missing_file_and_empty_data_resolve_to_nothing():
    assert process_pem_data("", "/nope/missing.pem", "app1") is None
    assert process_pem_data("", None, "app1") is None


def test_an_existing_file_is_returned_as_a_path(tmp_path):
    # A file path is handed on untouched; the caller reads and validates it with OpenSSL.
    target = tmp_path / "client-cert.pem"
    target.write_bytes(CERT)
    assert process_pem_data("", str(target), "app1") == target
