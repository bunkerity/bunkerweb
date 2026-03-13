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
    LOG.debug("🔄 OCSP running command: %s", " ".join(shlex.quote(c) for c in cmd))
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
    LOG.debug("🔒 OCSP checking support for certificate %s", fullchain)
    rc, out, err = run_cmd(
        ["openssl", "x509", "-noout", "-ocsp_uri", "-in", fullchain.as_posix()]
    )
    if rc != 0:
        LOG.debug("🔒 OCSP openssl -ocsp_uri failed for %s: %s", fullchain, err.strip())
        return None
    url = out.strip()
    if not url:
        LOG.debug("🔒 OCSP no responder URL advertised in %s", fullchain)
        return None
    LOG.debug("🌐 OCSP found responder URL for %s: %s", fullchain, url)
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
        LOG.debug("🔒 OCSP openssl -issuer failed for %s: %s", leaf_path, err1.strip())
        return False

    rc2, subject_line, err2 = run_cmd(
        ["openssl", "x509", "-noout", "-subject", "-in", issuer_path.as_posix()]
    )
    if rc2 != 0:
        LOG.debug("🔒 OCSP openssl -subject failed for %s: %s", issuer_path, err2.strip())
        return False

    issuer_dn = _normalize_dn_line(issuer_line, "issuer=")
    subject_dn = _normalize_dn_line(subject_line, "subject=")

    if issuer_dn != subject_dn:
        LOG.debug(
            "🔒 OCSP issuer mismatch for leaf %s and candidate %s: issuer_dn=%r subject_dn=%r",
            leaf_path,
            issuer_path,
            issuer_dn,
            subject_dn,
        )
        return False

    LOG.debug("✓ OCSP verified issuer for leaf %s is %s", leaf_path, issuer_path)
    return True


def split_chain(fullchain: Path) -> Tuple[Path, Path]:
    """
    Split fullchain.pem into leaf.pem and issuer.pem temporary files.
    Assumes first cert = leaf, second = issuer.
    """
    LOG.debug("📜 OCSP splitting fullchain %s into leaf and issuer candidates", fullchain)
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
                    "✓ OCSP selected issuer certificate index %d from fullchain %s",
                    idx,
                    fullchain,
                )
                break
        except Exception as e:
            LOG.debug("🔒 OCSP error while verifying issuer for %s: %s", fullchain, e)

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
    Falls back to 86400s (24 hours, RFC standard) on error.
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
        LOG.debug("⚡ OCSP no Next Update field found in response, falling back to RFC standard 86400s (24 hours) TTL")
        return 86400

    # Common OpenSSL OCSP time format: "Jan  1 00:00:00 2026 GMT"
    try:
        dt = datetime.strptime(next_update_str, "%b %d %H:%M:%S %Y %Z")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        ttl = int((dt - now).total_seconds())
        if ttl <= 0:
            LOG.debug("⚡ OCSP parsed Next Update is in the past, using 300s TTL instead")
            return 300
        # Cap TTL to 7 days to avoid very long-lived cache entries
        return min(ttl, 7 * 24 * 3600)
    except Exception as e:
        LOG.debug("⚡ OCSP failed to parse Next Update from response: %s, falling back to RFC standard 86400s (24 hours)", e)
        return 86400


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
            LOG.error("❌ OCSP openssl ocsp failed for %s: rc=%s err=%s", fullchain, rc, err.strip())
            return None, 0

        if not ocsp_der.is_file() or ocsp_der.stat().st_size == 0:
            LOG.error("❌ OCSP no response written for %s (empty respout file)", fullchain)
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


