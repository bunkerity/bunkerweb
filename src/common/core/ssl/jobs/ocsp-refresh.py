#!/usr/bin/env python3

import argparse
import fcntl
import hashlib
import io
import json
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
from collections import OrderedDict
from sys import exit as sys_exit, path as sys_path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp as x509_ocsp
from cryptography.x509 import AuthorityInformationAccess, SubjectAlternativeName, TLSFeature, TLSFeatureType
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


def _truncate_log(msg: str, max_len: int = 2048) -> str:
    """Truncate log message to max_len characters, adding ellipsis if truncated."""
    if isinstance(msg, str) and len(msg) > max_len:
        return msg[:max_len - 3] + "..."
    return str(msg) if msg is not None else ""


# Wrapper functions to enforce 2048 character limit on all log messages
def log_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log at DEBUG level with 2048 char limit."""
    try:
        formatted = (msg % args) if args else msg
    except Exception:
        formatted = f"{msg} {args}"
    LOG.debug(_truncate_log(formatted), **kwargs)


def log_info(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log at INFO level with 2048 char limit."""
    try:
        formatted = (msg % args) if args else msg
    except Exception:
        formatted = f"{msg} {args}"
    LOG.info(_truncate_log(formatted), **kwargs)


def log_warning(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log at WARNING level with 2048 char limit."""
    try:
        formatted = (msg % args) if args else msg
    except Exception:
        formatted = f"{msg} {args}"
    LOG.warning(_truncate_log(formatted), **kwargs)


def log_error(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log at ERROR level with 2048 char limit."""
    try:
        formatted = (msg % args) if args else msg
    except Exception:
        formatted = f"{msg} {args}"
    LOG.error(_truncate_log(formatted), **kwargs)


def log_critical(msg: str, *args: Any, **kwargs: Any) -> None:
    """Log at CRITICAL level with 2048 char limit."""
    try:
        formatted = (msg % args) if args else msg
    except Exception:
        formatted = f"{msg} {args}"
    LOG.critical(_truncate_log(formatted), **kwargs)


status = 0

# Use scheduler-managed cache directory (automatically synced from database on restart)
CONFIGS_SSL_BASE = Path(os.sep, "var", "cache", "bunkerweb", "ssl")
MIN_TTL = 4500  # 75 minutes: minimum safety threshold. Smart refresh uses max(MIN_TTL, 20% of response lifetime)
OPENSSL_BIN = "/usr/bin/openssl"

_FINGERPRINT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OCSP_RESPONDER_DNS_CACHE_MAX = 256
DNS_CACHE_TTL = 300  # 5 minutes: limit poisoning / stale DNS impact during a job
_OCSP_RESPONDER_DNS_CACHE: "OrderedDict[str, Tuple[List[str], float]]" = OrderedDict()


def _is_safe_ip_str(ip_str: str) -> bool:
    """
    Check whether an IP string is safe for outbound connections (SSRF defense).
    Mirrors the allow/deny logic in `is_safe_url()` but for a raw IP.
    """
    import ipaddress

    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return not (
            ip_obj.is_unspecified
            or ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
        )
    except Exception:
        return False


def _normalize_fingerprint(fingerprint: Optional[str]) -> Optional[str]:
    """
    Normalize an OCSP cache fingerprint into a lowercase 64-hex string.
    Returns None if fingerprint does not match the expected format.
    """
    if not fingerprint:
        return None
    fp = str(fingerprint).strip()
    if not _FINGERPRINT_RE.match(fp):
        return None
    return fp.lower()


def _resolve_hostname_to_ips(hostname: str, port: int) -> List[str]:
    """
    Resolve `hostname` to a unique list of IP strings (A/AAAA) for `port`.
    Filters out non-IP / unsafe results (SSRF defense).
    """
    import socket

    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except Exception:
        return []

    ips: set = set()
    for info in addr_info:
        ip_str = info[4][0]
        if isinstance(ip_str, str) and _is_safe_ip_str(ip_str):
            ips.add(ip_str)

    return sorted(ips)


def _get_ocsp_responder_ips(ocsp_url: str, default_port: int) -> Tuple[str, List[str]]:
    """
    Return (hostname, ips) for a given OCSP responder URL.
    - hostname is the original DNS name (used for TLS SNI + cert validation).
    - ips are resolved and safe IPs used for connecting.
    """
    parsed = urlparse(ocsp_url)
    hostname = parsed.hostname or ""
    if not hostname:
        return "", []

    if hostname in _OCSP_RESPONDER_DNS_CACHE:
        # Refresh LRU position
        ips, cached_at = _OCSP_RESPONDER_DNS_CACHE[hostname]
        if time.time() - cached_at < DNS_CACHE_TTL:
            _OCSP_RESPONDER_DNS_CACHE.move_to_end(hostname)
            return hostname, ips
        # Expired — re-resolve
        try:
            del _OCSP_RESPONDER_DNS_CACHE[hostname]
        except KeyError:
            pass

    port = parsed.port or default_port
    ips = _resolve_hostname_to_ips(hostname, port)
    _OCSP_RESPONDER_DNS_CACHE[hostname] = (ips, time.time())
    # Bounded cache to avoid unbounded memory growth.
    while len(_OCSP_RESPONDER_DNS_CACHE) > _OCSP_RESPONDER_DNS_CACHE_MAX:
        _OCSP_RESPONDER_DNS_CACHE.popitem(last=False)
    return hostname, ips


def _read_http_response_body(conn: Any, max_body_bytes: int) -> Tuple[int, bytes]:
    """
    Read an HTTP response from a (possibly SSL-wrapped) socket-like object.
    Returns (status_code, body_bytes). Body is capped to `max_body_bytes`.
    """
    status_code = 0
    body = b""
    buffer = b""

    # Read headers
    while b"\r\n\r\n" not in buffer:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buffer += chunk
        if len(buffer) > 1024 * 1024:
            # Unreasonably large headers
            raise RuntimeError("HTTP headers too large")

    if b"\r\n\r\n" not in buffer:
        raise RuntimeError("Invalid HTTP response (missing header terminator)")

    header_bytes, remainder = buffer.split(b"\r\n\r\n", 1)
    header_lines = header_bytes.split(b"\r\n")
    if not header_lines:
        raise RuntimeError("Invalid HTTP response (no status line)")

    # Example: b"HTTP/1.1 200 OK"
    parts = header_lines[0].split(b" ", 2)
    if len(parts) >= 2:
        try:
            status_code = int(parts[1].decode("ascii", errors="ignore"))
        except Exception:
            status_code = 0

    # Parse Content-Length if present (best-effort)
    content_length = None
    for line in header_lines[1:]:
        if b":" not in line:
            continue
        k, v = line.split(b":", 1)
        if k.strip().lower() == b"content-length":
            try:
                content_length = int(v.strip().decode("ascii", errors="ignore"))
            except Exception:
                content_length = None

    body = remainder
    if content_length is not None:
        # Cap the amount we read to avoid memory issues
        target = min(content_length, max_body_bytes)
        while len(body) < target:
            chunk = conn.recv(min(4096, target - len(body)))
            if not chunk:
                break
            body += chunk
            if len(body) >= target:
                body = body[:target]
                break
    else:
        # Read until EOF but cap the total body size
        while len(body) < max_body_bytes:
            chunk = conn.recv(min(4096, max_body_bytes - len(body)))
            if not chunk:
                break
            body += chunk
        body = body[:max_body_bytes]

    return status_code, body


def _post_ocsp_over_ip_with_sni(
    ocsp_url: str,
    ocsp_request_data: bytes,
    ocsp_hostname: str,
    ip_str: str,
    timeout: int,
) -> Tuple[Optional[bytes], Optional[int], str]:
    """
    Perform an OCSP HTTP POST by connecting to `ip_str` but using TLS SNI and
    certificate validation for `ocsp_hostname`.
    """
    parsed = urlparse(ocsp_url)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return None, None, ""

    import http.client as http_client
    import socket

    host_port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    headers = {
        "Content-Type": "application/ocsp-request",
        "User-Agent": "BunkerWeb OCSP Fetcher (SSRF-Protected)",
        "Connection": "close",
    }

    conn: Any = None
    sock: Optional[socket.socket] = None
    wrapped_sock: Any = None
    try:
        if scheme == "https":
            ssl_context = ssl.create_default_context()
            # Use the original hostname for SNI + certificate validation, but connect to the resolved IP.
            conn = http_client.HTTPSConnection(
                ocsp_hostname,
                port=host_port,
                timeout=timeout,
                context=ssl_context,
            )
            sock = socket.create_connection((ip_str, host_port), timeout=timeout)
            sock.settimeout(timeout)
            wrapped_sock = ssl_context.wrap_socket(sock, server_hostname=ocsp_hostname)
            conn.sock = wrapped_sock
        else:
            conn = http_client.HTTPConnection(
                ocsp_hostname,
                port=host_port,
                timeout=timeout,
            )
            sock = socket.create_connection((ip_str, host_port), timeout=timeout)
            sock.settimeout(timeout)
            conn.sock = sock

        conn.request("POST", path, body=ocsp_request_data, headers=headers)
        resp = conn.getresponse()
        status_code = resp.status
        reason = getattr(resp, "reason", "") or ""
        body = resp.read(102400)
        try:
            resp.close()
        except Exception:
            pass

        if status_code < 200 or status_code >= 300:
            log_warning(
                "⚠️ OCSP HTTP status %d from %s (%s) for %s",
                status_code,
                ocsp_hostname,
                ip_str,
                ocsp_url,
            )
            return None, status_code, reason

        return body, status_code, reason
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def _log_ocsp_responder_dns_table() -> None:
    """
    Log a consolidated uniq table (OCSP responder hostnames -> resolved IPs).
    """
    if not _OCSP_RESPONDER_DNS_CACHE:
        log_debug("ℹ️ OCSP responder DNS table: no DNS lookups performed")
        return

    # Print as a Markdown-like table for easy copy/paste
    rows = []
    for hostname, (ips, _) in sorted(_OCSP_RESPONDER_DNS_CACHE.items()):
        ip_list = ", ".join(ips) if ips else ""
        rows.append(f"| {hostname} | {ip_list} |")

    log_info("📇 OCSP responder DNS table (uniq responders):\n| Responder Hostname | Resolved IPs |\n|---|---|\n%s", "\n".join(rows))


def _get_sharded_ocsp_path(fingerprint: str) -> Path:
	"""
	Get sharded directory path for OCSP response storage using two-level hex tree sharding.
	Creates a tree structure: {hex1}/{hex2}/{fingerprint}/ where hex1 and hex2 are individual
	hex digits from the fingerprint, distributing 256 subdirectories across 16 first-level dirs.

	Args:
	    fingerprint: SHA256 fingerprint (lowercase hex string, 64 chars)

	Returns:
	    Path: /var/cache/bunkerweb/ssl/{hex1}/{hex2}/{full_fingerprint}/

	Example:
	    fingerprint: 089433bd22ca2b9536b597a9fc7ca86cdd1d1df0193caaa205043b40f1ea435b
	    returns: /var/cache/bunkerweb/ssl/0/8/089433bd22ca2b9536b597a9fc7ca86cdd1d1df0193caaa205043b40f1ea435b/
	"""
	normalized = _normalize_fingerprint(fingerprint)
	if not normalized:
		return CONFIGS_SSL_BASE / "unknown"
	# Use first hex digit (0-f) and second hex digit (0-f) as tree levels
	hex1 = normalized[0]
	hex2 = normalized[1]
	return CONFIGS_SSL_BASE / hex1 / hex2 / normalized


def _init_sharded_ocsp_directories() -> bool:
	"""
	Initialize tree-structured sharded subdirectories for OCSP response distribution.
	Creates 16 first-level (hex1: 0-f) × 16 second-level (hex2: 0-f) = 256 total directories.
	Structure: /var/cache/bunkerweb/ssl/{hex1}/{hex2}/
	Called at job startup to ensure directory structure exists.

	Returns:
	    True if all directories initialized successfully, False on error
	"""
	try:
		hex_digits = "0123456789abcdef"
		failed_dirs = []

		# Create tree structure: 16 first-level dirs × 16 second-level dirs = 256 total
		for hex1 in hex_digits:
			for hex2 in hex_digits:
				dir_path = CONFIGS_SSL_BASE / hex1 / hex2
				try:
					dir_path.mkdir(parents=True, exist_ok=True)
				except Exception as e:
					log_error("❌ OCSP failed to create directory %s: %s", dir_path, e)
					failed_dirs.append((f"{hex1}/{hex2}", str(e)))

		if failed_dirs:
			log_warning(
				"⚠️ OCSP failed to create %d director(ies): %s",
				len(failed_dirs),
				", ".join([f"{d[0]}({d[1]})" for d in failed_dirs[:3]])  # Show first 3 failures
			)
			return False

		log_debug("✓ OCSP initialized tree-structured directories (16×16) for OCSP caching")
		return True

	except Exception as e:
		log_error("❌ OCSP exception during sharded directory initialization: %s", e)
		return False


def _sanitize_filename(name: str) -> str:
    """
    Replace characters that are invalid in filenames or could cause issues.
    Specifically replaces '*' with '_wildcard_' for wildcard certificates.
    """
    return name.replace("*", "_wildcard_")


def _get_cert_pubkey_fingerprint(cert_data: bytes) -> Optional[str]:
    """
    Compute SHA256 fingerprint of certificate's public key (RFC 7469 format).
    Used for fingerprint-based OCSP response storage and matching.

    Supports both PEM and DER certificate formats.

    Args:
        cert_data: Certificate in PEM or DER format (bytes)

    Returns:
        Lowercase hex string (64 chars) of SHA256 fingerprint, or None on error
    """
    if not cert_data:
        return None

    cert = None
    try:
        # Try PEM format first (most common)
        try:
            cert = x509.load_pem_x509_certificate(cert_data)
            log_debug("✓ OCSP parsed certificate as PEM format")
        except Exception as pem_err:
            # Fallback to DER format
            try:
                cert = x509.load_der_x509_certificate(cert_data)
                log_debug("✓ OCSP parsed certificate as DER format")
            except Exception as der_err:
                log_warning("⚠️ OCSP certificate is neither PEM nor DER format: PEM error: %s, DER error: %s",
                           str(pem_err)[:100], str(der_err)[:100])
                return None

        # Extract public key
        public_key = cert.public_key()
        # Serialize public key to DER format (standard for fingerprinting)
        pubkey_der = public_key.public_bytes(
            encoding=Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        # Compute SHA256 fingerprint (lowercase for consistency)
        fingerprint = hashlib.sha256(pubkey_der).hexdigest().lower()
        log_debug("✓ OCSP computed certificate fingerprint: %s", fingerprint[:16] + "...")
        return fingerprint
    except Exception as e:
        log_warning("⚠️ OCSP could not compute certificate fingerprint: %s", e)
        return None


def _acquire_cert_lock(cert_name: str, timeout: int = 300, stale_threshold: int = 600) -> Optional[int]:
    """
    Acquire a file-based lock for a specific certificate to prevent race conditions
    when multiple scheduler instances fetch OCSP responses concurrently.

    Lock files are stored in a non-world-writable runtime directory (preferred: /run/bunkerweb,
    then /var/run/bunkerweb, then a safe fallback under /tmp). Timestamp-based staleness detection
    is used for identifying crashed/abandoned locks.
    If a lock file hasn't been updated in stale_threshold seconds, it's considered stale
    (indicating the previous process crashed or is hung).

    Args:
        cert_name: Certificate identifier
        timeout: Maximum seconds to wait for lock acquisition (default 300 = 5 minutes)
        stale_threshold: Lock file age (seconds) to consider it stale (default 600 = 10 minutes)

    Returns:
        File descriptor on success, None if lock unavailable or timed out
    """
    # Per-certificate lock is keyed by the certificate public key fingerprint.
    # This avoids host/cert-name collisions and matches the fingerprint-based OCSP cache layout.
    cert_fp = _normalize_fingerprint(cert_name)
    lock_dir: Optional[Path] = None
    lock_file: Optional[Path] = None

    # Fingerprint-based lock dir: root-folder/ssl/x/x (2-level sharding).
    if cert_fp and cert_name != "main":
        lock_dir = CONFIGS_SSL_BASE / cert_fp[0] / cert_fp[1]
        lock_file = lock_dir / f"ocsp-{cert_fp}.lock"
        try:
            lock_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            if lock_dir.is_symlink():
                log_error("❌ OCSP fingerprint lock directory %s is a symlink (refusing).", lock_dir)
                return None
            st = lock_dir.stat()
            if st.st_mode & 0o022:
                log_error(
                    "❌ OCSP fingerprint lock directory %s has unsafe permissions (mode=%o).",
                    lock_dir,
                    st.st_mode & 0o777,
                )
                return None
        except Exception as e:
            log_debug("⚠️ OCSP could not prepare fingerprint lock directory %s: %s", lock_dir, e)
            return None

    # Fallback (e.g. cert_name == "main" or unexpected non-fingerprint input): runtime lock dir.
    if lock_file is None or lock_dir is None:
        # Lock directories must not be attacker-controlled.
        # `/tmp` is world-writable, so we prefer runtime dirs first and only fall back
        # to `/tmp` if it's not a symlink and has safe permissions.
        lock_dir_candidates = [
            Path(os.sep, "run", "bunkerweb"),
            Path(os.sep, "var", "run", "bunkerweb"),
            Path(os.sep, "tmp", "bunkerweb"),
        ]

        for candidate in lock_dir_candidates:
            try:
                candidate.mkdir(parents=True, exist_ok=True, mode=0o700)
            except Exception as e:
                log_debug("⚠️ OCSP lock candidate mkdir failed for %s: %s", candidate, e)
                continue

            try:
                if candidate.is_symlink():
                    log_error("❌ OCSP lock directory %s is a symlink (refusing).", candidate)
                    continue

                st = candidate.stat()
                # Reject world/group-writable directories.
                if st.st_mode & 0o022:
                    log_error("❌ OCSP lock directory %s has unsafe permissions (mode=%o).", candidate, st.st_mode & 0o777)
                    continue

                lock_dir = candidate
                break
            except Exception as e:
                log_debug("⚠️ OCSP lock candidate stat failed for %s: %s", candidate, e)
                continue

        if not lock_dir:
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
                    log_warning(
                        "⚠️ OCSP detected stale lock for %s (age %.0fs > threshold %ds). "
                        "Previous process may have crashed. Proceeding without unlinking to avoid a race.",
                        cert_name, age, stale_threshold
                    )
                    # Do not unlink: another process may have just acquired the lock
                    # after updating mtime, and deleting here would be a race.
        except Exception as e:
            log_debug("⚠️ OCSP stale lock detection failed for %s: %s", lock_file, e)

        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_WRONLY, 0o600)
            # Try non-blocking lock acquisition (LOCK_NB)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Lock acquired successfully—write timestamp to detect stale locks
                try:
                    os.write(fd, str(int(time.time())).encode())
                except Exception as e:
                    log_debug("⚠️ OCSP could not write lock timestamp for %s: %s", cert_name, e)
                return fd
            except BlockingIOError:
                # Lock held by another process, close fd and exit or retry
                os.close(fd)

                if cert_name == "main":
                    # For main lock, fail fast: another OCSP job is already running
                    log_error(
                        "❌ OCSP job is already running (another instance holds the lock). "
                        "Exiting to avoid concurrent operations."
                    )
                    return None

                # For cert-specific locks, retry with timeout
                elapsed = time.time() - start_time
                remaining_time = timeout - elapsed
                if remaining_time > 0:
                    log_debug("⏳ OCSP waiting for lock on %s (%.0fs remaining)...", cert_name, remaining_time)
                    time.sleep(0.5)
                    continue
                else:
                    break
        except Exception as e:
            log_debug("⚠️ OCSP lock acquisition attempt failed for %s: %s", cert_name, e)
            time.sleep(0.5)

    # Timeout reached: log clear message based on lock type
    if cert_name == "main":
        chosen_lock_dir = str(lock_dir) if lock_dir else "/tmp/bunkerweb"
        log_error(
            "❌ OCSP job timed out waiting for the main lock (%ds timeout). "
            "Another OCSP job is still running. This may indicate a hung or very slow job. "
            "Check for stale lock files: rm -f %s/ocsp*.lock",
            chosen_lock_dir,
            timeout,
        )
    else:
        log_warning(
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
    
    cert_fp = _normalize_fingerprint(cert_name)
    lock_file_name: str
    lock_file: Optional[Path] = None
    lock_dir_candidates = [
        Path(os.sep, "run", "bunkerweb"),
        Path(os.sep, "var", "run", "bunkerweb"),
        Path(os.sep, "tmp", "bunkerweb"),
    ]

    # Fingerprint-based lock location: root-folder/ssl/x/x
    if cert_fp and cert_name != "main":
        lock_file = CONFIGS_SSL_BASE / cert_fp[0] / cert_fp[1] / f"ocsp-{cert_fp}.lock"
    else:
        sanitized_name = _sanitize_filename(cert_name)
        lock_file_name = f"ocsp-{sanitized_name}.lock"
    try:
        # Unlink while still holding the flock to avoid a release race where
        # another process could acquire the same lock file name before we unlock.
        if lock_file is not None:
            try:
                if lock_file.exists() and not lock_file.is_symlink():
                    lock_file.unlink()
            except Exception as e:
                log_debug("⚠️ OCSP fingerprint lock file unlink failed for %s: %s", lock_file, e)
        else:
            for lock_dir in lock_dir_candidates:
                lock_file = lock_dir / lock_file_name
                try:
                    if lock_file.exists() and not lock_file.is_symlink():
                        lock_file.unlink()
                        break
                except Exception as e:
                    log_debug("⚠️ OCSP lock file unlink failed for %s: %s", lock_file, e)
                    continue

        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except Exception as e:
        log_debug("⚠️ OCSP could not release lock for %s: %s", cert_name, e)


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
        log_debug("🔒 OCSP refreshed lock timestamp for %s", cert_name)
    except Exception as e:
        log_debug("⚠️ OCSP could not refresh lock timestamp for %s: %s", cert_name, e)


def _cleanup_stale_locks(stale_threshold: int = 300) -> None:
    """
    Clean up stale lock files from previous crashed/aborted jobs at startup.
    This is a defensive measure to prevent lock accumulation from crashed processes.

    Args:
        stale_threshold: Lock age (seconds) to consider stale (default 300 = 5 minutes)
    """
    current_time = time.time()
    cleaned = 0

    lock_dir_candidates = [
        Path(os.sep, "run", "bunkerweb"),
        Path(os.sep, "var", "run", "bunkerweb"),
        Path(os.sep, "tmp", "bunkerweb"),
    ]

    for lock_dir in lock_dir_candidates:
        if not lock_dir.exists():
            continue
        try:
            if lock_dir.is_symlink():
                continue
            st = lock_dir.stat()
            # Reject world/group-writable directories.
            if st.st_mode & 0o022:
                continue
        except Exception as e:
            log_debug("⚠️ OCSP lock directory stat failed for %s: %s", lock_dir, e)
            continue

        for lock_file in lock_dir.glob("ocsp-*.lock"):
            try:
                mtime = lock_file.stat().st_mtime
                age = current_time - mtime
                if age > stale_threshold:
                    # Only unlink if we can also acquire the lock.
                    # This avoids the stale-cleanup unlink race where another process
                    # is legitimately holding the lock.
                    fd = None
                    try:
                        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Unlink while the lock is still held to avoid a tiny race
                        # between unlocking and deleting the file.
                        try:
                            lock_file.unlink()
                        except Exception as e:
                            log_debug("⚠️ OCSP could not unlink stale lock file %s: %s", lock_file.name, e)

                        cleaned += 1
                        log_debug("🧹 OCSP removed stale lock file %s (age %.0fs)", lock_file.name, age)
                        fcntl.flock(fd, fcntl.LOCK_UN)
                        os.close(fd)
                        fd = None
                    except BlockingIOError:
                        if fd is not None:
                            try:
                                os.close(fd)
                            except Exception as e:
                                log_debug("⚠️ OCSP could not close stale lock fd: %s", e)
                        # Another process is holding the lock.
                        continue
                    except Exception as e:
                        if fd is not None:
                            try:
                                os.close(fd)
                            except Exception as close_e:
                                log_debug("⚠️ OCSP could not close stale lock fd after exception: %s", close_e)
                        log_debug("⚠️ OCSP failed to unlink stale lock file %s (age %.0fs): %s", lock_file.name, age, e)
                        continue
            except Exception as e:
                log_debug("⚠️ OCSP could not clean lock file %s: %s", lock_file.name, e)

    # Fingerprint-based lock cleanup (root-folder/ssl/x/x)
    if CONFIGS_SSL_BASE.is_dir():
        try:
            for lock_dir in CONFIGS_SSL_BASE.glob("*/*"):
                try:
                    if not lock_dir.is_dir() or lock_dir.is_symlink():
                        continue
                    st = lock_dir.stat()
                    if st.st_mode & 0o022:
                        continue
                except Exception as e:
                    log_debug("⚠️ OCSP lock directory stat failed for fingerprint shard %s: %s", lock_dir, e)
                    continue

                for lock_file in lock_dir.glob("ocsp-*.lock"):
                    try:
                        mtime = lock_file.stat().st_mtime
                        age = current_time - mtime
                        if age <= stale_threshold:
                            continue

                        fd = None
                        try:
                            fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            try:
                                lock_file.unlink()
                            except Exception as e:
                                log_debug("⚠️ OCSP could not unlink stale fingerprint lock file %s: %s", lock_file.name, e)

                            cleaned += 1
                            fcntl.flock(fd, fcntl.LOCK_UN)
                            os.close(fd)
                            fd = None
                        except BlockingIOError:
                            if fd is not None:
                                try:
                                    os.close(fd)
                                except Exception as close_e:
                                    log_debug("⚠️ OCSP could not close stale fingerprint lock fd: %s", close_e)
                            continue
                        except Exception as e:
                            if fd is not None:
                                try:
                                    os.close(fd)
                                except Exception as close_e:
                                    log_debug("⚠️ OCSP could not close stale fingerprint lock fd after exception: %s", close_e)
                            log_debug("⚠️ OCSP failed to cleanup stale fingerprint lock file %s: %s", lock_file.name, e)
                    except Exception as e:
                        log_debug("⚠️ OCSP could not stat stale fingerprint lock file %s: %s", lock_file, e)
        except Exception as e:
            log_debug("⚠️ OCSP fingerprint lock cleanup failed: %s", e)

    if cleaned > 0:
        log_info("🧹 OCSP cleaned up %d stale lock file(s) from previous runs", cleaned)


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
            log_warning("⚠️ SSRF protection: blocked URL with disallowed scheme: %s", url)
            return False

        hostname = parsed.hostname
        if not hostname:
            log_warning("⚠️ SSRF protection: blocked URL with no hostname: %s", url)
            return False

        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            log_warning("⚠️ SSRF protection: DNS resolution failed for %s", hostname)
            return False

        for info in addr_info:
            ip_str = info[4][0]
            if not _is_safe_ip_str(ip_str):
                log_warning("⚠️ SSRF protection: blocked request to %s (resolves to unsafe IP %s)", hostname, ip_str)
                return False

        return True
    except Exception as e:
        log_debug("SSRF protection: error validating URL %s: %s", url, e)
        return False


def extract_ocsp_url(pem_data: bytes, cert_name: str = "") -> Optional[str]:
    """
    Extract OCSP responder URL from PEM certificate data using the cryptography library.
    Validates the URL scheme is http:// or https://.
    Returns OCSP responder URL if present and valid, else None.
    """
    log_debug("🔒 OCSP checking support for certificate %s", cert_name)
    try:
        cert = x509.load_pem_x509_certificate(pem_data)

        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia_value = cast(AuthorityInformationAccess, aia.value)
        for access_description in aia_value:
            if access_description.access_method == AuthorityInformationAccessOID.OCSP:
                url = access_description.access_location.value
                parsed = urlparse(url)
                if parsed.scheme not in ("http", "https"):
                    log_warning("⚠️ OCSP URL has invalid scheme for %s: %s", cert_name, url)
                    return None
                log_debug("🌐 OCSP found responder URL for %s: %s", cert_name, url)
                return url

        log_debug("🔒 OCSP no responder URL advertised in %s", cert_name)
        return None
    except x509.ExtensionNotFound:
        log_debug("🔒 OCSP no AIA extension found in %s", cert_name)
        return None
    except Exception as e:
        log_debug("🔒 OCSP failed to extract OCSP URL from %s: %s", cert_name, e)
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
                log_debug("🌐 OCSP fetching issuer certificate from AIA: %s", issuer_url)
    
                # Pin DNS resolution before connecting to mitigate DNS rebinding.
                # We'll resolve the hostname to safe IPs and connect to those IPs directly
                # while preserving SNI + certificate validation against the original hostname.
                issuer_hostname = parsed.hostname
                if not issuer_hostname:
                    continue

                default_port = 443 if parsed.scheme == "https" else 80
                port = parsed.port or default_port
                ips = _resolve_hostname_to_ips(issuer_hostname, port)
                if not ips:
                    log_warning(
                        "⚠️ OCSP could not resolve safe IPs for AIA issuer hostname %s (%s)",
                        issuer_hostname,
                        issuer_url,
                    )
                    continue

                path = parsed.path or "/"
                if parsed.query:
                    path = f"{path}?{parsed.query}"

                import http.client as http_client
                import socket

                # Try each resolved IP (first successful response wins).
                for ip_str in ips:
                    conn: Any = None
                    sock: Optional[socket.socket] = None
                    wrapped_sock: Any = None
                    try:
                        if parsed.scheme == "https":
                            ssl_context = ssl.create_default_context()
                            conn = http_client.HTTPSConnection(
                                issuer_hostname,
                                port=port,
                                timeout=10,
                                context=ssl_context,
                            )
                            sock = socket.create_connection((ip_str, port), timeout=10)
                            sock.settimeout(10)
                            wrapped_sock = ssl_context.wrap_socket(sock, server_hostname=issuer_hostname)
                            conn.sock = wrapped_sock
                        else:
                            conn = http_client.HTTPConnection(
                                issuer_hostname,
                                port=port,
                                timeout=10,
                            )
                            sock = socket.create_connection((ip_str, port), timeout=10)
                            sock.settimeout(10)
                            conn.sock = sock

                        conn.request(
                            "GET",
                            path,
                            headers={"User-Agent": "BunkerWeb OCSP Fetcher (SSRF-Protected)", "Connection": "close"},
                        )
                        resp = conn.getresponse()
                        status_code = resp.status
                        if status_code < 200 or status_code >= 300:
                            log_warning(
                                "⚠️ OCSP AIA issuer HTTP %d for %s from %s (%s -> %s)",
                                status_code,
                                cert_name,
                                issuer_url,
                                issuer_hostname,
                                ip_str,
                            )
                            try:
                                resp.close()
                            except Exception as close_e:
                                log_debug(
                                    "⚠️ OCSP AIA issuer: failed to close HTTP response (%s -> %s): %s",
                                    issuer_hostname,
                                    ip_str,
                                    close_e,
                                )
                            continue

                        issuer_der = resp.read(1_048_576)  # Cap at 1MB
                        try:
                            resp.close()
                        except Exception as close_e:
                            log_debug(
                                "⚠️ OCSP AIA issuer: failed to close HTTP response after read (%s -> %s): %s",
                                issuer_hostname,
                                ip_str,
                                close_e,
                            )

                        if not issuer_der:
                            continue

                        # Try DER first (most common for caIssuers), then PEM
                        try:
                            return x509.load_der_x509_certificate(issuer_der)
                        except Exception:
                            return x509.load_pem_x509_certificate(issuer_der)
                    except Exception as e:
                        log_warning(
                            "⚠️ OCSP failed to fetch issuer from AIA for %s from %s (%s -> %s): %s",
                            cert_name,
                            issuer_url,
                            issuer_hostname,
                            ip_str,
                            e,
                        )
                    finally:
                        try:
                            if conn is not None:
                                conn.close()
                        except Exception as close_e:
                            log_debug(
                                "⚠️ OCSP AIA issuer: failed to close HTTP connection (%s -> %s): %s",
                                issuer_hostname,
                                ip_str,
                                close_e,
                            )
    except x509.ExtensionNotFound:
        log_debug("🔒 OCSP no AIA extension in leaf cert for %s", cert_name)
    except Exception as e:
        log_warning("⚠️ OCSP failed to fetch issuer from AIA for %s: %s", cert_name, e)
    return None


def _extract_cert_metadata(pem_data: bytes, cert_name: str = "") -> Dict[str, Any]:
    """
    Extract OCSP-related metadata from a certificate PEM:
    - serial (hex string)
    - ocsp_url (if present)
    - must_staple (bool via TLS Feature extension, OID 1.3.6.1.5.5.7.1.24)

    This metadata is stored alongside ocsp.der so NGINX Lua can make
    Must-Staple and OCSP decisions even when only a parsed certificate
    object is available at runtime.
    """
    meta: Dict[str, Any] = {
        "serial": None,
        "ocsp_url": None,
        "must_staple": False,
    }

    try:
        cert = x509.load_pem_x509_certificate(pem_data)
    except Exception as e:
        log_debug("🔒 OCSP metadata: failed to parse PEM for %s: %s", cert_name, e)
        return meta

    try:
        serial_int = cert.serial_number
        meta["serial"] = format(serial_int, "X")
    except Exception as e:
        log_debug("🔒 OCSP metadata: failed to extract serial for %s: %s", cert_name, e)

    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia_value = cast(AuthorityInformationAccess, aia.value)
        for access_description in aia_value:
            if access_description.access_method == AuthorityInformationAccessOID.OCSP:
                meta["ocsp_url"] = access_description.access_location.value
                break
    except x509.ExtensionNotFound:
        log_debug("🔒 OCSP metadata: no AIA/OCSP URL for %s", cert_name)
    except Exception as e:
        log_debug("🔒 OCSP metadata: failed to extract OCSP URL for %s: %s", cert_name, e)

    try:
        tls_feature_ext = cert.extensions.get_extension_for_oid(ExtensionOID.TLS_FEATURE)
        tls_features = cast(TLSFeature, tls_feature_ext.value)
        for feature in tls_features:
            if feature == TLSFeatureType.status_request:
                meta["must_staple"] = True
                break
    except x509.ExtensionNotFound:
        # No TLS Feature extension -> no Must-Staple
        pass
    except Exception as e:
        log_debug("🔒 OCSP metadata: failed to inspect TLS Feature extension for %s: %s", cert_name, e)

    return meta


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
                log_debug("✓ OCSP selected issuer certificate index %d for %s", idx, cert_name)
                return leaf, candidate

        # Fallback: use the second certificate
        log_warning(
            "⚠️ OCSP could not verify issuer chain for %s by DN match, falling back to second certificate",
            cert_name,
        )
        return leaf, certs[1]

    # Single cert (no chain): try to fetch issuer from AIA caIssuers URL
    log_debug("🔄 OCSP single cert for %s, attempting to fetch issuer from AIA caIssuers", cert_name)
    issuer = _fetch_issuer_from_aia(leaf, cert_name)
    if issuer:
        return leaf, issuer

    raise RuntimeError(f"fullchain for {cert_name} does not contain issuer and AIA fetch failed")


# Default OCSP TTL fallback (1 day) if Next Update is missing
DEFAULT_OCSP_TTL = 86400

# Backoff duration after certain HTTP errors (e.g. responder temporarily bad)
HTTP_ERROR_BACKOFF_SECONDS = 300  # 5 minutes


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
        log_debug("⚡ OCSP Next Update missing, using default lifetime of 24h from This Update")
        next_update = this_update + timedelta(hours=24)
    elif next_update.tzinfo is None:
        next_update = next_update.replace(tzinfo=timezone.utc)

    total_lifetime = int((next_update - this_update).total_seconds())
    if total_lifetime <= 0:
        log_debug("⚡ OCSP invalid lifetime: Next Update is not after This Update")
        return None, None

    now = datetime.now(timezone.utc)
    remaining = max(0, int((next_update - now).total_seconds()))
    return remaining, total_lifetime


def _write_ocsp_http_error_backoff(
    cert_fp: Optional[str],
    ocsp_url: str,
    http_code: int,
    reason: str,
    backoff_seconds: int = HTTP_ERROR_BACKOFF_SECONDS,
) -> None:
    """
    Persist an HTTP error backoff marker into ocsp.json so we can avoid
    re-fetching for a short duration.

    This is used by _process_cert() to skip OCSP refresh attempts shortly
    after certain transient/non-transient HTTP failures (e.g. 400/500).
    """
    if not cert_fp:
        return

    try:
        ocsp_cert_dir = _get_sharded_ocsp_path(cert_fp)
        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
        meta_path = ocsp_cert_dir / "ocsp.json"

        now = datetime.now(timezone.utc)
        retry_after = now + timedelta(seconds=backoff_seconds)

        meta = {
            "fingerprint": cert_fp,
            "ocsp_url": ocsp_url,
            "http_error": {"code": http_code, "reason": reason or ""},
            "retry_after": retry_after.isoformat(),
            # Keep "expires" for compatibility with the existing success metadata schema/logging.
            "expires": retry_after.isoformat(),
            "error_type": "http_backoff",
        }

        meta_path.write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
        meta_path.chmod(0o644)
    except Exception as e:
        log_debug("⚠️ OCSP could not write http_error backoff metadata: %s", e)


def _get_http_error_backoff_remaining(cert_fp: Optional[str]) -> int:
    """
    Return remaining seconds for an http_error backoff stored in ocsp.json.
    Returns 0 if no backoff marker exists or if it is expired/invalid.
    """
    if not cert_fp:
        return 0

    try:
        meta_path = _get_sharded_ocsp_path(cert_fp) / "ocsp.json"
        if not meta_path.is_file():
            return 0

        raw = meta_path.read_text(encoding="utf-8")
        meta = json.loads(raw) if raw else None
        if not isinstance(meta, dict):
            return 0

        # Only trust backoff markers we wrote.
        if meta.get("error_type") != "http_backoff":
            return 0

        retry_after = meta.get("retry_after")
        if not retry_after or not isinstance(retry_after, str):
            return 0

        # Accept ISO-8601 timestamps produced by .isoformat()
        retry_dt = datetime.fromisoformat(retry_after)
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        remaining = int((retry_dt - now).total_seconds())
        return max(0, remaining)
    except Exception:
        return 0


def fetch_ocsp_response(pem_data: bytes, ocsp_url: str, cert_name: str = "", timeout: int = 10) -> Tuple[Optional[bytes], int]:
    """
    Fetch OCSP response using cryptography + urllib.
    Returns (raw DER bytes or None, ttl_seconds).
    """
    try:
        leaf, issuer = _parse_chain(pem_data, cert_name)
    except Exception as e:
        log_error("❌ OCSP failed to parse chain for %s: %s", cert_name, e)
        return None, 0

    # Used for writing backoff metadata on HTTP errors.
    cert_fp = _get_cert_pubkey_fingerprint(pem_data)

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

                log_debug(
                    "🌐 OCSP fetching for %s (using %s): serial=%d, issuer=%s, responder=%s",
                    cert_name, alg_name, leaf.serial_number, issuer.subject.rfc4514_string(), ocsp_url
                )

                # --- Build HTTP request ---
                parsed = urlparse(ocsp_url)
                scheme = parsed.scheme.lower() if parsed.scheme else ""
                if scheme not in ("http", "https"):
                    log_error("❌ OCSP invalid responder scheme %s for %s: %s", scheme, cert_name, ocsp_url)
                    return None, 0

                default_port = 443 if scheme == "https" else 80
                ocsp_hostname, ips = _get_ocsp_responder_ips(ocsp_url, default_port=default_port)
                if not ocsp_hostname or not ips:
                    log_error("❌ OCSP could not resolve safe IPs for responder %s (host=%s)", cert_name, ocsp_hostname)
                    return None, 0

                # Fetch by connecting to each resolved IP, while keeping TLS SNI for `ocsp_hostname`.
                ocsp_der = None
                for ip_str in ips:
                    http_code: Optional[int] = None
                    http_reason: str = ""
                    try:
                        ocsp_der, http_code, http_reason = _post_ocsp_over_ip_with_sni(
                            ocsp_url=ocsp_url,
                            ocsp_request_data=ocsp_request_data,
                            ocsp_hostname=ocsp_hostname,
                            ip_str=ip_str,
                            timeout=timeout,
                        )
                    except Exception as e:
                        log_warning(
                            "⚠️ OCSP fetch failed for %s (%s) -> %s using %s: %s",
                            cert_name,
                            ocsp_hostname,
                            ip_str,
                            alg_name,
                            e,
                        )
                        ocsp_der = None
                    if ocsp_der:
                        break

                    # For HTTP 400/500, persist a short retry backoff.
                    if http_code in (400, 500):
                        _write_ocsp_http_error_backoff(
                            cert_fp=cert_fp,
                            ocsp_url=ocsp_url,
                            http_code=http_code,
                            reason=http_reason,
                        )
        
                if not ocsp_der:
                    log_warning("⚠️ OCSP empty response from %s for %s", ocsp_url, cert_name)
                    continue

                # Check if it's a valid OCSP response via cryptography
                ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_der)
                if ocsp_response.response_status != x509_ocsp.OCSPResponseStatus.SUCCESSFUL:
                    log_warning(
                        "⚠️ OCSP responder returned %s for %s (using %s), retrying if fallback available...",
                        ocsp_response.response_status, cert_name, alg_name
                    )
                    ocsp_der = None
                    continue

                # If we reached here, we have a SUCCESSFUL response
                break

            except HTTPError as e:
                log_warning("⚠️ OCSP HTTP %d error for %s using %s: %s", e.code, cert_name, alg_name, e.reason)
                if e.code in (400, 500):
                    _write_ocsp_http_error_backoff(
                        cert_fp=cert_fp,
                        ocsp_url=ocsp_url,
                        http_code=e.code,
                        reason=e.reason or "",
                    )
                ocsp_der = None
                continue
            except Exception as e:
                log_warning("⚠️ OCSP request failed for %s using %s: %s", cert_name, alg_name, e)
                ocsp_der = None
                continue
        else:
            # Loop finished without a break: all attempts failed
            log_error("❌ OCSP failed to fetch successful response for %s after trying both SHA256 and SHA1", cert_name)
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
                OPENSSL_BIN, "ocsp",
                "-respin", f_der.name,
                "-issuer", f_issuer.name,
                "-cert", f_leaf.name,
                "-CAfile", f_issuer.name,
                "-partial_chain"
            ]

            if not Path(OPENSSL_BIN).is_file():
                log_error("❌ OCSP verification requires openssl at %s", OPENSSL_BIN)
                return None, 0

            try:
                # Add a timeout so a stuck openssl process cannot hang the whole job
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            except subprocess.TimeoutExpired as e:
                log_error(
                    "❌ OCSP response cryptographic signature verification timed out for %s after %s seconds. Discarding response.",
                    cert_name,
                    e.timeout,
                )
                return None, 0
            if p.returncode != 0:
                log_error("❌ OCSP response cryptographic signature verification failed for %s. Discarding forged/invalid response. OpenSSL Error: %s", cert_name, p.stderr.strip() or p.stdout.strip())
                return None, 0

        # Extract TTL
        remaining, _ = _ocsp_response_lifetimes(ocsp_response)
        if remaining is not None:
            ttl = min(remaining, 7 * 24 * 3600)  # Cap to 7 days
        else:
            ttl = 86400  # RFC standard fallback

        # Delay after successful fetch to prevent rate limiting
        log_debug("⏸️ OCSP delaying 2 seconds after fetch for %s to prevent rate limiting", cert_name)
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
        log_error("❌ OCSP %s from responder for %s at %s", error_desc, cert_name, ocsp_url)

        # For HTTP 400/500, write a short backoff marker into ocsp.json so the job
        # doesn't immediately retry the same failing responder for every certificate.
        if e.code in (400, 500):
            cert_fp = _get_cert_pubkey_fingerprint(pem_data)
            _write_ocsp_http_error_backoff(
                cert_fp=cert_fp,
                ocsp_url=ocsp_url,
                http_code=e.code,
                reason=e.reason or "",
            )

        return None, 0
    except URLError as e:
        # Network error — DNS, connection refused, timeout, SSL error, etc.
        log_error("❌ OCSP network error fetching response for %s from %s: %s", cert_name, ocsp_url, e)
        return None, 0
    except Exception as e:
        log_error("❌ OCSP failed to fetch response for %s: %s", cert_name, e)
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
        log_debug("OCSP failed to extract SAN from %s: %s", cert_name, e)
        return []


