#!/usr/bin/python3
# -*- coding: utf-8 -*-

from datetime import timedelta
from logging import Logger
from socket import create_connection
from ssl import CERT_NONE, DER_cert_to_PEM_cert, create_default_context
from typing import Any

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from httpx import Response

from .http_common import perform_request


def handle(LOGGER: Logger, action: Any) -> None:
    ctx = perform_request(LOGGER, action)
    response = ctx.response

    if not isinstance(response, Response):
        if action.success:
            LOGGER.error(f"❌ Request failed unexpectedly:\n{response}")
            exit(1)
        LOGGER.info(f"🔐 SSL connection failed as expected during HTTP request phase:\n{response}")
        return

    if action.raise_for_status:
        response.raise_for_status()

    if response.url.scheme != "https":
        LOGGER.error("🔐 Response URL scheme is not HTTPS, exiting ...")
        exit(1)

    ssl_context = create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = CERT_NONE
    if action.client_cert:
        try:
            if action.client_cert_key:
                ssl_context.load_cert_chain(action.client_cert, action.client_cert_key)
            else:
                ssl_context.load_cert_chain(action.client_cert)
        except Exception as e:
            LOGGER.error(f"🔐 Failed to load client certificate {action.client_cert}: {e}")
            exit(1)
    if action.client_ssl_cipher is not None:
        ssl_context.set_ciphers(action.client_ssl_cipher)

    try:
        with create_connection((response.url.host, response.url.port or 443)) as conn:
            with ssl_context.wrap_socket(conn, server_hostname=response.url.host) as ssl_socket:
                cipher_info = ssl_socket.cipher()
                LOGGER.debug(f"🔐 Response SSL version: {ssl_socket.version()}")
                LOGGER.debug(f"🔐 Response SSL cipher: {cipher_info}")
                LOGGER.debug(f"🔐 Response SSL compression: {ssl_socket.compression()}")
                LOGGER.debug(f"🔐 Response SSL shared ciphers: {ssl_socket.shared_ciphers()}")
                LOGGER.debug(f"🔐 Response SSL server certificate binary: {ssl_socket.getpeercert(True)}")
                if ssl_socket.version() not in action.ssl_protocols:
                    if action.success:
                        LOGGER.error(f"🔐 SSL version {ssl_socket.version()} not found in response, exiting ...")
                        exit(1)
                    else:
                        LOGGER.info(f"🔐 SSL version {ssl_socket.version()} not in allowed protocols, as expected")

                if action.ssl_cipher is not None:
                    if action.ssl_cipher not in cipher_info:
                        if action.success:
                            LOGGER.error(f"🔐 SSL cipher {action.ssl_cipher} not found in response, exiting ...")
                            exit(1)
                        else:
                            LOGGER.info(f"🔐 SSL cipher {action.ssl_cipher} not found in response, as expected")
                    elif not action.success:
                        LOGGER.error(f"🔐 SSL cipher {action.ssl_cipher} was found in response but expected to fail, exiting ...")
                        exit(1)

                pem_data = DER_cert_to_PEM_cert(ssl_socket.getpeercert(True))  # type: ignore

        certificate = x509.load_pem_x509_certificate(pem_data.encode(), default_backend())
        # Show all certificate details for debugging
        LOGGER.debug(f"🔐 SSL certificate details: {certificate}")
        LOGGER.debug(f"🔐 SSL certificate serial number: {certificate.serial_number}")
        LOGGER.debug(f"🔐 SSL certificate version: {certificate.version}")
        LOGGER.debug(f"🔐 SSL certificate issuers: {[issuer.rfc4514_string() for issuer in certificate.issuer]}")
        LOGGER.debug(f"🔐 SSL certificate subjects: {[subject.rfc4514_string() for subject in certificate.subject]}")

        # Round to the beginning of the day
        not_valid_before = certificate.not_valid_before_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        not_valid_after = certificate.not_valid_after_utc.replace(hour=0, minute=0, second=0, microsecond=0)

        if not_valid_after - not_valid_before != timedelta(days=int(action.ssl_expiration)):
            if action.success:
                LOGGER.error(
                    f"🔐 Expiration date of SSL certificate is {not_valid_after} but should be {not_valid_before + timedelta(days=int(action.ssl_expiration))}, exiting ..."
                )
                exit(1)
            else:
                LOGGER.info("🔐 Expiration date of SSL certificate does not match expected value, as expected")

        subject_attributes = sorted(attribute.rfc4514_string() for attribute in certificate.subject)
        if subject_attributes != sorted(v for v in action.ssl_subject.split("/") if v):
            if action.success:
                LOGGER.error(f"🔐 SSL subject {certificate.subject} is different from the one in the configuration, exiting ...")
                exit(1)
            else:
                LOGGER.info(f"🔐 SSL subject {certificate.subject} is different from the expected value, as expected")

        public_key = certificate.public_key()
        key_type_ok = False
        key_size_ok = False
        curve_ok = False
        LOGGER.debug(f"🔐 SSL public key: {public_key}")
        LOGGER.debug(f"🔐 SSL public key type: {type(public_key)}")

        if action.ssl_algorithm.startswith("ec-"):
            if isinstance(public_key, ec.EllipticCurvePublicKey):
                LOGGER.debug(f"🔐 SSL public key curve: {public_key.curve}")
                key_type_ok = True
                if action.ssl_algorithm == "ec-prime256v1" and isinstance(public_key.curve, ec.SECP256R1):
                    curve_ok = True
                elif action.ssl_algorithm == "ec-secp384r1" and isinstance(public_key.curve, ec.SECP384R1):
                    curve_ok = True
        elif action.ssl_algorithm.startswith("rsa-"):
            if isinstance(public_key, rsa.RSAPublicKey):
                LOGGER.debug(f"🔐 SSL public key size: {public_key.key_size} bits")
                key_type_ok = True
                expected_size = int(action.ssl_algorithm.split("-")[1])
                if public_key.key_size == expected_size:
                    key_size_ok = True
                LOGGER.debug(f"🔐 SSL public key size: {public_key.key_size} bits, expected: {expected_size} bits")

        if action.ssl_algorithm.startswith("ec-") and not (key_type_ok and curve_ok):
            if action.success:
                LOGGER.error(f"🔐 SSL certificate doesn't use the expected EC curve {action.ssl_algorithm}, exiting ...")
                exit(1)
            else:
                LOGGER.info(f"🔐 SSL certificate doesn't use the expected EC curve {action.ssl_algorithm}, as expected")
        elif action.ssl_algorithm.startswith("rsa-") and not (key_type_ok and key_size_ok):
            if action.success:
                LOGGER.error(f"🔐 SSL certificate doesn't use the expected RSA key size {action.ssl_algorithm}, exiting ...")
                exit(1)
            else:
                LOGGER.info(f"🔐 SSL certificate doesn't use the expected RSA key size {action.ssl_algorithm}, as expected")

        LOGGER.info(f"🔐 SSL certificate using expected algorithm {action.ssl_algorithm}")

        if not action.success:
            LOGGER.error("🔐 SSL connection succeeded but was expected to fail, exiting ...")
            exit(1)
    except Exception as e:
        if action.success:
            LOGGER.error(f"🔐 SSL connection failed: {e}, exiting ...")
            exit(1)
        else:
            LOGGER.info(f"🔐 SSL connection failed as expected: {e}")
