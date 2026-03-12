#!/usr/bin/env python3

import hashlib
import logging
import os
import shlex
import subprocess
import sys as _sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from typing import Any, List, Optional, Tuple

# Add BunkerWeb Python deps (Job, logger, Database) to path
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

# Base paths
LIVE_BASE = Path(os.sep, "var", "cache", "bunkerweb", "letsencrypt", "etc", "live")
# Use scheduler-managed cache directory (automatically synced from database on restart)
CONFIGS_SSL_BASE = Path(os.sep, "var", "cache", "bunkerweb", "ssl")


def run_cmd(cmd: List[str]) -> Tuple[int, str, str]:
    """
    Run a subprocess command and return (rc, stdout, stderr).
    When LOG is in debug level, the command line is logged.
    """
    LOG.debug("OCSP running command: %s", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        env={"PATH": os.getenv("PATH", ""), "PYTHONPATH": os.getenv("PYTHONPATH", "")},
    )
    return proc.returncode, proc.stdout, proc.stderr


def cert_supports_ocsp(fullchain: Path) -> Optional[str]:
    """
    First function: test if the certificate supports OCSP.
    Returns OCSP responder URL if present, else None.
    """
    LOG.debug("OCSP checking support for certificate %s", fullchain)
    rc, out, err = run_cmd(
        ["openssl", "x509", "-noout", "-ocsp_uri", "-in", fullchain.as_posix()]
    )
    if rc != 0:
        LOG.debug("OCSP openssl -ocsp_uri failed for %s: %s", fullchain, err.strip())
        return None
    url = out.strip()
    if not url:
        LOG.debug("OCSP no responder URL advertised in %s", fullchain)
        return None
    LOG.debug("OCSP found responder URL for %s: %s", fullchain, url)
    return url


def _normalize_dn_line(line: str, prefix: str) -> str:
    """
    Normalize an OpenSSL subject/issuer line like 'issuer= CN = R3, O = Let's Encrypt, C = US'
    so comparison is more robust to spacing.
    """
    line = line.strip()
    if line.lower().startswith(prefix.lower()):
        line = line[len(prefix) :].strip()
    # Remove repeated spaces around '=' and commas
    parts = [part.strip() for part in line.replace(", ", ",").split(",")]
    return ",".join(parts).lower()


def is_cert_issuer(leaf_path: Path, issuer_path: Path) -> bool:
    """
    Verify that issuer_path is the issuer of leaf_path by comparing
    leaf issuer DN with issuer subject DN using openssl x509.
    """
    rc1, issuer_line, err1 = run_cmd(
        ["openssl", "x509", "-noout", "-issuer", "-in", leaf_path.as_posix()]
    )
    if rc1 != 0:
        LOG.debug("OCSP openssl -issuer failed for %s: %s", leaf_path, err1.strip())
        return False

    rc2, subject_line, err2 = run_cmd(
        ["openssl", "x509", "-noout", "-subject", "-in", issuer_path.as_posix()]
    )
    if rc2 != 0:
        LOG.debug("OCSP openssl -subject failed for %s: %s", issuer_path, err2.strip())
        return False

    issuer_dn = _normalize_dn_line(issuer_line, "issuer=")
    subject_dn = _normalize_dn_line(subject_line, "subject=")

    if issuer_dn != subject_dn:
        LOG.debug(
            "OCSP issuer mismatch for leaf %s and candidate %s: issuer_dn=%r subject_dn=%r",
            leaf_path,
            issuer_path,
            issuer_dn,
            subject_dn,
        )
        return False

    LOG.debug("OCSP verified issuer for leaf %s is %s", leaf_path, issuer_path)
    return True


def split_chain(fullchain: Path) -> Tuple[Path, Path]:
    """
    Split fullchain.pem into leaf.pem and issuer.pem temporary files.
    Assumes first cert = leaf, second = issuer.
    """
    LOG.debug("OCSP splitting fullchain %s into leaf and issuer candidates", fullchain)
    text = fullchain.read_text(encoding="utf-8")
    parts = text.strip().split("-----END CERTIFICATE-----")
    cert_blobs = [p for p in parts if "BEGIN CERTIFICATE" in p]
    if len(cert_blobs) < 2:
        raise RuntimeError(f"fullchain {fullchain} does not contain at least two certs")

    # Write the leaf cert (first block) to a temp file
    leaf_pem = cert_blobs[0] + "-----END CERTIFICATE-----\n"
    leaf_fd, leaf_path_str = tempfile.mkstemp(suffix=".pem", prefix="ocsp-leaf-")
    os.close(leaf_fd)
    leaf_path = Path(leaf_path_str)
    leaf_path.write_text(leaf_pem, encoding="utf-8")

    # By default, assume the second cert is the issuer
    issuer_path: Optional[Path] = None

    # Try to find a blob whose subject matches the leaf issuer
    for idx in range(1, len(cert_blobs)):
        pem = cert_blobs[idx] + "-----END CERTIFICATE-----\n"
        tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".pem", prefix="ocsp-issuer-")
        os.close(tmp_fd)
        tmp_path = Path(tmp_path_str)
        tmp_path.write_text(pem, encoding="utf-8")

        try:
            if is_cert_issuer(leaf_path, tmp_path):
                issuer_path = tmp_path
                LOG.debug(
                    "OCSP selected issuer certificate index %d from fullchain %s",
                    idx,
                    fullchain,
                )
                break
        except Exception as e:
            LOG.debug("OCSP error while verifying issuer for %s: %s", fullchain, e)

        # Not the issuer: clean up this temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    # Fallback: if we could not verify, still use the second cert as issuer
    if issuer_path is None:
        pem = cert_blobs[1] + "-----END CERTIFICATE-----\n"
        tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".pem", prefix="ocsp-issuer-")
        os.close(tmp_fd)
        issuer_path = Path(tmp_path_str)
        issuer_path.write_text(pem, encoding="utf-8")
        LOG.warning(
            "Could not verify issuer chain for %s, falling back to second certificate as issuer "
            "(this usually means the chain is non-standard or OpenSSL output could not be parsed cleanly)",
            fullchain,
        )

    return leaf_path, issuer_path