def get_cached_ocsp_ttl(cert_name: str, cert_pem: Optional[bytes] = None, fingerprint: Optional[str] = None) -> Tuple[Optional[int], Optional[int]]:
    """
    Check if cached OCSP DER file exists (using fingerprint-based sharded path) and return:
      - remaining TTL in seconds (until Next Update)
      - total lifetime in seconds (Next Update - This Update)
    Both values are None if they cannot be determined.

    Args:
        cert_name: Certificate identifier (for logging only)
        cert_pem: Optional certificate PEM data to compute fingerprint if not provided
        fingerprint: Optional pre-computed fingerprint. If not provided, computes from cert_pem.
    """
    # Compute fingerprint if not provided
    if fingerprint is None:
        if cert_pem is None:
            log_debug("⚡ OCSP TTL check: no fingerprint or cert_pem provided for %s", cert_name)
            return None, None
        fingerprint = _get_cert_pubkey_fingerprint(cert_pem)
        if fingerprint is None:
            log_debug("⚡ OCSP TTL check: could not compute fingerprint for %s", cert_name)
            return None, None

    # Use sharded fingerprint-based path
    ocsp_path = _get_sharded_ocsp_path(fingerprint) / "ocsp.der"
    log_debug("⚡ OCSP TTL check: checking cache for %s at sharded path %s (fingerprint: %s...)", cert_name, ocsp_path, fingerprint[:16])

    if not ocsp_path.is_file():
        log_debug("⚡ OCSP TTL check: cache miss - file not found for %s", cert_name)
        return None, None

    log_debug("⚡ OCSP cached file found for %s, reading This/Next Update...", cert_name)
    try:
        ocsp_data = ocsp_path.read_bytes()
        ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_data)

        remaining, total_lifetime = _ocsp_response_lifetimes(ocsp_response)
        if remaining is None or total_lifetime is None:
            log_debug("🔄 OCSP could not determine precise lifetime for %s from cached response", cert_name)
            return None, None

        # Type assertion: after None checks above, these are guaranteed to be int
        assert remaining is not None
        assert total_lifetime is not None

        log_info(
            "⚡ OCSP cached response for %s: remaining=%ds (%.1f days), total_lifetime=%ds (%.1f days)",
            cert_name,
            remaining,
            remaining / 86400.0,
            total_lifetime,
            total_lifetime / 86400.0,
        )
        return remaining, total_lifetime
    except Exception as e:
        log_warning("⚠️ OCSP exception while reading cached TTL for %s: %s", cert_name, e)
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
            log_warning("⚠️ OCSP sanitization: skipping invalid/unsafe SAN %s", san)
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
                        log_debug("🔗 OCSP SAN symlink for %s already correct (%s -> %s)", san, san_ocsp, target)
                    else:
                        log_debug("ℹ️ OCSP SAN symlink for %s points to different target (got %s, expected %s) — likely overlapping certs, skipping", san, target, expected_target)
                except Exception:
                    log_debug("⚠️ OCSP SAN symlink for %s is broken or unreadable", san)
            elif san_ocsp.is_file():
                log_debug("ℹ️ OCSP SAN path %s is a regular file (not a symlink) — likely another real cert, skipping symlink", san_ocsp)
            continue

        try:
            san_dir.mkdir(parents=True, exist_ok=True)
            # Use relative symlink: ../cert_name/ocsp.der
            rel_target = Path("..") / _sanitize_filename(cert_name) / "ocsp.der"
            san_ocsp.symlink_to(rel_target)
            log_debug("🔗 OCSP created SAN symlink %s -> %s", san_ocsp, rel_target)
        except Exception as e:
            log_debug("⚠️ OCSP could not create SAN symlink for %s: %s", san, e)


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
        log_warning("⚠️ OCSP could not retrieve cached certificate list from database: %s", e)

    return cached_certs


