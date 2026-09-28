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
from cryptography.x509 import AuthorityInformationAccess, TLSFeature, TLSFeatureType
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
    from jobs import (  # type: ignore
        Job,
        encode_ocsp_floor_payload,
        ocsp_floor_published_unix,
        ocsp_restore_skip_fingerprints,
        parse_ocsp_floor_bytes,
        parse_ocsp_floor_cache_name,
        load_disk_ocsp_floor,
        should_keep_disk_ocsp_floor,
    )
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

# Soft job deadline. Callers (certbot-new/renew, custom-cert) wait OCSP_REFRESH_TIMEOUT=2100s;
# keep this lower so the job can persist partial results before the parent kills the process.
JOB_TIMEOUT_SECONDS = 2040  # 34 minutes

# Use scheduler-managed cache directory (automatically synced from database on restart)
CONFIGS_SSL_BASE = Path(os.sep, "var", "cache", "bunkerweb", "ssl")


def _log_ocsp_cache_mount_hints() -> None:
    """
    Ops hint: handshake Lua reads the same path the job writes. Split mounts between
    scheduler and BunkerWeb break stapling unless each node restores via DB generate_caches.
    """
    log_info(
        "ℹ️ OCSP cache %s must be visible to BunkerWeb workers "
        "(shared volume with the scheduler, or restored via DB generate_caches on each instance)",
        CONFIGS_SSL_BASE,
    )
    try:
        mounts_path = Path("/proc/self/mountinfo")
        if not mounts_path.is_file():
            return
        cache_resolved = str(CONFIGS_SSL_BASE.resolve())
        best_mount = ""
        best_fstype = ""
        for line in mounts_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            # mountinfo: ... mount_point fstype ...
            parts = line.split()
            if len(parts) < 9:
                continue
            # Find separator "-" then fstype is next field
            try:
                dash = parts.index("-")
            except ValueError:
                continue
            if dash + 1 >= len(parts):
                continue
            mount_point = parts[4]
            fstype = parts[dash + 1]
            if cache_resolved == mount_point or cache_resolved.startswith(mount_point.rstrip("/") + "/"):
                if len(mount_point) >= len(best_mount):
                    best_mount = mount_point
                    best_fstype = fstype
        remoteish = {"nfs", "nfs4", "cifs", "smb", "ceph", "fuse", "fuse.ceph", "glusterfs", "afs"}
        if best_fstype and (best_fstype in remoteish or best_fstype.startswith("fuse")):
            log_info(
                "ℹ️ OCSP cache appears on %s (%s); local /run flock is paired with "
                "O_EXCL leases under %s/.ocsp-locks for multi-node writers.",
                best_fstype,
                best_mount or CONFIGS_SSL_BASE,
                CONFIGS_SSL_BASE,
            )
    except Exception as e:
        log_debug("⚠️ OCSP could not inspect cache mount type: %s", e)


MIN_TTL = 4500  # 75 minutes: minimum safety threshold. Smart refresh uses max(MIN_TTL, 20% of response lifetime)
OPENSSL_BIN = "/usr/bin/openssl"

# Forensic provenance stamped into every GOOD ocsp.json for this process invocation.
_JOB_RUN_ID: Optional[str] = None
_OPENSSL_IDENTITY: Optional[Dict[str, Any]] = None

_FINGERPRINT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OCSP_RESPONDER_DNS_CACHE_MAX = 256
# Empty/failed lookups only: one brief sticky miss must not fail every cert that
# shares this OCSP hostname. Positive answers are never reused across certs —
# CDN/anycast can move mid-job while later leaves would still dial the first IP.
DNS_CACHE_NEGATIVE_TTL = 15
_OCSP_RESPONDER_DNS_NEGATIVE: "OrderedDict[str, float]" = OrderedDict()
# Last successful resolution per host (logging / diagnostics only — not used to dial).
_OCSP_RESPONDER_DNS_LAST: "OrderedDict[str, List[str]]" = OrderedDict()
# Cert-name markers for differential tracking (cert_name → fingerprint hex).
OCSP_MARKER_PREFIX = "ocsp-marker/"


def _is_safe_ip_str(ip_str: str) -> bool:
    """
    Check whether an IP string is safe for outbound connections (SSRF defense).

    Require a globally routable address (`ipaddress.is_global`). That rejects
    RFC1918, loopback, link-local, multicast, reserved, *and* RFC6598 CGNAT
    ``100.64.0.0/10`` (which Python's ``is_private`` does not cover). Matches
    BunkerWeb's Lua ``ip_is_global`` notion of non-internal space.
    """
    import ipaddress

    try:
        return ipaddress.ip_address(ip_str).is_global
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

    Positive resolutions always call getaddrinfo (no cross-cert IP stickiness).
    Only empty/failed lookups are cached briefly (DNS_CACHE_NEGATIVE_TTL).
    """
    parsed = urlparse(ocsp_url)
    hostname = parsed.hostname or ""
    if not hostname:
        return "", []

    now = time.time()
    if hostname in _OCSP_RESPONDER_DNS_NEGATIVE:
        cached_at = _OCSP_RESPONDER_DNS_NEGATIVE[hostname]
        if now - cached_at < DNS_CACHE_NEGATIVE_TTL:
            _OCSP_RESPONDER_DNS_NEGATIVE.move_to_end(hostname)
            return hostname, []
        try:
            del _OCSP_RESPONDER_DNS_NEGATIVE[hostname]
        except KeyError:
            pass

    port = parsed.port or default_port
    ips = _resolve_hostname_to_ips(hostname, port)
    if not ips:
        _OCSP_RESPONDER_DNS_NEGATIVE[hostname] = now
        _OCSP_RESPONDER_DNS_NEGATIVE.move_to_end(hostname)
        while len(_OCSP_RESPONDER_DNS_NEGATIVE) > _OCSP_RESPONDER_DNS_CACHE_MAX:
            _OCSP_RESPONDER_DNS_NEGATIVE.popitem(last=False)
        return hostname, []

    try:
        del _OCSP_RESPONDER_DNS_NEGATIVE[hostname]
    except KeyError:
        pass
    _OCSP_RESPONDER_DNS_LAST[hostname] = list(ips)
    _OCSP_RESPONDER_DNS_LAST.move_to_end(hostname)
    while len(_OCSP_RESPONDER_DNS_LAST) > _OCSP_RESPONDER_DNS_CACHE_MAX:
        _OCSP_RESPONDER_DNS_LAST.popitem(last=False)
    return hostname, ips


def _invalidate_ocsp_responder_dns(hostname: str) -> None:
    """Drop sticky DNS state so the next lookup re-resolves (CDN/anycast cutover)."""
    if not hostname:
        return
    cleared = False
    for store in (_OCSP_RESPONDER_DNS_NEGATIVE, _OCSP_RESPONDER_DNS_LAST):
        try:
            del store[hostname]
            cleared = True
        except KeyError:
            pass
    if cleared:
        log_debug("🔄 OCSP invalidated DNS cache for responder %s", hostname)


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
    Log a consolidated uniq table (OCSP responder hostnames -> last resolved IPs).
    """
    if not _OCSP_RESPONDER_DNS_LAST and not _OCSP_RESPONDER_DNS_NEGATIVE:
        log_debug("ℹ️ OCSP responder DNS table: no DNS lookups performed")
        return

    # Print as a Markdown-like table for easy copy/paste (last successful resolve per host).
    rows = []
    for hostname, ips in sorted(_OCSP_RESPONDER_DNS_LAST.items()):
        ip_list = ", ".join(ips) if ips else ""
        rows.append(f"| {hostname} | {ip_list} |")
    for hostname in sorted(_OCSP_RESPONDER_DNS_NEGATIVE.keys()):
        if hostname not in _OCSP_RESPONDER_DNS_LAST:
            rows.append(f"| {hostname} | (negative cache) |")

    if not rows:
        log_debug("ℹ️ OCSP responder DNS table: no DNS lookups performed")
        return

    log_info("📇 OCSP responder DNS table (uniq responders):\n| Responder Hostname | Resolved IPs |\n|---|---|\n%s", "\n".join(rows))


_CACHE_ROOT_RESOLVED: Optional[Path] = None


def _cache_root_resolved() -> Path:
    """Resolved absolute cache root (created if needed)."""
    global _CACHE_ROOT_RESOLVED
    if _CACHE_ROOT_RESOLVED is None:
        CONFIGS_SSL_BASE.mkdir(parents=True, exist_ok=True)
        _CACHE_ROOT_RESOLVED = CONFIGS_SSL_BASE.resolve()
    return _CACHE_ROOT_RESOLVED


def _assert_path_under_cache_root(path: Path) -> Path:
    """
    Resolve path and require it to stay under CONFIGS_SSL_BASE.
    Blocks symlink/jail escapes that would write or read outside the OCSP tree.
    """
    root = _cache_root_resolved()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"OCSP path escapes cache root ({root}): {resolved}") from exc
    return resolved


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


def _resolved_sharded_ocsp_path(fingerprint: str) -> Path:
    """Shard directory after parents exist; realpath must stay under the cache root."""
    shard = _get_sharded_ocsp_path(fingerprint)
    if shard.name == "unknown":
        raise ValueError("empty fingerprint")
    shard.parent.mkdir(parents=True, exist_ok=True)
    return _assert_path_under_cache_root(shard)


def _ocsp_cache_relpath(fingerprint: str, leaf: str) -> Optional[str]:
	"""Job-cache file_name that generate_caches writes to the path the handshake opens.

	plugin cache root is /var/cache/bunkerweb/ssl, so
	{hex1}/{hex2}/{fingerprint}/ocsp.der becomes the sharded ocsp.der Lua reads.
	"""
	normalized = _normalize_fingerprint(fingerprint)
	if not normalized or leaf not in ("ocsp.der", "issuer.pem", "ocsp.json"):
		return None
	return f"{normalized[0]}/{normalized[1]}/{normalized}/{leaf}"


def _fingerprint_from_ocsp_der_name(file_name: str) -> Optional[str]:
	"""Fingerprint for a sharded ocsp.der row ({h1}/{h2}/{fp}/ocsp.der)."""
	parts = file_name.split("/")
	if len(parts) == 4 and parts[3] == "ocsp.der":
		return _normalize_fingerprint(parts[2])
	return None


def _fingerprint_from_issuer_name(file_name: str) -> Optional[str]:
	"""Fingerprint for a sharded issuer.pem row ({h1}/{h2}/{fp}/issuer.pem)."""
	parts = file_name.split("/")
	if len(parts) == 4 and parts[3] == "issuer.pem":
		return _normalize_fingerprint(parts[2])
	return None


def _fingerprint_from_meta_name(file_name: str) -> Optional[str]:
	"""Fingerprint for a sharded ocsp.json metadata row."""
	parts = file_name.split("/")
	if len(parts) == 4 and parts[3] == "ocsp.json":
		return _normalize_fingerprint(parts[2])
	return None


def _delete_fingerprint_db_rows(db: Any, fingerprint: str) -> None:
	"""Drop sharded response/issuer/metadata and checksum rows for one certificate."""
	if db is None or not fingerprint:
		return
	names = [f"cert_checksum/{fingerprint}"]
	for leaf in ("ocsp.der", "issuer.pem", "ocsp.json"):
		rel = _ocsp_cache_relpath(fingerprint, leaf)
		if rel:
			names.append(rel)
	for name in names:
		try:
			db.delete_job_cache(file_name=name, job_name="ocsp-refresh")
		except Exception:
			pass


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


def _ocsp_marker_relpath(cert_name: str) -> Optional[str]:
    """DB file_name for a cert-name marker (data = fingerprint hex)."""
    if not cert_name or not re.match(r"^[A-Za-z0-9_.*-]+$", cert_name):
        return None
    return f"{OCSP_MARKER_PREFIX}{_sanitize_filename(cert_name)}"


def _read_cert_name_marker(db: Any, cert_name: str) -> Optional[str]:
    """Return fingerprint hex from ocsp-marker/<cert_name>."""
    if db is None:
        return None
    key = _ocsp_marker_relpath(cert_name)
    if not key:
        return None
    try:
        marker_data = db.get_job_cache_file(file_name=key, job_name="ocsp-refresh")
        if not marker_data:
            return None
        decoded = marker_data.decode("utf-8", errors="ignore").strip()
        return _normalize_fingerprint(decoded)
    except Exception:
        return None


def _upsert_cert_name_marker(db: Any, cert_name: str, fingerprint: str) -> None:
    """Store cert_name → fingerprint under ocsp-marker/."""
    if db is None or not fingerprint:
        return
    marker_key = _ocsp_marker_relpath(cert_name)
    if not marker_key:
        return
    db.upsert_job_cache(
        service_id=None,
        file_name=marker_key,
        data=fingerprint.encode("utf-8"),
        job_name="ocsp-refresh",
        checksum=hashlib.sha256(fingerprint.encode("utf-8")).hexdigest().lower(),
    )


def _delete_cert_name_marker(db: Any, cert_name: str) -> None:
    """Remove ocsp-marker/<cert_name>."""
    if db is None:
        return
    key = _ocsp_marker_relpath(cert_name)
    if not key:
        return
    try:
        db.delete_job_cache(file_name=key, job_name="ocsp-refresh")
    except Exception:
        pass


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


def _spki_der_from_cert(cert: x509.Certificate) -> bytes:
    """SubjectPublicKeyInfo DER for SPKI pin comparisons."""
    return cert.public_key().public_bytes(
        encoding=Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _ocsp_signer_ends_on_issuer_spki(ocsp_der: bytes, issuer: x509.Certificate) -> bool:
    """
    True when the OCSP BasicResponse signer is the shard issuer itself (same SPKI)
    or a responder certificate directly issued by that issuer.

    OpenSSL ``-CAfile issuer -partial_chain`` usually enforces this; this pin makes
    the shard's issuer SPKI explicit so a mismatched restore cannot publish.
    """
    try:
        resp = x509_ocsp.load_der_ocsp_response(ocsp_der)
        issuer_spki = _spki_der_from_cert(issuer)
    except Exception:
        return False

    embedded: List[x509.Certificate] = []
    try:
        embedded = list(resp.certificates)
    except Exception:
        embedded = []

    if not embedded:
        # Issuer-signed response with no embedded certs; OpenSSL already used -CAfile.
        return True

    for cert in embedded:
        try:
            if _spki_der_from_cert(cert) == issuer_spki:
                return True
        except Exception:
            continue

    for cert in embedded:
        try:
            if hasattr(cert, "verify_directly_issued_by"):
                cert.verify_directly_issued_by(issuer)
                return True
        except Exception:
            continue

    # Older cryptography: verify tbs signature with the issuer public key.
    try:
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    except Exception:
        return False

    for cert in embedded:
        try:
            if cert.issuer != issuer.subject:
                continue
            pub = issuer.public_key()
            hash_alg = cert.signature_hash_algorithm
            if hash_alg is None:
                continue
            if isinstance(pub, rsa.RSAPublicKey):
                pub.verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), hash_alg)
                return True
            if isinstance(pub, ec.EllipticCurvePublicKey):
                pub.verify(cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(hash_alg))
                return True
        except Exception:
            continue

    return False


def _ocsp_lock_root_candidates() -> List[Path]:
    """Local runtime dirs for flock files (never the OCSP cache tree)."""
    return [
        Path(os.sep, "run", "bunkerweb"),
        Path(os.sep, "var", "run", "bunkerweb"),
        Path(os.sep, "tmp", "bunkerweb"),
    ]


def _prepare_ocsp_lock_root() -> Optional[Path]:
    """
    Pick a non-world-writable local directory for advisory locks.

    Local flock alone is not enough when several schedulers share CONFIGS_SSL_BASE:
    /run is node-private. Cross-node exclusion uses O_EXCL leases on the cache volume
    (see _acquire_shared_lease). Local flock still serializes writers on one host and
    avoids depending on NFS flock semantics.
    """
    for candidate in _ocsp_lock_root_candidates():
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
            if st.st_mode & 0o022:
                log_error("❌ OCSP lock directory %s has unsafe permissions (mode=%o).", candidate, st.st_mode & 0o777)
                continue
            return candidate
        except Exception as e:
            log_debug("⚠️ OCSP lock candidate stat failed for %s: %s", candidate, e)
            continue
    return None


def _fingerprint_lock_file(lock_root: Path, cert_fp: str) -> Path:
    """Per-SPKI lock path under the local runtime root (sharded)."""
    return lock_root / "ocsp-locks" / cert_fp[0] / cert_fp[1] / f"ocsp-{cert_fp}.lock"


def _shared_lease_path(cert_name: str) -> Path:
    """
    Per-cert lease on the shared OCSP cache volume (not flock).

    O_EXCL create is the cross-node mutex; /run flock only covers one host.
    """
    cert_fp = _normalize_fingerprint(cert_name)
    base = CONFIGS_SSL_BASE / ".ocsp-locks"
    if cert_fp and cert_name != "main":
        return base / cert_fp[0] / cert_fp[1] / f"ocsp-{cert_fp}.lease"
    return base / f"ocsp-{_sanitize_filename(cert_name)}.lease"


def _new_lease_token() -> str:
    import socket

    return f"{socket.gethostname()}\n{os.getpid()}\n{time.time_ns()}\n"


class OcspLock:
    """Local flock fd plus optional shared-volume O_EXCL lease."""

    __slots__ = ("local_fd", "lease_path", "lease_token", "cert_name")

    def __init__(
        self,
        local_fd: int,
        cert_name: str,
        lease_path: Optional[Path] = None,
        lease_token: Optional[str] = None,
    ) -> None:
        self.local_fd = local_fd
        self.cert_name = cert_name
        self.lease_path = lease_path
        self.lease_token = lease_token


def _prepare_shared_lease_parent(lease_path: Path) -> bool:
    try:
        lease_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if lease_path.parent.is_symlink() or (CONFIGS_SSL_BASE / ".ocsp-locks").is_symlink():
            log_error("❌ OCSP shared lease directory is a symlink (refusing).")
            return False
        return True
    except Exception as e:
        log_debug("⚠️ OCSP could not prepare shared lease directory %s: %s", lease_path.parent, e)
        return False


def _lease_is_stale(lease_path: Path, stale_threshold: int) -> bool:
    try:
        age = time.time() - lease_path.stat().st_mtime
        return age > stale_threshold
    except FileNotFoundError:
        return True
    except Exception:
        return False


def _try_reclaim_stale_lease(lease_path: Path, stale_threshold: int) -> bool:
    """Best-effort unlink of a stale shared lease so O_EXCL can succeed."""
    if not _lease_is_stale(lease_path, stale_threshold):
        return False
    try:
        lease_path.unlink()
        log_warning(
            "⚠️ OCSP reclaimed stale shared lease %s (age > %ds)",
            lease_path.name,
            stale_threshold,
        )
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        log_debug("⚠️ OCSP could not reclaim shared lease %s: %s", lease_path, e)
        return False