def parse_next_update_ttl(ocsp_text: str) -> int:
    """
    Parse Next Update from openssl ocsp -text output and return TTL in seconds.
    Falls back to 3600s on error.
    """
    next_update_str: Optional[str] = None
    for line in ocsp_text.splitlines():
        line = line.strip()
        if "Next Update:" in line:
            parts = line.split("Next Update:", 1)
            if len(parts) == 2:
                next_update_str = parts[1].strip()
                break

    if not next_update_str:
        LOG.debug("OCSP no Next Update field found in response, falling back to 3600s TTL")
        return 3600

    # Common OpenSSL OCSP time format: "Jan  1 00:00:00 2026 GMT"
    try:
        dt = datetime.strptime(next_update_str, "%b %d %H:%M:%S %Y %Z")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        ttl = int((dt - now).total_seconds())
        if ttl <= 0:
            LOG.debug("OCSP parsed Next Update is in the past, using 300s TTL instead")
            return 300
        # Cap TTL to 7 days to avoid very long-lived cache entries
        return min(ttl, 7 * 24 * 3600)
    except Exception as e:
        LOG.debug("OCSP failed to parse Next Update from response: %s", e)
        return 3600


def fetch_ocsp_response(fullchain: Path, ocsp_url: str, timeout: int = 10) -> Tuple[Optional[bytes], int]:
    """
    Fetch OCSP response using openssl ocsp with a network timeout.
    Returns (raw DER bytes or None, ttl_seconds).
    """
    leaf, issuer = split_chain(fullchain)
    ocsp_der_fd, ocsp_der_path = tempfile.mkstemp(suffix=".der", prefix="ocsp-resp-")
    os.close(ocsp_der_fd)
    ocsp_der = Path(ocsp_der_path)

    try:
        cmd = [
            "openssl",
            "ocsp",
            "-issuer",
            issuer.as_posix(),
            "-cert",
            leaf.as_posix(),
            "-url",
            ocsp_url,
            "-no_nonce",
            "-timeout",
            str(timeout),
            "-respout",
            ocsp_der.as_posix(),
            "-text",
        ]
        rc, out, err = run_cmd(cmd)
        if rc != 0:
            LOG.error("OCSP openssl ocsp failed for %s: rc=%s err=%s", fullchain, rc, err.strip())
            return None, 0

        if not ocsp_der.is_file() or ocsp_der.stat().st_size == 0:
            LOG.error("OCSP no response written for %s (empty respout file)", fullchain)
            return None, 0

        ttl = parse_next_update_ttl(out)
        return ocsp_der.read_bytes(), ttl
    finally:
        try:
            leaf.unlink(missing_ok=True)
            issuer.unlink(missing_ok=True)
            ocsp_der.unlink(missing_ok=True)
        except Exception:
            pass


def extract_san_dns(fullchain: Path) -> List[str]:
    """
    Try to extract DNS names from certificate SAN to use as SNI keys.
    This is best-effort; if it fails, we fall back to the cert directory basename.
    """
    rc, out, err = run_cmd(
        ["openssl", "x509", "-noout", "-text", "-in", fullchain.as_posix()]
    )
    if rc != 0:
        LOG.debug("OCSP openssl -text failed for %s: %s", fullchain, err.strip())
        return []

    names: List[str] = []
    in_san = False
    for line in out.splitlines():
        line = line.strip()
        if "X509v3 Subject Alternative Name" in line:
            in_san = True
            continue
        if in_san:
            if not line.startswith("DNS:") and "DNS:" not in line:
                break
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if part.startswith("DNS:"):
                    dns = part[4:].strip()
                    if dns:
                        names.append(dns)

    return sorted(set(names))


