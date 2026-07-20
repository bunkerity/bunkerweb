#!/usr/bin/env python3
"""Certificate parsing and private-key protection shared by the API and DB."""

from base64 import b64decode
from configparser import ConfigParser, Error as ConfigParserError
from datetime import datetime, timedelta, timezone
from io import BytesIO
from json import JSONDecodeError, loads
from os import environ
from os import urandom
from pathlib import PurePosixPath
from tarfile import TarFile, TarInfo, open as tar_open
from typing import Mapping, Optional

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, ed448, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID

KEYS_ENV = "CERTIFICATE_ENCRYPTION_KEYS"
ACTIVE_KEY_ENV = "CERTIFICATE_ENCRYPTION_ACTIVE_KEY"
MAX_CERTBOT_CACHE_SIZE = 100 * 1024 * 1024
MAX_PEM_SIZE = 1024 * 1024


def load_certificate_keyring(values: Optional[Mapping[str, str]] = None) -> tuple[dict[str, bytes], str]:
    """Load and validate the versioned AES-256-GCM keyring."""
    values = values or environ
    raw_keys = values.get(KEYS_ENV, "")
    active = values.get(ACTIVE_KEY_ENV, "").strip()
    if not raw_keys or not active:
        raise ValueError(f"{KEYS_ENV} and {ACTIVE_KEY_ENV} must both be configured")
    try:
        parsed = loads(raw_keys)
    except JSONDecodeError as exc:
        raise ValueError(f"{KEYS_ENV} must be a JSON object") from exc
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError(f"{KEYS_ENV} must be a non-empty JSON object")

    keys: dict[str, bytes] = {}
    for key_id, encoded in parsed.items():
        if not isinstance(key_id, str) or not key_id.strip() or not isinstance(encoded, str):
            raise ValueError(f"{KEYS_ENV} key ids and values must be strings")
        try:
            key = b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError(f"Invalid base64 key for key id {key_id!r}") from exc
        if len(key) != 32:
            raise ValueError(f"Key {key_id!r} must decode to exactly 32 bytes")
        keys[key_id] = key
    if active not in keys:
        raise ValueError(f"Active certificate encryption key {active!r} is not present in {KEYS_ENV}")
    return keys, active


def encrypt_private_key(private_key: bytes, resource_id: str, values: Optional[Mapping[str, str]] = None) -> tuple[bytes, bytes, str]:
    keys, active = load_certificate_keyring(values)
    nonce = urandom(12)
    return AESGCM(keys[active]).encrypt(nonce, private_key, resource_id.encode()), nonce, active


def decrypt_private_key(ciphertext: bytes, nonce: bytes, key_id: str, resource_id: str, values: Optional[Mapping[str, str]] = None) -> bytes:
    keys, _ = load_certificate_keyring(values)
    if key_id not in keys:
        raise ValueError(f"Certificate encryption key {key_id!r} is not configured")
    return AESGCM(keys[key_id]).decrypt(nonce, ciphertext, resource_id.encode())


def _public_key_bytes(key) -> bytes:
    return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def _key_type(key) -> str:
    if isinstance(key, rsa.RSAPublicKey):
        return f"RSA {key.key_size}"
    if isinstance(key, ec.EllipticCurvePublicKey):
        return f"EC {key.curve.name}"
    if isinstance(key, ed25519.Ed25519PublicKey):
        return "Ed25519"
    if isinstance(key, ed448.Ed448PublicKey):
        return "Ed448"
    return key.__class__.__name__


def _name_value(name: x509.Name, oid: x509.ObjectIdentifier) -> str:
    values = name.get_attributes_for_oid(oid)
    return values[0].value if values else name.rfc4514_string()


def parse_certificate(certificate_pem: bytes, private_key_pem: Optional[bytes] = None) -> dict:
    """Parse a PEM chain and optionally verify that its private key matches."""
    certificates = x509.load_pem_x509_certificates(certificate_pem)
    if not certificates:
        raise ValueError("No PEM certificate found")
    leaf = certificates[0]
    if private_key_pem is not None:
        try:
            private_key = serialization.load_pem_private_key(private_key_pem, password=None)
        except TypeError as exc:
            raise ValueError("Encrypted private keys are not supported") from exc
        if _public_key_bytes(private_key.public_key()) != _public_key_bytes(leaf.public_key()):
            raise ValueError("Certificate and private key do not match")

    sans: list[str] = []
    try:
        san = leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        sans.extend(san.get_values_for_type(x509.DNSName))
        sans.extend(str(value) for value in san.get_values_for_type(x509.IPAddress))
    except x509.ExtensionNotFound:
        pass

    chain = b"".join(cert.public_bytes(serialization.Encoding.PEM) for cert in certificates)
    return {
        "certificate_pem": chain.decode("ascii"),
        "leaf_pem": leaf.public_bytes(serialization.Encoding.PEM),
        "common_name": _name_value(leaf.subject, NameOID.COMMON_NAME),
        "sans": sans,
        "issuer": _name_value(leaf.issuer, NameOID.COMMON_NAME),
        "serial_number": str(leaf.serial_number),
        "fingerprint": leaf.fingerprint(hashes.SHA256()).hex(),
        "key_type": _key_type(leaf.public_key()),
        "valid_from": leaf.not_valid_before_utc,
        "valid_to": leaf.not_valid_after_utc,
    }


