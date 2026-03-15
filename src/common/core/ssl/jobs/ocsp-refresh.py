#!/usr/bin/env python3

import argparse
import fcntl
import hashlib
import io
import os
import re
import shutil
import ssl
import subprocess
import sys as _sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp as x509_ocsp
from cryptography.x509 import AuthorityInformationAccess, SubjectAlternativeName
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID

# Add BunkerWeb Python deps (Job, logger, Database) to path
# Add current script's parent directory to path for local imports
sys_path.append(str(Path(__file__).resolve().parent.parent.parent))
for deps_path in [
    Path(os.sep, "usr", "share", "bunkerweb", *paths).as_posix()
    for paths in (("deps", "python"), ("utils",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Gracefully handle import failures
try:
    from jobs import Job  # type: ignore
except ImportError as e:
    print(f"FATAL: Could not import Job: {e}", file=_sys.stderr)
    _sys.exit(1)

try:
    from logger import getLogger  # type: ignore
except ImportError as e:
    print(f"FATAL: Could not import logger: {e}", file=_sys.stderr)
    _sys.exit(1)

# Optional: Database support for OCSP storage
try:
    from Database import Database  # type: ignore
except ImportError as e:
    print(f"WARNING: Database not available: {e}", file=_sys.stderr)
    Database = None  # type: ignore

# Dedicated logger for OCSP refresh job.
# Log level is controlled by the standard BunkerWeb LOG_LEVEL / CUSTOM_LOG_LEVEL env vars.
try:
    LOG = getLogger("SSL.OCSP-REFRESH")
except Exception as e:
    print(f"FATAL: Could not initialize logger: {e}", file=_sys.stderr)
    _sys.exit(1)

status = 0

# Use scheduler-managed cache directory (automatically synced from database on restart)
CONFIGS_SSL_BASE = Path(os.sep, "var", "cache", "bunkerweb", "ssl")
MIN_TTL = 4500  # 75 minutes: aggressivly refresh/cleanup if TTL is below this


def _sanitize_filename(name: str) -> str:
    """
    Replace characters that are invalid in filenames or could cause issues.
    Specifically replaces '*' with '_wildcard_' for wildcard certificates.
    """
    return name.replace("*", "_wildcard_")


def _acquire_cert_lock(cert_name: str, timeout: int = 300, stale_threshold: int = 600) -> Optional[int]:
    """
    Acquire a file-based lock for a specific certificate to prevent race conditions
    when multiple scheduler instances fetch OCSP responses concurrently.

    Lock files are stored in /tmp/bunkerweb/ and use timestamp-based staleness detection.
    If a lock file hasn't been updated in stale_threshold seconds, it's considered stale
    (indicating the previous process crashed or is hung).

    Args:
        cert_name: Certificate identifier
        timeout: Maximum seconds to wait for lock acquisition (default 300 = 5 minutes)
        stale_threshold: Lock file age (seconds) to consider it stale (default 600 = 10 minutes)

    Returns:
        File descriptor on success, None if lock unavailable or timed out
    """
    lock_dir = Path(os.sep, "tmp", "bunkerweb")
    try:
        lock_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
    except Exception:
        return None

    sanitized_name = _sanitize_filename(cert_name)
    lock_file = lock_dir / f"ocsp-{sanitized_name}.lock"
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check if existing lock file is stale (crashed process)
        try:
            if lock_file.exists():
                mtime = lock_file.stat().st_mtime
                age = time.time() - mtime
                if age > stale_threshold:
                    LOG.warning(
                        "⚠️ OCSP detected stale lock for %s (age %.0fs > threshold %ds). "
                        "Previous process may have crashed. Removing stale lock.",
                        cert_name, age, stale_threshold
                    )
                    try:
                        lock_file.unlink()
                    except Exception:
                        pass  # If we can't delete, we'll wait more
        except Exception:
            pass

        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_WRONLY, 0o600)
            # Try non-blocking lock acquisition (LOCK_NB)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired successfully—write timestamp to detect stale locks
                try:
                    os.write(fd, str(int(time.time())).encode())
                except Exception:
                    pass  # Non-critical timestamp write
                return fd
            except BlockingIOError:
                # Lock held by another process, close fd and retry after brief delay
                os.close(fd)
                time.sleep(0.5)
                continue
        except Exception as e:
            LOG.debug("⚠️ OCSP lock acquisition attempt failed for %s: %s", cert_name, e)
            time.sleep(0.5)

    # Timeout reached: log warning and proceed without lock
    LOG.warning(
        "⚠️ OCSP could not acquire lock for %s after %ds. "
        "If concurrent OCSP fetches happen, cryptographic verification protects data integrity. "
        "Consider increasing scheduler interval or timeout if jobs consistently exceed %ds.",
        cert_name, timeout, timeout
    )
    return None


def _release_cert_lock(fd: Optional[int], cert_name: str = "undefined") -> None:
    """
    Release and delete a certificate-specific lock file.
    """
    if fd is None:
        return
    
    sanitized_name = _sanitize_filename(cert_name)
    lock_file = Path(os.sep, "tmp", "bunkerweb", f"ocsp-{sanitized_name}.lock")
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        if lock_file.exists():
            lock_file.unlink()
    except Exception:
        pass


def _refresh_cert_lock(fd: Optional[int], cert_name: str) -> None:
    """
    Refresh the lock file timestamp to prove the process is still alive.
    Call this periodically while holding a lock during long-running operations.
    Prevents stale lock detection from triggering on jobs that legitimately take >30 seconds.

    Args:
        fd: File descriptor from _acquire_cert_lock
        cert_name: Certificate identifier (for logging only)
    """
    if fd is None:
        return

    try:
        # Seek to start and truncate to update modification time and content
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        timestamp = str(int(time.time())).encode()
        os.write(fd, timestamp)
        os.fsync(fd)  # Ensure write is persisted
        LOG.debug("🔒 OCSP refreshed lock timestamp for %s", cert_name)
    except Exception as e:
        LOG.debug("⚠️ OCSP could not refresh lock timestamp for %s: %s", cert_name, e)


def is_safe_url(url: str) -> bool:
    """
    Validate that a URL is safe to fetch (HTTP/HTTPS only, no internal/private IPs).
    Prevents Server-Side Request Forgery (SSRF) when fetching OCSP responses or issuer certs
    from URLs embedded in untrusted certificates.

    Security note: Even if DNS rebinding occurs, the OCSP response is cryptographically
    verified against the issuer's public key (see fetch_ocsp_response). An attacker cannot
    forge a valid OCSP response without the issuer's private key.
    """
    import socket
    import ipaddress

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            LOG.warning("⚠️ SSRF protection: blocked URL with disallowed scheme: %s", url)
            return False

        hostname = parsed.hostname
        if not hostname:
            LOG.warning("⚠️ SSRF protection: blocked URL with no hostname: %s", url)
            return False

        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            LOG.warning("⚠️ SSRF protection: DNS resolution failed for %s", hostname)
            return False

        for info in addr_info:
            ip_str = info[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
                LOG.warning("⚠️ SSRF protection: blocked request to %s (resolves to internal IP %s)", hostname, ip_str)
                return False

        return True
    except Exception as e:
        LOG.debug("SSRF protection: error validating URL %s: %s", url, e)
        return False


def extract_ocsp_url(pem_data: bytes, cert_name: str = "") -> Optional[str]:
    """
    Extract OCSP responder URL from PEM certificate data using the cryptography library.
    Validates the URL scheme is http:// or https://.
    Returns OCSP responder URL if present and valid, else None.
    """
    LOG.debug("🔒 OCSP checking support for certificate %s", cert_name)
    try:
        cert = x509.load_pem_x509_certificate(pem_data)

        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia_value = cast(AuthorityInformationAccess, aia.value)
        for access_description in aia_value:
            if access_description.access_method == AuthorityInformationAccessOID.OCSP:
                url = access_description.access_location.value
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    LOG.warning("⚠️ OCSP URL has invalid scheme for %s: %s", cert_name, url)
                    return None
                LOG.debug("🌐 OCSP found responder URL for %s: %s", cert_name, url)
                return url

        LOG.debug("🔒 OCSP no responder URL advertised in %s", cert_name)
        return None
    except x509.ExtensionNotFound:
        LOG.debug("🔒 OCSP no AIA extension found in %s", cert_name)
        return None
    except Exception as e:
        LOG.debug("🔒 OCSP failed to extract OCSP URL from %s: %s", cert_name, e)
        return None


def _fetch_issuer_from_aia(leaf: x509.Certificate, cert_name: str = "") -> Optional[x509.Certificate]:
    """
    Fetch the issuer certificate from the AIA caIssuers URL in the leaf certificate.
    Returns the issuer certificate or None if unavailable.
    """
    try:
        aia = leaf.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia_value = cast(AuthorityInformationAccess, aia.value)
        for access_description in aia_value:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_url = access_description.access_location.value
                parsed = urlparse(issuer_url)
                if parsed.scheme not in ("http", "https"):
                    continue
                LOG.debug("🌐 OCSP fetching issuer certificate from AIA: %s", issuer_url)
    
                if not is_safe_url(issuer_url):
                    LOG.error("❌ OCSP unsafe AIA issuer URL detected: %s", issuer_url)
                    return None

                req = Request(issuer_url, headers={"User-Agent": "BunkerWeb OCSP Fetcher (SSRF-Protected)"})
                try:
                    # Use a short timeout so we don't hang
                    with urlopen(req, timeout=10) as response:
                        issuer_der = response.read(1_048_576)  # Cap at 1MB to prevent memory exhaustion
                    # Try DER first (most common for caIssuers), then PEM
                    try:
                        return x509.load_der_x509_certificate(issuer_der)
                    except Exception:
                        return x509.load_pem_x509_certificate(issuer_der)
                except HTTPError as e:
                    LOG.warning("⚠️ OCSP HTTP %d error fetching issuer from AIA for %s from %s: %s", e.code, cert_name, issuer_url, e.reason)
                except URLError as e:
                    LOG.warning("⚠️ OCSP network error fetching issuer from AIA for %s from %s: %s", cert_name, issuer_url, e)
                except Exception as e:
                    LOG.warning("⚠️ OCSP failed to fetch issuer from AIA for %s from %s: %s", cert_name, issuer_url, e)
    except x509.ExtensionNotFound:
        LOG.debug("🔒 OCSP no AIA extension in leaf cert for %s", cert_name)
    except Exception as e:
        LOG.warning("⚠️ OCSP failed to fetch issuer from AIA for %s: %s", cert_name, e)
    return None


def _parse_chain(pem_data: bytes, cert_name: str = "") -> Tuple[x509.Certificate, x509.Certificate]:
    """
    Parse fullchain PEM data and return (leaf_cert, issuer_cert).
    The leaf is the first certificate; the issuer is identified by matching
    the leaf's issuer DN against the subject DNs of the remaining certificates.
    Falls back to the second certificate if no DN match is found.
    """
    certs = x509.load_pem_x509_certificates(pem_data)
    leaf = certs[0]

    if len(certs) >= 2:
        # Find the issuer by matching leaf.issuer to candidate.subject
        for idx, candidate in enumerate(certs[1:], start=1):
            if leaf.issuer == candidate.subject:
                LOG.debug("✓ OCSP selected issuer certificate index %d for %s", idx, cert_name)
                return leaf, candidate

        # Fallback: use the second certificate
        LOG.warning(
            "⚠️ OCSP could not verify issuer chain for %s by DN match, falling back to second certificate",
            cert_name,
        )
        return leaf, certs[1]

    # Single cert (no chain): try to fetch issuer from AIA caIssuers URL
    LOG.debug("🔄 OCSP single cert for %s, attempting to fetch issuer from AIA caIssuers", cert_name)
    issuer = _fetch_issuer_from_aia(leaf, cert_name)
    if issuer:
        return leaf, issuer

    raise RuntimeError(f"fullchain for {cert_name} does not contain issuer and AIA fetch failed")


# Default OCSP TTL fallback (1 day) if Next Update is missing
DEFAULT_OCSP_TTL = 86400


def _ocsp_response_lifetimes(ocsp_response: x509_ocsp.OCSPResponse) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract (remaining_ttl_seconds, total_lifetime_seconds) from a parsed OCSP response.
    Returns (None, None) if the timing fields are unavailable or invalid.
    """
    # Prefer *_utc properties (cryptography 42.0+) to avoid deprecation warnings
    this_update = getattr(ocsp_response, "this_update_utc", None) or ocsp_response.this_update
    if this_update is None:
        return None, None

    if this_update.tzinfo is None:
        this_update = this_update.replace(tzinfo=timezone.utc)

    next_update = getattr(ocsp_response, "next_update_utc", None) or ocsp_response.next_update
    if next_update is None:
        # No Next Update: treat lifetime as 24 hours from This Update (RFC standard fallback)
        LOG.debug("⚡ OCSP Next Update missing, using default lifetime of 24h from This Update")
        next_update = this_update + timedelta(hours=24)
    elif next_update.tzinfo is None:
        next_update = next_update.replace(tzinfo=timezone.utc)

    total_lifetime = int((next_update - this_update).total_seconds())
    if total_lifetime <= 0:
        LOG.debug("⚡ OCSP invalid lifetime: Next Update is not after This Update")
        return None, None

    now = datetime.now(timezone.utc)
    remaining = max(0, int((next_update - now).total_seconds()))
    return remaining, total_lifetime


def fetch_ocsp_response(pem_data: bytes, ocsp_url: str, cert_name: str = "", timeout: int = 10) -> Tuple[Optional[bytes], int]:
    """
    Fetch OCSP response using cryptography + urllib.
    Returns (raw DER bytes or None, ttl_seconds).
    """
    try:
        leaf, issuer = _parse_chain(pem_data, cert_name)
    except Exception as e:
        LOG.error("❌ OCSP failed to parse chain for %s: %s", cert_name, e)
        return None, 0

    try:
        # Try SHA256 first, fallback to SHA1 if responder returns non-successful status (RFC 6960 compatibility)
        ocsp_der = None
        for hash_alg, alg_name in [(hashes.SHA256(), "SHA256"), (hashes.SHA1(), "SHA1")]:
            try:
                # Build OCSP request
                builder = x509_ocsp.OCSPRequestBuilder()
                builder = builder.add_certificate(leaf, issuer, hash_alg)
                ocsp_request = builder.build()
                ocsp_request_data = ocsp_request.public_bytes(Encoding.DER)

                LOG.debug(
                    "🌐 OCSP fetching for %s (using %s): serial=%d, issuer=%s, responder=%s",
                    cert_name, alg_name, leaf.serial_number, issuer.subject.rfc4514_string(), ocsp_url
                )

                # --- Build HTTP request ---
                if not is_safe_url(ocsp_url):
                    LOG.error("❌ OCSP unsafe responder URL detected: %s", ocsp_url)
                    return None, 0

                req = Request(
                    ocsp_url,
                    data=ocsp_request_data,
                    headers={
                        "Content-Type": "application/ocsp-request",
                        "User-Agent": "BunkerWeb OCSP Fetcher (SSRF-Protected)",
                    },
                    method="POST",
                )
                # Explicitly use default SSL context with certificate verification enabled
                ssl_context = ssl.create_default_context()
                with urlopen(req, timeout=timeout, context=ssl_context) as response:
                    # cap response size at 100KB to prevent memory exhaustion from malicious responder
                    ocsp_der = response.read(102400)
        
                if not ocsp_der:
                    LOG.warning("⚠️ OCSP empty response from %s for %s", ocsp_url, cert_name)
                    continue

                # Check if it's a valid OCSP response via cryptography
                ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_der)
                if ocsp_response.response_status != x509_ocsp.OCSPResponseStatus.SUCCESSFUL:
                    LOG.warning(
                        "⚠️ OCSP responder returned %s for %s (using %s), retrying if fallback available...",
                        ocsp_response.response_status, cert_name, alg_name
                    )
                    ocsp_der = None
                    continue

                # If we reached here, we have a SUCCESSFUL response
                break

            except HTTPError as e:
                LOG.warning("⚠️ OCSP HTTP %d error for %s using %s: %s", e.code, cert_name, alg_name, e.reason)
                ocsp_der = None
                continue
            except Exception as e:
                LOG.warning("⚠️ OCSP request failed for %s using %s: %s", cert_name, alg_name, e)
                ocsp_der = None
                continue
        else:
            # Loop finished without a break: all attempts failed
            LOG.error("❌ OCSP failed to fetch successful response for %s after trying both SHA256 and SHA1", cert_name)
            return None, 0

        # === SECURE OCSP RESPONSE VERIFICATION ===
        # Use OpenSSL to cryptographically verify the OCSP response signature.
        # This prevents an attacker from MITM-ing the HTTP request and feeding a fake "SUCCESSFUL" payload.
        # At this point, ocsp_der is guaranteed to be set and successful
        ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_der)

        # === SECURE OCSP RESPONSE VERIFICATION ===
        # Use OpenSSL to cryptographically verify the OCSP response signature.
        # This prevents an attacker from MITM-ing the HTTP request and feeding a fake "SUCCESSFUL" payload.
        # Verify the OCSP response signature using OpenSSL CLI.
        # tempfile and subprocess are imported at the top of the file.

        with tempfile.NamedTemporaryFile(suffix=".der", delete=True) as f_der, \
             tempfile.NamedTemporaryFile(suffix=".pem", mode="w", delete=True) as f_issuer, \
             tempfile.NamedTemporaryFile(suffix=".pem", mode="w", delete=True) as f_leaf:

            # Secure temporary files with 0600 permissions (read/write for owner only)
            os.chmod(f_der.name, 0o600)
            os.chmod(f_issuer.name, 0o600)
            os.chmod(f_leaf.name, 0o600)

            f_der.write(ocsp_der)
            f_der.flush()

            f_issuer.write(issuer.public_bytes(Encoding.PEM).decode("utf-8"))
            f_issuer.flush()

            f_leaf.write(leaf.public_bytes(Encoding.PEM).decode("utf-8"))
            f_leaf.flush()
            
            # -respin checks the response
            # -partial_chain allows the issuer to act as a trust anchor even if it's an intermediate
            cmd = [
                "openssl", "ocsp",
                "-respin", f_der.name,
                "-issuer", f_issuer.name,
                "-cert", f_leaf.name,
                "-CAfile", f_issuer.name,
                "-partial_chain"
            ]

            try:
                # Add a timeout so a stuck openssl process cannot hang the whole job
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            except subprocess.TimeoutExpired as e:
                LOG.error(
                    "❌ OCSP response cryptographic signature verification timed out for %s after %s seconds. Discarding response.",
                    cert_name,
                    e.timeout,
                )
                return None, 0
            if p.returncode != 0:
                LOG.error("❌ OCSP response cryptographic signature verification failed for %s. Discarding forged/invalid response. OpenSSL Error: %s", cert_name, p.stderr.strip() or p.stdout.strip())
                return None, 0

        # Extract TTL
        remaining, _ = _ocsp_response_lifetimes(ocsp_response)
        if remaining is not None:
            ttl = min(remaining, 7 * 24 * 3600)  # Cap to 7 days
        else:
            ttl = 86400  # RFC standard fallback

        # Delay after successful fetch to prevent rate limiting
        LOG.debug("⏸️ OCSP delaying 2 seconds after fetch for %s to prevent rate limiting", cert_name)
        time.sleep(2)

        return ocsp_der, ttl
    except HTTPError as e:
        # HTTP error code — OCSP responder returned an error
        error_desc = f"HTTP {e.code}"
        if e.code == 404:
            error_desc += " (Not Found - OCSP responder URL not available)"
        elif e.code == 503:
            error_desc += " (Service Unavailable - responder temporarily down)"
        elif e.code == 500:
            error_desc += " (Internal Server Error - responder misconfigured)"
        elif 400 <= e.code < 500:
            error_desc += f" (Client Error - {e.reason})"
        elif e.code >= 500:
            error_desc += f" (Server Error - {e.reason})"
        LOG.error("❌ OCSP %s from responder for %s at %s", error_desc, cert_name, ocsp_url)
        return None, 0
    except URLError as e:
        # Network error — DNS, connection refused, timeout, SSL error, etc.
        LOG.error("❌ OCSP network error fetching response for %s from %s: %s", cert_name, ocsp_url, e)
        return None, 0
    except Exception as e:
        LOG.error("❌ OCSP failed to fetch response for %s: %s", cert_name, e)
        return None, 0


def extract_san_dns(pem_data: bytes, cert_name: str = "") -> List[str]:
    """
    Extract DNS names from certificate SAN extension.
    Best-effort; returns empty list on failure.
    """
    try:
        cert = x509.load_pem_x509_certificate(pem_data)
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        san_value = cast(SubjectAlternativeName, san.value)
        names = san_value.get_values_for_type(x509.DNSName)
        return sorted(set(names))
    except x509.ExtensionNotFound:
        return []
    except Exception as e:
        LOG.debug("OCSP failed to extract SAN from %s: %s", cert_name, e)
        return []


def get_cached_ocsp_ttl(cert_name: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Check if cached OCSP DER file exists and return:
      - remaining TTL in seconds (until Next Update)
      - total lifetime in seconds (Next Update - This Update)
    Both values are None if they cannot be determined.
    """
    sanitized_name = _sanitize_filename(cert_name)
    ocsp_path = CONFIGS_SSL_BASE / sanitized_name / "ocsp.der"
    LOG.debug("⚡ OCSP TTL check: checking cache for %s at %s", cert_name, ocsp_path)

    if not ocsp_path.is_file():
        LOG.debug("⚡ OCSP TTL check: cache miss - file not found for %s", cert_name)
        return None, None

    LOG.debug("⚡ OCSP cached file found for %s, reading This/Next Update...", cert_name)
    try:
        ocsp_data = ocsp_path.read_bytes()
        ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_data)

        remaining, total_lifetime = _ocsp_response_lifetimes(ocsp_response)
        if remaining is None or total_lifetime is None:
            LOG.debug("🔄 OCSP could not determine precise lifetime for %s from cached response", cert_name)
            return None, None

        # Type assertion: after None checks above, these are guaranteed to be int
        assert remaining is not None
        assert total_lifetime is not None

        LOG.info(
            "⚡ OCSP cached response for %s: remaining=%ds (%.1f days), total_lifetime=%ds (%.1f days)",
            cert_name,
            remaining,
            remaining / 86400.0,
            total_lifetime,
            total_lifetime / 86400.0,
        )
        return remaining, total_lifetime
    except Exception as e:
        LOG.warning("⚠️ OCSP exception while reading cached TTL for %s: %s", cert_name, e)
        return None, None


def _create_san_symlinks(pem_data: bytes, ocsp_path: Path, cert_name: str) -> None:
    """
    Create symlinks for each SAN in the certificate so that OCSP responses
    can be found by any SNI name, not just the cert directory name.
    E.g., if cert is for example.com + www.example.com and stored under example.com/ocsp.der,
    creates www.example.com/ocsp.der -> example.com/ocsp.der
    """
    sans = extract_san_dns(pem_data, cert_name)
    # Strip -rsa/-ecdsa suffix from cert_name for comparison
    base_name = _service_name_from_dir(cert_name)

    for san in sans:
        # Prevent Path Traversal by validating SAN format
        # Allow alphanumeric, hyphens, dots, and wildcards (e.g., *.example.com)
        if not re.match(r"^[A-Za-z0-9_.*-]+$", san):
            LOG.warning("⚠️ OCSP sanitization: skipping invalid/unsafe SAN %s", san)
            continue

        if san == base_name or san == cert_name:
            continue

        sanitized_san = _sanitize_filename(san)
        san_dir = CONFIGS_SSL_BASE / sanitized_san
        san_ocsp = san_dir / "ocsp.der"

        # Skip if target already exists (real file or valid symlink)
        if san_ocsp.exists() or san_ocsp.is_symlink():
            # Log details about what's already there for troubleshooting
            if san_ocsp.is_symlink():
                try:
                    target = san_ocsp.readlink()
                    expected_target = Path("..") / _sanitize_filename(cert_name) / "ocsp.der"
                    if target == expected_target:
                        LOG.debug("🔗 OCSP SAN symlink for %s already correct (%s -> %s)", san, san_ocsp, target)
                    else:
                        LOG.debug("ℹ️ OCSP SAN symlink for %s points to different target (got %s, expected %s) — likely overlapping certs, skipping", san, target, expected_target)
                except Exception:
                    LOG.debug("⚠️ OCSP SAN symlink for %s is broken or unreadable", san)
            elif san_ocsp.is_file():
                LOG.debug("ℹ️ OCSP SAN path %s is a regular file (not a symlink) — likely another real cert, skipping symlink", san_ocsp)
            continue

        try:
            san_dir.mkdir(parents=True, exist_ok=True)
            # Use relative symlink: ../cert_name/ocsp.der
            rel_target = Path("..") / _sanitize_filename(cert_name) / "ocsp.der"
            san_ocsp.symlink_to(rel_target)
            LOG.debug("🔗 OCSP created SAN symlink %s -> %s", san_ocsp, rel_target)
        except Exception as e:
            LOG.debug("⚠️ OCSP could not create SAN symlink for %s: %s", san, e)


def _get_cached_ocsp_certs(db: Any) -> set:
    """
    Get the set of certificate names that have cached OCSP responses in the database.
    Used to identify new vs. existing certificates for differential refresh strategy.

    Returns set of cert_name strings
    """
    cached_certs = set()

    if db is None:
        return cached_certs

    try:
        cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=False)
        for entry in cache_files:
            file_name = entry.get("file_name", "")
            if file_name.startswith("ocsp/"):
                cert_name_raw = file_name[len("ocsp/"):]
                # Prevent path traversal from crafted database entries
                if re.match(r"^[A-Za-z0-9_.*-]+$", cert_name_raw):
                    cached_certs.add(cert_name_raw)
    except Exception as e:
        LOG.warning("⚠️ OCSP could not retrieve cached certificate list from database: %s", e)

    return cached_certs


def _get_cert_checksums(db: Any, cert_names: set) -> Dict[str, str]:
    """
    Get previously stored checksums for certificates from the database.
    Checksums are stored in cache entries like 'cert_checksum/cert_name'.

    Args:
        db: Database connection
        cert_names: Set of certificate names to retrieve checksums for

    Returns:
        Dict of {cert_name: checksum_hex}
    """
    checksums = {}

    if db is None or not cert_names:
        return checksums

    try:
        # Optimization: use with_data=True to fetch all checksums in one go
        cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        for entry in cache_files:
            file_name = entry.get("file_name", "")
            if file_name.startswith("cert_checksum/"):
                cert_name_raw = file_name[len("cert_checksum/"):]
                if cert_name_raw in cert_names:
                    data = entry.get("data")
                    if data:
                        try:
                            checksums[cert_name_raw] = data.decode("utf-8").strip()
                        except Exception:
                            pass
    except Exception as e:
        LOG.debug("⚠️ OCSP could not retrieve certificate checksums from database: %s", e)

    return checksums


def _calculate_cert_checksum(pem_data: bytes) -> str:
    """
    Calculate SHA256 checksum of certificate PEM data.
    """
    return hashlib.sha256(pem_data).hexdigest()


def _clean_pem(pem_data: bytes) -> bytes:
    """
    Strip private keys, comments, and noise before the first certificate block.
    Ensures consistent checksums regardless of extra data in the database.
    """
    # 1. Strip embedded private keys
    if b"PRIVATE KEY" in pem_data:
        pem_data = re.sub(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----\s*", b"", pem_data)

    # 2. Strip comment lines
    pem_data = b"\n".join(line for line in pem_data.split(b"\n") if not line.startswith(b"#"))

    # 3. Strip everything before the first -----BEGIN
    pem_start = pem_data.find(b"-----BEGIN")
    if pem_start > 0:
        pem_data = pem_data[pem_start:]

    return pem_data


def _load_le_certs_from_db(db: Any) -> Dict[str, bytes]:
    """
    Load Let's Encrypt fullchain PEM data from the database tarball.
    The certbot-new job stores the entire /var/cache/bunkerweb/letsencrypt/etc directory
    as a tarball via cache_dir(). We extract fullchain.pem for each cert directory.

    Returns dict: {cert_name: fullchain_pem_bytes}
    """
    result: Dict[str, bytes] = {}

    # The tarball is stored with file_name = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"
    # It may be stored by either certbot-new or certbot-renew depending on which ran last
    tgz_file_name = "folder:/var/cache/bunkerweb/letsencrypt/etc.tgz"

    tgz_data = None
    for job_name in ("certbot-renew", "certbot-new"):
        try:
            tgz_data = db.get_job_cache_file(
                job_name=job_name,
                file_name=tgz_file_name,
                with_data=True,
                with_info=False,
            )
        except Exception as e:
            LOG.warning("⚠️ OCSP failed to query database for LE tarball (job=%s): %s", job_name, e)
            continue
        if tgz_data:
            LOG.debug("✓ OCSP found LE tarball from %s job", job_name)
            break

    if tgz_data is None:
        LOG.debug("ℹ️ OCSP no LE tarball found in database (certbot-new cache)")
        return result

    try:
        with tarfile.open(fileobj=io.BytesIO(tgz_data), mode="r:gz") as tar:
            for member in tar.getmembers():
                # Match live/<cert_name>/fullchain.pem symlinks — tarfile.extractfile()
                # follows symlinks within the archive to read the actual archive/ data
                if not member.issym():
                    continue
                parts = Path(member.name).parts
                # Match pattern: ./live/<cert_name>/fullchain.pem
                if len(parts) < 3:
                    continue
                idx = 1 if parts[0] == "." else 0
                if len(parts) == idx + 3 and parts[idx] == "live" and parts[idx + 2] == "fullchain.pem":
                    cert_name = parts[idx + 1]
                    # Prevent path traversal from crafted tarball entries
                    if not re.match(r"^[A-Za-z0-9_.*-]+$", cert_name):
                        LOG.warning("⚠️ OCSP sanitization: skipping unsafe cert_name from tarball: %s", cert_name)
                        continue
                    try:
                        f = tar.extractfile(member)
                        if f:
                            pem_data = f.read()
                            if not pem_data or b"-----BEGIN" not in pem_data:
                                LOG.warning("⚠️ OCSP LE fullchain for %s is empty or not valid PEM, skipping", cert_name)
                                continue
                            result[cert_name] = pem_data
                            LOG.debug("✓ OCSP extracted LE fullchain for %s from database tarball", cert_name)
                        else:
                            LOG.warning("⚠️ OCSP could not read LE fullchain for %s from tarball (extractfile returned None)", cert_name)
                    except KeyError:
                        LOG.warning("⚠️ OCSP symlink target missing in tarball for %s", cert_name)
                    except Exception as e:
                        LOG.warning("⚠️ OCSP failed to extract LE fullchain for %s: %s", cert_name, e)
    except tarfile.TarError as e:
        LOG.error("❌ OCSP LE tarball is corrupted or invalid: %s", e)
    except Exception as e:
        LOG.error("❌ OCSP failed to extract LE certificates from database tarball: %s", e)

    return result


def _load_custom_certs_from_db(db: Any) -> Dict[str, bytes]:
    """
    Load custom certificate PEM data from the database.
    The custom-cert job stores cert.pem per service_id via cache_file().

    Returns dict: {service_name: cert_pem_bytes}
    """
    result: Dict[str, bytes] = {}

    try:
        cache_files = db.get_jobs_cache_files(job_name="custom-cert", with_data=True)
    except Exception as e:
        LOG.error("❌ OCSP failed to query database for custom certificates: %s", e)
        return result

    if not cache_files:
        LOG.debug("ℹ️ OCSP no custom-cert cache entries found in database")
        return result

    for entry in cache_files:
        try:
            file_name = entry.get("file_name", "")
            service_id = entry.get("service_id", "")
            # Match cert.pem, cert-ecdsa.pem, cert-rsa.pem
            if not (file_name.startswith("cert") and file_name.endswith(".pem")):
                continue
            if not service_id:
                LOG.debug("⚠️ OCSP custom cert entry %s has no service_id, skipping", file_name)
                continue
            # Prevent path traversal: validate service_id format
            if not re.match(r"^[A-Za-z0-9_.*-]+$", service_id):
                LOG.warning("⚠️ OCSP sanitization: skipping custom cert with invalid service_id: %s", service_id)
                continue
            data = entry.get("data")
            if not data:
                LOG.warning("⚠️ OCSP custom cert %s for service %s has no data, skipping", file_name, service_id)
                continue
            # Derive suffix from filename: cert-ecdsa.pem -> -ecdsa, cert.pem -> ""
            suffix = file_name.replace("cert", "").replace(".pem", "")  # e.g. "-ecdsa", "-rsa", ""
            key = f"customcert-{service_id}{suffix}"
            # Double-check derived key is safe (defensive validation)
            if not re.match(r"^[A-Za-z0-9_.*-]+$", key):
                LOG.warning("⚠️ OCSP sanitization: skipping custom cert with unsafe derived key: %s", key)
                continue
            result[key] = data
            LOG.debug("✓ OCSP loaded custom cert for %s from database (file=%s, size=%d)", key, file_name, len(data))
        except Exception as e:
            LOG.warning("⚠️ OCSP failed to process custom cert entry %s: %s", entry.get("file_name", "?"), e)

    return result


def restore_ocsp_from_database(db: Optional[Any] = None) -> None:
    """
    Restore cached OCSP responses from database to disk.
    Called at startup to ensure disk cache is populated from database.
    This handles ephemeral storage (tmpfs, etc.) by restoring files on each run.
    """
    if not db:
        LOG.debug("ℹ️ OCSP database not available, skipping cache restoration")
        return

    LOG.info("🔄 OCSP syncing cached responses from database to disk...")
    try:
        restored_count = 0
        replaced_count = 0
        ok_count = 0

        # Get all OCSP cache entries from database for this job
        cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        for entry in cache_files:
            file_name = entry.get("file_name", "")
            if not file_name.startswith("ocsp/") or not entry.get("data"):
                continue

            cert_name_raw = file_name[len("ocsp/"):]
            # Prevent path traversal from crafted database entries
            if not re.match(r"^[A-Za-z0-9_.*-]+$", cert_name_raw):
                LOG.warning("⚠️ OCSP sanitization: skipping unsafe cert_name from database: %s", cert_name_raw)
                continue
            
            sanitized_name = _sanitize_filename(cert_name_raw)
            db_data = entry["data"]
            db_checksum = entry.get("checksum") or hashlib.sha256(db_data).hexdigest()

            try:
                ocsp_cert_dir = CONFIGS_SSL_BASE / sanitized_name
                ocsp_path = ocsp_cert_dir / "ocsp.der"

                if ocsp_path.is_file():
                    # File exists — compare checksum
                    disk_checksum = hashlib.sha256(ocsp_path.read_bytes()).hexdigest()
                    if disk_checksum == db_checksum:
                        ok_count += 1
                        LOG.debug("✓ OCSP disk file for %s matches database (checksum=%s)", cert_name_raw, db_checksum[:8])
                        continue
                    # Checksum mismatch — replace with database version
                    LOG.info("🔄 OCSP disk file for %s has wrong checksum (disk=%s, db=%s), replacing", cert_name_raw, disk_checksum[:8], db_checksum[:8])
                    ocsp_path.write_bytes(db_data)
                    ocsp_path.chmod(0o644)
                    replaced_count += 1
                else:
                    # File missing — restore from database
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                    ocsp_path.write_bytes(db_data)
                    ocsp_path.chmod(0o644)
                    restored_count += 1
                    LOG.debug("✓ OCSP restored cached response for %s from database", cert_name_raw)
            except Exception as e:
                LOG.debug("⚠️ OCSP could not sync cache for %s: %s", cert_name_raw, e)

        if restored_count > 0 or replaced_count > 0:
            LOG.info("✓ OCSP sync complete: restored=%d, replaced=%d, unchanged=%d", restored_count, replaced_count, ok_count)
        else:
            LOG.debug("ℹ️ OCSP sync complete: all %d disk files match database (restored=0, replaced=0)", ok_count)
    except Exception as e:
        LOG.debug("OCSP exception while attempting cache sync: %s", e)


def _process_cert(cert_name: str, pem_data: bytes, db: Optional[Any] = None, stats: Optional[dict] = None, force_fetch: bool = False) -> Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]:
    """
    Process a single certificate for OCSP stapling. Works with in-memory PEM data.
    If force_fetch is True, skips the cached TTL check and retrieves a new response.

    Returns a tuple of (cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, was_attempted) for batched database writes.
    If ocsp_der is None, it means the fetch was skipped or failed.
    """
    if stats is None:
        stats = {}

    service_name = _service_name_from_dir(cert_name)
    sanitized_name = _sanitize_filename(cert_name)

    # === PEM CLEANING & SECURITY STRIPPING ===
    # Clean it immediately so all subsequent logic (OCSP fetch, checksum, parsing) 
    # uses the normalized/safe version.
    pem_data = _clean_pem(pem_data)
    cert_checksum = _calculate_cert_checksum(pem_data)

    # Check per-service OCSP stapling setting
    if not _is_ocsp_enabled_for_service(service_name):
        LOG.debug("🧹 OCSP stapling disabled for service %s, cleaning up cache for %s", service_name, cert_name)
        cleanup_ocsp_cache(db, cert_name)
        stats["le_certs_skipped"] = stats.get("le_certs_skipped", 0) + 1
        return (cert_name, None, 0, cert_checksum, pem_data, None, False)

    # Check if certificate checksum matches what we have in database
    cached_checksum = None
    if db:
        try:
            checksum_data = db.get_job_cache_file(file_name=f"cert_checksum/{sanitized_name}", job_name="ocsp-refresh")
            if checksum_data:
                cached_checksum = checksum_data.decode("utf-8").strip()
        except Exception as e:
            LOG.debug("⚠️ OCSP could not check cached checksum for %s: %s", cert_name, e)

    LOG.debug("🔄 OCSP processing certificate %s", cert_name)

    try:
        if not pem_data.startswith(b"-----BEGIN"):
            LOG.warning("⚠️ OCSP cert for %s has no PEM BEGIN marker or is invalid after cleaning, skipping", cert_name)
            return (cert_name, None, 0, cert_checksum, pem_data, None, False)

        # Proceed with extracting OCSP URL using the CLEANED pem_data
        ocsp_url = extract_ocsp_url(pem_data, cert_name)
        if not ocsp_url:
            LOG.debug("ℹ️ OCSP certificate %s has no responder, skipping fetch", cert_name)
            stats["le_certs_no_ocsp"] = stats.get("le_certs_no_ocsp", 0) + 1
            return (cert_name, None, 0, cert_checksum, pem_data, None, False)

        LOG.debug("🌐 OCSP responder for certificate %s: %s", cert_name, ocsp_url)

        # === Check if cached OCSP response is still fresh ===
        cached_ttl, total_lifetime = get_cached_ocsp_ttl(cert_name)
        if cached_ttl is not None:
            half_lifetime = (total_lifetime // 2) if (total_lifetime and total_lifetime > 0) else 0
            
            # Skip fetch ONLY if not forced AND TTL is above MIN_TTL AND above 50% lifetime
            if not force_fetch and cached_ttl > MIN_TTL and cached_ttl > half_lifetime:
                LOG.debug(
                    "✓ OCSP cached response for %s still valid for %ds (%.1f days), above thresholds (MIN_TTL=%ds, 50%% threshold=%ds), skipping fetch",
                    cert_name, cached_ttl, cached_ttl / 86400.0, MIN_TTL, half_lifetime,
                )
                stats["ocsp_cached_responses"] = stats.get("ocsp_cached_responses", 0) + 1
                return (cert_name, None, cached_ttl, cert_checksum, pem_data, ocsp_url, False)
            
            if cached_ttl <= MIN_TTL:
                LOG.info("🔄 OCSP response for %s is near expiration (TTL=%ds < %ds), attempting aggressive refresh", cert_name, cached_ttl, MIN_TTL)

        ocsp_der: Optional[bytes] = None
        ttl: int = 0

        # Use a timeout of 10 seconds per attempt, retry once after 10 seconds
        for attempt in (1, 2):
            ocsp_der, ttl = fetch_ocsp_response(pem_data, ocsp_url, cert_name=cert_name, timeout=10)
            if ocsp_der:
                LOG.debug("✓ OCSP successfully fetched response for %s on attempt %d (TTL=%ds)", cert_name, attempt, ttl)
                stats["ocsp_fetched_responses"] = stats.get("ocsp_fetched_responses", 0) + 1
                break
            if attempt == 1:
                LOG.warning("⚠️ OCSP fetch failed for %s, retrying once after 2 seconds ...", cert_name)
                time.sleep(2)

        if not ocsp_der:
            LOG.error("❌ OCSP failed to fetch response for %s after retries", cert_name)

            if cached_ttl is not None:
                current_ttl = cast(int, cached_ttl)
                if current_ttl <= 0:
                    LOG.warning(
                        "🧹 OCSP cached response for %s is already expired and refresh failed. Cleaning up invalid cache.",
                        cert_name,
                    )
                    cleanup_ocsp_cache(db, cert_name)
                elif current_ttl <= MIN_TTL:
                    LOG.warning(
                        "🚨 OCSP CRITICAL: Cached response for %s is near expiration (TTL=%ds) and refresh failed. "
                        "Removing from cache to prevent stapling expired data.",
                        cert_name,
                        current_ttl,
                    )
                    cleanup_ocsp_cache(db, cert_name)
                else:
                    LOG.warning(
                        "⚠️ OCSP could NOT refresh response for %s, keeping existing cache (TTL=%ds) for now",
                        cert_name,
                        current_ttl,
                    )
                return (cert_name, None, current_ttl, cert_checksum, pem_data, ocsp_url, True)

            return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)

        # Calculate checksum for integrity verification
        ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest()
        ttl_readable = f"{ttl / 86400.0:.1f} days" if ttl >= 86400 else f"{ttl / 3600.0:.1f} hours"
        LOG.info("⚡ OCSP final TTL for %s is %ds (%s) (checksum=%s)", cert_name, ttl, ttl_readable, ocsp_checksum[:8])

        # === Return result for batched database writes ===
        return (cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, True)

    except Exception as e:
        LOG.error("❌ OCSP exception while processing certificate %s: %s", cert_name, e)
        stats["errors"] = stats.get("errors", 0) + 1
        return (cert_name, None, 0, cert_checksum, pem_data, None, False)


def process_custom_certs(
    db: Optional[Any] = None,
    stats: Optional[dict] = None,
    lock_fd: Optional[int] = None,
    refresh_fn: Optional[Callable[[str], None]] = None,
    timeout_fn: Optional[Callable[[str], bool]] = None,
    skip_unchanged_ttl_checks: bool = False,
) -> List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]]:
    """
    Process OCSP for custom certificates using certificate data from the database.

    Returns a list of tuples (cert_name, ocsp_der, ttl, checksum, pem_data, ocsp_url, was_attempted) for batched database writes.

    Args:
        db: Database connection
        stats: Statistics dictionary
        lock_fd: Optional file descriptor for lock refresh (for long operations)
        refresh_fn: Optional callable to refresh lock (prevents stale detection)
        timeout_fn: Optional callable to check job timeout
    """
    if stats is None:
        stats = {}

    results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]] = []

    if not db:
        LOG.info("ℹ️ OCSP database not available, cannot process custom certificates")
        return results

    try:
        custom_certs = _load_custom_certs_from_db(db)
        if not custom_certs:
            LOG.info("ℹ️ OCSP no custom certificates found in database")
            return results

        LOG.info("🔄 OCSP loaded %d custom certificate(s) from database", len(custom_certs))

        # Check which custom certs have changed since last OCSP refresh
        # The names from _load_custom_certs_from_db already include the 'customcert-' prefix
        previous_custom_checksums = _get_cert_checksums(db, set(custom_certs.keys()))
        changed_custom_certs = {}
        unchanged_custom_certs = {}

        for cert_name, pem_data in custom_certs.items():
            # Clean PEM before calculating checksum to ensure consistency
            cleaned_pem = _clean_pem(pem_data)
            current_checksum = _calculate_cert_checksum(cleaned_pem)
            previous_checksum = previous_custom_checksums.get(cert_name)

            if previous_checksum is None:
                # No previous checksum, treat as changed
                changed_custom_certs[cert_name] = pem_data
                LOG.debug("⚠️ OCSP no previous checksum found for custom cert %s, will refresh", cert_name)
            elif current_checksum != previous_checksum:
                # Certificate content has changed
                changed_custom_certs[cert_name] = pem_data
                LOG.debug("🔄 OCSP custom certificate content changed for %s", cert_name)
            else:
                # Certificate content unchanged
                unchanged_custom_certs[cert_name] = pem_data

        if unchanged_custom_certs:
            if skip_unchanged_ttl_checks:
                LOG.info("✓ OCSP skipping TTL checks for %d unchanged custom certificate(s) (recently run)", len(unchanged_custom_certs))
                stats["custom_certs_skipped"] = stats.get("custom_certs_skipped", 0) + len(unchanged_custom_certs)
            else:
                LOG.info("✓ OCSP checking TTL for %d unchanged custom certificate(s): %s", len(unchanged_custom_certs), ", ".join(sorted(unchanged_custom_certs.keys())))
                stats["custom_certs_unchanged"] = stats.get("custom_certs_unchanged", 0) + len(unchanged_custom_certs)

        stats["custom_certs_processed"] = stats.get("custom_certs_processed", 0) + len(custom_certs)

        # 1. Process changed custom certificates (force refresh)
        for cert_name, cert_pem in sorted(changed_custom_certs.items()):
            if callable(timeout_fn) and timeout_fn(f"changed custom cert {cert_name}"):
                break
            if callable(refresh_fn):
                refresh_fn(cert_name)
            results.append(_process_cert(cert_name, cert_pem, db, stats, force_fetch=True))

        # 2. Process unchanged custom certificates (TTL check only)
        if not skip_unchanged_ttl_checks:
            for cert_name, cert_pem in sorted(unchanged_custom_certs.items()):
                if callable(timeout_fn) and timeout_fn(f"unchanged custom cert {cert_name}"):
                    break
                if callable(refresh_fn):
                    refresh_fn(cert_name)
                results.append(_process_cert(cert_name, cert_pem, db, stats, force_fetch=False))

    except Exception as e:
        LOG.error("OCSP exception while processing custom certificates: %s", e)
        stats["errors"] = stats.get("errors", 0) + 1

    return results


