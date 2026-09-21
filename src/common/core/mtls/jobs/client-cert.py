#!/usr/bin/env python3

from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, PIPE, run
from sys import exit as sys_exit, path as sys_path
from base64 import b64decode
from tempfile import NamedTemporaryFile
from traceback import format_exc
from typing import Tuple, Union, Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import bytes_hash  # type: ignore
from cache_restore import StagedDirectory, checked_cache_path, recover_directory  # type: ignore
from jobs import Job  # type: ignore
from logger import getLogger  # type: ignore

LOGGER = getLogger("MTLS.client-cert")
JOB = Job(LOGGER, __file__)

CA_CACHE_NAME = "ca.pem"
CRL_CACHE_NAME = "crl.pem"


def process_pem_data(data: str, file_path: Optional[str], kind: str, server_name: str) -> Union[bytes, Path, None]:
    """Resolve a client CA bundle or CRL from a file path or from direct data (base64 or plain PEM)."""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{kind} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        marker = b"-----BEGIN X509 CRL-----" if kind == "CRL" else b"-----BEGIN CERTIFICATE-----"

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if not text_data.strip().startswith(marker):
                LOGGER.error(f"Invalid {kind} format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode (strip whitespace, pad if needed).
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if not decoded.strip().startswith(marker):
                raise ValueError(f"decoded {kind} data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {kind} data as base64 for server {server_name}, trying as plain text")
            if not text_data.strip().startswith(marker):
                LOGGER.error(f"Invalid {kind} format for server {server_name}")
                return None
            return text_data
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {kind} for {server_name}: {e}")
        return None


def bundle_subjects(ca_temp_name: str, command_env: dict) -> Optional[dict]:
    """Load every certificate of the bundle and return the PEMs indexed by subject DN, or None if any of them fails."""
    # `openssl x509 -in` stops at the first PEM block, so a malformed second entry used to reach
    # NGINX and break SSL_CTX_load_verify_locations on every instance.
    loaded = run(["openssl", "crl2pkcs7", "-nocrl", "-certfile", ca_temp_name], stdin=DEVNULL, stdout=PIPE, stderr=DEVNULL, check=False, env=command_env)
    if loaded.returncode != 0:
        return None
    printed = run(["openssl", "pkcs7", "-print_certs"], input=loaded.stdout, stdout=PIPE, stderr=DEVNULL, check=False, env=command_env)
    if printed.returncode != 0:
        return None
    # One DN can carry several certificates (a CA key rollover or a cross-signed root keeps both
    # during the overlap), so keep every PEM rather than the DN alone.
    subjects, subject, pem = {}, None, None
    for line in printed.stdout.splitlines():
        if line.startswith(b"subject="):
            subject = line.removeprefix(b"subject=").strip()
        elif line == b"-----BEGIN CERTIFICATE-----":
            pem = [line]
        elif pem is not None:
            pem.append(line)
            if line == b"-----END CERTIFICATE-----":
                subjects.setdefault(subject, []).append(b"\n".join(pem) + b"\n")
                pem = None
    return subjects or None


def validate_pair(ca_file: bytes, crl_file: Optional[bytes], server_name: str) -> Union[str, BaseException]:
    """Validate the complete candidate CA/CRL pair before either cached file is replaced."""
    try:
        command_env = {"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")}
        with NamedTemporaryFile() as ca_temp:
            ca_temp.write(ca_file)
            ca_temp.flush()
            subjects = bundle_subjects(ca_temp.name, command_env)
            if subjects is None:
                return "Client CA bundle is invalid."
            if crl_file is not None:
                # OpenSSL's crl command reads one PEM object. Verify every CRL in a bundle,
                # otherwise an invalid second issuer can reach NGINX unchecked.
                end_marker = b"-----END X509 CRL-----"
                blocks = crl_file.split(end_marker)
                if len(blocks) < 2 or blocks[-1].strip():
                    return "CRL bundle is invalid."
                for block in blocks[:-1]:
                    with NamedTemporaryFile() as crl_temp:
                        crl_temp.write(block + end_marker + b"\n")
                        crl_temp.flush()
                        issuer = run(
                            ["openssl", "crl", "-noout", "-issuer", "-in", crl_temp.name],
                            stdin=DEVNULL,
                            stdout=PIPE,
                            stderr=DEVNULL,
                            check=False,
                            env=command_env,
                        )
                        if issuer.returncode != 0:
                            return "CRL is invalid."
                        issuer_dn = issuer.stdout.strip().removeprefix(b"issuer=").strip()
                        if issuer_dn not in subjects:
                            # NGINX checks the leaf only and builds the chain from the intermediates the
                            # peer sends, so a CRL issued by a CA outside the bundle is a valid setup.
                            LOGGER.warning(
                                f"CRL issuer {issuer_dn.decode(errors='replace')} is not part of {server_name}'s client CA bundle; "
                                "publishing it unverified (NGINX validates the chain with the intermediates the client presents)"
                            )
                            continue
                        # `openssl crl -verify` only tries the first store entry whose subject matches the
                        # issuer, so with two same-DN certificates the verdict would depend on the bundle
                        # order. Give every candidate its own single-certificate CAfile.
                        # Require OpenSSL's positive signature result as well as successful parsing.
                        for candidate in dict.fromkeys(subjects[issuer_dn]):
                            with NamedTemporaryFile() as signer_temp:
                                signer_temp.write(candidate)
                                signer_temp.flush()
                                result = run(
                                    ["openssl", "crl", "-noout", "-verify", "-CAfile", signer_temp.name, "-no-CApath", "-in", crl_temp.name],
                                    stdin=DEVNULL,
                                    stdout=DEVNULL,
                                    stderr=PIPE,
                                    check=False,
                                    env=command_env,
                                )
                                if result.returncode == 0 and b"verify OK" in result.stderr.splitlines():
                                    break
                        else:
                            return "CRL signature does not match the configured client CA bundle, or the CRL is invalid."
        return ""
    except BaseException as e:
        return e


