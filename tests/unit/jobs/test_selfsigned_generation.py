"""Self-signed jobs generate usable EC certificates and avoid needless renewal."""

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from _other_jobs_helpers import Cache, load_job

JOB = "selfsigned/jobs/self-signed.py"


def test_ec_generation_then_unchanged_check_reuses_pair(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")
    env = {"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_SUBJ": "/CN=app.example/", "SELF_SIGNED_SSL_EXPIRY": "2d"}
    module, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 1
    before = dict(cache.data)
    cert = x509.load_pem_x509_certificate(before["app.example", "cert.pem"])
    key = serialization.load_pem_private_key(before["app.example", "key.pem"], password=None)
    assert cert.public_key().public_numbers() == key.public_key().public_numbers()
    assert cert.subject.rfc4514_string() == "CN=app.example"
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days == 2
    module, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 0
    assert cache.data == before
    assert module.normalize_algorithm_name("ec-prime256v1") == ("ec-prime256v1", "ec-secp256r1")


@pytest.mark.parametrize("change", ["subject", "expiry", "algorithm"])
def test_changed_configuration_regenerates_certificate(tmp_path, monkeypatch, change):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")
    env = {"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_SUBJ": "/CN=app.example/"}
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 1
    old = cache.data["app.example", "cert.pem"]
    setting, value = {
        "subject": ("SELF_SIGNED_SSL_SUBJ", "/CN=changed.example/"),
        "expiry": ("SELF_SIGNED_SSL_EXPIRY", "30d"),
        "algorithm": ("SELF_SIGNED_SSL_ALGORITHM", "ec-secp384r1"),
    }[change]
    env[setting] = value
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)
    assert status == 1
    cert = x509.load_pem_x509_certificate(cache.data["app.example", "cert.pem"])
    assert cache.data["app.example", "cert.pem"] != old
    if change == "subject":
        assert cert.subject.rfc4514_string() == "CN=changed.example"
    elif change == "expiry":
        assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days == 30
    else:
        assert cert.public_key().curve.name == "secp384r1"


def test_bad_expiry_falls_back_to_365_days(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_EXPIRY": "bad"})
    assert status == 1
    cert = x509.load_pem_x509_certificate(cache.data["app.example", "cert.pem"])
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days == 365


def test_multisite_generates_only_enabled_service_and_purges_disabled(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")
    cache.cache_file("cert.pem", b"old", service_id="disabled.example")
    cache.cache_file("key.pem", b"old", service_id="disabled.example")
    _, status = load_job(
        monkeypatch,
        tmp_path,
        JOB,
        cache=cache,
        env={
            "MULTISITE": "yes",
            "SERVER_NAME": "app.example disabled.example",
            "app.example_GENERATE_SELF_SIGNED_SSL": "yes",
            "app.example_SELF_SIGNED_SSL_SUBJ": "/CN=app.example/",
        },
    )
    assert status == 1
    assert set(cache.data) == {("app.example", "cert.pem"), ("app.example", "key.pem")}


def test_empty_inventory_keeps_existing_pair(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "cache")
    cache.cache_file("cert.pem", b"retained", service_id="app.example")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"SERVER_NAME": ""})
    assert status == 0
    assert cache.data == {("app.example", "cert.pem"): b"retained"}


def test_invalid_curve_fails_and_removes_incomplete_pair(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_ALGORITHM": "ec-invalid"})
    assert status == 2
    assert cache.data == {}
