#!/usr/bin/env python3

from datetime import datetime, timedelta
from os import getenv, sep
from os.path import join
from pathlib import Path
from subprocess import DEVNULL, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Tuple

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from logger import getLogger  # type: ignore
from jobs import Job  # type: ignore

LOGGER = getLogger("SELF-SIGNED")
JOB = Job(LOGGER, __file__)
status = 0

multisite = getenv("MULTISITE", "no") == "yes"


def normalize_algorithm_name(algorithm: str) -> str:
    """Normalize algorithm names to handle equivalent curve names."""
    # Mapping of equivalent curve names
    curve_name_mapping = {
        "prime256v1": "secp256r1",
        "secp256r1": "prime256v1",
        "secp384r1": "secp384r1",  # No alternative name but added for completeness
    }

    # RSA bit sizes and their alternatives (no alternatives but added for completeness)
    rsa_mapping = {"2048": "2048", "4096": "4096"}

    if algorithm.startswith("ec-"):
        curve = algorithm.split("-", 1)[1]
        if curve in curve_name_mapping:
            normalized_curve = curve
            alternative_curve = curve_name_mapping.get(curve)
            return f"ec-{normalized_curve}", f"ec-{alternative_curve}" if alternative_curve != normalized_curve else None
    elif algorithm.startswith("rsa-"):
        bits = algorithm.split("-", 1)[1]
        if bits in rsa_mapping:
            return algorithm, None

    return algorithm, None


def generate_cert(first_server: str, days: str, subj: str, self_signed_path: Path) -> Tuple[bool, int]:
    server_path = self_signed_path.joinpath(first_server)
    cert_path = server_path.joinpath("cert.pem")
    key_path = server_path.joinpath("key.pem")

    # Get the algorithm from environment variable
    algorithm = getenv(f"{first_server}_SELF_SIGNED_SSL_ALGORITHM", "ec-prime256v1") if multisite else getenv("SELF_SIGNED_SSL_ALGORITHM", "ec-prime256v1")

    if cert_path.is_file() and key_path.is_file():
        if (
            run(
                ["openssl", "x509", "-checkend", "86400", "-noout", "-in", cert_path.as_posix()],
                stdin=DEVNULL,
                stderr=DEVNULL,
                check=False,
                env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
            ).returncode
            == 0
        ):
            LOGGER.info(f"Self-signed certificate already present for {first_server}")

            certificate = x509.load_pem_x509_certificate(JOB.get_cache("cert.pem", service_id=first_server), default_backend())

            try:
                not_valid_after = certificate.not_valid_after_utc
                not_valid_before = certificate.not_valid_before_utc
            except AttributeError:
                not_valid_after = certificate.not_valid_after
                not_valid_before = certificate.not_valid_before

            # Check if the current certificate uses the same algorithm as specified in the config
            current_algorithm = None
            public_key = certificate.public_key()
            if hasattr(public_key, "curve"):
                # For EC keys
                current_algorithm = f"ec-{public_key.curve.name}"
            elif hasattr(public_key, "key_size"):
                # For RSA keys
                current_algorithm = f"rsa-{public_key.key_size}"

            # Normalize algorithm names for comparison
            normalized_config_alg, alt_config_alg = normalize_algorithm_name(algorithm)

            # Compare with both the normalized and alternative names if available
            algorithm_mismatch = current_algorithm and current_algorithm != normalized_config_alg
            if algorithm_mismatch and alt_config_alg and current_algorithm == alt_config_alg:
                algorithm_mismatch = False  # Reset mismatch if matches the alternative name

            if algorithm_mismatch:
                LOGGER.warning(
                    f"Algorithm of self-signed certificate for {first_server} ({current_algorithm}) is different from the one in the configuration ({algorithm}), regenerating ..."
                )
            elif sorted(attribute.rfc4514_string() for attribute in certificate.subject) != sorted(v for v in subj.split("/") if v):
                LOGGER.warning(f"Subject of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ...")
            elif not_valid_after - not_valid_before != timedelta(days=int(days)):
                LOGGER.warning(
                    f"Expiration date of self-signed certificate for {first_server} is different from the one in the configuration, regenerating ..."
                )
            elif not_valid_after < datetime.now(tz=not_valid_after.tzinfo):
                LOGGER.warning(f"Self-signed certificate for {first_server} has expired, regenerating ...")
            else:
                LOGGER.info(f"Self-signed certificate for {first_server} is valid")
                return True, 0

    LOGGER.info(f"Generating self-signed certificate for {first_server}")
    server_path.mkdir(parents=True, exist_ok=True)

    # Prepare openssl command based on the selected algorithm
    openssl_cmd = [
        "openssl",
        "req",
        "-nodes",
        "-x509",
        "-newkey",
    ]

    # Add algorithm-specific options
    if algorithm.startswith("ec-"):
        curve = algorithm.split("-")[1]
        openssl_cmd.extend(["ec", "-pkeyopt", f"ec_paramgen_curve:{curve}"])
    elif algorithm.startswith("rsa-"):
        bits = algorithm.split("-")[1]
        openssl_cmd.extend(["rsa", "-pkeyopt", f"rsa_keygen_bits:{bits}"])

    # Add the rest of the common options
    openssl_cmd.extend(
        [
            "-keyout",
            key_path.as_posix(),
            "-out",
            cert_path.as_posix(),
            "-days",
            days,
            "-subj",
            subj,
        ]
    )

    if (
        run(
            openssl_cmd,
            stdin=DEVNULL,
            stderr=DEVNULL,
            check=False,
            env={"PATH": getenv("PATH", ""), "PYTHONPATH": getenv("PYTHONPATH", "")},
        ).returncode
        != 0
    ):
        LOGGER.error(f"Self-signed certificate generation failed for {first_server}")
        return False, 2

    # Update db
    cached, err = JOB.cache_file("cert.pem", self_signed_path.joinpath(first_server, "cert.pem"), service_id=first_server, overwrite_file=False)
    if not cached:
        LOGGER.error(f"Error while caching self-signed cert.pem file for {first_server} : {err}")

    cached, err = JOB.cache_file("key.pem", self_signed_path.joinpath(first_server, "key.pem"), service_id=first_server, overwrite_file=False)
    if not cached:
        LOGGER.error(f"Error while caching self-signed {first_server}.key file : {err}")

    LOGGER.info(f"Successfully generated self-signed certificate for {first_server}")
    return True, 1


