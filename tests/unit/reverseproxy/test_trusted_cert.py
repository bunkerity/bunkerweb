"""Execute the certificate job with a local cache and no subprocesses or database."""

from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from hashlib import sha256
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

JOB_PATH = Path(__file__).resolve().parents[3] / "src/common/core/reverseproxy/jobs/trusted-cert.py"


def make_pair():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "test")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return (
        cert.public_bytes(serialization.Encoding.PEM).decode(),
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode(),
    )


CERT, KEY = make_pair()
OTHER_CERT, OTHER_KEY = make_pair()
CRL = "-----BEGIN X509 CRL-----\ncrl\n-----END X509 CRL-----\n"


@pytest.fixture
def execute(monkeypatch, tmp_path):
    import os
    import subprocess

    cache = tmp_path / "cache"
    logger = Mock()
    original_is_file = Path.is_file
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setattr(
        Path,
        "is_file",
        lambda p: (
            original_is_file(cache / str(p).removeprefix("/var/cache/bunkerweb/reverseproxy/"))
            if str(p).startswith("/var/cache/bunkerweb/reverseproxy/")
            else original_is_file(p)
        ),
    )
    monkeypatch.setattr(subprocess, "run", Mock(return_value=SimpleNamespace(returncode=0)))
    monkeypatch.setitem(sys.modules, "logger", SimpleNamespace(getLogger=lambda *_: logger))
    monkeypatch.setitem(sys.modules, "common_utils", SimpleNamespace(bytes_hash=lambda data: sha256(data).hexdigest()))

    def cache_file(name, data, *, service_id, **kwargs):
        target = cache / service_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return True, ""

    def cache_hash(name, *, service_id):
        target = cache / service_id / name
        return sha256(target.read_bytes()).hexdigest() if target.is_file() else None

    job = SimpleNamespace(
        job_path=cache, cache_file=cache_file, cache_hash=cache_hash, del_cache=lambda name, service_id: (cache / service_id / name).unlink(missing_ok=True)
    )
    monkeypatch.setitem(sys.modules, "jobs", SimpleNamespace(Job=lambda *_: job))

    def execute(settings, present=(), service_upstreams=None):
        for service, name in present:
            cache_file(name, b"stale", service_id=service)

        def get_service_upstreams():
            if isinstance(service_upstreams, BaseException):
                raise service_upstreams
            return service_upstreams or {}

        job.db = SimpleNamespace(get_service_upstreams=get_service_upstreams)
        monkeypatch.setattr(os, "environ", {"SERVER_NAME": "example.com", **settings})
        with pytest.raises(SystemExit) as result:
            runpy.run_path(str(JOB_PATH))
        return result.value.code, {str(p.relative_to(cache)): p.read_bytes() for p in cache.rglob("*") if p.is_file()}, logger

    return execute


def grpc_settings():
    return {
        "USE_GRPC": "yes",
        "GRPC_SSL_VERIFY": "yes",
        "GRPC_SSL_TRUSTED_CERTIFICATE_DATA": CERT,
        "GRPC_SSL_CRL_DATA": CRL,
        "GRPC_SSL_CLIENT_CERT_DATA": CERT,
        "GRPC_SSL_CLIENT_KEY_DATA": KEY,
    }


def test_grpc_only_caches_its_own_material_and_is_stable(execute):
    settings = grpc_settings()
    status, files, _ = execute(settings)
    assert status == 1
    assert files == {
        "example.com/grpc-trusted-ca.pem": CERT.encode(),
        "example.com/grpc-crl.pem": CRL.encode(),
        "example.com/grpc-client.pem": CERT.encode(),
        "example.com/grpc-client.key": KEY.encode(),
    }
    assert execute(settings)[0] == 0


def test_grpc_does_not_materialize_reverseproxy_identity(execute):
    status, files, _ = execute({"USE_GRPC": "yes", "REVERSE_PROXY_SSL_CLIENT_CERT_DATA": CERT, "REVERSE_PROXY_SSL_CLIENT_KEY_DATA": KEY})
    assert status == 0
    assert not files


