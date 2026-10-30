"""Proxy and gRPC jobs validate PEMs and retain last-good upstream trust."""

from base64 import b64encode
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from _other_jobs_helpers import Cache, load_job

JOBS = [("reverseproxy", "trusted-cert.py", "REVERSE_PROXY"), ("grpc", "grpc-trusted-cert.py", "GRPC")]


@pytest.fixture
def pem_pair():
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "unit-ca")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    crl = x509.CertificateRevocationListBuilder().issuer_name(name).last_update(now).next_update(now + timedelta(days=1)).sign(key, hashes.SHA256())
    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
        crl.public_bytes(serialization.Encoding.PEM),
    )


@pytest.mark.parametrize("plugin, script, prefix", JOBS)
def test_valid_ca_client_pair_crl_publish_once(tmp_path, monkeypatch, pem_pair, plugin, script, prefix):
    cert, key, crl = pem_pair
    cache = Cache(tmp_path / "system/var/cache/bunkerweb" / plugin)
    env = {
        f"USE_{prefix}": "yes",
        f"{prefix}_SSL_VERIFY": "yes",
        f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": cert.decode(),
        f"{prefix}_SSL_CERT_DATA": cert.decode(),
        f"{prefix}_SSL_KEY_DATA": key.decode(),
        f"{prefix}_SSL_CRL_DATA": crl.decode(),
    }
    _, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{script}", cache=cache, env=env)
    assert status == 1
    assert cache.data == {
        ("app.example", "trusted-ca.pem"): cert,
        ("app.example", "client-cert.pem"): cert,
        ("app.example", "client-key.pem"): key,
        ("app.example", "crl.pem"): crl,
    }
    _, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{script}", cache=cache, env=env)
    assert status == 0


@pytest.mark.parametrize("plugin, script, prefix", JOBS)
def test_invalid_ca_keeps_last_good_cache(tmp_path, monkeypatch, plugin, script, prefix):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("trusted-ca.pem", b"last good trust", service_id="app.example")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        f"{plugin}/jobs/{script}",
        cache=cache,
        env={
            f"USE_{prefix}": "yes",
            f"{prefix}_SSL_VERIFY": "yes",
            f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": "not a certificate",
        },
    )
    assert status == 2
    assert cache.data == {("app.example", "trusted-ca.pem"): b"last good trust"}


@pytest.mark.parametrize("plugin, script, prefix", JOBS)
def test_disabling_proxy_purges_material_and_requests_reload(tmp_path, monkeypatch, plugin, script, prefix):
    cache = Cache(tmp_path / "cache")
    for name in ("trusted-ca.pem", "client-cert.pem", "client-key.pem", "crl.pem"):
        cache.cache_file(name, b"old", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{script}", cache=cache)
    assert status == 1
    assert cache.data == {}


@pytest.mark.parametrize("plugin, script, prefix", JOBS)
def test_multisite_changes_and_failures_both_reported(tmp_path, monkeypatch, pem_pair, plugin, script, prefix):
    cache = Cache(tmp_path / "cache")
    cert, _, _ = pem_pair
    _, status = load_job(
        monkeypatch,
        tmp_path,
        f"{plugin}/jobs/{script}",
        cache=cache,
        env={
            "SERVER_NAME": "good.example bad.example",
            "MULTISITE": "yes",
            f"good.example_USE_{prefix}": "yes",
            f"bad.example_USE_{prefix}": "yes",
            f"good.example_{prefix}_SSL_VERIFY": "yes",
            f"bad.example_{prefix}_SSL_VERIFY": "yes",
            f"good.example_{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": cert.decode(),
            f"bad.example_{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": "invalid",
        },
    )
    assert status == 3
    assert cache.data == {("good.example", "trusted-ca.pem"): cert}


@pytest.fixture(params=JOBS, ids=[job[0] for job in JOBS])
def upstream_job(request, tmp_path, monkeypatch):
    plugin, script, _ = request.param
    module, status = load_job(monkeypatch, tmp_path, f"{plugin}/jobs/{script}", env={"SERVER_NAME": ""})
    assert status == 0
    return module


def test_source_priority_and_fallback(upstream_job):
    assert upstream_job.pick_source("file", "/file", "inline") == ("/file", "")
    assert upstream_job.pick_source("file", "", "inline") == (None, "inline")
    assert upstream_job.pick_source("data", "/file", "inline") == (None, "inline")
    assert upstream_job.pick_source("data", "/file", "") == ("/file", "")
    assert upstream_job.pick_source("data", "", "") == (None, "")


def test_pem_base64_and_file_resolution(upstream_job, pem_pair, tmp_path):
    cert, key, crl = pem_pair
    file = tmp_path / "ca.pem"
    file.write_bytes(cert)
    assert upstream_job.resolve_material("invalid", str(file), "cert", "app") == file
    assert upstream_job.resolve_material("", str(tmp_path / "missing"), "cert", "app") is None
    assert upstream_job.resolve_material("", None, "cert", "app") is None
    assert upstream_job.resolve_material(b64encode(cert).decode(), None, "cert", "app") == cert
    assert upstream_job.resolve_material(key.decode(), None, "key", "app") == key
    assert upstream_job.resolve_material(b64encode(crl).decode().rstrip("="), None, "crl", "app") == crl
    assert upstream_job.read_material(upstream_job.Path(file), "ca") == cert
    file.unlink()
    assert "not a valid file" in upstream_job.read_material(upstream_job.Path(file), "ca")


def test_complete_bundle_and_crl_must_parse(upstream_job, pem_pair):
    cert, _, crl = pem_pair
    assert upstream_job.bundle_parses(cert + cert) is True
    assert upstream_job.bundle_parses(cert + b"-----BEGIN CERTIFICATE-----\nbad\n-----END CERTIFICATE-----") is False
    assert upstream_job.crl_parses(crl) is True
    assert upstream_job.crl_parses(b"invalid") is False
    assert upstream_job.normalize_crl(cert.decode(), "app") is None
    assert upstream_job.normalize_crl("$bad base64", "app") is None


def test_missing_or_mismatched_client_pair_never_publishes(upstream_job, pem_pair):
    cert, _, _ = pem_pair
    prefix = upstream_job.PREFIX
    settings = {f"{prefix}_SSL_CERT_DATA": cert.decode()}
    material, error = upstream_job.handle_client_pair("app", settings.get)
    assert material is None
    assert "must both be set" in error
    other_key = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    settings[f"{prefix}_SSL_KEY_DATA"] = other_key.decode()
    material, error = upstream_job.handle_client_pair("app", settings.get)
    assert material is None
    assert "match" in error


def test_crl_without_verification_is_ignored(upstream_job, pem_pair):
    _, _, crl = pem_pair
    settings = {f"{upstream_job.PREFIX}_SSL_CRL_DATA": crl.decode()}
    assert upstream_job.handle_crl("app", lambda k, default="": settings.get(k, default)) == ({}, "")


def test_cache_failure_returns_error_without_reload(upstream_job, monkeypatch, pem_pair):
    monkeypatch.setattr(upstream_job.JOB, "cache_file", Mock(return_value=(False, "disk full")))
    assert upstream_job.cache_material("trusted-ca.pem", pem_pair[0], "app") == (False, "disk full")
