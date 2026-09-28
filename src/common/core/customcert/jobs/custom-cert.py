#!/usr/bin/env python3
"""
Custom SSL certificate job — validate, cache, and kick OCSP refresh on change.

REVIEWER MAP
============
Caches operator-supplied cert/key pairs under
``/var/cache/bunkerweb/customcert/{service}/cert.pem|key.pem`` for the
``customcert`` Lua plugin (``ssl_certificate`` phase). When a pair changes
**and** OCSP stapling is enabled for that service, this job runs
``ocsp-refresh.py --changed-only`` so Must-Staple / staple shards track the
new leaf without waiting for the next scheduled OCSP tick.

Companions:
  customcert.lua                 — serves cached PEM; status[5] = SPKI fp hint
  ssl/jobs/ocsp-refresh.py       — fetch/canary/page OCSP for changed leaves
  certificate_validation         — shared with UI (normalize_pem / validate pair)

Exit status (scheduler convention):
  0 — no change / nothing to do
  1 — at least one cert/key was rewritten (reload signal)
  2 — validation / cache error for one or more services

OCSP post-change refresh is best-effort (timeout / failure → warning only);
a failed kick does not flip status to 2 — the next scheduled ocsp-refresh
still runs. Parent wait is OCSP_REFRESH_TIMEOUT (35m); the child soft-stops
earlier at JOB_TIMEOUT_SECONDS≈2040s inside ocsp-refresh.
"""

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, TimeoutExpired, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple, Union, Optional, Literal

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from certificate_validation import normalize_pem, validate_certificate_pair  # type: ignore
from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("CUSTOM-CERT")
JOB = Job(LOGGER, __file__)
# Parent wait for post-change OCSP kick. Child soft-stops at JOB_TIMEOUT_SECONDS≈2040s
# inside ocsp-refresh; keep this slightly above that so the child can exit cleanly.
OCSP_REFRESH_TIMEOUT = 2100  # 35m


def _ocsp_stapling_enabled_for(service_name: str) -> bool:
    """
    True when this service (or global fallback) has ``SSL_USE_OCSP_STAPLING=yes``.

    Multisite: ``{service}_SSL_USE_OCSP_STAPLING`` wins when set; otherwise the
    global value. Used only to decide whether a cert change should kick
    ``ocsp-refresh.py --changed-only`` — not whether custom SSL itself is on.
    """
    if getenv("MULTISITE", "no").lower() == "yes" and service_name:
        site_value = getenv(f"{service_name}_SSL_USE_OCSP_STAPLING")
        if site_value is not None:
            return site_value.lower() == "yes"
    return getenv("SSL_USE_OCSP_STAPLING", "no").lower() == "yes"


