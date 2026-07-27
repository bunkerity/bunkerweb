#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from tempfile import NamedTemporaryFile
from traceback import format_exc
from typing import Tuple, Union, Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore
from reverseproxy_pem import process_pem_data  # type: ignore

LOGGER = getLogger("REVERSE-PROXY.trusted-cert")
JOB = Job(LOGGER, __file__)

CACHE_NAME = "trusted-ca.pem"
CLIENT_CERT_CACHE_NAME = "client-cert.pem"
CLIENT_KEY_CACHE_NAME = "client-key.pem"


def process_ca_data(data: str, file_path: Optional[str], server_name: str) -> Union[bytes, Path, None]:
    """Resolve the trusted CA from a file path or from direct data (base64 or plain PEM)."""
    return process_pem_data(data, file_path, server_name)


def check_pem(
    pem_file: Union[Path, bytes],
    first_server: str,
    *,
    cache_name: str = CACHE_NAME,
    openssl_cmd: str = "x509",
    label: str = "trusted certificate",
) -> Tuple[bool, Union[str, BaseException]]:
    """Validate PEM material with OpenSSL and cache it (disk + DB) for distribution to instances."""
    try:
        if isinstance(pem_file, Path):
            if not pem_file.is_file():
                return False, f"{label.capitalize()} file {pem_file} is not a valid file, ignoring"
            pem_file = pem_file.read_bytes()

        with NamedTemporaryFile(delete=False) as pem_temp:
            try:
                pem_temp.write(pem_file)
                pem_temp.flush()
                result = run(
                    ["openssl", openssl_cmd, "-noout", "-in", pem_temp.name],
                    stdin=DEVNULL,
                    stderr=DEVNULL,
                    check=False,
                    env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
                )
                if result.returncode != 0:
                    return False, f"{label.capitalize()} is invalid."
            finally:
                Path(pem_temp.name).unlink(missing_ok=True)

        pem_hash = bytes_hash(pem_file)
        old_hash = JOB.cache_hash(cache_name, service_id=first_server)
        pem_path = Path(sep, "var", "cache", "bunkerweb", "reverseproxy", first_server, cache_name)
        if old_hash == pem_hash and pem_path.is_file():
            return False, ""

        cached, err = JOB.cache_file(cache_name, pem_file, service_id=first_server, checksum=pem_hash, delete_file=False)
        if not cached:
            LOGGER.error(f"Error while caching {label} for {first_server} : {err}")
            return False, err
        return True, ""
    except BaseException as e:
        return False, e


