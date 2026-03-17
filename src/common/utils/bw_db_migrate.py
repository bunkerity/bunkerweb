#!/usr/bin/env python3

"""
Standalone BunkerWeb database backend migration helper.

Usage example:

    # Option A: pass URIs via CLI
    python3 src/common/utils/bw_db_migrate.py \\
      --source-uri "sqlite:////var/lib/bunkerweb/db.sqlite3" \\
      --target-uri "postgresql://user:pass@db-primary:5432/bunkerweb"

    # Option B: read from env file (defaults to /etc/bunkerweb/variables.env)
    python3 src/common/utils/bw_db_migrate.py --env-file /etc/bunkerweb/variables.env

    # Option C: use current process environment
    export DATABASE_URI="sqlite:////var/lib/bunkerweb/db.sqlite3"
    export DB_MIGRATION_TARGET_URI="postgresql://user:pass@db-primary:5432/bunkerweb"
    python3 src/common/utils/bw_db_migrate.py

The script:
    - Connects to the current (source) database from DATABASE_URI
    - Connects to the target database from DB_MIGRATION_TARGET_URI
    - Ensures the target is empty from BunkerWeb's point of view
    - Runs Alembic migrations on the target to create the schema for the current version
    - Copies all data table-by-table
    - Verifies per-table row counts

It does NOT change the BunkerWeb version: it only moves data between backends.
Run it during a maintenance window when no writes are happening.
"""

from __future__ import annotations

import argparse
import sys as _sys
_sys.dont_write_bytecode = True
import os
import secrets
import shutil
import string
import sys
import time
import socket
import ssl
import sqlite3
from datetime import datetime
import logging
from logging import INFO, basicConfig, getLogger
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse

LOGGER = getLogger("bw_db_migrate")
basicConfig(level=INFO, format="%(asctime)s [%(levelname)s] %(message)s")

__version__ = "0.5"
_MAX_LOG_LEN = 2048
_DUMP_ROOT = Path("/tmp/bunkerweb/bw_db_migrate")


def _sanitize_message(text: object) -> str:
    """
    Sanitize log messages:
    - Never show passwords or credentials
    - Mask userinfo in URIs (user[:pass]@host -> ***@host)
    """
    import re

    s = str(text)

    # Mask userinfo in URIs: scheme://user:pass@host -> scheme://***@host
    s = re.sub(r"(\w+://)([^@/]+)@", r"\1***@", s)

    # Mask common password patterns (case-insensitive)
    s = re.sub(r"(?i)(password\s*=\s*['\"])[^'\"]*(['\"])", r"\1***\2", s)
    s = re.sub(r"(?i)(identified by\s+['\"])[^'\"]*(['\"])", r"\1***\2", s)

    return s


def _log_truncated(level: int, msg: object, *args, exc_info=None) -> None:
    """
    Central logging helper:
    - Formats message with args
    - Sanitizes secrets
    - Truncates to 2048 characters
    """
    try:
        if args:
            formatted = str(msg) % args
        else:
            formatted = str(msg)
    except Exception:
        formatted = f"{msg} {args}"

    formatted = _sanitize_message(formatted)
    if len(formatted) > _MAX_LOG_LEN:
        formatted = formatted[:_MAX_LOG_LEN]

    LOGGER.log(level, formatted, exc_info=exc_info)


def _log_debug(msg: object, *args, **kwargs) -> None:
    _log_truncated(logging.DEBUG, msg, *args, exc_info=kwargs.get("exc_info"))


def _log_info(msg: object, *args, **kwargs) -> None:
    _log_truncated(logging.INFO, msg, *args, exc_info=kwargs.get("exc_info"))


def _log_warning(msg: object, *args, **kwargs) -> None:
    _log_truncated(logging.WARNING, msg, *args, exc_info=kwargs.get("exc_info"))


def _log_error(msg: object, *args, **kwargs) -> None:
    _log_truncated(logging.ERROR, msg, *args, exc_info=kwargs.get("exc_info"))


def _log_exception(msg: object, *args, **kwargs) -> None:
    # Always include traceback when called via LOGGER.exception-style usage.
    _log_truncated(logging.ERROR, msg, *args, exc_info=True)


# Monkey-patch the module-local logger methods so all calls go through our
# sanitizer and truncation layer.
LOGGER.debug = _log_debug  # type: ignore[assignment]
LOGGER.info = _log_info  # type: ignore[assignment]
LOGGER.warning = _log_warning  # type: ignore[assignment]
LOGGER.error = _log_error  # type: ignore[assignment]
LOGGER.exception = _log_exception  # type: ignore[assignment]

_LAST_PROGRESS_LINE: str = ""


def _progress(line: str) -> None:
    """
    Print a single-line progress indicator (updates in place when possible).
    """
    global _LAST_PROGRESS_LINE
    if line == _LAST_PROGRESS_LINE:
        return
    _LAST_PROGRESS_LINE = line
    # stderr is commonly unbuffered; keep progress separate from INFO logs.
    # When stderr is not a TTY (e.g. redirected to a file), avoid carriage
    # returns which can overwrite earlier log lines in the output file.
    if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
        sys.stderr.write("\r" + line[:200] + " " * 10)
    else:
        sys.stderr.write(line[:200] + "\n")
    sys.stderr.flush()


def _progress_done() -> None:
    """
    End the progress line cleanly.
    """
    if _LAST_PROGRESS_LINE:
        sys.stderr.write("\n")
        sys.stderr.flush()


def _generate_password() -> str:
    """
    Generate a strong random password using 144-bit entropy .
    Uses Python's secrets module with base64 encoding.
    Strips invalid characters (+, /, =) to produce a database-safe password.
    """
    import base64

    # 144-bit (18 bytes) of entropy
    random_bytes = secrets.token_bytes(18)
    # Base64 encode and strip padding
    b64_pwd = base64.b64encode(random_bytes).decode("ascii").rstrip("=")
    # Strip invalid chars: + and /
    safe_pwd = b64_pwd.replace("+", "").replace("/", "")
    return safe_pwd


def _resolve_repo_root() -> Path:
    """
    Resolve the BunkerWeb root for both source and installed layouts.

    Source tree (development):
        .../bunkerweb/src/common/utils/bw_db_migrate.py
        -> root = .../bunkerweb

    Installed manager (runtime):
        /usr/share/bunkerweb/utils/bw_db_migrate.py
        -> root = /usr/share/bunkerweb
    """
    this_file = Path(__file__).resolve()
    # Try to detect a layout that contains src/common/db/model.py
    for parent in this_file.parents:
        if (parent / "src" / "common" / "db" / "model.py").is_file():
            return parent
        if (parent / "db" / "model.py").is_file():
            return parent
    # Fallback: assume /usr/share/bunkerweb when installed with utils/ under it
    if this_file.parent.name == "utils" and this_file.parent.parent.name == "bunkerweb":
        return this_file.parent.parent
    # Last resort: two levels up
    return this_file.parents[1]


REPO_ROOT = _resolve_repo_root()

# Ensure we can import db models and alembic configuration.
# Support both source layout (src/common/db) and installed layout (/usr/share/bunkerweb/db).
db_package_candidates = [
    REPO_ROOT / "src" / "common" / "db",
    REPO_ROOT / "db",
]
for db_package_path in db_package_candidates:
    if db_package_path.is_dir() and str(db_package_path) not in sys.path:
        sys.path.insert(0, str(db_package_path))

# Ensure bundled Python deps are available (installed layout: /usr/share/bunkerweb/deps/python).
deps_candidate = REPO_ROOT / "deps" / "python"
if deps_candidate.is_dir() and str(deps_candidate) not in sys.path:
    sys.path.insert(0, str(deps_candidate))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


try:
    from model import Base
except Exception as exc:  # pragma: no cover - import robustness
    LOGGER.error("Unable to import db model Base from model.py: %s", exc)
    raise