def process_ssl_data(data: str, file_path: Optional[str], data_type: Literal["cert", "key"], server_name: str) -> Union[bytes, Path, None]:
    """
    Resolve a cert or key from a filesystem path or inline data (PEM / base64).

    ``CUSTOM_SSL_CERT_PRIORITY=file`` prefers path over data. Inline values go
    through ``normalize_pem`` (same rules as the UI) so a pair accepted in the
    UI is accepted here. Returns a ``Path``, PEM ``bytes``, or ``None`` on error.
    """
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{data_type.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # Shared with the UI so a value accepted on one side is accepted on the other.
        pem, error = normalize_pem(data, data_type)
        if not pem:
            LOGGER.error(f"{error} for server {server_name}")
            return None
        return pem
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {data_type} for {server_name}: {e}")
        return None


def check_cert(cert_file: Union[Path, bytes], key_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """
    Validate the cert/key pair and cache under ``customcert/{service}/`` if changed.

    Returns ``(need_reload, err)``:
      * ``(True, "")``  — cert and/or key bytes differ from cache (or cache missing)
      * ``(False, "")`` — unchanged on disk
      * ``(False, msg|exc)`` — invalid pair / I/O; caller skips and may set status 2

    Validates in-process (certificate + key match). Expiry is a warning only —
    withdrawing a live cert would fall back to the default server cert, which
    is worse than serving expired material until the operator replaces it.
    """
    try:
        ret = False
        if not cert_file or not key_file:
            return False, "Both variables CUSTOM_SSL_CERT and CUSTOM_SSL_KEY have to be set to use custom certificates"

        if isinstance(cert_file, Path):
            if not cert_file.is_file():
                return False, f"Certificate file {cert_file} is not a valid file, ignoring the custom certificate"
            cert_file = cert_file.read_bytes()

        if isinstance(key_file, Path):
            if not key_file.is_file():
                return False, f"Key file {key_file} is not a valid file, ignoring the custom certificate"
            key_file = key_file.read_bytes()

        # Validate the pair in-process: the previous check only parsed the certificate and
        # never looked at the key at all, so a malformed, encrypted or mismatched key was
        # cached, shipped, and only failed later in Lua, where the service silently falls
        # back to the default certificate.
        check = validate_certificate_pair(cert_file, key_file)
        if not check["ok"]:
            return False, check["error"]

        # Expiry never blocks: withdrawing a certificate that is currently being served
        # would drop the service to the default one, which is worse than serving expired.
        for warning in check["warnings"]:
            LOGGER.warning(f"{first_server}: {warning}")

        cert_hash = bytes_hash(cert_file)
        old_hash = JOB.cache_hash("cert.pem", service_id=first_server)
        cert_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "cert.pem")
        if old_hash != cert_hash or not cert_path.is_file():
            ret = True
            cached, err = JOB.cache_file("cert.pem", cert_file, service_id=first_server, checksum=cert_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-cert cert.pem file : {err}")
                return False, err

        key_hash = bytes_hash(key_file)
        old_hash = JOB.cache_hash("key.pem", service_id=first_server)
        key_path = Path(sep, "var", "cache", "bunkerweb", "customcert", first_server, "key.pem")
        if old_hash != key_hash or not key_path.is_file():
            ret = True
            cached, err = JOB.cache_file("key.pem", key_file, service_id=first_server, checksum=key_hash, delete_file=False)
            if not cached:
                LOGGER.error(f"Error while caching custom-key key.pem file : {err}")
                return False, err

        return ret, ""
    except BaseException as e:
        return False, e


status = 0

try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    skipped_servers = []
    changed_domains = []  # Track which domains had certificate changes
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

            # Use file or data based on priority (file wins when path set + priority=file).
            use_cert_file = cert_priority == "file" and cert_file_path
            use_key_file = cert_priority == "file" and key_file_path

            cert_file = process_ssl_data(cert_data if not use_cert_file else "", cert_file_path if use_cert_file else None, "cert", first_server)

            key_file = process_ssl_data(key_data if not use_key_file else "", key_file_path if use_key_file else None, "key", first_server)

            if not cert_file or not key_file:
                LOGGER.warning(
                    "Variables (CUSTOM_SSL_CERT or CUSTOM_SSL_CERT_DATA) and (CUSTOM_SSL_KEY or CUSTOM_SSL_KEY_DATA) "
                    f"have to be set and valid to use custom certificates for {first_server}"
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
                changed_domains.append(first_server)  # Track this domain as changed
                status = 1
                continue

            LOGGER.info(f"No change in {first_server}'s certificate")

    # Services that turned custom SSL off (or failed validation) must not keep stale PEM.
    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)

    # After caching: same-key renew / new leaf must get a fresh OCSP page before
    # handshake Must-Staple can succeed. --changed-only diffs against the job's
    # known cert set (not a full fleet scan). Non-fatal on timeout/failure.
    if changed_domains and any(_ocsp_stapling_enabled_for(server) for server in changed_domains):
        LOGGER.info(f"🔄 OCSP triggering refresh for {len(changed_domains)} changed custom cert(s): {', '.join(changed_domains)}")
        try:
            import sys

            ocsp_script = join(sep, "usr", "share", "bunkerweb", "core", "ssl", "jobs", "ocsp-refresh.py")
            result = run([sys.executable, ocsp_script, "--changed-only"], stdin=DEVNULL, capture_output=True, text=True, timeout=OCSP_REFRESH_TIMEOUT)
            if result.returncode == 0:
                LOGGER.info("✓ OCSP refresh completed successfully after cert change")
            else:
                LOGGER.warning(f"⚠️ OCSP refresh returned exit code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    LOGGER.debug(f"OCSP: {line}")
        except TimeoutExpired as e:
            LOGGER.warning(
                f"⚠️ OCSP post-change refresh timed out after {OCSP_REFRESH_TIMEOUT}s (non-fatal): {e}"
            )
        except Exception as e:
            LOGGER.warning(f"⚠️ OCSP post-change refresh failed (non-fatal): {e}")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running custom-cert.py :\n{e}")

sys_exit(status)
