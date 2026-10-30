"""Real certificate and tar fixtures shared by the core UI tests."""

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from tarfile import TarInfo, open as tar_open

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def tar_bytes(files):
    stream = BytesIO()
    with tar_open(fileobj=stream, mode="w:gz") as tar:
        for name, content in files.items():
            content = content.encode() if isinstance(content, str) else content
            info = TarInfo(name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))
    return stream.getvalue()


def certificate_tree(root, domain="example.test"):
    key = ec.generate_private_key(ec.SECP256R1())
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, domain)]))
        .issuer_name(x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "Unit CA")]))
        .public_key(key.public_key())
        .serial_number(42)
        .not_valid_before(datetime(2026, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2027, 1, 1, tzinfo=timezone.utc))
        .sign(key, hashes.SHA256())
    )
    cert_path = Path(root) / "live" / domain / "fullchain.pem"
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    renewal = Path(root) / "renewal" / f"{domain}.conf"
    renewal.parent.mkdir(parents=True, exist_ok=True)
    renewal.write_text(
        "preferred_profile = shortlived\npref_challs = dns-01,http-01\nauthenticator = dns-route53\n"
        "server = https://acme.example/directory\nkey_type = ecdsa\n"
    )
    return certificate