def _get_cert_checksums(db: Any, cert_data: Dict[str, bytes]) -> Dict[str, str]:
    """
    Get previously stored checksums for certificates from the database.
    Checksums are stored in cache entries like 'cert_checksum/{fingerprint}'.

    Args:
        db: Database connection
        cert_data: Dict of {cert_name: pem_data} to retrieve checksums for

    Returns:
        Dict of {cert_name: checksum_hex}
    """
    checksums = {}

    if db is None or not cert_data:
        return checksums

    try:
        # Build mapping of fingerprints to cert_names for lookup
        fingerprint_to_name = {}
        for cert_name, pem_data in cert_data.items():
            # Clean PEM before fingerprinting (custom certs may have private keys/noise)
            cleaned_pem = _clean_pem(pem_data)
            cert_fp = _get_cert_pubkey_fingerprint(cleaned_pem)
            if cert_fp:
                fingerprint_to_name[cert_fp] = cert_name

        if not fingerprint_to_name:
            log_debug("⚠️ OCSP could not compute fingerprints for %d cert(s) when retrieving checksums", len(cert_data))
            return checksums

        # Optimization: use with_data=True to fetch all checksums in one go
        cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        for entry in cache_files:
            file_name = entry.get("file_name", "")
            if file_name.startswith("cert_checksum/"):
                fingerprint = file_name[len("cert_checksum/"):]
                if fingerprint in fingerprint_to_name:
                    cert_name = fingerprint_to_name[fingerprint]
                    data = entry.get("data")
                    if data:
                        try:
                            checksums[cert_name] = data.decode("utf-8").strip()
                        except Exception:
                            pass
    except Exception as e:
        log_debug("⚠️ OCSP could not retrieve certificate checksums from database: %s", e)

    return checksums


