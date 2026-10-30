"""mTLS jobs validate real CA/CRL pairs and publish one recoverable generation."""

from base64 import b64encode
from unittest.mock import Mock

import pytest

from _other_jobs_helpers import Cache, load_job
from common_utils import bytes_hash
import test_upstream_cert_material as _upstream

pem_pair = _upstream.pem_pair

JOB = "mtls/jobs/client-cert.py"


def test_valid_ca_crl_pair_publishes_disk_and_database_together(tmp_path, monkeypatch, pem_pair):
    cert, _, crl = pem_pair
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        env={
            "USE_MTLS": "yes",
            "MTLS_CA_CERTIFICATE_DATA": cert.decode(),
            "MTLS_CRL_DATA": crl.decode(),
        },
    )
    assert status == 1
    assert (cache.job_path / "app.example/ca.pem").read_bytes() == cert
    assert (cache.job_path / "app.example/crl.pem").read_bytes() == crl
    entries = cache.db.upsert_job_caches.call_args.args[0]
    assert {(e["file_name"], e["data"], e["checksum"]) for e in entries} == {("ca.pem", cert, bytes_hash(cert)), ("crl.pem", crl, bytes_hash(crl))}
    assert cache.db.upsert_job_caches.call_args.kwargs["deletions"] == []
    assert all(e["service_id"] == "app.example" for e in entries)
    assert not any(path.name.startswith(".") for path in cache.job_path.iterdir())


def test_database_failure_rolls_back_disk_generation(tmp_path, monkeypatch, pem_pair):
    cert, _, _ = pem_pair
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.cache_file("ca.pem", b"previous CA", service_id="app.example")
    cache.db.upsert_job_caches.return_value = "database unavailable"
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE_DATA": cert.decode()})
    assert status == 2
    assert (cache.job_path / "app.example/ca.pem").read_bytes() == b"previous CA"
    assert not (cache.job_path / "app.example/crl.pem").exists()


@pytest.mark.parametrize("bad_material", ["invalid-ca", "invalid-crl", "bad-signature"])
def test_invalid_pair_keeps_last_good_files(tmp_path, monkeypatch, pem_pair, bad_material):
    cert, _, crl = pem_pair
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.cache_file("ca.pem", b"last CA", service_id="app.example")
    cache.cache_file("crl.pem", b"last CRL", service_id="app.example")
    if bad_material == "bad-signature":
        # Same issuer DN, unrelated public key: both PEMs parse but signature cannot verify.
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        old = x509.load_pem_x509_crl(crl)
        crl = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(old.issuer)
            .last_update(old.last_update_utc)
            .next_update(old.next_update_utc)
            .sign(ec.generate_private_key(ec.SECP256R1()), hashes.SHA256())
            .public_bytes(serialization.Encoding.PEM)
        )
    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        env={
            "USE_MTLS": "yes",
            "MTLS_CA_CERTIFICATE_DATA": "bad" if bad_material == "invalid-ca" else cert.decode(),
            "MTLS_CRL_DATA": "bad" if bad_material == "invalid-crl" else crl.decode(),
        },
    )
    assert status == 2
    assert (cache.job_path / "app.example/ca.pem").read_bytes() == b"last CA"
    assert (cache.job_path / "app.example/crl.pem").read_bytes() == b"last CRL"
    cache.db.upsert_job_caches.assert_not_called()


def test_empty_inventory_never_purges_existing_material(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.cache_file("ca.pem", b"last CA", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"SERVER_NAME": ""})
    assert status == 0
    assert (cache.job_path / "app.example/ca.pem").read_bytes() == b"last CA"
    cache.db.upsert_job_caches.assert_not_called()


def test_disabled_and_deleted_services_are_purged_atomically(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.cache_file("ca.pem", b"old", service_id="app.example")
    cache.cache_file("crl.pem", b"old", service_id="deleted.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache)
    assert status == 1
    assert list(cache.job_path.rglob("*.pem")) == []
    removed = [entry for call in cache.db.upsert_job_caches.call_args_list for entry in call.kwargs["deletions"]]
    assert {(e["service_id"], e["file_name"]) for e in removed} == {
        (service, name) for service in ("app.example", "deleted.example") for name in ("ca.pem", "crl.pem")
    }


def test_failed_initial_restore_refuses_publication(tmp_path, monkeypatch, pem_pair):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.restore_ok = False
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE_DATA": pem_pair[0].decode()})
    assert status == 2
    assert list(cache.job_path.rglob("*.pem")) == []
    cache.db.upsert_job_caches.assert_not_called()


@pytest.fixture
def mtls_job(tmp_path, monkeypatch):
    module, status = load_job(monkeypatch, tmp_path, JOB, env={"SERVER_NAME": ""})
    assert status == 0
    return module


def test_material_resolution_validates_kind_and_base64(mtls_job, pem_pair, tmp_path):
    cert, _, crl = pem_pair
    assert mtls_job.process_pem_data(b64encode(cert).decode().rstrip("="), None, "CA", "app") == cert
    assert mtls_job.process_pem_data(crl.decode(), None, "CRL", "app") == crl
    assert mtls_job.process_pem_data(cert.decode(), None, "CRL", "app") is None
    assert mtls_job.process_pem_data("$bad", None, "CA", "app") is None
    assert mtls_job.process_pem_data("", None, "CA", "app") is None
    source = tmp_path / "ca.pem"
    source.write_bytes(cert)
    assert mtls_job.process_pem_data("bad", str(source), "CA", "app") == source
    assert mtls_job.process_pem_data("", str(tmp_path / "missing"), "CA", "app") is None


def test_pair_requires_every_ca_and_crl_to_parse(mtls_job, pem_pair):
    cert, _, crl = pem_pair
    assert mtls_job.validate_pair(cert + cert, crl + crl, "app") == ""
    assert mtls_job.validate_pair(b"not CA", None, "app") == "Client CA bundle is invalid."
    assert mtls_job.validate_pair(cert, b"not CRL", "app") == "CRL bundle is invalid."
    assert mtls_job.validate_pair(cert, crl + b"garbage", "app") == "CRL bundle is invalid."
    assert mtls_job.validate_pair(cert, b"-----BEGIN X509 CRL-----\nbad\n-----END X509 CRL-----\n", "app") == "CRL is invalid."


def test_unchanged_pair_requires_disk_and_database_agreement(mtls_job, tmp_path, pem_pair):
    cert, _, crl = pem_pair
    service = mtls_job.Path("/var/cache/bunkerweb/mtls/app")
    service.mkdir(parents=True)
    (service / "ca.pem").write_bytes(cert)
    (service / "crl.pem").write_bytes(crl)
    mtls_job.JOB.db.get_job_cache_file.side_effect = lambda _job, name, **_: {
        "data": cert if name == "ca.pem" else crl,
        "checksum": bytes_hash(cert if name == "ca.pem" else crl),
    }
    assert mtls_job.publish_pair(cert, crl, "app") == (False, "")
    mtls_job.JOB.db.upsert_job_caches.assert_not_called()
    (service / "ca.pem").write_bytes(b"tampered")
    assert mtls_job.publish_pair(cert, crl, "app") == (True, "")
    assert (service / "ca.pem").read_bytes() == cert


def test_validation_subprocess_error_is_reported(mtls_job, monkeypatch, pem_pair):
    monkeypatch.setattr(mtls_job, "run", Mock(side_effect=OSError("openssl unavailable")))
    error = mtls_job.validate_pair(pem_pair[0], None, "app")
    assert isinstance(error, OSError)
    assert str(error) == "openssl unavailable"