def get_cached_ocsp_ttl(cert_name: str) -> Optional[int]:
    """
    Check if cached OCSP file exists and return its remaining TTL in seconds.
    Returns None if file doesn't exist or TTL cannot be determined.

    This allows skipping fetch if the cached response is still valid for >3 days.
    """
    ocsp_path = CONFIGS_SSL_BASE / cert_name / "ocsp.der"
    LOG.info("⚡ OCSP TTL check: checking cache for %s at %s", cert_name, ocsp_path)

    if not ocsp_path.is_file():
        LOG.info("⚡ OCSP TTL check: cache miss - file not found for %s", cert_name)
        return None

    LOG.debug("⚡ OCSP cached file found for %s, reading TTL...", cert_name)
    try:
        # Use openssl ocsp -respin to read cached DER and extract Next Update
        # Use -noverify to skip signature verification (we only care about the TTL)
        rc, out, err = run_cmd(
            ["openssl", "ocsp", "-respin", ocsp_path.as_posix(), "-text", "-noverify"]
        )
        if rc != 0:
            LOG.warning("OCSP failed to read cached DER for %s (rc=%d): %s", cert_name, rc, err.strip())
            return None

        ttl = parse_next_update_ttl(out)
        three_days_sec = 259200
        if ttl > three_days_sec:
            LOG.info(
                "✓ OCSP cached response for %s is fresh: TTL=%ds (%.1f days) > 3 days threshold",
                cert_name,
                ttl,
                ttl / 86400.0,
            )
        else:
            LOG.info(
                "🔄 OCSP cached response for %s needs refresh: TTL=%ds (%.1f days) <= 3 days threshold",
                cert_name,
                ttl,
                ttl / 86400.0,
            )
        return ttl
    except Exception as e:
        LOG.warning("⚠️ OCSP exception while reading cached TTL for %s: %s", cert_name, e)
        return None