def _calculate_cert_checksum(pem_data: bytes) -> str:
    """
    Calculate SHA256 checksum of certificate PEM data.
    """
    return hashlib.sha256(pem_data).hexdigest().lower()


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
            log_warning("⚠️ OCSP failed to query database for LE tarball (job=%s): %s", job_name, e)
            continue
        if tgz_data:
            log_debug("✓ OCSP found LE tarball from %s job", job_name)
            break

    if tgz_data is None:
        log_debug("ℹ️ OCSP no LE tarball found in database (certbot-new cache)")
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
                        log_warning("⚠️ OCSP sanitization: skipping unsafe cert_name from tarball: %s", cert_name)
                        continue

                    # Defensive hardening: validate symlink target stays within the expected
                    # archive/<cert_name>/ subtree. We only read from the in-memory tarball,
                    # but a malicious tar entry could otherwise point to unexpected content.
                    try:
                        linkname = getattr(member, "linkname", "")
                        if not isinstance(linkname, str) or not linkname:
                            log_warning("⚠️ OCSP LE tarball: missing/invalid symlink target for %s", cert_name)
                            continue
                        # Disallow absolute targets.
                        if linkname.startswith("/"):
                            log_warning("⚠️ OCSP LE tarball: symlink target is absolute for %s", cert_name)
                            continue
                        # Ensure the normalized resolved target remains within archive/<cert_name>/.
                        import posixpath
                        from pathlib import PurePosixPath

                        base_dir = PurePosixPath(member.name).parent
                        combined = posixpath.normpath(str(base_dir / PurePosixPath(linkname)))
                        if combined.startswith("./"):
                            combined = combined[2:]
                        if combined.startswith("../"):
                            log_warning("⚠️ OCSP LE tarball: symlink target escapes archive for %s", cert_name)
                            continue

                        # Be tolerant to tarball prefix differences by validating against the
                        # extracted cache base where "live/<cert_name>/" comes from.
                        member_parts = PurePosixPath(member.name).parts
                        live_idx = None
                        for i, part in enumerate(member_parts):
                            if part == "live":
                                live_idx = i
                                break
                        if live_idx is None:
                            log_warning("⚠️ OCSP LE tarball: could not locate 'live' base for %s", cert_name)
                            continue

                        root_prefix_parts = [p for p in member_parts[:live_idx] if p not in (".", "")]
                        root_prefix = "/".join(root_prefix_parts)

                        archive_prefix = (
                            f"{root_prefix}/archive/{cert_name}/" if root_prefix else f"archive/{cert_name}/"
                        )
                        live_prefix = f"{root_prefix}/live/{cert_name}/" if root_prefix else f"live/{cert_name}/"

                        if not (combined.startswith(archive_prefix) or combined.startswith(live_prefix)):
                            log_warning(
                                "⚠️ OCSP LE tarball: symlink target not in expected subtree for %s (got=%s, expected_prefixes=%s,%s)",
                                cert_name,
                                combined,
                                archive_prefix,
                                live_prefix,
                            )
                            continue
                    except Exception as e:
                        log_warning("⚠️ OCSP LE tarball: failed to validate symlink target for %s: %s", cert_name, e)
                        continue
                    try:
                        f = tar.extractfile(member)
                        if f:
                            pem_data = f.read()
                            if not pem_data or b"-----BEGIN" not in pem_data:
                                log_warning("⚠️ OCSP LE fullchain for %s is empty or not valid PEM, skipping", cert_name)
                                continue
                            result[cert_name] = pem_data
                            log_debug("✓ OCSP extracted LE fullchain for %s from database tarball", cert_name)
                        else:
                            log_warning("⚠️ OCSP could not read LE fullchain for %s from tarball (extractfile returned None)", cert_name)
                    except KeyError:
                        log_warning("⚠️ OCSP symlink target missing in tarball for %s", cert_name)
                    except Exception as e:
                        log_warning("⚠️ OCSP failed to extract LE fullchain for %s: %s", cert_name, e)
    except tarfile.TarError as e:
        log_error("❌ OCSP LE tarball is corrupted or invalid: %s", e)
    except Exception as e:
        log_error("❌ OCSP failed to extract LE certificates from database tarball: %s", e)

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
        log_error("❌ OCSP failed to query database for custom certificates: %s", e)
        return result

    if not cache_files:
        log_debug("ℹ️ OCSP no custom-cert cache entries found in database")
        return result

    for entry in cache_files:
        try:
            file_name = entry.get("file_name", "")
            service_id = entry.get("service_id", "")
            # Match cert.pem, cert-ecdsa.pem, cert-rsa.pem
            if not (file_name.startswith("cert") and file_name.endswith(".pem")):
                continue
            if not service_id:
                log_debug("⚠️ OCSP custom cert entry %s has no service_id, skipping", file_name)
                continue
            # Prevent path traversal: validate service_id format
            if not re.match(r"^[A-Za-z0-9_.*-]+$", service_id):
                log_warning("⚠️ OCSP sanitization: skipping custom cert with invalid service_id: %s", service_id)
                continue
            data = entry.get("data")
            if not data:
                log_warning("⚠️ OCSP custom cert %s for service %s has no data, skipping", file_name, service_id)
                continue
            # Derive suffix from filename: cert-ecdsa.pem -> -ecdsa, cert.pem -> ""
            suffix = file_name.replace("cert", "").replace(".pem", "")  # e.g. "-ecdsa", "-rsa", ""
            key = f"customcert-{service_id}{suffix}"
            # Double-check derived key is safe (defensive validation)
            if not re.match(r"^[A-Za-z0-9_.*-]+$", key):
                log_warning("⚠️ OCSP sanitization: skipping custom cert with unsafe derived key: %s", key)
                continue
            result[key] = data
            log_debug("✓ OCSP loaded custom cert for %s from database (file=%s, size=%d)", key, file_name, len(data))
        except Exception as e:
            log_warning("⚠️ OCSP failed to process custom cert entry %s: %s", entry.get("file_name", "?"), e)

    return result


