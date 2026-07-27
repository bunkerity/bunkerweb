"""Internal certificates are local, persistent, and required before rendering."""

import os
import stat
import subprocess
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parents[3]
UTILS = ROOT / "src" / "common" / "helpers" / "utils.sh"


def _generate(cert: Path, key: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(UTILS=str(UTILS), CERT=str(cert), KEY=str(key))
    return subprocess.run(
        ["bash", "-c", 'source "$UTILS"; _generate_self_signed_cert "$CERT" "$KEY" TEST'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_valid_pair(cert_path: Path, key_path: Path) -> None:
    certificate = x509.load_pem_x509_certificate(cert_path.read_bytes())
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    assert certificate.public_key().public_numbers() == private_key.public_key().public_numbers()
    assert isinstance(private_key, ec.EllipticCurvePrivateKey)
    assert private_key.curve.name == "secp384r1"
    assert isinstance(certificate.signature_hash_algorithm, hashes.SHA512)
    assert certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "www.example.org"
    assert certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName) == ["www.example.org"]

    constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints)
    assert constraints.critical
    assert not constraints.value.ca

    usage = certificate.extensions.get_extension_for_class(x509.KeyUsage)
    assert usage.critical
    assert usage.value.digital_signature
    assert usage.value.key_encipherment
    assert usage.value.key_agreement
    assert certificate.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH])
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_generates_and_reuses_secure_certificate(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "cert.key"

    result = _generate(cert, key)
    assert result.returncode == 0, result.stderr or result.stdout
    _assert_valid_pair(cert, key)

    original = (cert.read_bytes(), key.read_bytes())
    key.chmod(0o644)
    result = _generate(cert, key)
    assert result.returncode == 0, result.stderr or result.stdout
    assert (cert.read_bytes(), key.read_bytes()) == original
    assert stat.S_IMODE(key.stat().st_mode) == 0o600


def test_regenerates_corrupt_or_mismatched_pair(tmp_path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "cert.key"
    assert _generate(cert, key).returncode == 0

    first_certificate = cert.read_bytes()
    mismatched_key = ec.generate_private_key(ec.SECP384R1())
    key.write_bytes(
        mismatched_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    result = _generate(cert, key)
    assert result.returncode == 0, result.stderr or result.stdout
    assert cert.read_bytes() != first_certificate
    _assert_valid_pair(cert, key)

    cert.write_text("not a certificate")
    result = _generate(cert, key)
    assert result.returncode == 0, result.stderr or result.stdout
    _assert_valid_pair(cert, key)

    subprocess.run(
        [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-key",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-sha512",
            "-subj",
            "/CN=www.example.org",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    expiring_pair = (cert.read_bytes(), key.read_bytes())
    result = _generate(cert, key)
    assert result.returncode == 0, result.stderr or result.stdout
    assert (cert.read_bytes(), key.read_bytes()) != expiring_pair
    _assert_valid_pair(cert, key)


def test_generation_failure_is_reported(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked")

    result = _generate(blocker / "cert.pem", blocker / "cert.key")

    assert result.returncode != 0
    assert not (blocker / "cert.pem").exists()
    assert not (blocker / "cert.key").exists()


def test_startup_is_fail_closed_and_tls_rendering_is_unconditional():
    entrypoint = (ROOT / "src" / "bw" / "entrypoint.sh").read_text()
    linux_start = (ROOT / "src" / "linux" / "scripts" / "start.sh").read_text()
    api_template = (ROOT / "src" / "common" / "confs" / "api.conf").read_text()

    assert entrypoint.index("generate_default_server_cert") < entrypoint.index("gen/main.py")
    assert entrypoint.index("generate_api_server_cert") < entrypoint.index("gen/main.py")
    assert "if ! generate_default_server_cert; then" in entrypoint
    assert "if ! generate_api_server_cert; then" in entrypoint
    assert "Continuing without a freshly generated" not in entrypoint

    generation = linux_start.index("generate_default_server_cert && generate_api_server_cert")
    render = linux_start.index("gen/main.py", generation)
    assert linux_start.rfind("if ! run_as_nginx", 0, generation) != -1
    assert generation < render
    assert "exit 1" in linux_start[generation:render]
    assert "Failed to provision internal certificates" in linux_start

    assert 'API_LISTEN_HTTPS == "yes"' in api_template
    assert "ssl_protocols TLSv1.3;" in api_template
    assert "ssl_certificate /var/lib/bunkerweb/api-server-cert.pem;" in api_template
    assert "ssl_certificate_key /var/lib/bunkerweb/api-server-cert.key;" in api_template
    assert "os.path.isfile" not in api_template
    assert "fallback to HTTP" not in api_template
