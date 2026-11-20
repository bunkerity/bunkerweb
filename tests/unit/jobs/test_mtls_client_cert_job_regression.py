"""The mTLS client-cert job keeps the last good CA when the configured bundle is rejected by OpenSSL.

A configured but unusable CA must never purge the cached `ca.pem`: dropping it sends every instance
to the placeholder CA, which fails open for `optional` verification and fails closed for everyone
else. Only an operator decision (mTLS off, CA setting removed) purges. This pins the case where the
bundle has well-formed PEM armour but its certificate body is not a certificate, so it passes the
material check and is rejected later, by the OpenSSL pair validation.
"""

import pytest

from _other_jobs_helpers import Cache, load_job

JOB = "mtls/jobs/client-cert.py"
ARMOURED_GARBAGE = "-----BEGIN CERTIFICATE-----\nZm9vYmFyZm9vYmFy\n-----END CERTIFICATE-----\n"


@pytest.mark.parametrize("variant", ["garbage-body", "two-garbage-blocks"])
def test_an_openssl_rejected_ca_keeps_the_cached_ca_and_fails_the_job(tmp_path, monkeypatch, variant):
    cache = Cache(tmp_path / "system/var/cache/bunkerweb/mtls")
    cache.cache_file("ca.pem", b"last good CA", service_id="app.example")
    bundle = ARMOURED_GARBAGE if variant == "garbage-body" else ARMOURED_GARBAGE + ARMOURED_GARBAGE

    _, status = load_job(monkeypatch, tmp_path, JOB, cache=cache, env={"USE_MTLS": "yes", "MTLS_CA_CERTIFICATE_DATA": bundle})

    assert status == 2
    assert (cache.job_path / "app.example/ca.pem").read_bytes() == b"last good CA"
    assert cache.data["app.example", "ca.pem"] == b"last good CA"
    cache.db.upsert_job_caches.assert_not_called()
