"""Classifier and feature probe for sensitive job-cache entries.

The convention: a stored basename that is exactly `secret` or ends with `.secret`, with at most one
trailing `.tgz`, case-sensitive. Core entries that predate it are mapped by (plugin id, job name,
existing stored name) so nothing is renamed on disk. A name such as `key.pem` is sensitive only for
the plugins that store a private key under it.
"""

import pytest

import common_utils  # type: ignore
from common_utils import SENSITIVE_JOB_CACHE_SUPPORTED, is_sensitive_job_cache_file  # type: ignore

LE_ARCHIVE = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
FAILOVER_ARCHIVE = "folder:/var/tmp/bunkerweb/failover.tgz"


def test_probe_is_published():
    assert SENSITIVE_JOB_CACHE_SUPPORTED is True
    assert common_utils.SENSITIVE_JOB_CACHE_SUPPORTED is True


@pytest.mark.parametrize(
    "name,expected",
    [
        ("secret", True),
        ("x.secret", True),
        ("token.secret", True),
        ("secret.tgz", True),
        ("x.secret.tgz", True),
        ("folder:/var/cache/bunkerweb/example/state.secret.tgz", True),
        ("folder:/var/cache/bunkerweb/example/secret.tgz", True),
        ("SECRET", False),
        ("token.SECRET", False),
        ("secret/ordinary.tgz", False),
        ("folder:/var/cache/bunkerweb/example/secret/ordinary.tgz", False),
        ("secret.txt", False),
        ("token.secret.bak", False),
        ("token.secret.tgz.bak", False),
        ("secret.tgz.tgz", False),
        ("backup.json", False),
        ("key.pem", False),
        ("crowdsec.conf", False),
        (LE_ARCHIVE, False),
        ("", False),
    ],
)
def test_convention_without_context(name, expected):
    assert is_sensitive_job_cache_file(name) is expected


@pytest.mark.parametrize(
    "name,plugin,job",
    [
        ("key.pem", "customcert", "custom-cert"),
        ("key.pem", "selfsigned", "self-signed"),
        ("default-server-cert.key", "misc", "default-server-cert"),
        ("api-server-cert.key", "jobs", "api-server-cert"),
        ("credentials_0123456789ab.ini", "letsencrypt", "certbot-new"),
        ("credentials_0123456789ab.json", "letsencrypt", "certbot-new"),
        ("credentials_0123456789ab.env", "letsencrypt", "certbot-new"),
        (LE_ARCHIVE, "letsencrypt", "certbot-new"),
        (LE_ARCHIVE, "letsencrypt", "certbot-renew"),
        ("crowdsec.conf", "crowdsec", "crowdsec-conf"),
        (FAILOVER_ARCHIVE, "jobs", "failover-backup"),
        ("any-other-name.bin", "jobs", "failover-backup"),
        ("client-key.pem", "reverseproxy", "trusted-cert"),
        ("client-key.pem", "grpc", "grpc-trusted-cert"),
        ("Client-Key.PEM", "ReverseProxy", "Trusted-Cert"),
        ("CLIENT-KEY.PEM", "GRPC", "GRPC-Trusted-Cert"),
        ("Key.PEM", "CustomCert", "Custom-Cert"),
        (FAILOVER_ARCHIVE.upper(), "Jobs", "Failover-Backup"),
    ],
)
def test_mapped_core_entries_are_sensitive_in_their_plugin(name, plugin, job):
    assert is_sensitive_job_cache_file(name, plugin_id=plugin, job_name=job) is True


@pytest.mark.parametrize(
    "name,plugin,job",
    [
        ("key.pem", "other", "other-job"),
        ("key.pem", "customcert", "self-signed"),
        ("key.pem", "", ""),
        ("cert.pem", "customcert", "custom-cert"),
        ("cert.pem", "selfsigned", "self-signed"),
        ("default-server-cert.pem", "misc", "default-server-cert"),
        ("api-server-cert.pem", "jobs", "api-server-cert"),
        ("default-server-cert.key", "jobs", "api-server-cert"),
        ("backup.json", "backup", "backup-data"),
        ("credentials_0123456789ab.ini", "other", "certbot-new"),
        ("credentials_0123456789ab.ini", "letsencrypt", "certbot-renew"),
        ("credentials_xyz.ini", "letsencrypt", "certbot-new"),
        ("credentials_0123456789ab.ini.bak", "letsencrypt", "certbot-new"),
        (LE_ARCHIVE, "other", "other-job"),
        ("folder:/var/cache/bunkerweb/letsencrypt/other.tgz", "letsencrypt", "certbot-renew"),
        ("crowdsec.conf", "other", "crowdsec-conf"),
        ("crowdsec.conf.bak", "crowdsec", "crowdsec-conf"),
        (FAILOVER_ARCHIVE, "other", "failover-backup"),
        (FAILOVER_ARCHIVE, "jobs", "other-job"),
        ("latest_release.json", "jobs", "update-check"),
        ("client-cert.pem", "reverseproxy", "trusted-cert"),
        ("trusted-ca.pem", "reverseproxy", "trusted-cert"),
        ("crl.pem", "reverseproxy", "trusted-cert"),
        ("client-cert.pem", "grpc", "grpc-trusted-cert"),
        ("trusted-ca.pem", "grpc", "grpc-trusted-cert"),
        ("crl.pem", "grpc", "grpc-trusted-cert"),
        ("client-key.pem", "other", "trusted-cert"),
        ("client-key.pem", "reverseproxy", "grpc-trusted-cert"),
        ("client-key.pem", "grpc", "trusted-cert"),
        ("client-key.pem.bak", "reverseproxy", "trusted-cert"),
    ],
)
def test_mapping_is_plugin_scoped_and_exact(name, plugin, job):
    assert is_sensitive_job_cache_file(name, plugin_id=plugin, job_name=job) is False


def test_convention_still_applies_with_a_plugin_context():
    assert is_sensitive_job_cache_file("secret", plugin_id="anything", job_name="anything") is True
