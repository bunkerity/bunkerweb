"""The mTLS client-cert job tells the operator about CA/CRL material that makes NGINX refuse clients.

NGINX sets `X509_V_FLAG_CRL_CHECK | X509_V_FLAG_CRL_CHECK_ALL`: an expired CRL, or a chain whose CA has
no CRL, refuses valid clients with nothing in the Scheduler log. The job still publishes the material
(NGINX fails closed, and keeping older material is no better), but names the service and the CA.
All PKI is generated in memory; no key material is stored in the tree.
"""

import logging
from datetime import datetime, timedelta, timezone

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from _other_jobs_helpers import Cache, load_job

JOB = "mtls/jobs/client-cert.py"
SERVICE = "app.example"
NOW = datetime.now(timezone.utc)


def make_ca(common_name, *, issuer=None, key=None, serial=None, not_before=None, not_after=None, ca=True):
    """Return (certificate, key); self-signed unless `issuer=(certificate, key)` is given."""
    key = key or ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer[0].subject if issuer else name)
        .public_key(key.public_key())
        .serial_number(serial or x509.random_serial_number())
        .not_valid_before(not_before or NOW - timedelta(days=30))
        .not_valid_after(not_after or NOW + timedelta(days=365))
    )
    if ca is not None:
        builder = builder.add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    return builder.sign(issuer[1] if issuer else key, hashes.SHA256()), key


def der_encode(tag, body):
    size = len(body)
    if size < 0x80:
        return bytes([tag, size]) + body
    length = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(length)]) + length + body


def der_header(data, pos):
    """Return (header length, body length) of the TLV starting at `pos`."""
    first = data[pos + 1]
    if first < 0x80:
        return 2, first
    count = first & 0x7F
    begin = pos + 2
    end = begin + count
    return 2 + count, int.from_bytes(data[begin:end], "big")


def der_split(data):
    """Return the direct children of a DER SEQUENCE as whole TLVs."""
    start = der_header(data, 0)[0]
    children = []
    while start < len(data):
        header, size = der_header(data, start)
        end = start + header + size
        children.append(data[start:end])
        start = end
    return children


def make_crl(signer, next_update=NOW + timedelta(days=30)):
    """Sign a CRL; `next_update=None` drops the field, which the cryptography builder refuses, so the TBS is re-signed by hand."""
    cert, key = signer
    builder = x509.CertificateRevocationListBuilder().issuer_name(cert.subject).last_update(NOW - timedelta(days=10)).next_update(next_update or NOW)
    crl = builder.sign(key, hashes.SHA256())
    if next_update is not None:
        return crl.public_bytes(serialization.Encoding.PEM)
    tbs, algorithm, _ = der_split(crl.public_bytes(serialization.Encoding.DER))
    tbs = der_encode(0x30, b"".join(der_split(tbs)[:-1]))  # version, algorithm, issuer, thisUpdate: nextUpdate is last
    signature = key.sign(tbs, ec.ECDSA(hashes.SHA256()))
    rebuilt = x509.load_der_x509_crl(der_encode(0x30, tbs + algorithm + der_encode(0x03, b"\x00" + signature)))
    assert rebuilt.next_update_utc is None
    return rebuilt.public_bytes(serialization.Encoding.PEM)


def pem(*certs):
    return b"".join(cert.public_bytes(serialization.Encoding.PEM) for cert in certs)


def run_job(monkeypatch, tmp_path, caplog, ca_pem, *crls):
    caplog.set_level(logging.DEBUG)
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    env = {"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE_DATA": ca_pem.decode()}
    if crls:
        env["MTLS_CRL_DATA"] = b"".join(crls).decode()
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    published = {name: (cache.job_path / SERVICE / name).read_bytes() for name in ("ca.pem", "crl.pem") if (cache.job_path / SERVICE / name).is_file()}
    return status, published, [(r.levelno, r.getMessage()) for r in caplog.records if r.levelno >= logging.WARNING]


def day(moment):
    return moment.strftime("%Y-%m-%d")


def test_a_crl_past_next_update_is_an_error_naming_the_service_the_signer_and_the_date(tmp_path, monkeypatch, caplog):
    root = make_ca("expired-crl-root")
    expired = NOW - timedelta(days=2)
    ca_pem, crl = pem(root[0]), make_crl(root, next_update=expired)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, ca_pem, crl)

    assert status == 1 and published == {"ca.pem": ca_pem, "crl.pem": crl}  # still published
    assert [level for level, _ in records] == [logging.ERROR]
    message = records[0][1]
    assert SERVICE in message and "expired-crl-root" in message and day(expired) in message
    assert "clients whose chain goes through that CA are refused until a fresh CRL is published" in message
    assert "every client" not in message


def test_a_crl_expiring_within_seven_days_is_one_warning_with_the_date(tmp_path, monkeypatch, caplog):
    root = make_ca("soon-crl-root")
    soon = NOW + timedelta(days=3)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, pem(root[0]), make_crl(root, next_update=soon))

    assert status == 1 and set(published) == {"ca.pem", "crl.pem"}
    assert [level for level, _ in records] == [logging.WARNING]
    assert SERVICE in records[0][1] and "soon-crl-root" in records[0][1] and day(soon) in records[0][1]