def test_both_plugins_have_independent_client_pairs(execute):
    settings = grpc_settings() | {
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_SSL_CLIENT_CERT_DATA": OTHER_CERT,
        "REVERSE_PROXY_SSL_CLIENT_KEY_DATA": OTHER_KEY,
    }
    status, files, _ = execute(settings)
    assert status == 1
    assert files["example.com/client-cert.pem"] != files["example.com/grpc-client.pem"]
    assert "example.com/client-key.pem" in files


@pytest.mark.parametrize("prefix,cache_name", [("REVERSE_PROXY", "crl.pem"), ("GRPC", "grpc-crl.pem")])
def test_crl_path_wins_over_data_and_removal_drops_cache(execute, tmp_path, prefix, cache_name):
    crl_path = tmp_path / "revoked.pem"
    crl_path.write_text(CRL.replace("crl", "from-file"))
    settings = {
        f"USE_{prefix}": "yes",
        f"{prefix}_SSL_VERIFY": "yes",
        f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": CERT,
        f"{prefix}_SSL_CRL": str(crl_path),
        f"{prefix}_SSL_CRL_DATA": CRL,
    }
    status, files, _ = execute(settings)
    assert status == 1
    assert files[f"example.com/{cache_name}"] == crl_path.read_bytes()
    del settings[f"{prefix}_SSL_CRL"]
    del settings[f"{prefix}_SSL_CRL_DATA"]
    status, files, _ = execute(settings)
    assert status == 1
    assert f"example.com/{cache_name}" not in files


def test_disabled_grpc_drops_all_four_files(execute):
    present = [("example.com", name) for name in ("grpc-trusted-ca.pem", "grpc-crl.pem", "grpc-client.pem", "grpc-client.key")]
    status, files, _ = execute({}, present)
    assert status == 1
    assert not files


def test_grpc_incomplete_pair_drops_both_halves(execute):
    status, files, _ = execute({"USE_GRPC": "yes", "GRPC_SSL_CLIENT_CERT_DATA": CERT}, [("example.com", "grpc-client.pem"), ("example.com", "grpc-client.key")])
    assert status == 2
    assert not files


def test_multisite_uses_service_prefixed_grpc_settings(execute):
    settings = {f"example.com_{key}": value for key, value in grpc_settings().items()}
    settings.update(MULTISITE="yes", SERVER_NAME="example.com other.example.com")
    status, files, _ = execute(settings)
    assert status == 1
    assert len(files) == 4
    assert all(name.startswith("example.com/") for name in files)


def test_later_success_does_not_hide_earlier_failure(execute):
    settings = grpc_settings() | {
        "USE_REVERSE_PROXY": "yes",
        "REVERSE_PROXY_SSL_CLIENT_CERT_DATA": CERT,
        "REVERSE_PROXY_SSL_VERIFY": "yes",
        "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA": CERT,
    }
    assert execute(settings)[0] == 2


@pytest.mark.parametrize("prefix,ca_name,crl_name", [("REVERSE_PROXY", "trusted-ca.pem", "crl.pem"), ("GRPC", "grpc-trusted-ca.pem", "grpc-crl.pem")])
def test_verification_disabled_warns_and_drops_ca_and_crl(execute, prefix, ca_name, crl_name):
    status, files, logger = execute({f"USE_{prefix}": "yes", f"{prefix}_SSL_CRL_DATA": CRL}, [("example.com", ca_name), ("example.com", crl_name)])
    assert status == 1
    assert not files
    assert any("CRL is ignored" in str(call) for call in logger.warning.call_args_list)


def kept_log(logger, name):
    return any("keeping the last good" in str(call) and name in str(call) for call in logger.error.call_args_list)


def test_invalid_ca_keeps_the_last_good_ca_and_crl(execute):
    settings = grpc_settings() | {"GRPC_SSL_TRUSTED_CERTIFICATE_DATA": "invalid"}
    status, files, logger = execute(settings, [("example.com", "grpc-crl.pem"), ("example.com", "grpc-trusted-ca.pem")])
    assert status == 2
    assert files["example.com/grpc-trusted-ca.pem"] == b"stale"
    assert files["example.com/grpc-crl.pem"] == b"stale"
    assert {"example.com/grpc-client.pem", "example.com/grpc-client.key"} <= set(files)
    assert kept_log(logger, "grpc-trusted-ca.pem")