def restore_ocsp_from_database(db: Optional[Any] = None) -> None:
    """
    Restore cached OCSP responses from database to disk.
    Called at startup to ensure disk cache is populated from database.
    This handles ephemeral storage (tmpfs, etc.) by restoring files on each run.
    """
    if not db:
        log_debug("ℹ️ OCSP database not available, skipping cache restoration")
        return

    log_info("🔄 OCSP syncing cached responses from database to disk...")
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
            cert_or_fp_raw = file_name[len("ocsp/"):]
            # We only restore actual OCSP responses from database.
            # Marker entries are stored as: ocsp/{cert_name} (data contains the fingerprint).
            # Response entries are stored as: ocsp/{fingerprint}.
            fingerprint = _normalize_fingerprint(cert_or_fp_raw)
            if not fingerprint:
                continue

            db_data = entry["data"]
            db_checksum = (entry.get("checksum") or hashlib.sha256(db_data).hexdigest()).lower()

            try:
                ocsp_cert_dir = _get_sharded_ocsp_path(fingerprint)
                ocsp_path = ocsp_cert_dir / "ocsp.der"

                if ocsp_path.is_file():
                    # File exists — compare checksum
                    disk_checksum = hashlib.sha256(ocsp_path.read_bytes()).hexdigest().lower()
                    if disk_checksum == db_checksum:
                        ok_count += 1
                        log_debug("✓ OCSP disk file for %s matches database (checksum=%s)", fingerprint, db_checksum[:8])
                        continue
                    # Checksum mismatch — replace with database version
                    log_info("🔄 OCSP disk file for %s has wrong checksum (disk=%s, db=%s), replacing", fingerprint, disk_checksum[:8], db_checksum[:8])
                    ocsp_path.write_bytes(db_data)
                    ocsp_path.chmod(0o644)
                    replaced_count += 1
                else:
                    # File missing — restore from database
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                    ocsp_path.write_bytes(db_data)
                    ocsp_path.chmod(0o644)
                    restored_count += 1
                    log_debug("✓ OCSP restored cached response for %s from database", fingerprint)
            except Exception as e:
                log_debug("⚠️ OCSP could not sync cache for %s: %s", fingerprint, e)

        if restored_count > 0 or replaced_count > 0:
            log_info("✓ OCSP sync complete: restored=%d, replaced=%d, unchanged=%d", restored_count, replaced_count, ok_count)
        else:
            log_debug("ℹ️ OCSP sync complete: all %d disk files match database (restored=0, replaced=0)", ok_count)
    except Exception as e:
        log_debug("OCSP exception while attempting cache sync: %s", e)


def _process_cert(cert_name: str, pem_data: bytes, db: Optional[Any] = None, stats: Optional[dict] = None, force_fetch: bool = False) -> Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]:
    """
    Process a single certificate for OCSP stapling. Works with in-memory PEM data.
    If force_fetch is True, skips the cached TTL check and retrieves a new response from upstream PKI.
    On error with force_fetch, returns ocsp_der=None, and disk files are NOT replaced (existing files kept intact).

    Returns a tuple of (cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, was_attempted) for batched database writes.
    If ocsp_der is None, it means the fetch was skipped or failed (disk files remain untouched).
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
    cert_fp = _get_cert_pubkey_fingerprint(pem_data)

    # Check per-service OCSP stapling setting
    if not _is_ocsp_enabled_for_service(service_name):
        log_debug("🧹 OCSP stapling disabled for service %s, cleaning up cache for %s", service_name, cert_name)
        cleanup_ocsp_cache(db, cert_name, fingerprint=cert_fp)
        stats["le_certs_skipped"] = stats.get("le_certs_skipped", 0) + 1
        return (cert_name, None, 0, cert_checksum, pem_data, None, False)

    # Check if certificate checksum matches what we have in database
    # Checksums are stored by fingerprint (cert_checksum/{fingerprint}), so compute it first
    cached_checksum = None
    fingerprint_for_checksum = cert_fp
    if db and fingerprint_for_checksum:
        try:
            checksum_key = f"cert_checksum/{fingerprint_for_checksum}"
            checksum_data = db.get_job_cache_file(file_name=checksum_key, job_name="ocsp-refresh")
            if checksum_data:
                cached_checksum = checksum_data.decode("utf-8").strip()
                log_debug("✓ OCSP found cached checksum for %s (key=%s)", cert_name, checksum_key[:30])
        except Exception as e:
            log_debug("⚠️ OCSP could not check cached checksum for %s: %s", cert_name, e)

    log_debug("🔄 OCSP processing certificate %s", cert_name)

    try:
        if not pem_data.startswith(b"-----BEGIN"):
            log_warning("⚠️ OCSP cert for %s has no PEM BEGIN marker or is invalid after cleaning, skipping", cert_name)
            return (cert_name, None, 0, cert_checksum, pem_data, None, False)

        # Proceed with extracting OCSP URL using the CLEANED pem_data
        ocsp_url = extract_ocsp_url(pem_data, cert_name)
        if not ocsp_url:
            log_debug("ℹ️ OCSP certificate %s has no responder, skipping fetch", cert_name)
            stats["le_certs_no_ocsp"] = stats.get("le_certs_no_ocsp", 0) + 1
            return (cert_name, None, 0, cert_checksum, pem_data, None, False)

        log_debug("🌐 OCSP responder for certificate %s: %s", cert_name, ocsp_url)

        # === Compute fingerprint for sharded path lookup ===
        fingerprint = cert_fp
        if not fingerprint:
            log_warning("⚠️ OCSP could not compute fingerprint for %s, treating as new fetch", cert_name)

        # === HTTP error backoff (400/500) ===
        # If we previously got an HTTP 400/500 for this certificate's OCSP responder,
        # avoid hammering the same endpoint until the backoff expires.
        if not force_fetch:
            backoff_remaining = _get_http_error_backoff_remaining(cert_fp)
            if backoff_remaining > 0:
                stats["ocsp_http_error_backoff_skipped"] = stats.get("ocsp_http_error_backoff_skipped", 0) + 1
                log_info(
                    "⏸️ OCSP HTTP backoff active for %s (ocsp.json retry_after in %ds), skipping fetch",
                    cert_name,
                    backoff_remaining,
                )
                return (cert_name, None, backoff_remaining, cert_checksum, pem_data, ocsp_url, False)

        # === Check if cached OCSP response is still fresh (disk + database) ===
        # This two-tier check handles aborted downloads, database inconsistencies, and ephemeral storage
        cached_ttl, total_lifetime = get_cached_ocsp_ttl(cert_name, pem_data, fingerprint)

        # If disk check found valid response, use it (even if database is out of sync)
        if cached_ttl is not None:
            half_lifetime = (total_lifetime // 2) if (total_lifetime and total_lifetime > 0) else 0
            # Smart TTL calculation: use 20% of total lifetime as refresh threshold (or MIN_TTL if larger for safety)
            refresh_threshold = max(MIN_TTL, int(total_lifetime * 0.20)) if total_lifetime and total_lifetime > 0 else MIN_TTL

            # Skip fetch ONLY if not forced AND TTL is above refresh_threshold AND above 50% lifetime
            if not force_fetch and cached_ttl > refresh_threshold and cached_ttl > half_lifetime:
                log_info(
                    "✓ OCSP cached response for %s still valid for %ds (%.1f days), above thresholds (refresh_threshold=%ds [20%% of %ds], 50%% threshold=%ds), skipping fetch",
                    cert_name, cached_ttl, cached_ttl / 86400.0, refresh_threshold, total_lifetime, half_lifetime,
                )
                stats["ocsp_cached_responses"] = stats.get("ocsp_cached_responses", 0) + 1
                return (cert_name, None, cached_ttl, cert_checksum, pem_data, ocsp_url, False)

            if cached_ttl <= refresh_threshold:
                log_info("🔄 OCSP response for %s is near expiration (TTL=%ds <= refresh_threshold=%ds [20%% of %ds]), attempting aggressive refresh", cert_name, cached_ttl, refresh_threshold, total_lifetime)

        ocsp_der: Optional[bytes] = None
        ttl: int = 0

        # Use a timeout of 10 seconds per attempt, retry once after 10 seconds
        for attempt in (1, 2):
            ocsp_der, ttl = fetch_ocsp_response(pem_data, ocsp_url, cert_name=cert_name, timeout=10)
            if ocsp_der:
                log_debug("✓ OCSP successfully fetched response for %s on attempt %d (TTL=%ds)", cert_name, attempt, ttl)
                stats["ocsp_fetched_responses"] = stats.get("ocsp_fetched_responses", 0) + 1
                break
            if attempt == 1:
                log_warning("⚠️ OCSP fetch failed for %s, retrying once after 2 seconds ...", cert_name)
                time.sleep(2)

        if not ocsp_der:
            log_error("❌ OCSP failed to fetch response for %s after retries", cert_name)

            if cached_ttl is not None:
                current_ttl = cast(int, cached_ttl)
                # Recalculate refresh_threshold for failure handling (same logic as above)
                current_refresh_threshold = max(MIN_TTL, int(total_lifetime * 0.20)) if total_lifetime and total_lifetime > 0 else MIN_TTL

                if current_ttl <= 0:
                    log_warning(
                        "🧹 OCSP cached response for %s is already expired and refresh failed. Cleaning up invalid cache.",
                        cert_name,
                    )
                    cleanup_ocsp_cache(db, cert_name, fingerprint=cert_fp)
                elif current_ttl <= current_refresh_threshold:
                    log_warning(
                        "🚨 OCSP CRITICAL: Cached response for %s is near expiration (TTL=%ds <= refresh_threshold=%ds [20%% of %ds]) and refresh failed. "
                        "Removing from cache to prevent stapling expired data.",
                        cert_name,
                        current_ttl,
                        current_refresh_threshold,
                        total_lifetime,
                    )
                    cleanup_ocsp_cache(db, cert_name, fingerprint=cert_fp)
                else:
                    log_warning(
                        "⚠️ OCSP could NOT refresh response for %s, keeping existing cache (TTL=%ds, above threshold %ds) for now",
                        cert_name,
                        current_ttl,
                        current_refresh_threshold,
                    )
                return (cert_name, None, current_ttl, cert_checksum, pem_data, ocsp_url, True)

            return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)

        # Calculate checksum for integrity verification (lowercase for consistency)
        ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest().lower()
        ttl_readable = f"{ttl / 86400.0:.1f} days" if ttl >= 86400 else f"{ttl / 3600.0:.1f} hours"
        log_info("⚡ OCSP final TTL for %s is %ds (%s) (checksum=%s)", cert_name, ttl, ttl_readable, ocsp_checksum[:8])

        # === Return result for batched database writes ===
        return (cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, True)

    except Exception as e:
        log_error("❌ OCSP exception while processing certificate %s: %s", cert_name, e)
        stats["errors"] = stats.get("errors", 0) + 1
        return (cert_name, None, 0, cert_checksum, pem_data, None, False)


def process_custom_certs(
    db: Optional[Any] = None,
    stats: Optional[dict] = None,
    lock_fd: Optional[int] = None,
    refresh_fn: Optional[Callable[[str], None]] = None,
    timeout_fn: Optional[Callable[[str], bool]] = None,
    skip_unchanged_ttl_checks: bool = False,
    force_fetch: bool = False,
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
        force_fetch: If True, force refetch all OCSP responses from upstream PKI
    """
    if stats is None:
        stats = {}

    results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]] = []

    if not db:
        log_info("ℹ️ OCSP database not available, cannot process custom certificates")
        return results

    try:
        custom_certs = _load_custom_certs_from_db(db)
        if not custom_certs:
            log_info("ℹ️ OCSP no custom certificates found in database")
            return results

        log_info("🔄 OCSP loaded %d custom certificate(s) from database", len(custom_certs))

        # Check which custom certs have changed since last OCSP refresh
        # The names from _load_custom_certs_from_db already include the 'customcert-' prefix
        previous_custom_checksums = _get_cert_checksums(db, custom_certs)
        changed_custom_certs = {}
        unchanged_custom_certs = {}

        for cert_name, pem_data in custom_certs.items():
            # Clean PEM before calculating checksum to ensure consistency
            cleaned_pem = _clean_pem(pem_data)
            current_checksum = _calculate_cert_checksum(cleaned_pem)
            previous_checksum = previous_custom_checksums.get(cert_name)

            if previous_checksum is None:
                # No previous checksum, treat as changed (will be recategorized by robustness check if valid disk cache exists)
                changed_custom_certs[cert_name] = pem_data
                log_debug("ℹ️ OCSP no previous checksum found for custom cert %s (will check disk cache)", cert_name)
            elif current_checksum != previous_checksum:
                # Certificate content has changed
                changed_custom_certs[cert_name] = pem_data
                log_debug("🔄 OCSP custom certificate content changed for %s", cert_name)
            else:
                # Certificate content unchanged
                unchanged_custom_certs[cert_name] = pem_data

        if unchanged_custom_certs:
            if skip_unchanged_ttl_checks:
                log_info("✓ OCSP skipping TTL checks for %d unchanged custom certificate(s) (recently run)", len(unchanged_custom_certs))
                stats["custom_certs_skipped"] = stats.get("custom_certs_skipped", 0) + len(unchanged_custom_certs)
            else:
                log_info("✓ OCSP checking TTL for %d unchanged custom certificate(s): %s", len(unchanged_custom_certs), ", ".join(sorted(unchanged_custom_certs.keys())))
                stats["custom_certs_unchanged"] = stats.get("custom_certs_unchanged", 0) + len(unchanged_custom_certs)

        stats["custom_certs_processed"] = stats.get("custom_certs_processed", 0) + len(custom_certs)

        # 1. Process changed custom certificates (robustness: skip force-fetch if valid OCSP cached on disk)
        recategorized_changed_custom = {}
        for cert_name, cert_pem in list(changed_custom_certs.items()):
            # Clean PEM before fingerprinting (custom certs may have private keys/noise)
            cleaned_pem = _clean_pem(cert_pem)
            fingerprint = _get_cert_pubkey_fingerprint(cleaned_pem)
            if fingerprint:
                cached_ttl, _ = get_cached_ocsp_ttl(cert_name, cert_pem, fingerprint)
                if cached_ttl is not None and cached_ttl > 0:
                    # Valid OCSP cached on disk - skip force refresh
                    log_info("ℹ️ OCSP disk file exists for %s (marked changed due to missing checksum): TTL=%ds, skipping force-fetch", cert_name, cached_ttl)
                    recategorized_changed_custom[cert_name] = cert_pem
                    del changed_custom_certs[cert_name]
                    unchanged_custom_certs[cert_name] = cert_pem

        if recategorized_changed_custom:
            log_info("ℹ️ OCSP recategorized %d custom cert(s) from changed→unchanged due to valid disk cache", len(recategorized_changed_custom))
            # Add recategorized certs to results so their checksums get persisted to database
            # (even though we didn't fetch new OCSP responses, we need to record their checksums for future runs)
            for cert_name, cert_pem in sorted(recategorized_changed_custom.items()):
                pem_checksum = _calculate_cert_checksum(cert_pem)
                # Tuple: (cert_name, ocsp_der=None, ttl=0, checksum, pem_data, ocsp_url=None, was_attempted=False)
                # We're not fetching, just recording the cert's checksum for differential tracking
                results.append((cert_name, None, 0, pem_checksum, cert_pem, None, False))
                log_debug("✓ OCSP added recategorized custom cert %s to database persist list (checksum=%s)", cert_name, pem_checksum[:8])

        # Process remaining changed custom certificates with force refresh
        for cert_name, cert_pem in sorted(changed_custom_certs.items()):
            if callable(timeout_fn) and timeout_fn(f"changed custom cert {cert_name}"):
                break
            if callable(refresh_fn):
                refresh_fn(cert_name)
            results.append(_process_cert(cert_name, cert_pem, db, stats, force_fetch=True))

        # 2. Process unchanged custom certificates (TTL check only or force-fetch if requested)
        if not skip_unchanged_ttl_checks:
            for cert_name, cert_pem in sorted(unchanged_custom_certs.items()):
                if callable(timeout_fn) and timeout_fn(f"unchanged custom cert {cert_name}"):
                    break
                if callable(refresh_fn):
                    refresh_fn(cert_name)
                results.append(_process_cert(cert_name, cert_pem, db, stats, force_fetch=force_fetch))

    except Exception as e:
        log_error("OCSP exception while processing custom certificates: %s", e)
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


