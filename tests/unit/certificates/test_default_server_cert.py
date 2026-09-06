"""`DEFAULT_SERVER_SSL_CERT` — the default server's own certificate (default-server conception, (a)).

The default server answers every request that matched no configured service: an unknown SNI, a raw
IP, a `Host` nobody serves. Until now the only certificate it could show was the internal
self-signed leaf generated at boot, so an operator who wanted a real certificate there had no
setting to reach for.

Three properties are asserted here because each one is a way the feature could be worse than not
shipping it:

1. **It never writes `/var/lib/bunkerweb/default-server-cert.{pem,key}`.** That pair is the STATIC
   fallback of every service block (`confs/server-http/ssl-certificate-lua.conf:1-2`), not the
   default server's private property. Overwriting it would hand an operator's default-server
   certificate to every service whose own providers stay silent.
2. **It refuses a certificate that also covers a configured service.** The default server is
   reachable with any SNI; a certificate that also covers `www.example.com` lets a client open the
   connection with an unknown SNI, receive that certificate and then reuse the same connection for
   `Host: www.example.com` (HTTP/2 connection coalescing) — a certificate the service never
   authorised, now usable for it. The refusal is the mitigation the PO chose over a request-time
   exclusion, because it is the one an operator can act on.
3. **A refusal never withdraws what is already being served.** Invalid material, a mismatched pair
   or a covered hostname all exit 2 and leave the cache untouched, so the previously served
   certificate stays up rather than the default server dropping to nothing mid-incident.

`custom-cert.py` builds a `Job` at import and ends in `sys_exit`, so the module is loaded through
the same AST filter `test_custom_cert_validation.py` uses.
"""

import ast
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[3]
JOB_PATH = ROOT / "src" / "common" / "core" / "customcert" / "jobs" / "custom-cert.py"


def _load_job_definitions():
    """Keep the module-level imports, assignments and defs; discard the executable body."""
    tree = ast.parse(JOB_PATH.read_text(encoding="utf-8"), filename=str(JOB_PATH))
    tree.body = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign))]

    jobs_module = ModuleType("jobs")
    jobs_module.Job = Mock()
    logger_module = ModuleType("logger")
    logger_module.getLogger = Mock(return_value=Mock())
    module = ModuleType("bw_default_server_cert")
    module.__dict__["__file__"] = str(JOB_PATH)
    with patch.dict(sys.modules, {"jobs": jobs_module, "logger": logger_module}):
        exec(compile(tree, str(JOB_PATH), "exec"), module.__dict__)  # noqa: S102
    return module


CUSTOM_CERT = _load_job_definitions()


def make_pair(common_name: str, sans=(), *, days_valid: int = 365, not_before_offset_days: int = -1):
    """A self-signed leaf and its key, both PEM."""
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + timedelta(days=not_before_offset_days))
        .not_valid_after(now + timedelta(days=days_valid))
    )
    if sans:
        builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(name) for name in sans]), critical=False)
    certificate = builder.sign(key, hashes.SHA256())
    return (
        certificate.public_bytes(Encoding.PEM),
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()),
    )


@pytest.fixture
def job(monkeypatch):
    """A JOB whose cache is empty and whose writes succeed, so only the validation can refuse."""
    fake = Mock()
    fake.cache_hash.return_value = None
    fake.cache_file.return_value = (True, "")
    fake.del_cache.return_value = (True, "")
    monkeypatch.setattr(CUSTOM_CERT, "JOB", fake)
    return fake