def test_invalid_ca_without_a_cached_copy_caches_nothing(execute):
    status, files, logger = execute(grpc_settings() | {"GRPC_SSL_TRUSTED_CERTIFICATE_DATA": "invalid"})
    assert status == 2
    assert "example.com/grpc-trusted-ca.pem" not in files
    assert "example.com/grpc-crl.pem" not in files
    assert not kept_log(logger, "grpc-trusted-ca.pem")


def test_openssl_crl_validation_failure_keeps_cached_crl(execute, monkeypatch):
    import subprocess

    calls = []

    def validate(command, **kwargs):
        calls.append(command[1])
        return SimpleNamespace(returncode=1 if command[1] == "crl" else 0)

    monkeypatch.setattr(subprocess, "run", validate)
    status, files, logger = execute(grpc_settings(), [("example.com", "grpc-crl.pem")])
    assert status == 2
    assert "crl" in calls
    assert files["example.com/grpc-crl.pem"] == b"stale"
    assert kept_log(logger, "grpc-crl.pem")


def test_missing_preferred_crl_path_does_not_fall_back_to_data(execute):
    status, files, _ = execute(grpc_settings() | {"GRPC_SSL_CRL": "/missing/crl.pem"})
    assert status == 2
    assert "example.com/grpc-crl.pem" not in files


@pytest.mark.parametrize("prefix,stem", [("REVERSE_PROXY", ""), ("GRPC", "grpc-")])
def test_corrupt_second_ca_is_rejected_and_the_last_good_kept(execute, prefix, stem):
    status, files, logger = execute(
        {
            f"USE_{prefix}": "yes",
            f"{prefix}_SSL_VERIFY": "yes",
            f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": CERT + "-----BEGIN CERTIFICATE-----\ncorrupt\n-----END CERTIFICATE-----\n",
        },
        [("example.com", stem + "trusted-ca.pem")],
    )
    assert status == 2
    assert files["example.com/" + stem + "trusted-ca.pem"] == b"stale"
    assert kept_log(logger, stem + "trusted-ca.pem")


@pytest.mark.parametrize(
    "prefix,names",
    [
        ("REVERSE_PROXY", ("trusted-ca.pem", "crl.pem", "client-cert.pem", "client-key.pem")),
        ("GRPC", ("grpc-trusted-ca.pem", "grpc-crl.pem", "grpc-client.pem", "grpc-client.key")),
    ],
)
@pytest.mark.parametrize("artifact", ["TRUSTED_CERTIFICATE", "CRL", "CLIENT_CERT", "CLIENT_KEY"])
@pytest.mark.parametrize("missing", [False, True])
def test_transient_read_keeps_cached_material(execute, monkeypatch, tmp_path, prefix, names, artifact, missing):
    target = tmp_path / "unreadable.pem"
    if not missing:
        target.write_text(CERT)
    read_bytes = Path.read_bytes

    def read(path):
        if path == target:
            raise PermissionError("temporary read failure")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    settings = {k.replace("GRPC", prefix): v for k, v in grpc_settings().items()}
    settings[f"{prefix}_SSL_{artifact}"] = str(target)
    status, files, logger = execute(settings, [("example.com", name) for name in names])
    assert status == 2
    affected = names[:2] if artifact == "TRUSTED_CERTIFICATE" else names[1:2] if artifact == "CRL" else names[2:]
    for name in affected:
        assert files["example.com/" + name] == b"stale"
    assert any("keeping cached" in str(call) for call in logger.error.call_args_list)


@pytest.mark.parametrize("prefix,names", [("REVERSE_PROXY", ("client-cert.pem", "client-key.pem")), ("GRPC", ("grpc-client.pem", "grpc-client.key"))])
def test_mismatched_pair_keeps_the_last_good_pair_whole(execute, prefix, names):
    status, files, logger = execute(
        {f"USE_{prefix}": "yes", f"{prefix}_SSL_CLIENT_CERT_DATA": CERT, f"{prefix}_SSL_CLIENT_KEY_DATA": OTHER_KEY}, [("example.com", name) for name in names]
    )
    assert status == 2
    assert files == {f"example.com/{name}": b"stale" for name in names}
    assert any("does not match" in str(call) for call in logger.warning.call_args_list)
    assert kept_log(logger, names[0])