def process_one_cert_dir(job: Job, cert_dir: Path, db: Optional[Any] = None) -> None:
    fullchain = cert_dir / "fullchain.pem"
    if not fullchain.is_file():
        return

    cert_name = cert_dir.name
    LOG.info("OCSP processing certificate directory %s", cert_name)

    ocsp_url = cert_supports_ocsp(fullchain)
    if not ocsp_url:
        LOG.info("OCSP certificate %s has no responder, skipping fetch", cert_name)
        return

    LOG.info("OCSP responder for certificate %s: %s", cert_name, ocsp_url)

    ocsp_der: Optional[bytes] = None
    ttl: int = 0

    # Use a timeout of 10 seconds per attempt, retry once after 10 seconds
    for attempt in (1, 2):
        ocsp_der, ttl = fetch_ocsp_response(fullchain, ocsp_url, timeout=10)
        if ocsp_der:
            LOG.debug("OCSP successfully fetched response for %s on attempt %d (TTL=%ds)", cert_name, attempt, ttl)
            break
        if attempt == 1:
            LOG.warning("OCSP fetch failed for %s, retrying once after 10 seconds ...", cert_name)
            time.sleep(10)

    if not ocsp_der:
        LOG.error("OCSP failed to fetch response for %s after retries", cert_name)
        return

    LOG.debug("OCSP final TTL for %s is %ds (from Next Update parsing)", cert_name, ttl)

    # Calculate checksum for integrity verification
    checksum = hashlib.sha256(ocsp_der).hexdigest()

    # === Store OCSP response in database (new) ===
    if db:
        cache_key = f"ocsp/{cert_name}"
        try:
            # Store in database
            err = db.upsert_job_cache(
                service_id=None,  # Global cache entry
                file_name=cache_key,
                data=ocsp_der,
                job_name="ocsp-refresh",
                checksum=checksum,
            )

            if err:
                LOG.error("OCSP error while storing response for %s in database: %s", cert_name, err)
            else:
                LOG.info("OCSP stored response for %s in database (TTL=%ds, checksum=%s)",
                         cert_name, ttl, checksum[:8])
        except Exception as e:
            LOG.error("OCSP exception while storing response for %s in database: %s", cert_name, e)

    # === Datastore sync would happen via scheduler sync (not needed here) ===
    # The scheduler will sync OCSP responses from database to datastore on workers
    # For now, disk storage is sufficient and always works

    # === Also store on disk as fallback (/etc/bunkerweb/configs/ssl/{cert-name}/ocsp.der) ===
    # Create the SSL configs directory for this certificate
    ocsp_cert_dir = CONFIGS_SSL_BASE / cert_name
    try:
        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        LOG.error("OCSP error while creating directory %s: %s", ocsp_cert_dir, e)
        return

    # Write OCSP response to configs/ssl/{cert-name}/ocsp.der
    ocsp_path = ocsp_cert_dir / "ocsp.der"
    try:
        ocsp_path.write_bytes(ocsp_der)
        ocsp_path.chmod(0o644)  # Readable by nginx
        LOG.info("OCSP saved response for %s to disk at %s", cert_name, ocsp_path)
    except Exception as e:
        LOG.error("OCSP error while writing response for %s to disk: %s", cert_name, e)


def main() -> int:
    global status
    db: Optional[Any] = None
    try:
        # CRITICAL: Log immediately to confirm script is running
        try:
            LOG.error("OCSP DEBUG: script started, initializing Job")
        except Exception as e:
            print(f"ERROR: Could not log initial message: {e}", file=_sys.stderr)

        try:
            job = Job(LOG, __file__)
            LOG.debug("OCSP Job initialized successfully")
        except Exception as e:
            LOG.error("OCSP could not initialize Job: %s", e)
            return 2

        # Initialize database connection (optional)
        if Database is not None:
            try:
                db = Database(LOG)
                LOG.debug("OCSP database connection established")
            except Exception as e:
                LOG.warning("OCSP could not establish database connection, will use disk-only storage: %s", e)
                db = None
        else:
            LOG.debug("OCSP Database module not available, will use disk-only storage")

        if not LIVE_BASE.is_dir():
            LOG.info("OCSP live certificate directory %s does not exist, nothing to do", LIVE_BASE)
            return 0

        cert_dirs = [d for d in sorted(LIVE_BASE.iterdir()) if d.is_dir()]
        LOG.info("OCSP found %d live certificate directories under %s", len(cert_dirs), LIVE_BASE)

        for cert_dir in cert_dirs:
            fullchain = cert_dir / "fullchain.pem"
            if not fullchain.is_file():
                LOG.debug("OCSP skipping %s because fullchain.pem is missing", cert_dir)
                continue
            process_one_cert_dir(job, cert_dir, db)

        return status
    except BaseException as e:
        LOG.exception("OCSP exception in ocsp-refresh.py")
        LOG.error("OCSP exception while running ocsp-refresh.py: %s", e)
        return 2
    finally:
        # Ensure database connection is properly closed
        if db:
            try:
                db.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys_exit(main())