@pytest.fixture
def env(monkeypatch):
    """A clean environment: one configured service, www.example.com, and no override set."""
    for name in (
        "SERVER_NAME",
        "MULTISITE",
        "DEFAULT_SERVER_SSL_CERT",
        "DEFAULT_SERVER_SSL_KEY",
        "DEFAULT_SERVER_SSL_CERT_DATA",
        "DEFAULT_SERVER_SSL_KEY_DATA",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SERVER_NAME", "www.example.com")
    return monkeypatch


def set_override(env, cert_pem: bytes, key_pem: bytes):
    env.setenv("DEFAULT_SERVER_SSL_CERT_DATA", cert_pem.decode())
    env.setenv("DEFAULT_SERVER_SSL_KEY_DATA", key_pem.decode())


# --------------------------------------------------------------------------- hostname coverage


@pytest.mark.parametrize(
    ("pattern", "name", "expected"),
    [
        ("example.com", "example.com", True),
        ("EXAMPLE.com.", "example.com", True),  # SNI casing and a trailing dot are both legal
        ("example.com", "other.com", False),
        # RFC 6125 and NGINX agree: a leading wildcard covers exactly one label.
        ("*.example.com", "app.example.com", True),
        ("*.example.com", "deep.app.example.com", False),
        ("*.example.com", "example.com", False),
        ("*.example.com", "app.notexample.com", False),
        # NGINX's ".example.com" is the base plus every sub-domain, at any depth.
        (".example.com", "example.com", True),
        (".example.com", "deep.app.example.com", True),
        (".example.com", "notexample.com", False),
        # NGINX's trailing wildcard.
        ("www.example.*", "www.example.com", True),
        ("www.example.*", "www.example.co.uk", False),
        ("www.example.*", "api.example.com", False),
        # A neighbouring domain must never be considered covered.
        ("example.com", "example.com.evil.test", False),
    ],
)
def test_hostname_coverage_rules(pattern, name, expected):
    assert CUSTOM_CERT.hostname_covered_by(pattern, name) is expected


def test_configured_hostnames_multisite_reads_every_service(env):
    env.setenv("app_SERVER_NAME", "app.example.com www.app.example.com")
    # `one` declares no <id>_SERVER_NAME: a service always answers on its own id.
    assert CUSTOM_CERT.get_configured_hostnames(["app", "one"], True) == {"app.example.com", "www.app.example.com", "one"}


def test_configured_hostnames_single_site_reads_every_vhost(env):
    assert CUSTOM_CERT.get_configured_hostnames(["www.example.com", "example.com"], False) == {"www.example.com", "example.com"}


def test_configured_hostnames_takes_the_resolved_roster_not_the_environment():
    """The job body defaults `SERVER_NAME` to `www.example.com` and this helper used to default it
    to `""`. With the variable unset the coverage set came out EMPTY while the service loop still
    processed `www.example.com`, so a certificate covering that service was accepted. Taking the
    roster the job already resolved is what closes it -- an under-match here is the direction that
    opens the hole."""
    assert CUSTOM_CERT.get_configured_hostnames(["www.example.com"], False) == {"www.example.com"}


# --------------------------------------------------------------------------- the job branch


def test_not_configured_is_a_no_op(job, env):
    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 0
    job.cache_file.assert_not_called()
    job.del_cache.assert_not_called()


def test_clearing_the_setting_drops_the_cache(job, env):
    # Something WAS cached: the operator emptied the settings, so the internal certificate must
    # come back rather than the last override sticking forever.
    job.cache_hash.return_value = "deadbeef"
    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 1
    assert {call.args[0] for call in job.del_cache.call_args_list} == {"default-server-cert.pem", "default-server-key.pem"}


def test_valid_material_is_cached(job, env):
    cert, key = make_pair("unknown.test")
    set_override(env, cert, key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 1

    cached = {call.args[0]: call.args[1] for call in job.cache_file.call_args_list}
    assert cached == {"default-server-cert.pem": cert, "default-server-key.pem": key}
    # PO ruling 3, and the reason this file exists: the static fallback of every service block is
    # never a cache name here.
    assert all("/var/lib/bunkerweb" not in name for name in cached)
    for call in job.cache_file.call_args_list:
        assert call.kwargs["service_id"] == ""  # global entry: bw_jobs_cache.service_id is NULL


def test_unchanged_material_reports_no_change(job, env):
    cert, key = make_pair("unknown.test")
    set_override(env, cert, key)
    # The checksums already on record, and the files present on disk.
    job.cache_hash.side_effect = lambda name, **kw: CUSTOM_CERT.bytes_hash(cert if "cert" in name else key)
    with patch.object(CUSTOM_CERT.Path, "is_file", return_value=True):
        assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 0
    job.cache_file.assert_not_called()


def test_invalid_material_is_refused_without_withdrawing(job, env):
    env.setenv("DEFAULT_SERVER_SSL_CERT_DATA", "not a certificate at all")
    env.setenv("DEFAULT_SERVER_SSL_KEY_DATA", "not a key either")

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 2
    job.cache_file.assert_not_called()
    job.del_cache.assert_not_called()  # what was served stays served (PO ruling 4)


def test_mismatched_pair_is_refused(job, env):
    cert, _ = make_pair("unknown.test")
    _, other_key = make_pair("unrelated.test")
    set_override(env, cert, other_key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 2
    job.cache_file.assert_not_called()


def test_half_configured_is_refused(job, env):
    cert, _ = make_pair("unknown.test")
    env.setenv("DEFAULT_SERVER_SSL_CERT_DATA", cert.decode())

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 2
    job.cache_file.assert_not_called()


def test_expired_material_is_served_with_a_warning(job, env):
    # Same rule as a service certificate: withdrawing one that is being served is worse than
    # serving it expired.
    cert, key = make_pair("unknown.test", days_valid=-1, not_before_offset_days=-30)
    set_override(env, cert, key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 1
    assert job.cache_file.call_count == 2


# --------------------------------------------------------------------------- the coalescence refusal


@pytest.mark.parametrize(
    ("common_name", "sans", "configured"),
    [
        # The exact hostname of a configured service.
        ("www.example.com", (), {"www.example.com"}),
        # Only in the SAN list, which is what a browser actually reads.
        ("unknown.test", ("unknown.test", "www.example.com"), {"www.example.com"}),
        # A wildcard on the certificate covering a configured service.
        ("unknown.test", ("*.example.com",), {"www.example.com"}),
        # A wildcard on the SERVICE covered by the certificate: SERVER_NAME accepts `*.example.com`
        # (settings.json:SERVER_NAME) and NGINX matches it, so the direction has to be tested too.
        ("app.example.com", (), {"*.example.com"}),
        # Case and trailing dot must not be a way around the refusal.
        ("WWW.Example.COM.", (), {"www.example.com"}),
    ],
)
def test_a_certificate_covering_a_service_is_refused(job, env, common_name, sans, configured):
    cert, key = make_pair(common_name, sans)
    set_override(env, cert, key)

    assert CUSTOM_CERT.process_default_server(configured) == 2
    job.cache_file.assert_not_called()
    job.del_cache.assert_not_called()


def test_a_certificate_that_becomes_covering_is_withdrawn(job, env):
    """The ordering hole. An override accepted while nothing matched it stays cached, pushed and
    served; adding a service the certificate covers must not leave it in place, or the refusal
    protects nothing. "The previously served certificate stays" cannot mean "keep serving the one
    you just refused" -- so when the offending material IS what is cached, it is withdrawn, and
    with exit 1 because that is the only code that ships the removal to the instances."""
    cert, key = make_pair("unknown.test", ("*.example.com",))
    set_override(env, cert, key)
    # The cache holds exactly this material: it was accepted before the service existed.
    job.cache_hash.side_effect = lambda name, **kw: CUSTOM_CERT.bytes_hash(cert if "cert" in name else key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 1
    assert {call.args[0] for call in job.del_cache.call_args_list} == {"default-server-cert.pem", "default-server-key.pem"}
    job.cache_file.assert_not_called()


def test_a_different_cached_certificate_is_not_withdrawn(job, env):
    """The case PO ruling 2 is actually written about: the operator supplies a covering certificate
    while a previously vetted one is being served. Refuse the new material, keep the old."""
    cert, key = make_pair("unknown.test", ("*.example.com",))
    set_override(env, cert, key)
    job.cache_hash.return_value = "some other certificate's checksum"

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 2
    job.del_cache.assert_not_called()
    job.cache_file.assert_not_called()


def test_a_neighbouring_name_is_not_refused(job, env):
    # The guard refuses; over-refusing would be a usability bug of its own, so the near miss is
    # pinned as accepted.
    cert, key = make_pair("unknown.test", ("*.notexample.com", "example.com.evil.test"))
    set_override(env, cert, key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}) == 1


def test_the_cache_contract_matches_the_lua_reader():
    """The job writes these two names and `customcert.lua` reads those two paths; the internalstore
    key the job's material ends up under is written in one place and read in another. Nothing else
    in the suite ties the halves together, so a rename on either side would ship silently and the
    default server would quietly keep the internal certificate."""
    lua = (ROOT / "src" / "common" / "core" / "customcert" / "customcert.lua").read_text(encoding="utf-8")
    for cache_name in (CUSTOM_CERT.DEFAULT_SERVER_CERT_CACHE, CUSTOM_CERT.DEFAULT_SERVER_KEY_CACHE):
        assert f"/var/cache/bunkerweb/customcert/{cache_name}" in lua, cache_name
    # Written in init(), read in ssl_certificate_default(): both occurrences, or neither half works.
    assert lua.count('"plugin_customcert_default_server"') == 2


def test_the_service_id_seam_is_a_parameter(job, env):
    """Option (b) turns the default server into a reserved pseudo-service; only this changes."""
    cert, key = make_pair("unknown.test")
    set_override(env, cert, key)

    assert CUSTOM_CERT.process_default_server({"www.example.com"}, service_id="default-server") == 1
    for call in job.cache_file.call_args_list:
        assert call.kwargs["service_id"] == "default-server"