def _service_name_from_dir(dir_name: str) -> str:
    """Strip -rsa or -ecdsa suffix and customcert- prefix from a name to get the service name."""
    name = dir_name
    if name.startswith("customcert-"):
        name = name[len("customcert-"):]
    for suffix in ("-rsa", "-ecdsa"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _is_ocsp_enabled_for_service(service_name: str) -> bool:
    """Check if OCSP stapling is enabled for a specific service (multisite setting)."""
    # Check service-specific setting first, fall back to global
    value = os.getenv(f"{service_name}_SSL_USE_OCSP_STAPLING", os.getenv("SSL_USE_OCSP_STAPLING", "yes"))
    return value.lower() == "yes"


def cleanup_ocsp_cache(db: Optional[Any] = None, cert_name: Optional[str] = None, purge_db: bool = True) -> None:
    """
    Remove OCSP stapling leftovers from disk and optionally database.
    If cert_name is provided, only clean up that specific certificate.
    If cert_name is None, clean up ALL OCSP caches.
    If purge_db is False, only disk files are removed — database entries are preserved
    so cached responses can be quickly restored when OCSP is re-enabled.
    """
    if cert_name:
        # Prevent Path Traversal during cleanup
        if not re.match(r"^[A-Za-z0-9_.*-]+$", cert_name):
            LOG.error("❌ OCSP sanitization: refusing to clean up invalid/unsafe cert_name %s", cert_name)
            return

        # Clean up a single certificate's OCSP cache
        sanitized_name = _sanitize_filename(cert_name)
        ocsp_dir = CONFIGS_SSL_BASE / sanitized_name
        if ocsp_dir.is_dir():
            shutil.rmtree(ocsp_dir, ignore_errors=True)
            LOG.info("🧹 OCSP removed cache directory for %s", cert_name)

        # Also remove any SAN symlinks that point to this cert's OCSP cache
        if CONFIGS_SSL_BASE.is_dir():
            target_rel = Path("..") / sanitized_name / "ocsp.der"
            for entry in CONFIGS_SSL_BASE.iterdir():
                if not entry.is_dir():
                    continue
                san_ocsp = entry / "ocsp.der"
                if san_ocsp.is_symlink():
                    try:
                        if san_ocsp.readlink() == target_rel:
                            san_ocsp.unlink()
                            LOG.debug("🧹 OCSP removed SAN symlink %s", san_ocsp)
                            # Remove empty directory
                            try:
                                entry.rmdir()
                            except OSError:
                                pass
                    except Exception:
                        pass

        if db and purge_db:
            try:
                # Delete both response and checksum from database
                db.delete_job_cache(file_name=f"ocsp/{sanitized_name}", job_name="ocsp-refresh")
                db.delete_job_cache(file_name=f"cert_checksum/{sanitized_name}", job_name="ocsp-refresh")
                LOG.debug("🧹 OCSP database records removed for %s", cert_name)
            except Exception as e:
                LOG.debug("🧹 OCSP could not remove database entry for %s: %s", cert_name, e)
    else:
        # Clean up ALL OCSP caches (including symlinks)
        if CONFIGS_SSL_BASE.is_dir():
            for entry in sorted(CONFIGS_SSL_BASE.iterdir()):
                if not entry.is_dir():
                    continue
                ocsp_file = entry / "ocsp.der"
                if ocsp_file.is_symlink() or ocsp_file.is_file():
                    ocsp_file.unlink(missing_ok=True)
                    LOG.info("🧹 OCSP removed cached response %s", ocsp_file)
                # Remove the directory if it's now empty
                try:
                    entry.rmdir()
                except OSError:
                    pass  # Directory not empty, leave it

        if db and purge_db:
            try:
                # Remove all OCSP-related cache entries from database
                job_cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh")
                for cache_file in job_cache_files:
                    file_name = cache_file.get("file_name", "")
                    if file_name.startswith("ocsp/") or file_name.startswith("cert_checksum/") or file_name == "last_full_refresh":
                        try:
                            db.delete_job_cache(file_name=file_name, job_name="ocsp-refresh")
                            LOG.debug("🧹 OCSP removed database entry %s", file_name)
                        except Exception as e:
                            LOG.debug("🧹 OCSP could not remove database entry %s: %s", file_name, e)
            except Exception as e:
                LOG.debug("🧹 OCSP could not clean database entries: %s", e)
        elif not purge_db:
            LOG.info("🧹 OCSP disk caches cleaned up")

        LOG.info("🧹 OCSP all stapling caches cleaned up")


def _cleanup_orphaned_ocsp(db: Optional[Any], le_certs: Dict[str, bytes], stats: Optional[dict] = None) -> None:
    """
    Remove OCSP cache entries (disk + database) for services that no longer have
    certificates in the database. This handles deleted services.
    """
    if stats is None:
        stats = {}

    # Build set of valid cert names from LE certs
    valid_cert_names: set = set(le_certs.keys())

    # Add custom cert names
    if db:
        try:
            custom_certs = _load_custom_certs_from_db(db)
            for key in custom_certs:
                # key already starts with customcert-
                valid_cert_names.add(key)
        except Exception as e:
            LOG.warning("⚠️ OCSP could not load custom certs for orphan check: %s", e)
            return  # Don't clean up if we can't verify what's valid

    if not valid_cert_names:
        LOG.debug("ℹ️ OCSP no valid certs found, skipping orphan cleanup to avoid accidental deletion")
        return

    orphaned_count: int = 0

    # Check database OCSP entries
    if db:
        try:
            cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=False)
            for entry in cache_files:
                file_name = entry.get("file_name", "")
                if not file_name.startswith("ocsp/"):
                    continue
                cert_name_raw = file_name[len("ocsp/"):]
                if cert_name_raw not in valid_cert_names:
                    LOG.info("🧹 OCSP removing orphaned entry for deleted service: %s", cert_name_raw)
                    cleanup_ocsp_cache(db, cert_name_raw)
                    orphaned_count = orphaned_count + 1
        except Exception as e:
            LOG.warning("⚠️ OCSP could not check database for orphaned entries: %s", e)

    # Check disk directories for orphaned OCSP files
    if CONFIGS_SSL_BASE.is_dir():
        for entry in sorted(CONFIGS_SSL_BASE.iterdir()):
            if not entry.is_dir():
                continue
            ocsp_file = entry / "ocsp.der"
            if not ocsp_file.is_file() and not ocsp_file.is_symlink():
                continue
            cert_name_raw = entry.name
            if cert_name_raw not in valid_cert_names:
                # Check if it's a SAN symlink (those are managed by _create_san_symlinks)
                if ocsp_file.is_symlink():
                    continue
                LOG.info("🧹 OCSP removing orphaned disk cache for deleted service: %s", cert_name_raw)
                cleanup_ocsp_cache(db, cert_name_raw)
                orphaned_count = orphaned_count + 1

    if orphaned_count > 0:
        LOG.info("🧹 OCSP cleaned up %d orphaned cache entries for deleted services", orphaned_count)
        stats["orphaned_cleaned"] = orphaned_count


