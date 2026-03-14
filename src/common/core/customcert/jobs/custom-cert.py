#!/usr/bin/env python3

from datetime import datetime, timezone, timedelta
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from tempfile import NamedTemporaryFile
import re
from traceback import format_exc
from typing import Tuple, Union, Optional, Literal

from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_der_private_key,
    load_pem_private_key,
)
from cryptography.x509 import (
    Certificate,
    load_der_x509_certificate,
    load_pem_x509_certificate,
    load_pem_x509_certificates,
)

# PQC (post-quantum) signature OIDs. Extend as more algorithms are standardized.
# RFC 9881: ML-DSA (Dilithium). RFC 9909: SLH-DSA (SPHINCS+).
# Map OID -> directory suffix so multiple PQC algorithms get distinct dirs (e.g. -ML-DSA, -SLH-DSA).
ML_DSA_OIDS = frozenset({
    "2.16.840.1.101.3.4.3.17",  # id-ml-dsa-44
    "2.16.840.1.101.3.4.3.18",  # id-ml-dsa-65
    "2.16.840.1.101.3.4.3.19",  # id-ml-dsa-87
})
SLH_DSA_OIDS = frozenset({
    "2.16.840.1.101.3.4.3.20", "2.16.840.1.101.3.4.3.21", "2.16.840.1.101.3.4.3.22", "2.16.840.1.101.3.4.3.23",
    "2.16.840.1.101.3.4.3.24", "2.16.840.1.101.3.4.3.25", "2.16.840.1.101.3.4.3.26", "2.16.840.1.101.3.4.3.27",
    "2.16.840.1.101.3.4.3.28", "2.16.840.1.101.3.4.3.29", "2.16.840.1.101.3.4.3.30", "2.16.840.1.101.3.4.3.31",
    "2.16.840.1.101.3.4.3.35", "2.16.840.1.101.3.4.3.36", "2.16.840.1.101.3.4.3.37", "2.16.840.1.101.3.4.3.38",
    "2.16.840.1.101.3.4.3.39", "2.16.840.1.101.3.4.3.40", "2.16.840.1.101.3.4.3.41", "2.16.840.1.101.3.4.3.42",
    "2.16.840.1.101.3.4.3.43", "2.16.840.1.101.3.4.3.44", "2.16.840.1.101.3.4.3.45", "2.16.840.1.101.3.4.3.46",
})
PQC_SIGNATURE_OIDS = ML_DSA_OIDS | SLH_DSA_OIDS
PQC_OID_TO_SUFFIX = {oid: "ML-DSA" for oid in ML_DSA_OIDS} | {oid: "SLH-DSA" for oid in SLH_DSA_OIDS}

# All possible cert-dir suffixes (classic + PQC). Used for candidate lookup and cleanup.
CERT_DIR_SUFFIXES = ("ecdsa", "rsa", "ML-DSA", "SLH-DSA", "pqc")

# Wildcard certs stored under this prefix so names do not collide with non-wildcard (e.g. *.example.com -> _wildcard_.example.com).
WILDCARD_CERT_NAME_PREFIX = "_wildcard_."

CUSTOMCERT_CACHE_ROOT = Path(sep, "var", "cache", "bunkerweb", "customcert")

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("CUSTOM-CERT")
JOB = Job(LOGGER, __file__)


def normalize_cert_identifier(server_name: str) -> str:
    """Use _wildcard_. prefix for wildcard server names (e.g. *.example.com -> _wildcard_.example.com)."""
    if server_name.startswith("*."):
        return WILDCARD_CERT_NAME_PREFIX + server_name[2:]
    return server_name


