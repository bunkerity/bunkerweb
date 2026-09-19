#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from traceback import format_exc
from typing import Dict, List, Tuple, Union, Optional

from cryptography import x509

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from certificate_validation import normalize_pem, validate_certificate_pair  # type: ignore
from common_utils import bytes_hash  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

PLUGIN_ID = "reverseproxy"
PREFIX = "REVERSE_PROXY"
USE_SETTING = "USE_REVERSE_PROXY"
DIRECTIVE = "proxy_ssl"

LOGGER = getLogger(f"{PREFIX.replace('_', '-')}.trusted-cert")
JOB = Job(LOGGER, __file__)

CA_NAME = "trusted-ca.pem"
CERT_NAME = "client-cert.pem"
KEY_NAME = "client-key.pem"
CRL_NAME = "crl.pem"
ALL_NAMES = (CA_NAME, CERT_NAME, KEY_NAME, CRL_NAME)


def resolve_material(data: str, file_path: Optional[str], kind: str, server_name: str) -> Union[bytes, Path, None]:
    """Resolve PEM material from a file path or from direct data (base64 or plain PEM)."""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{kind} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        if kind == "crl":
            return normalize_crl(data, server_name)

        pem, error = normalize_pem(data, "key" if kind == "key" else "cert")
        if not pem:
            LOGGER.error(f"{error} for server {server_name} ({kind})")
            return None
        return pem
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {kind} for {server_name}: {e}")
        return None


def normalize_crl(data: str, server_name: str) -> Optional[bytes]:
    """Same PEM-or-base64 contract as normalize_pem, for a revocation list."""
    header = b"-----BEGIN X509 CRL-----"
    text_data = data.encode()
    if text_data.strip().startswith(b"-----BEGIN"):
        if text_data.strip().startswith(header):
            return text_data
        LOGGER.error(f"Invalid CRL format for server {server_name}")
        return None
    try:
        base64_data = "".join(data.split())
        base64_data += "=" * (-len(base64_data) % 4)
        decoded = b64decode(base64_data, validate=True)
        if not decoded.strip().startswith(header):
            raise ValueError("decoded CRL data is not PEM")
        return decoded
    except BaseException:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Invalid CRL format for server {server_name}")
        return None


def read_material(material: Union[Path, bytes], label: str) -> Union[bytes, str]:
    """Return the bytes of a resolved material, or an error string."""
    if isinstance(material, Path):
        if not material.is_file():
            return f"{label} file {material} is not a valid file, ignoring"
        return material.read_bytes()
    return material


def bundle_parses(blob: bytes) -> bool:
    """Every certificate in the bundle must parse, not just the first one."""
    try:
        return bool(x509.load_pem_x509_certificates(blob))
    except Exception:
        LOGGER.debug(format_exc())
        return False


def crl_parses(blob: bytes) -> bool:
    try:
        x509.load_pem_x509_crl(blob)
        return True
    except Exception:
        LOGGER.debug(format_exc())
        return False


def pick_source(priority: str, file_path: str, data: str) -> Tuple[Optional[str], str]:
    """Choose between the path and the inline data, falling back to whichever is actually set."""
    if priority == "file":
        return (file_path, "") if file_path else (None, data)
    return (None, data) if data else (file_path or None, "")


def cache_material(name: str, blob: bytes, first_server: str) -> Tuple[bool, str]:
    """Cache the material for distribution to the instances. Returns (changed, error)."""
    blob_hash = bytes_hash(blob)
    old_hash = JOB.cache_hash(name, service_id=first_server)
    cached_path = Path(sep, "var", "cache", "bunkerweb", PLUGIN_ID, first_server, name)
    if old_hash == blob_hash and cached_path.is_file():
        return False, ""

    cached, err = JOB.cache_file(name, blob, service_id=first_server, checksum=blob_hash, delete_file=False)
    if not cached:
        return False, err or f"Error while caching {name} for {first_server}"
    return True, ""


def handle_ca(first_server: str, get) -> Tuple[Optional[Dict[str, bytes]], str]:
    """Trusted CA bundle, only used when upstream verification is on."""
    if get(f"{PREFIX}_SSL_VERIFY", "no") != "yes":
        return {}, ""

    priority = get(f"{PREFIX}_SSL_TRUSTED_CERTIFICATE_PRIORITY", "file")
    ca_path = get(f"{PREFIX}_SSL_TRUSTED_CERTIFICATE")
    ca_data = get(f"{PREFIX}_SSL_TRUSTED_CERTIFICATE_DATA")
    if not ca_path and not ca_data:
        LOGGER.info(f"No trusted CA configured for {first_server}; upstream verification will be disabled")
        return {}, ""

    path_arg, data_arg = pick_source(priority, ca_path, ca_data)
    material = resolve_material(data_arg, path_arg, "cert", first_server)
    if not material:
        return None, "no valid trusted certificate"

    blob = read_material(material, "Trusted certificate")
    if isinstance(blob, str):
        return None, blob
    if not bundle_parses(blob):
        return None, "trusted certificate is invalid"
    return {CA_NAME: blob}, ""