def _verify_and_restore_ocsp_files(db: Optional[Any] = None, stats: Optional[dict] = None) -> None:
    """
    End-of-job verification: ensure all OCSP files on disk match database checksums.
    Restores missing files from database to prevent OCSP stapling failures.

    This handles cases where OCSP cache directories are externally deleted or corrupted.
    Includes sleep before verification to allow concurrent writers to finish.
    """
    if stats is None:
        stats = {}

    if not db:
        LOG.warning("⚠️ OCSP cannot verify files without database connection")
        return

    # Verification: check if files exist on disk and match database checksums

    verify_count = 0
    restored_count = 0
    mismatch_count = 0

    try:
        # Get all OCSP entries from database
        # Get all entries and filter for actual OCSP responses
        all_entries = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        ocsp_entries = [e for e in all_entries if e.get("file_name", "").startswith("ocsp/")]
        if not ocsp_entries:
            LOG.info("ℹ️ OCSP no cache entries in database to verify")
            return
            
        LOG.info("🔍 OCSP verifying %d cache entry(ies) from database", len(ocsp_entries))

        for entry in ocsp_entries:
            file_name = entry.get("file_name", "")
            if not file_name.startswith("ocsp/"):
                continue

            cert_name_raw = file_name[len("ocsp/"):]
            sanitized_name = _sanitize_filename(cert_name_raw)
            data = entry.get("data")
            db_checksum = entry.get("checksum", "")

            if not data or not db_checksum:
                LOG.warning("⚠️ OCSP database entry %s has no data or checksum, skipping verification", cert_name_raw)
                continue

            verify_count += 1

            # Check if file exists on disk
            ocsp_cert_dir = CONFIGS_SSL_BASE / sanitized_name
            ocsp_path = ocsp_cert_dir / "ocsp.der"

            # Check if database response is already expired
            try:
                ocsp_response = x509_ocsp.load_der_ocsp_response(data)
                remaining, _ = _ocsp_response_lifetimes(ocsp_response)
                if remaining is not None and remaining <= 0:
                    LOG.warning("🧹 OCSP response in database for %s is expired (remaining=%ds). Skipping restoration to disk.", cert_name_raw, remaining)
                    # Optionally remove from database to prevent future attempts
                    if db:
                        try:
                            db.delete_job_cache(file_name=file_name, job_name="ocsp-refresh")
                            LOG.debug("🧹 OCSP removed expired database entry %s", file_name)
                        except Exception:
                            pass
                    continue
            except Exception as e:
                LOG.warning("⚠️ OCSP could not parse response from database for %s during verification: %s", cert_name_raw, e)

            try:
                if not ocsp_path.is_file():
                    # File missing: restore from database
                    LOG.warning("⚠️ OCSP file missing for %s, restoring from database", cert_name_raw)
                    try:
                        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                        ocsp_path.write_bytes(data)
                        ocsp_path.chmod(0o644)
                        LOG.info("✓ OCSP restored %s from database", cert_name_raw)
                        restored_count += 1
                    except Exception as e:
                        LOG.error("❌ OCSP could not restore %s from database: %s", cert_name_raw, e)
                        stats["errors"] = stats.get("errors", 0) + 1
                        continue

                else:
                    # File exists: verify checksum
                    file_data = ocsp_path.read_bytes()
                    file_checksum = hashlib.sha256(file_data).hexdigest()

                    if file_checksum != db_checksum:
                        LOG.warning(
                            "⚠️ OCSP checksum mismatch for %s (file=%s, db=%s). "
                            "Restoring from database.",
                            cert_name_raw, file_checksum[:8], db_checksum[:8]
                        )
                        try:
                            ocsp_path.write_bytes(data)
                            ocsp_path.chmod(0o644)
                            LOG.info("✓ OCSP restored correct version of %s", cert_name_raw)
                            mismatch_count += 1
                        except Exception as e:
                            LOG.error("❌ OCSP could not restore %s: %s", cert_name_raw, e)
                            stats["errors"] = stats.get("errors", 0) + 1
                    else:
                        LOG.debug("✓ OCSP %s checksum verified (matches database)", cert_name_raw)

            except Exception as e:
                LOG.warning("⚠️ OCSP error verifying %s: %s", cert_name_raw, e)
                stats["errors"] = stats.get("errors", 0) + 1

        if verify_count > 0:
            LOG.info(
                "🔍 OCSP verification complete: %d checked | ✓ %d restored (missing) | 🔄 %d corrected (mismatch)",
                verify_count, restored_count, mismatch_count
            )
            if stats is not None:
                stats["ocsp_verified"] = stats.get("ocsp_verified", 0) + verify_count
                stats["ocsp_restored"] = stats.get("ocsp_restored", 0) + restored_count
                stats["ocsp_corrected"] = stats.get("ocsp_corrected", 0) + mismatch_count

    except Exception as e:
        LOG.warning("⚠️ OCSP verification failed: %s", e)
        stats["errors"] = stats.get("errors", 0) + 1


