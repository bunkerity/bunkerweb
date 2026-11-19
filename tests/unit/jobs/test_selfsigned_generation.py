"""Certificate jobs publish complete pairs and report changes across services."""

import subprocess
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

import cache_restore
import test_job_cache_contracts as cache_contracts
from _other_jobs_helpers import Cache, load_job

pem_pair = cache_contracts.pem_pair
runtime = cache_contracts.runtime

JOB = "selfsigned/jobs/self-signed.py"


@pytest.fixture
def cache(tmp_path):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/selfsigned")

    def save_pair(entries):
        for entry in entries:
            cache.data[entry["service_id"], entry["file_name"]] = entry["data"]
        return ""

    cache.db.upsert_job_caches.side_effect = save_pair
    cache.db.get_job_cache_file.side_effect = lambda _job, name, *, service_id: cache.data.get((service_id, name))
    return cache


def test_ec_generation_then_unchanged_check_reuses_pair(tmp_path, monkeypatch, cache):
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
def test_changed_configuration_regenerates_certificate(tmp_path, monkeypatch, cache, change):
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


def test_bad_expiry_falls_back_to_365_days(tmp_path, monkeypatch, cache):
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_EXPIRY": "bad"})
    assert status == 1
    cert = x509.load_pem_x509_certificate(cache.data["app.example", "cert.pem"])
    assert (cert.not_valid_after_utc - cert.not_valid_before_utc).days == 365


def test_multisite_generates_only_enabled_service_and_purges_disabled(tmp_path, monkeypatch, cache):
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


def test_invalid_curve_fails_and_removes_incomplete_pair(tmp_path, monkeypatch, cache):
    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_ALGORITHM": "ec-invalid"})
    assert status == 2
    assert cache.data == {}