def certificate_status(valid_from: datetime, valid_to: datetime, *, revoked: bool = False, now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    if valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    if valid_to.tzinfo is None:
        valid_to = valid_to.replace(tzinfo=timezone.utc)
    if revoked:
        return "revoked"
    if now < valid_from:
        return "not_yet_valid"
    if now >= valid_to:
        return "expired"
    if valid_to - now <= timedelta(days=30):
        return "expiring_soon"
    return "valid"


def generate_self_signed(common_name: str, sans: list[str], *, valid_days: int = 365, key_type: str = "ec") -> tuple[bytes, bytes]:
    """Generate a leaf self-signed certificate and unencrypted PKCS#8 key."""
    from ipaddress import ip_address

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048) if key_type == "rsa" else ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    san_values = []
    for value in dict.fromkeys([common_name, *sans]):
        try:
            san_values.append(x509.IPAddress(ip_address(value)))
        except ValueError:
            san_values.append(x509.DNSName(value))
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )
    return (
        certificate.public_bytes(serialization.Encoding.PEM),
        private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
    )


def renew_self_signed(certificate_pem: bytes, private_key_pem: bytes, *, valid_days: int = 365) -> bytes:
    """Renew a self-signed leaf while preserving its subject, key and extensions."""
    old = x509.load_pem_x509_certificates(certificate_pem)[0]
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(old.subject)
        .issuer_name(old.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=valid_days))
    )
    for extension in old.extensions:
        builder = builder.add_extension(extension.value, extension.critical)
    algorithm = None if isinstance(private_key, (ed25519.Ed25519PrivateKey, ed448.Ed448PrivateKey)) else hashes.SHA256()
    return builder.sign(private_key, algorithm).public_bytes(serialization.Encoding.PEM)


def _safe_tar_name(name: str, parent: tuple[str, ...] = ()) -> str:
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError(f"Unsafe absolute path in certificate cache: {name}")
    parts = list(parent)
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"Unsafe path traversal in certificate cache: {name}")
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def _tar_member_bytes(archive: TarFile, members: dict[str, TarInfo], name: str, seen: Optional[set[str]] = None) -> bytes:
    seen = seen or set()
    if name in seen:
        raise ValueError(f"Certificate cache link cycle at {name}")
    seen.add(name)
    member = members.get(name)
    if member is None:
        raise ValueError(f"Certificate cache member not found: {name}")
    if member.issym():
        target = _safe_tar_name(member.linkname, tuple(name.split("/")[:-1]))
        return _tar_member_bytes(archive, members, target, seen)
    if member.islnk():
        target = _safe_tar_name(member.linkname)
        return _tar_member_bytes(archive, members, target, seen)
    if not member.isfile():
        raise ValueError(f"Certificate cache member is not a regular file: {name}")
    if member.size > MAX_PEM_SIZE:
        raise ValueError(f"Certificate cache member exceeds the 1 MiB limit: {name}")
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError(f"Unable to read certificate cache member: {name}")
    data = extracted.read(MAX_PEM_SIZE + 1)
    if len(data) > MAX_PEM_SIZE:
        raise ValueError(f"Certificate cache member exceeds the 1 MiB limit: {name}")
    return data


def read_certbot_cache(data: bytes) -> list[dict]:
    """Read certificate/key pairs from a certbot cache tarball without extraction."""
    if len(data) > MAX_CERTBOT_CACHE_SIZE:
        raise ValueError("Compressed certificate cache exceeds the 100 MiB limit")
    with tar_open(fileobj=BytesIO(data), mode="r:gz") as archive:
        infos = archive.getmembers()
        if len(infos) > 10000:
            raise ValueError("Certificate cache contains too many members")
        members: dict[str, TarInfo] = {}
        for member in infos:
            normalized = _safe_tar_name(member.name)
            if normalized:
                members[normalized] = member

        records = []
        for name in sorted(members):
            parts = name.split("/")
            if len(parts) != 3 or parts[0] != "live" or parts[2] != "fullchain.pem":
                continue
            cert_name = parts[1]
            private_key_name = f"live/{cert_name}/privkey.pem"
            if private_key_name not in members:
                continue
            metadata = {"legacy": True}
            renewal_name = f"renewal/{cert_name}.conf"
            if renewal_name in members:
                config = ConfigParser(interpolation=None)
                try:
                    config.read_string(_tar_member_bytes(archive, members, renewal_name).decode("utf-8"))
                    params = config["renewalparams"] if config.has_section("renewalparams") else {}
                    for key in ("server", "authenticator", "pref_challs", "key_type", "preferred_profile"):
                        if params.get(key):
                            metadata[key] = params.get(key)
                except (ConfigParserError, UnicodeDecodeError, ValueError):
                    pass
            records.append(
                {
                    "name": cert_name,
                    "certificate_pem": _tar_member_bytes(archive, members, name),
                    "private_key_pem": _tar_member_bytes(archive, members, private_key_name),
                    "renewal_metadata": metadata,
                }
            )
        return records