def process_ssl_data(data: str, file_path: Optional[str], data_type: Literal["cert", "key"], server_name: str) -> Union[bytes, Path, None]:
    """Process SSL certificate or key data from file path or direct data (base64 or plain text)"""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{data_type.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                LOGGER.error(f"Invalid certificate format for server {server_name}")
                return None
            if data_type == "key" and b"PRIVATE KEY" not in text_data:
                LOGGER.error(f"Invalid key format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode. We remove whitespaces and pad if needed.
        decoded = b""
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if data_type == "cert" and not decoded.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                raise ValueError("decoded certificate data is not PEM")
            if data_type == "key" and (not decoded.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in decoded):
                raise ValueError("decoded key data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {data_type} data as base64 for server {server_name}, trying as plain text")

            # Fallback: validate and use plaintext data.
            try:
                if data_type == "cert" and not text_data.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
                    LOGGER.error(f"Invalid certificate format for server {server_name}")
                    return None
                elif data_type == "key" and (not text_data.strip().startswith(b"-----BEGIN") or b"PRIVATE KEY" not in text_data):
                    LOGGER.error(f"Invalid key format for server {server_name}")
                    return None
                return text_data
            except BaseException:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while processing {data_type} data for server {server_name}")
                return None
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {data_type} for {server_name}: {e}")
        return None


def get_key_type(key_bytes: bytes, cert_bytes: Optional[bytes] = None) -> str:
    """
    Detect key type from PEM private key (and optionally cert for PQC). Uses cryptography:
    EC -> ecdsa, RSA -> rsa. If the key cannot be loaded (e.g. PQC), infer from cert signature OID;
    PQC certs use algorithm-specific suffixes: ML-DSA, SLH-DSA, or pqc (fallback).
    """
    try:
        key = load_pem_private_key(key_bytes, password=None)
        if isinstance(key, ec.EllipticCurvePrivateKey):
            return "ecdsa"
        if isinstance(key, rsa.RSAPrivateKey):
            return "rsa"
    except Exception:
        pass
    if cert_bytes:
        try:
            cert = load_pem_x509_certificate(cert_bytes)
            oid = cert.signature_algorithm_oid.dotted_string
            if oid in PQC_OID_TO_SUFFIX:
                return PQC_OID_TO_SUFFIX[oid]
            if oid in PQC_SIGNATURE_OIDS:
                return "pqc"
        except Exception:
            pass
    return "rsa"


OPENSSL_MIN_VERSION = (3, 5)


def get_openssl_version() -> Optional[Tuple[int, int, int]]:
    """Run openssl --version (or version) and return (major, minor, patch) or None if unavailable/unparseable."""
    env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    for args in (["openssl", "--version"], ["openssl", "version"]):
        proc = run(args, capture_output=True, stdin=DEVNULL, env=env, check=False)
        if proc.returncode == 0 and proc.stdout:
            break
    else:
        return None
    match = re.search(r"OpenSSL\s+(\d+)\.(\d+)(?:\.(\d+))?", proc.stdout.decode(errors="replace"))
    if not match:
        return None
    try:
        patch = int(match.group(3)) if match.group(3) else 0
        return (int(match.group(1)), int(match.group(2)), patch)
    except (ValueError, IndexError):
        return None


def _verify_cert_key_match_openssl(cert: Certificate, key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Use OpenSSL to compare cert and key public keys (works for PQC with OpenSSL 3.5+).
    Requires OpenSSL 3.5+ before running the key check.
    """
    version = get_openssl_version()
    if version is None:
        msg = "OpenSSL version could not be determined. OpenSSL 3.5 or later is required for PQC certificate verification."
        LOGGER.warning(msg)
        return False, msg
    if (version[0], version[1]) < OPENSSL_MIN_VERSION:
        msg = (
            f"OpenSSL {OPENSSL_MIN_VERSION[0]}.{OPENSSL_MIN_VERSION[1]} or later is required for PQC certificate verification. Found: {version[0]}.{version[1]}.{version[2]}"
        )
        LOGGER.warning(msg)
        return False, msg
    env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
    try:
        cert_pem = cert.public_bytes(Encoding.PEM)
    except Exception as e:
        msg = f"Could not serialize certificate: {e}"
        LOGGER.warning(msg)
        return False, msg
    with NamedTemporaryFile(delete=False, suffix=".pem") as cert_tmp, NamedTemporaryFile(delete=False, suffix=".pem") as key_tmp:
        try:
            cert_tmp.write(cert_pem)
            key_tmp.write(key_bytes)
            cert_tmp.flush()
            key_tmp.flush()
            proc_cert = run(
                ["openssl", "x509", "-noout", "-pubkey", "-in", cert_tmp.name],
                capture_output=True,
                stdin=DEVNULL,
                env=env,
                check=False,
            )
            proc_key = run(
                ["openssl", "pkey", "-pubout", "-in", key_tmp.name],
                capture_output=True,
                stdin=DEVNULL,
                env=env,
                check=False,
            )
        finally:
            Path(cert_tmp.name).unlink(missing_ok=True)
            Path(key_tmp.name).unlink(missing_ok=True)
    if proc_cert.returncode != 0 or proc_key.returncode != 0:
        msg = "Could not verify certificate and key match. For PQC keys, OpenSSL 3.5+ is required."
        LOGGER.warning(msg)
        return False, msg
    if (proc_cert.stdout or b"") != (proc_key.stdout or b""):
        msg = "Certificate does not match the private key."
        LOGGER.warning(msg)
        return False, msg
    return True, None


def verify_cert_key_match(cert: Certificate, key_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify that the certificate's public key matches the private key. Returns (False, error_msg) on
    mismatch, (True, None) on match. Uses cryptography for RSA/EC; OpenSSL for PQC (3.5+).
    """
    try:
        key = load_pem_private_key(key_bytes, password=None)
    except Exception:
        key = None
    if key is not None and isinstance(key, (ec.EllipticCurvePrivateKey, rsa.RSAPrivateKey)):
        try:
            if key.public_key().public_numbers() != cert.public_key().public_numbers():
                msg = "Certificate does not match the private key."
                LOGGER.warning(msg)
                return False, msg
        except Exception as e:
            msg = f"Could not verify certificate and key match: {e}"
            LOGGER.warning(msg)
            return False, msg
        return True, None
    return _verify_cert_key_match_openssl(cert, key_bytes)


def resolve_cert_dir(server_name: str, key_type: str) -> str:
    """
    Return the cache directory name for this server. Existing certificates keep their
    current naming (no suffix); new certificates use server_name-ecdsa, -rsa, -ML-DSA, -SLH-DSA, or -pqc.
    """
    candidates = (server_name,) + tuple(f"{server_name}-{s}" for s in CERT_DIR_SUFFIXES)
    for candidate in candidates:
        if (CUSTOMCERT_CACHE_ROOT / candidate / "cert.pem").is_file():
            return candidate
    return f"{server_name}-{key_type}"


def verify_cert_chain_order(cert_pem_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """
    Verify the certificate chain is in the correct order: leaf cert first, then intermediate(s), then root CA.
    Each cert's issuer must match the next cert's subject. The first cert must not be self-signed (root first).
    """
    try:
        certs = load_pem_x509_certificates(cert_pem_bytes)
    except Exception as e:
        msg = f"Invalid certificate chain: {e}"
        LOGGER.warning(msg)
        return False, msg
    if not certs:
        msg = "No certificate found."
        LOGGER.warning(msg)
        return False, msg
    if len(certs) == 1:
        try:
            issuer_str = certs[0].issuer.rfc4514_string()
        except Exception:
            issuer_str = str(certs[0].issuer)
        LOGGER.warning(
            "Certificate chain contains only the leaf certificate. For best compatibility, include the intermediate(s). "
            "Issuer of leaf cert (download intermediate from your CA): %s",
            issuer_str,
        )
        return True, None
    if certs[0].issuer == certs[0].subject:
        msg = "Certificate chain order is incorrect: leaf certificate must be first (found self-signed root first)."
        LOGGER.warning(msg)
        return False, msg
    for i in range(len(certs) - 1):
        if certs[i].issuer != certs[i + 1].subject:
            msg = (
                "Certificate chain order is incorrect: expected leaf cert, then intermediate(s), then root CA. "
                "Each cert's issuer must match the next cert's subject."
            )
            LOGGER.warning(msg)
            return False, msg
    return True, None


def _strip_pem_comments(data: bytes) -> bytes:
    """Remove lines that are blank or start with # so PEM with comments is accepted (beginning, middle, end)."""
    lines = data.splitlines()
    kept = [line for line in lines if line.strip() and not line.strip().startswith(b"#")]
    return b"\n".join(kept) if kept else data


def _ensure_pem_bytes(data: bytes, kind: str) -> Tuple[Optional[bytes], Optional[str]]:
    """
    Normalize to PEM bytes: accept PEM, base64-encoded PEM, or DER (binary or base64-encoded).
    Strips # comment lines and blank lines so PEM with comments is accepted.
    Returns (bytes, None) on success.
    """
    data = _strip_pem_comments(data)
    if data.strip().startswith(b"-----BEGIN"):
        return data, None
    decoded_b64: Optional[bytes] = None
    try:
        base64_clean = "".join(data.decode(errors="replace").split())
        base64_clean += "=" * (-len(base64_clean) % 4)
        decoded_b64 = b64decode(base64_clean, validate=True)
        if kind == "cert" and decoded_b64.strip().startswith(b"-----BEGIN CERTIFICATE-----"):
            return decoded_b64, None
        if kind == "key" and decoded_b64.strip().startswith(b"-----BEGIN") and b"PRIVATE KEY" in decoded_b64:
            return decoded_b64, None
    except Exception:
        pass
    for raw in (data, decoded_b64):
        if raw is None:
            continue
        try:
            if kind == "cert":
                cert = load_der_x509_certificate(raw)
                return cert.public_bytes(Encoding.PEM), None
            key = load_der_private_key(raw, password=None)
            return key.private_bytes(encoding=Encoding.PEM, format=PrivateFormat.TraditionalOpenSSL, encryption_algorithm=NoEncryption()), None
        except Exception:
            continue
    msg = f"Invalid {kind} data: expected PEM, base64-encoded PEM, or DER."
    LOGGER.warning(msg)
    return None, msg


def verify_cert_matches_service(cert: Certificate, service_name: str) -> Tuple[bool, str]:
    """
    Verify that the certificate's CN and SAN match the service name.
    Supports wildcard matching (e.g., *.example.com matches subdomain.example.com).

    Args:
        cert: Loaded X.509 certificate object
        service_name: The service name/SNI to verify against

    Returns:
        Tuple of (is_match, debug_message)
    """
    try:
        from cryptography.x509 import SubjectAlternativeName, DNSName
        from cryptography.x509.oid import ExtensionOID, NameOID

        cert_domains = set()

        # Extract CN (Common Name) from Subject
        try:
            cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if cn:
                cn_value = str(cn[0].value).lower()
                cert_domains.add(cn_value)
                LOGGER.debug(f"📋 Certificate CN: {cn_value}")
        except Exception as e:
            LOGGER.debug(f"⚠️ Could not extract CN from certificate: {e}")

        # Extract SAN (Subject Alternative Names)
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            if isinstance(san_ext.value, SubjectAlternativeName):
                for name in san_ext.value:
                    if isinstance(name, DNSName):
                        dns_value = str(name.value).lower()
                        cert_domains.add(dns_value)
                LOGGER.debug(f"📋 Certificate SANs: {', '.join(sorted(cert_domains))}")
        except Exception as e:
            LOGGER.debug(f"⚠️ Could not extract SAN from certificate: {e}")

        if not cert_domains:
            msg = f"❌ Certificate has no CN or SAN domains configured"
            return False, msg

        service_lower = service_name.lower()

        # Check exact match
        if service_lower in cert_domains:
            msg = f"✓ Certificate matches service: {service_name} found in {', '.join(sorted(cert_domains))}"
            LOGGER.info(msg)
            return True, msg

        # Check wildcard match
        for cert_domain in cert_domains:
            if cert_domain.startswith("*."):
                # Wildcard certificate (e.g., *.example.com)
                wildcard_base = cert_domain[2:]  # Remove "*."
                if service_lower.endswith("." + wildcard_base) or service_lower == wildcard_base:
                    msg = f"✓ Certificate wildcard matches service: {cert_domain} matches {service_name}"
                    LOGGER.info(msg)
                    return True, msg

        # No match found
        msg = f"❌ Certificate domain mismatch: service={service_name}, certificate domains={', '.join(sorted(cert_domains))}"
        LOGGER.warning(msg)
        return False, msg

    except Exception as e:
        msg = f"⚠️ Error verifying certificate domains: {e}"
        LOGGER.warning(msg)
        return False, msg


def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    try:
        ret = False
        if not cert_file or not key_file:
            msg = "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"
            LOGGER.warning(msg)
            return False, msg

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                msg = f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
                LOGGER.warning(msg)
                return False, msg
            cert_file = cert_file.read_bytes()

        if isinstance(key_file, Path):
            if not key_file.is_file():
                msg = f"Key file {key_file} is not a valid file, ignoring the custom certificate"
                LOGGER.warning(msg)
                return False, msg
            key_file = key_file.read_bytes()

        cert_file, err = _ensure_pem_bytes(cert_file, "cert")
        if err:
            LOGGER.warning(err)
            return False, err
        key_file, err = _ensure_pem_bytes(key_file, "key")
        if err:
            LOGGER.warning(err)
            return False, err

        ok, err = verify_cert_chain_order(cert_file)
        if not ok:
            LOGGER.warning(err)
            return False, err

        cert = load_pem_x509_certificate(cert_file)
        ok, err = verify_cert_key_match(cert, key_file)
        if not ok:
            err = err or "Certificate and key do not match."
            LOGGER.warning(err)
            return False, err

        # Verify that the certificate actually matches the service name
        cert_matches, match_msg = verify_cert_matches_service(cert, first_server)
        if not cert_matches:
            LOGGER.error(f"Certificate validation failed for {first_server}: {match_msg}")
            return False, match_msg

        key_type = get_key_type(key_file, cert_file)
        cert_identifier = normalize_cert_identifier(first_server)
        cert_dir = resolve_cert_dir(cert_identifier, key_type)
        LOGGER.debug(f"📁 Certificate cache directory: {cert_dir}")

        # Validate certificate validity/expiry using cryptography
        now = datetime.now(timezone.utc)
        not_after = cert.not_valid_after_utc
        if getattr(not_after, "tzinfo", None) is None:
            not_after = not_after.replace(tzinfo=timezone.utc)
        ttl_seconds = (not_after - now).total_seconds()
        ttl_days = ttl_seconds / 86400.0
        if ttl_seconds <= 86400:  # 1 day
            msg = "Certificate is invalid or will expire within the next 24 hours."
            LOGGER.critical("Certificate TTL below 1 day (%.2f days). %s", ttl_days, msg)
            return False, msg
        if ttl_seconds < 259200:  # 3 days
            LOGGER.warning("Certificate TTL below 3 days (%.2f days). Consider renewal.", ttl_days)

        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=cert_dir)
        cert_path = CUSTOMCERT_CACHE_ROOT / cert_dir / "cert.pem"
        LOGGER.debug(f"📋 Certificate hash: {cert_hash[:8]}..., Previous hash: {old_hash[:8] if old_hash else 'none'}...")
        if old_hash != cert_hash or not cert_path.is_file():
            ret = True
            LOGGER.info(f"💾 Uploading certificate for {first_server} to {cert_dir}/cert.pem (hash: {cert_hash[:8]}...)")
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=cert_dir, checksum=cert_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"❌ Error while caching custom-cert cert.pem file for {first_server}: {err}")
                return False, err
            LOGGER.info(f"✓ Successfully cached certificate for {first_server}")
        else:
            LOGGER.debug(f"✓ Certificate for {first_server} unchanged, skipping cert upload")

        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=cert_dir)
        key_path = CUSTOMCERT_CACHE_ROOT / cert_dir / "key.pem"
        LOGGER.debug(f"🔑 Key hash: {key_hash[:8]}..., Previous hash: {old_hash[:8] if old_hash else 'none'}...")
        if old_hash != key_hash or not key_path.is_file():
            ret = True
            LOGGER.info(f"💾 Uploading key for {first_server} to {cert_dir}/key.pem (hash: {key_hash[:8]}...)")
            cached, err = JOB.cache_file("key.pem", key_file, service_id=cert_dir, checksum=key_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"❌ Error while caching custom-key key.pem file for {first_server}: {err}")
                return False, err
            LOGGER.info(f"✓ Successfully cached key for {first_server}")
        else:
            LOGGER.debug(f"✓ Key for {first_server} unchanged, skipping key upload")

        return ret, ""
    except BaseException as e:
        LOGGER.error("Unexpected error while checking certificate: %s", e)
        return False, e


status = 0
any_success = False  # at least one server had cert/key valid and checked

try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    skipped_servers = []
    if not multisite:
        all_domains = [all_domains[0]]
        if getenv("USE_CUSTOM_SSL", "no") == "no":
            LOGGER.info("Custom SSL is not enabled, skipping ...")
            skipped_servers = all_domains

    if not skipped_servers:
        for first_server in all_domains:
            if (getenv(f"{first_server}_USE_CUSTOM_SSL", "no") if multisite else getenv("USE_CUSTOM_SSL", "no")) == "no":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using custom SSL certificates, checking ...")

            cert_priority = getenv(f"{first_server}_CUSTOM_SSL_CERT_PRIORITY", "file") if multisite else getenv("CUSTOM_SSL_CERT_PRIORITY", "file")
            cert_file_path = getenv(f"{first_server}_CUSTOM_SSL_CERT", "") if multisite else getenv("CUSTOM_SSL_CERT", "")
            key_file_path = getenv(f"{first_server}_CUSTOM_SSL_KEY", "") if multisite else getenv("CUSTOM_SSL_KEY", "")
            cert_data = getenv(f"{first_server}_CUSTOM_SSL_CERT_DATA", "") if multisite else getenv("CUSTOM_SSL_CERT_DATA", "")
            key_data = getenv(f"{first_server}_CUSTOM_SSL_KEY_DATA", "") if multisite else getenv("CUSTOM_SSL_KEY_DATA", "")

            # Use file or data based on priority
            use_cert_file = cert_priority == "file" and cert_file_path
            use_key_file = cert_priority == "file" and key_file_path

            cert_file = process_ssl_data(cert_data if not use_cert_file else "", cert_file_path if use_cert_file else None, "cert", first_server)

            key_file = process_ssl_data(key_data if not use_key_file else "", key_file_path if use_key_file else None, "key", first_server)

            if not cert_file or not key_file:
                prefix = f"{first_server}_" if multisite else ""
                LOGGER.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) "
                    f"have to be set and valid to use custom certificates for {first_server}. "
                    f"For multisite, use prefixed names (e.g. {prefix}CUSTOM_SSL_CERT_DATA and {prefix}CUSTOM_SSL_KEY_DATA). "
                    "Check the service configuration in the UI or environment."
                )
                skipped_servers.append(first_server)
                status = 2
                continue

            LOGGER.info(f"Checking certificate for {first_server} ...")
            need_reload, err = check_cert(cert_file, key_file, first_server)
            if isinstance(err, BaseException):
                LOGGER.error(f"Exception while checking {first_server}'s certificate, skipping ... \n{err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif err:
                LOGGER.warning(f"Error while checking {first_server}'s certificate : {err}")
                skipped_servers.append(first_server)
                status = 2
                continue
            elif need_reload:
                LOGGER.info(f"Detected change in {first_server}'s certificate")
                status = 1
                any_success = True
                continue

            any_success = True
            LOGGER.info(f"No change in {first_server}'s certificate")

    # Do not fail the whole job if at least one service was processed successfully
    if any_success and status == 2:
        status = 0

    for first_server in skipped_servers:
        cert_id = normalize_cert_identifier(first_server)
        for cert_dir in (cert_id,) + tuple(f"{cert_id}-{s}" for s in CERT_DIR_SUFFIXES):
            JOB.del_cache("cert.pem", service_id=cert_dir)
            JOB.del_cache("key.pem", service_id=cert_dir)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running custom-cert.py :\n{e}")

sys_exit(status)