@pytest.mark.parametrize("changed,failed,expected", [(True, False, 1), (False, True, 2), (True, True, 3)])
@pytest.mark.parametrize("reverse", [False, True])
def test_multisite_combines_outcomes_and_keeps_pair_on_failure(tmp_path, monkeypatch, cache, changed, failed, expected, reverse):
    names = ("change.example", "fail.example", "stable.example")
    env = {"MULTISITE": "yes", "SERVER_NAME": " ".join(names)}
    for name in names:
        env[f"{name}_GENERATE_SELF_SIGNED_SSL"] = "yes"
    assert load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)[1] == 1
    before = cache.data.copy()
    if changed:
        env["change.example_SELF_SIGNED_SSL_SUBJ"] = "/CN=changed.example/"
    if failed:
        env["fail.example_SELF_SIGNED_SSL_SUBJ"] = "/CN=changed.example/"
    if reverse:
        env["SERVER_NAME"] = " ".join(reversed(names))

    openssl = subprocess.run

    def run(command, **kwargs):
        if failed and command[1] == "req" and "fail.example" in command[command.index("-keyout") + 1]:
            key_file = cache.job_path / command[command.index("-keyout") + 1]
            key_file.write_bytes(b"incomplete output from openssl")
            return subprocess.CompletedProcess(command, 1)
        return openssl(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    assert load_job(monkeypatch, tmp_path, JOB, cache=cache, env=env)[1] == expected
    for name in ("fail.example", "stable.example"):
        for filename in ("cert.pem", "key.pem"):
            assert cache.data[name, filename] == before[name, filename]
            assert (cache.job_path / name / filename).read_bytes() == before[name, filename]
    assert (cache.data["change.example", "cert.pem"] != before["change.example", "cert.pem"]) == changed


def block_key_publication(fault, live, attempted_keys):
    def protect(operation):
        def guarded(source, target):
            source, target = Path(source), Path(target)
            staged = f".{live.name}.cache-staging-"
            if target == live / "key.pem" or (target.name == "key.pem" and target.parent.name.startswith(staged)):
                attempted_keys.append(target)
                raise OSError("injected key write failure")
            if target == live and source.name.startswith(staged):
                attempted_keys.append(target / "key.pem")
                raise OSError("injected certificate pair publication failure")
            return operation(source, target)

        return guarded

    fault.setattr(cache_restore, "replace", protect(cache_restore.replace))
    fault.setattr(Path, "replace", protect(Path.replace))
    fault.setattr(Path, "rename", protect(Path.rename))


@pytest.mark.parametrize("plugin", ["customcert", "selfsigned"])
@pytest.mark.parametrize("existing_pair", [False, True])
@pytest.mark.parametrize("failure", ["database", "filesystem"])
def test_certificate_key_write_failure_preserves_pair(runtime, pem_pair, monkeypatch, plugin, existing_pair, failure):
    selfsigned_job, run_selfsigned = runtime(JOB)
    env = {"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_SUBJ": "/CN=old.example/"}
    if existing_pair:
        assert run_selfsigned(env=env)[1] == 1
        old_pair = {name: selfsigned_job.get_cache(name, service_id="app.example") for name in ("cert.pem", "key.pem")}

    if plugin == "customcert":
        job, run = runtime("customcert/jobs/custom-cert.py")
        if existing_pair:
            for name, data in old_pair.items():
                assert job.cache_file(name, data, service_id="app.example")[0]
        cert, key = pem_pair
        env = {"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT_DATA": cert.decode(), "CUSTOM_SSL_KEY_DATA": key.decode()}
    else:
        job, run = selfsigned_job, run_selfsigned
        env["SELF_SIGNED_SSL_SUBJ"] = "/CN=new.example/"

    store = job.db._blob_store
    attempted_keys = []

    def fail_key_write(session, owner, data):
        if b"PRIVATE KEY-----" in data:
            attempted_keys.append(owner)
            raise OSError("injected key write failure")
        return store(session, owner, data)

    with monkeypatch.context() as fault:
        if failure == "database":
            fault.setattr(job.db, "_blob_store", fail_key_write)
        else:
            block_key_publication(fault, job.job_path / "app.example", attempted_keys)
        _, status = run(env=env)

    assert len(attempted_keys) == 1
    for name in ("cert.pem", "key.pem"):
        if existing_pair:
            assert (job.job_path / "app.example" / name).read_bytes() == old_pair[name]
            assert job.db.get_job_cache_file(job.job_name, name, service_id="app.example") == old_pair[name]
        else:
            assert not (job.job_path / "app.example" / name).exists()
            assert job.db.get_job_cache_file(job.job_name, name, service_id="app.example") is None
    assert status == 2
    assert run(env=env)[1] == 1
    assert run(env=env)[1] == 0


@pytest.mark.parametrize("plugin", ["customcert", "selfsigned"])
@pytest.mark.parametrize("interruption", ["journal", "missing-row", "different-row"])
def test_uncommitted_certificate_pair_is_published_on_retry(runtime, plugin, interruption):
    job, run = runtime(JOB)
    env = {"GENERATE_SELF_SIGNED_SSL": "yes", "SELF_SIGNED_SSL_SUBJ": "/CN=app.example/"}
    service = "app.example"
    names = ("cert.pem", "key.pem")
    assert run(env=env)[1] == 1
    pair = {name: job.db.get_job_cache_file(job.job_name, name, service_id=service) for name in names}

    if plugin == "customcert":
        job, run = runtime("customcert/jobs/custom-cert.py")
        env = {"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT_DATA": pair["cert.pem"].decode(), "CUSTOM_SSL_KEY_DATA": pair["key.pem"].decode()}
    live = job.job_path / service
    for name in names:
        if interruption == "journal":
            assert job.del_cache(name, service_id=service)[0]
        else:
            assert job.cache_file(name, pair[name], service_id=service)[0]
    if interruption == "journal":
        # A process exit between the rename and DB commit leaves the journal beside the live pair.
        stage = cache_restore.StagedDirectory(live)
        for name, data in pair.items():
            cache_restore.write_atomic(stage.path / name, data)
        stage.publish()
        assert stage.journal.is_file()
        assert all(job.db.get_job_cache_file(job.job_name, name, service_id=service) is None for name in names)
    elif interruption == "missing-row":
        assert job.db.delete_job_cache("key.pem", job_name=job.job_name, service_id=service) == ""
    else:
        assert job.db.upsert_job_cache(service, "key.pem", b"another generation", job_name=job.job_name) == ""

    assert run(env=env)[1] == 1
    assert not list(job.job_path.glob(".*.cache-*"))
    for name in names:
        assert (live / name).read_bytes() == job.db.get_job_cache_file(job.job_name, name, service_id=service)
    assert run(env=env)[1] == 0


@pytest.mark.parametrize("plugin", ["selfsigned", "customcert"])
def test_certificate_cache_read_failure_does_not_skip_healthy_service(runtime, pem_pair, monkeypatch, plugin):
    service, sibling = "app.example", "alias.example"
    cert, key = pem_pair
    if plugin == "selfsigned":
        job, run = runtime(JOB)
        settings = {"GENERATE_SELF_SIGNED_SSL": "yes"}
    else:
        job, run = runtime("customcert/jobs/custom-cert.py")
        settings = {"USE_CUSTOM_SSL": "yes", "CUSTOM_SSL_CERT_DATA": cert.decode(), "CUSTOM_SSL_KEY_DATA": key.decode()}
    assert run(env=settings)[1] == 1

    env = {"MULTISITE": "yes", "SERVER_NAME": f"{service} {sibling}"}
    for name in (service, sibling):
        env.update({f"{name}_{setting}": value for setting, value in settings.items()})
    before = {name: (job.job_path / service / name).read_bytes() for name in ("cert.pem", "key.pem")}
    read_cache = job.db.get_job_cache_file
    failed_reads = []

    def fail_first_service_read(job_name, name, *, service_id):
        if service_id == service:
            failed_reads.append(name)
            raise OSError("cache read refused")
        return read_cache(job_name, name, service_id=service_id)

    with monkeypatch.context() as fault:
        fault.setattr(job.db, "get_job_cache_file", fail_first_service_read)
        _, status = run(env=env)

    assert failed_reads == ["cert.pem"]
    assert status == 3
    for name, previous in before.items():
        assert (job.job_path / service / name).read_bytes() == previous == read_cache(job.job_name, name, service_id=service)
        assert (job.job_path / sibling / name).read_bytes() == read_cache(job.job_name, name, service_id=sibling)
    assert run(env=env)[1] == 0


@pytest.mark.parametrize("failed_first", [False, True])
def test_customcert_reload_preserves_invalid_certificate_status(runtime, pem_pair, failed_first):
    job, run = runtime("customcert/jobs/custom-cert.py")
    cert, key = pem_pair
    env = {
        "MULTISITE": "yes",
        "SERVER_NAME": "alias.example app.example" if failed_first else "app.example alias.example",
        "app.example_USE_CUSTOM_SSL": "yes",
        "app.example_CUSTOM_SSL_CERT_DATA": cert.decode(),
        "app.example_CUSTOM_SSL_KEY_DATA": key.decode(),
        "alias.example_USE_CUSTOM_SSL": "yes",
        "alias.example_CUSTOM_SSL_CERT_DATA": "invalid",
        "alias.example_CUSTOM_SSL_KEY_DATA": key.decode(),
    }
    assert run(env=env)[1] == 3
    assert job.db.get_job_cache_file(job.job_name, "cert.pem", service_id="app.example") == cert
    assert job.db.get_job_cache_file(job.job_name, "key.pem", service_id="app.example") == key
