"""The api-server-cert job records the one certificate it replaces (S05A-F5).

Clients pin the API server certificate. An instance keeps serving the one it loaded until its next reload, and a
scheduler or UI restarted after a renewal never saw the old one, so the job stores it next to the new one
(``api-server-cert-previous.pem``), bounded to the single certificate this job generated before.
"""

import pytest
from cryptography import x509

from _other_jobs_helpers import Cache, load_job

JOB = "jobs/jobs/api-server-cert.py"
ENV = {"API_LISTEN_HTTPS": "yes"}


class _JobCache(Cache):
    """The helper cache has no is_cached_file: ``fresh`` says whether the stored pair is still within the month."""

    fresh = False

    def is_cached_file(self, name, expire, **kwargs):
        return self.fresh and ("", name) in self.data


def _run(monkeypatch, tmp_path, cache):
    return load_job(monkeypatch, tmp_path, JOB, cache=cache, env=ENV)[1]


def test_first_generation_records_no_previous_certificate(tmp_path, monkeypatch):
    cache = _JobCache(tmp_path / "system/var/cache/bunkerweb/jobs")

    assert _run(monkeypatch, tmp_path, cache) == 1

    assert ("", "api-server-cert.pem") in cache.data and ("", "api-server-cert.key") in cache.data
    assert ("", "api-server-cert-previous.pem") not in cache.data


def test_a_renewal_records_the_certificate_it_replaces(tmp_path, monkeypatch):
    cache = _JobCache(tmp_path / "system/var/cache/bunkerweb/jobs")
    assert _run(monkeypatch, tmp_path, cache) == 1
    first = cache.data["", "api-server-cert.pem"]

    assert _run(monkeypatch, tmp_path, cache) == 1  # the month is over: not fresh, so it renews

    second = cache.data["", "api-server-cert.pem"]
    assert second != first
    assert cache.data["", "api-server-cert-previous.pem"] == first
    x509.load_pem_x509_certificate(cache.data["", "api-server-cert-previous.pem"])

    # Only one generation back: a third renewal drops the first.
    assert _run(monkeypatch, tmp_path, cache) == 1
    assert cache.data["", "api-server-cert-previous.pem"] == second


def test_a_fresh_certificate_is_left_alone(tmp_path, monkeypatch):
    cache = _JobCache(tmp_path / "system/var/cache/bunkerweb/jobs")
    assert _run(monkeypatch, tmp_path, cache) == 1
    cache.fresh = True
    before = dict(cache.data)

    assert _run(monkeypatch, tmp_path, cache) == 0

    assert cache.data == before


@pytest.mark.parametrize("failure", ["return", "raise", "after_disk_write"])
def test_failed_previous_save_keeps_current_pair(tmp_path, monkeypatch, caplog, failure):
    cache = _JobCache(tmp_path / "system/var/cache/bunkerweb/jobs")
    assert _run(monkeypatch, tmp_path, cache) == 1
    before = dict(cache.data)
    names = ("api-server-cert.pem", "api-server-cert.key")
    # Also preserve any pair still present in OpenSSL's output directory.
    misc = tmp_path / "system/var/cache/bunkerweb/misc"
    misc.mkdir(parents=True, exist_ok=True)
    for name in names:
        (misc / name).write_bytes(before["", name])
    save = cache.cache_file

    def fail_previous(name, data, **kwargs):
        if name == "api-server-cert-previous.pem":
            if failure == "raise":
                raise OSError("previous cache unavailable")
            if failure == "after_disk_write":
                (cache.job_path / name).write_bytes(data)
            return False, "previous cache unavailable"
        return save(name, data, **kwargs)

    monkeypatch.setattr(cache, "cache_file", fail_previous)
    status = _run(monkeypatch, tmp_path, cache)

    assert cache.data == before
    for name in names:
        assert (cache.job_path / name).read_bytes() == before["", name]
        assert (misc / name).read_bytes() == before["", name]
    assert status == 2
    errors = [record for record in caplog.records if record.levelno >= 40]
    assert len(errors) == 1
    assert "previous cache unavailable" in errors[0].message


@pytest.mark.parametrize("stored", [b"junk", b""])
def test_something_that_is_not_a_certificate_is_never_recorded_as_previous(tmp_path, monkeypatch, stored):
    cache = _JobCache(tmp_path / "system/var/cache/bunkerweb/jobs")
    cache.data["", "api-server-cert.pem"] = stored

    assert _run(monkeypatch, tmp_path, cache) == 1

    assert ("", "api-server-cert-previous.pem") not in cache.data
    x509.load_pem_x509_certificate(cache.data["", "api-server-cert.pem"])
