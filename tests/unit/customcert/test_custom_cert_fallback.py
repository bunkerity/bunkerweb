"""Missing certificate sources clear cache; rejected replacements retain the served pair."""

import os
from unittest.mock import Mock, call

import pytest

import certificate_validation
from test_custom_cert_strip_duplicates import run_job


@pytest.fixture(autouse=True)
def clean_custom_ssl_environment(monkeypatch):
    for name in tuple(os.environ):
        if "CUSTOM_SSL" in name:
            monkeypatch.delenv(name)


def execute(monkeypatch, multisite, **settings):
    environment = {"SERVER_NAME": "app.example", "MULTISITE": "yes" if multisite else "no"}
    prefix = "app.example_" if multisite else ""
    environment.update({prefix + name: value for name, value in {"USE_CUSTOM_SSL": "yes", **settings}.items()})
    return run_job(monkeypatch, **environment)


@pytest.mark.parametrize("multisite", [False, True])
@pytest.mark.parametrize("priority", ["file", "data"])
@pytest.mark.parametrize("source", [None, "CERT", "KEY", "CERT_DATA", "KEY_DATA"])
def test_missing_certificate_source_clears_both_cached_halves(monkeypatch, multisite, priority, source):
    settings = {"CUSTOM_SSL_CERT_PRIORITY": priority}
    if source:
        settings[f"CUSTOM_SSL_{source}"] = "configured-but-invalid"
    job, status = execute(monkeypatch, multisite, **settings)

    assert status == 2
    assert job.del_cache.call_args_list == [call("cert.pem", service_id="app.example"), call("key.pem", service_id="app.example")]
    job.test_logger.warning.assert_called_once()
    job.cache_file.assert_not_called()


@pytest.mark.parametrize("multisite", [False, True])
@pytest.mark.parametrize("source", ["missing-file", "bad-file", "bad-data", "malformed-pem", "ignored-file"])
def test_invalid_configured_sources_keep_cached_pair(monkeypatch, tmp_path, multisite, source):
    if source in ("missing-file", "bad-file", "ignored-file"):
        cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
        if source == "bad-file":
            cert.write_text("invalid certificate")
            key.write_text("invalid key")
        settings = {"CUSTOM_SSL_CERT": str(cert), "CUSTOM_SSL_KEY": str(key)}
        if source == "ignored-file":
            settings["CUSTOM_SSL_CERT_PRIORITY"] = "data"
    else:
        settings = {"CUSTOM_SSL_CERT_DATA": "invalid certificate", "CUSTOM_SSL_KEY_DATA": "invalid key"}
        if source == "malformed-pem":
            settings = {
                "CUSTOM_SSL_CERT_DATA": "-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----",
                "CUSTOM_SSL_KEY_DATA": "-----BEGIN PRIVATE KEY-----\ninvalid\n-----END PRIVATE KEY-----",
            }
    job, status = execute(monkeypatch, multisite, **settings)

    assert status == 2
    job.del_cache.assert_not_called()
    job.cache_file.assert_not_called()


@pytest.mark.parametrize("multisite", [False, True])
@pytest.mark.parametrize("failure", ["error", "exception"])
def test_check_cert_failure_keeps_cached_pair(monkeypatch, tmp_path, multisite, failure):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("certificate input")
    key.write_text("key input")
    validator = Mock(return_value={"ok": False, "error": "validation refused"})
    if failure == "exception":
        validator.side_effect = RuntimeError("validation failed")
    monkeypatch.setattr(certificate_validation, "validate_certificate_pair", validator)

    job, status = execute(monkeypatch, multisite, CUSTOM_SSL_CERT=str(cert), CUSTOM_SSL_KEY=str(key))

    validator.assert_called_once_with(b"certificate input", b"key input")
    assert status == 2
    job.del_cache.assert_not_called()
    job.cache_file.assert_not_called()
    if failure == "exception":
        assert "Exception while checking" in job.test_logger.error.call_args.args[0]
    else:
        assert "Error while checking" in job.test_logger.warning.call_args.args[0]