def test_a_crl_expiring_after_seven_days_or_with_no_next_update_is_silent(tmp_path, monkeypatch, caplog):
    root = make_ca("quiet-crl-root")
    for next_update in (NOW + timedelta(days=8), None):
        _, published, records = run_job(monkeypatch, tmp_path / str(next_update), caplog, pem(root[0]), make_crl(root, next_update=next_update))
        assert "crl.pem" in published
        assert records == []


def test_a_ca_without_a_crl_is_one_warning_when_another_ca_has_one(tmp_path, monkeypatch, caplog):
    root = make_ca("bare-root")
    inter = make_ca("covered-intermediate", issuer=root)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, pem(root[0], inter[0]), make_crl(inter))

    assert status == 1 and "crl.pem" in published
    assert [level for level, _ in records] == [logging.WARNING]
    message = records[0][1]
    assert "no CRL issued by CN=bare-root" in message and SERVICE in message
    assert "covered-intermediate" not in message
    assert "certificates issued by that CA cannot be checked, so clients whose chain includes one are refused" in message


def test_no_coverage_message_when_every_ca_has_a_crl_or_none_is_configured(tmp_path, monkeypatch, caplog):
    root = make_ca("full-root")
    inter = make_ca("full-intermediate", issuer=root)

    _, _, records = run_job(monkeypatch, tmp_path / "full", caplog, pem(root[0], inter[0]), make_crl(root), make_crl(inter))
    assert records == []

    caplog.clear()
    status, published, records = run_job(monkeypatch, tmp_path / "none", caplog, pem(root[0], inter[0]))
    assert status == 1 and set(published) == {"ca.pem"}
    assert records == []


def test_coverage_follows_the_signing_key_not_the_subject_name(tmp_path, monkeypatch, caplog):
    """A key rollover keeps one DN on two CA certificates: a CRL signed by one covers only that one."""
    old = make_ca("rolled-root", serial=0x1111)
    new = make_ca("rolled-root", serial=0x2222)

    _, _, records = run_job(monkeypatch, tmp_path, caplog, pem(old[0], new[0]), make_crl(old))

    assert [level for level, _ in records] == [logging.WARNING]
    assert "no CRL issued by CN=rolled-root" in records[0][1] and "2222" in records[0][1] and "1111" not in records[0][1]


def test_a_crl_from_an_issuer_outside_the_bundle_is_published_with_a_warning_that_does_not_claim_leaf_only(tmp_path, monkeypatch, caplog):
    root = make_ca("in-bundle-root")
    outsider = make_ca("outside-intermediate", issuer=root)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, pem(root[0]), make_crl(outsider))

    assert status == 1 and "crl.pem" in published
    messages = [message for _, message in records]
    assert any("outside-intermediate" in m and "not part of" in m and SERVICE in m for m in messages)
    assert not any("leaf" in m for m in messages)
    assert any("no CRL issued by CN=in-bundle-root" in m for m in messages)  # the CRL signs for a CA the bundle does not hold
    assert logging.ERROR not in [level for level, _ in records]


def test_the_job_source_no_longer_claims_nginx_checks_the_leaf_only():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[3] / "src/common/core" / JOB).read_text()
    assert "checks the leaf only" not in source
    assert "CRL_CHECK_ALL" in source


def test_an_expired_bundle_certificate_is_an_error_naming_it(tmp_path, monkeypatch, caplog):
    gone = NOW - timedelta(days=2)
    root = make_ca("gone-root", not_before=NOW - timedelta(days=90), not_after=gone)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, pem(root[0]))

    assert status == 1 and "ca.pem" in published
    assert [level for level, _ in records] == [logging.ERROR]
    assert SERVICE in records[0][1] and "gone-root" in records[0][1] and day(gone) in records[0][1]


def test_a_bundle_certificate_expiring_within_thirty_days_is_a_warning_with_the_date(tmp_path, monkeypatch, caplog):
    soon = NOW + timedelta(days=20)
    root = make_ca("ageing-root", not_after=soon)

    _, published, records = run_job(monkeypatch, tmp_path, caplog, pem(root[0]))

    assert "ca.pem" in published
    assert [level for level, _ in records] == [logging.WARNING]
    assert SERVICE in records[0][1] and "ageing-root" in records[0][1] and day(soon) in records[0][1]


@pytest.mark.parametrize("ca", [False, None], ids=["ca-false", "no-basic-constraints"])
def test_a_bundle_certificate_that_is_not_a_ca_is_a_warning(tmp_path, monkeypatch, caplog, ca):
    leaf = make_ca("not-a-ca", ca=ca)

    _, published, records = run_job(monkeypatch, tmp_path, caplog, pem(leaf[0]))

    assert "ca.pem" in published
    assert [level for level, _ in records] == [logging.WARNING]
    assert SERVICE in records[0][1] and "not-a-ca" in records[0][1] and "not a CA" in records[0][1]


def test_two_independent_chains_only_name_the_chain_with_the_expired_crl(tmp_path, monkeypatch, caplog):
    first = make_ca("first-chain-root")
    second = make_ca("second-chain-root")
    expired = NOW - timedelta(days=1)

    status, published, records = run_job(monkeypatch, tmp_path, caplog, pem(first[0], second[0]), make_crl(first, next_update=expired), make_crl(second))

    assert status == 1 and set(published) == {"ca.pem", "crl.pem"}
    assert [level for level, _ in records] == [logging.ERROR]
    assert "first-chain-root" in records[0][1] and "second-chain-root" not in records[0][1]