def cleanup_ocsp_cache(
    db: Optional[Any] = None,
    cert_name: Optional[str] = None,
    fingerprint: Optional[str] = None,
    purge_db: bool = True,
) -> None:
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
            log_error("❌ OCSP sanitization: refusing to clean up invalid/unsafe cert_name %s", cert_name)
            return

        # Clean up a single certificate's OCSP cache
        sanitized_name = _sanitize_filename(cert_name)
        resolved_fp = _normalize_fingerprint(fingerprint)

        # If fingerprint wasn't provided, try to resolve it from the marker stored in DB.
        # Marker entries are stored as: ocsp/{cert_name} with data = fingerprint (ASCII hex).
        if not resolved_fp and db and purge_db:
            try:
                marker_data = db.get_job_cache_file(
                    file_name=f"ocsp/{sanitized_name}",
                    job_name="ocsp-refresh",
                )
                if marker_data:
                    decoded = marker_data.decode("utf-8", errors="ignore").strip()
                    resolved_fp = _normalize_fingerprint(decoded)
            except Exception as e:
                log_debug("⚠️ OCSP could not resolve fingerprint marker for %s: %s", cert_name, e)
                resolved_fp = None

        # Disk cleanup: prefer fingerprint-based sharded storage.
        if resolved_fp:
            ocsp_fp_dir = _get_sharded_ocsp_path(resolved_fp)
            if ocsp_fp_dir.is_dir():
                shutil.rmtree(ocsp_fp_dir, ignore_errors=True)
                log_info("🧹 OCSP removed sharded cache for %s (fingerprint=%s)", cert_name, resolved_fp[:16] + "...")
        else:
            ocsp_dir = CONFIGS_SSL_BASE / sanitized_name
            if ocsp_dir.is_dir():
                shutil.rmtree(ocsp_dir, ignore_errors=True)
                log_info("🧹 OCSP removed cache directory for %s", cert_name)

        # Best-effort legacy flat cache cleanup (kept for backward compatibility).
        legacy_ocsp_dir = CONFIGS_SSL_BASE / sanitized_name
        if legacy_ocsp_dir.is_dir():
            shutil.rmtree(legacy_ocsp_dir, ignore_errors=True)

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
                            log_debug("🧹 OCSP removed SAN symlink %s", san_ocsp)
                            # Remove empty directory
                            try:
                                entry.rmdir()
                            except OSError:
                                pass
                    except Exception as e:
                        log_debug("⚠️ OCSP failed to remove SAN symlink %s: %s", san_ocsp, e)

        if db and purge_db:
            try:
                # Always remove the cert-name marker (differential tracking).
                db.delete_job_cache(
                    file_name=f"ocsp/{sanitized_name}",
                    job_name="ocsp-refresh",
                )
                # If we resolved a fingerprint, also remove the corresponding response+checksum.
                if resolved_fp:
                    db.delete_job_cache(
                        file_name=f"ocsp/{resolved_fp}",
                        job_name="ocsp-refresh",
                    )
                    db.delete_job_cache(
                        file_name=f"cert_checksum/{resolved_fp}",
                        job_name="ocsp-refresh",
                    )
                log_debug("🧹 OCSP database records removed for %s (fingerprint resolved=%s)", cert_name, bool(resolved_fp))
            except Exception as e:
                log_debug("🧹 OCSP could not remove database entry for %s: %s", cert_name, e)
    else:
        # Clean up ALL OCSP caches (handles both old flat and new tree structures)
        if CONFIGS_SSL_BASE.is_dir():
            # Recursively find and remove all ocsp.der files
            for root, dirs, files in os.walk(CONFIGS_SSL_BASE, topdown=False):
                # Try to remove ocsp.der if it exists
                ocsp_file = Path(root) / "ocsp.der"
                if ocsp_file.is_symlink() or ocsp_file.is_file():
                    try:
                        ocsp_file.unlink()
                        log_info("🧹 OCSP removed cached response %s", ocsp_file)
                    except Exception as e:
                        log_debug("⚠️ OCSP failed to unlink ocsp.der file %s: %s", ocsp_file, e)

                # Try to remove ocsp.json metadata if it exists
                meta_file = Path(root) / "ocsp.json"
                if meta_file.is_file():
                    try:
                        meta_file.unlink()
                    except Exception as e:
                        log_debug("⚠️ OCSP failed to unlink ocsp.json metadata %s: %s", meta_file, e)

                # Remove empty directories (walk in reverse order ensures we clean up bottom-up)
                try:
                    if root != str(CONFIGS_SSL_BASE):  # Don't remove the base directory
                        Path(root).rmdir()
                except OSError:
                    pass  # Directory not empty or other error, skip

        if db and purge_db:
            try:
                # Remove all OCSP-related cache entries from database
                job_cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh")
                for cache_file in job_cache_files:
                    file_name = cache_file.get("file_name", "")
                    if file_name.startswith("ocsp/") or file_name.startswith("cert_checksum/") or file_name == "last_full_refresh":
                        try:
                            db.delete_job_cache(file_name=file_name, job_name="ocsp-refresh")
                            log_debug("🧹 OCSP removed database entry %s", file_name)
                        except Exception as e:
                            log_debug("🧹 OCSP could not remove database entry %s: %s", file_name, e)
            except Exception as e:
                log_debug("🧹 OCSP could not clean database entries: %s", e)
        elif not purge_db:
            log_info("🧹 OCSP disk caches cleaned up")

        log_info("🧹 OCSP all stapling caches cleaned up")