status = 0

try:
    self_signed_path = Path(sep, "var", "cache", "bunkerweb", "selfsigned")
    servers = getenv("SERVER_NAME", "www.example.com") or []

    if isinstance(servers, str):
        servers = servers.split(" ")

    if not servers:
        LOGGER.info("No server found, skipping self-signed certificate generation ...")
        sys_exit(0)

    skipped_servers = []
    if getenv("MULTISITE", "no") == "no":
        servers = [servers[0]]
        if getenv("GENERATE_SELF_SIGNED_SSL", "no") == "no":
            LOGGER.info("Generate self-signed SSL is not enabled, skipping certificate generation ...")
            skipped_servers = servers

    if not skipped_servers:
        for first_server in servers:
            if (getenv(f"{first_server}_GENERATE_SELF_SIGNED_SSL", "no") if multisite else getenv("GENERATE_SELF_SIGNED_SSL", "no")) == "no":
                skipped_servers.append(first_server)
                continue

            LOGGER.info(f"Service {first_server} is using self-signed SSL certificates, checking ...")

            ret, ret_status = generate_cert(
                first_server,
                getenv(f"{first_server}_SELF_SIGNED_SSL_EXPIRY", "365") if multisite else getenv("SELF_SIGNED_SSL_EXPIRY", "365"),
                getenv(f"{first_server}_SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/") if multisite else getenv("SELF_SIGNED_SSL_SUBJ", "/CN=www.example.com/"),
                self_signed_path,
            )
            if not ret:
                skipped_servers.append(first_server)
            status = ret_status

    for first_server in skipped_servers:
        JOB.del_cache("cert.pem", service_id=first_server)
        JOB.del_cache("key.pem", service_id=first_server)
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running self-signed.py :\n{e}")

sys_exit(status)