def _persist_ocsp_results_to_db(
    db: Optional[Any],
    all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]],
    stats: Optional[Dict[str, int]] = None,
) -> None:
    """
    Persist OCSP responses and certificate checksums to database.
    Called both at normal completion and when timeout occurs.
    """
    if db is None or not all_ocsp_results:
        return

    if stats is None:
        stats = {}

    LOG.info("🔄 OCSP batching database updates for %d certificate(s)", len(all_ocsp_results))

    for cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, was_attempted in all_ocsp_results:
        sanitized_name = _sanitize_filename(cert_name)

        # 1. Update OCSP response if we have a new one
        if ocsp_der and ttl > 0:
            cache_key = f"ocsp/{sanitized_name}"
            try:
                ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest()
                err = db.upsert_job_cache(
                    service_id=None,  # Global cache entry
                    file_name=cache_key,
                    data=ocsp_der,
                    job_name="ocsp-refresh",
                    checksum=ocsp_checksum,
                )

                if err:
                    LOG.error("❌ OCSP error while storing response for %s in database: %s", cert_name, err)
                    stats["errors"] = stats.get("errors", 0) + 1
                else:
                    LOG.info("✓ OCSP stored response for %s in database (TTL=%ds, checksum=%s)", cert_name, ttl, ocsp_checksum[:8])
            except Exception as e:
                LOG.error("❌ OCSP exception while storing response for %s in database: %s", cert_name, e)
                stats["errors"] = stats.get("errors", 0) + 1

        # 2. ALWAYS store/update certificate content checksum for future differential checks
        cert_checksum_key = f"cert_checksum/{sanitized_name}"
        try:
            err = db.upsert_job_cache(
                service_id=None,
                file_name=cert_checksum_key,
                data=cert_checksum.encode("utf-8"),
                job_name="ocsp-refresh",
                checksum=hashlib.sha256(cert_checksum.encode("utf-8")).hexdigest(),
            )
            if err:
                LOG.debug("⚠️ OCSP could not store cert checksum for %s: %s", cert_name, err)
            else:
                LOG.debug("✓ OCSP persisted checksum for %s", cert_name)
        except Exception as e:
            LOG.debug("⚠️ OCSP exception while storing cert checksum for %s: %s", cert_name, e)