@pytest.mark.parametrize("prefix,names", [("REVERSE_PROXY", ("client-cert.pem", "client-key.pem")), ("GRPC", ("grpc-client.pem", "grpc-client.key"))])
def test_mismatched_pair_without_a_cached_pair_caches_nothing(execute, prefix, names):
    status, files, _ = execute({f"USE_{prefix}": "yes", f"{prefix}_SSL_CLIENT_CERT_DATA": CERT, f"{prefix}_SSL_CLIENT_KEY_DATA": OTHER_KEY})
    assert status == 2
    assert not files


@pytest.mark.parametrize("prefix,names", [("REVERSE_PROXY", ("client-cert.pem", "client-key.pem")), ("GRPC", ("grpc-client.pem", "grpc-client.key"))])
def test_unparsable_pair_keeps_the_last_good_pair(execute, prefix, names):
    status, files, logger = execute(
        {f"USE_{prefix}": "yes", f"{prefix}_SSL_CLIENT_CERT_DATA": "invalid", f"{prefix}_SSL_CLIENT_KEY_DATA": KEY}, [("example.com", name) for name in names]
    )
    assert status == 2
    assert files == {f"example.com/{name}": b"stale" for name in names}
    assert kept_log(logger, names[0])


@pytest.mark.parametrize("prefix,names", [("REVERSE_PROXY", ("client-cert.pem", "client-key.pem")), ("GRPC", ("grpc-client.pem", "grpc-client.key"))])
def test_pair_is_never_half_replaced(execute, monkeypatch, prefix, names):
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda command, **kwargs: SimpleNamespace(returncode=1 if command[1] == "pkey" else 0))
    status, files, logger = execute(
        {f"USE_{prefix}": "yes", f"{prefix}_SSL_CLIENT_CERT_DATA": OTHER_CERT, f"{prefix}_SSL_CLIENT_KEY_DATA": OTHER_KEY},
        [("example.com", name) for name in names],
    )
    assert status == 2
    assert files == {f"example.com/{name}": b"stale" for name in names}
    assert kept_log(logger, names[0])


@pytest.mark.parametrize("prefix,names", [("REVERSE_PROXY", ("trusted-ca.pem", "crl.pem")), ("GRPC", ("grpc-trusted-ca.pem", "grpc-crl.pem"))])
def test_invalid_crl_keeps_the_last_good_crl_and_ca(execute, prefix, names):
    settings = {k.replace("GRPC", prefix): v for k, v in grpc_settings().items()} | {f"{prefix}_SSL_CRL_DATA": "invalid"}
    status, files, logger = execute(settings, [("example.com", names[1])])
    assert status == 2
    assert files[f"example.com/{names[1]}"] == b"stale"
    assert files[f"example.com/{names[0]}"] == CERT.encode()
    assert kept_log(logger, names[1])


def test_valid_ca_bundle_is_cached_whole(execute):
    status, files, _ = execute({"USE_GRPC": "yes", "GRPC_SSL_VERIFY": "yes", "GRPC_SSL_TRUSTED_CERTIFICATE_DATA": CERT + OTHER_CERT})
    assert status == 1
    assert files["example.com/grpc-trusted-ca.pem"] == (CERT + OTHER_CERT).encode()


POOL_FAMILIES = [("REVERSE_PROXY", "http"), ("REVERSE_PROXY", "stream"), ("GRPC", "grpc")]
POOL_CACHE_NAMES = {
    "REVERSE_PROXY": ("trusted-ca.pem", "crl.pem", "client-cert.pem", "client-key.pem"),
    "GRPC": ("grpc-trusted-ca.pem", "grpc-crl.pem", "grpc-client.pem", "grpc-client.key"),
}


def pool_only_settings(prefix):
    """Full upstream TLS material, with the ``USE_<prefix>`` flag left unset like a pool-only service has it."""
    return {key.replace("GRPC", prefix): value for key, value in grpc_settings().items() if not key.startswith("USE_")}


@pytest.mark.parametrize("prefix,protocol", POOL_FAMILIES)
def test_pool_only_service_gets_its_upstream_tls_material(execute, prefix, protocol):
    status, files, _ = execute(pool_only_settings(prefix), service_upstreams={"example.com": [{"name": "pool", "protocol": protocol}]})
    assert status == 1
    assert set(files) == {f"example.com/{name}" for name in POOL_CACHE_NAMES[prefix]}