def publish_pair(ca_file: Optional[bytes], crl_file: Optional[bytes], first_server: str) -> Tuple[bool, Union[str, BaseException]]:
    """Publish both validated files, or deliberate removals, as one disk/DB generation."""
    committed = False
    try:
        if not JOB.restore_ok:
            return False, "Initial mTLS cache restore failed; refusing to replace the retained cache generation"
        service_path = checked_cache_path(Path(sep, "var", "cache", "bunkerweb", "mtls"), first_server)
        recover_directory(service_path)
        files = ((CA_CACHE_NAME, ca_file), (CRL_CACHE_NAME, crl_file))
        for name, data in files:
            path = service_path.joinpath(name)
            if path.is_symlink():
                break
            cached = JOB.db.get_job_cache_file(JOB.job_name, name, service_id=first_server, plugin_id="mtls", with_info=True, with_data=True)
            if data is None:
                if cached is not None or path.exists():
                    break
            elif (
                not isinstance(cached, dict)
                or cached.get("data") != data
                or cached.get("checksum") != bytes_hash(data)
                or not path.is_file()
                or path.read_bytes() != data
            ):
                break
        else:
            # Disk alone is not persistence proof after a crash or loss of database rows.
            return False, ""

        with StagedDirectory(service_path) as staged:
            entries, deletions = [], []
            for name, data in files:
                entry = {"job_name": JOB.job_name, "service_id": first_server, "file_name": name}
                if data is None:
                    deletions.append(entry)
                else:
                    staged.path.joinpath(name).write_bytes(data)
                    entries.append(entry | {"data": data, "checksum": bytes_hash(data)})
            staged.publish()
            err = JOB.db.upsert_job_caches(entries, deletions=deletions)
            if err:
                raise RuntimeError(err)
            committed = True
            staged.commit()
        return True, ""
    except BaseException as e:
        # Cleanup after the DB commit must not suppress a required reload or restore the old pair.
        return committed, e


changed = False
failed = False