def _parse_bool(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v in ("yes", "true", "1", "on"):
        return True
    if v in ("no", "false", "0", "off"):
        return False
    return default


def _parse_int(value: str, default: int) -> int:
    v = (value or "").strip()
    try:
        return int(v)
    except Exception:
        return default


def _parse_float(value: str, default: float) -> float:
    v = (value or "").strip()
    try:
        return float(v)
    except Exception:
        return default


def _engine_kwargs_from_settings(settings: Dict[str, str]) -> Dict[str, object]:
    """
    Map BunkerWeb DATABASE_* pool settings to SQLAlchemy create_engine kwargs.
    """
    pool_size = _parse_int(settings.get("DATABASE_POOL_SIZE", ""), 40)
    max_overflow = _parse_int(settings.get("DATABASE_POOL_MAX_OVERFLOW", ""), 20)
    pool_timeout = _parse_int(settings.get("DATABASE_POOL_TIMEOUT", ""), 5)
    pool_recycle = _parse_int(settings.get("DATABASE_POOL_RECYCLE", ""), 1800)
    pool_pre_ping = _parse_bool(settings.get("DATABASE_POOL_PRE_PING", ""), True)
    pool_reset_on_return = (settings.get("DATABASE_POOL_RESET_ON_RETURN", "") or "").strip().lower() or None

    # SQLAlchemy expects None or one of: "rollback", "commit", None, False
    if pool_reset_on_return not in (None, "rollback", "commit", "none"):
        pool_reset_on_return = None
    if pool_reset_on_return == "none":
        pool_reset_on_return = None

    return {
        "future": True,
        "pool_pre_ping": pool_pre_ping,
        "pool_recycle": pool_recycle,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_reset_on_return": pool_reset_on_return,
    }


def _normalize_mysql_ssl_in_uri(uri: str) -> str:
    """
    Work around PyMySQL expecting a dict for `ssl` while URLs like ?ssl=true
    produce a plain string.
    - For mysql+pymysql / mariadb+pymysql URIs, drop bare `ssl=true`.
    - Keep more specific options like ssl_ca=... as-is.
    """
    from sqlalchemy.engine.url import make_url

    try:
        url = make_url(uri)
    except Exception:
        return uri

    drivername = (url.drivername or "").lower()
    if "mysql+pymysql" not in drivername and "mariadb+pymysql" not in drivername:
        return uri

    query = dict(url.query or {})
    # If ssl is provided as a bare truthy flag, remove it to avoid AttributeError in PyMySQL.
    if "ssl" in query and isinstance(query["ssl"], str) and query["ssl"].lower() in ("true", "1", "yes", "on"):
        query.pop("ssl", None)

    if query == (url.query or {}):
        return uri

    url = url.set(query=query)
    return str(url)


def _create_engine(uri: str, *, engine_kwargs: Optional[Dict[str, object]] = None) -> Engine:
    """
    Create a SQLAlchemy engine with sensible defaults for migrations.
    For mysql+pymysql URIs with ssl_ca, inject it as connect_args so PyMySQL
    picks it up correctly (passing it only via query string is not reliable).
    """
    from sqlalchemy.engine.url import make_url

    normalized_uri = _normalize_mysql_ssl_in_uri(uri)
    kwargs: Dict[str, object] = dict(engine_kwargs or {"future": True, "pool_pre_ping": True, "pool_recycle": 1800})

    try:
        url = make_url(normalized_uri)
        drivername = (url.drivername or "").lower()
        if "pymysql" in drivername:
            query = dict(url.query or {})
            ssl_ca = query.get("ssl_ca") or query.get("sslrootcert")
            if ssl_ca:
                # PyMySQL requires ssl as a dict in connect_args, not a query string param
                existing_ssl: dict = {}
                if isinstance(kwargs.get("connect_args"), dict):
                    existing_ssl = dict(kwargs["connect_args"].get("ssl", {}))  # type: ignore[arg-type]
                existing_ssl.setdefault("ca", ssl_ca)
                connect_args = dict(kwargs.get("connect_args") or {})  # type: ignore[arg-type]
                connect_args["ssl"] = existing_ssl
                kwargs["connect_args"] = connect_args
    except Exception:
        pass

    return create_engine(normalized_uri, **kwargs)


def _uri_uses_ssl(uri: str) -> bool:
    """
    Best-effort check to see if a DB URI is configured for SSL/TLS.
    Used only for diagnostics and extra logging.
    """
    lower = uri.lower()
    return any(
        marker in lower
        for marker in (
            "sslmode=",
            "ssl=true",
            "ssl_ca=",
            "sslrootcert=",
        )
    )


def _extract_ca_from_uri(uri: str) -> str:
    """
    Extract CA path from a DB URI if present (ssl_ca or sslrootcert).
    Returns empty string if none.
    """
    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(uri)
        query = dict(url.query or {})
        for key in ("ssl_ca", "sslrootcert"):
            v = query.get(key)
            if isinstance(v, str) and v:
                return v
    except Exception:
        return ""
    return ""


def _resolve_target_host_port(uri: str) -> tuple[str, int]:
    """
    Best-effort extraction of host/port from a SQLAlchemy URI.
    """
    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(uri)
        host = url.host or ""
        port = int(url.port or 0)
        if host and port:
            return host, port
        if host:
            # Reasonable defaults
            driver = (url.drivername or "").lower()
            if "postgres" in driver:
                return host, int(url.port or 5432)
            if "mysql" in driver or "mariadb" in driver:
                return host, int(url.port or 3306)
            return host, int(url.port or 0)
    except Exception:
        pass

    try:
        p = urlparse(uri)
        return (p.hostname or ""), int(p.port or 0)
    except Exception:
        return "", 0


def _resolve_ips(hostname: str) -> list[str]:
    """
    Resolve a hostname to a list of IPs (best effort).
    """
    if not hostname:
        return []
    try:
        infos = socket.getaddrinfo(hostname, None)
        ips: list[str] = []
        for family, _socktype, _proto, _canon, sockaddr in infos:
            if family in (socket.AF_INET, socket.AF_INET6) and sockaddr:
                ip = sockaddr[0]
                if ip not in ips:
                    ips.append(ip)
        return ips
    except Exception:
        return []


def _system_ca_summary() -> tuple[str, str]:
    """
    Return (cafile, capath) from system defaults; may be empty strings.
    """
    paths = ssl.get_default_verify_paths()
    return (paths.cafile or ""), (paths.capath or "")


def _sqlite_path_from_uri(uri: str) -> str:
    """
    Extract filesystem path from sqlite:/// SQLAlchemy URIs.
    """
    try:
        from sqlalchemy.engine.url import make_url

        url = make_url(uri)
        if (url.drivername or "").lower().startswith("sqlite"):
            return url.database or ""
    except Exception:
        pass
    # Fallback: sqlite:////absolute/path or sqlite:///relative
    if uri.startswith("sqlite:////"):
        return "/" + uri[len("sqlite:////") :]
    if uri.startswith("sqlite:///"):
        return uri[len("sqlite:///") :]
    return ""


def _sqlite_snapshot_if_wal(source_uri: str, dump_dir: Path) -> str:
    """
    If the source SQLite database uses WAL mode, create a consistent snapshot
    DB file using SQLite's online backup API, reading from a read-only
    connection. Returns a SQLAlchemy sqlite URI to use for dumping.

    If WAL is not enabled, returns source_uri unchanged.
    """
    db_path = _sqlite_path_from_uri(source_uri)
    if not db_path:
        return source_uri

    try:
        src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except Exception:
        # If read-only URI open fails, fall back to normal dumping on source_uri.
        return source_uri

    try:
        try:
            cur = src.execute("PRAGMA journal_mode;")
            row = cur.fetchone()
            mode = (row[0] if row else "") or ""
        except Exception:
            mode = ""

        if str(mode).strip().lower() != "wal":
            return source_uri

        dump_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = dump_dir / "sqlite-source-snapshot.sqlite3"
        # Create the destination snapshot DB and copy.
        dst = sqlite3.connect(snapshot_path.as_posix())
        try:
            src.backup(dst)
        finally:
            try:
                dst.close()
            except Exception:
                pass

        LOGGER.info("SQLite source is in WAL mode; created read-only snapshot at %s", snapshot_path)
        return f"sqlite:////{str(snapshot_path).lstrip('/')}"
    finally:
        try:
            src.close()
        except Exception:
            pass


def _verify_mysql_ssl_and_log_details(target_uri: str) -> None:
    """
    Perform an explicit MySQL SSL/TLS verification handshake using PyMySQL so we can:
    - Verify server certificate (against provided CA or system CAs)
    - Log SSL protocol/cipher and certificate details
    """
    try:
        from sqlalchemy.engine.url import make_url
        import pymysql
    except Exception as exc:
        LOGGER.warning("Unable to perform MySQL SSL verification (missing deps): %s", exc)
        return

    url = make_url(target_uri)
    driver = (url.drivername or "").lower()
    if "mysql+pymysql" not in driver and "mariadb+pymysql" not in driver:
        return

    host = url.host or ""
    port = int(url.port or 3306)
    user = url.username or ""
    password = url.password or ""
    dbname = url.database or ""

    ca_path = _extract_ca_from_uri(target_uri)
    cafile, capath = _system_ca_summary()

    ssl_dict: Dict[str, object] = {"cert_reqs": ssl.CERT_REQUIRED, "check_hostname": True}
    if ca_path:
        ssl_dict["ca"] = ca_path
    else:
        if cafile:
            ssl_dict["ca"] = cafile
        elif capath:
            ssl_dict["capath"] = capath

    def _log_cert_details_from_conn(connection: "pymysql.connections.Connection", context: str) -> tuple[str, str]:  # type: ignore[name-defined]
        sock = getattr(connection, "_sock", None)
        if sock is None or not hasattr(sock, "cipher"):
            LOGGER.warning("%s: expected an SSL socket, but connection socket has no SSL attributes.", context)
            return "", ""
        cipher = sock.cipher()
        cipher_name = cipher[0] if isinstance(cipher, (tuple, list)) and cipher else str(cipher)
        version = sock.version() if hasattr(sock, "version") else ""
        LOGGER.info("%s: protocol=%s cipher=%s", context, version, cipher)

        cert = sock.getpeercert() if hasattr(sock, "getpeercert") else None
        if isinstance(cert, dict) and cert:
            LOGGER.info("%s: server certificate subject=%s", context, cert.get("subject"))
            LOGGER.info("%s: server certificate issuer=%s", context, cert.get("issuer"))
            LOGGER.info(
                "%s: server certificate validity notBefore=%s notAfter=%s",
                context,
                cert.get("notBefore"),
                cert.get("notAfter"),
            )
            if cert.get("subjectAltName"):
                LOGGER.info("%s: server certificate SAN=%s", context, cert.get("subjectAltName"))
            return version, cipher_name

        # Fallback: dump full PEM for the leaf certificate and then decode it to
        # show detailed fields, similar to `openssl s_client -starttls mysql`.
        try:
            import base64
            import tempfile
            import os

            bin_cert = sock.getpeercert(binary_form=True) if hasattr(sock, "getpeercert") else None
            if not bin_cert:
                LOGGER.warning("%s: unable to read server certificate details from SSL socket.", context)
                return

            b64 = base64.b64encode(bin_cert).decode("ascii")
            lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
            pem_body = "\n".join(lines)
            pem_text = "-----BEGIN CERTIFICATE-----\n" + pem_body + "\n-----END CERTIFICATE-----"

            # Log the full PEM in multiple chunks so that our per-message
            # truncation does not cut the certificate itself.
            chunk_size = 1800
            for idx in range(0, len(pem_text), chunk_size):
                chunk = pem_text[idx : idx + chunk_size]
                LOGGER.info("%s: server certificate PEM (chunk %d):\n%s", context, idx // chunk_size + 1, chunk)

            # Decode the PEM using the built-in test helper to extract fields.
            try:
                from ssl import _ssl  # type: ignore[attr-defined]

                with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
                    tf.write(pem_text)
                    tf.flush()
                    tmp_path = tf.name
                try:
                    info = _ssl._test_decode_cert(tmp_path)  # type: ignore[attr-defined]
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

                if info:
                    LOGGER.info("%s: decoded certificate subject=%s", context, info.get("subject"))
                    LOGGER.info("%s: decoded certificate issuer=%s", context, info.get("issuer"))
                    LOGGER.info(
                        "%s: decoded certificate validity notBefore=%s notAfter=%s",
                        context,
                        info.get("notBefore"),
                        info.get("notAfter"),
                    )
                    if info.get("subjectAltName"):
                        LOGGER.info("%s: decoded certificate SAN=%s", context, info.get("subjectAltName"))

                # Additionally, try to determine RSA key size and warn if it is
                # below 3072 bits (BSI recommendation).
                try:
                    from cryptography import x509  # type: ignore[import]
                    from cryptography.hazmat.backends import default_backend  # type: ignore[import]
                    from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore[import]

                    cert_obj = x509.load_der_x509_certificate(bin_cert, default_backend())
                    pub_key = cert_obj.public_key()
                    if isinstance(pub_key, rsa.RSAPublicKey):
                        key_size = pub_key.key_size
                        LOGGER.info("%s: RSA public key size=%d bits", context, key_size)
                        if key_size < 3072:
                            LOGGER.warning(
                                "%s: WARNING – RSA key size below 3072 bits (%d). "
                                "BSI recommends at least 3072-bit RSA or equivalent EC strength.",
                                context,
                                key_size,
                            )
                except Exception:
                    # If cryptography is not available or parsing fails, skip key-size specific checks.
                    pass
            except Exception as decode_exc:
                LOGGER.warning("%s: unable to decode server certificate for details: %s", context, decode_exc)
        except Exception as pem_exc:
            LOGGER.warning("%s: unable to dump server certificate PEM: %s", context, pem_exc)
        return version, cipher_name

    def _analyze_tls_strength(version: str, cipher_name: str) -> None:
        """
        Emit warnings for weak TLS settings and a GOOD line when everything
        looks strong (modern protocol + forward secrecy).
        """
        weak = False
        if not version or not (version.startswith("TLSv1.2") or version.startswith("TLSv1.3")):
            LOGGER.warning(
                "TLS configuration: WARNING – old or unknown TLS version in use (%s). "
                "Prefer TLSv1.2 or TLSv1.3.",
                version or "(none)",
            )
            weak = True
        # Forward secrecy:
        # - For TLS 1.3, all standard cipher suites provide FS by design.
        # - For TLS <= 1.2, require DHE/ECDHE in the cipher name.
        upper_cipher = cipher_name.upper() if cipher_name else ""
        if version and not version.startswith("TLSv1.3"):
            if cipher_name and not any(token in upper_cipher for token in ("DHE", "ECDHE")):
                LOGGER.warning(
                    "TLS configuration: WARNING – cipher without forward secrecy in use (%s). "
                    "Prefer ECDHE/DHE-based ciphers.",
                    cipher_name,
                )
                weak = True
        # Key type recommendation: if RSA-based cipher is in use, recommend
        # switching to ECDSA/EC keys in line with modern guidance (e.g. BSI 3072+
        # RSA or equivalent EC strength).
        if "RSA" in upper_cipher and "ECDSA" not in upper_cipher:
            LOGGER.warning(
                "TLS configuration: WARNING – RSA-based cipher negotiated (%s). "
                "It is recommended to migrate to ECDSA certificates with EC keys "
                "for stronger security and better performance.",
                cipher_name or "(unknown)",
            )
            weak = True
        if not weak:
            LOGGER.info("TLS configuration: GOOD – all TLS tests passed with modern protocol and forward-secret cipher.")

    # First, try with full verification.
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname or None,
            ssl=ssl_dict,
            connect_timeout=10,
            read_timeout=10,
            write_timeout=10,
        )
        try:
            ver, ciph = _log_cert_details_from_conn(conn, "SSL verified")
            _analyze_tls_strength(ver, ciph)
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return
    except Exception as exc:
        # Verification failed; try a secondary, non-verifying connection solely
        # to inspect and log the certificate chain to help the user locate the
        # correct CA file. Then re-raise the original error.
        LOGGER.error("SSL verification failed for target database: %s", exc)
        # Emit a clear warning summarizing why the certificate is considered invalid.
        reason = str(exc)
        if "self-signed certificate" in reason:
            LOGGER.warning(
                "TLS certificate validation failed: self-signed certificate in chain. "
                "You likely need to configure the corresponding CA PEM in the TUI."
            )
        elif "certificate has expired" in reason:
            LOGGER.warning("TLS certificate validation failed: certificate has expired.")
        elif "hostname" in reason or "doesn't match" in reason:
            LOGGER.warning(
                "TLS certificate validation failed: hostname mismatch between DB host and certificate subject/SAN."
            )
        else:
            LOGGER.warning("TLS certificate validation failed: %s", reason)
        try:
            diag_ssl: Dict[str, object] = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
            # Reuse explicit CA if one was configured, as it may help expose the full chain.
            if ca_path:
                diag_ssl["ca"] = ca_path
            conn2 = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=dbname or None,
                ssl=diag_ssl,
                connect_timeout=10,
                read_timeout=10,
                write_timeout=10,
            )
            try:
                _log_cert_details_from_conn(conn2, "SSL diagnostics (verification disabled)")
            finally:
                try:
                    conn2.close()
                except Exception:
                    pass
        except Exception as diag_exc:
            LOGGER.error("Additional SSL diagnostics connection failed: %s", diag_exc)
        raise