def _persist_ocsp_results_to_disk(
    all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]],
    stats: Optional[Dict[str, int]] = None,
) -> None:
    """
    Write OCSP responses to disk cache files.
    Called both at normal completion and when timeout occurs.
    """
    if not all_ocsp_results:
        return

    if stats is None:
        stats = {}

    for cert_name, ocsp_der, ttl, checksum, pem_data, ocsp_url, was_attempted in all_ocsp_results:
        if not ocsp_der:
            continue
        try:
            # Acquire lock to prevent race conditions with concurrent OCSP fetches
            lock_fd = _acquire_cert_lock(cert_name)
            sanitized_name = _sanitize_filename(cert_name)
            try:
                # Create the SSL configs directory for this certificate
                ocsp_cert_dir = CONFIGS_SSL_BASE / sanitized_name
                try:
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    LOG.error("❌ OCSP error while creating directory %s: %s", ocsp_cert_dir, e)
                    stats["errors"] = stats.get("errors", 0) + 1
                    continue

                # Write OCSP response to cache/ssl/{cert-name}/ocsp.der
                ocsp_path = ocsp_cert_dir / "ocsp.der"
                try:
                    ocsp_path.write_bytes(ocsp_der)
                    ocsp_path.chmod(0o644)  # Readable by nginx
                    LOG.info("✓ OCSP saved response for %s to disk at %s", cert_name, ocsp_path)

                    # Create symlinks for each SAN so OCSP is found by any SNI name
                    _create_san_symlinks(pem_data, ocsp_path, cert_name)
                except Exception as e:
                    LOG.error("❌ OCSP error while writing response for %s to disk: %s", cert_name, e)
                    stats["errors"] = stats.get("errors", 0) + 1
            finally:
                _release_cert_lock(lock_fd)
        except Exception as e:
            LOG.error("❌ OCSP exception while writing response for %s to disk: %s", cert_name, e)
            stats["errors"] = stats.get("errors", 0) + 1


