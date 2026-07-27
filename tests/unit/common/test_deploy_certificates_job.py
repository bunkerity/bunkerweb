"""deploy-certificates — turning inventory attachments into files an instance can serve.

The job is a script: the worker runs it by importing it, so these tests do the same with its
``Job`` dependency replaced by a fake. That exercises the real control flow — fingerprint
skip, prune, renewal, exit codes — rather than asserting on its source text.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import jobs as jobs_module  # type: ignore
import pytest

ROOT = Path(__file__).resolve().parents[3]
JOB_FILE = ROOT / "src" / "common" / "core" / "certificates" / "jobs" / "deploy-certificates.py"


class _FakeJob:
    """Stands in for utils/jobs.py:Job with an in-memory cache."""

    def __init__(self, db, job_path, cached=None):
        self.db = db
        self.job_path = job_path
        self.cached = dict(cached or {})
        self.written = []
        self.deleted = []

    def get_cache(self, name, *, service_id="", **_kwargs):
        return self.cached.get((service_id, name))

    def cache_file(self, name, content, *, service_id="", **_kwargs):
        self.written.append((service_id, name))
        self.cached[(service_id, name)] = content
        return True, ""

    def del_cache(self, name, *, service_id="", **_kwargs):
        self.deleted.append((service_id, name))
        self.cached.pop((service_id, name), None)
        return True, ""


def _run(monkeypatch, job):
    """Import the job module the way the worker does and return its exit code."""
    monkeypatch.setattr(jobs_module, "Job", lambda _logger, _path: job)
    name = f"bw_deploy_certificates_test_{len(sys.modules)}"
    spec = importlib.util.spec_from_file_location(name, JOB_FILE)
    module = importlib.util.module_from_spec(spec)
    try:
        with pytest.raises(SystemExit) as exit_info:
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return exit_info.value.code


def _certificate(name="app", fingerprint="aa", source="selfsigned"):
    return {
        "resource_id": f"id-{name}",
        "name": name,
        "source": source,
        "fingerprint": fingerprint,
        "certificate_pem": b"-----BEGIN CERTIFICATE-----\n",
        "private_key_pem": b"-----BEGIN PRIVATE KEY-----\n",
    }


def _db(deployable=None, due=()):
    db = Mock()
    db.get_deployable_certificates.return_value = deployable or {}
    db.get_self_signed_certificates_due_for_renewal.return_value = list(due)
    db.renew_self_signed_certificate.return_value = ""
    return db


def test_writes_material_and_requests_a_reload(monkeypatch, tmp_path):
    job = _FakeJob(_db({"app.example.com": _certificate()}), tmp_path)

    assert _run(monkeypatch, job) == 1

    assert job.written == [("app.example.com", "cert.pem"), ("app.example.com", "key.pem"), ("app.example.com", "fingerprint")]


def test_unchanged_fingerprint_is_not_redeployed(monkeypatch, tmp_path):
    """Without this the hourly run would push and reload on every single tick."""
    cached = {("app.example.com", "fingerprint"): b"aa"}
    job = _FakeJob(_db({"app.example.com": _certificate(fingerprint="aa")}), tmp_path, cached=cached)

    assert _run(monkeypatch, job) == 0
    assert job.written == []


def test_rotated_fingerprint_is_redeployed(monkeypatch, tmp_path):
    cached = {("app.example.com", "fingerprint"): b"old"}
    job = _FakeJob(_db({"app.example.com": _certificate(fingerprint="new")}), tmp_path, cached=cached)

    assert _run(monkeypatch, job) == 1
    assert ("app.example.com", "cert.pem") in job.written


def test_detached_service_material_is_pruned(monkeypatch, tmp_path):
    """A detached, deleted or revoked certificate must stop being served."""
    tmp_path.joinpath("gone.example.com").mkdir()
    job = _FakeJob(_db({}), tmp_path)

    assert _run(monkeypatch, job) == 1
    assert job.deleted == [("gone.example.com", "cert.pem"), ("gone.example.com", "key.pem"), ("gone.example.com", "fingerprint")]


def test_still_attached_service_is_not_pruned(monkeypatch, tmp_path):
    tmp_path.joinpath("app.example.com").mkdir()
    cached = {("app.example.com", "fingerprint"): b"aa"}
    job = _FakeJob(_db({"app.example.com": _certificate(fingerprint="aa")}), tmp_path, cached=cached)

    assert _run(monkeypatch, job) == 0
    assert job.deleted == []


def test_due_self_signed_certificates_are_renewed_before_deploying(monkeypatch, tmp_path):
    db = _db({}, due=["id-1", "id-2"])
    job = _FakeJob(db, tmp_path)

    _run(monkeypatch, job)

    assert [call.args[0] for call in db.renew_self_signed_certificate.call_args_list] == ["id-1", "id-2"]


def test_a_failing_renewal_does_not_stop_the_deployment(monkeypatch, tmp_path):
    db = _db({"app.example.com": _certificate()}, due=["id-1"])
    db.renew_self_signed_certificate.return_value = "InvalidTag"
    job = _FakeJob(db, tmp_path)

    assert _run(monkeypatch, job) == 1
    assert ("app.example.com", "cert.pem") in job.written


def test_a_cache_write_failure_reports_an_error(monkeypatch, tmp_path):
    job = _FakeJob(_db({"app.example.com": _certificate()}), tmp_path)
    job.cache_file = lambda *args, **kwargs: (False, "disk full")

    assert _run(monkeypatch, job) == 2
