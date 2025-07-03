# -*- coding: utf-8 -*-

from io import BytesIO
from logging import getLogger
from os.path import sep
from pathlib import Path
from shutil import rmtree
from tarfile import open as tar_open
from traceback import format_exc
from typing import Tuple
from uuid import uuid4

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes


def extract_cache(folder_path, cache_files):
    folder_path.mkdir(parents=True, exist_ok=True)

    for cache_file in cache_files:
        if cache_file["file_name"].endswith(".tgz") and cache_file["file_name"].startswith("folder:"):
            with tar_open(fileobj=BytesIO(cache_file["data"]), mode="r:gz") as tar:
                try:
                    tar.extractall(folder_path, filter="fully_trusted")
                except TypeError:
                    tar.extractall(folder_path)


def retrieve_certificates_info(folder_paths: Tuple[Path, Path]) -> dict:
    certificates = {
        "domain": [],
        "common_name": [],
        "issuer": [],
        "issuer_server": [],
        "valid_from": [],
        "valid_to": [],
        "serial_number": [],
        "fingerprint": [],
        "version": [],
        "challenge": [],
        "authenticator": [],
        "key_type": [],
    }

    for folder_path in folder_paths:
        for cert_file in folder_path.joinpath("live").glob("*/fullchain.pem"):
            domain = cert_file.parent.name
            certificates["domain"].append(domain)

            # Default values
            cert_info = {
                "common_name": "Unknown",
                "issuer": "Unknown",
                "issuer_server": "Unknown",
                "valid_from": None,
                "valid_to": None,
                "serial_number": "Unknown",
                "fingerprint": "Unknown",
                "version": "Unknown",
                "preferred_profile": "classic",
                "challenge": "Unknown",
                "authenticator": "Unknown",
                "key_type": "Unknown",
            }

            # * Parsing the certificate
            try:
                cert = x509.load_pem_x509_certificate(cert_file.read_bytes(), default_backend())

                # ? Getting the subject
                subject = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                if subject:
                    cert_info["common_name"] = subject[0].value

                # ? Getting the issuer
                issuer = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                if issuer:
                    cert_info["issuer"] = issuer[0].value

                # ? Getting the validity period
                cert_info["valid_from"] = cert.not_valid_before.strftime("%d-%m-%Y %H:%M:%S UTC")
                cert_info["valid_to"] = cert.not_valid_after.strftime("%d-%m-%Y %H:%M:%S UTC")

                # ? Getting the serial number
                cert_info["serial_number"] = str(cert.serial_number)

                # ? Getting the fingerprint
                cert_info["fingerprint"] = cert.fingerprint(hashes.SHA256()).hex()

                # ? Getting the version
                cert_info["version"] = cert.version.name
            except BaseException:
                print(f"Error while parsing certificate {cert_file}: {format_exc()}", flush=True)

            # * Parsing the renewal configuration
            try:
                renewal_file = folder_path.joinpath("renewal", f"{domain}.conf")
                if renewal_file.exists():
                    with renewal_file.open("r") as f:
                        for line in f:
                            if line.startswith("preferred_profile = "):
                                cert_info["preferred_profile"] = line.split(" = ")[1].strip()
                            elif line.startswith("pref_challs = "):
                                cert_info["challenge"] = line.split(" = ")[1].strip().split(",")[0]
                            elif line.startswith("authenticator = "):
                                cert_info["authenticator"] = line.split(" = ")[1].strip()
                            elif line.startswith("server = "):
                                cert_info["issuer_server"] = line.split(" = ")[1].strip()
                            elif line.startswith("key_type = "):
                                cert_info["key_type"] = line.split(" = ")[1].strip()
            except BaseException:
                print(f"Error while parsing renewal configuration {renewal_file}: {format_exc()}", flush=True)

            # Append values to corresponding lists in certificates dictionary
            for key in cert_info:
                certificates[key].append(cert_info[key])

    return certificates


def pre_render(app, *args, **kwargs):
    logger = getLogger("UI")
    ret = {
        "list_certificates": {
            "data": {
                "domain": [],
                "common_name": [],
                "issuer": [],
                "issuer_server": [],
                "valid_from": [],
                "valid_to": [],
                "serial_number": [],
                "fingerprint": [],
                "version": [],
                "preferred_profile": [],
                "challenge": [],
                "authenticator": [],
                "key_type": [],
            },
            "order": {
                "column": 5,
                "dir": "asc",
            },
            "svg_color": "primary",
            "col-size": "col-12",
        },
    }

    root_folder = Path(sep, "var", "tmp", "bunkerweb", "ui")
    try:
        # ? Fetching Let's Encrypt cache files
        regular_cache_files = kwargs["db"].get_jobs_cache_files(job_name="certbot-renew")

        # ? Extracting cache files
        folder_path = root_folder.joinpath("letsencrypt", str(uuid4()))
        regular_le_folder = folder_path.joinpath("regular")
        extract_cache(regular_le_folder, regular_cache_files)

        # ? We retrieve the certificates from the cache files by parsing the content of the .pem files
        ret["list_certificates"]["data"] = retrieve_certificates_info((regular_le_folder,))
    except BaseException as e:
        logger.debug(format_exc())
        logger.error(f"Failed to get Let's Encrypt certificates: {e}")
        ret["error"] = str(e)
    finally:
        if folder_path:
            rmtree(root_folder, ignore_errors=True)

    return ret