def _load_env_file(path: Path) -> Dict[str, str]:
    """
    Minimal dotenv parser for KEY=VALUE lines.
    Supports optional leading 'export ' and ignores comments/blank lines.
    """
    data: Dict[str, str] = {}
    if not path.exists():
        return data

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def _resolve_input_value(cli_value: Optional[str], env_file_values: Dict[str, str], env_key: str) -> str:
    """
    Resolve a value with precedence: CLI > env file > process environment.
    """
    if cli_value:
        return cli_value.strip()
    if env_key in env_file_values:
        return env_file_values[env_key].strip()
    return os.getenv(env_key, "").strip()


def _run_tui(default_env_file: str) -> tuple[str, str, str, bool, bool, bool, bool]:
    """
    Basic terminal UI to collect inputs without extra dependencies.

    Returns: (env_file, source_uri, target_uri, test_target, update_env_file, dry_run, write_config_now)
    """
    import curses

    def _tui_main(stdscr):
        curses.curs_set(1)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)    # highlight
            curses.init_pair(2, curses.COLOR_YELLOW, -1)  # checkboxes/buttons/hints
            highlight_attr = curses.color_pair(1) | curses.A_BOLD
            checkbox_attr = curses.color_pair(2)
        else:
            highlight_attr = curses.A_REVERSE
            checkbox_attr = curses.A_BOLD
        stdscr.keypad(True)

        env_file = default_env_file
        env_vals = _load_env_file(Path(env_file))
        source_uri = env_vals.get("DATABASE_URI", os.getenv("DATABASE_URI", "")).strip()
        if not source_uri:
            # Fallback to default SQLite DB if nothing is configured
            source_uri = "sqlite:////var/lib/bunkerweb/db.sqlite3"
        # Source host/port (optional; parsed from source_uri or editable)
        source_host = ""
        source_port = ""
        try:
            parsed = urlparse(source_uri)
            if parsed.hostname:
                source_host = parsed.hostname or ""
            if parsed.port is not None:
                source_port = str(parsed.port)
        except Exception:
            pass
        # Target config fields (used to build target_uri). Start empty so dry-run
        # users are not forced to have a destination configured.
        target_db_type = ""
        target_host = ""
        target_port = ""
        target_dbname = ""
        target_username = ""
        target_password = ""
        target_ssl = False
        root_ca_cert = ""
        target_uri = env_vals.get("DB_MIGRATION_TARGET_URI", os.getenv("DB_MIGRATION_TARGET_URI", "")).strip()

        # If target_uri exists, parse it to populate individual fields
        if target_uri:
            try:
                import re
                # Manual regex-based parsing to handle special chars (like /) in passwords
                # Pattern: scheme://[user[:password]@]host[:port][/dbname][?query]
                uri_pattern = r"^([a-z+]+)://(?:([^:@]+)(?::([^@]*))?@)?([^:/?]+)(?::(\d+))?(?:/([^?]*))?(?:\?(.*))?$"
                match = re.match(uri_pattern, target_uri)

                if match:
                    scheme, username, password, hostname, port, dbname, query = match.groups()

                    # Extract database type from scheme
                    if "postgres" in scheme:
                        target_db_type = "postgresql"
                    elif "mysql" in scheme:
                        target_db_type = "mysql"
                    elif "mariadb" in scheme:
                        target_db_type = "mariadb"
                    elif "sqlite" in scheme:
                        target_db_type = "sqlite"

                    if hostname:
                        target_host = hostname
                    if port:
                        target_port = port
                    if username:
                        target_username = username
                    if password:
                        target_password = password
                    if dbname:
                        target_dbname = dbname

                    # Check for SSL in query parameters
                    if query:
                        from urllib.parse import parse_qsl

                        # Simple containment checks for legacy values
                        if "ssl=true" in query or "sslmode=require" in query:
                            target_ssl = True
                        # Robustly parse key=value pairs to recover CA paths
                        for k, v in parse_qsl(query, keep_blank_values=True):
                            lk = (k or "").lower()
                            if lk in ("ssl_ca", "sslrootcert") and v:
                                root_ca_cert = v
                                target_ssl = True
                else:
                    # Fallback to standard urlparse
                    parsed = urlparse(target_uri)
                    if parsed.scheme and "postgres" in parsed.scheme:
                        target_db_type = "postgresql"
                    elif parsed.scheme and "mysql" in parsed.scheme:
                        target_db_type = "mysql"
                    if parsed.hostname:
                        target_host = parsed.hostname
                    if parsed.port:
                        target_port = str(parsed.port)
                    if parsed.username:
                        target_username = parsed.username
                    if parsed.password:
                        target_password = parsed.password
                    if parsed.path:
                        target_dbname = parsed.path.lstrip("/")
                    if parsed.query:
                        from urllib.parse import parse_qsl

                        q = parsed.query
                        if "ssl=true" in q or "sslmode=require" in q:
                            target_ssl = True
                        for k, v in parse_qsl(q, keep_blank_values=True):
                            lk = (k or "").lower()
                            if lk in ("ssl_ca", "sslrootcert") and v:
                                root_ca_cert = v
                                target_ssl = True
            except Exception as e:
                # If parsing fails, log and leave fields empty
                LOGGER.debug("Failed to parse target_uri from env file: %s", e)
        test_target = False
        update_env_file = True
        dry_run = False
        write_config_now = False
        show_password = False
        sql_snippet = ""

        selected = 0
        # Navigation indices for bottom action buttons.
        RUN_INDEX = 20
        QUIT_INDEX = 21
        # order:
        #  0 env_file
        #  1 source_uri
        #  2 source_host
        #  3 source_port
        #  4 target_db_type
        #  5 target_host
        #  6 target_port
        #  7 target_dbname
        #  8 target_username
        #  9 target_password
        # 10 generate_sql
        # 11 show_sql_command
        # 12 root_ca_cert
        # 13 target_ssl
        # 14 test_target_checkbox
        # 15 update_env_file_checkbox
        # 16 dry_run_checkbox
        # 17 write_config_button
        # 18 show_password_checkbox
        # 19 write_button
        # 20 run_button
        # 21 quit_button
        # Total selectable items (0 through 21 inclusive).
        total_items = 22

        def _apply_source_host_port() -> None:
            """Update source_uri with current source_host/source_port if both set and URI is non-sqlite."""
            nonlocal source_uri
            if not source_uri or source_uri.startswith("sqlite:"):
                return
            if not source_host and not source_port:
                return
            try:
                p = urlparse(source_uri)
                # netloc is user:pass@host:port; we replace host and/or port
                netloc = p.netloc
                if "@" in netloc:
                    userinfo, hostport = netloc.rsplit("@", 1)
                else:
                    userinfo, hostport = "", netloc
                if ":" in hostport:
                    cur_host, cur_port = hostport.rsplit(":", 1)
                else:
                    cur_host, cur_port = hostport, ""
                new_host = source_host or cur_host
                new_port = source_port or cur_port
                new_hostport = f"{new_host}:{new_port}" if new_port else new_host
                new_netloc = f"{userinfo}@{new_hostport}" if userinfo else new_hostport
                source_uri = urlunparse((p.scheme, new_netloc, p.path or "", p.params, p.query, p.fragment))
            except Exception:
                pass

        def _build_target_uri(mask_password: bool = False) -> str:
            db_type = target_db_type
            if not db_type:
                # No destination configured (common for source-only dry runs)
                return ""
            if db_type == "sqlite":
                # For sqlite, host/port/user/pass are ignored; reuse dbname as path
                path = target_dbname or "/var/lib/bunkerweb/db.sqlite3"
                if not path.startswith("/"):
                    path = "/" + path
                return f"sqlite:////{path.lstrip('/')}"

            if db_type == "postgresql":
                scheme = "postgresql+psycopg"
            elif db_type == "mysql":
                scheme = "mysql+pymysql"
            elif db_type == "mariadb":
                scheme = "mariadb+pymysql"
            else:
                scheme = db_type

            userinfo = ""
            if target_username:
                userinfo = target_username
                if target_password:
                    # Mask password for display, show actual password for final use
                    pwd_display = "***" if mask_password else target_password
                    userinfo += f":{pwd_display}"
                userinfo += "@"

            hostport = target_host or "localhost"
            if target_port:
                hostport = f"{hostport}:{target_port}"

            uri = f"{scheme}://{userinfo}{hostport}/{target_dbname or 'bunkerweb'}"

            # Add SSL/TLS parameters if enabled
            query_params = []
            if target_ssl:
                if db_type == "postgresql":
                    query_params.append("sslmode=require")
                    if root_ca_cert:
                        query_params.append(f"sslrootcert={root_ca_cert}")
                elif db_type in ("mysql", "mariadb"):
                    # Persist SSL intent in the URI so reloading the env file
                    # restores the checkbox state:
                    # - If a CA is provided, store ssl_ca=<path>
                    # - Otherwise, store ssl=true (later normalized before connect)
                    if root_ca_cert:
                        query_params.append(f"ssl_ca={root_ca_cert}")
                    else:
                        query_params.append("ssl=true")

            if query_params:
                uri += "?" + "&".join(query_params)
            return uri

        def _build_sql_snippet(pwd: str, mask_password: bool = False) -> str:
            dbname = target_dbname or "bunkerweb"
            user = target_username or "bunkerweb"
            display_pwd = "***" if mask_password else pwd
            if target_db_type == "postgresql":
                return (
                    f"-- PostgreSQL Database and User Configuration\n"
                    f"CREATE DATABASE {dbname};\n"
                    f"CREATE USER {user} WITH ENCRYPTED PASSWORD '{display_pwd}';\n"
                    f"GRANT ALL PRIVILEGES ON DATABASE {dbname} TO {user};\n"
                    f"ALTER DATABASE {dbname} OWNER TO {user};\n"
                    f"\n-- Connect as the new user to verify\n"
                    f"-- psql -h <host> -U {user} -d {dbname}"
                )
            if target_db_type in ("mysql", "mariadb"):
                return (
                    f"-- MySQL/MariaDB Database and User Configuration\n"
                    f"CREATE DATABASE {dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
                    f"CREATE USER '{user}'@'%' IDENTIFIED BY '{display_pwd}';\n"
                    f"GRANT ALL PRIVILEGES ON {dbname}.* TO '{user}'@'%';\n"
                    f"GRANT CREATE TEMPORARY TABLES ON {dbname}.* TO '{user}'@'%';\n"
                    f"FLUSH PRIVILEGES;\n"
                    f"\n-- Verify user and database\n"
                    f"-- SELECT user, host FROM mysql.user WHERE user='{user}';\n"
                    f"-- SHOW DATABASES LIKE '{dbname}';"
                )
            # sqlite: no SQL to create user/db, only file path
            sqlite_path = target_dbname or "/var/lib/bunkerweb/db.sqlite3"
            return (
                f"-- SQLite Configuration\n"
                f"-- SQLite does not require user/database creation\n"
                f"-- Database file will be created at: {sqlite_path}\n"
                f"-- Ensure the directory exists and has appropriate permissions:\n"
                f"-- mkdir -p $(dirname {sqlite_path})\n"
                f"-- chmod 755 $(dirname {sqlite_path})"
            )

        def _show_sql_modal(masked_sql: str, unmasked_sql: str, start_show_password: bool) -> None:
            """
            Display SQL command in a modal popup.

            Controls:
              - Space: toggle show/hide password
              - q / Escape: close
            """
            show_pwd = start_show_password
            while True:
                stdscr.erase()
                max_y, max_x = stdscr.getmaxyx()

                # Title
                title = "SQL Command to Execute"
                stdscr.addstr(1, 2, title, highlight_attr)
                stdscr.addstr(2, 2, "Space: toggle password  q/Esc: close"[: max_x - 4])

                # Display SQL with line wrapping
                sql_text = unmasked_sql if show_pwd else masked_sql
                lines = sql_text.splitlines()
                display_start = 4
                for i, line in enumerate(lines):
                    if display_start + i >= max_y - 2:
                        break
                    # Wrap long lines
                    if len(line) > max_x - 6:
                        # Simple wrapping: just truncate with ellipsis
                        stdscr.addstr(display_start + i, 4, line[: max_x - 10] + "...", curses.A_NORMAL)
                    else:
                        stdscr.addstr(display_start + i, 4, line, curses.A_NORMAL)
                    stdscr.clrtoeol()

                # Footer
                if display_start + len(lines) + 2 < max_y:
                    footer = "[x] Show password" if show_pwd else "[ ] Show password"
                    stdscr.addstr(max_y - 2, 2, f"{footer}   Space: toggle   q/Esc: close"[: max_x - 4], checkbox_attr)

                stdscr.refresh()
                key = stdscr.getch()

                # Exit on q, Q, or Escape (27)
                if key in (ord("q"), ord("Q"), 27):
                    return
                # Toggle password display
                if key == ord(" "):
                    show_pwd = not show_pwd

        def _pick_from_list(title: str, options: list[str], current: str) -> str:
            idx = options.index(current) if current in options else 0
            offset = 0
            while True:
                stdscr.erase()
                stdscr.addstr(1, 2, title)
                stdscr.addstr(2, 2, "Up/Down selects. Enter confirms. q cancels.")
                h, _w = stdscr.getmaxyx()
                top = 4
                height = max(1, h - top - 2)
                if idx < offset:
                    offset = idx
                elif idx >= offset + height:
                    offset = idx - height + 1
                visible = options[offset : offset + height]
                for i, opt in enumerate(visible):
                    real = offset + i
                    prefix = "➜ " if real == idx else "  "
                    attr = highlight_attr if real == idx else curses.A_NORMAL
                    stdscr.addstr(top + i, 2, f"{prefix}{opt}", attr)
                    stdscr.clrtoeol()
                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord("q"), ord("Q")):
                    return current
                if key in (curses.KEY_UP, ord("k")):
                    idx = max(0, idx - 1)
                elif key in (curses.KEY_DOWN, ord("j")):
                    idx = min(len(options) - 1, idx + 1)
                elif key in (curses.KEY_ENTER, 10, 13):
                    return options[idx]

        def _file_picker(initial_path: str) -> Optional[str]:
            """
            Simple filesystem browser to select a file.

            Controls:
              - Up/Down: move
              - Enter: open dir / select file
              - Backspace: parent dir
              - q: cancel
            """
            current = Path(initial_path).expanduser()
            if current.is_file():
                current_dir = current.parent
                selected_name = current.name
            else:
                current_dir = current if current.is_dir() else Path("/")
                selected_name = ""

            cursor = 0
            offset = 0

            while True:
                stdscr.erase()
                stdscr.addstr(1, 2, "Select env file")
                stdscr.addstr(2, 2, f"Directory: {str(current_dir)}")
                stdscr.addstr(3, 2, "Enter=open/select  Backspace=up  q=cancel")

                try:
                    entries = sorted(current_dir.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                except Exception as exc:
                    stdscr.addstr(5, 2, f"Unable to list directory: {exc}")
                    stdscr.addstr(7, 2, "Press Backspace to go up or q to cancel.")
                    stdscr.refresh()
                    key = stdscr.getch()
                    if key in (ord("q"), ord("Q")):
                        return None
                    if key in (curses.KEY_BACKSPACE, 127, 8):
                        parent = current_dir.parent
                        if parent != current_dir:
                            current_dir = parent
                        continue
                    continue

                # Add explicit parent entry (except at filesystem root)
                display_entries = []
                if current_dir.parent != current_dir:
                    display_entries.append(("..", current_dir.parent, True))
                for p in entries:
                    display_entries.append((p.name + ("/" if p.is_dir() else ""), p, p.is_dir()))

                if selected_name:
                    for i, (label, p, _) in enumerate(display_entries):
                        if p.name == selected_name:
                            cursor = i
                            break
                    selected_name = ""

                height, width = stdscr.getmaxyx()
                list_top = 5
                list_height = max(1, height - list_top - 2)
                cursor = max(0, min(cursor, len(display_entries) - 1)) if display_entries else 0

                if cursor < offset:
                    offset = cursor
                elif cursor >= offset + list_height:
                    offset = cursor - list_height + 1

                visible = display_entries[offset : offset + list_height]
                for i, (label, _p, _is_dir) in enumerate(visible):
                    idx = offset + i
                    prefix = "➜ " if idx == cursor else "  "
                    line = f"{prefix}{label}"
                    attr = highlight_attr if idx == cursor else curses.A_NORMAL
                    stdscr.addstr(list_top + i, 2, line[: max(1, width - 4)], attr)
                    stdscr.clrtoeol()

                stdscr.refresh()
                key = stdscr.getch()
                if key in (ord("q"), ord("Q")):
                    return None
                if key in (curses.KEY_UP, ord("k")):
                    cursor = max(0, cursor - 1)
                    continue
                if key in (curses.KEY_DOWN, ord("j")):
                    cursor = min(max(0, len(display_entries) - 1), cursor + 1)
                    continue
                if key in (curses.KEY_BACKSPACE, 127, 8):
                    parent = current_dir.parent
                    if parent != current_dir:
                        current_dir = parent
                        cursor = 0
                        offset = 0
                    continue
                if key in (curses.KEY_ENTER, 10, 13):
                    if not display_entries:
                        continue
                    _label, chosen, is_dir = display_entries[cursor]
                    if is_dir:
                        current_dir = chosen
                        cursor = 0
                        offset = 0
                        continue
                    return str(chosen)

        def _draw() -> None:
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()
            stdscr.addstr(1, 2, "BunkerWeb DB migrate (TUI)"[: max_x - 4], highlight_attr)
            stdscr.addstr(2, 2, "Up/Down selects. Enter edits/activates. Space toggles checkbox."[: max_x - 4])

            def _item(y: int, idx: int, label: str, value: str) -> None:
                is_sel = selected == idx
                prefix = "➜ " if is_sel else "  "
                attr = highlight_attr if is_sel else curses.A_NORMAL
                stdscr.addstr(y, 2, f"{prefix}{label}{value}", attr)
                stdscr.clrtoeol()

            _item(5, 0, "Env file: ", env_file[: max_x - 20])
            _item(6, 1, "Source DATABASE_URI: ", source_uri[: max_x - 30])
            _item(7, 2, "Source host: ", source_host[: max_x - 20])
            _item(8, 3, "Source port: ", source_port[: max_x - 20])

            _item(10, 4, "Target DB type: ", target_db_type[: max_x - 25])
            _item(11, 5, "Target host: ", target_host[: max_x - 25])
            _item(12, 6, "Target port: ", target_port[: max_x - 25])
            _item(13, 7, "Target database: ", target_dbname[: max_x - 25])
            _item(14, 8, "Target username: ", target_username[: max_x - 25])
            pw_display = ""
            if target_password:
                # Show either stars or the real password, plus a small checkbox
                # hint to toggle masking.
                visible = target_password if show_password else "*" * len(target_password)
                checkbox = f"  [{'x' if show_password else ' '}] Show"
                pw_display = (visible + checkbox)[: max_x - 25]
            _item(15, 9, "Target password: ", pw_display)

            # Generate password button - only enabled if database type is selected
            gen_prefix = "➜ " if selected == 10 else "  "
            gen_label = "Generate SQL & password (Enter)" if target_db_type else "[Requires DB type selection]"
            gen_attr = highlight_attr if selected == 10 and target_db_type else (curses.A_DIM if not target_db_type else curses.A_NORMAL)
            stdscr.addstr(16, 2, f"{gen_prefix}{gen_label}"[: max_x - 4], gen_attr)
            stdscr.clrtoeol()

            # Show SQL button - always available if database type is selected
            sql_prefix = "➜ " if selected == 11 else "  "
            sql_label = "Show SQL command (Enter)" if target_db_type else "[Requires DB type selection]"
            sql_attr = highlight_attr if selected == 11 and target_db_type else (curses.A_DIM if not target_db_type else curses.A_NORMAL)
            stdscr.addstr(17, 2, f"{sql_prefix}{sql_label}"[: max_x - 4], sql_attr)
            stdscr.clrtoeol()

            # Root CA certificate selector
            root_ca_display = root_ca_cert[: max_x - 25] if root_ca_cert else "(not set)"
            _item(18, 12, "Root CA certificate: ", root_ca_display)

            ssl_prefix = "➜ " if selected == 13 else "  "
            if 20 < max_y - 1:
                ssl_attr = highlight_attr if selected == 13 else checkbox_attr
                stdscr.addstr(20, 2, f"{ssl_prefix}[{'x' if target_ssl else ' '}] SSL (yes/no)"[: max_x - 4], ssl_attr)
                stdscr.clrtoeol()

            preview = _build_target_uri(mask_password=True)
            if 22 < max_y - 1:
                stdscr.addstr(22, 2, "Target URI preview (password masked):"[: max_x - 4], checkbox_attr)
            if 23 < max_y - 1:
                stdscr.addstr(23, 2, preview[: max(1, max_x - 4)])
                stdscr.clrtoeol()
            if 24 < max_y - 1:
                stdscr.addstr(24, 2, "→ Password is hidden. Use 'Show SQL command' to view and copy."[: max_x - 4], checkbox_attr)

            base_y = 26

            cb_prefix = "➜ " if selected == 14 else "  "
            if base_y < max_y - 1:
                cb_attr = highlight_attr if selected == 14 else checkbox_attr
                stdscr.addstr(
                    base_y,
                    2,
                    f"{cb_prefix}[{'x' if test_target else ' '}] Test target only (no migrations/copy)"[: max_x - 4],
                    cb_attr,
                )
                stdscr.clrtoeol()

            upd_prefix = "➜ " if selected == 15 else "  "
            if base_y + 1 < max_y - 1:
                upd_attr = highlight_attr if selected == 15 else checkbox_attr
                stdscr.addstr(
                    base_y + 1,
                    2,
                    f"{upd_prefix}[{'x' if update_env_file else ' '}] Update env file on success"[: max_x - 4],
                    upd_attr,
                )
                stdscr.clrtoeol()

            dry_prefix = "➜ " if selected == 16 else "  "
            if base_y + 2 < max_y - 1:
                dry_attr = highlight_attr if selected == 16 else checkbox_attr
                stdscr.addstr(
                    base_y + 2,
                    2,
                    f"{dry_prefix}[{'x' if dry_run else ' '}] Dry run (no schema or data changes)"[: max_x - 4],
                    dry_attr,
                )
                stdscr.clrtoeol()

            cfg_prefix = "➜ " if selected == 17 else "  "
            if base_y + 3 < max_y - 1:
                cfg_attr = highlight_attr if selected == 17 else checkbox_attr
                stdscr.addstr(
                    base_y + 3,
                    2,
                    f"{cfg_prefix}[{'x' if write_config_now else ' '}] Write config to env file now (skip migration)"[: max_x - 4],
                    cfg_attr,
                )
                stdscr.clrtoeol()

            show_pwd_prefix = "➜ " if selected == 18 else "  "
            if base_y + 4 < max_y - 1:
                show_pwd_attr = highlight_attr if selected == 18 else checkbox_attr
                stdscr.addstr(
                    base_y + 4,
                    2,
                    f"{show_pwd_prefix}[{'x' if show_password else ' '}] Show password in SQL command"[: max_x - 4],
                    show_pwd_attr,
                )
                stdscr.clrtoeol()

            write_prefix = "[WRITE]" if selected == 19 else " WRITE "
            run_prefix = "[ RUN ]" if selected == 20 else "  RUN  "
            quit_prefix = "[ QUIT ]" if selected == 21 else "  QUIT "
            if base_y + 6 < max_y - 1:
                write_attr = highlight_attr if selected == 19 else checkbox_attr
                run_attr = highlight_attr if selected == 20 else checkbox_attr
                quit_attr = highlight_attr if selected == 21 else checkbox_attr
                stdscr.addstr(base_y + 6, 2, write_prefix[: max_x - 4], write_attr)
                stdscr.addstr(base_y + 6, 10, run_prefix[: max_x - 14], run_attr)
                stdscr.addstr(base_y + 6, 20, quit_prefix[: max_x - 24], quit_attr)
                stdscr.clrtoeol()

            if base_y + 8 < max_y - 1:
                stdscr.addstr(
                    base_y + 8,
                    2,
                    "Tip: Fill target fields, verify preview, then select RUN and press Enter."[: max_x - 4],
                    checkbox_attr,
                )
            stdscr.refresh()

        def _edit_line(y: int, label: str, current: str, *, secret: bool = False) -> str:
            stdscr.move(y, 0)
            stdscr.clrtoeol()
            stdscr.addstr(y, 2, label)
            if not secret:
                stdscr.addstr(y, 2 + len(label), current)
                stdscr.clrtoeol()
                curses.echo()
                stdscr.move(y, 2 + len(label) + len(current))
                raw = stdscr.getstr(y, 2 + len(label), 4096)
                value = raw.decode(errors="replace").strip()
                curses.noecho()
                return value or current

            # Secret input: show '*' for each character, or plain text when
            # "Show" is enabled for the password field.
            curses.noecho()
            buf = list(current)
            x0 = 2 + len(label)
            while True:
                stdscr.move(y, 0)
                stdscr.clrtoeol()
                stdscr.addstr(y, 2, label)
                display = "".join(buf) if show_password else "*" * len(buf)
                stdscr.addstr(y, x0, display[: 4096])
                stdscr.clrtoeol()
                stdscr.move(y, x0 + len(display))
                ch = stdscr.getch()
                if ch in (curses.KEY_ENTER, 10, 13):
                    break
                if ch in (27,):  # Escape cancels edits
                    buf = list(current)
                    break
                if ch in (curses.KEY_BACKSPACE, 127, 8):
                    if buf:
                        buf.pop()
                    continue
                if 32 <= ch <= 126:
                    buf.append(chr(ch))
                    continue

            value = "".join(buf).strip() or current

            # Show inline hint about potentially problematic characters.
            bad_chars = ['"', "'", " ", "\\", "`", "$"]
            present = [ch for ch in bad_chars if ch in value]
            stdscr.move(y + 1, 0)
            stdscr.clrtoeol()
            if present:
                stdscr.addstr(
                    y + 1,
                    4,
                    "Warning: password contains characters that may need escaping in env/URI: "
                    + " ".join(repr(ch) for ch in present),
                )
            stdscr.refresh()

            return value

        while True:
            _draw()
            key = stdscr.getch()

            if key in (ord("q"), ord("Q")):
                raise KeyboardInterrupt
            if key in (ord("g"), ord("G")):
                # Generate random password and SQL snippet for current target DB
                gen_pwd = _generate_password()
                if not target_username:
                    target_username = "bunkerweb"
                if not target_dbname:
                    target_dbname = "bunkerweb"
                target_password = gen_pwd
                sql_snippet = _build_sql_snippet(gen_pwd)
                continue
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % total_items
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % total_items
                continue
            if key in (curses.KEY_LEFT, ord('h')):
                if selected == RUN_INDEX:
                    selected = QUIT_INDEX
                elif selected == QUIT_INDEX:
                    selected = RUN_INDEX
                continue
            if key in (curses.KEY_RIGHT, ord('l')):
                if selected == RUN_INDEX:
                    selected = QUIT_INDEX
                elif selected == QUIT_INDEX:
                    selected = RUN_INDEX
                continue
            if key == ord(" "):
                if selected == 9:
                    show_password = not show_password
                if selected == 13:
                    target_ssl = not target_ssl
                if selected == 14:
                    test_target = not test_target
                if selected == 15:
                    update_env_file = not update_env_file
                if selected == 16:
                    dry_run = not dry_run
                if selected == 17:
                    write_config_now = not write_config_now
                if selected == 18:
                    show_password = not show_password
                continue
            if key in (curses.KEY_ENTER, 10, 13):
                if selected == 0:
                    picked = _file_picker(env_file)
                    if picked:
                        env_file = picked
                    env_vals = _load_env_file(Path(env_file))
                    # Always refresh source URI/host/port from the selected env file when DATABASE_URI is present.
                    if env_vals.get("DATABASE_URI"):
                        source_uri = env_vals["DATABASE_URI"].strip()
                    elif not source_uri:
                        # Fallback to default SQLite if nothing is defined
                        source_uri = "sqlite:////var/lib/bunkerweb/db.sqlite3"
                    if source_uri:
                        try:
                            p = urlparse(source_uri)
                            if p.hostname:
                                source_host = p.hostname
                            if p.port is not None:
                                source_port = str(p.port)
                        except Exception:
                            pass
                    continue
                if selected == 1:
                    source_uri = _edit_line(6, "Source DATABASE_URI: ", source_uri)
                    if source_uri:
                        try:
                            p = urlparse(source_uri)
                            if p.hostname:
                                source_host = p.hostname
                            if p.port is not None:
                                source_port = str(p.port)
                        except Exception:
                            pass
                    continue
                if selected == 2:
                    source_host = _edit_line(7, "Source host: ", source_host)
                    _apply_source_host_port()
                    continue
                if selected == 3:
                    source_port = _edit_line(8, "Source port: ", source_port)
                    _apply_source_host_port()
                    continue
                if selected == 4:
                    target_db_type = _pick_from_list("Target DB type", ["postgresql", "mysql", "mariadb", "sqlite"], target_db_type)
                    if target_db_type == "postgresql" and not target_port:
                        target_port = "5432"
                    if target_db_type in ("mysql", "mariadb") and not target_port:
                        target_port = "3306"
                    continue
                if selected == 5:
                    target_host = _edit_line(11, "Target host: ", target_host)
                    continue
                if selected == 6:
                    target_port = _edit_line(12, "Target port: ", target_port)
                    continue
                if selected == 7:
                    target_dbname = _edit_line(13, "Target database: ", target_dbname)
                    continue
                if selected == 8:
                    target_username = _edit_line(14, "Target username: ", target_username)
                    continue
                if selected == 9:
                    target_password = _edit_line(15, "Target password: ", "", secret=True) if not target_password else _edit_line(15, "Target password: ", target_password, secret=True)
                    continue
                if selected == 10:
                    # Generate password button - requires database type selection
                    if not target_db_type:
                        continue
                    gen_pwd = _generate_password()
                    if not target_username:
                        target_username = "bunkerweb"
                    if not target_dbname:
                        target_dbname = "bunkerweb"
                    target_password = gen_pwd
                    sql_snippet = _build_sql_snippet(gen_pwd)
                    continue
                if selected == 11:
                    # Show SQL command button - requires database type selection
                    if not target_db_type:
                        continue
                    display_pwd = target_password or "YOUR_PASSWORD_HERE"
                    masked_sql = _build_sql_snippet(display_pwd, mask_password=True)
                    unmasked_sql = _build_sql_snippet(display_pwd, mask_password=False)
                    _show_sql_modal(masked_sql, unmasked_sql, show_password)
                    continue
                if selected == 12:
                    # Root CA certificate file picker
                    picked = _file_picker(root_ca_cert or "/etc/ssl/certs/")
                    if picked:
                        root_ca_cert = str(picked)
                        # If a CA is chosen, automatically enable SSL.
                        target_ssl = True
                    # Update preview when CA is selected
                    continue
                if selected == 13:
                    target_ssl = not target_ssl
                    # Update preview when SSL is toggled
                    continue
                if selected == 14:
                    test_target = not test_target
                    continue
                if selected == 15:
                    update_env_file = not update_env_file
                    continue
                if selected == 16:
                    dry_run = not dry_run
                    continue
                if selected == 17:
                    write_config_now = not write_config_now
                    continue
                if selected == 19:
                    # Write config to env file now (without migration)
                    _apply_source_host_port()
                    target_uri = _build_target_uri(mask_password=False)
                    return env_file, source_uri.strip(), target_uri.strip(), False, True, False, True
                if selected == 20:
                    _apply_source_host_port()
                    target_uri = _build_target_uri(mask_password=False)
                    return env_file, source_uri.strip(), target_uri.strip(), test_target, update_env_file, dry_run, write_config_now
                if selected == 21:
                    raise KeyboardInterrupt

    return curses.wrapper(_tui_main)


def _ensure_target_empty(engine: Engine) -> None:
    """
    Raise if any of the known BunkerWeb tables already contain rows in the target DB.
    """
    from sqlalchemy import inspect

    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_tables = {t.lower() for t in inspector.get_table_names()}

        non_empty: Dict[str, int] = {}
        for table in Base.metadata.sorted_tables:
            if table.name.lower() not in existing_tables:
                # Table does not exist yet on target – fine, Alembic will create it.
                continue
            result = conn.execute(text(f"SELECT COUNT(1) FROM {table.name}"))
            count = result.scalar_one()
            if count:
                non_empty[table.name] = count

        if non_empty:
            raise RuntimeError(f"Target database is not empty for BunkerWeb tables: {non_empty}")


def _run_alembic_upgrade(target_uri: str) -> None:
    """
    Run Alembic migrations up to head on the target URI.
    Catches and suppresses SystemExit(0) from Alembic, which is normal behavior.
    """
    from alembic import command
    from alembic.config import Config

    # Support both source layout (src/common/db/alembic) and installed layout (db/alembic).
    candidates = [
        REPO_ROOT / "src" / "common" / "db" / "alembic" / "alembic.ini",
        REPO_ROOT / "db" / "alembic" / "alembic.ini",
    ]
    alembic_ini = next((p for p in candidates if p.is_file()), None)
    if alembic_ini is None:
        raise RuntimeError(f"alembic.ini not found in expected locations under {REPO_ROOT}")

    cfg = Config(str(alembic_ini))
    # Set script_location to absolute path so Alembic can find env.py
    alembic_dir = alembic_ini.parent
    cfg.set_main_option("script_location", str(alembic_dir))
    # Alembic ini may be empty for sqlalchemy.url; we override it here.
    cfg.set_main_option("sqlalchemy.url", target_uri.replace("%", "%%"))
    # Prevent Alembic's fileConfig() from disabling our existing loggers.
    # alembic.ini has a [loggers] section which triggers fileConfig() with
    # disable_existing_loggers=True (Python's default), wiping out our handlers.
    cfg.config_file_name = None

    # Pre-set version_locations to the absolute path for the target DB type so
    # Alembic finds the right migration scripts regardless of CWD.
    # env.py will later call config.set_main_option("version_locations", relative_path)
    # which would override this; we freeze the key by monkey-patching set_main_option
    # to ignore any subsequent write to "version_locations".
    from sqlalchemy.engine.url import make_url as _make_url
    _db_type = (_make_url(target_uri).drivername or "").split("+")[0].split(":")[0]
    _versions_dir = alembic_dir / f"{_db_type}_versions"
    if _versions_dir.is_dir():
        cfg.set_main_option("version_locations", str(_versions_dir))
        LOGGER.info("Using migration version_locations: %s", _versions_dir)
    else:
        LOGGER.warning("version_locations directory not found: %s — Alembic may find no migrations", _versions_dir)

    # Freeze version_locations: prevent env.py from overriding our absolute path
    _orig_set = cfg.set_main_option
    def _frozen_set(name: str, value: str) -> None:
        if name == "version_locations":
            return  # already set to absolute path above
        _orig_set(name, value)
    cfg.set_main_option = _frozen_set  # type: ignore[method-assign]

    # Create the full schema using the ORM model (same as Database.py line 726).
    # BunkerWeb's Alembic migrations are incremental (ALTER TABLE, etc.) and assume
    # the base schema already exists. For a fresh target database we must create all
    # tables first, then stamp Alembic at head so future upgrades work correctly.
    LOGGER.info("Creating target schema via Base.metadata.create_all()...")
    target_engine = _create_engine(target_uri)
    Base.metadata.create_all(target_engine, checkfirst=True)
    LOGGER.info("Target schema created successfully.")

    # Snapshot our root logger configuration; Alembic may reconfigure logging
    # even without fileConfig if it calls basicConfig internally.
    root_logger = logging.getLogger()
    saved_root_level = root_logger.level
    saved_root_handlers = list(root_logger.handlers)
    our_logger = logging.getLogger("bw_db_migrate")
    saved_our_level = our_logger.level
    saved_our_handlers = list(our_logger.handlers)

    # env.py overrides sqlalchemy.url from the DATABASE_URI env var; temporarily
    # point it at the target so the stamp is recorded there, not on the source.
    old_db_uri = os.environ.get("DATABASE_URI")
    os.environ["DATABASE_URI"] = target_uri

    try:
        # Stamp Alembic at head: records that the schema is up-to-date without
        # running any migration scripts (which would fail on a fresh schema).
        command.stamp(cfg, "head")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 0
        if code != 0:
            raise
    finally:
        # Restore DATABASE_URI env var
        if old_db_uri is not None:
            os.environ["DATABASE_URI"] = old_db_uri
        else:
            os.environ.pop("DATABASE_URI", None)
        # Restore logging state so subsequent log calls are visible
        root_logger.setLevel(saved_root_level)
        for h in saved_root_handlers:
            if h not in root_logger.handlers:
                root_logger.addHandler(h)
        our_logger.setLevel(saved_our_level)
        for h in saved_our_handlers:
            if h not in our_logger.handlers:
                our_logger.addHandler(h)

    LOGGER.info("Alembic stamped at head on target database.")


def _save_target_uri_to_env_file(env_file: Path, target_uri: str) -> None:
    """
    Save target URI to env file as DB_MIGRATION_TARGET_URI (without switching current DB).
    Used when user wants to save config for later migration.
    """
    if not env_file.exists():
        LOGGER.warning("Env file %s does not exist, skipping update.", env_file)
        return

    # Check that the directory is writable and that there is enough free disk space
    env_dir = env_file.parent
    if not os.access(env_dir, os.W_OK):
        LOGGER.error("Directory %s is not writable by current user, cannot update env file.", env_dir)
        return

    try:
        usage = shutil.disk_usage(env_dir)
        current_size = env_file.stat().st_size
        # Require at least twice the current file size or 16 KiB free, whichever is larger
        required_free = max(current_size * 2, 16 * 1024)
        if usage.free < required_free:
            LOGGER.error(
                "Not enough free disk space in %s to safely update env file. "
                "Required at least %d bytes free, found %d bytes.",
                env_dir,
                required_free,
                usage.free,
            )
            return
    except Exception as exc:
        LOGGER.error("Failed to check disk space for %s: %s", env_dir, exc)
        return

    # Create backup first: <name>.<YYMMDD-HHSS>.bak
    timestamp = datetime.now().strftime("%y%m%d-%H%S")
    backup_path = env_file.with_name(f"{env_file.name}.{timestamp}.bak")
    try:
        shutil.copy2(env_file, backup_path)
        LOGGER.info("Created env file backup at %s.", backup_path)
    except Exception as exc:
        LOGGER.error("Failed to create env file backup %s: %s", backup_path, exc)
        return

    lines = env_file.read_text(encoding="utf-8", errors="replace").splitlines()
    commented_keys = ("DB_MIGRATION_TARGET_URI",)
    new_lines = []
    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            new_lines.append(raw)
            continue
        if any(stripped.startswith(f"{k}=") or stripped.startswith(f"export {k}=") for k in commented_keys):
            # Comment out existing DB_MIGRATION_TARGET_URI line
            new_lines.append(f"# {raw}")
        else:
            new_lines.append(raw)

    new_lines.append("")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_lines.append(f"# Target database configuration (saved by bw_db_migrate at {timestamp}, not yet migrated)")
    new_lines.append(f"DB_MIGRATION_TARGET_URI={target_uri}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    LOGGER.info("Updated env file %s with target database URI.", env_file)


def _update_env_file_on_success(env_file: Path, target_uri: str) -> None:
    """
    Comment out old DATABASE_* and DB_MIGRATION* lines and append new DATABASE_URI
    pointing to the migrated backend.
    """
    if not env_file.exists():
        LOGGER.warning("Env file %s does not exist, skipping update.", env_file)
        return

    # Check that the directory is writable and that there is enough free disk space
    env_dir = env_file.parent
    if not os.access(env_dir, os.W_OK):
        LOGGER.error("Directory %s is not writable by current user, cannot update env file.", env_dir)
        return

    try:
        usage = shutil.disk_usage(env_dir)
        current_size = env_file.stat().st_size
        # Require at least twice the current file size or 16 KiB free, whichever is larger
        required_free = max(current_size * 2, 16 * 1024)
        if usage.free < required_free:
            LOGGER.error(
                "Not enough free disk space in %s to safely update env file. "
                "Required at least %d bytes free, found %d bytes.",
                env_dir,
                required_free,
                usage.free,
            )
            return
    except Exception as exc:
        LOGGER.error("Failed to check disk space for %s: %s", env_dir, exc)
        return

    # Create backup first: <name>.<YYMMDD-HHSS>.bak
    timestamp = datetime.now().strftime("%y%m%d-%H%S")
    backup_path = env_file.with_name(f"{env_file.name}.{timestamp}.bak")
    try:
        shutil.copy2(env_file, backup_path)
        LOGGER.info("Created env file backup at %s.", backup_path)
    except Exception as exc:
        LOGGER.error("Failed to create env file backup %s: %s", backup_path, exc)
        return

    lines = env_file.read_text(encoding="utf-8", errors="replace").splitlines()
    commented_keys = ("DATABASE_URI", "DATABASE_URI_READONLY", "DB_MIGRATION", "DB_MIGRATION_TARGET_URI")
    new_lines = []
    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            new_lines.append(raw)
            continue
        if any(stripped.startswith(f"{k}=") or stripped.startswith(f"export {k}=") for k in commented_keys):
            # Comment out existing DB-related lines with a clear hint
            new_lines.append(f"# commented out old settings by bw_db_migrate: {raw}")
        else:
            new_lines.append(raw)

    new_lines.append("")
    new_lines.append("# Updated by bw_db_migrate after successful migration")
    new_lines.append(f"DATABASE_URI={target_uri}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    LOGGER.info("Updated env file %s with new DATABASE_URI.", env_file)


def _copy_all_data(source_engine: Engine, target_engine: Engine) -> None:
    """
    Copy all rows from each known table from source to target.
    Initial implementation loads entire tables; for very large databases
    this can be extended to use batching/streaming.
    """
    batch_size = 100
    tables = list(Base.metadata.sorted_tables)
    total_tables = max(1, len(tables))

    with source_engine.connect() as src_conn:
        table_row_counts: Dict[str, int] = {}
        total_rows = 0
        for table in tables:
            count = src_conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one()
            table_row_counts[table.name] = int(count)
            total_rows += int(count)

    rows_done = 0
    tables_done = 0
    start = time.monotonic()

    try:
        with source_engine.connect() as src_conn, target_engine.begin() as tgt_conn:
                for idx, table in enumerate(tables, start=1):
                    table_total = table_row_counts.get(table.name, 0)
                    LOGGER.info("Copying table %s (%s rows) ...", table.name, table_total)

                    table_done = 0
                    if table_total == 0:
                        tables_done += 1
                        elapsed = time.monotonic() - start
                        _progress(f"Tables {tables_done}/{total_tables} | Rows {rows_done}/{total_rows} | Last {table.name} (0 rows) | {elapsed:.1f}s")
                        continue

                    while table_done < table_total:
                        _progress(
                            f"[{idx}/{total_tables}] Copying {table.name} "
                            f"({table_done}/{table_total}) | Tables {tables_done}/{total_tables} | Rows {rows_done}/{total_rows}"
                        )
                        try:
                            rows = list(
                                src_conn.execute(
                                    text(f"SELECT * FROM {table.name} LIMIT :limit OFFSET :offset"),
                                    {"limit": batch_size, "offset": table_done},
                                )
                            )
                            if not rows:
                                break
                            insert_stmt = table.insert()
                            tgt_conn.execute(insert_stmt, [dict(row._mapping) for row in rows])
                            table_done += len(rows)
                            rows_done += len(rows)
                        except Exception as e:
                            _progress_done()
                            error_msg = f"Error copying table {table.name} at offset {table_done}: {e}"
                            LOGGER.error(error_msg)
                            # Write to file to ensure we capture the error
                            with open("/tmp/bw_db_migrate_error.log", "a") as f:
                                f.write(error_msg + "\n")
                                f.write(f"Table: {table.name}, Done: {table_done}/{table_total}\n")
                            sys.stderr.write(error_msg + "\n")
                            sys.stderr.flush()
                            raise

                    tables_done += 1
                    elapsed = time.monotonic() - start
                    _progress(f"Tables {tables_done}/{total_tables} | Rows {rows_done}/{total_rows} | Finished {table.name} | {elapsed:.1f}s")

        _progress_done()
    except Exception as e:
        _progress_done()
        error_msg = f"Fatal error during data copy: {e}"
        LOGGER.error(error_msg)
        with open("/tmp/bw_db_migrate_error.log", "a") as f:
            f.write(error_msg + "\n")
            import traceback
            f.write(traceback.format_exc() + "\n")
        sys.stderr.write(error_msg + "\n")
        sys.stderr.flush()
        raise


def _verify_all_data(source_engine: Engine, target_engine: Engine) -> None:
    """
    Verify that per-table row counts match between source and target.
    """
    tables = list(Base.metadata.sorted_tables)
    total = max(1, len(tables))
    with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
        start = time.monotonic()
        for idx, table in enumerate(tables, start=1):
            _progress(f"[{idx}/{total}] Verifying {table.name} ...")
            src_count = src_conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one()
            tgt_count = tgt_conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one()
            if src_count != tgt_count:
                _progress_done()
                raise RuntimeError(f"Row count mismatch for {table.name}: source={src_count}, target={tgt_count}")
            LOGGER.info("Verified table %s: %s rows", table.name, src_count)
            elapsed = time.monotonic() - start
            _progress(f"[{idx}/{total}] Verified {table.name} ({src_count} rows) in {elapsed:.1f}s")
    _progress_done()


_DUMP_BATCH_SIZE = 500  # rows per INSERT batch


def _dump_source_to_files(source_engine: Engine, dump_dir: Path) -> None:
    """
    Dump source database to per-table JSONL files using SQLAlchemy.
    Each line in a .jsonl file is one row serialised as a JSON object.
    Binary columns are base64-encoded and marked with a __b64__ wrapper so
    the importer can restore them as bytes.
    """
    import json
    import base64

    dump_dir.mkdir(parents=True, exist_ok=True)
    tables = list(Base.metadata.sorted_tables)
    total_tables = max(1, len(tables))

    def _serialise(v: object) -> object:
        if v is None:
            return None
        if isinstance(v, (bool, int, float, str)):
            return v
        if isinstance(v, (bytes, bytearray)):
            return {"__b64__": base64.b64encode(bytes(v)).decode()}
        # datetime, date, Decimal, etc. → str
        return str(v)

    with source_engine.connect() as conn:
        for idx, table in enumerate(tables, start=1):
            table_file = dump_dir / f"{table.name}.jsonl"
            LOGGER.info("[%d/%d] Dumping table %s ...", idx, total_tables, table.name)
            _progress(f"[{idx}/{total_tables}] Dumping {table.name}")
            row_count = 0
            with table_file.open("w", encoding="utf-8") as fh:
                result = conn.execute(text(f"SELECT * FROM {table.name}"))
                cols = list(result.keys())
                for row in result:
                    fh.write(json.dumps({c: _serialise(row._mapping[c]) for c in cols}, ensure_ascii=False) + "\n")
                    row_count += 1
                    if row_count % 5000 == 0:
                        _progress(f"[{idx}/{total_tables}] Dumping {table.name} ({row_count} rows)")
            LOGGER.info("[%d/%d] Dumped %s: %d rows → %s", idx, total_tables, table.name, row_count, table_file)

    _progress_done()
    LOGGER.info("Dump complete: %d tables written to %s", total_tables, dump_dir)


def _import_files_to_target(dump_dir: Path, target_engine: Engine) -> None:
    """
    Import per-table JSONL files into the target database via SQLAlchemy bulk inserts.
    No native client tools required; SSL and auth are handled by the driver.
    """
    import json
    import base64

    tables = list(Base.metadata.sorted_tables)
    total_tables = max(1, len(tables))

    from sqlalchemy.sql.type_api import TypeDecorator

    def _deserialise(v: object, col_type=None) -> object:
        if isinstance(v, dict) and "__b64__" in v:
            return base64.b64decode(v["__b64__"])
        # TypeDecorator columns (e.g. custom JSON-as-text) expect a Python object,
        # not a raw JSON string. SQLite stores them as text; parse them back here.
        if isinstance(v, str) and col_type is not None and isinstance(col_type, TypeDecorator):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                pass
        return v

    # Detect if the target is MySQL/MariaDB so we can disable FK checks during import.
    # SQLite source may have orphaned rows that SQLite silently accepted (FK enforcement
    # is off by default in SQLite). MySQL enforces FK constraints at INSERT time, so we
    # disable them for the bulk load and re-enable afterwards.
    is_mysql = target_engine.dialect.name in ("mysql", "mariadb")

    with target_engine.connect() as tgt_conn:
        if is_mysql:
            tgt_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            tgt_conn.commit()

        try:
            for idx, table in enumerate(tables, start=1):
                table_file = dump_dir / f"{table.name}.jsonl"
                if not table_file.is_file():
                    LOGGER.info("[%d/%d] No dump file for %s, skipping.", idx, total_tables, table.name)
                    continue

                LOGGER.info("[%d/%d] Importing table %s ...", idx, total_tables, table.name)
                _progress(f"[{idx}/{total_tables}] Importing {table.name}")
                row_count = 0
                batch: list = []
                # Build column-name → SQLAlchemy type map for this table
                col_types = {col.name: col.type for col in table.columns}

                def _flush(batch: list, table=table, tgt_conn=tgt_conn) -> None:
                    if batch:
                        tgt_conn.execute(table.insert(), batch)
                        tgt_conn.commit()

                with table_file.open("r", encoding="utf-8") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        row = {k: _deserialise(v, col_types.get(k)) for k, v in json.loads(raw).items()}
                        batch.append(row)
                        row_count += 1
                        if len(batch) >= _DUMP_BATCH_SIZE:
                            _flush(batch)
                            batch = []
                            if row_count % 5000 == 0:
                                _progress(f"[{idx}/{total_tables}] Importing {table.name} ({row_count} rows)")

                _flush(batch)
                LOGGER.info("[%d/%d] Imported %s: %d rows.", idx, total_tables, table.name, row_count)

        finally:
            if is_mysql:
                tgt_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                tgt_conn.commit()

    _progress_done()
    LOGGER.info("Import complete: %d tables loaded into target.", total_tables)


def main() -> int:
    """
    Entrypoint for the standalone migration script.
    """
    LOGGER.info("bw_db_migrate version %s running from: %s", __version__, Path(__file__).resolve())
    parser = argparse.ArgumentParser(
        description="Migrate BunkerWeb DB data between supported backends.",
        epilog=(
            "DB preparation hints (run on your DB server before migrating):\n"
            "  PostgreSQL:\n"
            "    CREATE DATABASE bunkerweb;\n"
            "    CREATE USER bunkerweb WITH ENCRYPTED PASSWORD 'changeme';\n"
            "    GRANT ALL PRIVILEGES ON DATABASE bunkerweb TO bunkerweb;\n"
            "\n"
            "  MySQL/MariaDB:\n"
            "    CREATE DATABASE db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
            "    CREATE USER 'bunkerweb'@'%' IDENTIFIED BY 'changeme';\n"
            "    GRANT ALL PRIVILEGES ON db.* TO 'bunkerweb'@'%';\n"
            "    FLUSH PRIVILEGES;\n"
            "\n"
            "  SQLite:\n"
            "    Just choose a writable path for the .sqlite3 file; it will be created automatically.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env-file", default="/etc/bunkerweb/variables.env", help="Read DATABASE_URI and DB_MIGRATION_TARGET_URI from this file.")
    parser.add_argument("--source-uri", help="Source SQLAlchemy URI (overrides env/env-file DATABASE_URI).")
    parser.add_argument("--target-uri", help="Target SQLAlchemy URI (overrides env/env-file DB_MIGRATION_TARGET_URI).")
    parser.add_argument(
        "--test-target",
        action="store_true",
        help="Only test that the target database is reachable and empty (no migrations, no copy).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated (table and row counts) without changing the target database.",
    )
    parser.add_argument("--tui", action="store_true", help="Launch an interactive terminal UI to collect inputs.")
    args = parser.parse_args()

    update_env_file = False
    tui_dry_run = False

    if args.tui:
        try:
            env_file, source_uri, target_uri, test_target, update_env_file, tui_dry_run, write_config_now = _run_tui(args.env_file)
        except KeyboardInterrupt:
            LOGGER.info("Aborted.")
            return 130
        env_file_values = _load_env_file(Path(env_file))
        source_uri = _resolve_input_value(source_uri, env_file_values, "DATABASE_URI")
        target_uri = _resolve_input_value(target_uri, env_file_values, "DB_MIGRATION_TARGET_URI")
        args.test_target = args.test_target or test_target
        args.dry_run = args.dry_run or tui_dry_run

        # If write_config_now is set, just write config and exit without migration
        if write_config_now:
            if target_uri:
                _save_target_uri_to_env_file(Path(env_file), target_uri)
                LOGGER.info("Target database configuration saved to env file: %s", env_file)
                LOGGER.info("Target DB_MIGRATION_TARGET_URI: %s", target_uri)
            return 0
    else:
        env_file_values = _load_env_file(Path(args.env_file))
        source_uri = _resolve_input_value(args.source_uri, env_file_values, "DATABASE_URI")
        target_uri = _resolve_input_value(args.target_uri, env_file_values, "DB_MIGRATION_TARGET_URI")

    # Merge settings from env file and environment (environment wins)
    settings: Dict[str, str] = dict(env_file_values)
    for k, v in os.environ.items():
        settings[k] = v
    engine_kwargs = _engine_kwargs_from_settings(settings)

    # Ensure dump root exists and clean up any leftovers from previous runs.
    try:
        if _DUMP_ROOT.exists():
            shutil.rmtree(_DUMP_ROOT)
        _DUMP_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        LOGGER.error("Unable to prepare dump directory %s: %s", _DUMP_ROOT, exc)
        return 1

    if not source_uri:
        LOGGER.error("DATABASE_URI is not set (CLI --source-uri, env file, or environment).")
        return 1
    if not target_uri and not args.dry_run:
        LOGGER.error("DB_MIGRATION_TARGET_URI is not set (CLI --target-uri, env file, or environment).")
        return 1

    LOGGER.info("Source DATABASE_URI: %r", source_uri)
    LOGGER.info("Target DB_MIGRATION_TARGET_URI: %r", target_uri)

    # Warn about characters that may require manual escaping in env files or URIs.
    for label, uri in (("source", source_uri), ("target", target_uri)):
        if any(ch in uri for ch in ['"', "'", " ", "\\", "`", "$"]):
            LOGGER.warning(
                "The %s URI contains characters like quotes, spaces, backslashes, backticks or '$'. "
                "If you store it in an env file, ensure it is properly quoted/escaped.",
                label,
            )

    try:
        LOGGER.debug("Engine settings type=%s keys=%s", type(engine_kwargs), sorted(engine_kwargs.keys()))
        source_engine = _create_engine(source_uri, engine_kwargs=engine_kwargs)
        target_engine: Optional[Engine] = None

        # 1. Basic connectivity to source
        with source_engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Only touch target when we have a target URI (dry-run can be source-only).
        if target_uri:
            ssl_expected = _uri_uses_ssl(target_uri)
            host, port = _resolve_target_host_port(target_uri)
            ips = _resolve_ips(host)
            ca_path = _extract_ca_from_uri(target_uri)
            cafile, capath = _system_ca_summary()

            LOGGER.info("Target connect details: host=%s port=%s ips=%s", host or "(unknown)", port or "(unknown)", ",".join(ips) if ips else "(unresolved)")
            LOGGER.info("Target SSL requested: %s", "yes" if ssl_expected else "no")
            if ssl_expected:
                LOGGER.info("Target CA file: %s", ca_path if ca_path else "(not set)")
                if not ca_path:
                    LOGGER.info("System CA bundle: cafile=%s capath=%s", cafile or "(none)", capath or "(none)")
                LOGGER.info("SSL verification: verifying server certificate (CA=%s).", ca_path if ca_path else "system-default")

            target_engine = _create_engine(target_uri, engine_kwargs=engine_kwargs)
            with target_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            if ssl_expected:
                # Perform explicit verification and certificate introspection for MySQL/MariaDB+pymysql.
                _verify_mysql_ssl_and_log_details(target_uri)
                LOGGER.info("Encrypted connection to target database established successfully.")
            else:
                # Even when SSL is not explicitly enabled in the URI, try a
                # best-effort SSL probe. If it fails, log and continue, since
                # the user did not request SSL.
                try:
                    _verify_mysql_ssl_and_log_details(target_uri)
                    LOGGER.info(
                        "Target appears to support SSL/TLS; server certificate verified successfully "
                        "even though SSL is not enabled in the URI."
                    )
                except Exception as exc:
                    LOGGER.info(
                        "Best-effort SSL probe on target failed or is unsupported (SSL disabled in URI): %s",
                        exc,
                    )
            # Ensure target is empty from BunkerWeb's perspective
            _ensure_target_empty(target_engine)

        if args.dry_run:
            # Summarize what would be migrated and time the read path from the source DB,
            # but don't touch schema or data on the target.
            tables = list(Base.metadata.sorted_tables)
            total_tables = len(tables)
            total_rows = 0
            LOGGER.info("Dry run: summarizing source database contents (full table counts).")
            start_dry = time.monotonic()
            with source_engine.connect() as conn:
                for table in tables:
                    t0 = time.monotonic()
                    count = conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one()
                    total_rows += int(count)
                    elapsed_tbl = time.monotonic() - t0
                    LOGGER.info("Table %s: %s rows (count query %.3fs)", table.name, count, elapsed_tbl)
            elapsed = time.monotonic() - start_dry
            LOGGER.info(
                "Dry run complete: %s tables, %s total rows would be migrated. "
                "Total time spent reading counts from source DB: %.3fs. No changes were made.",
                total_tables,
                total_rows,
                elapsed,
            )
            return 0

        if args.test_target:
            LOGGER.info("Target database connectivity OK and target appears empty for BunkerWeb tables.")
            return 0

        LOGGER.info("Starting database backend migration (no schema change, backend move only) ...")

        # 3. Create schema on target for current BunkerWeb version
        assert target_engine is not None, "Target engine must be initialized for real migration"
        LOGGER.info("Running Alembic schema upgrade...")
        try:
            _run_alembic_upgrade(target_uri)
            LOGGER.info("Alembic upgrade completed successfully.")
        except SystemExit as exc:
            # Some Alembic environments call sys.exit(0) after upgrade; treat
            # that as "upgrade completed" and continue with the migration.
            code = exc.code if isinstance(exc.code, int) else 1
            LOGGER.warning("Alembic triggered SystemExit(%d); continuing migration.", code)
            if code != 0:
                raise
        except Exception as e:
            LOGGER.error("Alembic upgrade failed: %s", e)
            raise
        LOGGER.info("Target schema ready; proceeding with dump/import.")

        # 3b. Durable intermediate dump under /tmp/bunkerweb/bw_db_migrate:
        # source -> files -> target
        dump_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dump_dir = _DUMP_ROOT / f"dump-{dump_timestamp}"
        LOGGER.info("Using intermediate dump directory at %s", dump_dir)

        # 4. Phase 1: dump from source into neutral files
        LOGGER.info("Phase 1/2: dumping data from source database to intermediate dump files.")
        effective_source_uri = source_uri
        if source_uri.startswith("sqlite:"):
            effective_source_uri = _sqlite_snapshot_if_wal(source_uri, dump_dir)
        effective_source_engine = source_engine if effective_source_uri == source_uri else _create_engine(effective_source_uri, engine_kwargs=engine_kwargs)
        _dump_source_to_files(effective_source_engine, dump_dir)

        # 4b. Phase 2: import from files into target
        LOGGER.info("Phase 2/2: importing data from intermediate dump files into target database.")
        _import_files_to_target(dump_dir, target_engine)

        # 5. Verify per-table row counts between source and target
        _verify_all_data(effective_source_engine, target_engine)

        if args.tui and update_env_file and not args.test_target and not args.dry_run:
            _update_env_file_on_success(Path(args.env_file), target_uri)

        # Clean up dump directory on successful completion.
        try:
            if _DUMP_ROOT.exists():
                shutil.rmtree(_DUMP_ROOT)
                LOGGER.info("Cleaned up intermediate dump directory %s.", _DUMP_ROOT)
        except Exception as exc:
            LOGGER.warning("Unable to clean up dump directory %s: %s", _DUMP_ROOT, exc)

        LOGGER.info("Database backend migration completed successfully.")
        LOGGER.info("You can now point BunkerWeb's DATABASE_URI to the target URI.")
        LOGGER.info("=" * 60)
        LOGGER.info("ACTION REQUIRED: reboot this manager to apply the new database backend.")
        LOGGER.info("  Recommended : sudo reboot")
        LOGGER.info("  Alternative : sudo systemctl restart bunkerweb bunkerweb-scheduler bunkerweb-ui")
        LOGGER.info("=" * 60)
        return 0
    except KeyboardInterrupt:
        LOGGER.error("Database backend migration ABORTED (KeyboardInterrupt).")
        return 130
    except SystemExit as exc:
        # Some external libraries may raise SystemExit (e.g. via sys.exit()).
        # Treat it as a failure unless the exit code is explicitly 0.
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            LOGGER.warning("Database backend migration triggered SystemExit(0) unexpectedly; treating as success.")
            return 0
        LOGGER.exception("Database backend migration FAILED due to SystemExit(%s).", code)
        return code or 1
    except SQLAlchemyError as exc:
        if target_uri and _uri_uses_ssl(target_uri):
            LOGGER.exception(
                "SQLAlchemy error during DB migration while SSL/TLS was requested for target URI. "
                "If you see certificate or TLS errors, ensure the correct CA is provided or disable SSL in the TUI."
            )
        else:
            LOGGER.exception("SQLAlchemy error during DB migration: %s", exc)
        LOGGER.error("Database backend migration FAILED due to SQLAlchemy error.")
        return 1
    except Exception:  # pragma: no cover - generic safety
        LOGGER.exception("Unexpected error during DB migration.")
        LOGGER.error("Database backend migration FAILED due to an unexpected error.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

