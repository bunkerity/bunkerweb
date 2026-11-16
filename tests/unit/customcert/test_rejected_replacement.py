"""Rejected settings retain the served cache pair and central inventory attachment."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import certificate_utils

JOB = Path(__file__).resolve().parents[3] / "src/common/core/customcert/jobs/custom-cert.py"


@pytest.mark.parametrize("reason", ["missing", "mismatch", "exception", "disabled"])
@pytest.mark.parametrize("multisite", [False, True])
def test_rejected_replacement_keeps_served_material(tmp_path, monkeypatch, reason, multisite):
    cert, key = certificate_utils.generate_self_signed("example.com", [])
    _, wrong_key = certificate_utils.generate_self_signed("example.com", [])
    cache = {"cert.pem": cert, "key.pem": key}
    attached = {"example.com"}
    job = Mock()
    job.cache_hash.return_value = None
    job.del_cache.side_effect = lambda name, **kwargs: (cache.pop(name, None) is not None, "")

    def sync(source, services):
        attached.intersection_update(services)
        return ""

    job.db.sync_managed_attachments.side_effect = sync
    prefix = "example.com_" if multisite else ""
    monkeypatch.setenv("SERVER_NAME", "example.com")
    monkeypatch.setenv("MULTISITE", "yes" if multisite else "no")
    monkeypatch.setenv(prefix + "USE_CUSTOM_SSL", "no" if reason == "disabled" else "yes")
    monkeypatch.setenv(prefix + "CUSTOM_SSL_CERT_DATA", "invalid" if reason == "missing" else cert.decode())
    monkeypatch.setenv(prefix + "CUSTOM_SSL_KEY_DATA", wrong_key.decode())
    monkeypatch.setenv(prefix + "CUSTOM_SSL_CERT_PRIORITY", "data")
    for name in ("DEFAULT_SERVER_SSL_CERT", "DEFAULT_SERVER_SSL_KEY", "DEFAULT_SERVER_SSL_CERT_DATA", "DEFAULT_SERVER_SSL_KEY_DATA"):
        monkeypatch.delenv(name, raising=False)
    if reason == "exception":
        monkeypatch.setattr(certificate_utils, "parse_certificate", Mock(side_effect=RuntimeError("validation failed")))
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *args: job))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *args: Mock()))
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(JOB))
    if reason != "disabled":
        assert exited.value.code == 2
    assert cache == ({} if reason == "disabled" else {"cert.pem": cert, "key.pem": key})
    assert attached == (set() if reason == "disabled" else {"example.com"})
    job.db.import_certificate.assert_not_called()