def _cleanup_orphaned_ocsp(db: Optional[Any], le_certs: Dict[str, bytes], stats: Optional[dict] = None) -> None:
    """
    Remove OCSP cache entries (disk + database) for services that no longer have
    certificates in the database. This handles deleted services.
    """
    if stats is None:
        stats = {}

    # Build set of valid cert names from LE certs
    valid_cert_names: set = set(le_certs.keys())
    valid_fingerprints: set = set()

    # Build the set of valid OCSP cache fingerprints to safely prune sharded disk entries.
    for _, pem_data in le_certs.items():
        try:
            fp = _get_cert_pubkey_fingerprint(_clean_pem(pem_data))
            if fp:
                valid_fingerprints.add(fp)
        except Exception:
            continue

    # Add custom cert names
    if db:
        try:
            custom_certs = _load_custom_certs_from_db(db)
            for key, pem_data in custom_certs.items():
                # key already starts with customcert-
                valid_cert_names.add(key)
                try:
                    fp = _get_cert_pubkey_fingerprint(_clean_pem(pem_data))
                    if fp:
                        valid_fingerprints.add(fp)
                except Exception:
                    continue
        except Exception as e:
            log_warning("⚠️ OCSP could not load custom certs for orphan check: %s", e)
            return  # Don't clean up if we can't verify what's valid

    if not valid_cert_names:
        log_debug("ℹ️ OCSP no valid certs found, skipping orphan cleanup to avoid accidental deletion")
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

                # Database layout:
                # - marker entries: ocsp/<cert_name> (data = fingerprint)
                # - response entries: ocsp/<fingerprint> (data = ocsp.der bytes)
                # Only delete response entries if the fingerprint is not present anymore.
                if cert_name_raw in valid_cert_names:
                    continue

                resolved_fp = _normalize_fingerprint(cert_name_raw)
                if resolved_fp and resolved_fp in valid_fingerprints:
                    continue

                if resolved_fp:
                    # Orphaned OCSP response entry: remove DB record + checksum (disk cleanup is fingerprint-aware below).
                    try:
                        db.delete_job_cache(
                            file_name=f"ocsp/{resolved_fp}",
                            job_name="ocsp-refresh",
                        )
                        db.delete_job_cache(
                            file_name=f"cert_checksum/{resolved_fp}",
                            job_name="ocsp-refresh",
                        )
                        log_info("🧹 OCSP removed orphaned fingerprint DB entries: fp=%s", resolved_fp[:16] + "...")
                        orphaned_count += 1
                    except Exception as e:
                        log_debug("⚠️ OCSP failed to remove orphaned fingerprint DB entries fp=%s: %s", resolved_fp, e)
                else:
                    # Orphaned marker entry (deleted service): reuse cleanup logic.
                    log_info("🧹 OCSP removing orphaned marker entry for deleted service: %s", cert_name_raw)
                    cleanup_ocsp_cache(db, cert_name_raw)
                    orphaned_count += 1
        except Exception as e:
            log_warning("⚠️ OCSP could not check database for orphaned entries: %s", e)

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
                log_info("🧹 OCSP removing orphaned disk cache for deleted service: %s", cert_name_raw)
                cleanup_ocsp_cache(db, cert_name_raw)
                orphaned_count = orphaned_count + 1

    # Check sharded fingerprint cache directories for orphaned OCSP files.
    # Sharded layout is: /var/cache/bunkerweb/ssl/<hex1>/<hex2>/<fingerprint>/ocsp.der
    if CONFIGS_SSL_BASE.is_dir() and valid_fingerprints:
        for root, dirs, files in os.walk(CONFIGS_SSL_BASE, topdown=False):
            if "ocsp.der" not in files:
                continue
            fingerprint = _normalize_fingerprint(Path(root).name)
            if not fingerprint:
                continue
            if fingerprint not in valid_fingerprints:
                try:
                    log_info("🧹 OCSP removing orphaned sharded disk cache for fingerprint: %s", fingerprint)
                    shutil.rmtree(root, ignore_errors=True)
                    orphaned_count = orphaned_count + 1
                except Exception:
                    continue

    if orphaned_count > 0:
        log_info("🧹 OCSP cleaned up %d orphaned cache entries for deleted services", orphaned_count)
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
        log_warning("⚠️ OCSP cannot verify files without database connection")
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
            log_info("ℹ️ OCSP no cache entries in database to verify")
            return
            
        log_info("🔍 OCSP verifying %d cache entry(ies) from database", len(ocsp_entries))

        for entry in ocsp_entries:
            file_name = entry.get("file_name", "")
            if not file_name.startswith("ocsp/"):
                continue

            cert_name_raw = file_name[len("ocsp/"):]
            data = entry.get("data")
            db_checksum = entry.get("checksum", "")

            if not data or not db_checksum:
                log_warning("⚠️ OCSP database entry %s has no data or checksum, skipping verification", cert_name_raw)
                continue

            # Check if this is a marker entry (fingerprint reference) vs actual OCSP response
            # Marker entries: UTF-8 encoded fingerprints (~64 bytes)
            # Real OCSP responses: DER-encoded binary (typically 500+ bytes)
            is_marker = False
            try:
                # Try to decode as UTF-8 fingerprint string (marker entries are ~64 hex chars)
                decoded = data.decode("utf-8", errors="strict")
                if len(decoded) == 64 and all(c in "0123456789abcdef" for c in decoded):
                    # This is a marker entry - skip it during verification
                    log_debug("ℹ️ OCSP skipping marker entry %s (fingerprint reference)", cert_name_raw)
                    is_marker = True
            except (UnicodeDecodeError, Exception):
                pass  # Not a marker, try to parse as OCSP response

            if is_marker:
                continue

            # At this point, data should be a DER-encoded OCSP response
            fingerprint = _normalize_fingerprint(cert_name_raw)
            if not fingerprint:
                continue
            verify_count += 1

            # Check if file exists on disk
            ocsp_cert_dir = _get_sharded_ocsp_path(fingerprint)
            ocsp_path = ocsp_cert_dir / "ocsp.der"

            # Check if database response is already expired
            try:
                ocsp_response = x509_ocsp.load_der_ocsp_response(data)
                remaining, _ = _ocsp_response_lifetimes(ocsp_response)
                if remaining is not None and remaining <= 0:
                    log_warning("🧹 OCSP response in database for %s is expired (remaining=%ds). Skipping restoration to disk.", cert_name_raw, remaining)
                    # Optionally remove from database to prevent future attempts
                    if db:
                        try:
                            db.delete_job_cache(file_name=file_name, job_name="ocsp-refresh")
                            log_debug("🧹 OCSP removed expired database entry %s", file_name)
                        except Exception as e:
                            log_debug("⚠️ OCSP could not remove expired database entry %s: %s", file_name, e)
                    continue
            except Exception as e:
                log_warning("⚠️ OCSP could not parse response from database for %s during verification: %s", cert_name_raw, e)

            try:
                if not ocsp_path.is_file():
                    # File missing: restore from database
                    log_warning("⚠️ OCSP file missing for %s, restoring from database", cert_name_raw)
                    try:
                        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                        ocsp_path.write_bytes(data)
                        ocsp_path.chmod(0o644)
                        # Verify checksum after restoration
                        written_checksum = hashlib.sha256(ocsp_path.read_bytes()).hexdigest().lower()
                        if written_checksum != db_checksum:
                            log_error("❌ OCSP checksum mismatch after restoring %s (expected=%s, got=%s)", cert_name_raw, db_checksum[:8], written_checksum[:8])
                            stats["errors"] = stats.get("errors", 0) + 1
                            continue
                        log_info("✓ OCSP restored %s from database (verified)", cert_name_raw)
                        restored_count += 1
                    except Exception as e:
                        log_error("❌ OCSP could not restore %s from database: %s", cert_name_raw, e)
                        stats["errors"] = stats.get("errors", 0) + 1
                        continue

                else:
                    # File exists: verify checksum (lowercase for consistency)
                    file_data = ocsp_path.read_bytes()
                    file_checksum = hashlib.sha256(file_data).hexdigest().lower()

                    if file_checksum != db_checksum:
                        log_warning(
                            "⚠️ OCSP checksum mismatch for %s (file=%s, db=%s). "
                            "Restoring from database.",
                            cert_name_raw, file_checksum[:8], db_checksum[:8]
                        )
                        try:
                            ocsp_path.write_bytes(data)
                            ocsp_path.chmod(0o644)
                            # Verify checksum after restoration
                            written_checksum = hashlib.sha256(ocsp_path.read_bytes()).hexdigest().lower()
                            if written_checksum != db_checksum:
                                log_error("❌ OCSP checksum mismatch after restoring %s (expected=%s, got=%s)", cert_name_raw, db_checksum[:8], written_checksum[:8])
                                stats["errors"] = stats.get("errors", 0) + 1
                                continue
                            log_info("✓ OCSP restored correct version of %s (verified)", cert_name_raw)
                            mismatch_count += 1
                        except Exception as e:
                            log_error("❌ OCSP could not restore %s: %s", cert_name_raw, e)
                            stats["errors"] = stats.get("errors", 0) + 1
                    else:
                        log_debug("✓ OCSP %s checksum verified (matches database)", cert_name_raw)

            except Exception as e:
                log_warning("⚠️ OCSP error verifying %s: %s", cert_name_raw, e)
                stats["errors"] = stats.get("errors", 0) + 1

        if verify_count > 0:
            log_info(
                "🔍 OCSP verification complete: %d checked | ✓ %d restored (missing) | 🔄 %d corrected (mismatch)",
                verify_count, restored_count, mismatch_count
            )
            if stats is not None:
                stats["ocsp_verified"] = stats.get("ocsp_verified", 0) + verify_count
                stats["ocsp_restored"] = stats.get("ocsp_restored", 0) + restored_count
                stats["ocsp_corrected"] = stats.get("ocsp_corrected", 0) + mismatch_count

    except Exception as e:
        log_warning("⚠️ OCSP verification failed: %s", e)
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

    log_info("🔄 OCSP batching database updates for %d certificate(s)", len(all_ocsp_results))

    for cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, was_attempted in all_ocsp_results:
        # Clean PEM before fingerprinting (custom certs may have private keys/noise)
        cleaned_pem = _clean_pem(pem_data)
        # Compute certificate fingerprint for storage key
        cert_fp = _get_cert_pubkey_fingerprint(cleaned_pem)
        if not cert_fp:
            log_warning("⚠️ OCSP cannot store database cache for %s: failed to compute fingerprint", cert_name)
            continue

        # 1. Update OCSP response if we have a new one (using fingerprint-based key)
        if ocsp_der and ttl > 0:
            cache_key = f"ocsp/{cert_fp}"  # Use fingerprint instead of cert_name
            try:
                ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest().lower()
                err = db.upsert_job_cache(
                    service_id=None,  # Global cache entry
                    file_name=cache_key,
                    data=ocsp_der,
                    job_name="ocsp-refresh",
                    checksum=ocsp_checksum,
                )

                if err:
                    log_error("❌ OCSP error while storing response for %s (fingerprint: %s) in database: %s", cert_name, cert_fp[:16] + "...", err)
                    stats["errors"] = stats.get("errors", 0) + 1
                else:
                    log_info("✓ OCSP stored response for %s in database (fingerprint: %s, TTL=%ds)", cert_name, cert_fp[:16] + "...", ttl)

                    # Also store a marker entry with cert_name for differential tracking
                    # This allows _get_cached_ocsp_certs() to identify cached certificates
                    sanitized_name = _sanitize_filename(cert_name)
                    try:
                        db.upsert_job_cache(
                            service_id=None,
                            file_name=f"ocsp/{sanitized_name}",
                            data=cert_fp.encode("utf-8"),  # Store fingerprint reference
                            job_name="ocsp-refresh",
                            checksum=hashlib.sha256(cert_fp.encode("utf-8")).hexdigest().lower(),
                        )
                        log_debug("✓ OCSP stored cert_name marker for %s (fingerprint: %s)", cert_name, cert_fp[:16] + "...")
                    except Exception as e:
                        log_debug("⚠️ OCSP could not store cert_name marker for %s: %s", cert_name, e)
            except Exception as e:
                log_error("❌ OCSP exception while storing response for %s in database: %s", cert_name, e)
                stats["errors"] = stats.get("errors", 0) + 1

        # 2. ALWAYS store/update certificate content checksum for future differential checks (using fingerprint)
        cert_checksum_key = f"cert_checksum/{cert_fp}"
        try:
            err = db.upsert_job_cache(
                service_id=None,
                file_name=cert_checksum_key,
                data=cert_checksum.encode("utf-8"),
                job_name="ocsp-refresh",
                checksum=hashlib.sha256(cert_checksum.encode("utf-8")).hexdigest().lower(),
            )
            if err:
                log_debug("⚠️ OCSP could not store cert checksum for %s: %s", cert_name, err)
            else:
                log_debug("✓ OCSP persisted checksum for %s", cert_name)
        except Exception as e:
            log_debug("⚠️ OCSP exception while storing cert checksum for %s: %s", cert_name, e)


