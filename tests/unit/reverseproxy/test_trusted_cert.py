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

    def execute(settings, present=()):
        for service, name in present:
            cache_file(name, b"stale", service_id=service)
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


def test_invalid_ca_drops_the_crl_and_preserves_failure(execute):
    settings = grpc_settings() | {"GRPC_SSL_TRUSTED_CERTIFICATE_DATA": "invalid"}
    status, files, _ = execute(settings, [("example.com", "grpc-crl.pem"), ("example.com", "grpc-trusted-ca.pem")])
    assert status == 2
    assert set(files) == {"example.com/grpc-client.pem", "example.com/grpc-client.key"}


def test_openssl_crl_validation_failure_drops_cached_crl(execute, monkeypatch):
    import subprocess

    calls = []

    def validate(command, **kwargs):
        calls.append(command[1])
        return SimpleNamespace(returncode=1 if command[1] == "crl" else 0)

    monkeypatch.setattr(subprocess, "run", validate)
    status, files, _ = execute(grpc_settings(), [("example.com", "grpc-crl.pem")])
    assert status == 2
    assert "crl" in calls
    assert "example.com/grpc-crl.pem" not in files


def test_missing_preferred_crl_path_does_not_fall_back_to_data(execute):
    status, files, _ = execute(grpc_settings() | {"GRPC_SSL_CRL": "/missing/crl.pem"})
    assert status == 2
    assert "example.com/grpc-crl.pem" not in files


@pytest.mark.parametrize("prefix,stem", [("REVERSE_PROXY", ""), ("GRPC", "grpc-")])
def test_corrupt_second_ca_is_rejected(execute, prefix, stem):
    status, files, _ = execute(
        {
            f"USE_{prefix}": "yes",
            f"{prefix}_SSL_VERIFY": "yes",
            f"{prefix}_SSL_TRUSTED_CERTIFICATE_DATA": CERT + "-----BEGIN CERTIFICATE-----\ncorrupt\n-----END CERTIFICATE-----\n",
        },
        [("example.com", stem + "trusted-ca.pem")],
    )
    assert status == 2
    assert "example.com/" + stem + "trusted-ca.pem" not in files


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
def test_mismatched_pair_dropped_before_either_half_cached(execute, prefix, names):
    status, files, logger = execute(
        {f"USE_{prefix}": "yes", f"{prefix}_SSL_CLIENT_CERT_DATA": CERT, f"{prefix}_SSL_CLIENT_KEY_DATA": OTHER_KEY}, [("example.com", name) for name in names]
    )
    assert status == 2
    assert not files
    assert any("does not match" in str(call) for call in logger.warning.call_args_list)


def test_valid_ca_bundle_is_cached_whole(execute):
    status, files, _ = execute({"USE_GRPC": "yes", "GRPC_SSL_VERIFY": "yes", "GRPC_SSL_TRUSTED_CERTIFICATE_DATA": CERT + OTHER_CERT})
    assert status == 1
    assert files["example.com/grpc-trusted-ca.pem"] == (CERT + OTHER_CERT).encode()