def main() -> int:
    global status
    db: Optional[Any] = None

    # Job-level timeout: exit gracefully if exceeded (prevents deadlock on slow systems)
    # Responses fetched so far are saved; next run continues where left off
    JOB_TIMEOUT = 1500  # 25 minutes in seconds
    job_start_time = time.time()
    lock_fd_main = None

    def check_job_timeout(phase: str = "") -> bool:
        """Check if job has exceeded timeout. Returns True if timeout exceeded."""
        elapsed = time.time() - job_start_time
        if elapsed > JOB_TIMEOUT:
            LOG.warning(
                "⏱️ OCSP job timeout after %.0fs (%.1f minutes) %s. "
                "Saved responses fetched so far; next run will continue processing remaining certificates.",
                elapsed, elapsed / 60.0, phase
            )
            return True
        return False

    def refresh_job_lock(cert_name: str = "") -> None:
        """Refresh the lock to prevent stale detection during long jobs."""
        _refresh_cert_lock(lock_fd_main, cert_name or "main")

    # Statistics tracking
    stats: Dict[str, int] = {
        "le_certs_processed": 0,
        "le_certs_skipped": 0,
        "le_certs_no_ocsp": 0,
        "custom_certs_processed": 0,
        "custom_certs_skipped": 0,
        "custom_certs_no_ocsp": 0,
        "ocsp_cached_responses": 0,
        "ocsp_fetched_responses": 0,
        "errors": 0,
        "le_certs_new": 0,
        "le_certs_changed": 0,
        "custom_certs_unchanged": 0,
        "ocsp_verified": 0,
        "ocsp_restored": 0,
        "ocsp_corrected": 0,
        "orphaned_cleaned": 0,
    }

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OCSP refresh job for BunkerWeb")
    parser.add_argument("--force", action="store_true", help="Force full OCSP refresh and TTL checks managed by the job")
    args, unknown = parser.parse_known_args()
    force_all = args.force

    try:
        LOG.info("🔄 OCSP refresh job started with differential update strategy (timeout in %d minutes%s)", 
                 JOB_TIMEOUT // 60, " [FORCE]" if force_all else "")

        # Acquire main lock for the entire OCSP refresh operation
        lock_fd_main = _acquire_cert_lock("main", timeout=300, stale_threshold=1800)

        # Initialize database connection — this is our primary data source
        db = None
        if Database is not None:
            try:
                db = Database(LOG)
                LOG.debug("✓ OCSP database connection established")
            except Exception as e:
                LOG.error("❌ OCSP could not establish database connection: %s", e)
                return 2
        else:
            LOG.error("❌ OCSP Database module not available, cannot proceed")
            return 2

        # === Check for previously cached OCSP responses ===
        previous_ocsp_certs = _get_cached_ocsp_certs(db)
        LOG.info("ℹ️ OCSP found %d previously cached certificate(s)", len(previous_ocsp_certs))

        # === Early validation: check cache directory permissions ===
        try:
            CONFIGS_SSL_BASE.mkdir(parents=True, exist_ok=True)
            # Verify we can write to the cache directory
            test_file = CONFIGS_SSL_BASE / ".ocsp_write_test"
            try:
                test_file.touch()
                test_file.unlink()
                LOG.debug("✓ OCSP cache directory %s is readable and writable", CONFIGS_SSL_BASE)
            except PermissionError:
                LOG.error("❌ OCSP cache directory %s is not writable (permission denied). Check directory ownership and permissions.", CONFIGS_SSL_BASE)
                return 2
            except Exception as e:
                LOG.error("❌ OCSP could not verify write access to cache directory %s: %s", CONFIGS_SSL_BASE, e)
                return 2
        except Exception as e:
            LOG.error("❌ OCSP could not create cache directory %s: %s", CONFIGS_SSL_BASE, e)
            return 2

        # Check if OCSP stapling is globally disabled
        ocsp_enabled = os.getenv("SSL_USE_OCSP_STAPLING", "yes").lower()
        if ocsp_enabled != "yes":
            LOG.info("🧹 OCSP stapling is globally disabled (SSL_USE_OCSP_STAPLING=%s), cleaning up all caches", ocsp_enabled)
            cleanup_ocsp_cache(db, purge_db=True)
            return 0

        # Wait for scheduler's directory purge to finish after service restart,
        # then restore cached OCSP responses from database to disk.
        # This handles ephemeral storage and post-restart cache directory cleanup.
        ocsp_files_exist = any((CONFIGS_SSL_BASE / d / "ocsp.der").is_file() for d in CONFIGS_SSL_BASE.iterdir()) if CONFIGS_SSL_BASE.is_dir() else False
        if not ocsp_files_exist:
            LOG.info("🔄 OCSP no cached files on disk, waiting 2s for scheduler purge to finish before restoring from database...")
            time.sleep(2)
        restore_ocsp_from_database(db)

        # === Efficiency optimization: skip full refresh if run recently and no changes detected ===
        last_refresh_key = "last_full_refresh"
        now_ts = int(time.time())
        skip_unchanged_ttl_checks = False
        
        if not force_all:
            last_refresh_entry = db.get_job_cache_file(file_name=last_refresh_key, job_name="ocsp-refresh", with_info=True)
            if last_refresh_entry and last_refresh_entry.get("data"):
                try:
                    last_refresh_time = int(last_refresh_entry["data"].decode("utf-8"))
                    if now_ts - last_refresh_time < 1800: # 30 minutes window
                        skip_unchanged_ttl_checks = True
                        LOG.info("ℹ️ OCSP full refresh was recently run (%ds ago), will only process new/changed certificates", now_ts - last_refresh_time)
                except Exception:
                    pass

        # === Collect all OCSP data for batched database writes ===
        all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]] = []
        stashed_failures: List[Tuple[str, bytes]] = []


        # Process Let's Encrypt certificates from database tarball
        le_certs = _load_le_certs_from_db(db)
        if le_certs:
            LOG.info("ℹ️ OCSP loaded %d LE certificate(s) from database", len(le_certs))

            # Separate new certs from existing ones
            new_le_certs = {k: v for k, v in le_certs.items() if k not in previous_ocsp_certs}
            existing_le_certs = {k: v for k, v in le_certs.items() if k in previous_ocsp_certs}

            # For existing certs, check if certificate content has changed
            previous_le_checksums = _get_cert_checksums(db, set(existing_le_certs.keys()))
            changed_le_certs = {}
            unchanged_le_certs = {}

            for cert_name, pem_data in existing_le_certs.items():
                cleaned_pem = _clean_pem(pem_data)
                current_checksum = _calculate_cert_checksum(cleaned_pem)
                previous_checksum = previous_le_checksums.get(cert_name)

                if previous_checksum is None:
                    # No previous checksum found, treat as changed (data loss or first refresh after upgrade)
                    changed_le_certs[cert_name] = pem_data
                    LOG.debug("⚠️ OCSP no previous checksum found for %s, will refresh", cert_name)
                elif current_checksum != previous_checksum:
                    # Certificate content has changed
                    changed_le_certs[cert_name] = pem_data
                    LOG.debug("🔄 OCSP certificate content changed for %s", cert_name)
                else:
                    # Certificate content unchanged
                    unchanged_le_certs[cert_name] = pem_data

            if new_le_certs:
                LOG.info("🆕 OCSP found %d newly issued LE certificate(s): %s", len(new_le_certs), ", ".join(sorted(new_le_certs.keys())))
                stats["le_certs_new"] = len(new_le_certs)

            if changed_le_certs:
                LOG.info("🔄 OCSP found %d LE certificate(s) with changed content: %s", len(changed_le_certs), ", ".join(sorted(changed_le_certs.keys())))
                stats["le_certs_changed"] = len(changed_le_certs)

            if unchanged_le_certs:
                if skip_unchanged_ttl_checks:
                    LOG.info("✓ OCSP skipping TTL checks for %d unchanged LE certificate(s) (recently run)", len(unchanged_le_certs))
                    stats["le_certs_skipped"] = stats.get("le_certs_skipped", 0) + len(unchanged_le_certs)
                else:
                    LOG.info("✓ OCSP checking TTL for %d LE certificate(s) unchanged: %s", len(unchanged_le_certs), ", ".join(sorted(unchanged_le_certs.keys())))

            stats["le_certs_processed"] = len(le_certs)

            # 1. Process newly issued certs (force refresh)
            for cert_name, pem_data in sorted(new_le_certs.items()):
                if check_job_timeout(f"new LE cert {cert_name}"): break
                refresh_job_lock(cert_name)
                res = _process_cert(cert_name, pem_data, db, stats, force_fetch=True)
                all_ocsp_results.append(res)
                if res[1] is None and res[5] and res[6]: # ocsp_der is None AND ocsp_url is present AND was_attempted is True
                    stashed_failures.append((cert_name, pem_data))

            # 2. Process changed certs (force refresh)
            for cert_name, pem_data in sorted(changed_le_certs.items()):
                if check_job_timeout(f"changed LE cert {cert_name}"): break
                refresh_job_lock(cert_name)
                res = _process_cert(cert_name, pem_data, db, stats, force_fetch=True)
                all_ocsp_results.append(res)
                if res[1] is None and res[5] and res[6]:
                    stashed_failures.append((cert_name, pem_data))

            # 3. Process unchanged certs (TTL check only)
            if not skip_unchanged_ttl_checks:
                for cert_name, pem_data in sorted(unchanged_le_certs.items()):
                    if check_job_timeout(f"unchanged LE cert {cert_name}"): break
                    refresh_job_lock(cert_name)
                    res = _process_cert(cert_name, pem_data, db, stats, force_fetch=False)
                    all_ocsp_results.append(res)
                    if res[1] is None and res[5] and res[6]:
                        stashed_failures.append((cert_name, pem_data))

        else:
            LOG.info("ℹ️ OCSP no LE certificates found in database")

        # Check timeout before processing custom certs
        if not check_job_timeout("before custom cert processing"):
            # Process custom certificates from database
            custom_results = process_custom_certs(
                db, 
                stats, 
                lock_fd=lock_fd_main, 
                refresh_fn=refresh_job_lock, 
                timeout_fn=check_job_timeout,
                skip_unchanged_ttl_checks=skip_unchanged_ttl_checks
            )
            all_ocsp_results.extend(custom_results)
            for res in custom_results:
                if res[1] is None and res[5] and res[6]: # ocsp_der is None AND ocsp_url is present AND was_attempted is True
                    stashed_failures.append((res[0], res[4])) # cert_name, pem_data

        # === Final deferred retry for stashed failures ===
        if stashed_failures:
            LOG.info("⏸️ OCSP stashed %d failed fetch(es), waiting 120 seconds before final retry...", len(stashed_failures))

            # Use smaller sleeps to stay responsive and allow timeout checks
            for i in range(120):
                if check_job_timeout("during stashed retry wait"): break
                time.sleep(1)

            if not check_job_timeout("before starting stashed retries"):
                for cert_name, pem_data in stashed_failures:
                    if check_job_timeout(f"stashed retry for {cert_name}"): break
                    LOG.info("🔄 OCSP retrying fetch for stashed failure: %s", cert_name)
                    refresh_job_lock(cert_name)
                    # Force fetch for the final retry attempt
                    all_ocsp_results.append(_process_cert(cert_name, pem_data, db, stats, force_fetch=True))

        # === Check if timeout has been reached and save partial results ===
        if check_job_timeout("after processing phase"):
            LOG.warning("⏱️ OCSP job timeout during processing. Saving partial results (%d cert(s)) to database and disk.", len(all_ocsp_results))
            _persist_ocsp_results_to_db(db, all_ocsp_results, stats)
            _persist_ocsp_results_to_disk(all_ocsp_results, stats)
            # Return early with partial results saved
            elapsed = time.time() - job_start_time
            LOG.warning("📊 OCSP partial job completed in %.3fs with %d results saved", elapsed, len(all_ocsp_results))
            return status

        # === Persist all OCSP responses to database and disk ===
        _persist_ocsp_results_to_db(db, all_ocsp_results, stats)
        _persist_ocsp_results_to_disk(all_ocsp_results, stats)

        # Check timeout before cleanup
        if not check_job_timeout("before orphaned cleanup"):
            # Clean up orphaned OCSP entries for deleted services
            _cleanup_orphaned_ocsp(db, le_certs or {}, stats)

        # Update last full refresh timestamp if we did a full run or found changes
        if db is not None and (not skip_unchanged_ttl_checks or any(r[1] is not None for r in all_ocsp_results)):
            try:
                db.upsert_job_cache(
                    service_id=None,
                    file_name=last_refresh_key,
                    data=str(now_ts).encode("utf-8"),
                    job_name="ocsp-refresh",
                    checksum=hashlib.sha256(str(now_ts).encode("utf-8")).hexdigest(),
                )
                LOG.debug("✓ OCSP updated last full refresh timestamp to %d", now_ts)
            except Exception as e:
                LOG.debug("⚠️ OCSP could not update last full refresh timestamp: %s", e)

        # End-of-job verification: ensure OCSP files match database checksums
        # Restores missing files from database
        if not check_job_timeout("before final verification"):
            # Skip expensive verification if nothing changed and we were in "skip" mode
            if skip_unchanged_ttl_checks and not any(r[1] is not None for r in all_ocsp_results):
                LOG.info("🔍 OCSP skipping final verification (nothing changed and recently run)")
            else:
                LOG.info("🔍 OCSP running end-of-job verification and restoration...")
                _verify_and_restore_ocsp_files(db, stats)

        # Decide exit status based on results
        if stats["errors"] > 0:
            status = 2

        if stats["errors"] == 0:
            LOG.info("✓ OCSP refresh job completed successfully")
        else:
            LOG.warning("⚠️ OCSP refresh job completed with %d error(s)", stats["errors"])

        elapsed = time.time() - job_start_time
        LOG.info(
            "📊 Statistics (completed in %.3fs): 🔐 LE certs=%d (skipped=%d, no OCSP=%d) | 🔐 Custom certs=%d (unchanged=%d, skipped=%d, no OCSP=%d) | 🔄 Fetched=%d | ✓ Cached=%d | 🧹 Orphaned=%d | 🔍 Verified=%d (restored=%d, corrected=%d) | ❌ Errors=%d",
            elapsed,
            stats["le_certs_processed"],
            stats["le_certs_skipped"],
            stats["le_certs_no_ocsp"],
            stats["custom_certs_processed"],
            stats.get("custom_certs_unchanged", 0),
            stats["custom_certs_skipped"],
            stats["custom_certs_no_ocsp"],
            stats["ocsp_fetched_responses"],
            stats["ocsp_cached_responses"],
            stats.get("orphaned_cleaned", 0),
            stats.get("ocsp_verified", 0),
            stats.get("ocsp_restored", 0),
            stats.get("ocsp_corrected", 0),
            stats["errors"],
        )
        return status
    except BaseException as e:
        LOG.exception("❌ OCSP exception in ocsp-refresh.py")
        LOG.error("❌ OCSP exception while running ocsp-refresh.py: %s", e)
        return 2
    finally:
        # Always release the main lock
        _release_cert_lock(lock_fd_main)


# run it
sys_exit(main())
