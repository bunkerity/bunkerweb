#!/usr/bin/env python3
"""PEM resolution shared by the reverse proxy jobs.

Kept out of ``trusted-cert.py`` because that file is an executable job script: importing it
runs the job. This module holds the pure part — deciding what a blob is and turning a setting
into PEM bytes — so it can be tested on its own, the same split ``letsencrypt_utils`` uses.
"""

from base64 import b64decode
from os import sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from traceback import format_exc
from typing import Optional, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore

LOGGER = getLogger("REVERSE-PROXY.pem")


def is_pem(blob: bytes, kind: str = "certificate") -> bool:
    """Whether ``blob`` is PEM of the requested kind.

    Private keys carry several banners (``PRIVATE KEY``, ``RSA PRIVATE KEY``,
    ``EC PRIVATE KEY``, ``ENCRYPTED PRIVATE KEY``), so they are matched on the suffix rather
    than on one fixed header. Checking the kind — not merely "is it PEM" — is what stops a
    certificate pasted into the key field from being cached as a key and handed to NGINX.
    """
    blob = blob.strip()
    if not blob.startswith(b"-----BEGIN"):
        return False
    if kind == "key":
        parts = blob.split(b"-----", 2)
        return len(parts) > 1 and parts[1].endswith(b"PRIVATE KEY")
    return blob.startswith(b"-----BEGIN CERTIFICATE-----")


def process_pem_data(
    data: str,
    file_path: Optional[str],
    server_name: str,
    *,
    kind: str = "certificate",
    label: str = "trusted certificate",
) -> Union[bytes, Path, None]:
    """Resolve PEM material from a file path or from direct data (base64 or plain PEM)."""
    try:
        if file_path:
            path_obj = Path(file_path)
            if not path_obj.is_file():
                LOGGER.error(f"{label.capitalize()} file {file_path} is not a valid file for {server_name}")
                return None
            return path_obj

        if not data:
            return None

        # If the data already looks like PEM, use it directly.
        text_data = data.encode()
        if text_data.strip().startswith(b"-----BEGIN"):
            if not is_pem(text_data, kind):
                LOGGER.error(f"Invalid {label} format for server {server_name}")
                return None
            return text_data

        # Try strict base64 decode (strip whitespace, pad if needed).
        try:
            base64_data = "".join(data.split())
            base64_data += "=" * (-len(base64_data) % 4)
            decoded = b64decode(base64_data, validate=True)
            if not is_pem(decoded, kind):
                raise ValueError(f"decoded {label} data is not PEM")
            return decoded
        except BaseException:
            LOGGER.debug(format_exc())
            LOGGER.warning(f"Failed to decode {label} data as base64 for server {server_name}, trying as plain text")
            if not is_pem(text_data, kind):
                LOGGER.error(f"Invalid {label} format for server {server_name}")
                return None
            return text_data
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Error processing {label} for {server_name}: {e}")
        return None