def validate_cert_file(cert_file: Path, key_file: Path) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Validate cert and key file order. Tries both orderings if the first one fails.
    Accepts certificate chains (fullchain.pem with multiple certs) - OpenSSL reads the first one.
    Returns (valid_cert_path, valid_key_path) or (None, None) if both fail.
    """
    for attempt in (1, 2):
        test_cert = cert_file if attempt == 1 else key_file
        test_key = key_file if attempt == 1 else cert_file

        # Try to read the file as a certificate (openssl x509 reads first cert from chain)
        rc, _, _ = run_cmd(
            ["openssl", "x509", "-noout", "-in", test_cert.as_posix()]
        )

        if rc == 0:
            # File is a valid certificate or certificate chain
            LOG.debug("✓ OCSP validated cert/key ordering: cert=%s, key=%s", test_cert, test_key)
            return test_cert, test_key

    # Both orderings failed
    LOG.warning("❌ OCSP could not find valid certificate in either file ordering")
    return None, None


def extract_ocsp_url_from_cert(cert_file: Path) -> Optional[str]:
    """
    Extract OCSP responder URL from a certificate file.
    Returns the URL if present, None otherwise.
    """
    rc, out, err = run_cmd(
        ["openssl", "x509", "-noout", "-ocsp_uri", "-in", cert_file.as_posix()]
    )
    if rc != 0:
        LOG.debug("🔒 OCSP could not extract OCSP URL from %s: %s", cert_file, err.strip())
        return None
    url = out.strip()
    if not url:
        LOG.debug("🔒 OCSP no responder URL found in %s", cert_file)
        return None
    return url


def process_custom_certs(job: Job, db: Optional[Any] = None, stats: Optional[dict] = None) -> None:
    """
    Process OCSP for custom certificates by auto-discovering from filesystem.
    Scans /var/cache/bunkerweb/customcert/ for existing service directories.
    """
    if stats is None:
        stats = {}

    try:
        customcert_base = Path(os.sep, "var", "cache", "bunkerweb", "customcert")

        # Auto-discover services from filesystem instead of environment variables
        if not customcert_base.is_dir():
            LOG.info("ℹ️ OCSP custom cert directory %s does not exist", customcert_base)
            return

        service_dirs = sorted([d for d in customcert_base.iterdir() if d.is_dir()])
        if not service_dirs:
            LOG.info("ℹ️ OCSP no custom certificate directories found under %s", customcert_base)
            return

        all_domains = [d.name for d in service_dirs]
        LOG.info("🔄 OCSP auto-discovered %d custom certificate service(s) from filesystem", len(all_domains))
        stats["custom_certs_processed"] = len(all_domains)

        for service_name in all_domains:
            # Service directory exists, so custom certs are configured for this service
            # Try to find custom certificate files (main, -ecdsa, or -rsa variants)
            base_dir = Path(os.sep, "var", "cache", "bunkerweb", "customcert", service_name)
            cert_variants = ["cert.pem", "cert-ecdsa.pem", "cert-rsa.pem"]
            key_variants = ["key.pem", "key-ecdsa.pem", "key-rsa.pem"]

            valid_cert = None

            # Try to find valid cert/key pair among all variants
            for cert_variant in cert_variants:
                cert_path = base_dir / cert_variant
                if not cert_path.is_file():
                    continue

                for key_variant in key_variants:
                    key_path = base_dir / key_variant
                    if not key_path.is_file():
                        continue

                    LOG.debug("🔄 OCSP trying custom cert variant: %s / %s", cert_variant, key_variant)
                    valid_cert, _ = validate_cert_file(cert_path, key_path)
                    if valid_cert:
                        LOG.info("✓ OCSP found valid custom certificate for service %s: %s", service_name, valid_cert)
                        break

                if valid_cert:
                    break

            if not valid_cert:
                LOG.debug("ℹ️ OCSP custom cert cache not found for %s in %s", service_name, base_dir)
                stats["custom_certs_skipped"] = stats.get("custom_certs_skipped", 0) + 1
                continue

            LOG.info("🔄 OCSP processing custom certificate for service %s", service_name)

            # Extract OCSP URL from certificate
            ocsp_url = extract_ocsp_url_from_cert(valid_cert)
            if not ocsp_url:
                LOG.info("ℹ️ OCSP custom cert %s has no responder, skipping", service_name)
                stats["custom_certs_no_ocsp"] = stats.get("custom_certs_no_ocsp", 0) + 1
                continue

            LOG.info("🌐 OCSP responder for custom cert %s: %s", service_name, ocsp_url)

            # Use customcert- prefix for OCSP cache key
            cert_name = f"customcert-{service_name}"

            # Check if cached OCSP response is still fresh
            # Skip fetch if cached response still valid for > 50% of its lifetime
            cached_ttl = get_cached_ocsp_ttl(cert_name)
            if cached_ttl is not None:
                refresh_threshold = int(cached_ttl * 0.5)
                if cached_ttl > refresh_threshold:
                    LOG.info(
                        "✓ OCSP cached response for custom cert %s still valid for %ds (%.1f days), refresh at 50%% threshold=%ds, skipping fetch",
                        service_name,
                        cached_ttl,
                        cached_ttl / 86400.0,
                        refresh_threshold,
                    )
                    stats["ocsp_cached_responses"] = stats.get("ocsp_cached_responses", 0) + 1
                    continue

            ocsp_der: Optional[bytes] = None
            ttl: int = 0

            # Use a timeout of 10 seconds per attempt, retry once after 10 seconds
            for attempt in (1, 2):
                ocsp_der, ttl = fetch_ocsp_response(valid_cert, ocsp_url, timeout=10)
                if ocsp_der:
                    LOG.debug("✓ OCSP successfully fetched response for custom cert %s on attempt %d (TTL=%ds)",
                              service_name, attempt, ttl)
                    break
                if attempt == 1:
                    LOG.warning("⚠️ OCSP fetch failed for custom cert %s, retrying once after 10 seconds ...", service_name)
                    time.sleep(10)

            if not ocsp_der:
                LOG.error("❌ OCSP failed to fetch response for custom cert %s after retries", service_name)
                stats["errors"] = stats.get("errors", 0) + 1
                continue

            LOG.debug("⚡ OCSP final TTL for custom cert %s is %ds", service_name, ttl)

            # Calculate checksum for integrity verification
            checksum = hashlib.sha256(ocsp_der).hexdigest()

            # Store OCSP response in database
            db_stored = False
            if db:
                cache_key = f"ocsp/{cert_name}"
                try:
                    err = db.upsert_job_cache(
                        service_id=None,  # Global cache entry
                        file_name=cache_key,
                        data=ocsp_der,
                        job_name="ocsp-refresh",
                        checksum=checksum,
                    )

                    if err:
                        LOG.error("❌ OCSP error storing custom cert %s response in database: %s", service_name, err)
                        stats["errors"] = stats.get("errors", 0) + 1
                    else:
                        LOG.info("✓ OCSP stored custom cert %s response in database (TTL=%ds, checksum=%s)",
                                 service_name, ttl, checksum[:8])
                        db_stored = True
                except Exception as e:
                    LOG.error("❌ OCSP exception storing custom cert %s in database: %s", service_name, e)
                    stats["errors"] = stats.get("errors", 0) + 1
            else:
                db_stored = True

            # Write to disk only after successful database storage
            if not db_stored:
                LOG.warning("⚠️ OCSP skipping disk storage for custom cert %s due to database storage failure", service_name)
                continue

            # Create SSL configs directory for this certificate
            ocsp_cert_dir = CONFIGS_SSL_BASE / cert_name
            try:
                ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                LOG.error("❌ OCSP error creating directory %s: %s", ocsp_cert_dir, e)
                stats["errors"] = stats.get("errors", 0) + 1
                continue

            # Write OCSP response to cache
            ocsp_path = ocsp_cert_dir / "ocsp.der"
            try:
                ocsp_path.write_bytes(ocsp_der)
                ocsp_path.chmod(0o644)  # Readable by nginx
                LOG.info("✓ OCSP saved custom cert %s response to disk at %s", service_name, ocsp_path)
                stats["ocsp_fetched_responses"] = stats.get("ocsp_fetched_responses", 0) + 1
            except Exception as e:
                LOG.error("❌ OCSP error writing custom cert %s response to disk: %s", service_name, e)
                stats["errors"] = stats.get("errors", 0) + 1

    except Exception as e:
        LOG.error("OCSP exception while processing custom certificates: %s", e)
        stats["errors"] = stats.get("errors", 0) + 1


def restore_ocsp_from_database(db: Optional[Any] = None) -> None:
    """
    Restore cached OCSP responses from database to disk.
    Called at startup to ensure disk cache is populated from database.
    This handles ephemeral storage (tmpfs, etc.) by restoring files on each run.
    """
    if not db:
        LOG.debug("ℹ️ OCSP database not available, skipping cache restoration")
        return

    LOG.info("🔄 OCSP restoring cached responses from database to disk...")
    try:
        restored_count = 0

        # Get all possible cert names from live directory and restore from database
        if LIVE_BASE.is_dir():
            for cert_dir in sorted(LIVE_BASE.iterdir()):
                if not cert_dir.is_dir():
                    continue
                cert_name = cert_dir.name
                cache_key = f"ocsp/{cert_name}"

                try:
                    # Use the Database.get_job_cache_file() method to retrieve cached OCSP response
                    # Returns bytes directly if found, None if not found
                    data = db.get_job_cache_file(
                        job_name="ocsp-refresh",
                        file_name=cache_key,
                        with_data=True,
                        with_info=False,
                    )

                    if not data:
                        continue

                    # Restore to disk
                    ocsp_cert_dir = CONFIGS_SSL_BASE / cert_name
                    ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                    ocsp_path = ocsp_cert_dir / "ocsp.der"
                    ocsp_path.write_bytes(data)
                    ocsp_path.chmod(0o644)
                    restored_count += 1
                    LOG.debug("✓ OCSP restored cached response for %s from database", cert_name)
                except Exception as e:
                    LOG.debug("⚠️ OCSP could not restore cache for %s: %s", cert_name, e)
                    continue

        # Also restore custom certificate OCSP responses (using filesystem auto-discovery)
        try:
            customcert_base = Path(os.sep, "var", "cache", "bunkerweb", "customcert")
            if customcert_base.is_dir():
                service_dirs = sorted([d for d in customcert_base.iterdir() if d.is_dir()])
                for service_dir in service_dirs:
                    service_name = service_dir.name
                    cache_key = f"ocsp/customcert-{service_name}"
                    try:
                        data = db.get_job_cache_file(
                            job_name="ocsp-refresh",
                            file_name=cache_key,
                            with_data=True,
                            with_info=False,
                        )
                        if not data:
                            continue
                        ocsp_cert_dir = CONFIGS_SSL_BASE / f"customcert-{service_name}"
                        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
                        ocsp_path = ocsp_cert_dir / "ocsp.der"
                        ocsp_path.write_bytes(data)
                        ocsp_path.chmod(0o644)
                        restored_count += 1
                        LOG.debug("✓ OCSP restored cached custom cert %s from database", service_name)
                    except Exception as e:
                        LOG.debug("⚠️ OCSP could not restore custom cert cache for %s: %s", service_name, e)
                        continue
        except Exception as e:
            LOG.debug("⚠️ OCSP exception while restoring custom cert cache: %s", e)

        if restored_count > 0:
            LOG.info("✓ OCSP restored %d cached responses from database to disk", restored_count)
        else:
            LOG.debug("ℹ️ OCSP no cached responses restored from database (cache may be cold)")
    except Exception as e:
        LOG.debug("OCSP exception while attempting cache restoration: %s", e)


def process_one_cert_dir(job: Job, cert_dir: Path, db: Optional[Any] = None, stats: Optional[dict] = None) -> None:
    if stats is None:
        stats = {}
    fullchain = cert_dir / "fullchain.pem"
    if not fullchain.is_file():
        return

    cert_name = cert_dir.name
    LOG.info("🔄 OCSP processing certificate directory %s", cert_name)

    ocsp_url = cert_supports_ocsp(fullchain)
    if not ocsp_url:
        LOG.info("ℹ️ OCSP certificate %s has no responder, skipping fetch", cert_name)
        stats["le_certs_no_ocsp"] = stats.get("le_certs_no_ocsp", 0) + 1
        return

    LOG.info("🌐 OCSP responder for certificate %s: %s", cert_name, ocsp_url)

    # === Check if cached OCSP response is still fresh ===
    # TTL-based optimization: skip fetch if cached response still valid for > 50% of its lifetime
    cached_ttl = get_cached_ocsp_ttl(cert_name)
    if cached_ttl is not None:
        refresh_threshold = int(cached_ttl * 0.5)
        if cached_ttl > refresh_threshold:
            LOG.info(
                "✓ OCSP cached response for %s still valid for %ds (%.1f days), refresh at 50%% threshold=%ds, skipping fetch",
                cert_name,
                cached_ttl,
                cached_ttl / 86400.0,
                refresh_threshold,
            )
            stats["ocsp_cached_responses"] = stats.get("ocsp_cached_responses", 0) + 1
            return

    ocsp_der: Optional[bytes] = None
    ttl: int = 0

    # Use a timeout of 10 seconds per attempt, retry once after 10 seconds
    for attempt in (1, 2):
        ocsp_der, ttl = fetch_ocsp_response(fullchain, ocsp_url, timeout=10)
        if ocsp_der:
            LOG.debug("✓ OCSP successfully fetched response for %s on attempt %d (TTL=%ds)", cert_name, attempt, ttl)
            break
        if attempt == 1:
            LOG.warning("⚠️ OCSP fetch failed for %s, retrying once after 10 seconds ...", cert_name)
            time.sleep(10)

    if not ocsp_der:
        LOG.error("❌ OCSP failed to fetch response for %s after retries", cert_name)
        stats["errors"] = stats.get("errors", 0) + 1
        return

    LOG.debug("⚡ OCSP final TTL for %s is %ds (from Next Update parsing)", cert_name, ttl)

    # Calculate checksum for integrity verification
    checksum = hashlib.sha256(ocsp_der).hexdigest()

    # === Store OCSP response in database ===
    db_stored = False
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
                LOG.error("❌ OCSP error while storing response for %s in database: %s", cert_name, err)
                stats["errors"] = stats.get("errors", 0) + 1
            else:
                LOG.info("✓ OCSP stored response for %s in database (TTL=%ds, checksum=%s)",
                         cert_name, ttl, checksum[:8])
                db_stored = True
        except Exception as e:
            LOG.error("❌ OCSP exception while storing response for %s in database: %s", cert_name, e)
            stats["errors"] = stats.get("errors", 0) + 1
    else:
        # If no database available, still proceed with disk storage
        db_stored = True

    # === Only write to disk AFTER successful database storage ===
    # This prevents overwriting existing OCSP files if the fetch failed or had issues
    if not db_stored:
        LOG.warning("⚠️ OCSP skipping disk storage for %s due to database storage failure", cert_name)
        return

    # Create the SSL configs directory for this certificate
    ocsp_cert_dir = CONFIGS_SSL_BASE / cert_name
    try:
        ocsp_cert_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        LOG.error("❌ OCSP error while creating directory %s: %s", ocsp_cert_dir, e)
        stats["errors"] = stats.get("errors", 0) + 1
        return

    # Write OCSP response to cache/ssl/{cert-name}/ocsp.der
    ocsp_path = ocsp_cert_dir / "ocsp.der"
    try:
        ocsp_path.write_bytes(ocsp_der)
        ocsp_path.chmod(0o644)  # Readable by nginx
        LOG.info("✓ OCSP saved response for %s to disk at %s", cert_name, ocsp_path)
        stats["ocsp_fetched_responses"] = stats.get("ocsp_fetched_responses", 0) + 1
    except Exception as e:
        LOG.error("❌ OCSP error while writing response for %s to disk: %s", cert_name, e)
        stats["errors"] = stats.get("errors", 0) + 1


def main() -> int:
    global status
    db: Optional[Any] = None

    # Statistics tracking
    stats = {
        "le_certs_processed": 0,
        "le_certs_skipped": 0,
        "le_certs_no_ocsp": 0,
        "custom_certs_processed": 0,
        "custom_certs_skipped": 0,
        "custom_certs_no_ocsp": 0,
        "ocsp_cached_responses": 0,
        "ocsp_fetched_responses": 0,
        "errors": 0,
    }

    try:
        # CRITICAL: Log immediately to confirm script is running
        try:
            LOG.error("🔄 OCSP DEBUG: script started, initializing Job")
        except Exception as e:
            print(f"ERROR: Could not log initial message: {e}", file=_sys.stderr)

        try:
            job = Job(LOG, __file__)
            LOG.debug("✓ OCSP Job initialized successfully")
        except Exception as e:
            LOG.error("❌ OCSP could not initialize Job: %s", e)
            return 2

        # Initialize database connection (optional)
        if Database is not None:
            try:
                db = Database(LOG)
                LOG.debug("✓ OCSP database connection established")
            except Exception as e:
                LOG.warning("⚠️ OCSP could not establish database connection, will use disk-only storage: %s", e)
                db = None
        else:
            LOG.debug("ℹ️ OCSP Database module not available, will use disk-only storage")

        if not LIVE_BASE.is_dir():
            LOG.info("ℹ️ OCSP live certificate directory %s does not exist, nothing to do", LIVE_BASE)
            return 0

        # Restore cached OCSP responses from database (handles ephemeral storage)
        restore_ocsp_from_database(db)

        cert_dirs = [d for d in sorted(LIVE_BASE.iterdir()) if d.is_dir()]
        LOG.info("ℹ️ OCSP found %d live certificate directories under %s", len(cert_dirs), LIVE_BASE)
        stats["le_certs_processed"] = len(cert_dirs)

        for cert_dir in cert_dirs:
            fullchain = cert_dir / "fullchain.pem"
            if not fullchain.is_file():
                LOG.debug("OCSP skipping %s because fullchain.pem is missing", cert_dir)
                stats["le_certs_skipped"] += 1
                continue
            process_one_cert_dir(job, cert_dir, db, stats)

        # Process custom certificates
        process_custom_certs(job, db, stats)

        # Summary message with statistics
        LOG.info("✓ OCSP refresh job completed successfully")
        LOG.info(
            "📊 Statistics: 🔐 LE certs=%d (skipped=%d, no OCSP=%d) | 🔐 Custom certs=%d (no OCSP=%d) | 🔄 Fetched=%d | ✓ Cached=%d | ❌ Errors=%d",
            stats["le_certs_processed"],
            stats["le_certs_skipped"],
            stats["le_certs_no_ocsp"],
            stats["custom_certs_processed"],
            stats["custom_certs_no_ocsp"],
            stats["ocsp_fetched_responses"],
            stats["ocsp_cached_responses"],
            stats["errors"],
        )
        return status
    except BaseException as e:
        LOG.exception("❌ OCSP exception in ocsp-refresh.py")
        LOG.error("❌ OCSP exception while running ocsp-refresh.py: %s", e)
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

