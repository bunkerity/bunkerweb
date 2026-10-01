"""QA-UI-6 Q6-M4: a self-signed certificate is issued for the service's own names.

`SELF_SIGNED_SSL_SUBJ` defaults to `/CN=www.example.com/`, and the job passed it to `openssl`
verbatim, with no SAN: every service left at the default got a certificate for www.example.com,
whatever it was called. Left at the default, the subject is now the service's first server name,
and the SANs list all of them; a subject the operator set stays as set.

Loaded with `test_key_pair_integrity.py`'s loader (definitions only, `jobs`/`logger` stubbed).
`generate_cert` is run for real, with the local `openssl`, into `tmp_path`.
"""

from unittest.mock import Mock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

from test_key_pair_integrity import SELF_SIGNED


def test_the_default_subject_becomes_the_services_first_name():
    subj, sans = SELF_SIGNED.certificate_identity("/CN=www.example.com/", ["app.example.org", "www.app.example.org"])

    assert subj == "/CN=app.example.org/"
    assert sans == ["DNS:app.example.org", "DNS:www.app.example.org"]


def test_a_subject_set_by_the_operator_stays_as_set():
    subj, sans = SELF_SIGNED.certificate_identity("/CN=internal.corp/", ["app.example.org"])

    assert subj == "/CN=internal.corp/"
    assert sans == ["DNS:app.example.org"]


def test_an_ip_server_name_is_an_ip_san():
    assert SELF_SIGNED.certificate_identity("/CN=www.example.com/", ["192.0.2.10"])[1] == ["IP:192.0.2.10"]


def test_the_cn_is_the_first_name_that_fits_64_characters():
    too_long = f"{'a' * 60}.example.org"
    subj, sans = SELF_SIGNED.certificate_identity("/CN=www.example.com/", [too_long, "short.example.org"])

    assert subj == "/CN=short.example.org/"
    assert sans == [f"DNS:{too_long}", "DNS:short.example.org"]


def _generate(tmp_path, subj, server_names, *, cached=None):
    stored = {}
    job = Mock()
    job.cache_file.side_effect = lambda name, content, service_id=None: stored.__setitem__(name, content) or (True, None)
    job.get_cache.side_effect = lambda name, service_id=None: (cached or stored).get(name)
    with patch.object(SELF_SIGNED, "JOB", job), patch.object(SELF_SIGNED, "sep", str(tmp_path)):
        ret, status = SELF_SIGNED.generate_cert(server_names[0], "365", subj, tmp_path / "selfsigned", server_names)
    assert ret, "openssl failed"
    return status, stored


def _write_pair(tmp_path, server, stored):
    folder = tmp_path / "selfsigned" / server
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("cert.pem").write_bytes(stored["cert.pem"])
    folder.joinpath("key.pem").write_bytes(stored["key.pem"])


def test_a_generated_certificate_names_the_service(tmp_path):
    status, stored = _generate(tmp_path, "/CN=www.example.com/", ["app.example.org", "www.app.example.org"])

    certificate = x509.load_pem_x509_certificate(stored["cert.pem"], default_backend())
    assert status == 1
    assert certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "app.example.org"
    assert sorted(SELF_SIGNED.certificate_sans(certificate)) == ["DNS:app.example.org", "DNS:www.app.example.org"]


def test_a_certificate_matching_its_names_is_kept(tmp_path):
    _, stored = _generate(tmp_path, "/CN=www.example.com/", ["app.example.org"])
    _write_pair(tmp_path, "app.example.org", stored)

    status, _ = _generate(tmp_path, "/CN=www.example.com/", ["app.example.org"], cached=stored)

    assert status == 0


@pytest.mark.parametrize("server_names", [["app.example.org"], ["app.example.org", "new.example.org"]])
def test_a_certificate_issued_for_other_names_is_regenerated(tmp_path, server_names):
    """The www.example.com certificates already issued, and a service that gained a name."""
    _, legacy = _generate(tmp_path, "/CN=www.example.com/", ["www.example.com"])
    if len(server_names) > 1:
        _, legacy = _generate(tmp_path, "/CN=www.example.com/", server_names[:1])
    _write_pair(tmp_path, server_names[0], legacy)

    status, _ = _generate(tmp_path, "/CN=www.example.com/", server_names, cached=legacy)

    assert status == 1