@pytest.mark.parametrize("prefix,protocol", POOL_FAMILIES)
def test_pool_only_service_material_is_stable_and_dropped_on_detach(execute, prefix, protocol):
    settings = pool_only_settings(prefix)
    attached = {"example.com": [{"name": "pool", "protocol": protocol}]}
    assert execute(settings, service_upstreams=attached)[0] == 1
    assert execute(settings, service_upstreams=attached)[0] == 0
    status, files, _ = execute(settings)
    assert status == 1
    assert not files


@pytest.mark.parametrize("prefix,protocol", [("REVERSE_PROXY", "grpc"), ("GRPC", "http"), ("GRPC", "stream")])
def test_pool_of_the_other_family_caches_nothing(execute, prefix, protocol):
    status, files, _ = execute(pool_only_settings(prefix), service_upstreams={"example.com": [{"name": "pool", "protocol": protocol}]})
    assert status == 0
    assert not files


@pytest.mark.parametrize("prefix", ["REVERSE_PROXY", "GRPC"])
def test_pool_attached_to_another_service_caches_nothing(execute, prefix):
    status, files, _ = execute(
        pool_only_settings(prefix), service_upstreams={"other.example.com": [{"name": "pool", "protocol": "http" if prefix == "REVERSE_PROXY" else "grpc"}]}
    )
    assert status == 0
    assert not files


@pytest.mark.parametrize("prefix", ["REVERSE_PROXY", "GRPC"])
def test_no_pool_and_no_flag_caches_nothing(execute, prefix):
    status, files, _ = execute(pool_only_settings(prefix))
    assert status == 0
    assert not files


@pytest.mark.parametrize("prefix,protocol", POOL_FAMILIES)
def test_database_error_while_listing_pools_caches_nothing_new(execute, prefix, protocol):
    status, files, _ = execute(pool_only_settings(prefix), service_upstreams=RuntimeError("database is down"))
    assert status == 0
    assert not files


@pytest.mark.parametrize("prefix,protocol", POOL_FAMILIES)
@pytest.mark.parametrize("flag", ["unset", "no"])
def test_database_error_while_listing_pools_keeps_the_cached_material(execute, prefix, protocol, flag):
    """A pool-only service has USE_<prefix> off in the job env: a failed lookup must not read that as 'family off'."""
    settings = pool_only_settings(prefix) | ({f"USE_{prefix}": "no"} if flag == "no" else {})
    present = [("example.com", name) for name in POOL_CACHE_NAMES[prefix]]
    status, files, logger = execute(settings, present, service_upstreams=RuntimeError("database is down"))
    assert status == 0
    assert files == {f"example.com/{name}": b"stale" for name in POOL_CACHE_NAMES[prefix]}
    assert any("keeping the cached upstream TLS material" in str(call) for call in logger.warning.call_args_list)


@pytest.mark.parametrize("prefix", ["REVERSE_PROXY", "GRPC"])
def test_database_error_does_not_keep_material_of_a_service_with_the_family_on(execute, prefix):
    """The lookup failure only protects services the job env cannot vouch for; an enabled family still follows its settings."""
    present = [("example.com", name) for name in POOL_CACHE_NAMES[prefix]]
    status, files, _ = execute({f"USE_{prefix}": "yes"}, present, service_upstreams=RuntimeError("database is down"))
    assert status == 1
    assert not files


@pytest.mark.parametrize("prefix", ["REVERSE_PROXY", "GRPC"])
def test_successful_lookup_without_pool_and_family_off_still_deletes(execute, prefix):
    present = [("example.com", name) for name in POOL_CACHE_NAMES[prefix]]
    status, files, _ = execute(pool_only_settings(prefix), present, service_upstreams={"other.example.com": [{"name": "pool", "protocol": "http"}]})
    assert status == 1
    assert not files


def test_multisite_pool_only_service_is_resolved_per_service(execute):
    settings = {f"example.com_{key}": value for key, value in pool_only_settings("REVERSE_PROXY").items()}
    settings.update(MULTISITE="yes", SERVER_NAME="example.com other.example.com")
    status, files, _ = execute(settings, service_upstreams={"example.com": [{"name": "pool", "protocol": "http"}]})
    assert status == 1
    assert set(files) == {f"example.com/{name}" for name in POOL_CACHE_NAMES["REVERSE_PROXY"]}