def _persist_ocsp_results_to_disk(
    all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]],
    stats: Optional[Dict[str, int]] = None,
) -> None:
    """
    Write OCSP responses to disk cache files (atomic writes with temporary files).
    Ensures existing files are only replaced when new fetches complete successfully.
    On any write error, keeps existing OCSP files intact with remaining TTL.
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
            # Compute certificate public key fingerprint for storage location
            cert_fp = _get_cert_pubkey_fingerprint(pem_data)
            if not cert_fp:
                log_error("❌ OCSP cannot store response for %s: failed to compute fingerprint", cert_name)
                stats["errors"] = stats.get("errors", 0) + 1
                continue

            # Acquire lock to prevent race conditions with concurrent OCSP fetches.
            # Lock is keyed by certificate public key fingerprint (not hostname/cert_name).
            lock_fd = _acquire_cert_lock(cert_fp)
            if lock_fd is None:
                # Avoid writing ocsp.der / ocsp.json without a lock.
                stats["errors"] = stats.get("errors", 0) + 1
                log_warning(
                    "⏭️ OCSP skipping disk write for %s (fingerprint: %s) due to lock acquisition failure",
                    cert_name,
                    cert_fp[:16] + "...",
                )
                continue
            try:
                # Create sharded directory using fingerprint (0-f distribution)
                # Example: /var/cache/bunkerweb/ssl/0/089433bd22ca2b9536b597a9fc7ca86cdd1d1df0193caaa205043b40f1ea435b/ocsp.der
                ocsp_cert_dir = _get_sharded_ocsp_path(cert_fp)
                try:
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    log_error("❌ OCSP error while creating sharded directory %s: %s", ocsp_cert_dir, e)
                    stats["errors"] = stats.get("errors", 0) + 1
                    raise  # Let finally block release the lock before skipping this cert

                # Write OCSP response to sharded cache location (atomic write with temp file)
                ocsp_path = ocsp_cert_dir / "ocsp.der"
                try:
                    # Write to temporary file first, then atomically move to final location
                    # This ensures existing file is only replaced if write succeeds completely
                    with tempfile.NamedTemporaryFile(dir=ocsp_cert_dir, delete=False, prefix=".ocsp_", suffix=".tmp") as tmp_file:
                        tmp_file.write(ocsp_der)
                        tmp_file.flush()
                        os.fsync(tmp_file.fileno())  # Ensure write is persisted
                        tmp_path = Path(tmp_file.name)

                    # Set permissions on temp file before moving
                    tmp_path.chmod(0o644)  # Readable by nginx

                    # Atomically move temp file to final location (overwrites only on success)
                    tmp_path.replace(ocsp_path)
                    log_info("✓ OCSP saved response for %s to disk at %s (fingerprint: %s)", cert_name, ocsp_path, cert_fp[:16] + "...")

                    # Write OCSP metadata to cache/ssl/{fingerprint}/ocsp.json
                    # Metadata includes cert_name, serial, fingerprint, expires, and must_staple flag
                    meta_path = ocsp_cert_dir / "ocsp.json"
                    try:
                        meta = _extract_cert_metadata(pem_data, cert_name)
                        # Add fingerprint reference for debugging/verification
                        meta["fingerprint"] = cert_fp
                        meta["expires"] = datetime.now(timezone.utc).isoformat() + f" + {ttl}s" if ttl else "unknown"
                        meta_path.write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
                        meta_path.chmod(0o644)
                        log_debug(
                            "✓ OCSP saved metadata for %s (fingerprint: %s, serial=%s, must_staple=%s)",
                            cert_name,
                            cert_fp[:16] + "...",
                            meta.get("serial") or "unknown",
                            meta.get("must_staple"),
                        )
                    except Exception as e:
                        log_debug("⚠️ OCSP metadata write failed for %s: %s", cert_name, e)

                    # Note: With fingerprint-based storage, SAN symlinks are no longer needed
                    # The NGINX code directly looks up OCSP responses by certificate fingerprint
                    # (previous implementation left here for reference but not executed)
                except Exception as e:
                    # Clean up any leftover temp files on error (existing ocsp.der remains intact)
                    try:
                        for tmp_file in ocsp_cert_dir.glob(".ocsp_*.tmp"):
                            tmp_file.unlink()
                    except Exception:
                        pass  # Ignore cleanup errors
                    log_error("❌ OCSP error while writing response for %s to disk: %s", cert_name, e)
                    log_info("ℹ️ OCSP kept existing OCSP response file for %s (new fetch failed)", cert_name)
                    stats["errors"] = stats.get("errors", 0) + 1
            finally:
                if lock_fd is not None:
                    _release_cert_lock(lock_fd, cert_fp)
        except Exception as e:
            log_error("❌ OCSP exception while writing response for %s to disk: %s", cert_name, e)
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
            log_warning(
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
    parser.add_argument("--force-fetch", action="store_true", help="Force refetch all OCSP responses from upstream PKI, do not replace existing files on error")
    args, unknown = parser.parse_known_args()
    force_all = args.force
    force_fetch = args.force_fetch

    try:
        force_flags = ""
        if force_all:
            force_flags += " [FORCE]"
        if force_fetch:
            force_flags += " [FORCE-FETCH]"
        log_info("🔄 OCSP refresh job started with differential update strategy (timeout in %d minutes%s)",
                 JOB_TIMEOUT // 60, force_flags)

        # Clean up stale lock files from previous crashed runs (defensive measure)
        _cleanup_stale_locks()

        # Acquire main lock for the entire OCSP refresh operation
        lock_fd_main = _acquire_cert_lock("main", timeout=300, stale_threshold=1800)
        if lock_fd_main is None:
            # If we can't acquire the main lock, avoid concurrent refresh runs.
            # This prevents overlapping disk/database writes and reduces race conditions.
            log_error("❌ OCSP could not acquire main lock; another instance may be running")
            return 1

        # Initialize database connection — this is our primary data source
        db = None
        if Database is not None:
            try:
                db = Database(LOG)
                log_debug("✓ OCSP database connection established")
            except Exception as e:
                log_error("❌ OCSP could not establish database connection: %s", e)
                return 2
        else:
            log_error("❌ OCSP Database module not available, cannot proceed")
            return 2

        # === Check for previously cached OCSP responses ===
        previous_ocsp_certs = _get_cached_ocsp_certs(db)
        log_info("ℹ️ OCSP found %d previously cached certificate(s)", len(previous_ocsp_certs))

        # === Early validation: check cache directory permissions ===
        try:
            CONFIGS_SSL_BASE.mkdir(parents=True, exist_ok=True)
            # Verify we can write to the cache directory
            test_file = CONFIGS_SSL_BASE / ".ocsp_write_test"
            try:
                test_file.touch()
                test_file.unlink()
                log_debug("✓ OCSP cache directory %s is readable and writable", CONFIGS_SSL_BASE)
            except PermissionError:
                log_error("❌ OCSP cache directory %s is not writable (permission denied). Check directory ownership and permissions.", CONFIGS_SSL_BASE)
                return 2
            except Exception as e:
                log_error("❌ OCSP could not verify write access to cache directory %s: %s", CONFIGS_SSL_BASE, e)
                return 2
        except Exception as e:
            log_error("❌ OCSP could not create cache directory %s: %s", CONFIGS_SSL_BASE, e)
            return 2

        # === Initialize sharded directory structure (16 subdirectories: 0-9, a-f) ===
        # This distributes OCSP responses across 16 directories for filesystem performance
        if not _init_sharded_ocsp_directories():
            log_warning("⚠️ OCSP sharded directory initialization had issues, will attempt to continue")

        # === Clean up old temporary OCSP files (older than 5 minutes) ===
        # Removes stale temp files from failed script runs before processing begins
        try:
            current_time = time.time()
            temp_cutoff = current_time - (5 * 60)  # 5 minutes ago
            cleanup_count = 0

            for tmp_file in CONFIGS_SSL_BASE.glob("**/.ocsp_*.tmp"):
                try:
                    if tmp_file.stat().st_mtime < temp_cutoff:
                        tmp_file.unlink()
                        cleanup_count += 1
                except Exception:
                    pass  # Ignore individual file cleanup errors

            if cleanup_count > 0:
                log_debug("🧹 OCSP cleaned up %d stale temporary file(s) (older than 5 minutes)", cleanup_count)
        except Exception as e:
            log_debug("⚠️ OCSP temporary file cleanup failed: %s", e)

        # Check if OCSP stapling is globally disabled
        ocsp_enabled = os.getenv("SSL_USE_OCSP_STAPLING", "yes").lower()
        if ocsp_enabled != "yes":
            log_info("🧹 OCSP stapling is globally disabled (SSL_USE_OCSP_STAPLING=%s), cleaning up all caches", ocsp_enabled)
            cleanup_ocsp_cache(db, purge_db=True)
            return 0

        # Wait for scheduler's directory purge to finish after service restart,
        # then restore cached OCSP responses from database to disk.
        # This handles ephemeral storage and post-restart cache directory cleanup.
        # Note: OCSP files may live under legacy flat dirs (ssl/<name>/ocsp.der) or
        # tree-sharded dirs (ssl/<hex1>/<hex2>/<fingerprint>/ocsp.der). Only checking
        # direct children of ssl/ misses the sharded layout and falsely logs "no cached files".
        ocsp_files_exist = (
            any(CONFIGS_SSL_BASE.rglob("ocsp.der")) if CONFIGS_SSL_BASE.is_dir() else False
        )
        if not ocsp_files_exist:
            log_info("🔄 OCSP no cached files on disk, waiting 2s for scheduler purge to finish before restoring from database...")
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
                        log_info("ℹ️ OCSP full refresh was recently run (%ds ago), will only process new/changed certificates", now_ts - last_refresh_time)
                except Exception:
                    pass

        # === Collect all OCSP data for batched database writes ===
        all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]] = []
        stashed_failures: List[Tuple[str, bytes]] = []


        # Process Let's Encrypt certificates from database tarball
        le_certs = _load_le_certs_from_db(db)
        if le_certs:
            log_info("ℹ️ OCSP loaded %d LE certificate(s) from database", len(le_certs))

            # Separate new certs from existing ones
            new_le_certs = {k: v for k, v in le_certs.items() if k not in previous_ocsp_certs}
            existing_le_certs = {k: v for k, v in le_certs.items() if k in previous_ocsp_certs}

            # ROBUSTNESS: Check disk files for "new" certs (database may be out of sync, cache cleared, or download aborted)
            # If a "new" cert has valid cached OCSP on disk, move it to "existing" to avoid re-fetching
            recategorized_certs = {}
            for cert_name, pem_data in list(new_le_certs.items()):
                fingerprint = _get_cert_pubkey_fingerprint(pem_data)
                if fingerprint:
                    cached_ttl, total_lifetime = get_cached_ocsp_ttl(cert_name, pem_data, fingerprint)
                    if cached_ttl is not None:
                        # Disk file exists with valid TTL - treat as unchanged, not new
                        log_info("ℹ️ OCSP disk file exists for %s (marked new in DB): TTL=%ds, recategorizing to existing", cert_name, cached_ttl)
                        recategorized_certs[cert_name] = pem_data
                        del new_le_certs[cert_name]
                        existing_le_certs[cert_name] = pem_data

            if recategorized_certs:
                log_info("ℹ️ OCSP recategorized %d cert(s) from new→existing due to valid disk cache", len(recategorized_certs))

            # For existing certs, check if certificate content has changed
            previous_le_checksums = _get_cert_checksums(db, existing_le_certs)
            changed_le_certs = {}
            unchanged_le_certs = {}

            for cert_name, pem_data in existing_le_certs.items():
                cleaned_pem = _clean_pem(pem_data)
                current_checksum = _calculate_cert_checksum(cleaned_pem)
                previous_checksum = previous_le_checksums.get(cert_name)

                if previous_checksum is None:
                    # No previous checksum found, treat as changed (will be recategorized by robustness check if valid disk cache exists)
                    changed_le_certs[cert_name] = pem_data
                    log_debug("ℹ️ OCSP no previous checksum found for %s (will check disk cache)", cert_name)
                elif current_checksum != previous_checksum:
                    # Certificate content has changed
                    changed_le_certs[cert_name] = pem_data
                    log_debug("🔄 OCSP certificate content changed for %s", cert_name)
                else:
                    # Certificate content unchanged
                    unchanged_le_certs[cert_name] = pem_data

            if new_le_certs:
                log_info("🆕 OCSP found %d newly issued LE certificate(s): %s", len(new_le_certs), ", ".join(sorted(new_le_certs.keys())))
                stats["le_certs_new"] = len(new_le_certs)

            if changed_le_certs:
                log_info("🔄 OCSP found %d LE certificate(s) with changed content: %s", len(changed_le_certs), ", ".join(sorted(changed_le_certs.keys())))
                stats["le_certs_changed"] = len(changed_le_certs)

            if unchanged_le_certs:
                if skip_unchanged_ttl_checks:
                    log_info("✓ OCSP skipping TTL checks for %d unchanged LE certificate(s) (recently run)", len(unchanged_le_certs))
                    stats["le_certs_skipped"] = stats.get("le_certs_skipped", 0) + len(unchanged_le_certs)
                else:
                    log_info("✓ OCSP checking TTL for %d LE certificate(s) unchanged: %s", len(unchanged_le_certs), ", ".join(sorted(unchanged_le_certs.keys())))

            stats["le_certs_processed"] = len(le_certs)

            # 1. Process newly issued certs (force refresh)
            for cert_name, pem_data in sorted(new_le_certs.items()):
                if check_job_timeout(f"new LE cert {cert_name}"): break
                refresh_job_lock(cert_name)
                res = _process_cert(cert_name, pem_data, db, stats, force_fetch=True)
                all_ocsp_results.append(res)
                if res[1] is None and res[5] and res[6]: # ocsp_der is None AND ocsp_url is present AND was_attempted is True
                    stashed_failures.append((cert_name, pem_data))

            # 2. Process changed certs (robustness: skip force-fetch if valid OCSP cached on disk)
            # This handles cases where checksums are missing but OCSP responses exist with fresh TTL
            recategorized_changed = {}
            for cert_name, pem_data in list(changed_le_certs.items()):
                # Clean PEM before fingerprinting (custom certs may have private keys/noise)
                cleaned_pem = _clean_pem(pem_data)
                fingerprint = _get_cert_pubkey_fingerprint(cleaned_pem)
                if fingerprint:
                    cached_ttl, total_lifetime = get_cached_ocsp_ttl(cert_name, pem_data, fingerprint)
                    if cached_ttl is not None and cached_ttl > 0:
                        # Valid OCSP cached on disk - skip force refresh
                        log_info("ℹ️ OCSP disk file exists for %s (marked changed due to missing checksum): TTL=%ds, skipping force-fetch", cert_name, cached_ttl)
                        recategorized_changed[cert_name] = pem_data
                        del changed_le_certs[cert_name]
                        unchanged_le_certs[cert_name] = pem_data

            if recategorized_changed:
                log_info("ℹ️ OCSP recategorized %d cert(s) from changed→unchanged due to valid disk cache", len(recategorized_changed))
                # Add recategorized certs to all_ocsp_results so their checksums get persisted to database
                # (even though we didn't fetch new OCSP responses, we need to record their checksums for future runs)
                for cert_name, pem_data in sorted(recategorized_changed.items()):
                    pem_checksum = _calculate_cert_checksum(pem_data)
                    # Tuple: (cert_name, ocsp_der=None, ttl=0, checksum, pem_data, ocsp_url=None, was_attempted=False)
                    # We're not fetching, just recording the cert's checksum for differential tracking
                    all_ocsp_results.append((cert_name, None, 0, pem_checksum, pem_data, None, False))
                    log_debug("✓ OCSP added recategorized cert %s to database persist list (checksum=%s)", cert_name, pem_checksum[:8])

            # Process remaining changed certs with force refresh
            for cert_name, pem_data in sorted(changed_le_certs.items()):
                if check_job_timeout(f"changed LE cert {cert_name}"): break
                refresh_job_lock(cert_name)
                res = _process_cert(cert_name, pem_data, db, stats, force_fetch=True)
                all_ocsp_results.append(res)
                if res[1] is None and res[5] and res[6]:
                    stashed_failures.append((cert_name, pem_data))

            # 3. Process unchanged certs (TTL check only or force-fetch if requested)
            if not skip_unchanged_ttl_checks:
                for cert_name, pem_data in sorted(unchanged_le_certs.items()):
                    if check_job_timeout(f"unchanged LE cert {cert_name}"): break
                    refresh_job_lock(cert_name)
                    res = _process_cert(cert_name, pem_data, db, stats, force_fetch=force_fetch)
                    all_ocsp_results.append(res)
                    if res[1] is None and res[5] and res[6]:
                        stashed_failures.append((cert_name, pem_data))

        else:
            log_info("ℹ️ OCSP no LE certificates found in database")

        # Check timeout before processing custom certs
        if not check_job_timeout("before custom cert processing"):
            # Process custom certificates from database
            custom_results = process_custom_certs(
                db,
                stats,
                lock_fd=lock_fd_main,
                refresh_fn=refresh_job_lock,
                timeout_fn=check_job_timeout,
                skip_unchanged_ttl_checks=skip_unchanged_ttl_checks,
                force_fetch=force_fetch
            )
            all_ocsp_results.extend(custom_results)
            for res in custom_results:
                if res[1] is None and res[5] and res[6]: # ocsp_der is None AND ocsp_url is present AND was_attempted is True
                    stashed_failures.append((res[0], res[4])) # cert_name, pem_data

        # === Final deferred retry for stashed failures ===
        if stashed_failures:
            log_info("⏸️ OCSP stashed %d failed fetch(es), waiting 120 seconds before final retry...", len(stashed_failures))

            # Use smaller sleeps to stay responsive and allow timeout checks
            for _ in range(120):
                if check_job_timeout("during stashed retry wait"): break
                time.sleep(1)

            if not check_job_timeout("before starting stashed retries"):
                for cert_name, pem_data in stashed_failures:
                    if check_job_timeout(f"stashed retry for {cert_name}"): break
                    log_info("🔄 OCSP retrying fetch for stashed failure: %s", cert_name)
                    refresh_job_lock(cert_name)
                    # Force fetch for the final retry attempt
                    all_ocsp_results.append(_process_cert(cert_name, pem_data, db, stats, force_fetch=True))

        # === Check if timeout has been reached and save partial results ===
        if check_job_timeout("after processing phase"):
            log_warning("⏱️ OCSP job timeout during processing. Saving partial results (%d cert(s)) to database and disk.", len(all_ocsp_results))
            _persist_ocsp_results_to_db(db, all_ocsp_results, stats)
            _persist_ocsp_results_to_disk(all_ocsp_results, stats)
            # Return early with partial results saved
            elapsed = time.time() - job_start_time
            log_warning("📊 OCSP partial job completed in %.3fs with %d results saved", elapsed, len(all_ocsp_results))
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
                    checksum=hashlib.sha256(str(now_ts).encode("utf-8")).hexdigest().lower(),
                )
                log_debug("✓ OCSP updated last full refresh timestamp to %d", now_ts)
            except Exception as e:
                log_debug("⚠️ OCSP could not update last full refresh timestamp: %s", e)

        # End-of-job verification: ensure OCSP files match database checksums
        # Restores missing files from database
        if not check_job_timeout("before final verification"):
            # Skip expensive verification if nothing changed and we were in "skip" mode
            if skip_unchanged_ttl_checks and not any(r[1] is not None for r in all_ocsp_results):
                log_info("🔍 OCSP skipping final verification (nothing changed and recently run)")
            else:
                log_info("🔍 OCSP running end-of-job verification and restoration...")
                _verify_and_restore_ocsp_files(db, stats)

        # Log a consolidated view of all OCSP responders resolved during this run.
        _log_ocsp_responder_dns_table()

        # Decide exit status based on results
        if stats["errors"] > 0:
            status = 2

        if stats["errors"] == 0:
            log_info("✓ OCSP refresh job completed successfully")
            # Check if all certificates are up-to-date (no fetches needed)
            if stats["ocsp_fetched_responses"] == 0 and (stats["le_certs_processed"] + stats["custom_certs_processed"]) > 0:
                log_info("✅ All OCSP responses are current and valid - no updates needed")
        else:
            log_warning("⚠️ OCSP refresh job completed with %d error(s)", stats["errors"])

        elapsed = time.time() - job_start_time
        log_info(
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
        log_error("❌ OCSP exception while running ocsp-refresh.py: %s", e)
        return 2
    finally:
        # Always release the main lock
        _release_cert_lock(lock_fd_main, "main")


# run it
sys_exit(main())