try:
    all_domains = getenv("SERVER_NAME", "www.example.com") or []
    multisite = getenv("MULTISITE", "no") == "yes"

    if isinstance(all_domains, str):
        all_domains = all_domains.split()

    # An empty SERVER_NAME is the documented autoconf/Kubernetes value: with no service list there
    # is nothing to compare the cache against, and purging it would drop every mTLS service to the
    # placeholder CA until the next successful daily run.
    if not all_domains:
        LOGGER.info("No services found, exiting ...")
        sys_exit(0)

    def _get(server: str, key: str, default: str = "") -> str:
        return getenv(f"{server}_{key}", default) if multisite else getenv(key, default)

    # Only an operator decision (mTLS turned off, or the CA setting removed) purges the cached
    # bundle. A configured but unusable CA keeps the last known-good cache so instances stay on a
    # real trust anchor instead of one nothing can be validated against.
    cache_root = Path(sep, "var", "cache", "bunkerweb", "mtls")
    # Without SERVER_NAME in the environment the list above is only the single-site default, which is
    # not an authoritative inventory: leave the other services' cached material alone.
    purge_servers = (
        {
            path.name
            for path in cache_root.iterdir()
            if path.is_dir() and not path.is_symlink() and not path.name.startswith(".") and path.name not in all_domains
        }
        if cache_root.is_dir() and getenv("SERVER_NAME") is not None
        else set()
    )
    for first_server in all_domains:
        if _get(first_server, "USE_MTLS", "no") != "yes":
            purge_servers.add(first_server)
            continue

        verify_mode = _get(first_server, "MTLS_VERIFY_CLIENT", "on")
        # With nothing cached there is no last-good bundle to fall back on, so a failure here must
        # not be reported as continuity: `on` and `optional` drop to the placeholder and
        # `optional_no_ca` gets no CA at all, and no client certificate can be validated either way.
        fallback = (
            "keeping the previously distributed CA/CRL state"
            if Path(sep, "var", "cache", "bunkerweb", "mtls", first_server, CA_CACHE_NAME).is_file()
            else "no bundle is currently distributed, so no client certificate can be validated"
        )
        ca_priority = _get(first_server, "MTLS_CA_CERTIFICATE_PRIORITY", "file")
        ca_path = _get(first_server, "MTLS_CA_CERTIFICATE")
        ca_data = _get(first_server, "MTLS_CA_CERTIFICATE_DATA")

        if not ca_path and not ca_data:
            if verify_mode != "optional_no_ca":
                failed = True
                LOGGER.error(
                    f"No client CA bundle configured for {first_server}; no client certificate can be validated "
                    "until one is configured and distributed "
                    "(set MTLS_CA_CERTIFICATE or MTLS_CA_CERTIFICATE_DATA)"
                )
            else:
                LOGGER.info(f"Service {first_server} runs mTLS with optional_no_ca and no client CA bundle configured")
            purge_servers.add(first_server)
            continue

        use_file = ca_priority == "file" and ca_path
        ca_file = process_pem_data(ca_data if not use_file else "", ca_path if use_file else None, "CA", first_server)
        if not ca_file:
            LOGGER.error(f"No valid client CA bundle for {first_server}; {fallback}")
            failed = True
            continue

        crl_priority = _get(first_server, "MTLS_CRL_PRIORITY", "file")
        crl_path = _get(first_server, "MTLS_CRL")
        crl_data = _get(first_server, "MTLS_CRL_DATA")

        crl_file = None
        if crl_path or crl_data:
            use_file = crl_priority == "file" and crl_path
            crl_file = process_pem_data(crl_data if not use_file else "", crl_path if use_file else None, "CRL", first_server)
            if not crl_file:
                LOGGER.error(f"No valid CRL for {first_server}; {fallback}")
                failed = True
                continue

        try:
            ca_file = ca_file.read_bytes() if isinstance(ca_file, Path) else ca_file
            crl_file = crl_file.read_bytes() if isinstance(crl_file, Path) else crl_file
        except OSError as e:
            LOGGER.error(f"Could not read client CA bundle or CRL for {first_server}: {e}; {fallback}")
            failed = True
            continue

        err = validate_pair(ca_file, crl_file, first_server)
        if err:
            LOGGER.error(f"Error while checking {first_server}'s client CA bundle and CRL: {err}; {fallback}")
            failed = True
            continue

        need_reload, err = publish_pair(ca_file, crl_file, first_server)
        changed = changed or need_reload
        if err:
            LOGGER.error(f"Error while publishing client CA/CRL pair for {first_server}: {err}")
            failed = True

    for first_server in sorted(purge_servers):
        need_reload, err = publish_pair(None, None, first_server)
        changed = changed or need_reload
        if err:
            LOGGER.error(f"Error while removing client CA/CRL pair for {first_server}: {err}")
            failed = True

    status = 1 if changed else (2 if failed else 0)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 1 if changed else 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running client-cert.py :\n{e}")

sys_exit(status)