def _acquire_shared_lease(
    cert_name: str,
    timeout: int,
    stale_threshold: int,
) -> Optional[Tuple[Path, str]]:
    """
    Cross-node mutex via exclusive create on the shared cache volume.

    Does not use fcntl.flock on the cache FS (unreliable on NFS). Returns
    (lease_path, token) or None on timeout. If the cache tree is unavailable,
    returns None so the caller can fail closed for publishes.
    """
    lease_path = _shared_lease_path(cert_name)
    if not _prepare_shared_lease_parent(lease_path):
        return None

    start_time = time.time()
    while time.time() - start_time < timeout:
        token = _new_lease_token()
        fd = None
        try:
            fd = os.open(str(lease_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, token.encode())
                os.fsync(fd)
            finally:
                os.close(fd)
                fd = None
            return lease_path, token
        except FileExistsError:
            if _try_reclaim_stale_lease(lease_path, stale_threshold):
                continue
            if cert_name == "main":
                log_error(
                    "❌ OCSP job is already running on another node (shared lease held at %s). "
                    "Exiting to avoid concurrent cache publishes.",
                    lease_path,
                )
                return None
            elapsed = time.time() - start_time
            remaining = timeout - elapsed
            if remaining <= 0:
                break
            log_debug(
                "⏳ OCSP waiting for shared lease on %s (%.0fs remaining)...",
                cert_name,
                remaining,
            )
            time.sleep(0.5)
            continue
        except Exception as e:
            if fd is not None:
                try:
                    os.close(fd)
                except Exception:
                    pass
            log_debug("⚠️ OCSP shared lease acquire failed for %s: %s", cert_name, e)
            time.sleep(0.5)

    log_warning(
        "⚠️ OCSP could not acquire shared cache lease for %s after %ds at %s",
        cert_name,
        timeout,
        lease_path,
    )
    return None


def _release_shared_lease(lease_path: Optional[Path], lease_token: Optional[str]) -> None:
    if lease_path is None or lease_token is None:
        return
    try:
        if not lease_path.is_file() or lease_path.is_symlink():
            return
        # Only unlink if we still own the lease (another node may have reclaimed).
        raw = lease_path.read_text(encoding="utf-8", errors="ignore")
        if raw != lease_token:
            log_debug("⚠️ OCSP shared lease %s no longer owned; skip unlink", lease_path)
            return
        lease_path.unlink()
    except FileNotFoundError:
        return
    except Exception as e:
        log_debug("⚠️ OCSP shared lease release failed for %s: %s", lease_path, e)


def _refresh_shared_lease(lease_path: Optional[Path], lease_token: Optional[str]) -> Optional[str]:
    """Rewrite lease content to refresh mtime; returns updated token or None."""
    if lease_path is None or lease_token is None:
        return lease_token
    try:
        if not lease_path.is_file():
            return lease_token
        raw = lease_path.read_text(encoding="utf-8", errors="ignore")
        if raw != lease_token:
            return lease_token
        parts = lease_token.split("\n")
        host = parts[0] if parts else ""
        pid = parts[1] if len(parts) > 1 else str(os.getpid())
        new_token = f"{host}\n{pid}\n{time.time_ns()}\n"
        fd = os.open(str(lease_path), os.O_WRONLY | os.O_TRUNC, 0o600)
        try:
            os.write(fd, new_token.encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        return new_token
    except Exception as e:
        log_debug("⚠️ OCSP shared lease refresh failed for %s: %s", lease_path, e)
        return lease_token


def _acquire_local_flock(
    cert_name: str,
    timeout: int,
    stale_threshold: int,
) -> Optional[int]:
    """Node-local fcntl.flock under /run (or fallback). Returns fd or None."""
    cert_fp = _normalize_fingerprint(cert_name)
    lock_root = _prepare_ocsp_lock_root()
    if not lock_root:
        return None

    lock_dir: Optional[Path] = None
    lock_file: Optional[Path] = None

    if cert_fp and cert_name != "main":
        lock_file = _fingerprint_lock_file(lock_root, cert_fp)
        lock_dir = lock_file.parent
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
    else:
        sanitized_name = _sanitize_filename(cert_name)
        lock_dir = lock_root
        lock_file = lock_dir / f"ocsp-{sanitized_name}.lock"

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            if lock_file.exists():
                mtime = lock_file.stat().st_mtime
                age = time.time() - mtime
                if age > stale_threshold:
                    log_warning(
                        "⚠️ OCSP detected stale local lock for %s (age %.0fs > threshold %ds). "
                        "Previous process may have crashed. Proceeding without unlinking to avoid a race.",
                        cert_name, age, stale_threshold
                    )
        except Exception as e:
            log_debug("⚠️ OCSP stale lock detection failed for %s: %s", lock_file, e)

        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    os.write(fd, str(int(time.time())).encode())
                except Exception as e:
                    log_debug("⚠️ OCSP could not write lock timestamp for %s: %s", cert_name, e)
                return fd
            except BlockingIOError:
                os.close(fd)

                if cert_name == "main":
                    log_error(
                        "❌ OCSP job is already running (another instance holds the local lock). "
                        "Exiting to avoid concurrent operations."
                    )
                    return None

                elapsed = time.time() - start_time
                remaining_time = timeout - elapsed
                if remaining_time > 0:
                    log_debug("⏳ OCSP waiting for local lock on %s (%.0fs remaining)...", cert_name, remaining_time)
                    time.sleep(0.5)
                    continue
                else:
                    break
        except Exception as e:
            log_debug("⚠️ OCSP local lock acquisition attempt failed for %s: %s", cert_name, e)
            time.sleep(0.5)

    if cert_name == "main":
        chosen_lock_dir = str(lock_dir) if lock_dir else "/tmp/bunkerweb"
        log_error(
            "❌ OCSP job timed out waiting for the main local lock (%ds timeout). "
            "Another OCSP job is still running. "
            "Check for stale lock files: rm -f %s/ocsp*.lock",
            timeout,
            chosen_lock_dir,
        )
    else:
        log_warning(
            "⚠️ OCSP could not acquire local lock for %s after %ds.",
            cert_name, timeout
        )
    return None


def _release_local_flock(fd: Optional[int], cert_name: str = "undefined") -> None:
    if fd is None:
        return

    cert_fp = _normalize_fingerprint(cert_name)
    lock_file: Optional[Path] = None

    if cert_fp and cert_name != "main":
        for root in _ocsp_lock_root_candidates():
            candidate = _fingerprint_lock_file(root, cert_fp)
            if candidate.exists():
                lock_file = candidate
                break
        if lock_file is None:
            root = _prepare_ocsp_lock_root()
            if root:
                lock_file = _fingerprint_lock_file(root, cert_fp)
    else:
        sanitized_name = _sanitize_filename(cert_name)
        lock_file_name = f"ocsp-{sanitized_name}.lock"
        for lock_dir in _ocsp_lock_root_candidates():
            candidate = lock_dir / lock_file_name
            if candidate.exists():
                lock_file = candidate
                break

    try:
        if lock_file is not None:
            try:
                if lock_file.exists() and not lock_file.is_symlink():
                    lock_file.unlink()
            except Exception as e:
                log_debug("⚠️ OCSP lock file unlink failed for %s: %s", lock_file, e)

        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    except Exception as e:
        log_debug("⚠️ OCSP could not release local lock for %s: %s", cert_name, e)


def _acquire_cert_lock(cert_name: str, timeout: int = 300, stale_threshold: int = 600) -> Optional[OcspLock]:
    """
    Acquire exclusion for OCSP publish/fetch of one certificate (or the main job).

    Two layers:
      1) Local fcntl.flock under /run (reliable on one host; not visible cross-node)
      2) O_EXCL lease under CONFIGS_SSL_BASE/.ocsp-locks (shared cache coherence bus)

    Both must succeed. Local-only locking left multi-node writers free to tear
    issuer.pem / ocsp.der / ocsp.json on a shared volume.
    """
    # Split budget so a stuck remote lease cannot burn the whole timeout after local success.
    local_budget = max(1, timeout // 2)
    shared_budget = max(1, timeout - local_budget)

    local_fd = _acquire_local_flock(cert_name, timeout=local_budget, stale_threshold=stale_threshold)
    if local_fd is None:
        return None

    lease = _acquire_shared_lease(cert_name, timeout=shared_budget, stale_threshold=stale_threshold)
    if lease is None:
        _release_local_flock(local_fd, cert_name)
        return None

    lease_path, lease_token = lease
    return OcspLock(local_fd=local_fd, cert_name=cert_name, lease_path=lease_path, lease_token=lease_token)


def _release_cert_lock(lock: Optional[OcspLock], cert_name: str = "undefined") -> None:
    """Release shared lease then local flock."""
    if lock is None:
        return
    name = cert_name if cert_name != "undefined" else lock.cert_name
    _release_shared_lease(lock.lease_path, lock.lease_token)
    _release_local_flock(lock.local_fd, name)


def _refresh_cert_lock(lock: Optional[OcspLock], cert_name: str) -> None:
    """
    Refresh local lock + shared lease timestamps to prove the process is still alive.
    """
    if lock is None:
        return

    fd = lock.local_fd
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.ftruncate(fd, 0)
        timestamp = str(int(time.time())).encode()
        os.write(fd, timestamp)
        os.fsync(fd)
        log_debug("🔒 OCSP refreshed local lock timestamp for %s", cert_name)
    except Exception as e:
        log_debug("⚠️ OCSP could not refresh local lock timestamp for %s: %s", cert_name, e)

    new_token = _refresh_shared_lease(lock.lease_path, lock.lease_token)
    if new_token is not None:
        lock.lease_token = new_token


def _try_unlink_stale_lock(lock_file: Path, stale_threshold: int, current_time: float) -> bool:
    """Unlink one stale lock if we can acquire it. Returns True if removed."""
    try:
        mtime = lock_file.stat().st_mtime
        age = current_time - mtime
        # stale_threshold < 0 means "always try".
        if stale_threshold >= 0 and age <= stale_threshold:
            return False
    except Exception as e:
        log_debug("⚠️ OCSP could not clean lock file %s: %s", lock_file.name, e)
        return False

    fd = None
    try:
        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            lock_file.unlink()
        except Exception as e:
            log_debug("⚠️ OCSP could not unlink stale lock file %s: %s", lock_file.name, e)
        log_debug("🧹 OCSP removed stale lock file %s (age %.0fs)", lock_file.name, age)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        return True
    except BlockingIOError:
        if fd is not None:
            try:
                os.close(fd)
            except Exception as e:
                log_debug("⚠️ OCSP could not close stale lock fd: %s", e)
        return False
    except Exception as e:
        if fd is not None:
            try:
                os.close(fd)
            except Exception as close_e:
                log_debug("⚠️ OCSP could not close stale lock fd after exception: %s", close_e)
        log_debug("⚠️ OCSP failed to unlink stale lock file %s: %s", lock_file.name, e)
        return False


def _cleanup_stale_locks(stale_threshold: int = 300) -> None:
    """
    Clean up stale lock files from previous crashed/aborted jobs at startup.
    Scans local runtime lock roots (including ocsp-locks/) and removes leftover
    lock files that used to live on the OCSP cache filesystem.
    """
    current_time = time.time()
    cleaned = 0

    for lock_dir in _ocsp_lock_root_candidates():
        if not lock_dir.exists():
            continue
        try:
            if lock_dir.is_symlink():
                continue
            st = lock_dir.stat()
            if st.st_mode & 0o022:
                continue
        except Exception as e:
            log_debug("⚠️ OCSP lock directory stat failed for %s: %s", lock_dir, e)
            continue

        # Main / named locks at runtime root
        for lock_file in lock_dir.glob("ocsp-*.lock"):
            if _try_unlink_stale_lock(lock_file, stale_threshold, current_time):
                cleaned += 1

        # Fingerprint locks under runtime/ocsp-locks/h1/h2/
        locks_root = lock_dir / "ocsp-locks"
        if locks_root.is_dir() and not locks_root.is_symlink():
            try:
                for lock_file in locks_root.glob("*/*/ocsp-*.lock"):
                    if _try_unlink_stale_lock(lock_file, stale_threshold, current_time):
                        cleaned += 1
            except Exception as e:
                log_debug("⚠️ OCSP fingerprint lock cleanup failed under %s: %s", locks_root, e)

    # Stale shared O_EXCL leases (multi-node mutex) under .ocsp-locks/
    if CONFIGS_SSL_BASE.is_dir():
        leases_root = CONFIGS_SSL_BASE / ".ocsp-locks"
        if leases_root.is_dir() and not leases_root.is_symlink():
            try:
                for lease_file in leases_root.glob("**/ocsp-*.lease"):
                    try:
                        age = current_time - lease_file.stat().st_mtime
                        if age > stale_threshold:
                            lease_file.unlink()
                            cleaned += 1
                            log_debug("🧹 OCSP removed stale shared lease %s (age %.0fs)", lease_file.name, age)
                    except Exception as e:
                        log_debug("⚠️ OCSP shared lease cleanup failed for %s: %s", lease_file, e)
            except Exception as e:
                log_debug("⚠️ OCSP shared lease tree cleanup failed: %s", e)

    if cleaned > 0:
        log_info("🧹 OCSP cleaned up %d stale lock file(s) from previous runs", cleaned)


def is_safe_url(url: str) -> bool:
    """
    Validate that a URL is safe to fetch (HTTP/HTTPS only, globally routable IPs).
    Prevents Server-Side Request Forgery (SSRF) when fetching OCSP responses or issuer certs
    from URLs embedded in untrusted certificates. Blocks RFC1918, loopback, link-local,
    and RFC6598 CGNAT ``100.64.0.0/10`` via ``_is_safe_ip_str`` / ``ipaddress.is_global``.

    Security note: Even if DNS rebinding occurs, the OCSP response is cryptographically
    verified against the issuer's public key (see fetch_ocsp_response). An attacker cannot
    forge a valid OCSP response without the issuer's private key.
    """
    import socket

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
    Extract the first usable OCSP responder URL from the leaf AIA extension.
    Validates the URL scheme is http:// or https://.
    Returns a normalized URI if present and valid, else None.
    """
    uris = extract_ocsp_aia_uris(pem_data, cert_name)
    return uris[0] if uris else None


def _normalize_ocsp_aia_uri(url: Optional[str]) -> Optional[str]:
    """
    Canonical form for AIA OCSP URI comparison: strip, http(s) only,
    lowercase scheme and host, preserve path/query/fragment.
    """
    if not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if ":" in host and not host.startswith("["):
        netloc = f"[{host}]"
    else:
        netloc = host
    if parsed.port is not None:
        default = 80 if scheme == "http" else 443
        if parsed.port != default:
            netloc = f"{netloc}:{parsed.port}"
    path = parsed.path or ""
    query = f"?{parsed.query}" if parsed.query else ""
    frag = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{scheme}://{netloc}{path}{query}{frag}"


def extract_ocsp_aia_uris(pem_data: bytes, cert_name: str = "") -> List[str]:
    """
    All http(s) OCSP URIs from the leaf AIA extension, normalized and de-duplicated.
    Order follows the certificate.
    """
    log_debug("🔒 OCSP checking support for certificate %s", cert_name)
    out: List[str] = []
    seen = set()
    try:
        cert = x509.load_pem_x509_certificate(pem_data)
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia_value = cast(AuthorityInformationAccess, aia.value)
        for access_description in aia_value:
            if access_description.access_method != AuthorityInformationAccessOID.OCSP:
                continue
            normalized = _normalize_ocsp_aia_uri(getattr(access_description.access_location, "value", None))
            if not normalized:
                log_warning(
                    "⚠️ OCSP AIA URI has invalid scheme/host for %s: %s",
                    cert_name,
                    getattr(access_description.access_location, "value", None),
                )
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized)
            log_debug("🌐 OCSP found AIA responder URL for %s: %s", cert_name, normalized)
        if not out:
            log_debug("🔒 OCSP no responder URL advertised in %s", cert_name)
        return out
    except x509.ExtensionNotFound:
        log_debug("🔒 OCSP no AIA extension found in %s", cert_name)
        return []
    except Exception as e:
        log_debug("🔒 OCSP failed to extract OCSP URL from %s: %s", cert_name, e)
        return []


def _pin_aia_ocsp_uri(pem_data: bytes, fetch_url: Optional[str], cert_name: str = "") -> Optional[str]:
    """
    Require fetch_url to be one of the leaf's AIA OCSP URIs. Returns the normalized pin, or None.
    """
    leaf_uris = extract_ocsp_aia_uris(pem_data, cert_name)
    if not leaf_uris:
        log_error("❌ OCSP refusing pin: leaf %s has no usable AIA OCSP URI", cert_name)
        return None
    normalized_fetch = _normalize_ocsp_aia_uri(fetch_url)
    if not normalized_fetch:
        log_error("❌ OCSP refusing pin: fetch URL for %s is not a usable OCSP URI (%s)", cert_name, fetch_url)
        return None
    if normalized_fetch not in leaf_uris:
        log_error(
            "❌ OCSP refusing pin: fetch URL %s is not among leaf AIA OCSP URIs for %s (%s)",
            normalized_fetch,
            cert_name,
            ", ".join(leaf_uris),
        )
        return None
    return normalized_fetch


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
        aia_uris = extract_ocsp_aia_uris(pem_data, cert_name)
        if aia_uris:
            meta["ocsp_url"] = aia_uris[0]
            meta["aia_ocsp_uris"] = aia_uris
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

# Wall-clock cap on how long a published GOOD body may be retained/served, even when
# nextUpdate is still in the future. Failed refreshes cannot keep last-good forever.
PREVIOUS_GOOD_MAX_AGE_SECONDS = 24 * 3600

# Declared clock-skew budget. Handshake Lua uses the same value.
# Death time = nextUpdate/max_age_unix minus this skew: stop serving before the CA's
# advertised expiry so a lagging worker clock cannot staple a response the CA already
# considers dead. Stored meta keeps the true absolute time; serve until absolute - skew.
OCSP_CLOCK_SKEW_SECONDS = 300

# Signed-window policy (intrinsic to the OCSP response — not retention / skew death).
# Must match handshake Lua. A CA-stretched GOOD cannot outlive these ceilings.
OCSP_MAX_INTRINSIC_LIFETIME_SECONDS = 7 * 24 * 3600  # nextUpdate − thisUpdate
OCSP_MAX_THIS_UPDATE_AGE_SECONDS = 7 * 24 * 3600  # thisUpdate not older than this vs now

# Verified CertStatus != GOOD. REVOKED tombstones immediately; UNKNOWN waits
# so a single "responder unsure" answer does not drop a usable staple.
_NON_GOOD_TOMBSTONE_AFTER = {"REVOKED": 1, "UNKNOWN": 3}
# Soft recall: after this many same-status sightings, stop stapling (paged=false)
# but keep the DER until the tombstone threshold. First UNKNOWN only halves TTL.
_NON_GOOD_UNPAGE_AFTER = {"UNKNOWN": 2}


class _VerifiedNonGood(Exception):
    """OCSP response verified, but CertStatus is not GOOD. Not a transport failure."""

    def __init__(self, status_name: str, serial: Optional[int], this_update_unix: Optional[int] = None):
        self.status_name = status_name
        self.serial = serial
        self.this_update_unix = this_update_unix
        super().__init__(status_name)


def _ocsp_response_lifetimes(ocsp_response: x509_ocsp.OCSPResponse) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract (remaining_ttl_seconds, total_lifetime_seconds) from a parsed OCSP response.
    Returns (None, None) if the timing fields are unavailable or invalid.
    Does not enforce intrinsic policy — call _ocsp_intrinsic_policy_reason for that.
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


def _ocsp_response_update_unix(
    ocsp_response: x509_ocsp.OCSPResponse,
) -> Tuple[Optional[int], Optional[int]]:
    """Return (this_update_unix, next_update_unix). nextUpdate falls back to thisUpdate+24h."""
    this_update = getattr(ocsp_response, "this_update_utc", None) or ocsp_response.this_update
    if this_update is None:
        return None, None
    if this_update.tzinfo is None:
        this_update = this_update.replace(tzinfo=timezone.utc)
    try:
        this_unix = int(this_update.timestamp())
    except Exception:
        return None, None

    next_update = getattr(ocsp_response, "next_update_utc", None) or ocsp_response.next_update
    if next_update is None:
        next_update = this_update + timedelta(hours=24)
    elif next_update.tzinfo is None:
        next_update = next_update.replace(tzinfo=timezone.utc)
    try:
        next_unix = int(next_update.timestamp())
    except Exception:
        return this_unix, None
    return this_unix, next_unix


def _ocsp_intrinsic_policy_reason(
    ocsp_response: x509_ocsp.OCSPResponse,
    cert_name: str = "",
) -> Optional[str]:
    """
    Enforce signed-window policy on a verified OCSP response.

    Returns a reason code on refusal, or None when acceptable:
      thisUpdate_future, thisUpdate_stale, lifetime_invalid, lifetime_too_long, thisUpdate_unreadable

    This is not skew death time, wall-clock max-age since publish, or the storage TTL clamp.
    Refusals must not be treated as GOOD (do not clear nongood / tombstone counters).
    """
    this_unix, next_unix = _ocsp_response_update_unix(ocsp_response)
    if this_unix is None or next_unix is None:
        log_error("❌ OCSP thisUpdate/nextUpdate unreadable for %s; refusing", cert_name)
        return "thisUpdate_unreadable"

    now_unix = int(datetime.now(timezone.utc).timestamp())
    if this_unix > now_unix + OCSP_CLOCK_SKEW_SECONDS:
        log_error(
            "❌ OCSP thisUpdate is in the future for %s (thisUpdate=%s now=%s skew=%ss); refusing",
            cert_name,
            this_unix,
            now_unix,
            OCSP_CLOCK_SKEW_SECONDS,
        )
        return "thisUpdate_future"
    if this_unix < now_unix - OCSP_MAX_THIS_UPDATE_AGE_SECONDS:
        log_error(
            "❌ OCSP thisUpdate is too old for %s (thisUpdate=%s now=%s max_age=%ss); refusing",
            cert_name,
            this_unix,
            now_unix,
            OCSP_MAX_THIS_UPDATE_AGE_SECONDS,
        )
        return "thisUpdate_stale"

    lifetime = next_unix - this_unix
    if lifetime <= 0:
        log_error("❌ OCSP intrinsic lifetime invalid for %s (nextUpdate <= thisUpdate)", cert_name)
        return "lifetime_invalid"
    if lifetime > OCSP_MAX_INTRINSIC_LIFETIME_SECONDS:
        log_error(
            "❌ OCSP intrinsic lifetime too long for %s (%ss > %ss cap); refusing",
            cert_name,
            lifetime,
            OCSP_MAX_INTRINSIC_LIFETIME_SECONDS,
        )
        return "lifetime_too_long"
    return None


def _ocsp_this_update_unix(ocsp_response: x509_ocsp.OCSPResponse) -> Optional[int]:
    """thisUpdate as unix seconds, used to tell a newer GOOD from the banned body."""
    this_unix, _ = _ocsp_response_update_unix(ocsp_response)
    return this_unix


def _pin_single_certid(
    ocsp_response: x509_ocsp.OCSPResponse,
    leaf: x509.Certificate,
    issuer: x509.Certificate,
    cert_name: str,
) -> Optional[Dict[str, str]]:
    """
    Require exactly one SingleResponse whose CertID matches leaf+issuer.

    Returns a certid pin for ocsp.json, or None to fail closed (multi-response,
    unreadable fields, or CertID mismatch). Libraries that expose "the" serial from
    a multi-response blob must not be allowed to disagree with sha256(DER).
    """
    try:
        singles = list(ocsp_response.responses)
    except Exception as e:
        log_error("❌ OCSP could not enumerate SingleResponse(s) for %s: %s", cert_name, e)
        return None
    if len(singles) != 1:
        log_error(
            "❌ OCSP response for %s has %d SingleResponse(s); refusing to publish (need exactly 1)",
            cert_name,
            len(singles),
        )
        return None
    single = singles[0]
    try:
        hash_alg = single.hash_algorithm
        serial = int(single.serial_number)
        name_hash = bytes(single.issuer_name_hash)
        key_hash = bytes(single.issuer_key_hash)
    except Exception as e:
        log_error("❌ OCSP SingleResponse CertID unreadable for %s: %s", cert_name, e)
        return None
    if serial != int(leaf.serial_number):
        log_error(
            "❌ OCSP CertID serial %s does not match leaf serial %s for %s",
            serial,
            leaf.serial_number,
            cert_name,
        )
        return None
    try:
        expected = x509_ocsp.OCSPRequestBuilder().add_certificate(leaf, issuer, hash_alg).build()
        exp_name = bytes(expected.issuer_name_hash)
        exp_key = bytes(expected.issuer_key_hash)
        exp_serial = int(expected.serial_number)
    except Exception as e:
        log_error("❌ OCSP could not build expected CertID for %s: %s", cert_name, e)
        return None
    if exp_serial != serial or exp_name != name_hash or exp_key != key_hash:
        log_error(
            "❌ OCSP CertID pin mismatch for %s (serial/name_hash/key_hash vs leaf+issuer)",
            cert_name,
        )
        return None
    serial_hex = format(serial, "X").lstrip("0") or "0"
    return {
        "serial": serial_hex,
        "issuer_name_hash": name_hash.hex().lower(),
        "issuer_key_hash": key_hash.hex().lower(),
        "hash_algorithm": getattr(hash_alg, "name", str(hash_alg)).lower(),
    }


def _serial_forms(serial: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    if serial is None:
        return None, None
    try:
        number = int(serial)
    except (TypeError, ValueError):
        return None, None
    if number < 0:
        return None, None
    decimal = str(number)
    serial_hex = format(number, "X").lstrip("0") or "0"
    return decimal, serial_hex


def _ocsp_expiry_meta(ttl: Optional[int]) -> Dict[str, Any]:
    """
    Fields handshake Lua uses to refuse stapling past nextUpdate.

    expires_unix: absolute UTC unix death time (required by handshake / cleanup)
    published_unix / max_age_unix: wall-clock stop independent of nextUpdate
    """
    if not ttl or ttl <= 0:
        return {}
    now = datetime.now(timezone.utc)
    published = int(now.timestamp())
    return {
        "expires_unix": published + int(ttl),
        "published_unix": published,
        "max_age_unix": published + PREVIOUS_GOOD_MAX_AGE_SECONDS,
    }


def _ocsp_signed_timing_meta(ocsp_der: bytes) -> Dict[str, Any]:
    """
    Absolute thisUpdate/nextUpdate from the DER for handshake intrinsic-policy checks.
    Empty dict when unreadable (caller should already have refused publish).
    """
    try:
        resp = x509_ocsp.load_der_ocsp_response(ocsp_der)
        this_unix, next_unix = _ocsp_response_update_unix(resp)
    except Exception:
        return {}
    out: Dict[str, Any] = {}
    if this_unix is not None:
        out["this_update_unix"] = this_unix
    if next_unix is not None:
        out["next_update_unix"] = next_unix
        if this_unix is not None and next_unix > this_unix:
            out["intrinsic_lifetime_seconds"] = next_unix - this_unix
    return out


def _new_job_run_id() -> str:
    """Stable id for one ocsp-refresh invocation (pid + monotonic ns)."""
    return f"{os.getpid()}.{time.time_ns()}"


def _begin_job_run() -> str:
    """Start a new job run id and refresh cached OpenSSL identity."""
    global _JOB_RUN_ID, _OPENSSL_IDENTITY
    _JOB_RUN_ID = _new_job_run_id()
    _OPENSSL_IDENTITY = None
    return _JOB_RUN_ID


def _openssl_identity() -> Dict[str, Any]:
    """
    Identity of OPENSSL_BIN used to verify OCSP responses.
    Cached for the current job run so every ocsp.json agrees.
    """
    global _OPENSSL_IDENTITY
    if _OPENSSL_IDENTITY is not None:
        return dict(_OPENSSL_IDENTITY)

    ident: Dict[str, Any] = {"path": OPENSSL_BIN}
    try:
        bin_path = Path(OPENSSL_BIN)
        if not bin_path.is_file():
            ident["missing"] = True
        else:
            try:
                ident["mtime_ns"] = bin_path.stat().st_mtime_ns
            except Exception:
                pass
            try:
                proc = subprocess.run(
                    [OPENSSL_BIN, "version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                )
                line = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
                if line:
                    ident["version"] = line[0][:256]
            except Exception as e:
                ident["version_error"] = str(e)[:128]
    except Exception as e:
        ident["error"] = str(e)[:128]

    _OPENSSL_IDENTITY = ident
    return dict(ident)


def _provenance_meta() -> Dict[str, Any]:
    """
    Forensic fields for ocsp.json: which job run published, and which OpenSSL verified.
    Handshake Lua does not require these; they exist for on-call correlation.
    """
    run_id = _JOB_RUN_ID or _new_job_run_id()
    openssl = _openssl_identity()
    out: Dict[str, Any] = {"job_run_id": run_id}
    if openssl.get("version"):
        out["openssl_version"] = str(openssl["version"])
    if openssl.get("path"):
        out["openssl_path"] = str(openssl["path"])
    mtime_ns = openssl.get("mtime_ns")
    if isinstance(mtime_ns, int) and mtime_ns > 0:
        out["openssl_mtime_ns"] = mtime_ns
    return out


def _preserve_provenance(dst: Dict[str, Any], src: Optional[Dict[str, Any]]) -> None:
    """Keep prior GOOD provenance when rewriting ocsp.json for backoff/markers."""
    if not isinstance(src, dict):
        return
    for key in ("job_run_id", "openssl_version", "openssl_path", "openssl_mtime_ns"):
        val = src.get(key)
        if val is None or val == "":
            continue
        dst[key] = val


def _meta_int_unix(meta: Dict[str, Any], key: str) -> Optional[int]:
    raw = meta.get(key)
    if isinstance(raw, (int, float)) and int(raw) > 0:
        return int(raw)
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _seconds_until_death(absolute_unix: int, now_unix: Optional[int] = None) -> int:
    """
    Seconds until death time (absolute_unix - OCSP_CLOCK_SKEW_SECONDS).
    <= 0 means the staple must not be served (past nextUpdate/max_age minus skew).
    """
    now = int(now_unix if now_unix is not None else datetime.now(timezone.utc).timestamp())
    return int(absolute_unix) - OCSP_CLOCK_SKEW_SECONDS - now


def _wall_clock_remaining(meta: Optional[Dict[str, Any]], now_unix: Optional[int] = None) -> Optional[int]:
    """
    Remaining seconds until wall-clock death (max_age_unix - skew).
    None when meta has no publish age (pre-upgrade); caller keeps nextUpdate-only behavior.
    """
    if not isinstance(meta, dict):
        return None
    now = int(now_unix if now_unix is not None else datetime.now(timezone.utc).timestamp())
    max_age = _meta_int_unix(meta, "max_age_unix")
    if max_age is None:
        published = _meta_int_unix(meta, "published_unix")
        if published is None:
            return None
        max_age = published + PREVIOUS_GOOD_MAX_AGE_SECONDS
    return max(0, _seconds_until_death(max_age, now))


def _atomic_write_bytes(path: Path, data: bytes, mode: int = 0o640) -> None:
    """Write bytes via tempfile + replace so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as tmp_file:
            # Record path before write so a mid-write failure still cleans up the tmp.
            tmp_path = Path(tmp_file.name)
            tmp_file.write(data)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        tmp_path.chmod(mode)
        tmp_path.replace(path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except TypeError:
                # Python < 3.8 compatibility (should not apply, but keep safe).
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
            except Exception:
                pass


def _atomic_write_text(path: Path, text: str, mode: int = 0o640) -> None:
    """Atomic text write (UTF-8)."""
    _atomic_write_bytes(path, text.encode("utf-8"), mode=mode)


# Sidecars that must survive a shard directory swap (not rewritten by a GOOD publish).
_OCSP_SHARD_SIDECARS = frozenset({"nongood.json", "serial-blacklist.json"})


def _write_bytes_inplace(path: Path, data: bytes, mode: int = 0o640) -> None:
    """Write bytes into a staging tree (no rename). Caller publishes the directory."""
    with open(path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    path.chmod(mode)


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync so renames persist across power loss."""
    try:
        fd = os.open(str(path), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        pass


def _copy_ocsp_shard_sidecars(live_dir: Path, staging_dir: Path) -> None:
    """Carry quarantine/blacklist markers into a new shard tree before rename."""
    if not live_dir.is_dir():
        return
    for name in _OCSP_SHARD_SIDECARS:
        src = live_dir / name
        if not src.is_file():
            continue
        try:
            shutil.copy2(src, staging_dir / name)
        except Exception as e:
            log_debug("⚠️ OCSP could not copy sidecar %s into staging: %s", name, e)


def _canary_ocsp_handshake(
    *,
    leaf_pem: bytes,
    issuer_pem: bytes,
    ocsp_der: bytes,
    meta: Dict[str, Any],
    cert_name: str = "",
) -> Tuple[bool, str]:
    """
    Scheduler canary before paging a staged shard live.

    Re-runs the handshake acceptance path against the staged trio (openssl
    verify, issuer SPKI pin, single CertID, CertStatus=GOOD, intrinsic timing,
    der_sha256 / CertID / AIA meta ligands). Does not touch the live shard or
    bump ``.ocsp_epoch``. Private key is not required; this is the same crypto
    gate ``ssl_certificate`` uses before ``set_ocsp_status_resp``.
    """
    label = cert_name or "canary"
    if not leaf_pem or not issuer_pem or not ocsp_der:
        return False, "canary_missing_inputs"
    if not isinstance(meta, dict):
        return False, "canary_meta_invalid"

    expected_der = meta.get("der_sha256")
    if not isinstance(expected_der, str) or len(expected_der) != 64:
        return False, "canary_der_sha256_missing"
    if hashlib.sha256(ocsp_der).hexdigest().lower() != expected_der.lower():
        return False, "canary_der_sha256_mismatch"

    try:
        leaf = x509.load_pem_x509_certificate(leaf_pem)
        issuer = x509.load_pem_x509_certificate(issuer_pem)
        ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_der)
    except Exception as e:
        log_error("❌ OCSP canary parse failed for %s: %s", label, e)
        return False, "canary_parse_failed"

    if ocsp_response.response_status != x509_ocsp.OCSPResponseStatus.SUCCESSFUL:
        return False, "canary_response_status"

    if not Path(OPENSSL_BIN).is_file():
        log_error("❌ OCSP canary requires openssl at %s", OPENSSL_BIN)
        return False, "canary_openssl_missing"

    try:
        with tempfile.NamedTemporaryFile(suffix=".der", delete=True) as f_der, tempfile.NamedTemporaryFile(
            suffix=".pem", mode="w", delete=True
        ) as f_issuer, tempfile.NamedTemporaryFile(suffix=".pem", mode="w", delete=True) as f_leaf:
            os.chmod(f_der.name, 0o600)
            os.chmod(f_issuer.name, 0o600)
            os.chmod(f_leaf.name, 0o600)
            f_der.write(ocsp_der)
            f_der.flush()
            f_issuer.write(
                issuer_pem.decode("utf-8")
                if isinstance(issuer_pem, (bytes, bytearray))
                else str(issuer_pem)
            )
            f_issuer.flush()
            # Prefer the leaf PEM the job will staple against (fullchain first block ok).
            if isinstance(leaf_pem, (bytes, bytearray)):
                leaf_text = leaf_pem.decode("utf-8", errors="ignore")
            else:
                leaf_text = str(leaf_pem)
            if "BEGIN CERTIFICATE" not in leaf_text:
                leaf_text = leaf.public_bytes(Encoding.PEM).decode("utf-8")
            f_leaf.write(leaf_text)
            f_leaf.flush()
            cmd = [
                OPENSSL_BIN,
                "ocsp",
                "-respin",
                f_der.name,
                "-issuer",
                f_issuer.name,
                "-cert",
                f_leaf.name,
                "-CAfile",
                f_issuer.name,
                "-partial_chain",
            ]
            try:
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            except subprocess.TimeoutExpired:
                return False, "canary_openssl_timeout"
            if p.returncode != 0:
                log_error(
                    "❌ OCSP canary openssl verify failed for %s: %s",
                    label,
                    (p.stderr or p.stdout or "").strip(),
                )
                return False, "canary_openssl_verify"
    except Exception as e:
        log_error("❌ OCSP canary openssl exception for %s: %s", label, e)
        return False, "canary_openssl_exception"

    if not _ocsp_signer_ends_on_issuer_spki(ocsp_der, issuer):
        return False, "canary_signer_spki"

    certid_pin = _pin_single_certid(ocsp_response, leaf, issuer, label)
    if not certid_pin:
        return False, "canary_certid"
    meta_certid = meta.get("certid")
    if not isinstance(meta_certid, dict):
        return False, "canary_certid_meta_missing"
    for key in ("serial", "issuer_name_hash", "issuer_key_hash"):
        if str(meta_certid.get(key) or "").lower() != str(certid_pin.get(key) or "").lower():
            return False, "canary_certid_mismatch"

    try:
        cert_status = ocsp_response.certificate_status
    except (ValueError, AttributeError):
        return False, "canary_cert_status_unreadable"
    if cert_status != x509_ocsp.OCSPCertStatus.GOOD:
        return False, "canary_cert_status_not_good"

    policy_reason = _ocsp_intrinsic_policy_reason(ocsp_response, label)
    if policy_reason:
        return False, f"canary_{policy_reason}"

    aia_pin = meta.get("aia_ocsp_uri") or meta.get("ocsp_url")
    if not isinstance(aia_pin, str) or not aia_pin.strip():
        return False, "canary_aia_unpinned"
    try:
        if not _pin_aia_ocsp_uri(leaf_pem, aia_pin, label):
            return False, "canary_aia_mismatch"
    except Exception:
        return False, "canary_aia_check_failed"

    return True, "ok"


def _publish_ocsp_shard(
    fingerprint: str,
    *,
    issuer_pem: bytes,
    ocsp_der: bytes,
    meta: Dict[str, Any],
    leaf_pem: Optional[bytes] = None,
    cert_name: str = "",
    db: Optional[Any] = None,
) -> Path:
    """
    Page issuer.pem + ocsp.der + ocsp.json as one directory rename — only after
    a scheduler canary handshake against the staged trio succeeds.

    Stage under ``.{fp}.pub-*``. Canary runs while the previous live shard (if
    any) is still in place. On canary failure the stage is discarded and live
    is untouched. On success, stamp ``paged`` / ``paged_unix``, move live aside
    to ``.{fp}.old-*``, then rename the stage into place. Readers see either the
    previous complete shard or the new paged shard — never a mix of old DER and
    new JSON. Sidecars are carried into the new tree. On rename failure the
    previous live directory is restored.
    """
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        raise ValueError("empty fingerprint")
    if not issuer_pem or not ocsp_der:
        raise ValueError("issuer_pem and ocsp_der are required")
    if not leaf_pem:
        raise ValueError("leaf_pem is required for canary-before-page")

    final_dir = _resolved_sharded_ocsp_path(normalized)
    parent = final_dir.parent
    parent.mkdir(parents=True, exist_ok=True)

    token = f"{os.getpid()}.{time.time_ns()}"
    staging = parent / f".{final_dir.name}.pub-{token}"
    stale = parent / f".{final_dir.name}.old-{token}"

    staging_created = False
    live_moved_aside = False
    published = False
    page_meta = dict(meta) if isinstance(meta, dict) else {}

    try:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)

        staging.mkdir(mode=0o750)
        staging_created = True

        _copy_ocsp_shard_sidecars(final_dir, staging)
        _write_bytes_inplace(staging / "issuer.pem", issuer_pem)
        _write_bytes_inplace(staging / "ocsp.der", ocsp_der)
        # Unpaged marker while canary runs (never exposed as the live tree).
        page_meta["paged"] = False
        _write_bytes_inplace(
            staging / "ocsp.json",
            json.dumps(page_meta, separators=(",", ":")).encode("utf-8"),
        )
        _fsync_directory(staging)

        canary_ok, canary_reason = _canary_ocsp_handshake(
            leaf_pem=leaf_pem,
            issuer_pem=issuer_pem,
            ocsp_der=ocsp_der,
            meta=page_meta,
            cert_name=cert_name or normalized[:16],
        )
        if not canary_ok:
            log_error(
                "❌ staple_decision=canary_refused tag=OCSP_CANARY detail=%s fp=%s... cert=%s — live shard unchanged",
                canary_reason,
                normalized[:16],
                cert_name or normalized[:16],
            )
            raise RuntimeError(f"canary refused page: {canary_reason}")

        page_meta["paged"] = True
        page_meta["paged_unix"] = int(datetime.now(timezone.utc).timestamp())
        page_meta["canary_reason"] = canary_reason
        page_meta.pop("unpaged_after_nongood", None)
        _write_bytes_inplace(
            staging / "ocsp.json",
            json.dumps(page_meta, separators=(",", ":")).encode("utf-8"),
        )
        _fsync_directory(staging)

        # Page: swap staged (canary-ok) tree into the live path.
        if final_dir.exists() or final_dir.is_symlink():
            final_dir.rename(stale)
            live_moved_aside = True
        staging.rename(final_dir)
        published = True
        staging_created = False

        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)
        _fsync_directory(parent)

        # Keep caller meta in sync with what was paged (floor / DB use published_unix).
        if isinstance(meta, dict):
            meta.clear()
            meta.update(page_meta)

        log_info(
            "✓ staple_decision=ok tag=OCSP_CANARY_PAGED fp=%s... paged_unix=%s cert=%s",
            normalized[:16],
            page_meta.get("paged_unix"),
            cert_name or normalized[:16],
        )

        # Peer-refuse clear is deferred to the persist batch (bump epoch first, then
        # unlock). Clearing here would open the bus while L1 still trusts the old epoch.

        # DB issuer mirror after the live tree is visible (der/json batched elsewhere).
        if db is not None:
            try:
                db.upsert_job_cache(
                    service_id=None,
                    file_name=_ocsp_cache_relpath(normalized, "issuer.pem"),
                    data=issuer_pem,
                    job_name="ocsp-refresh",
                    checksum=hashlib.sha256(issuer_pem).hexdigest().lower(),
                )
            except Exception as e:
                log_debug("⚠️ OCSP could not store issuer certificate for %s: %s", normalized[:16], e)

        return final_dir
    except Exception:
        if not published:
            if live_moved_aside and stale.exists() and not final_dir.exists():
                try:
                    stale.rename(final_dir)
                except Exception as restore_err:
                    log_error(
                        "❌ OCSP failed to restore shard after publish error (fp=%s): %s",
                        normalized[:16],
                        restore_err,
                    )
            if staging_created and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        raise


def _normalize_ocsp_serial(serial: Any) -> Optional[str]:
    """Canonical lowercase hex serial (no 0x prefix) for backoff identity matching."""
    if serial is None:
        return None
    if isinstance(serial, int):
        return format(serial, "x")
    s = str(serial).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if not s or not re.fullmatch(r"[0-9a-f]+", s):
        return None
    # Drop leading zeros so decimal/hex formatting skew cannot split identity.
    return s.lstrip("0") or "0"


def _write_ocsp_http_error_backoff(
    cert_fp: Optional[str],
    ocsp_url: str,
    http_code: int,
    reason: str,
    serial: Optional[Any] = None,
    backoff_seconds: int = HTTP_ERROR_BACKOFF_SECONDS,
) -> None:
    """
    Persist an HTTP error backoff marker into ocsp.json so we can avoid
    re-fetching for a short duration.

    Identity is (SPKI fingerprint, leaf serial, ocsp_url): same-key renews and
    unrelated responders must not inherit another CertID's freeze.
    """
    if not cert_fp:
        return

    lock_fd = _acquire_cert_lock(cert_fp)
    if lock_fd is None:
        log_debug("⚠️ OCSP could not lock for http_error backoff metadata (fp=%s)", cert_fp[:16] + "...")
        return

    try:
        ocsp_cert_dir = _get_sharded_ocsp_path(cert_fp)
        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
        meta_path = ocsp_cert_dir / "ocsp.json"

        now = datetime.now(timezone.utc)
        retry_after = now + timedelta(seconds=backoff_seconds)
        serial_norm = _normalize_ocsp_serial(serial)

        meta = {
            "fingerprint": cert_fp,
            "ocsp_url": ocsp_url,
            "http_error": {"code": http_code, "reason": reason or ""},
            "retry_after": retry_after.isoformat(),
            "error_type": "http_backoff",
        }
        if serial_norm:
            meta["serial"] = serial_norm
        # Preserve success-cache fields. Never put retry_after into expires_unix —
        # TTL cleanup treats that as OCSP response lifetime and would delete a still-valid ocsp.der.
        try:
            if meta_path.is_file():
                old = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    old_sha = old.get("der_sha256")
                    if isinstance(old_sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", old_sha):
                        meta["der_sha256"] = old_sha.lower()
                    # Keep OCSP death clocks across repeated backoffs. Do not require
                    # old.error_type != http_backoff — a second 5xx would otherwise
                    # strip expires_unix and fail-closed freshness on the live DER.
                    old_exp_unix = old.get("expires_unix")
                    if isinstance(old_exp_unix, (int, float)) and int(old_exp_unix) > 0:
                        meta["expires_unix"] = int(old_exp_unix)
                    elif isinstance(old_exp_unix, str) and old_exp_unix.isdigit():
                        meta["expires_unix"] = int(old_exp_unix)
                    for age_key in ("published_unix", "max_age_unix"):
                        old_age = old.get(age_key)
                        if isinstance(old_age, (int, float)) and int(old_age) > 0:
                            meta[age_key] = int(old_age)
                        elif isinstance(old_age, str) and old_age.isdigit():
                            meta[age_key] = int(old_age)
                    # Keep prior GOOD verifier identity; backoff is not a new openssl publish.
                    _preserve_provenance(meta, old)
                    # Keep canary / pin fields so a fetch blip does not demote a live GOOD shard
                    # (missing paged → not_paged; missing AIA/CertID pins fail Must-Staple).
                    for keep_key in (
                        "paged",
                        "paged_unix",
                        "canary_reason",
                        "certid",
                        "aia_ocsp_uri",
                        "aia_ocsp_uris",
                        "this_update_unix",
                        "next_update_unix",
                        "must_staple",
                        "cert_status",
                        "fingerprint",
                        "serial",
                        "unpaged_after_nongood",
                    ):
                        if keep_key not in meta and keep_key in old:
                            meta[keep_key] = old[keep_key]
        except Exception:
            pass

        _atomic_write_text(meta_path, json.dumps(meta, separators=(",", ":")))
    except Exception as e:
        log_debug("⚠️ OCSP could not write http_error backoff metadata: %s", e)
    finally:
        _release_cert_lock(lock_fd, cert_fp)


def _get_http_error_backoff_remaining(
    cert_fp: Optional[str],
    serial: Optional[Any] = None,
    ocsp_url: Optional[str] = None,
) -> int:
    """
    Return remaining seconds for an http_error backoff stored in ocsp.json.
    Returns 0 if no backoff marker exists, it is expired/invalid, or it was
    written for a different leaf serial / OCSP URL (shared SPKI must not freeze
    unrelated CertIDs).
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

        # Bind to CertID + responder. Legacy SPKI-only markers (no serial) are ignored
        # so a prior shared-key freeze cannot keep blocking after this fix.
        want_serial = _normalize_ocsp_serial(serial)
        have_serial = _normalize_ocsp_serial(meta.get("serial"))
        if not want_serial or not have_serial or want_serial != have_serial:
            return 0

        have_url = meta.get("ocsp_url")
        if ocsp_url and isinstance(have_url, str) and have_url.strip() and have_url.strip() != ocsp_url.strip():
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


def _write_issuer_pem(
    fingerprint: Optional[str],
    issuer_pem: bytes,
    db: Optional[Any] = None,
    already_locked: bool = False,
) -> bool:
    """Persist the issuer certificate used to verify an OCSP response.

    Returns True on successful disk write. False means the caller must not publish
    ocsp.der for this fingerprint (handshake validate needs issuer.pem).

    When already_locked is False, acquires the per-fingerprint cert lock so issuer.pem
    is not swapped while a concurrent publisher is writing ocsp.der / ocsp.json.
    """
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized or not issuer_pem:
        return False

    lock_fd: Optional[OcspLock] = None
    if not already_locked:
        lock_fd = _acquire_cert_lock(normalized)
        if lock_fd is None:
            log_debug("⚠️ OCSP could not lock for issuer.pem write (fp=%s)", normalized[:16] + "...")
            return False

    try:
        try:
            ocsp_dir = _get_sharded_ocsp_path(normalized)
            ocsp_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(ocsp_dir / "issuer.pem", issuer_pem)
        except Exception as e:
            log_debug("⚠️ OCSP could not write issuer.pem for %s: %s", normalized[:16], e)
            return False

        if db is None:
            return True
        try:
            db.upsert_job_cache(
                service_id=None,
                file_name=_ocsp_cache_relpath(normalized, "issuer.pem"),
                data=issuer_pem,
                job_name="ocsp-refresh",
                checksum=hashlib.sha256(issuer_pem).hexdigest().lower(),
            )
        except Exception as e:
            log_debug("⚠️ OCSP could not store issuer certificate for %s: %s", normalized[:16], e)
            # Disk issuer is present; DB mirror failure must not block handshake publish.
        return True
    finally:
        if lock_fd is not None:
            _release_cert_lock(lock_fd, normalized)


def _ensure_issuer_pem(pem_data: bytes, fingerprint: Optional[str], cert_name: str = "", db: Optional[Any] = None) -> None:
    """Write issuer.pem when a cached OCSP response has none yet."""
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized or not pem_data:
        return
    issuer_path = _get_sharded_ocsp_path(normalized) / "issuer.pem"
    if issuer_path.is_file() and issuer_path.stat().st_size > 0:
        return
    try:
        _leaf, issuer = _parse_chain(pem_data, cert_name)
    except Exception as e:
        log_debug("⚠️ OCSP could not resolve issuer certificate for %s: %s", cert_name, e)
        return
    _write_issuer_pem(normalized, issuer.public_bytes(Encoding.PEM), db)


def fetch_ocsp_response(pem_data: bytes, ocsp_url: str, cert_name: str = "", timeout: int = 10) -> Tuple[Optional[bytes], int, Optional[bytes]]:
    """
    Fetch OCSP response using cryptography + urllib.
    Returns (raw DER bytes or None, ttl_seconds, issuer PEM or None).

    Only returns DER when responseStatus is SUCCESSFUL, the signature verifies,
    CertStatus is good, and the response serial matches the leaf. A verified
    revoked/unknown response raises _VerifiedNonGood so the caller can tombstone
    the previous GOOD staple. Transport and signature failures return None.
    """
    try:
        leaf, issuer = _parse_chain(pem_data, cert_name)
    except Exception as e:
        log_error("❌ OCSP failed to parse chain for %s: %s", cert_name, e)
        return None, 0, None

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
                    return None, 0, None

                default_port = 443 if scheme == "https" else 80
                ocsp_hostname, ips = _get_ocsp_responder_ips(ocsp_url, default_port=default_port)
                if not ocsp_hostname or not ips:
                    log_error("❌ OCSP could not resolve safe IPs for responder %s (host=%s)", cert_name, ocsp_hostname)
                    return None, 0, None

                # Fetch by connecting to each resolved IP, while keeping TLS SNI for `ocsp_hostname`.
                # If every cached IP fails, invalidate DNS and re-resolve once (CDN/anycast cutover).
                ocsp_der = None
                for dns_attempt in range(2):
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
                                serial=leaf.serial_number,
                            )

                    if ocsp_der:
                        break
                    if dns_attempt == 0:
                        log_debug(
                            "🔄 OCSP all cached IPs failed for %s; re-resolving %s",
                            cert_name,
                            ocsp_hostname,
                        )
                        _invalidate_ocsp_responder_dns(ocsp_hostname)
                        ocsp_hostname, ips = _get_ocsp_responder_ips(ocsp_url, default_port=default_port)
                        if not ips:
                            break

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
                        serial=leaf.serial_number,
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
            return None, 0, None

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
                return None, 0, None

            try:
                # Add a timeout so a stuck openssl process cannot hang the whole job
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            except subprocess.TimeoutExpired as e:
                log_error(
                    "❌ OCSP response cryptographic signature verification timed out for %s after %s seconds. Discarding response.",
                    cert_name,
                    e.timeout,
                )
                return None, 0, None
            if p.returncode != 0:
                log_error("❌ OCSP response cryptographic signature verification failed for %s. Discarding forged/invalid response. OpenSSL Error: %s", cert_name, p.stderr.strip() or p.stdout.strip())
                return None, 0, None

        if not _ocsp_signer_ends_on_issuer_spki(ocsp_der, issuer):
            log_error(
                "❌ OCSP signer chain does not end on issuer SPKI for %s; refusing to publish.",
                cert_name,
            )
            return None, 0, None

        # Exactly one SingleResponse whose CertID names this leaf+issuer (pin for ocsp.json).
        certid_pin = _pin_single_certid(ocsp_response, leaf, issuer, cert_name)
        if not certid_pin:
            return None, 0, None

        # responseStatus=SUCCESSFUL ≠ CertStatus=good (RFC 6960). Only publish staples
        # that attest the leaf is good; revoked/unknown must not replace a usable cache.
        try:
            cert_status = ocsp_response.certificate_status
        except (ValueError, AttributeError) as e:
            log_error(
                "❌ OCSP response for %s has no usable CertStatus after SUCCESSFUL outer status: %s. Discarding.",
                cert_name,
                e,
            )
            return None, 0, None
        if cert_status != x509_ocsp.OCSPCertStatus.GOOD:
            status_name = getattr(cert_status, "name", None) or str(cert_status)
            log_error(
                "❌ OCSP CertStatus=%s for %s (serial=%s); refusing to publish non-good staple.",
                status_name,
                cert_name,
                leaf.serial_number,
            )
            raise _VerifiedNonGood(status_name, leaf.serial_number, _ocsp_this_update_unix(ocsp_response))
        try:
            resp_serial = ocsp_response.serial_number
        except (ValueError, AttributeError):
            resp_serial = None
        if resp_serial is not None and resp_serial != leaf.serial_number:
            log_error(
                "❌ OCSP response serial %s does not match leaf serial %s for %s. Discarding.",
                resp_serial,
                leaf.serial_number,
                cert_name,
            )
            return None, 0, None

        # Signed-window policy: refuse stretched / future / ancient thisUpdate.
        # Discard only — not a GOOD and not a CertStatus non-GOOD for tombstone counters.
        policy_reason = _ocsp_intrinsic_policy_reason(ocsp_response, cert_name)
        if policy_reason:
            return None, 0, None

        # Extract TTL (storage clamp; intrinsic policy already enforced above).
        remaining, _ = _ocsp_response_lifetimes(ocsp_response)
        if remaining is not None:
            ttl = min(remaining, OCSP_MAX_INTRINSIC_LIFETIME_SECONDS)
        else:
            ttl = 86400  # RFC standard fallback

        # Delay after successful fetch to prevent rate limiting
        log_debug("⏸️ OCSP delaying 2 seconds after fetch for %s to prevent rate limiting", cert_name)
        time.sleep(2)

        return ocsp_der, ttl, issuer.public_bytes(Encoding.PEM)
    except _VerifiedNonGood:
        raise
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
        # doesn't immediately retry the same failing CertID/responder.
        if e.code in (400, 500):
            cert_fp = _get_cert_pubkey_fingerprint(pem_data)
            serial = None
            try:
                serial = x509.load_pem_x509_certificate(pem_data).serial_number
            except Exception:
                pass
            _write_ocsp_http_error_backoff(
                cert_fp=cert_fp,
                ocsp_url=ocsp_url,
                http_code=e.code,
                reason=e.reason or "",
                serial=serial,
            )

        return None, 0, None
    except URLError as e:
        # Network error — DNS, connection refused, timeout, SSL error, etc.
        log_error("❌ OCSP network error fetching response for %s from %s: %s", cert_name, ocsp_url, e)
        return None, 0, None
    except Exception as e:
        log_error("❌ OCSP failed to fetch response for %s: %s", cert_name, e)
        return None, 0, None


def get_cached_ocsp_ttl(cert_name: str, cert_pem: Optional[bytes] = None, fingerprint: Optional[str] = None) -> Tuple[Optional[int], Optional[int]]:
    """
    Check if cached OCSP DER file exists (using fingerprint-based sharded path) and return:
      - remaining TTL in seconds (until Next Update)
      - total lifetime in seconds (Next Update - This Update)
    Both values are None if they cannot be determined.

    When ``cert_pem`` is provided, the cached response's CertID serial must match the
    current leaf. Shards are SPKI-keyed, so a same-key renew (or two names sharing a
    key) can leave a still-fresh DER for a different serial — callers that skip fetch
    on TTL must treat that as a miss.

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

        # SPKI shard ≠ CertID: same-key renew / shared-key sites must not TTL-skip.
        if cert_pem is not None:
            leaf_serial = None
            try:
                leaf = x509.load_pem_x509_certificate(_clean_pem(cert_pem))
                leaf_serial = int(leaf.serial_number)
            except Exception:
                try:
                    leaf = x509.load_der_x509_certificate(cert_pem)
                    leaf_serial = int(leaf.serial_number)
                except Exception:
                    leaf_serial = None
            if leaf_serial is not None:
                try:
                    resp_serial = int(ocsp_response.serial_number)
                except (ValueError, AttributeError, TypeError):
                    log_info(
                        "⚡ OCSP cached response for %s: fp=%s CertID serial unreadable/ambiguous; "
                        "treating as miss so refresh can refetch",
                        cert_name,
                        (fingerprint[:16] + "...") if fingerprint else "unknown",
                    )
                    return None, None
                if resp_serial != leaf_serial:
                    log_info(
                        "⚡ OCSP cached response for %s: fp=%s CertID serial mismatch "
                        "(cached=%s leaf=%s); treating as miss so refresh can refetch",
                        cert_name,
                        (fingerprint[:16] + "...") if fingerprint else "unknown",
                        resp_serial,
                        leaf_serial,
                    )
                    return None, None

        remaining, total_lifetime = _ocsp_response_lifetimes(ocsp_response)
        if remaining is None or total_lifetime is None:
            log_debug("🔄 OCSP could not determine precise lifetime for %s from cached response", cert_name)
            return None, None

        # Type assertion: after None checks above, these are guaranteed to be int
        assert remaining is not None
        assert total_lifetime is not None

        # Death time = nextUpdate - skew (meta stays exact).
        remaining = max(0, remaining - OCSP_CLOCK_SKEW_SECONDS)

        # Wall-clock max-age can expire a previous-good body before nextUpdate.
        meta_path = _get_sharded_ocsp_path(fingerprint) / "ocsp.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = None
            wall_remaining = _wall_clock_remaining(meta if isinstance(meta, dict) else None)
            if wall_remaining is not None and wall_remaining < remaining:
                log_info(
                    "⚡ OCSP cached response for %s: fp=%s wall-clock death remaining=%ds "
                    "(nextUpdate-skew remaining=%ds); using the shorter window",
                    cert_name,
                    (fingerprint[:16] + "...") if fingerprint else "unknown",
                    wall_remaining,
                    remaining,
                )
                remaining = wall_remaining

        log_info(
            "⚡ OCSP cached response for %s: fp=%s remaining=%ds (%.1f days, death=nextUpdate-%ds), "
            "total_lifetime=%ds (%.1f days)",
            cert_name,
            (fingerprint[:16] + "...") if fingerprint else "unknown",
            remaining,
            remaining / 86400.0,
            OCSP_CLOCK_SKEW_SECONDS,
            total_lifetime,
            total_lifetime / 86400.0,
        )
        return remaining, total_lifetime
    except Exception as e:
        log_warning("⚠️ OCSP exception while reading cached TTL for %s: %s", cert_name, e)
        return None, None


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
            if not file_name.startswith(OCSP_MARKER_PREFIX):
                continue
            cert_name_raw = file_name[len(OCSP_MARKER_PREFIX) :]
            if cert_name_raw and re.match(r"^[A-Za-z0-9_.*-]+$", cert_name_raw):
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


def _load_selfsigned_certs_from_db(db: Any) -> Dict[str, bytes]:
    """Load self-signed certificate PEM data stored by the self-signed job."""
    result: Dict[str, bytes] = {}
    try:
        cache_files = db.get_jobs_cache_files(job_name="self-signed", with_data=True)
    except Exception as e:
        log_error("❌ OCSP failed to query database for self-signed certificates: %s", e)
        return result

    if not cache_files:
        log_debug("ℹ️ OCSP no self-signed cache entries found in database")
        return result

    for entry in cache_files:
        try:
            file_name = entry.get("file_name", "")
            service_id = entry.get("service_id", "")
            if file_name != "cert.pem" or not service_id:
                continue
            if not re.match(r"^[A-Za-z0-9_.*-]+$", service_id):
                log_warning("⚠️ OCSP sanitization: skipping self-signed cert with invalid service_id: %s", service_id)
                continue
            data = entry.get("data")
            if not data or b"-----BEGIN" not in data:
                continue
            result[f"selfsigned-{service_id}"] = data
            log_debug("✓ OCSP loaded self-signed cert for %s from database", service_id)
        except Exception as e:
            log_warning("⚠️ OCSP failed to process self-signed cert entry %s: %s", entry.get("file_name", "?"), e)

    return result


def restore_ocsp_from_database(db: Optional[Any] = None) -> None:
    """
    Restore cached OCSP responses from database to disk.
    Called at startup to ensure disk cache is populated from database.
    This handles ephemeral storage (tmpfs, etc.) by restoring files on each run.

    Never overwrites a newer on-disk SPKI shard with an older complete DB trio
    (checksum mismatch alone is not a freshness signal).
    """
    if not db:
        log_debug("ℹ️ OCSP database not available, skipping cache restoration")
        return

    log_info("🔄 OCSP syncing cached responses from database to disk...")
    try:
        restored_count = 0
        replaced_count = 0
        ok_count = 0
        skipped_newer = 0

        # Get all OCSP cache entries from database for this job
        cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        try:
            ocsp_skip = ocsp_restore_skip_fingerprints(list(cache_files or []), CONFIGS_SSL_BASE)
        except Exception as e:
            log_debug("⚠️ OCSP restore fence unavailable: %s", e)
            ocsp_skip = {}

        for entry in cache_files:
            file_name = entry.get("file_name", "")
            if not entry.get("data"):
                continue
            # Cluster floor rows: max-only merge before shard leaves.
            if parse_ocsp_floor_cache_name(file_name):
                try:
                    if _restore_ocsp_cluster_floor_entry(file_name, entry["data"]):
                        restored_count += 1
                except Exception as e:
                    log_debug("⚠️ OCSP could not restore cluster floor %s: %s", file_name, e)
                continue
            issuer_fp = _fingerprint_from_issuer_name(file_name)
            if issuer_fp:
                if issuer_fp in ocsp_skip:
                    skipped_newer += 1
                    log_info(
                        "⏭️ OCSP restore skip issuer.pem fp=%s... reason=%s",
                        issuer_fp[:16],
                        ocsp_skip[issuer_fp],
                    )
                    continue
                try:
                    issuer_path = _resolved_sharded_ocsp_path(issuer_fp) / "issuer.pem"
                    if not issuer_path.is_file() or hashlib.sha256(issuer_path.read_bytes()).hexdigest().lower() != hashlib.sha256(entry["data"]).hexdigest().lower():
                        issuer_path.write_bytes(entry["data"])
                        issuer_path.chmod(0o640)
                        log_debug("✓ OCSP restored issuer certificate for %s", issuer_fp[:16])
                except Exception as e:
                    log_debug("⚠️ OCSP could not restore issuer certificate for %s: %s", file_name, e)
                continue
            meta_fp = _fingerprint_from_meta_name(file_name)
            if meta_fp:
                if meta_fp in ocsp_skip:
                    skipped_newer += 1
                    log_info(
                        "⏭️ OCSP restore skip ocsp.json fp=%s... reason=%s",
                        meta_fp[:16],
                        ocsp_skip[meta_fp],
                    )
                    continue
                try:
                    meta_path = _resolved_sharded_ocsp_path(meta_fp) / "ocsp.json"
                    if not meta_path.is_file() or hashlib.sha256(meta_path.read_bytes()).hexdigest().lower() != hashlib.sha256(entry["data"]).hexdigest().lower():
                        meta_path.write_bytes(entry["data"])
                        meta_path.chmod(0o640)
                        log_debug("✓ OCSP restored metadata for %s", meta_fp[:16])
                except Exception as e:
                    log_debug("⚠️ OCSP could not restore metadata for %s: %s", file_name, e)
                continue
            # Marker entries live under ocsp-marker/<cert_name>.
            # Response entries are {hex1}/{hex2}/{fingerprint}/ocsp.der.
            fingerprint = _fingerprint_from_ocsp_der_name(file_name)
            if not fingerprint:
                continue

            db_data = entry["data"]
            db_checksum = (entry.get("checksum") or hashlib.sha256(db_data).hexdigest()).lower()
            if _serial_blacklist_blocks(fingerprint, db_data, fingerprint[:16]):
                log_warning("🧹 OCSP skipping database sync of blacklisted serial for %s", fingerprint[:16])
                continue

            try:
                ocsp_cert_dir = _resolved_sharded_ocsp_path(fingerprint)
                ocsp_path = ocsp_cert_dir / "ocsp.der"

                if ocsp_path.is_file():
                    # File exists — compare checksum
                    disk_checksum = hashlib.sha256(ocsp_path.read_bytes()).hexdigest().lower()
                    if disk_checksum == db_checksum:
                        ok_count += 1
                        log_debug("✓ OCSP disk file for %s matches database (checksum=%s)", fingerprint, db_checksum[:8])
                    elif fingerprint in ocsp_skip:
                        skipped_newer += 1
                        log_info(
                            "⏭️ OCSP restore skip ocsp.der fp=%s... (disk newer than DB) reason=%s",
                            fingerprint[:16],
                            ocsp_skip[fingerprint],
                        )
                    else:
                        # Checksum mismatch and restore fence allows DB → replace.
                        log_info(
                            "🔄 OCSP disk file for %s has wrong checksum (disk=%s, db=%s), replacing",
                            fingerprint,
                            disk_checksum[:8],
                            db_checksum[:8],
                        )
                        ocsp_path.write_bytes(db_data)
                        ocsp_path.chmod(0o640)
                        replaced_count += 1
                else:
                    # File missing — restore from database
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                    ocsp_path.write_bytes(db_data)
                    ocsp_path.chmod(0o640)
                    restored_count += 1
                    log_debug("✓ OCSP restored cached response for %s from database", fingerprint)
            except Exception as e:
                log_debug("⚠️ OCSP could not sync cache for %s: %s", fingerprint, e)

        if restored_count > 0 or replaced_count > 0 or skipped_newer > 0:
            log_info(
                "✓ OCSP sync complete: restored=%d, replaced=%d, unchanged=%d, skipped_newer=%d",
                restored_count,
                replaced_count,
                ok_count,
                skipped_newer,
            )
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
            no_ocsp_key = "custom_certs_no_ocsp" if cert_name.startswith(("customcert-", "selfsigned-")) else "le_certs_no_ocsp"
            stats[no_ocsp_key] = stats.get(no_ocsp_key, 0) + 1
            return (cert_name, None, 0, cert_checksum, pem_data, None, False)

        log_debug("🌐 OCSP responder for certificate %s: %s", cert_name, ocsp_url)

        # === Compute fingerprint for sharded path lookup ===
        fingerprint = cert_fp
        if not fingerprint:
            log_warning("⚠️ OCSP could not compute fingerprint for %s, treating as new fetch", cert_name)

        # === HTTP error backoff (400/500) ===
        # Skip only when the same leaf serial + OCSP URL is still in backoff.
        # SPKI-only keys would freeze every site/renew sharing that public key.
        if not force_fetch:
            leaf_serial = None
            try:
                leaf_serial = x509.load_pem_x509_certificate(pem_data).serial_number
            except Exception:
                pass
            backoff_remaining = _get_http_error_backoff_remaining(
                cert_fp, serial=leaf_serial, ocsp_url=ocsp_url
            )
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
                fp_prefix = (fingerprint[:16] + "...") if fingerprint else "unknown"
                log_info(
                    "✓ OCSP cached response for %s still valid for %ds (%.1f days) [fp=%s], above thresholds (refresh_threshold=%ds [20%% of %ds], 50%% threshold=%ds), skipping fetch",
                    cert_name,
                    cached_ttl,
                    cached_ttl / 86400.0,
                    fp_prefix,
                    refresh_threshold,
                    total_lifetime,
                    half_lifetime,
                )
                stats["ocsp_cached_responses"] = stats.get("ocsp_cached_responses", 0) + 1
                _ensure_issuer_pem(pem_data, fingerprint, cert_name, db)
                return (cert_name, None, cached_ttl, cert_checksum, pem_data, ocsp_url, False)

            if cached_ttl <= refresh_threshold:
                log_info("🔄 OCSP response for %s is near expiration (TTL=%ds <= refresh_threshold=%ds [20%% of %ds]), attempting aggressive refresh", cert_name, cached_ttl, refresh_threshold, total_lifetime)

        ocsp_der: Optional[bytes] = None
        ttl: int = 0

        # Use a timeout of 10 seconds per attempt, retry once after 10 seconds.
        # A verified non-GOOD answer is not a transport failure: count it once and do not retry.
        verified_nongood: Optional[_VerifiedNonGood] = None
        for attempt in (1, 2):
            try:
                ocsp_der, ttl, _issuer_pem = fetch_ocsp_response(pem_data, ocsp_url, cert_name=cert_name, timeout=10)
            except _VerifiedNonGood as exc:
                verified_nongood = exc
                break
            if ocsp_der:
                if _serial_blacklist_blocks(fingerprint, ocsp_der, cert_name):
                    stats["ocsp_serial_blacklist_blocked"] = stats.get("ocsp_serial_blacklist_blocked", 0) + 1
                    return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)
                log_debug("✓ OCSP successfully fetched response for %s on attempt %d (TTL=%ds)", cert_name, attempt, ttl)
                stats["ocsp_fetched_responses"] = stats.get("ocsp_fetched_responses", 0) + 1
                _clear_nongood_marker(fingerprint)
                break
            if attempt == 1:
                log_warning("⚠️ OCSP fetch failed for %s, retrying once after 2 seconds ...", cert_name)
                time.sleep(2)

        if verified_nongood is not None:
            tombstoned, halved_ttl = _note_verified_nongood(
                fingerprint,
                verified_nongood.serial,
                verified_nongood.status_name,
                cert_name,
                db,
                verified_nongood.this_update_unix,
            )
            if tombstoned:
                stats["ocsp_tombstoned"] = stats.get("ocsp_tombstoned", 0) + 1
                return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)
            keep_ttl = halved_ttl if halved_ttl is not None else cached_ttl
            if keep_ttl is not None and keep_ttl > 0:
                if halved_ttl is not None:
                    stats["ocsp_ttl_halved"] = stats.get("ocsp_ttl_halved", 0) + 1
                    log_warning(
                        "⚠️ OCSP CertStatus=%s for %s is below tombstone threshold; "
                        "keeping existing cache with halved TTL=%ds (staple still served until soft-recall / tombstone)",
                        verified_nongood.status_name,
                        cert_name,
                        keep_ttl,
                    )
                else:
                    log_warning(
                        "⚠️ OCSP CertStatus=%s for %s is below tombstone threshold; "
                        "existing cache retained (soft-recall may have set paged=false)",
                        verified_nongood.status_name,
                        cert_name,
                    )
                return (cert_name, None, cast(int, keep_ttl), cert_checksum, pem_data, ocsp_url, True)
            return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)

        if not ocsp_der:
            log_error("❌ OCSP failed to fetch response for %s after retries", cert_name)

            if cached_ttl is not None:
                current_ttl = cast(int, cached_ttl)
                # Recalculate refresh_threshold for failure handling (same logic as above)
                current_refresh_threshold = max(MIN_TTL, int(total_lifetime * 0.20)) if total_lifetime and total_lifetime > 0 else MIN_TTL

                if current_ttl <= 0:
                    log_warning(
                        "🧹 OCSP cached response for %s is already expired (nextUpdate or wall-clock max-age) "
                        "and refresh failed. Cleaning up invalid cache.",
                        cert_name,
                    )
                    cleanup_ocsp_cache(db, cert_name, fingerprint=cert_fp)
                else:
                    # Still within the effective window — keep stapling even inside the soft
                    # refresh window. Deleting here caused self-inflicted staple outages on
                    # transient responder failures. Wall-clock max-age is already folded into
                    # current_ttl via get_cached_ocsp_ttl.
                    log_warning(
                        "⚠️ OCSP could NOT refresh response for %s (TTL=%ds, refresh_threshold=%ds [20%% of %ds]); "
                        "keeping existing cache until effective expiry (nextUpdate and wall-clock max-age)",
                        cert_name,
                        current_ttl,
                        current_refresh_threshold,
                        total_lifetime,
                    )
                    _ensure_issuer_pem(pem_data, fingerprint, cert_name, db)
                return (cert_name, None, current_ttl, cert_checksum, pem_data, ocsp_url, True)

            return (cert_name, None, 0, cert_checksum, pem_data, ocsp_url, True)

        # Issuer is published with ocsp.der / ocsp.json under the cert lock in _persist_ocsp_results_to_disk.

        # Calculate checksum for integrity verification (lowercase for consistency)
        ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest().lower()
        ttl_readable = f"{ttl / 86400.0:.1f} days" if ttl >= 86400 else f"{ttl / 3600.0:.1f} hours"
        log_info(
            "⚡ OCSP final TTL for %s is %ds (%s) [fp=%s] (checksum=%s)",
            cert_name,
            ttl,
            ttl_readable,
            (fingerprint[:16] + "...") if fingerprint else "unknown",
            ocsp_checksum[:8],
        )

        # === Return result for batched database writes ===
        return (cert_name, ocsp_der, ttl, cert_checksum, pem_data, ocsp_url, True)

    except Exception as e:
        log_error("❌ OCSP exception while processing certificate %s: %s", cert_name, e)
        stats["errors"] = stats.get("errors", 0) + 1
        return (cert_name, None, 0, cert_checksum, pem_data, None, False)


def process_custom_certs(
    db: Optional[Any] = None,
    stats: Optional[dict] = None,
    lock_fd: Optional[OcspLock] = None,
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
        lock_fd: Optional OcspLock for lock refresh (for long operations)
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


def process_selfsigned_certs(
    db: Optional[Any] = None,
    stats: Optional[dict] = None,
    refresh_fn: Optional[Callable[[str], None]] = None,
    timeout_fn: Optional[Callable[[str], bool]] = None,
    force_fetch: bool = False,
) -> List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]]:
    """Fetch OCSP responses for self-signed certificates that advertise a responder."""
    if stats is None:
        stats = {}
    results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]] = []
    if not db:
        return results

    try:
        certs = _load_selfsigned_certs_from_db(db)
        if not certs:
            log_info("ℹ️ OCSP no self-signed certificates found in database")
            return results
        log_info("🔄 OCSP loaded %d self-signed certificate(s) from database", len(certs))
        stats["custom_certs_processed"] = stats.get("custom_certs_processed", 0) + len(certs)
        for cert_name, pem_data in sorted(certs.items()):
            if callable(timeout_fn) and timeout_fn(f"self-signed cert {cert_name}"):
                break
            if callable(refresh_fn):
                refresh_fn(cert_name)
            results.append(_process_cert(cert_name, pem_data, db, stats, force_fetch=force_fetch))
    except Exception as e:
        log_error("OCSP exception while processing self-signed certificates: %s", e)
        stats["errors"] = stats.get("errors", 0) + 1

    return results


def _service_name_from_dir(dir_name: str) -> str:
    """Strip key-type suffixes and cert-source prefixes to get the service name."""
    name = dir_name
    for prefix in ("customcert-", "selfsigned-"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    for suffix in ("-rsa", "-ecdsa"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _is_ocsp_enabled_for_service(service_name: str) -> bool:
    """Check if OCSP stapling is enabled for a specific service (multisite setting).

    The scheduler expands multisite settings to ``{service}_SSL_USE_OCSP_STAPLING``.
    That value wins when set. Otherwise the global ``SSL_USE_OCSP_STAPLING`` is used.
    The plugin default is ``no``.
    """
    if os.getenv("MULTISITE", "no").lower() == "yes" and service_name:
        site_value = os.getenv(f"{service_name}_SSL_USE_OCSP_STAPLING")
        if site_value is not None:
            return site_value.lower() == "yes"
    return os.getenv("SSL_USE_OCSP_STAPLING", "no").lower() == "yes"


def _is_ocsp_enabled_anywhere() -> bool:
    """True when at least one service would staple with the effective setting.

    Multisite: evaluate each SERVER_NAME entry with ``_is_ocsp_enabled_for_service``
    (site override wins). Global ``yes`` alone must not boot the job when every
    site overrides to ``no``.
    """
    if os.getenv("MULTISITE", "no").lower() == "yes":
        servers = [s for s in os.getenv("SERVER_NAME", "").split() if s]
        if servers:
            return any(_is_ocsp_enabled_for_service(server) for server in servers)
    return os.getenv("SSL_USE_OCSP_STAPLING", "no").lower() == "yes"


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
        resolved_fp = _normalize_fingerprint(fingerprint)

        # If fingerprint wasn't provided, try to resolve it from the marker stored in DB.
        if not resolved_fp and db and purge_db:
            try:
                resolved_fp = _read_cert_name_marker(db, cert_name)
            except Exception as e:
                log_debug("⚠️ OCSP could not resolve fingerprint marker for %s: %s", cert_name, e)
                resolved_fp = None

        # Disk cleanup: fingerprint-sharded storage only.
        if resolved_fp:
            ocsp_fp_dir = _get_sharded_ocsp_path(resolved_fp)
            if ocsp_fp_dir.is_dir():
                shutil.rmtree(ocsp_fp_dir, ignore_errors=True)
                log_info("🧹 OCSP removed sharded cache for %s (fingerprint=%s)", cert_name, resolved_fp[:16] + "...")
        else:
            log_debug("🧹 OCSP no fingerprint for %s; skipping disk shard cleanup", cert_name)

        if db and purge_db:
            try:
                # Always remove the cert-name marker (differential tracking).
                _delete_cert_name_marker(db, cert_name)
                # If we resolved a fingerprint, also remove the corresponding response+checksum.
                if resolved_fp:
                    _delete_fingerprint_db_rows(db, resolved_fp)
                log_debug("🧹 OCSP database records removed for %s (fingerprint resolved=%s)", cert_name, bool(resolved_fp))
            except Exception as e:
                log_debug("🧹 OCSP could not remove database entry for %s: %s", cert_name, e)
    else:
        # Clean up ALL OCSP caches (sharded tree under CONFIGS_SSL_BASE)
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

                issuer_file = Path(root) / "issuer.pem"
                if issuer_file.is_file():
                    try:
                        issuer_file.unlink()
                    except Exception as e:
                        log_debug("⚠️ OCSP failed to unlink issuer.pem %s: %s", issuer_file, e)

                # Remove empty directories (walk in reverse order ensures we clean up bottom-up)
                try:
                    if root != str(CONFIGS_SSL_BASE):  # Don't remove the base directory
                        Path(root).rmdir()
                except OSError:
                    pass  # Directory not empty or other error, skip

        if db and purge_db:
            try:
                # Remove all OCSP-related cache entries from database.
                # Also wipe leftover pre-shard keys (ocsp/<fp>, issuer/<fp>) if any remain.
                job_cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh")
                for cache_file in job_cache_files:
                    file_name = cache_file.get("file_name", "")
                    if (
                        file_name.startswith("ocsp/")
                        or file_name.startswith(OCSP_MARKER_PREFIX)
                        or file_name.startswith("issuer/")
                        or file_name.startswith("cert_checksum/")
                        or file_name.startswith("ocsp-floor/")
                        or file_name == "last_full_refresh"
                        or _fingerprint_from_ocsp_der_name(file_name)
                        or _fingerprint_from_issuer_name(file_name)
                        or _fingerprint_from_meta_name(file_name)
                    ):
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


def _cleanup_expired_ocsp_entries(
    db: Optional[Any] = None,
    stats: Optional[dict] = None,
) -> int:
    """
    Cleanup expired/stale OCSP response cache entries.

    This job maintains a fingerprint-sharded cache:
      - /var/cache/bunkerweb/ssl/<hex1>/<hex2>/<fingerprint>/ocsp.der
      - /var/cache/bunkerweb/ssl/<hex1>/<hex2>/<fingerprint>/ocsp.json
    and mirrors OCSP response bytes in database cache entries under the same
    relative sharded paths (plus ocsp-marker/ and cert_checksum/).
    """
    if stats is None:
        stats = {}

    now = datetime.now(timezone.utc)

    # Fingerprints whose ocsp.{json,der} are believed expired.
    expired_fingerprints: set = set()

    # Fingerprints whose ocsp.json exists but expires_unix couldn't be read,
    # so we might need to fall back to parsing ocsp.der.
    meta_unparseable_fingerprints: set = set()

    expired_cleaned_count: int = 0

    max_disk_meta_checks = 2000
    max_disk_der_checks = 2000
    max_db_checks = 500

    def _meta_expires_unix(meta: Dict[str, Any]) -> Optional[int]:
        """Absolute UTC death time from ocsp.json (expires_unix or next_update_unix)."""
        for key in ("expires_unix", "next_update_unix"):
            raw = meta.get(key)
            if isinstance(raw, (int, float)) and int(raw) > 0:
                return int(raw)
            if isinstance(raw, str) and raw.isdigit():
                return int(raw)
        return None

    def _delete_fingerprint_cache(fingerprint: str) -> None:
        nonlocal expired_cleaned_count
        if not fingerprint:
            return
        if fingerprint in expired_fingerprints:
            return

        ocsp_dir = _get_sharded_ocsp_path(fingerprint)
        try:
            shutil.rmtree(ocsp_dir, ignore_errors=True)
        except Exception:
            pass

        if db:
            _delete_fingerprint_db_rows(db, fingerprint)

        expired_fingerprints.add(fingerprint)
        expired_cleaned_count += 1

    # 1. Disk cleanup using ocsp.json expires_unix.
    if CONFIGS_SSL_BASE.is_dir():
        try:
            meta_files = list(CONFIGS_SSL_BASE.rglob("ocsp.json"))
        except Exception:
            meta_files = []

        now_unix = int(now.timestamp())
        for meta_file in meta_files[:max_disk_meta_checks]:
            try:
                raw = meta_file.read_text(encoding="utf-8")
                meta = json.loads(raw) if raw else None
                if not isinstance(meta, dict):
                    continue

                fingerprint = _normalize_fingerprint(meta.get("fingerprint")) or _normalize_fingerprint(
                    meta_file.parent.name
                )
                if not fingerprint:
                    continue

                # Backoff markers must not drive deletion; only success expires_unix (or ocsp.der) may.
                if meta.get("error_type") == "http_backoff":
                    if _meta_expires_unix(meta) is None:
                        meta_unparseable_fingerprints.add(fingerprint)
                    continue

                expires_unix = _meta_expires_unix(meta)
                if expires_unix is None:
                    meta_unparseable_fingerprints.add(fingerprint)
                    continue

                if expires_unix > now_unix:
                    continue

                _delete_fingerprint_cache(fingerprint)
            except Exception:
                # Best-effort: don't fail the job due to a corrupted metadata file.
                continue

    # 2. Disk cleanup fallback using ocsp.der parsing.
    # Parse ocsp.der when ocsp.json is missing OR could not be interpreted.
    if CONFIGS_SSL_BASE.is_dir():
        try:
            der_files = list(CONFIGS_SSL_BASE.rglob("ocsp.der"))
        except Exception:
            der_files = []

        checked = 0
        for ocsp_der in der_files:
            if checked >= max_disk_der_checks:
                break
            checked += 1

            try:
                fingerprint = _normalize_fingerprint(ocsp_der.parent.name)
                if not fingerprint or fingerprint in expired_fingerprints:
                    continue

                # Parse only when ocsp.json couldn't be trusted or is missing.
                ocsp_json = ocsp_der.parent / "ocsp.json"
                if ocsp_json.is_file() and fingerprint not in meta_unparseable_fingerprints:
                    continue

                ocsp_data = ocsp_der.read_bytes()
                ocsp_response = x509_ocsp.load_der_ocsp_response(ocsp_data)
                remaining, _ = _ocsp_response_lifetimes(ocsp_response)
                # Past death time (nextUpdate - skew).
                if remaining is not None and remaining <= OCSP_CLOCK_SKEW_SECONDS:
                    _delete_fingerprint_cache(fingerprint)
            except Exception:
                continue

    # 3. Database cleanup: delete expired OCSP response entries.
    if db:
        try:
            cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=True)
        except Exception:
            cache_files = []

        checked_db = 0
        for entry in cache_files:
            try:
                file_name = entry.get("file_name", "")
                fingerprint = _fingerprint_from_ocsp_der_name(file_name)
                if not fingerprint or fingerprint in expired_fingerprints:
                    continue

                data = entry.get("data")
                if not data:
                    continue

                if checked_db >= max_db_checks:
                    break
                checked_db += 1

                # Marker entries should not reach here (we require a valid fingerprint key).
                ocsp_response = x509_ocsp.load_der_ocsp_response(data)
                remaining, _ = _ocsp_response_lifetimes(ocsp_response)
                if remaining is not None and remaining <= OCSP_CLOCK_SKEW_SECONDS:
                    _delete_fingerprint_cache(fingerprint)
            except Exception:
                continue

    stats["expired_cleaned"] = stats.get("expired_cleaned", 0) + expired_cleaned_count
    if expired_cleaned_count > 0:
        log_info("🧹 OCSP removed %d expired cache item(s)", expired_cleaned_count)
    return expired_cleaned_count


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

        try:
            selfsigned_certs = _load_selfsigned_certs_from_db(db)
            for key, pem_data in selfsigned_certs.items():
                valid_cert_names.add(key)
                try:
                    fp = _get_cert_pubkey_fingerprint(_clean_pem(pem_data))
                    if fp:
                        valid_fingerprints.add(fp)
                except Exception:
                    continue
        except Exception as e:
            log_warning("⚠️ OCSP could not load self-signed certs for orphan check: %s", e)
            return  # Don't clean up if we can't verify what's valid

    if not valid_cert_names:
        log_debug("ℹ️ OCSP no valid certs found, skipping orphan cleanup to avoid accidental deletion")
        return

    orphaned_count: int = 0
    removed_fingerprints: set = set()

    def _drop_orphan_fingerprint(fingerprint: str) -> None:
        nonlocal orphaned_count
        if not fingerprint or fingerprint in valid_fingerprints or fingerprint in removed_fingerprints:
            return
        try:
            # Response, issuer, metadata, and checksum. Leaving any of
            # them lets restore_ocsp_from_database recreate the sharded directory.
            _delete_fingerprint_db_rows(db, fingerprint)
            removed_fingerprints.add(fingerprint)
            log_info("🧹 OCSP removed orphaned fingerprint DB entries: fp=%s", fingerprint[:16] + "...")
            orphaned_count += 1
        except Exception as e:
            log_debug("⚠️ OCSP failed to remove orphaned fingerprint DB entries fp=%s: %s", fingerprint, e)

    # Check database OCSP entries
    if db:
        try:
            cache_files = db.get_jobs_cache_files(job_name="ocsp-refresh", with_data=False)
            for entry in cache_files:
                file_name = entry.get("file_name", "")

                # Response/issuer/metadata rows are {hex1}/{hex2}/{fingerprint}/…
                if valid_fingerprints:
                    response_fp = _fingerprint_from_ocsp_der_name(file_name)
                    issuer_fp = None if response_fp else _fingerprint_from_issuer_name(file_name)
                    meta_fp = None if response_fp or issuer_fp else _fingerprint_from_meta_name(file_name)
                    related_fp = response_fp or issuer_fp or meta_fp
                    if related_fp:
                        if related_fp not in valid_fingerprints:
                            _drop_orphan_fingerprint(related_fp)
                        continue

                if not file_name.startswith(OCSP_MARKER_PREFIX):
                    continue
                cert_name_raw = file_name[len(OCSP_MARKER_PREFIX) :]

                # Marker entries map cert_name → fingerprint.
                if cert_name_raw in valid_cert_names:
                    continue

                log_info("🧹 OCSP removing orphaned marker entry for deleted service: %s", cert_name_raw)
                cleanup_ocsp_cache(db, cert_name_raw)
                orphaned_count += 1
        except Exception as e:
            log_warning("⚠️ OCSP could not check database for orphaned entries: %s", e)

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
        ocsp_entries = [e for e in all_entries if _fingerprint_from_ocsp_der_name(e.get("file_name", ""))]
        if not ocsp_entries:
            log_info("ℹ️ OCSP no cache entries in database to verify")
            return
            
        log_info("🔍 OCSP verifying %d cache entry(ies) from database", len(ocsp_entries))

        for entry in ocsp_entries:
            file_name = entry.get("file_name", "")
            if not _fingerprint_from_ocsp_der_name(file_name):
                continue

            cert_name_raw = _fingerprint_from_ocsp_der_name(file_name) or file_name
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
                if remaining is not None and remaining <= OCSP_CLOCK_SKEW_SECONDS:
                    log_warning(
                        "🧹 OCSP response in database for %s is past death time "
                        "(nextUpdate-%ds; raw remaining=%ds). Skipping restoration to disk.",
                        cert_name_raw,
                        OCSP_CLOCK_SKEW_SECONDS,
                        remaining,
                    )
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

            if data and _serial_blacklist_blocks(fingerprint, data, cert_name_raw):
                log_warning("🧹 OCSP skipping restore of blacklisted serial for %s", cert_name_raw)
                continue

            try:
                if not ocsp_path.is_file():
                    # File missing: restore from database
                    log_warning("⚠️ OCSP file missing for %s, restoring from database", cert_name_raw)
                    try:
                        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                        ocsp_path.write_bytes(data)
                        ocsp_path.chmod(0o640)
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
                            ocsp_path.chmod(0o640)
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
            # Only mirror bodies the scheduler canary already paged onto disk.
            # DB must not become a back-channel that restores an unpaged generation.
            disk_shard = _get_sharded_ocsp_path(cert_fp)
            disk_der_path = disk_shard / "ocsp.der"
            disk_meta_path = disk_shard / "ocsp.json"
            try:
                disk_der = disk_der_path.read_bytes() if disk_der_path.is_file() else b""
            except Exception:
                disk_der = b""
            if not disk_der or hashlib.sha256(disk_der).digest() != hashlib.sha256(ocsp_der).digest():
                log_debug(
                    "⏭️ OCSP skipping DB mirror for %s: disk not paged to this DER (canary-before-page)",
                    cert_name,
                )
                continue
            disk_meta_obj: Optional[Dict[str, Any]] = None
            try:
                if disk_meta_path.is_file():
                    loaded = json.loads(disk_meta_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        disk_meta_obj = loaded
            except Exception:
                disk_meta_obj = None
            if not isinstance(disk_meta_obj, dict) or disk_meta_obj.get("paged") is not True:
                log_debug(
                    "⏭️ OCSP skipping DB mirror for %s: disk meta not explicitly canary-paged",
                    cert_name,
                )
                continue

            cache_key = _ocsp_cache_relpath(cert_fp, "ocsp.der")
            try:
                # Pin CertID before mirroring DER — refuse multi-response / mismatch blobs.
                try:
                    leaf_obj, issuer_obj = _parse_chain(cleaned_pem, cert_name)
                    parsed_resp = x509_ocsp.load_der_ocsp_response(ocsp_der)
                    certid_pin = _pin_single_certid(parsed_resp, leaf_obj, issuer_obj, cert_name)
                    policy_reason = _ocsp_intrinsic_policy_reason(parsed_resp, cert_name)
                except Exception as pin_err:
                    log_error("❌ OCSP CertID/timing pin failed for DB store of %s: %s", cert_name, pin_err)
                    certid_pin = None
                    policy_reason = "thisUpdate_unreadable"
                if not certid_pin:
                    log_error("❌ OCSP refusing DB cache for %s without single CertID pin", cert_name)
                    stats["errors"] = stats.get("errors", 0) + 1
                    continue
                if policy_reason:
                    log_error(
                        "❌ OCSP refusing DB cache for %s (intrinsic timing: %s)",
                        cert_name,
                        policy_reason,
                    )
                    stats["errors"] = stats.get("errors", 0) + 1
                    continue

                aia_pin = _pin_aia_ocsp_uri(cleaned_pem, ocsp_url, cert_name)
                if not aia_pin:
                    log_error("❌ OCSP refusing DB cache for %s without AIA OCSP URI pin", cert_name)
                    stats["errors"] = stats.get("errors", 0) + 1
                    continue

                ocsp_checksum = hashlib.sha256(ocsp_der).hexdigest().lower()
                err = db.upsert_job_cache(
                    service_id=None,  # Global cache entry
                    file_name=cache_key,
                    data=ocsp_der,
                    job_name="ocsp-refresh",
                    checksum=ocsp_checksum,
                )
                if not err:
                    try:
                        # Prefer the paged on-disk meta (includes paged_unix / canary_reason).
                        # Disk is already verified paged=true above; never invent paged without canary.
                        meta = dict(disk_meta_obj)
                        meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")
                        db.upsert_job_cache(
                            service_id=None,
                            file_name=_ocsp_cache_relpath(cert_fp, "ocsp.json"),
                            data=meta_bytes,
                            job_name="ocsp-refresh",
                            checksum=hashlib.sha256(meta_bytes).hexdigest().lower(),
                        )
                    except Exception as meta_err:
                        log_debug("⚠️ OCSP could not store metadata for %s: %s", cert_name, meta_err)

                if err:
                    log_error("❌ OCSP error while storing response for %s (fingerprint: %s) in database: %s", cert_name, cert_fp[:16] + "...", err)
                    stats["errors"] = stats.get("errors", 0) + 1
                else:
                    log_info("✓ OCSP stored response for %s in database (fingerprint: %s, TTL=%ds)", cert_name, cert_fp[:16] + "...", ttl)

                    # Also store a marker entry with cert_name for differential tracking
                    # (ocsp-marker/<name>).
                    try:
                        _upsert_cert_name_marker(db, cert_name, cert_fp)
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


def _bump_ocsp_cache_epoch() -> None:
    """
    Bump a shared on-disk generation counter so HTTP and stream L1 caches
    (separate lua_shared_dict zones) both drop stale OCSP entries after publish.
    Workers compare TLS:SSL:ocsp_gen:{fp} to this file; they cannot cross-delete
    each other's shared dicts, so disk is the coherence bus.
    """
    try:
        CONFIGS_SSL_BASE.mkdir(parents=True, exist_ok=True)
        (CONFIGS_SSL_BASE / "ocsp-refuse").mkdir(parents=True, exist_ok=True)
        _atomic_write_text(CONFIGS_SSL_BASE / ".ocsp_epoch", str(time.time_ns()), mode=0o640)
    except Exception as e:
        log_debug("⚠️ OCSP could not bump cache epoch: %s", e)


def _clear_ocsp_peer_refuse(fingerprint: str) -> None:
    """Drop HTTP↔stream generation refuse marker for this SPKI (new page / tombstone)."""
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return
    try:
        refuse_dir = CONFIGS_SSL_BASE / "ocsp-refuse"
        refuse_dir.mkdir(parents=True, exist_ok=True)
        path = refuse_dir / normalized
        if path.is_file():
            path.unlink()
            log_debug("🧹 OCSP cleared peer-refuse bus for fp=%s...", normalized[:16])
    except Exception as e:
        log_debug("⚠️ OCSP could not clear peer-refuse for %s: %s", normalized[:16] if normalized else "?", e)


def _ocsp_floor_relpath(fingerprint: str) -> Optional[str]:
    """Job-cache file_name for the per-SPKI cluster floor."""
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return None
    return f"ocsp-floor/{normalized}"


def _advance_ocsp_cluster_floor(
    fingerprint: str,
    this_update_unix: Optional[int],
    job_run_id: Optional[str] = None,
    db: Optional[Any] = None,
    published_unix: Optional[int] = None,
) -> bool:
    """
    Raise the colony floor for this SPKI to this_update_unix when it is higher.

    Must-Staple Lua refuses until local ocsp.json this_update_unix is at least this
    floor, so a peer that already published/tombstoned cannot be undercut by a
    lagging node's older GOOD body. Floor is max-only on CA-signed thisUpdate
    (colony-comparable without synchronized clocks). published_unix is forensic
    only; never advance on wall clock alone. job_run_id is forensic only.
    """
    normalized = _normalize_fingerprint(fingerprint)
    try:
        new_this = int(this_update_unix) if this_update_unix is not None else 0
    except (TypeError, ValueError):
        new_this = 0
    if not normalized or new_this <= 0:
        return False
    try:
        new_pub = int(published_unix) if published_unix is not None else 0
    except (TypeError, ValueError):
        new_pub = 0

    floor_dir = CONFIGS_SSL_BASE / "ocsp-floor"
    floor_path = floor_dir / normalized
    try:
        floor_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log_debug("⚠️ OCSP could not create floor dir: %s", e)
        return False

    incoming: Dict[str, Any] = {"this_update_unix": new_this}
    if new_pub > 0:
        incoming["published_unix"] = new_pub
    if isinstance(job_run_id, str) and job_run_id:
        incoming["job_run_id"] = job_run_id
    disk_floor = load_disk_ocsp_floor(CONFIGS_SSL_BASE, normalized)
    if should_keep_disk_ocsp_floor(disk_floor, incoming):
        # Disk already at or above; still ensure DB has at least disk's value.
        mirror = disk_floor if isinstance(disk_floor, dict) else incoming
    else:
        try:
            payload = encode_ocsp_floor_payload(
                new_this,
                job_run_id if isinstance(job_run_id, str) else None,
                published_unix=new_pub if new_pub > 0 else None,
            )
            _atomic_write_bytes(floor_path, payload, mode=0o640)
            mirror = incoming
            log_info(
                "📈 OCSP cluster floor advanced fp=%s... this_update_unix=%s (was %s)",
                normalized[:16],
                new_this,
                ocsp_floor_published_unix(disk_floor) or "none",
            )
        except Exception as e:
            log_error("❌ OCSP could not advance cluster floor for %s: %s", normalized[:16], e)
            return False

    if db is not None and isinstance(mirror, dict):
        rel = _ocsp_floor_relpath(normalized)
        if rel:
            try:
                mirror_this = int(mirror["this_update_unix"]) if mirror.get("this_update_unix") else 0
                mirror_pub = int(mirror["published_unix"]) if mirror.get("published_unix") else 0
                # Prefer writing CA-time floor; legacy disk may only have published_unix.
                if mirror_this > 0:
                    payload = encode_ocsp_floor_payload(
                        mirror_this,
                        mirror.get("job_run_id") if isinstance(mirror.get("job_run_id"), str) else None,
                        published_unix=mirror_pub if mirror_pub > 0 else None,
                    )
                elif mirror_pub > 0:
                    payload = encode_ocsp_floor_payload(
                        None,
                        mirror.get("job_run_id") if isinstance(mirror.get("job_run_id"), str) else None,
                        published_unix=mirror_pub,
                    )
                else:
                    return True
                db.upsert_job_cache(
                    service_id=None,
                    file_name=rel,
                    data=payload,
                    job_name="ocsp-refresh",
                    checksum=hashlib.sha256(payload).hexdigest().lower(),
                )
            except Exception as e:
                log_debug("⚠️ OCSP could not mirror cluster floor for %s: %s", normalized[:16], e)
    return True


def _restore_ocsp_cluster_floor_entry(file_name: str, data: bytes) -> bool:
    """Max-only restore of one ocsp-floor/{fp} row from DB. Returns True if applied."""
    floor_fp = parse_ocsp_floor_cache_name(file_name)
    if not floor_fp:
        return False
    incoming = parse_ocsp_floor_bytes(data)
    disk_floor = load_disk_ocsp_floor(CONFIGS_SSL_BASE, floor_fp)
    if should_keep_disk_ocsp_floor(disk_floor, incoming):
        log_info(
            "⏭️ OCSP floor restore skip fp=%s... disk_rank=%s incoming_rank=%s",
            floor_fp[:16],
            ocsp_floor_published_unix(disk_floor),
            ocsp_floor_published_unix(incoming),
        )
        return False
    if not isinstance(incoming, dict) or ocsp_floor_published_unix(incoming) <= 0:
        return False
    floor_dir = CONFIGS_SSL_BASE / "ocsp-floor"
    floor_dir.mkdir(parents=True, exist_ok=True)
    run_id = incoming.get("job_run_id") if isinstance(incoming.get("job_run_id"), str) else None
    this_u = int(incoming["this_update_unix"]) if incoming.get("this_update_unix") else 0
    pub_u = int(incoming["published_unix"]) if incoming.get("published_unix") else 0
    _atomic_write_bytes(
        floor_dir / floor_fp,
        encode_ocsp_floor_payload(
            this_u if this_u > 0 else None,
            run_id,
            published_unix=pub_u if pub_u > 0 else None,
        ),
        mode=0o640,
    )
    log_info(
        "📈 OCSP floor restored fp=%s... this_update_unix=%s published_unix=%s",
        floor_fp[:16],
        this_u or "none",
        pub_u or "none",
    )
    return True


def _nongood_marker_path(fingerprint: str) -> Optional[Path]:
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return None
    return _get_sharded_ocsp_path(normalized) / "nongood.json"


def _clear_nongood_marker(fingerprint: Optional[str]) -> None:
    """A verified GOOD answer that is allowed to publish resets the non-GOOD streak."""
    if not fingerprint:
        return
    path = _nongood_marker_path(fingerprint)
    if path is None or not path.is_file():
        return
    try:
        path.unlink()
    except Exception as e:
        log_debug("⚠️ OCSP could not clear non-GOOD marker for %s: %s", fingerprint[:16], e)


def _serial_blacklist_path(fingerprint: str) -> Optional[Path]:
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return None
    return _get_sharded_ocsp_path(normalized) / "serial-blacklist.json"


def _read_serial_blacklist(fingerprint: str) -> Optional[Dict[str, Any]]:
    path = _serial_blacklist_path(fingerprint)
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"unreadable": True}
    if not isinstance(data, dict):
        return {"unreadable": True}
    return data


def _write_serial_blacklist(
    fingerprint: str,
    serial: Optional[int],
    status_name: str,
    this_update_unix: Optional[int],
) -> None:
    path = _serial_blacklist_path(fingerprint)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    decimal, serial_hex = _serial_forms(serial)
    # Omit this_update_unix when unknown — a JSON null can never satisfy
    # "newer GOOD thisUpdate" and permanently sticks the ban for this serial.
    stamp: Dict[str, Any] = {"status": status_name}
    if isinstance(this_update_unix, (int, float)) and int(this_update_unix) > 0:
        stamp["this_update_unix"] = int(this_update_unix)
    # Nil serial still writes a fail-closed marker: Lua refuses when serial_hex is absent.
    if not decimal:
        stamp["serial_unknown"] = True
        _atomic_write_text(path, json.dumps(stamp), mode=0o640)
        return
    stamp["serial"] = decimal
    stamp["serial_hex"] = serial_hex
    _atomic_write_text(path, json.dumps(stamp), mode=0o640)


def _clear_serial_blacklist(fingerprint: str) -> None:
    path = _serial_blacklist_path(fingerprint)
    if path is None or not path.is_file():
        return
    try:
        path.unlink()
    except Exception as e:
        log_debug("⚠️ OCSP could not clear serial blacklist for %s: %s", fingerprint[:16], e)


def _der_serial_and_this_update(ocsp_der: bytes) -> Tuple[Optional[str], Optional[int]]:
    try:
        parsed = x509_ocsp.load_der_ocsp_response(ocsp_der)
        decimal, _serial_hex = _serial_forms(parsed.serial_number)
        return decimal, _ocsp_this_update_unix(parsed)
    except Exception:
        return None, None


def _serial_ban_superseded_by_good(ban_unix: Optional[int], this_unix: Optional[int]) -> bool:
    """
    Same-serial GOOD clears the ban when its thisUpdate is strictly newer.
    A ban with no this_update_unix (legacy null / omitted) is superseded by any
    dated GOOD — otherwise that ban can never clear.
    """
    if this_unix is None:
        return False
    if ban_unix is None:
        return True
    return this_unix > ban_unix


def _serial_blacklist_blocks(fingerprint: Optional[str], ocsp_der: bytes, cert_name: str) -> bool:
    """
    True when this body must not be published or restored.
    The same serial stays banned until a verified GOOD with a later thisUpdate.
    A ban missing this_update_unix clears on any dated GOOD for that serial.
    A different serial (reissue on the same key) is not banned.
    serial_unknown (tombstone without a readable serial) clears on any verified GOOD
    that has a serial — otherwise it would permanently block republish.
    """
    if not fingerprint or not ocsp_der:
        return False
    ban = _read_serial_blacklist(fingerprint)
    if not ban:
        return False
    if ban.get("unreadable"):
        log_error("❌ OCSP serial blacklist for %s is unreadable; refusing to publish", cert_name)
        return True
    got_serial, this_unix = _der_serial_and_this_update(ocsp_der)
    if ban.get("serial_unknown"):
        if got_serial:
            _clear_serial_blacklist(fingerprint)
            log_info(
                "✓ OCSP serial_unknown blacklist cleared for %s (verified GOOD serial=%s)",
                cert_name,
                got_serial,
            )
            return False
        log_error("❌ OCSP serial_unknown blacklist for %s; refusing body without serial", cert_name)
        return True
    banned_serial = str(ban.get("serial")) if ban.get("serial") is not None else None
    if not banned_serial or not got_serial:
        log_error("❌ OCSP serial blacklist for %s has no comparable serial; refusing to publish", cert_name)
        return True
    if got_serial != banned_serial:
        return False
    try:
        ban_unix = int(ban.get("this_update_unix"))
    except (TypeError, ValueError):
        ban_unix = None
    if _serial_ban_superseded_by_good(ban_unix, this_unix):
        _clear_serial_blacklist(fingerprint)
        log_info(
            "✓ OCSP serial blacklist cleared for %s serial=%s (newer GOOD thisUpdate=%s, ban=%s)",
            cert_name,
            got_serial,
            this_unix,
            ban_unix,
        )
        return False
    log_error(
        "❌ OCSP serial %s for %s stays blacklisted until a newer GOOD (thisUpdate=%s, ban=%s)",
        got_serial,
        cert_name,
        this_unix,
        ban_unix,
    )
    return True


def _delete_ocsp_der_db_rows(db: Optional[Any], fingerprint: str) -> None:
    """Drop stored DER so end-of-job restore cannot put a tombstoned staple back."""
    if db is None or not fingerprint:
        return
    names = []
    rel = _ocsp_cache_relpath(fingerprint, "ocsp.der")
    if rel:
        names.append(rel)
    for name in names:
        try:
            db.delete_job_cache(file_name=name, job_name="ocsp-refresh")
        except Exception:
            pass


def _tombstone_ocsp_shard(
    fingerprint: str,
    serial: Optional[int],
    status_name: str,
    cert_name: str,
    db: Optional[Any],
    this_update_unix: Optional[int] = None,
) -> bool:
    """
    Remove the published staple for this SPKI.

    Order matters for the mid-flight handshake window:
    1. Write ocsp.json with tombstoned=true / paged=false (no der_sha256) so Lua
       can refuse without waiting for .ocsp_epoch.
    2. Bump .ocsp_epoch immediately so both L1 zones drop the last GOOD.
    3. Then unlink ocsp.der, write serial blacklist, clear refuse, drop DB DER.

    Keeps must_staple in ocsp.json so Must-Staple still fail-closes.
    """
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return False
    lock = _acquire_cert_lock(normalized)
    if lock is None:
        log_error("❌ OCSP could not lock shard to tombstone %s", cert_name)
        return False
    try:
        shard = _resolved_sharded_ocsp_path(normalized)
        shard.mkdir(parents=True, exist_ok=True)
        meta_path = shard / "ocsp.json"
        meta: Dict[str, Any] = {
            "fingerprint": normalized,
            "tombstoned": True,
            "paged": False,
            "cert_status": status_name,
        }
        if serial is not None:
            meta["serial"] = str(serial)
        try:
            if meta_path.is_file():
                old = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(old, dict) and old.get("must_staple") is True:
                    meta["must_staple"] = True
        except Exception:
            pass
        meta.update(_provenance_meta())
        meta["published_unix"] = int(datetime.now(timezone.utc).timestamp())
        # Visible refuse signal first — Lua samples tombstoned before epoch/DER.
        _atomic_write_text(meta_path, json.dumps(meta), mode=0o640)
        _bump_ocsp_cache_epoch()
        _write_serial_blacklist(normalized, serial, status_name, this_update_unix)
        der_path = shard / "ocsp.der"
        try:
            if der_path.is_file():
                der_path.unlink()
        except Exception as e:
            log_error("❌ OCSP could not remove ocsp.der while tombstoning %s: %s", cert_name, e)
            return False
        _delete_ocsp_der_db_rows(db, normalized)
        _clear_ocsp_peer_refuse(normalized)
        _advance_ocsp_cluster_floor(
            normalized,
            this_update_unix,
            meta.get("job_run_id"),
            db,
            meta.get("published_unix"),
        )
        log_error(
            "🧹 OCSP tombstoned shard for %s (fp=%s..., CertStatus=%s, serial=%s); previous GOOD staple removed",
            cert_name,
            normalized[:16],
            status_name,
            serial,
        )
        return True
    except Exception as e:
        log_error("❌ OCSP tombstone failed for %s: %s", cert_name, e)
        return False
    finally:
        _release_cert_lock(lock, normalized)


def _halve_cached_staple_ttl(fingerprint: str, cert_name: str, db: Optional[Any] = None) -> Optional[int]:
    """
    First verified non-GOOD that does not yet tombstone: cut leftover GOOD TTL in half.
    Keeps ocsp.der; rewrites expires / expires_unix, upserts that meta to the DB (so
    restore cannot put the longer death clock back), and bumps the epoch so L1 reloads.
    Returns the new remaining seconds, or None when there was nothing to shorten.
    """
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return None
    lock = _acquire_cert_lock(normalized)
    if lock is None:
        log_warning("⚠️ OCSP could not lock shard to halve TTL for %s", cert_name)
        return None
    try:
        shard = _get_sharded_ocsp_path(normalized)
        der_path = shard / "ocsp.der"
        meta_path = shard / "ocsp.json"
        if not der_path.is_file():
            return None

        now_unix = int(datetime.now(timezone.utc).timestamp())
        expires_unix: Optional[int] = None
        meta: Dict[str, Any] = {}
        if meta_path.is_file():
            try:
                loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    meta = loaded
                    raw_exp = meta.get("expires_unix")
                    if isinstance(raw_exp, (int, float)) and int(raw_exp) > 0:
                        expires_unix = int(raw_exp)
                    elif isinstance(raw_exp, str) and raw_exp.isdigit():
                        expires_unix = int(raw_exp)
            except Exception:
                meta = {}

        if expires_unix is None:
            try:
                remaining, _ = _ocsp_response_lifetimes(x509_ocsp.load_der_ocsp_response(der_path.read_bytes()))
                if remaining is not None:
                    expires_unix = now_unix + int(remaining)
            except Exception:
                return None

        remaining = max(0, _seconds_until_death(expires_unix, now_unix))
        if remaining <= 0:
            return 0
        wall_remaining = _wall_clock_remaining(meta, now_unix)
        if wall_remaining is not None:
            remaining = min(remaining, wall_remaining)
            if remaining <= 0:
                return 0
        if meta.get("ttl_halved_after_nongood") is True:
            # Already shortened once for this cached body; do not quarter it.
            return remaining

        new_remaining = max(1, remaining // 2)
        # Shorten expires only; keep published_unix / max_age_unix for the same body.
        published = _meta_int_unix(meta, "published_unix")
        max_age = _meta_int_unix(meta, "max_age_unix")
        meta.update(_ocsp_expiry_meta(new_remaining))
        if published is not None:
            meta["published_unix"] = published
        if max_age is not None:
            meta["max_age_unix"] = max_age
        elif published is not None:
            meta["max_age_unix"] = published + PREVIOUS_GOOD_MAX_AGE_SECONDS
        meta["fingerprint"] = normalized
        meta["ttl_halved_after_nongood"] = True
        meta["ttl_halved_from"] = remaining
        meta.update(_provenance_meta())
        meta_text = json.dumps(meta, separators=(",", ":"))
        _atomic_write_text(meta_path, meta_text, mode=0o640)
        _bump_ocsp_cache_epoch()
        if db is not None:
            try:
                meta_bytes = meta_text.encode("utf-8")
                err = db.upsert_job_cache(
                    service_id=None,
                    file_name=_ocsp_cache_relpath(normalized, "ocsp.json"),
                    data=meta_bytes,
                    job_name="ocsp-refresh",
                    checksum=hashlib.sha256(meta_bytes).hexdigest().lower(),
                )
                if err:
                    log_warning(
                        "⚠️ OCSP halved TTL on disk for %s but DB upsert failed: %s",
                        cert_name,
                        err,
                    )
            except Exception as e:
                log_warning(
                    "⚠️ OCSP halved TTL on disk for %s but could not upsert meta: %s",
                    cert_name,
                    e,
                )
        log_warning(
            "⚠️ OCSP halved leftover staple TTL for %s after first non-GOOD (fp=%s... %ds → %ds)",
            cert_name,
            normalized[:16],
            remaining,
            new_remaining,
        )
        return new_remaining
    except Exception as e:
        log_warning("⚠️ OCSP could not halve leftover TTL for %s: %s", cert_name, e)
        return None
    finally:
        _release_cert_lock(lock, normalized)


def _unpage_ocsp_shard_after_nongood(
    fingerprint: str,
    cert_name: str,
    db: Optional[Any] = None,
) -> bool:
    """
    Soft recall: set paged=false so handshakes stop stapling the cached GOOD
    without tombstoning (no serial ban / DER unlink yet). Idempotent when already
    unpaged. Upserts meta and bumps epoch so L1 drops the body.
    """
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return False
    lock = _acquire_cert_lock(normalized)
    if lock is None:
        log_warning("⚠️ OCSP could not lock shard to unpage after non-GOOD for %s", cert_name)
        return False
    try:
        shard = _get_sharded_ocsp_path(normalized)
        meta_path = shard / "ocsp.json"
        if not meta_path.is_file():
            return False
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(loaded, dict):
            return False
        if loaded.get("tombstoned") is True:
            return False
        if loaded.get("paged") is not True and loaded.get("unpaged_after_nongood") is True:
            return True
        loaded["paged"] = False
        loaded["unpaged_after_nongood"] = True
        loaded["fingerprint"] = normalized
        loaded.update(_provenance_meta())
        meta_text = json.dumps(loaded, separators=(",", ":"))
        _atomic_write_text(meta_path, meta_text, mode=0o640)
        _bump_ocsp_cache_epoch()
        if db is not None:
            try:
                meta_bytes = meta_text.encode("utf-8")
                err = db.upsert_job_cache(
                    service_id=None,
                    file_name=_ocsp_cache_relpath(normalized, "ocsp.json"),
                    data=meta_bytes,
                    job_name="ocsp-refresh",
                    checksum=hashlib.sha256(meta_bytes).hexdigest().lower(),
                )
                if err:
                    log_warning(
                        "⚠️ OCSP unpaged shard for %s but DB upsert failed: %s",
                        cert_name,
                        err,
                    )
            except Exception as e:
                log_warning(
                    "⚠️ OCSP unpaged shard for %s but could not upsert meta: %s",
                    cert_name,
                    e,
                )
        log_warning(
            "⚠️ OCSP soft-recalled staple for %s after repeated non-GOOD (fp=%s... paged=false; DER kept until tombstone)",
            cert_name,
            normalized[:16],
        )
        return True
    except Exception as e:
        log_warning("⚠️ OCSP could not unpage shard after non-GOOD for %s: %s", cert_name, e)
        return False
    finally:
        _release_cert_lock(lock, normalized)


def _note_verified_nongood(
    fingerprint: Optional[str],
    serial: Optional[int],
    status_name: str,
    cert_name: str,
    db: Optional[Any],
    this_update_unix: Optional[int] = None,
) -> Tuple[bool, Optional[int]]:
    """
    Count one verified non-GOOD answer. Tombstone the shard at the threshold.
    First sighting below threshold: halve leftover GOOD TTL (staple still served).
    From _NON_GOOD_UNPAGE_AFTER (UNKNOWN: 2): soft-recall with paged=false.
    Returns (tombstoned, remaining_ttl_after_halve_or_None).
    """
    if not fingerprint:
        log_error("❌ OCSP CertStatus=%s for %s but fingerprint is missing; cannot tombstone", status_name, cert_name)
        return False, None
    normalized = _normalize_fingerprint(fingerprint)
    if not normalized:
        return False, None
    threshold = _NON_GOOD_TOMBSTONE_AFTER.get(status_name, 1)
    path = _nongood_marker_path(normalized)
    if path is None:
        return False, None
    consecutive = 1
    try:
        if path.is_file():
            old = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(old, dict):
                old_serial = str(old.get("serial")) if old.get("serial") is not None else None
                new_serial = str(serial) if serial is not None else None
                same_serial = old_serial == new_serial
                same_status = old.get("status") == status_name
                if same_serial and same_status:
                    try:
                        consecutive = int(old.get("consecutive") or 0) + 1
                    except (TypeError, ValueError):
                        consecutive = 1
    except Exception:
        consecutive = 1
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(
            path,
            json.dumps({"consecutive": consecutive, "status": status_name, "serial": None if serial is None else str(serial)}),
            mode=0o640,
        )
    except Exception as e:
        log_error("❌ OCSP could not record non-GOOD streak for %s: %s", cert_name, e)
        return False, None
    log_error(
        "❌ OCSP verified CertStatus=%s for %s (serial=%s) streak=%d/%d",
        status_name,
        cert_name,
        serial,
        consecutive,
        threshold,
    )
    if consecutive < threshold:
        halved = None
        if consecutive == 1:
            halved = _halve_cached_staple_ttl(normalized, cert_name, db)
        unpage_after = _NON_GOOD_UNPAGE_AFTER.get(status_name)
        if isinstance(unpage_after, int) and unpage_after > 0 and consecutive >= unpage_after:
            _unpage_ocsp_shard_after_nongood(normalized, cert_name, db)
        return False, halved
    return _tombstone_ocsp_shard(normalized, serial, status_name, cert_name, db, this_update_unix), None


def _persist_ocsp_results_to_disk(
    all_ocsp_results: List[Tuple[str, Optional[bytes], int, str, bytes, Optional[str], bool]],
    stats: Optional[Dict[str, int]] = None,
    db: Optional[Any] = None,
) -> None:
    """
    Write OCSP cache as one locked directory rename per fingerprint after a
    scheduler canary handshake: stage issuer.pem + ocsp.der + ocsp.json, canary,
    then page the shard into place.

    Holding the cert lock across the publish avoids concurrent writers racing
    the rename. The previous shard stays intact if staging, canary, or rename fails.
    After the batch: bump ``.ocsp_epoch`` once, then clear peer-refuse for each
    published SPKI (L1 must invalidate before the refuse bus unlocks).
    Called at normal completion and on timeout.
    """
    if not all_ocsp_results:
        return

    if stats is None:
        stats = {}

    published_fps: List[str] = []
    for cert_name, ocsp_der, ttl, checksum, pem_data, ocsp_url, was_attempted in all_ocsp_results:
        if not ocsp_der:
            continue
        try:
            cleaned_pem = _clean_pem(pem_data)
            # Compute certificate public key fingerprint for storage location
            cert_fp = _get_cert_pubkey_fingerprint(cleaned_pem)
            if not cert_fp:
                log_error("❌ OCSP cannot store response for %s: failed to compute fingerprint", cert_name)
                stats["errors"] = stats.get("errors", 0) + 1
                continue
            if _serial_blacklist_blocks(cert_fp, ocsp_der, cert_name):
                stats["ocsp_serial_blacklist_blocked"] = stats.get("ocsp_serial_blacklist_blocked", 0) + 1
                continue

            # Acquire lock to prevent race conditions with concurrent OCSP fetches.
            # Lock is keyed by certificate public key fingerprint (not hostname/cert_name).
            lock_fd = _acquire_cert_lock(cert_fp)
            if lock_fd is None:
                # Avoid publishing the shard without a lock.
                stats["errors"] = stats.get("errors", 0) + 1
                log_warning(
                    "⏭️ OCSP skipping disk write for %s (fingerprint: %s) due to lock acquisition failure",
                    cert_name,
                    cert_fp[:16] + "...",
                )
                continue
            try:
                publish_error_logged = False
                ocsp_cert_dir = _get_sharded_ocsp_path(cert_fp)
                try:
                    _leaf, issuer = _parse_chain(cleaned_pem, cert_name)
                    issuer_pem = issuer.public_bytes(Encoding.PEM)
                    if not issuer_pem:
                        raise RuntimeError("empty issuer PEM")
                except Exception as issuer_err:
                    log_error(
                        "❌ OCSP refusing to publish ocsp.der for %s without issuer.pem: %s",
                        cert_name,
                        issuer_err,
                    )
                    stats["errors"] = stats.get("errors", 0) + 1
                    publish_error_logged = True
                    raise

                meta = _extract_cert_metadata(cleaned_pem, cert_name)
                meta["fingerprint"] = cert_fp
                meta["der_sha256"] = hashlib.sha256(ocsp_der).hexdigest().lower()
                # Re-pin CertID at publish: exactly one SingleResponse matching leaf+issuer.
                try:
                    parsed_resp = x509_ocsp.load_der_ocsp_response(ocsp_der)
                    certid_pin = _pin_single_certid(parsed_resp, _leaf, issuer, cert_name)
                except Exception as pin_err:
                    log_error("❌ OCSP CertID pin failed for %s: %s", cert_name, pin_err)
                    certid_pin = None
                if not certid_pin:
                    stats["errors"] = stats.get("errors", 0) + 1
                    publish_error_logged = True
                    raise RuntimeError("CertID pin refused (need exactly one matching SingleResponse)")
                meta["certid"] = certid_pin
                # Keep top-level serial aligned with the pinned CertID.
                meta["serial"] = certid_pin["serial"]
                # Pin staple to the leaf AIA OCSP URI that produced this body.
                aia_pin = _pin_aia_ocsp_uri(cleaned_pem, ocsp_url, cert_name)
                if not aia_pin:
                    stats["errors"] = stats.get("errors", 0) + 1
                    publish_error_logged = True
                    raise RuntimeError("AIA OCSP URI pin refused")
                meta["aia_ocsp_uri"] = aia_pin
                meta["ocsp_url"] = aia_pin
                # Re-check intrinsic policy at publish and stamp signed timing for Lua.
                try:
                    parsed_for_timing = x509_ocsp.load_der_ocsp_response(ocsp_der)
                    policy_reason = _ocsp_intrinsic_policy_reason(parsed_for_timing, cert_name)
                except Exception as timing_err:
                    log_error("❌ OCSP intrinsic policy check failed for %s: %s", cert_name, timing_err)
                    policy_reason = "thisUpdate_unreadable"
                if policy_reason:
                    stats["errors"] = stats.get("errors", 0) + 1
                    publish_error_logged = True
                    raise RuntimeError(f"intrinsic timing refused: {policy_reason}")
                meta.update(_ocsp_signed_timing_meta(ocsp_der))
                meta.update(_ocsp_expiry_meta(ttl))
                if isinstance(meta.get("next_update_unix"), int) and meta["next_update_unix"] > 0:
                    meta["expires_unix"] = meta["next_update_unix"]
                meta.update(_provenance_meta())

                published_dir = _publish_ocsp_shard(
                    cert_fp,
                    issuer_pem=issuer_pem,
                    ocsp_der=ocsp_der,
                    meta=meta,
                    leaf_pem=cleaned_pem,
                    cert_name=cert_name,
                    db=db,
                )
                published_fps.append(cert_fp)
                _advance_ocsp_cluster_floor(
                    cert_fp,
                    meta.get("this_update_unix"),
                    meta.get("job_run_id"),
                    db,
                    meta.get("published_unix"),
                )
                log_info(
                    "✓ OCSP saved response for %s to disk at %s (fingerprint: %s)",
                    cert_name,
                    published_dir / "ocsp.der",
                    cert_fp[:16] + "...",
                )
                log_debug(
                    "✓ OCSP saved metadata for %s (fingerprint: %s, serial=%s, must_staple=%s)",
                    cert_name,
                    cert_fp[:16] + "...",
                    meta.get("serial") or "unknown",
                    meta.get("must_staple"),
                )
            except Exception as e:
                try:
                    # Drop leftover staging only — never unlink .old-* here; that tree
                    # may be the sole intact shard if restore-after-rename failed.
                    parent = ocsp_cert_dir.parent
                    for tmp_file in ocsp_cert_dir.glob(".*.tmp"):
                        tmp_file.unlink()
                    for orphan in parent.glob(f".{ocsp_cert_dir.name}.pub-*"):
                        shutil.rmtree(orphan, ignore_errors=True)
                except Exception:
                    pass
                if not publish_error_logged:
                    log_error("❌ OCSP error while writing response for %s to disk: %s", cert_name, e)
                    log_info("ℹ️ OCSP kept existing OCSP response file for %s (new fetch failed)", cert_name)
                    stats["errors"] = stats.get("errors", 0) + 1
            finally:
                if lock_fd is not None:
                    _release_cert_lock(lock_fd, cert_fp)
        except Exception as e:
            log_error("❌ OCSP exception while writing response for %s to disk: %s", cert_name, e)
            stats["errors"] = stats.get("errors", 0) + 1

    # One bump per persist batch, then unlock peer-refuse. Order matters: clearing
    # refuse before the epoch bump would let handshakes use still-valid L1 entries
    # for a generation the bus no longer blocks.
    if published_fps:
        _bump_ocsp_cache_epoch()
        for fp in published_fps:
            _clear_ocsp_peer_refuse(fp)


def main() -> int:
    global status
    db: Optional[Any] = None

    # Job-level timeout: exit gracefully if exceeded (prevents deadlock on slow systems)
    # Responses fetched so far are saved; next run continues where left off.
    # Must stay below caller OCSP_REFRESH_TIMEOUT (2100s) for a clean persist window.
    JOB_TIMEOUT = JOB_TIMEOUT_SECONDS
    job_start_time = time.time()
    lock_fd_main = None
    timed_out = False

    # Provision peer-refuse bus off the TLS path (handshake writes must not mkdir).
    try:
        (CONFIGS_SSL_BASE / "ocsp-refuse").mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log_debug("⚠️ OCSP could not provision ocsp-refuse/: %s", e)

    def check_job_timeout(phase: str = "") -> bool:
        """Check if job has exceeded timeout. Returns True if timeout exceeded."""
        nonlocal timed_out
        elapsed = time.time() - job_start_time
        if elapsed > JOB_TIMEOUT:
            timed_out = True
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
        "expired_cleaned": 0,
    }

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="OCSP refresh job for BunkerWeb")
    parser.add_argument("--force", action="store_true", help="Force full OCSP refresh and TTL checks managed by the job")
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only process new/changed certificates; skip unchanged TTL checks (for post-renew/issuance hooks)",
    )
    parser.add_argument("--force-fetch", action="store_true", help="Force refetch all OCSP responses from upstream PKI, do not replace existing files on error")
    args, unknown = parser.parse_known_args()
    force_all = args.force
    changed_only = args.changed_only
    force_fetch = args.force_fetch

    try:
        force_flags = ""
        if force_all:
            force_flags += " [FORCE]"
        if changed_only:
            force_flags += " [CHANGED-ONLY]"
        if force_fetch:
            force_flags += " [FORCE-FETCH]"
        run_id = _begin_job_run()
        openssl = _openssl_identity()
        log_info(
            "🔄 OCSP refresh job started with differential update strategy (timeout in %d minutes%s) "
            "job_run_id=%s openssl=%s",
            JOB_TIMEOUT // 60,
            force_flags,
            run_id,
            openssl.get("version") or openssl.get("path") or "unknown",
        )

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
                _log_ocsp_cache_mount_hints()
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

        # Skip the whole job only when no service wants stapling.
        # A global "no" must not wipe caches for sites that override the setting to "yes".
        if not _is_ocsp_enabled_anywhere():
            log_info("🧹 OCSP stapling is disabled for every service, cleaning up all caches")
            cleanup_ocsp_cache(db, purge_db=True)
            return 0

        # Wait for scheduler's directory purge to finish after service restart,
        # then restore cached OCSP responses from database to disk.
        # This handles ephemeral storage and post-restart cache directory cleanup.
        # OCSP files live under tree-sharded dirs (ssl/<hex1>/<hex2>/<fingerprint>/ocsp.der).
        ocsp_files_exist = (
            any(CONFIGS_SSL_BASE.rglob("ocsp.der")) if CONFIGS_SSL_BASE.is_dir() else False
        )
        if not ocsp_files_exist:
            log_info("🔄 OCSP no cached files on disk, waiting 2s for scheduler purge to finish before restoring from database...")
            time.sleep(2)
        restore_ocsp_from_database(db)

        # Cleanup expired/stale OCSP cache entries early (before TTL-skip optimization).
        # This prevents expired OCSP responses from staying on disk/db when the job runs in a
        # "recently refreshed" optimization mode.
        try:
            _cleanup_expired_ocsp_entries(db, stats)
        except Exception as e:
            log_debug("⚠️ OCSP expired cleanup failed: %s", e)

        # === Efficiency optimization: skip full refresh if run recently and no changes detected ===
        last_refresh_key = "last_full_refresh"
        now_ts = int(time.time())
        skip_unchanged_ttl_checks = False

        # Post-renew/issuance hooks use --changed-only so the soft deadline is spent on
        # new/changed leaves, not a whole-fleet unchanged TTL walk.
        if changed_only and not force_all:
            skip_unchanged_ttl_checks = True
            log_info("ℹ️ OCSP --changed-only: processing new/changed certificates only (skipping unchanged TTL checks)")
        elif not force_all:
            last_refresh_entry = db.get_job_cache_file(file_name=last_refresh_key, job_name="ocsp-refresh", with_info=True)
            if last_refresh_entry and last_refresh_entry.get("data") and stats.get("expired_cleaned", 0) == 0:
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

        if not check_job_timeout("before self-signed cert processing"):
            selfsigned_results = process_selfsigned_certs(
                db,
                stats,
                refresh_fn=refresh_job_lock,
                timeout_fn=check_job_timeout,
                force_fetch=force_fetch,
            )
            all_ocsp_results.extend(selfsigned_results)
            for res in selfsigned_results:
                if res[1] is None and res[5] and res[6]:
                    stashed_failures.append((res[0], res[4]))

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
            _persist_ocsp_results_to_disk(all_ocsp_results, stats, db=db)
            _persist_ocsp_results_to_db(db, all_ocsp_results, stats)
            # Still prune orphans on soft timeout: deleted services must not keep growing
            # sharded cache just because the fetch phase ran long.
            try:
                _cleanup_orphaned_ocsp(db, le_certs or {}, stats)
            except Exception as e:
                log_warning("⚠️ OCSP orphaned cleanup after soft timeout failed: %s", e)
            # Return early with partial results saved — non-zero so callers do not treat this as success
            elapsed = time.time() - job_start_time
            log_warning(
                "📊 OCSP partial job completed in %.3fs with %d results saved (orphaned_cleaned=%d)",
                elapsed,
                len(all_ocsp_results),
                stats.get("orphaned_cleaned", 0),
            )
            return 1 if status == 0 else status

        # === Persist: canary-page disk first, then DB mirrors only paged shards ===
        _persist_ocsp_results_to_disk(all_ocsp_results, stats, db=db)
        _persist_ocsp_results_to_db(db, all_ocsp_results, stats)

        # Prune orphans after persist even near the soft deadline — deleted services
        # must not keep sharded cache forever on chronically slow fleets.
        try:
            _cleanup_orphaned_ocsp(db, le_certs or {}, stats)
        except Exception as e:
            log_warning("⚠️ OCSP orphaned cleanup failed: %s", e)

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
        if timed_out and status == 0:
            status = 1
            log_warning("⚠️ OCSP refresh job ended after soft timeout (partial run)")
        if stats["errors"] > 0:
            status = 2

        if stats["errors"] == 0 and not timed_out:
            log_info("✓ OCSP refresh job completed successfully")
            # Check if all certificates are up-to-date (no fetches needed)
            if stats["ocsp_fetched_responses"] == 0 and (stats["le_certs_processed"] + stats["custom_certs_processed"]) > 0:
                log_info("✅ All OCSP responses are current and valid - no updates needed")
        elif stats["errors"] > 0:
            log_warning("⚠️ OCSP refresh job completed with %d error(s)", stats["errors"])
        elif timed_out:
            log_warning("⚠️ OCSP refresh job completed partially due to timeout")

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