def handle_client_pair(first_server: str, get) -> Tuple[Optional[Dict[str, bytes]], str]:
    """Client certificate and key presented to the upstream for mutual TLS."""
    priority = get(f"{PREFIX}_SSL_CERT_PRIORITY", "file")
    cert_path = get(f"{PREFIX}_SSL_CERT")
    cert_data = get(f"{PREFIX}_SSL_CERT_DATA")
    key_path = get(f"{PREFIX}_SSL_KEY")
    key_data = get(f"{PREFIX}_SSL_KEY_DATA")

    if not any((cert_path, cert_data, key_path, key_data)):
        return {}, ""
    if not (cert_path or cert_data) or not (key_path or key_data):
        return None, f"{PREFIX}_SSL_CERT(_DATA) and {PREFIX}_SSL_KEY(_DATA) must both be set to use upstream mutual TLS"

    cert_arg, cert_inline = pick_source(priority, cert_path, cert_data)
    key_arg, key_inline = pick_source(priority, key_path, key_data)
    cert_material = resolve_material(cert_inline, cert_arg, "cert", first_server)
    key_material = resolve_material(key_inline, key_arg, "key", first_server)
    if not cert_material or not key_material:
        return None, "no valid client certificate/key pair"

    cert_blob = read_material(cert_material, "Client certificate")
    if isinstance(cert_blob, str):
        return None, cert_blob
    key_blob = read_material(key_material, "Client key")
    if isinstance(key_blob, str):
        return None, key_blob

    # Same in-process pair check the customcert plugin uses, so a mismatched or encrypted key
    # fails here with a reason instead of at NGINX reload.
    check = validate_certificate_pair(cert_blob, key_blob)
    if not check["ok"]:
        return None, check["error"]
    for warning in check["warnings"]:
        LOGGER.warning(f"{first_server}: client certificate {warning}")

    return {CERT_NAME: cert_blob, KEY_NAME: key_blob}, ""


def handle_crl(first_server: str, get) -> Tuple[Optional[Dict[str, bytes]], str]:
    """Revocation list, only meaningful while verifying the upstream."""
    crl_path = get(f"{PREFIX}_SSL_CRL")
    crl_data = get(f"{PREFIX}_SSL_CRL_DATA")
    if not crl_path and not crl_data:
        return {}, ""
    if get(f"{PREFIX}_SSL_VERIFY", "no") != "yes":
        LOGGER.warning(f"{first_server}: {PREFIX}_SSL_CRL is set but {PREFIX}_SSL_VERIFY is no, the CRL will not be applied")
        return {}, ""

    # the CRL has no priority setting of its own: prefer the path when one is given
    material = resolve_material("" if crl_path else crl_data, crl_path or None, "crl", first_server)
    if not material:
        return None, "no valid CRL"

    blob = read_material(material, "CRL")
    if isinstance(blob, str):
        return None, blob
    if not crl_parses(blob):
        return None, "CRL is invalid"
    return {CRL_NAME: blob}, ""


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

    # name -> services that still want it cached, so everything else is purged below
    wanted: Dict[str, List[str]] = {name: [] for name in ALL_NAMES}

    for first_server in all_domains:
        if _get(first_server, USE_SETTING, "no") != "yes":
            continue

        def get(key: str, default: str = "", _server: str = first_server) -> str:
            return _get(_server, key, default)

        materials: Dict[str, bytes] = {}
        for handler, names in ((handle_ca, (CA_NAME,)), (handle_client_pair, (CERT_NAME, KEY_NAME)), (handle_crl, (CRL_NAME,))):
            resolved, err = handler(first_server, get)
            if resolved is None:
                # A transient failure must not purge last-known-good material below: dropping a
                # cached CA silently turns upstream verification off on the next render.
                kept = [name for name in names if JOB.cache_hash(name, service_id=first_server)]
                for name in kept:
                    wanted[name].append(first_server)
                detail = f", keeping the {', '.join(kept)} already cached" if kept else ""
                LOGGER.warning(f"{first_server}: {err}; the matching {DIRECTIVE} directives will not be regenerated{detail}")
                status = 2
                continue
            materials.update(resolved)

        for name, blob in materials.items():
            wanted[name].append(first_server)
            try:
                changed, err = cache_material(name, blob, first_server)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while caching {name} for {first_server}: {e}")
                status = 2
                continue
            if err:
                LOGGER.error(f"Error while caching {name} for {first_server}: {err}")
                status = 2
            elif changed:
                LOGGER.info(f"Detected change in {first_server}'s {name}")
                status = 1 if status != 2 else status
            else:
                LOGGER.info(f"No change in {first_server}'s {name}")

    for name, keep in wanted.items():
        for first_server in all_domains:
            if first_server in keep or not JOB.cache_hash(name, service_id=first_server):
                continue
            # something was cached and is no longer wanted: the instances must reload without it
            deleted, err = JOB.del_cache(name, service_id=first_server)
            if not deleted:
                LOGGER.error(f"Error while removing {first_server}'s {name}: {err}")
                status = 2
            else:
                LOGGER.info(f"Removed {first_server}'s {name}")
                status = 1 if status != 2 else status
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running trusted-cert.py :\n{e}")

sys_exit(status)