def check_ca(ca_file: Union[Path, bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """Validate the CA bundle with OpenSSL and cache it for distribution to instances."""
    return check_pem(ca_file, first_server)


def handle_client_material(first_server: str, get) -> Tuple[bool, bool, bool]:
    """Materialize the client certificate and key used for mutual TLS with the upstream.

    Returns ``(need_reload, failed, configured)``. Both halves are required: a certificate
    without its key (or the reverse) is refused rather than half-written, because NGINX needs
    both directives or neither. The pair is cached and distributed like every other job
    artifact, which lands it on the instances with owner/group-only permissions.
    """
    priority = get(first_server, "REVERSE_PROXY_SSL_CLIENT_CERT_PRIORITY", "file")
    pairs = (
        (CLIENT_CERT_CACHE_NAME, "REVERSE_PROXY_SSL_CLIENT_CERT", "certificate", "x509", "client certificate"),
        (CLIENT_KEY_CACHE_NAME, "REVERSE_PROXY_SSL_CLIENT_KEY", "key", "pkey", "client key"),
    )

    configured = [setting for _, setting, _, _, _ in pairs if get(first_server, setting) or get(first_server, f"{setting}_DATA")]
    if not configured:
        return False, False, False
    if len(configured) != len(pairs):
        LOGGER.error(f"Service {first_server} sets only one half of the upstream client certificate pair, ignoring it")
        return False, True, True

    need_reload = False
    for cache_name, setting, kind, openssl_cmd, label in pairs:
        path_value = get(first_server, setting)
        data_value = get(first_server, f"{setting}_DATA")
        use_file = priority == "file" and path_value
        material = process_pem_data(data_value if not use_file else "", path_value if use_file else None, first_server, kind=kind, label=label)
        if not material:
            LOGGER.warning(f"No valid {label} for {first_server}; mutual TLS with the upstream will be disabled for that server")
            return False, True, True

        changed, err = check_pem(material, first_server, cache_name=cache_name, openssl_cmd=openssl_cmd, label=label)
        if isinstance(err, BaseException):
            LOGGER.error(f"Exception while checking {first_server}'s {label}, skipping ... \n{err}")
            return False, True, True
        elif err:
            LOGGER.warning(f"Error while checking {first_server}'s {label} : {err}")
            return False, True, True
        need_reload = need_reload or changed

    if need_reload:
        LOGGER.info(f"Detected change in {first_server}'s upstream client certificate")
    return need_reload, False, True


status = 0

try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    def _get(server: str, key: str, default: str = "") -> str:
        return getenv(f"{server}_{key}", default) if multisite else getenv(key, default)

    skipped_servers = []
    skipped_client_servers = []
    for first_server in all_domains:
        # Mutual TLS towards the upstream is independent of upstream verification, and applies
        # to gRPC services too — they share this one client identity per service.
        if "yes" in (_get(first_server, "USE_REVERSE_PROXY", "no"), _get(first_server, "USE_GRPC", "no")):
            client_reload, client_failed, client_configured = handle_client_material(first_server, _get)
            if client_failed or not client_configured:
                skipped_client_servers.append(first_server)
            if client_failed:
                status = 2
            elif client_reload and status == 0:
                status = 1
        else:
            skipped_client_servers.append(first_server)

        if _get(first_server, "USE_REVERSE_PROXY", "no") != "yes" or _get(first_server, "REVERSE_PROXY_SSL_VERIFY", "no") != "yes":
            skipped_servers.append(first_server)
            continue

        priority = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_PRIORITY", "file")
        ca_path = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE")
        ca_data = _get(first_server, "REVERSE_PROXY_SSL_TRUSTED_CERTIFICATE_DATA")

        # No CA configured: upstream verification falls back to the system CA store, nothing to cache.
        if not ca_path and not ca_data:
            LOGGER.info(f"Service {first_server} verifies the upstream against the system CA store (no trusted certificate set)")
            skipped_servers.append(first_server)
            continue

        use_file = priority == "file" and ca_path
        ca_file = process_ca_data(ca_data if not use_file else "", ca_path if use_file else None, first_server)
        if not ca_file:
            LOGGER.warning(f"No valid trusted certificate for {first_server}; upstream verification will be disabled for that server")
            skipped_servers.append(first_server)
            status = 2
            continue

        LOGGER.info(f"Checking trusted certificate for {first_server} ...")
        need_reload, err = check_ca(ca_file, first_server)
        if isinstance(err, BaseException):
            LOGGER.error(f"Exception while checking {first_server}'s trusted certificate, skipping ... \n{err}")
            skipped_servers.append(first_server)
            status = 2
            continue
        elif err:
            LOGGER.warning(f"Error while checking {first_server}'s trusted certificate : {err}")
            skipped_servers.append(first_server)
            status = 2
            continue
        elif need_reload:
            LOGGER.info(f"Detected change in {first_server}'s trusted certificate")
            status = 1
            continue

        LOGGER.info(f"No change in {first_server}'s trusted certificate")

    for first_server in skipped_servers:
        JOB.del_cache(CACHE_NAME, service_id=first_server)

    # Dropping the pair when it is no longer configured is what turns mutual TLS back off:
    # the templates emit the directives only when both files are present.
    for first_server in skipped_client_servers:
        JOB.del_cache(CLIENT_CERT_CACHE_NAME, service_id=first_server)
        JOB.del_cache(CLIENT_KEY_CACHE_NAME, service_id=first_server)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running trusted-cert.py :\n{e}")

sys_exit(status)
