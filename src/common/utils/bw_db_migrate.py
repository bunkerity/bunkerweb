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
import hashlib
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

__version__ = "0.5.7"
_MAX_LOG_LEN = 32768  # large enough for full table output (29+ rows × ~170 chars)
_DUMP_ROOT = Path("/tmp/bunkerweb/bw_db_migrate")
_PID_FILE = _DUMP_ROOT / "bw_db_migrate.pid"


def _pid_write(step: str) -> None:
    """Write/update the PID file with current PID, timestamp, and step name.

    Updated at each major migration step so operators can tell if a run is
    active and how far it has progressed. Also used to detect concurrent runs.
    """
    try:
        _DUMP_ROOT.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(
            f"pid={os.getpid()}\n"
            f"time={datetime.now().isoformat(timespec='seconds')}\n"
            f"step={step}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _pid_check_concurrent() -> Optional[str]:
    """Return a warning string if another instance appears to be running, else None."""
    try:
        if not _PID_FILE.exists():
            return None
        data = dict(line.split("=", 1) for line in _PID_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
        other_pid = int(data.get("pid", 0))
        step = data.get("step", "unknown")
        ts = data.get("time", "unknown")
        if other_pid and other_pid != os.getpid():
            # Check if the process is actually alive
            try:
                os.kill(other_pid, 0)
                return f"PID {other_pid} (started {ts}, step: {step})"
            except OSError:
                return None  # process is dead — stale PID file
    except Exception:
        pass
    return None


def _pid_remove() -> None:
    """Remove the PID file on clean exit."""
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


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
        formatted = formatted[:_MAX_LOG_LEN] + "\n... [LOG MESSAGE TRUNCATED]"

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
from sqlalchemy.schema import UniqueConstraint


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


def _mask_uri_password(uri: str) -> str:
    """Return the URI with the password replaced by '***' for safe logging."""
    try:
        from sqlalchemy.engine.url import make_url

        return make_url(uri).__repr__()
    except Exception:
        # Fallback: crude regex mask for user:pass@ pattern
        import re

        return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", uri)


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

    # Normalize bare postgresql:// (no driver suffix) to postgresql+psycopg://
    # so SQLAlchemy uses psycopg (v3) instead of defaulting to psycopg2 which is not installed.
    if normalized_uri.startswith("postgresql://") or normalized_uri.startswith("postgres://"):
        normalized_uri = normalized_uri.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)
    kwargs: Dict[str, object] = dict(engine_kwargs or {"future": True, "pool_pre_ping": True, "pool_recycle": 1800})

    try:
        from urllib.parse import unquote

        url = make_url(normalized_uri)
        drivername = (url.drivername or "").lower()
        if "pymysql" in drivername:
            query = dict(url.query or {})
            ssl_ca = query.get("ssl_ca") or query.get("sslrootcert")
            if ssl_ca:
                ssl_ca = unquote(ssl_ca)
                # PyMySQL requires ssl as a dict in connect_args, not a query string param
                existing_ssl: dict = {}
                if isinstance(kwargs.get("connect_args"), dict):
                    existing_ssl = dict(kwargs["connect_args"].get("ssl", {}))  # type: ignore[arg-type]
                existing_ssl.setdefault("ca", ssl_ca)
                connect_args = dict(kwargs.get("connect_args") or {})  # type: ignore[arg-type]
                connect_args["ssl"] = existing_ssl
                kwargs["connect_args"] = connect_args
        elif "psycopg" in drivername:
            query = dict(url.query or {})
            ssl_rootcert = query.get("sslrootcert")
            if ssl_rootcert:
                ssl_rootcert = unquote(ssl_rootcert)
                # Update query with decoded path so psycopg receives the real filesystem path
                query["sslrootcert"] = ssl_rootcert
                url = url.set(query=query)
                normalized_uri = str(url)
            # libpq looks for $HOME/.postgresql/postgresql.crt even when no client cert is
            # configured. Set sslcert/sslkey to a nonexistent path to skip that lookup.
            # Reference: https://www.postgresql.org/docs/current/libpq-ssl.html
            if query.get("sslmode"):
                connect_args = dict(kwargs.get("connect_args") or {})  # type: ignore[arg-type]
                connect_args.setdefault("sslcert", "/tmp/.bw-no-client-cert")
                connect_args.setdefault("sslkey", "/tmp/.bw-no-client-cert")
                kwargs["connect_args"] = connect_args
    except Exception:
        pass

    # Inject a connect_timeout (seconds) into connect_args for drivers that support it.
    #
    # - SQLite's DBAPI (`sqlite3.connect`) does not accept `connect_timeout` and will raise
    #   `TypeError: Connection() got an unexpected keyword argument 'connect_timeout'`.
    # - MySQL/PyMySQL and Postgres/Psycopg generally accept `connect_timeout`.
    try:
        _drivername = ""
        try:
            _drivername = (make_url(normalized_uri).drivername or "").lower()  # type: ignore[name-defined]
        except Exception:
            _drivername = ""

        connect_args = dict(kwargs.get("connect_args") or {})  # type: ignore[arg-type]
        if "sqlite" in _drivername:
            # SQLAlchemy may pass arbitrary engine_kwargs connect args; sqlite3.connect
            # does not accept connect_timeout.
            connect_args.pop("connect_timeout", None)
        else:
            connect_args.setdefault("connect_timeout", 2)
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


def _fix_sqlite_permissions(target_uri: str) -> None:
    """
    Ensure the SQLite backend is readable/writable by the BunkerWeb runtime user.

    When bw_db_migrate is executed as root, it may create the SQLite file owned by root:root.
    The BunkerWeb scheduler (often running as `nginx`) needs write access for SQLite journal/WAL
    state, so we best-effort chown/chmod the DB file and its parent directory.
    """
    if not (target_uri or "").lower().startswith("sqlite"):
        return

    sqlite_fs_path = _sqlite_path_from_uri(target_uri)
    if not sqlite_fs_path:
        return

    db_path = Path(sqlite_fs_path)
    if not db_path.exists():
        return

    # Use the parent directory owner/group for best compatibility with the
    # distribution packaging (nginx may run as a different UID/GID).
    try:
        st = os.stat(db_path.parent.as_posix())
        _uid = st.st_uid
        _gid = st.st_gid
    except Exception:
        LOGGER.warning("AUTO-SWITCH: unable to stat parent dir for SQLite permissions fix.")
        return

    try:
        os.chown(db_path.as_posix(), _uid, _gid)
    except Exception as exc:
        LOGGER.warning("AUTO-SWITCH: unable to chown sqlite db %s: %s", db_path, exc)

    # Apply typical permissions on the DB file only.
    try:
        db_path.chmod(0o640)
    except Exception as exc:
        LOGGER.warning("AUTO-SWITCH: unable to chmod sqlite paths: %s", exc)


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


def _tls_status(version: str, cipher_name: str) -> str:
    """Return a short status string for a TLS connection (used in the overview table)."""
    issues = []
    if not version or not (version.startswith("TLSv1.2") or version.startswith("TLSv1.3")):
        issues.append(f"old-protocol({version or 'none'})")
    upper = (cipher_name or "").upper()
    if version and not version.startswith("TLSv1.3"):
        if cipher_name and not any(t in upper for t in ("DHE", "ECDHE")):
            issues.append("no-FS")
    if "RSA" in upper and "ECDSA" not in upper:
        issues.append("RSA-cipher")
    return "WARN: " + ", ".join(issues) if issues else "OK"


def _analyze_tls_strength(version: str, cipher_name: str) -> None:
    """Emit warnings for weak TLS settings and a GOOD line when everything
    looks strong (modern protocol + forward secrecy)."""
    weak = False
    if not version or not (version.startswith("TLSv1.2") or version.startswith("TLSv1.3")):
        LOGGER.warning(
            "TLS configuration: WARNING – old or unknown TLS version in use (%s). "
            "Prefer TLSv1.2 or TLSv1.3.",
            version or "(none)",
        )
        weak = True
    upper_cipher = cipher_name.upper() if cipher_name else ""
    if version and not version.startswith("TLSv1.3"):
        if cipher_name and not any(token in upper_cipher for token in ("DHE", "ECDHE")):
            LOGGER.warning(
                "TLS configuration: WARNING – cipher without forward secrecy in use (%s). "
                "Prefer ECDHE/DHE-based ciphers.",
                cipher_name,
            )
            weak = True
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


def _verify_mysql_ssl_and_log_details(target_uri: str, *, ssl_required: bool = True) -> None:
    """
    Perform an explicit MySQL SSL/TLS verification handshake using PyMySQL so we can:
    - Verify server certificate (against provided CA or system CAs)
    - Log SSL protocol/cipher and certificate details
    When ssl_required=False (best-effort probe), failures are logged at WARNING level
    instead of ERROR so they don't appear as errors when SSL was never configured.
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

            # Only log the PEM if it is a CA certificate (BasicConstraints CA:TRUE or self-signed).
            # Leaf certificates are not useful as ssl_ca values and should not be printed.
            _print_pem = False
            try:
                from cryptography import x509 as _cx509
                from cryptography.hazmat.backends import default_backend as _cdb
                from cryptography.x509.oid import ExtensionOID as _CEOID
                _cert_obj = _cx509.load_der_x509_certificate(bin_cert, _cdb())
                try:
                    _bc = _cert_obj.extensions.get_extension_for_oid(_CEOID.BASIC_CONSTRAINTS)
                    _print_pem = _bc.value.ca
                except Exception:
                    _print_pem = _cert_obj.subject == _cert_obj.issuer  # self-signed fallback
            except Exception:
                pass  # cryptography not available — skip PEM printing to be safe

            if _print_pem:
                chunk_size = 1800
                for idx in range(0, len(pem_text), chunk_size):
                    chunk = pem_text[idx : idx + chunk_size]
                    LOGGER.info("%s: server certificate PEM (chunk %d):\n%s", context, idx // chunk_size + 1, chunk)
            else:
                LOGGER.info("%s: server certificate is a leaf cert (not a CA) — PEM not printed", context)

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
        _log = LOGGER.error if ssl_required else LOGGER.warning
        _log("SSL verification failed for target database: %s", exc)
        # Emit a clear, actionable message summarizing why the certificate is considered invalid.
        reason = str(exc)
        if "self-signed certificate" in reason or "certificate verify failed" in reason:
            if not ca_path:
                _log(
                    "SSL is enabled on the target database server but no trusted CA file is configured. "
                    "The server uses a private/self-signed CA that the system trust store does not know. "
                    "Fix: add the CA certificate path to your target URI, e.g.: "
                    "DB_MIGRATION_TARGET_URI=mysql+pymysql://user:pass@host/db?ssl=true&ssl_ca=/path/to/ca.pem"
                )
            else:
                _log(
                    "SSL certificate verification failed: the configured CA file (%s) does not match "
                    "the certificate chain presented by the target database server. "
                    "Make sure you are using the correct CA for this database cluster.",
                    ca_path,
                )
        elif "certificate has expired" in reason:
            _log("SSL certificate verification failed: the server certificate has expired.")
        elif "hostname" in reason or "doesn't match" in reason:
            _log(
                "SSL certificate verification failed: hostname mismatch between the configured DB host "
                "and the certificate subject/SAN. Check that the hostname in the URI matches the certificate."
            )
        else:
            _log("SSL certificate verification failed: %s", reason)
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


_TLS13_CIPHERSUITES = [
    "TLS_AES_256_GCM_SHA384",
    "TLS_AES_128_GCM_SHA256",
    "TLS_CHACHA20_POLY1305_SHA256",
]

_TLS12_CIPHERS = [
    # Forward-secret ECDSA (preferred)
    ("ECDHE-ECDSA-AES256-GCM-SHA384",   True,  False),
    ("ECDHE-ECDSA-AES128-GCM-SHA256",   True,  False),
    ("ECDHE-ECDSA-CHACHA20-POLY1305",   True,  False),
    ("ECDHE-ECDSA-AES256-SHA384",       True,  False),
    # Forward-secret RSA
    ("ECDHE-RSA-AES256-GCM-SHA384",     True,  False),
    ("ECDHE-RSA-AES128-GCM-SHA256",     True,  False),
    ("ECDHE-RSA-CHACHA20-POLY1305",     True,  False),
    ("ECDHE-RSA-AES256-SHA384",         True,  False),
    ("DHE-RSA-AES256-GCM-SHA384",       True,  False),
    ("DHE-RSA-AES128-GCM-SHA256",       True,  False),
    # No forward secrecy (RSA key exchange)
    ("AES256-GCM-SHA384",               False, False),
    ("AES128-GCM-SHA256",               False, False),
    ("AES256-SHA256",                   False, False),
    ("AES128-SHA256",                   False, False),
    # Weak / legacy
    ("DES-CBC3-SHA",                    False, True),
    ("RC4-SHA",                         False, True),
    ("RC4-MD5",                         False, True),
    ("EXP-RC4-MD5",                     False, True),
]


def _enumerate_node_ciphers(
    host: str,
    port: int,
    *,
    ca_file: Optional[str] = None,
    starttls: str = "",
    connect_ip: Optional[str] = None,
) -> None:
    """Probe host:port for each TLS 1.2 and TLS 1.3 cipher and log which are accepted.
    Flags ciphers without forward secrecy or known-weak ciphers as warnings."""
    import ssl as _ssl

    def _try_cipher(tls_version: str, cipher_str: str, tls13: bool) -> Optional[str]:
        """Attempt a handshake with a single cipher. Returns negotiated cipher name or None."""
        try:
            ctx = _ssl.SSLContext(_ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = True
            ctx.verify_mode = _ssl.CERT_REQUIRED
            if ca_file:
                ctx.load_verify_locations(cafile=ca_file)
            else:
                ctx.load_default_certs()
                ctx.set_default_verify_paths()
            if tls13:
                # Allow TLS 1.2 as minimum so the server can still negotiate —
                # we pin only the ciphersuite and check the negotiated version afterward.
                ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
                ctx.maximum_version = _ssl.TLSVersion.TLSv1_3
                try:
                    ctx.set_ciphersuites(cipher_str)
                    # Disable all TLS 1.2 ciphers so only the TLS 1.3 suite is offered
                    ctx.set_ciphers("NULL")
                except Exception:
                    pass  # set_ciphers("NULL") may fail on some builds; still try
            else:
                ctx.minimum_version = _ssl.TLSVersion.TLSv1_2
                ctx.maximum_version = _ssl.TLSVersion.TLSv1_2
                try:
                    ctx.set_ciphers(cipher_str)
                except Exception:
                    return None
            with socket.create_connection((connect_ip or host, port), timeout=1) as raw:
                if starttls == "postgres":
                    raw.sendall(b"\x00\x00\x00\x08\x04\xd2\x16\x2f")
                    if raw.recv(1) != b"S":
                        return None
                with ctx.wrap_socket(raw, server_hostname=host) as s:
                    negotiated = s.cipher()
                    neg_version = s.version() or ""
                    neg_name = negotiated[0] if isinstance(negotiated, (tuple, list)) else str(negotiated)
                    # For TLS 1.3 probes, only count as accepted if TLS 1.3 was actually negotiated
                    if tls13 and not neg_version.startswith("TLSv1.3"):
                        return None
                    return neg_name
        except (_ssl.SSLError, OSError):
            return None
        except Exception:
            return None

    accepted_fs: list = []
    accepted_no_fs: list = []
    accepted_weak: list = []

    for cs in _TLS13_CIPHERSUITES:
        name = _try_cipher("TLSv1.3", cs, tls13=True)
        if name:
            accepted_fs.append(f"  TLSv1.3  {name}")

    for cipher_name, fs, weak in _TLS12_CIPHERS:
        name = _try_cipher("TLSv1.2", cipher_name, tls13=False)
        if name:
            entry = f"  TLSv1.2  {name}"
            if weak:
                accepted_weak.append(entry)
            elif fs:
                accepted_fs.append(entry)
            else:
                accepted_no_fs.append(entry)

    lines = []
    if accepted_fs:
        lines.append("  [OK ] Forward-secret ciphers accepted:")
        lines.extend(f"        {l.strip()}" for l in accepted_fs)
    if accepted_no_fs:
        lines.append("  [WARN] Non-forward-secret ciphers accepted (no PFS):")
        lines.extend(f"        {l.strip()}" for l in accepted_no_fs)
    if accepted_weak:
        lines.append("  [CRIT] Weak/legacy ciphers accepted:")
        lines.extend(f"        {l.strip()}" for l in accepted_weak)
    if not lines:
        lines.append("  (no ciphers matched — server may require SNI or mutual TLS)")

    label = connect_ip or host
    if accepted_weak:
        LOGGER.warning("Cipher enumeration for %s:%d (%s):\n%s", host, port, label, "\n".join(lines))
    elif accepted_no_fs:
        LOGGER.warning("Cipher enumeration for %s:%d (%s):\n%s", host, port, label, "\n".join(lines))
    else:
        LOGGER.info("Cipher enumeration for %s:%d (%s):\n%s", host, port, label, "\n".join(lines))


def _log_ssl_chain(host: str, port: int, *, ca_file: Optional[str] = None, starttls: str = "", connect_ip: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Fetch the full TLS certificate chain from host:port and log each certificate's
    subject, issuer, validity, and SAN.  The root CA issuer is highlighted so operators
    know which CA PEM to extract if they need to configure one manually.

    starttls: optional protocol hint passed to openssl for STARTTLS handshakes
    (e.g. "postgres", "mysql").  When empty, a direct TLS connection is used.
    """
    import ssl
    import socket

    try:
        ctx = ssl.create_default_context(cafile=ca_file)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # we want the chain regardless of validity

        # Connect to the specific IP if given (keeps hostname for SNI/pg_hba matching)
        with socket.create_connection((connect_ip or host, port), timeout=5) as raw_sock:
            if starttls == "postgres":
                # PostgreSQL STARTTLS: send SSLRequest message
                raw_sock.sendall(b"\x00\x00\x00\x08\x04\xd2\x16\x2f")
                resp = raw_sock.recv(1)
                if resp != b"S":
                    LOGGER.warning("SSL chain probe: PostgreSQL server declined SSL (response=%r)", resp)
                    return
            elif starttls == "mysql":
                # MySQL STARTTLS: read the server greeting packet, then send
                # a minimal ClientSSL packet (4-byte header + capability flags with SSL bit set).
                # Read initial handshake packet (length-prefixed: 3-byte len + 1-byte seq)
                _hdr = raw_sock.recv(4)
                if len(_hdr) < 4:
                    LOGGER.warning("SSL chain probe: MySQL server sent short greeting header")
                    return
                _pkt_len = _hdr[0] | (_hdr[1] << 8) | (_hdr[2] << 16)
                _greeting = raw_sock.recv(_pkt_len)  # consume the rest of the handshake
                if not _greeting:
                    LOGGER.warning("SSL chain probe: MySQL server sent empty greeting")
                    return
                # Send a minimal SSL upgrade request:
                # capabilities = CLIENT_SSL (0x0800) | CLIENT_PROTOCOL_41 (0x0200) | CLIENT_LONG_PASSWORD (0x0001)
                _cap = 0x0800 | 0x0200 | 0x0001
                _ssl_req = (
                    _cap.to_bytes(4, "little")   # capability flags (4 bytes)
                    + (16384).to_bytes(4, "little")  # max packet size
                    + b"\x21"                         # charset: utf8mb4
                    + b"\x00" * 23                    # reserved
                )
                _ssl_pkt_len = len(_ssl_req).to_bytes(3, "little") + b"\x01"  # seq=1
                raw_sock.sendall(_ssl_pkt_len + _ssl_req)
            with ctx.wrap_socket(raw_sock, server_hostname=host) as tls_sock:
                # TLS cipher/protocol analysis (same checks as MySQL path)
                cipher = tls_sock.cipher()
                version = tls_sock.version() or ""
                cipher_name = cipher[0] if isinstance(cipher, (tuple, list)) and cipher else str(cipher)
                LOGGER.info("SSL probe: protocol=%s cipher=%s", version, cipher)
                _analyze_tls_strength(version, cipher_name)

                # Fetch DER-encoded chain
                try:
                    chain = tls_sock.get_verified_chain()  # Python 3.13+
                except AttributeError:
                    chain = None

                root_ca_issuer: Optional[str] = None  # populated from chain root cert below
                root_ca_pem: Optional[str] = None
                cert_critical = False
                cert_expiry: Optional[str] = None
                cert_ttl_str: Optional[str] = None
                if chain:
                    for depth, cert_obj in enumerate(chain):
                        issuer, is_critical, pem = _log_chain_cert(depth, len(chain), cert_obj)
                        if issuer is not None:
                            root_ca_issuer = issuer
                            root_ca_pem = pem
                        if depth == 0:
                            # Always capture expiry from the leaf cert for the TLS overview table
                            try:
                                from cryptography.x509 import load_der_x509_certificate as _ldx
                                from datetime import timezone as _tz2
                                _c = _ldx(bytes(cert_obj) if isinstance(cert_obj, (bytes, bytearray)) else cert_obj)
                                _exp = _c.not_valid_after_utc
                                _rem = _exp - datetime.now(_tz2.utc)
                                cert_expiry = _exp.strftime("%Y-%m-%d")
                                _total_secs = int(_rem.total_seconds())
                                if _total_secs < 3600:
                                    cert_ttl_str = f"{max(0, _total_secs // 60)}m"
                                elif _total_secs < 86400:
                                    cert_ttl_str = f"{_total_secs // 3600}h"
                                else:
                                    cert_ttl_str = f"{_total_secs // 86400}d"
                            except Exception:
                                pass
                            if is_critical:
                                cert_critical = True
                else:
                    # Fallback: log only the leaf cert via getpeercert
                    cert = tls_sock.getpeercert()
                    if cert:
                        LOGGER.info("SSL chain: leaf certificate subject=%s", cert.get("subject"))
                        LOGGER.info("SSL chain: leaf certificate issuer=%s", cert.get("issuer"))
                        LOGGER.info(
                            "SSL chain: leaf certificate validity notBefore=%s notAfter=%s",
                            cert.get("notBefore"), cert.get("notAfter"),
                        )
                        LOGGER.info(
                            "SSL chain: root CA issuer not available (Python < 3.13); "
                            "run: openssl s_client -connect %s:%d%s 2>/dev/null | openssl x509 -noout -issuer",
                            host, port,
                            f" -starttls {starttls}" if starttls else "",
                        )

                tls_info: Dict[str, str] = {
                    "version": version,
                    "cipher": cipher_name,
                    "root_ca": root_ca_issuer or "",
                    "root_ca_pem": root_ca_pem or "",
                    "cert_critical": "1" if cert_critical else "0",
                    "cert_expiry": cert_expiry or "",
                    "cert_ttl": cert_ttl_str or "",
                    "status": _tls_status(version, cipher_name),
                }
        return tls_info
    except Exception as exc:
        LOGGER.warning("SSL chain probe failed (non-fatal): %s", exc)
    return None


def _log_chain_cert(depth: int, total: int, cert_obj: object) -> tuple[Optional[str], bool]:
    """Log a single certificate from the chain.
    cert_obj may be raw DER bytes (Python ssl.get_verified_chain) or a
    cryptography Certificate object.
    """
    try:
        from cryptography.x509 import load_der_x509_certificate  # type: ignore[import]
        from cryptography.hazmat.primitives.serialization import Encoding  # type: ignore[import]
        import base64

        # get_verified_chain() returns DER bytes; load them
        if isinstance(cert_obj, (bytes, bytearray)):
            der = bytes(cert_obj)
        else:
            der = cert_obj.public_bytes(Encoding.DER)  # type: ignore[attr-defined]

        from datetime import timezone as _tz, timedelta as _td

        c = load_der_x509_certificate(der)
        is_root = depth == total - 1
        label = "root CA" if is_root else f"chain[{depth}]"
        LOGGER.info("SSL chain %s subject: %s", label, c.subject.rfc4514_string())
        LOGGER.info("SSL chain %s issuer:  %s", label, c.issuer.rfc4514_string())
        LOGGER.info(
            "SSL chain %s validity: %s → %s",
            label,
            c.not_valid_before_utc.date(),
            c.not_valid_after_utc.date(),
        )
        # Certificate expiry check — warn operators before renewal is urgent.
        # Short-lived certs (total lifetime < 8 days, e.g. ACME 7-day certs) use
        # tighter thresholds since they rotate frequently by design.
        _now = datetime.now(_tz.utc)
        _issued = c.not_valid_before_utc
        _expires = c.not_valid_after_utc
        _total_days = (_expires - _issued).days
        _remaining = _expires - _now
        _days = _remaining.days
        _short_lived = _total_days < 8

        _cert_critical = False
        if _short_lived:
            LOGGER.info(
                "SSL chain %s is a short-lived certificate (total lifetime %d day(s), expires %s).",
                label, _total_days, _expires.date(),
            )
            if _days < 1:
                _cert_critical = True
            elif _days <= 3:
                LOGGER.warning(
                    "SSL chain %s expires in %d day(s) (%s). Renewal required soon.",
                    label, _days, _expires.date(),
                )
            elif _days <= 5:
                LOGGER.info(
                    "SSL chain %s expires in %d day(s) (%s).",
                    label, _days, _expires.date(),
                )
        else:
            if _days < 1:
                _cert_critical = True
            elif _days <= 3:
                LOGGER.warning(
                    "SSL chain %s expires in %d day(s) (%s). Urgent renewal required.",
                    label, _days, _expires.date(),
                )
            elif _days <= 7:
                LOGGER.info(
                    "SSL chain %s expires in %d day(s) (%s). Renewal recommended soon.",
                    label, _days, _expires.date(),
                )
        if is_root:
            b64 = base64.b64encode(der).decode("ascii")
            lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
            pem = "-----BEGIN CERTIFICATE-----\n" + "\n".join(lines) + "\n-----END CERTIFICATE-----"
            return c.issuer.rfc4514_string(), _cert_critical, pem
        return None, _cert_critical, None
    except Exception as exc:
        LOGGER.warning("SSL chain cert[%d] decode failed: %s", depth, exc)
    return None, False, None


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
        scroll_offset = 0
        _layout: dict = {}
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
                wrap_w = max(1, max_x - 5)

                # If the terminal is very narrow, the SQL view will quickly run
                # out of vertical space and cut off content. Warn users early.
                if wrap_w < 60:
                    msg = f"ERROR: SQL line width < 60 (current: {wrap_w}). Widen terminal to see all."
                    stdscr.addstr(0, 0, msg[: max_x - 1], curses.A_BOLD | curses.A_REVERSE)

                # Title
                title = "SQL Command to Execute"
                stdscr.addstr(1, 2, title, highlight_attr)
                stdscr.addstr(2, 2, "Space: toggle password  q/Esc: close"[: max_x - 4])

                # Display SQL with line wrapping
                sql_text = unmasked_sql if show_pwd else masked_sql
                lines = sql_text.splitlines()
                display_start = 4
                # Char-wrap long SQL lines so they don't get truncated.
                # `_show_sql_modal` prints at x=4, so the available width is max_x - 5 (with a small safety margin).
                wrapped_lines: list[str] = []
                if wrap_w < 60:
                    # Replace SQL lines with the error message for narrow terminals.
                    err = f"ERROR: SQL width < 60 (current: {wrap_w}). Widen terminal to see all."
                    for start in range(0, len(err), wrap_w):
                        wrapped_lines.append(err[start : start + wrap_w])
                else:
                    for line in lines:
                        if line == "":
                            wrapped_lines.append("")
                            continue
                        for start in range(0, len(line), wrap_w):
                            wrapped_lines.append(line[start : start + wrap_w])

                drawn = 0
                for i, line in enumerate(wrapped_lines):
                    if display_start + i >= max_y - 2:
                        break
                    stdscr.addstr(display_start + i, 4, line[:wrap_w], curses.A_NORMAL)
                    stdscr.clrtoeol()
                    drawn += 1

                # Footer
                last_text_y = display_start + max(0, drawn - 1)
                if max_y - 2 > last_text_y:
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

        def _build_layout(max_x: int) -> dict:
            """Compute {key: (virtual_y_start, height)} for every item and static row.

            Heights are based on line wrapping at the current terminal width.
            Virtual row 1-2 = header (fixed).  Content starts at virtual row 5.
            """
            usable = max(1, max_x - 6)  # 4 left margin + 2 prefix chars

            indent_len = 4  # must match _item() continuation indent: "    "
            prefix_len = 3  # worst-case prefix width (selected): "➜ "

            def _h_plain(text: str) -> int:
                """Lines needed to render *text* wrapped to *usable* columns."""
                return max(1, (len(text) + usable - 1) // usable)

            def _h_item(label: str, value: str) -> int:
                """Lines needed to render an `_item()` field.

                `_item()` renders:
                  - first line using `usable` columns (prefix + label + value)
                  - continuation lines prefixed with 4 spaces, so each consumes
                    `usable - indent_len` columns.
                """
                full_len = prefix_len + len(label) + len(value)
                if full_len <= usable:
                    return 1
                cont_w = max(1, usable - indent_len)
                remaining = full_len - usable
                return 1 + (remaining + cont_w - 1) // cont_w

            pw_vis = target_password if show_password else "*" * len(target_password) if target_password else ""
            pw_txt = (pw_vis + f"  [{'x' if show_password else ' '}] Show") if target_password else ""

            layout: dict = {}
            vy = 5

            def _place(key: int, label: str, value: str) -> None:
                nonlocal vy
                ht = _h_item(label, value)
                layout[key] = (vy, ht)
                vy += ht

            _place(0, "Env file: ", env_file)
            _place(1, "Source DATABASE_URI: ", _mask_uri_password(source_uri))
            _place(2, "Source host: ", source_host)
            _place(3, "Source port: ", source_port)
            vy += 1  # blank line

            _place(4, "Target DB type: ", target_db_type)
            _place(5, "Target host: ", target_host)
            _place(6, "Target port: ", target_port)
            _place(7, "Target database: ", target_dbname)
            _place(8, "Target username: ", target_username)
            _place(9, "Target password: ", pw_txt)
            gen_lbl = "Generate SQL & password (Enter)" if target_db_type else "[Requires DB type selection]"
            _place(10, "", gen_lbl)
            sql_lbl = "Show SQL command (Enter)" if target_db_type else "[Requires DB type selection]"
            _place(11, "", sql_lbl)
            _place(12, "Root CA certificate: ", root_ca_cert if root_ca_cert else "(not set)")
            vy += 1  # blank line

            _place(13, "", f"[{'x' if target_ssl else ' '}] SSL (yes/no)")
            vy += 1  # blank line

            # URI preview rows (not selectable)
            layout["preview_label"] = (vy, 1)
            vy += 1
            preview_val = _build_target_uri(mask_password=True)
            ph = _h_plain(preview_val) if preview_val else 1
            layout["preview_val"] = (vy, ph)
            vy += ph
            layout["preview_hint"] = (vy, 1)
            vy += 1
            vy += 1  # blank line

            _place(14, "", f"[{'x' if test_target else ' '}] Test target only (no migrations/copy)")
            _place(15, "", f"[{'x' if update_env_file else ' '}] Update env file on success")
            _place(16, "", f"[{'x' if dry_run else ' '}] Dry run (no schema or data changes)")
            _place(17, "", f"[{'x' if write_config_now else ' '}] Write config to env file now (skip migration)")
            _place(18, "", f"[{'x' if show_password else ' '}] Show password in SQL command")
            vy += 1  # blank line

            # Action buttons share the same row
            layout[19] = (vy, 1)
            layout[20] = (vy, 1)
            layout[21] = (vy, 1)
            vy += 1
            vy += 1  # blank line
            layout["tip"] = (vy, 1)
            vy += 1
            layout["total"] = vy
            return layout

        def _ensure_visible(idx: int, max_y: int) -> None:
            """Adjust scroll_offset so item *idx* is fully visible on screen.

            The scrollable content area is rows 4 … max_y-2 (inclusive).
            Row 3 is reserved for the "↑ more" indicator.
            The last row (max_y-1) is reserved for the "↓ more" indicator.
            """
            nonlocal scroll_offset
            if idx not in _layout:
                return
            vy, height = _layout[idx]
            top_screen = 4   # first usable content row
            bot_screen = max_y - 2  # last usable content row
            item_top_screen = vy - scroll_offset
            item_bot_screen = vy + height - 1 - scroll_offset
            if item_top_screen < top_screen:
                scroll_offset = vy - top_screen
            elif item_bot_screen > bot_screen:
                scroll_offset = vy + height - 1 - bot_screen
            scroll_offset = max(0, scroll_offset)

        def _draw() -> None:
            nonlocal _layout
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()

            # Reject terminals that are too narrow to be usable.
            if max_x < 24:
                msg = "Terminal too narrow (min 24 cols)"
                stdscr.addstr(0, 0, msg[: max_x], curses.A_REVERSE)
                stdscr.refresh()
                return

            _layout = _build_layout(max_x)
            usable = max(1, max_x - 6)
            total_vy = _layout.get("total", 40)

            # ── Fixed header ────────────────────────────────────────────
            stdscr.addstr(1, 2, "BunkerWeb DB migrate (TUI)"[: max_x - 4], highlight_attr)
            stdscr.addstr(2, 2, "Up/Down selects. Enter edits/activates. Space toggles checkbox."[: max_x - 4])

            # Scroll indicators on row 3 / last row
            if scroll_offset > 0:
                stdscr.addstr(3, 2, "↑ more"[: max_x - 4], checkbox_attr)
            else:
                stdscr.move(3, 0)
                stdscr.clrtoeol()

            if total_vy - scroll_offset > max_y - 1:
                try:
                    stdscr.addstr(max_y - 1, 2, "↓ more"[: max_x - 4], checkbox_attr)
                except curses.error:
                    pass

            # ── Item renderer ────────────────────────────────────────────
            def _item(idx: int, label: str, value: str, extra_attr=None) -> None:
                """Render a selectable item, wrapping if the text exceeds terminal width."""
                vy, _h = _layout[idx]
                sy = vy - scroll_offset
                if sy < 4 or sy >= max_y - 1:
                    return
                is_sel = selected == idx
                prefix = "➜ " if is_sel else "  "
                attr = extra_attr if extra_attr is not None else (highlight_attr if is_sel else curses.A_NORMAL)
                full = prefix + label + value
                # First line
                stdscr.addstr(sy, 2, full[:usable], attr)
                stdscr.clrtoeol()
                # Continuation lines when wrapping
                rest = full[usable:]
                indent = "    "
                cont_w = max(1, usable - len(indent))
                line_num = 1
                while rest and sy + line_num < max_y - 1:
                    stdscr.addstr(sy + line_num, 2, (indent + rest[:cont_w])[:usable], attr)
                    stdscr.clrtoeol()
                    rest = rest[cont_w:]
                    line_num += 1

            def _static(vy_key: str, text: str, attr=None) -> None:
                """Render a non-selectable static row (e.g. preview label/hint)."""
                if vy_key not in _layout:
                    return
                vy, _h = _layout[vy_key]
                sy = vy - scroll_offset
                if sy < 4 or sy >= max_y - 1:
                    return
                a = attr if attr is not None else curses.A_NORMAL
                stdscr.addstr(sy, 2, text[:usable], a)
                stdscr.clrtoeol()

            # ── Source section ───────────────────────────────────────────
            _item(0, "Env file: ", env_file)
            _item(1, "Source DATABASE_URI: ", _mask_uri_password(source_uri))
            _item(2, "Source host: ", source_host)
            _item(3, "Source port: ", source_port)

            # ── Target section ───────────────────────────────────────────
            _item(4, "Target DB type: ", target_db_type)
            _item(5, "Target host: ", target_host)
            _item(6, "Target port: ", target_port)
            _item(7, "Target database: ", target_dbname)
            _item(8, "Target username: ", target_username)
            pw_display = ""
            if target_password:
                visible = target_password if show_password else "*" * len(target_password)
                pw_display = visible + f"  [{'x' if show_password else ' '}] Show"
            _item(9, "Target password: ", pw_display)

            # Generate SQL & Show SQL buttons
            gen_attr = highlight_attr if selected == 10 and target_db_type else (curses.A_DIM if not target_db_type else curses.A_NORMAL)
            _item(10, "", "Generate SQL & password (Enter)" if target_db_type else "[Requires DB type selection]", extra_attr=gen_attr)
            sql_attr = highlight_attr if selected == 11 and target_db_type else (curses.A_DIM if not target_db_type else curses.A_NORMAL)
            _item(11, "", "Show SQL command (Enter)" if target_db_type else "[Requires DB type selection]", extra_attr=sql_attr)

            # Root CA cert + SSL checkbox
            _item(12, "Root CA certificate: ", root_ca_cert if root_ca_cert else "(not set)")
            _item(13, "", f"[{'x' if target_ssl else ' '}] SSL (yes/no)", extra_attr=highlight_attr if selected == 13 else checkbox_attr)

            # URI preview (non-selectable)
            _static("preview_label", "Target URI preview (password masked):", checkbox_attr)
            preview = _build_target_uri(mask_password=True)
            if "preview_val" in _layout:
                vy, _ph = _layout["preview_val"]
                sy = vy - scroll_offset
                if 4 <= sy < max_y - 1:
                    # Wrap the preview URI across multiple lines
                    rest = preview
                    line_num = 0
                    while rest and sy + line_num < max_y - 1:
                        stdscr.addstr(sy + line_num, 2, rest[:usable])
                        stdscr.clrtoeol()
                        rest = rest[usable:]
                        line_num += 1
            _static("preview_hint", "→ Password is hidden. Use 'Show SQL command' to view and copy.", checkbox_attr)

            # ── Options checkboxes ───────────────────────────────────────
            _item(14, "", f"[{'x' if test_target else ' '}] Test target only (no migrations/copy)", extra_attr=highlight_attr if selected == 14 else checkbox_attr)
            _item(15, "", f"[{'x' if update_env_file else ' '}] Update env file on success", extra_attr=highlight_attr if selected == 15 else checkbox_attr)
            _item(16, "", f"[{'x' if dry_run else ' '}] Dry run (no schema or data changes)", extra_attr=highlight_attr if selected == 16 else checkbox_attr)
            _item(17, "", f"[{'x' if write_config_now else ' '}] Write config to env file now (skip migration)", extra_attr=highlight_attr if selected == 17 else checkbox_attr)
            _item(18, "", f"[{'x' if show_password else ' '}] Show password in SQL command", extra_attr=highlight_attr if selected == 18 else checkbox_attr)

            # ── Action buttons ───────────────────────────────────────────
            if 19 in _layout:
                btn_vy, _ = _layout[19]
                btn_sy = btn_vy - scroll_offset
                if 4 <= btn_sy < max_y - 1:
                    write_prefix = "[WRITE]" if selected == 19 else " WRITE "
                    run_prefix = "[ RUN ]" if selected == 20 else "  RUN  "
                    quit_prefix = "[ QUIT ]" if selected == 21 else "  QUIT "
                    write_attr = highlight_attr if selected == 19 else checkbox_attr
                    run_attr = highlight_attr if selected == 20 else checkbox_attr
                    quit_attr = highlight_attr if selected == 21 else checkbox_attr
                    stdscr.addstr(btn_sy, 2, write_prefix[: max_x - 4], write_attr)
                    if max_x > 14:
                        stdscr.addstr(btn_sy, 10, run_prefix[: max_x - 14], run_attr)
                    if max_x > 24:
                        stdscr.addstr(btn_sy, 20, quit_prefix[: max_x - 24], quit_attr)
                    stdscr.clrtoeol()

            # Tip row
            _static("tip", "Tip: Fill target fields, verify preview, then select RUN and press Enter.", checkbox_attr)

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
                _ensure_visible(selected, stdscr.getmaxyx()[0])
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % total_items
                _ensure_visible(selected, stdscr.getmaxyx()[0])
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
                    sy1 = _layout.get(1, (6, 1))[0] - scroll_offset
                    source_uri = _edit_line(sy1, "Source DATABASE_URI: ", source_uri)
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
                    sy2 = _layout.get(2, (7, 1))[0] - scroll_offset
                    source_host = _edit_line(sy2, "Source host: ", source_host)
                    _apply_source_host_port()
                    continue
                if selected == 3:
                    sy3 = _layout.get(3, (8, 1))[0] - scroll_offset
                    source_port = _edit_line(sy3, "Source port: ", source_port)
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
                    sy5 = _layout.get(5, (11, 1))[0] - scroll_offset
                    target_host = _edit_line(sy5, "Target host: ", target_host)
                    continue
                if selected == 6:
                    sy6 = _layout.get(6, (12, 1))[0] - scroll_offset
                    target_port = _edit_line(sy6, "Target port: ", target_port)
                    continue
                if selected == 7:
                    sy7 = _layout.get(7, (13, 1))[0] - scroll_offset
                    target_dbname = _edit_line(sy7, "Target database: ", target_dbname)
                    continue
                if selected == 8:
                    sy8 = _layout.get(8, (14, 1))[0] - scroll_offset
                    target_username = _edit_line(sy8, "Target username: ", target_username)
                    continue
                if selected == 9:
                    sy9 = _layout.get(9, (15, 1))[0] - scroll_offset
                    target_password = _edit_line(sy9, "Target password: ", "", secret=True) if not target_password else _edit_line(sy9, "Target password: ", target_password, secret=True)
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
            total_rows = sum(non_empty.values())
            table_list = ", ".join(f"{t}({n})" for t, n in sorted(non_empty.items()))

            is_sqlite = (getattr(engine.dialect, "name", "") or "").lower() == "sqlite"
            sqlite_path = ""
            ts_example = datetime.now().strftime("%Y%m%d-%H%M%S")
            if is_sqlite:
                try:
                    sqlite_path = _sqlite_path_from_uri(str(engine.url))
                except Exception:
                    sqlite_path = ""

            LOGGER.error(
                "Target database already contains BunkerWeb data (%d rows across %d tables: %s).\n"
                "  → To start a fresh migration, prepare an empty target first:\n"
                "%s\n"
                "  → Or if this migration already completed successfully, the target is ready to use.",
                total_rows,
                len(non_empty),
                table_list,
                (
                    "      DROP DATABASE bunkerweb; CREATE DATABASE bunkerweb;"
                    if not is_sqlite
                    else (
                        "      Move/rename the existing SQLite DB file"
                        + (f" at: {sqlite_path}" if sqlite_path else "")
                        + f"\n      Example: mv /var/lib/bunkerweb/db.sqlite3 /var/lib/bunkerweb/db.sqlite3.bak-{ts_example}"
                    )
                ),
            )
            raise RuntimeError("Target database is not empty — see error above for details.")


def _run_alembic_upgrade(target_uri: str, *, engine_kwargs: Optional[Dict[str, object]] = None) -> None:
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
    target_engine = _create_engine(target_uri, engine_kwargs=engine_kwargs)
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
    # Keys to comment out (old source URI + migration target key replaced by new DATABASE_URI below)
    comment_keys = ("DATABASE_URI", "DATABASE_URI_READONLY", "DB_MIGRATION_TARGET_URI")
    new_lines = []
    target_line_commented = False
    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            new_lines.append(raw)
            continue
        is_old_db = any(stripped.startswith(f"{k}=") or stripped.startswith(f"export {k}=") for k in comment_keys)
        if is_old_db:
            is_target = stripped.startswith("DB_MIGRATION_TARGET_URI=") or stripped.startswith("export DB_MIGRATION_TARGET_URI=")
            if is_target:
                # Replace this line with DATABASE_URI pointing to the target
                new_lines.append(f"# migrated by bw_db_migrate (was DB_MIGRATION_TARGET_URI): {raw}")
                if not target_line_commented:
                    new_lines.append(f"DATABASE_URI={target_uri}")
                    target_line_commented = True
            else:
                new_lines.append(f"# commented out by bw_db_migrate: {raw}")
        else:
            new_lines.append(raw)

    # If DB_MIGRATION_TARGET_URI was not in the file, append DATABASE_URI at the end
    if not target_line_commented:
        new_lines.append("")
        new_lines.append("# Added by bw_db_migrate after successful migration")
        new_lines.append(f"DATABASE_URI={target_uri}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    LOGGER.info("Updated env file %s: DATABASE_URI now points to migrated target.", env_file)


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


def _verify_all_data(source_engine: Engine, target_engine: Engine, skipped_orphans: Optional[Dict[str, int]] = None) -> None:
    """
    Verify that per-table row counts match between source and target.
    skipped_orphans: per-table count of intentionally skipped orphaned FK rows (source > target is OK by that amount).
    Prints a summary table at the end showing source, target, skipped, and status per table.
    """
    tables = list(Base.metadata.sorted_tables)
    total = max(1, len(tables))
    skipped_orphans = skipped_orphans or {}
    mismatch_error: Optional[str] = None

    # Collect results for the summary table
    _results: list[tuple[str, int, int, int, str]] = []  # (table, src, tgt, orphans, status)

    with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
        start = time.monotonic()
        for idx, table in enumerate(tables, start=1):
            _progress(f"[{idx}/{total}] Verifying {table.name} ...")
            src_count = int(src_conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one())
            tgt_count = int(tgt_conn.execute(text(f"SELECT COUNT(1) FROM {table.name}")).scalar_one())
            orphans = skipped_orphans.get(table.name, 0)
            expected_tgt = src_count - orphans
            if tgt_count != expected_tgt:
                _progress_done()
                status = f"MISMATCH (expected {expected_tgt}, got {tgt_count})"
                _results.append((table.name, src_count, tgt_count, orphans, status))
                if not mismatch_error:
                    if orphans:
                        mismatch_error = (
                            f"Row count mismatch for {table.name}: source={src_count}, "
                            f"skipped_orphans={orphans}, expected_target={expected_tgt}, actual_target={tgt_count}"
                        )
                    else:
                        mismatch_error = f"Row count mismatch for {table.name}: source={src_count}, target={tgt_count}"
            else:
                note = f"({orphans} orphans skipped)" if orphans else ""
                status = f"OK {note}".strip()
                _results.append((table.name, src_count, tgt_count, orphans, status))
            elapsed = time.monotonic() - start
            _progress(f"[{idx}/{total}] Verified {table.name} ({tgt_count} rows) in {elapsed:.1f}s")
    _progress_done()

    # Print summary table
    _col_tbl = max(len("Table"), max(len(r[0]) for r in _results))
    _col_src = max(len("Source"), max(len(str(r[1])) for r in _results))
    _col_tgt = max(len("Target"), max(len(str(r[2])) for r in _results))
    _col_skip = max(len("Skipped"), max(len(str(r[3])) for r in _results))
    _col_st = max(len("Status"), max(len(r[4]) for r in _results))
    _sep = f"+-{'-' * _col_tbl}-+-{'-' * _col_src}-+-{'-' * _col_tgt}-+-{'-' * _col_skip}-+-{'-' * _col_st}-+"
    _hdr = f"| {'Table':<{_col_tbl}} | {'Source':>{_col_src}} | {'Target':>{_col_tgt}} | {'Skipped':>{_col_skip}} | {'Status':<{_col_st}} |"
    _rows = []
    _has_issue = False
    for _tname, _src, _tgt, _skip, _st in _results:
        if _st.startswith("MISMATCH"):
            _has_issue = True
        _rows.append(f"| {_tname:<{_col_tbl}} | {_src:>{_col_src}} | {_tgt:>{_col_tgt}} | {_skip:>{_col_skip}} | {_st:<{_col_st}} |")
    _total_src = sum(r[1] for r in _results)
    _total_tgt = sum(r[2] for r in _results)
    _total_skip = sum(r[3] for r in _results)
    _total_st = "MISMATCH" if _has_issue else "OK"
    _rows.append(_sep.replace("-", "-"))
    _rows.append(f"| {'TOTAL':<{_col_tbl}} | {_total_src:>{_col_src}} | {_total_tgt:>{_col_tgt}} | {_total_skip:>{_col_skip}} | {_total_st:<{_col_st}} |")
    _table_str = "\n".join([_sep, _hdr, _sep] + _rows + [_sep])
    _log_fn = LOGGER.warning if _has_issue else LOGGER.info
    _log_fn("Row count verification:\n%s", _table_str)

    if mismatch_error:
        raise RuntimeError(mismatch_error)


_DUMP_BATCH_SIZE = 500  # rows per INSERT batch


def _pg_quote_ident(ident: str) -> str:
    """Quote a PostgreSQL identifier using double-quotes."""
    return '"' + ident.replace('"', '""') + '"'


def _mysql_quote_ident(ident: str) -> str:
    """Quote a MySQL identifier using backticks."""
    return '`' + ident.replace('`', '``') + '`'


def _pg_pk_constraint_name(table_name: str) -> str:
    """
    Generate a deterministic, PostgreSQL-compliant constraint name for a table primary key.
    PostgreSQL identifier limit is 63 bytes.
    """
    base = f"{table_name}_pkey"
    if len(base) <= 63:
        return base
    digest = hashlib.sha256(table_name.encode("utf-8")).hexdigest()[:8]
    # Keep some prefix for operator readability, ensure total length <= 63
    prefix = table_name[: max(0, 63 - len(digest) - 2)]  # -2 for '_' + '_'
    return f"{prefix}_{digest}_pkey"


def _post_copy_rebuild_indexes(target_engine: Engine) -> None:
    """
    Post-copy step: recreate missing indexes and update index statistics on the target.

    Called after bulk data import to ensure all expected indexes exist and have current stats.
    - SQLite:       REINDEX (rebuilds all indexes) + ANALYZE (updates stats)
    - PostgreSQL:   Recreate missing unique constraint indexes, then ANALYZE per table
    - MySQL/MariaDB: Recreate missing unique constraint indexes, then ANALYZE TABLE batch
    """
    from sqlalchemy import inspect

    dialect_name = (getattr(target_engine.dialect, "name", "") or "").lower()
    tables = list(Base.metadata.sorted_tables)
    total = len(tables)

    if dialect_name == "sqlite":
        with target_engine.connect() as conn:
            LOGGER.info("SQLite: rebuilding indexes (REINDEX) ...")
            conn.execute(text("REINDEX"))
            LOGGER.info("SQLite: updating statistics (ANALYZE) ...")
            conn.execute(text("ANALYZE"))
            LOGGER.info("SQLite: reclaiming disk space (VACUUM) ...")
            conn.execute(text("VACUUM"))
            LOGGER.info("SQLite: optimizing with PRAGMA optimize ...")
            conn.execute(text("PRAGMA optimize"))
            conn.commit()

    elif dialect_name == "postgresql":
        # First pass: recreate missing unique constraint indexes
        with target_engine.begin() as conn:
            insp = inspect(conn)
            indexes_recreated = 0
            for table in tables:
                existing_indexes = insp.get_indexes(table.name)
                existing_col_sets = [set(idx["column_names"]) for idx in existing_indexes]
                existing_constraints = insp.get_unique_constraints(table.name) or []
                existing_constraint_col_sets = [set(c.get("column_names", [])) for c in existing_constraints]

                # Get expected unique constraints from model (table_args)
                if table.table_args and isinstance(table.table_args, tuple):
                    for arg in table.table_args:
                        if isinstance(arg, UniqueConstraint):
                            cols = [c.name for c in arg.columns]
                            col_set = set(cols)
                            try:
                                if col_set not in existing_col_sets and col_set not in existing_constraint_col_sets:
                                    # Index/constraint missing, create it
                                    idx_name = f"ix_{table.name}_{'_'.join(cols)}"
                                    if len(idx_name) > 63:
                                        idx_name = f"ix_{hashlib.sha256('_'.join(cols).encode()).hexdigest()[:8]}"
                                    cols_sql = ", ".join(_pg_quote_ident(c) for c in cols)
                                    try:
                                        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {_pg_quote_ident(idx_name)} ON {_pg_quote_ident(table.name)} ({cols_sql})"))
                                        LOGGER.info("PostgreSQL: created missing index %s on %s(%s)", idx_name, table.name, ", ".join(cols))
                                        indexes_recreated += 1
                                    except Exception as exc:
                                        LOGGER.warning("PostgreSQL: failed to create index %s: %s (non-fatal)", idx_name, exc)
                            except Exception as exc:
                                LOGGER.warning("PostgreSQL: could not check indexes for %s: %s (non-fatal)", table.name, exc)

                # Also check for single-column unique=True constraints
                try:
                    for column in table.columns:
                        if column.unique:
                            col_set = {column.name}
                            if col_set not in existing_col_sets and col_set not in existing_constraint_col_sets:
                                # Unique index missing on this column, create it
                                idx_name = f"ix_{table.name}_{column.name}"
                                try:
                                    conn.execute(text(f"CREATE UNIQUE INDEX IF NOT EXISTS {_pg_quote_ident(idx_name)} ON {_pg_quote_ident(table.name)} ({_pg_quote_ident(column.name)})"))
                                    LOGGER.info("PostgreSQL: created missing unique index %s on %s(%s)", idx_name, table.name, column.name)
                                    indexes_recreated += 1
                                except Exception as exc:
                                    LOGGER.warning("PostgreSQL: failed to create unique index %s: %s (non-fatal)", idx_name, exc)
                except Exception as exc:
                    LOGGER.warning("PostgreSQL: could not check unique columns for %s: %s (non-fatal)", table.name, exc)

            if indexes_recreated > 0:
                LOGGER.info("PostgreSQL: recreated %d missing indexes.", indexes_recreated)

        # Second pass: vacuum and update statistics via VACUUM ANALYZE
        with target_engine.connect() as conn:
            for idx, table in enumerate(tables, start=1):
                _progress(f"[{idx}/{total}] VACUUM ANALYZE {table.name}")
                try:
                    conn.execute(text(f"VACUUM ANALYZE {_pg_quote_ident(table.name)}"))
                except Exception as exc:
                    LOGGER.warning("VACUUM ANALYZE failed for %s: %s (non-fatal)", table.name, exc)
            conn.commit()
            _progress_done()
        LOGGER.info("PostgreSQL: tables vacuumed and index statistics updated via VACUUM ANALYZE on %d tables.", total)

    elif dialect_name in ("mysql", "mariadb"):
        # First pass: recreate missing unique constraint indexes
        with target_engine.begin() as conn:
            insp = inspect(conn)
            indexes_recreated = 0
            for table in tables:
                existing_indexes = insp.get_indexes(table.name)
                existing_col_sets = [set(idx["column_names"]) for idx in existing_indexes]
                existing_constraints = insp.get_unique_constraints(table.name) or []
                existing_constraint_col_sets = [set(c.get("column_names", [])) for c in existing_constraints]

                # Get expected unique constraints from model (table_args)
                if table.table_args and isinstance(table.table_args, tuple):
                    for arg in table.table_args:
                        if isinstance(arg, UniqueConstraint):
                            cols = [c.name for c in arg.columns]
                            col_set = set(cols)
                            try:
                                if col_set not in existing_col_sets and col_set not in existing_constraint_col_sets:
                                    # Index/constraint missing, create it
                                    idx_name = f"ix_{table.name}_{'_'.join(cols)}"
                                    cols_sql = ", ".join(_mysql_quote_ident(c) for c in cols)
                                    try:
                                        conn.execute(text(f"CREATE UNIQUE INDEX {_mysql_quote_ident(idx_name)} ON {_mysql_quote_ident(table.name)} ({cols_sql})"))
                                        LOGGER.info("MySQL/MariaDB: created missing index %s on %s(%s)", idx_name, table.name, ", ".join(cols))
                                        indexes_recreated += 1
                                    except Exception as exc:
                                        LOGGER.warning("MySQL/MariaDB: failed to create index %s: %s (non-fatal)", idx_name, exc)
                            except Exception as exc:
                                LOGGER.warning("MySQL/MariaDB: could not check indexes for %s: %s (non-fatal)", table.name, exc)

                # Also check for single-column unique=True constraints
                try:
                    for column in table.columns:
                        if column.unique:
                            col_set = {column.name}
                            if col_set not in existing_col_sets and col_set not in existing_constraint_col_sets:
                                # Unique index missing on this column, create it
                                idx_name = f"ix_{table.name}_{column.name}"
                                try:
                                    conn.execute(text(f"CREATE UNIQUE INDEX {_mysql_quote_ident(idx_name)} ON {_mysql_quote_ident(table.name)} ({_mysql_quote_ident(column.name)})"))
                                    LOGGER.info("MySQL/MariaDB: created missing unique index %s on %s(%s)", idx_name, table.name, column.name)
                                    indexes_recreated += 1
                                except Exception as exc:
                                    LOGGER.warning("MySQL/MariaDB: failed to create unique index %s: %s (non-fatal)", idx_name, exc)
                except Exception as exc:
                    LOGGER.warning("MySQL/MariaDB: could not check unique columns for %s: %s (non-fatal)", table.name, exc)

            if indexes_recreated > 0:
                LOGGER.info("MySQL/MariaDB: recreated %d missing indexes.", indexes_recreated)

        # Second pass: update statistics
        table_list = ", ".join(_mysql_quote_ident(t.name) for t in tables)
        with target_engine.begin() as conn:
            LOGGER.info("MySQL/MariaDB: running ANALYZE TABLE on %d tables ...", total)
            conn.execute(text(f"ANALYZE TABLE {table_list}"))
        LOGGER.info("MySQL/MariaDB: index statistics updated.")

    else:
        LOGGER.debug("Index rebuild skipped for dialect %r (not supported).", dialect_name)


def _post_copy_apply_primary_keys(target_engine: Engine) -> None:
    """
    Post-copy step: ensure primary key constraints match the SQLAlchemy model.

    Reads primary keys from `src/common/db/model.py` via the imported SQLAlchemy `Base`
    metadata, then applies missing (and can repair mismatched) PK constraints on the
    target database.
    """
    dialect_name = (getattr(target_engine.dialect, "name", "") or "").lower()
    if dialect_name not in ("postgresql", "mysql", "mariadb"):
        return

    from sqlalchemy import inspect

    def _pg_find_table_schema(conn, table_name: str) -> str:
        # Prefer `public` when available; otherwise pick the first schema containing the table.
        row = conn.execute(
            text(
                """
                SELECT n.nspname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = :t
                ORDER BY (n.nspname = 'public') DESC
                LIMIT 1
                """
            ),
            {"t": table_name},
        ).scalar()
        return str(row) if row else "public"

    expected_pk_tables = [t for t in Base.metadata.sorted_tables if t.primary_key and t.primary_key.columns]
    if not expected_pk_tables:
        return

    def _pg_reverse_fk_count(conn, schema_name: str, table_name: str) -> int:
        # If any other table has a FK referencing this table, dropping/recreating the PK
        # is risky (dependency may prevent drop, or FKs may become invalid).
        row = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM pg_constraint
                WHERE contype = 'f'
                  AND confrelid = (:rel)::regclass
                """
            ),
            {"rel": f"{schema_name}.{table_name}"},
        ).scalar()
        return int(row or 0)

    with target_engine.begin() as conn:
        insp = inspect(conn)
        for table in expected_pk_tables:
            expected_cols = [col.name for col in table.primary_key.columns]
            if not expected_cols:
                continue

            # SQLAlchemy inspector returns primary key constraint info (name + constrained_columns).
            try:
                if dialect_name == "postgresql":
                    schema_name = _pg_find_table_schema(conn, table.name)
                    pk_info = insp.get_pk_constraint(table.name, schema=schema_name) or {}
                else:
                    pk_info = insp.get_pk_constraint(table.name) or {}
            except Exception as exc:
                LOGGER.warning("Could not inspect PK for table %s: %s", table.name, exc)
                pk_info = {}

            existing_cols = list(pk_info.get("constrained_columns") or [])
            if existing_cols:
                if existing_cols == expected_cols:
                    continue

                # PK exists but columns mismatch. Since this runs as a backend migration
                # (target is not in production yet), we try to repair.
                LOGGER.warning(
                    "Primary key mismatch for %s: existing=%s expected=%s (attempting repair).",
                    table.name,
                    existing_cols,
                    expected_cols,
                )

                try:
                    if dialect_name == "postgresql":
                        # Avoid dropping PK when other tables reference it.
                        if _pg_reverse_fk_count(conn, schema_name, table.name) > 0:
                            LOGGER.error(
                                "Cannot repair PK for %s: other tables have FKs referencing this table. Skipping.",
                                table.name,
                            )
                            continue

                        existing_pk_name = pk_info.get("name") or None
                        if not existing_pk_name:
                            LOGGER.error("Cannot repair PK for %s: existing PK constraint name not found.", table.name)
                            continue

                        conn.execute(
                            text(
                                f"ALTER TABLE {_pg_quote_ident(schema_name)}.{_pg_quote_ident(table.name)} "
                                f"DROP CONSTRAINT {_pg_quote_ident(existing_pk_name)}"
                            )
                        )

                        constraint_name = _pg_pk_constraint_name(table.name)
                        cols_sql = ", ".join(_pg_quote_ident(c) for c in expected_cols)
                        conn.execute(
                            text(
                                f"ALTER TABLE {_pg_quote_ident(schema_name)}.{_pg_quote_ident(table.name)} "
                                f"ADD CONSTRAINT {_pg_quote_ident(constraint_name)} PRIMARY KEY ({cols_sql})"
                            )
                        )
                        LOGGER.info("Repaired PostgreSQL PK for %s.", table.name)
                    else:
                        # MySQL/MariaDB: easiest repair is drop/re-add PRIMARY KEY.
                        conn.execute(text(f"ALTER TABLE {_mysql_quote_ident(table.name)} DROP PRIMARY KEY"))
                        cols_sql = ", ".join(_mysql_quote_ident(c) for c in expected_cols)
                        conn.execute(text(f"ALTER TABLE {_mysql_quote_ident(table.name)} ADD PRIMARY KEY ({cols_sql})"))
                        LOGGER.info("Repaired MySQL/MariaDB PK for %s.", table.name)
                except Exception as exc:
                    LOGGER.error("Failed to repair PK for table %s: %s", table.name, exc)
                    raise

                continue
            if dialect_name == "postgresql":
                schema_name = _pg_find_table_schema(conn, table.name)
                constraint_name = _pg_pk_constraint_name(table.name)
                cols_sql = ", ".join(_pg_quote_ident(c) for c in expected_cols)
                ddl = (
                    f"ALTER TABLE {_pg_quote_ident(schema_name)}.{_pg_quote_ident(table.name)} "
                    f"ADD CONSTRAINT {_pg_quote_ident(constraint_name)} PRIMARY KEY ({cols_sql})"
                )
                LOGGER.info("Adding missing PostgreSQL primary key on %s(%s)", table.name, ", ".join(expected_cols))
            else:
                # MySQL/MariaDB: PK name is always PRIMARY, so use ALTER TABLE ... ADD PRIMARY KEY (...)
                cols_sql = ", ".join(_mysql_quote_ident(c) for c in expected_cols)
                ddl = f"ALTER TABLE {_mysql_quote_ident(table.name)} ADD PRIMARY KEY ({cols_sql})"
                LOGGER.info("Adding missing MySQL/MariaDB primary key on %s(%s)", table.name, ", ".join(expected_cols))

            conn.execute(text(ddl))

        # Verify PKs after any add/repair operations.
        # This makes the migration self-validating even in environments where `tests/`
        # is not installed (e.g. production images).
        mismatches: list[str] = []
        for table in expected_pk_tables:
            expected_cols = [col.name for col in table.primary_key.columns]
            if not expected_cols:
                continue

            try:
                if dialect_name == "postgresql":
                    schema_name = _pg_find_table_schema(conn, table.name)
                    pk_info = insp.get_pk_constraint(table.name, schema=schema_name) or {}
                else:
                    pk_info = insp.get_pk_constraint(table.name) or {}
            except Exception as exc:
                mismatches.append(f"{table.name}: could not inspect PK ({exc})")
                continue

            existing_cols = list(pk_info.get("constrained_columns") or [])
            if not existing_cols:
                mismatches.append(f"{table.name}: missing primary key (expected {expected_cols})")
                continue

            if set(existing_cols) != set(expected_cols) or len(existing_cols) != len(expected_cols):
                mismatches.append(f"{table.name}: existing={existing_cols} expected={expected_cols}")

        if mismatches:
            # Raising here prevents swapping/using a partially broken schema.
            raise RuntimeError("Primary key layout verification failed:\n" + "\n".join(mismatches))


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


def _import_files_to_target(dump_dir: Path, target_engine: Engine) -> Dict[str, int]:
    """
    Import per-table JSONL files into the target database via SQLAlchemy bulk inserts.
    No native client tools required; SSL and auth are handled by the driver.
    """
    import json
    import base64
    from sqlalchemy import inspect

    tables = list(Base.metadata.sorted_tables)
    total_tables = max(1, len(tables))

    from sqlalchemy.sql.type_api import TypeDecorator

    _all_skipped: Dict[str, int] = {}  # table_name -> orphaned rows skipped

    def _deserialise(v: object, col_type=None) -> object:
        if isinstance(v, dict) and "__b64__" in v:
            return base64.b64decode(v["__b64__"])

        # SQLite DateTime columns expect Python `datetime` objects.
        # During dump we serialize datetime/date/etc as strings, so we need to parse them back.
        if isinstance(v, str) and col_type is not None:
            try:
                py_t = getattr(col_type, "python_type", None)
            except Exception:
                py_t = None
            if py_t is datetime:
                s = v.strip()
                # Normalize common variants.
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                try:
                    return datetime.fromisoformat(s)
                except ValueError:
                    pass
            elif getattr(py_t, "__name__", None) == "date":
                # Handle DATE columns stored as ISO strings.
                try:
                    from datetime import date as _date

                    s = v.strip()
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"
                    return _date.fromisoformat(s)
                except Exception:
                    pass

        # TypeDecorator columns (e.g. custom JSON-as-text) expect a Python object,
        # not a raw JSON string. SQLite stores them as text; parse them back here.
        if isinstance(v, str) and col_type is not None and isinstance(col_type, TypeDecorator):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                pass
        return v

    # Disable FK constraint enforcement during bulk import on all backends.
    # The source DB (especially MySQL/SQLite) may have orphaned rows that were silently
    # accepted because FK enforcement was off or missing on the source.
    is_mysql = target_engine.dialect.name in ("mysql", "mariadb")
    is_pg    = target_engine.dialect.name == "postgresql"

    # For PostgreSQL: session_replication_role=replica disables FK trigger checks.
    # Requires the db user to have the REPLICATION attribute or superuser.
    # If not available, fall back to filtering orphaned FK rows at insert time.
    pg_fk_disabled = False

    with target_engine.connect() as tgt_conn:
        if is_mysql:
            tgt_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            tgt_conn.commit()
        elif is_pg:
            try:
                tgt_conn.execute(text("SET session_replication_role = replica"))
                tgt_conn.commit()
                pg_fk_disabled = True
                LOGGER.info("PostgreSQL FK checks disabled via session_replication_role=replica.")
            except Exception as _pg_fk_exc:
                tgt_conn.rollback()  # clear the aborted transaction before any further use
                LOGGER.warning(
                    "Could not disable PostgreSQL FK checks (session_replication_role requires REPLICATION privilege): %s. "
                    "Will filter orphaned rows instead.",
                    _pg_fk_exc,
                )

        # Pre-load FK parent sets for orphan filtering (used only when pg_fk_disabled=False)
        # Maps table_name -> {fk_col -> set(known parent values)}
        _fk_parent_cache: Dict[str, Dict[str, set]] = {}
        if is_pg and not pg_fk_disabled:
            for tbl in tables:
                for fk in tbl.foreign_keys:
                    parent_tbl = fk.column.table.name
                    fk_col     = fk.parent.name
                    if parent_tbl not in _fk_parent_cache:
                        _fk_parent_cache[parent_tbl] = {}
                    dump_file = dump_dir / f"{parent_tbl}.jsonl"
                    if dump_file.is_file() and fk.column.name not in _fk_parent_cache.get(parent_tbl, {}):
                        import json as _json2
                        parent_vals: set = set()
                        with dump_file.open("r", encoding="utf-8") as _pfh:
                            for _praw in _pfh:
                                _praw = _praw.strip()
                                if _praw:
                                    parent_vals.add(_json2.loads(_praw).get(fk.column.name))
                        _fk_parent_cache.setdefault(parent_tbl, {})[fk.column.name] = parent_vals

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

                # Build per-table FK filter for orphan detection (fallback when FK checks not disabled)
                _fk_filters: list = []  # list of (row_col, parent_table, parent_col)
                if is_pg and not pg_fk_disabled:
                    for fk in table.foreign_keys:
                        parent_vals = _fk_parent_cache.get(fk.column.table.name, {}).get(fk.column.name)
                        if parent_vals is not None:
                            _fk_filters.append((fk.parent.name, fk.column.table.name, fk.column.name, parent_vals))
                _orphans_skipped = 0

                with table_file.open("r", encoding="utf-8") as fh:
                    for raw in fh:
                        raw = raw.strip()
                        if not raw:
                            continue
                        row = {k: _deserialise(v, col_types.get(k)) for k, v in json.loads(raw).items()}
                        # Skip orphaned rows that would violate FK constraints
                        if _fk_filters:
                            orphan = False
                            for row_col, parent_tbl, parent_col, parent_vals in _fk_filters:
                                val = row.get(row_col)
                                if val is not None and val not in parent_vals:
                                    orphan = True
                                    break
                            if orphan:
                                _orphans_skipped += 1
                                continue
                        batch.append(row)
                        row_count += 1
                        if len(batch) >= _DUMP_BATCH_SIZE:
                            _flush(batch)
                            batch = []
                            if row_count % 5000 == 0:
                                _progress(f"[{idx}/{total_tables}] Importing {table.name} ({row_count} rows)")

                _flush(batch)
                if _orphans_skipped:
                    _all_skipped[table.name] = _orphans_skipped
                    LOGGER.warning(
                        "[%d/%d] Imported %s: %d rows (%d orphaned FK rows skipped — "
                        "referenced parent rows missing in source data).",
                        idx, total_tables, table.name, row_count, _orphans_skipped,
                    )
                else:
                    LOGGER.info("[%d/%d] Imported %s: %d rows.", idx, total_tables, table.name, row_count)

        finally:
            if is_mysql:
                tgt_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                tgt_conn.commit()
            elif is_pg and pg_fk_disabled:
                tgt_conn.execute(text("SET session_replication_role = DEFAULT"))
                tgt_conn.commit()
                LOGGER.info("PostgreSQL FK checks re-enabled.")

    # Resync auto-increment/sequence counters after explicit-id imports.
    # Without this, PostgreSQL nextval()/AUTO_INCREMENT may still return an already used id.
    if is_pg:
        with target_engine.connect() as tgt_conn:
            for table in tables:
                # Only attempt to resync integer identity/serial PKs named `id`.
                if not hasattr(table, "c") or "id" not in table.c:
                    continue

                seq_name = tgt_conn.execute(text(f"SELECT pg_get_serial_sequence('{table.name}', 'id')")).scalar()
                if not seq_name:
                    continue

                max_id = tgt_conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table.name}")).scalar() or 0
                # setval() requires sequence name as identifier, not parameter.
                tgt_conn.execute(text(f"SELECT setval('{seq_name}', :val, true)"), {"val": int(max_id)})
                LOGGER.info("PostgreSQL sequence re-synchronized for %s.id.", table.name)

            tgt_conn.commit()
    elif is_mysql:
        with target_engine.connect() as tgt_conn:
            max_id = tgt_conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM bw_jobs_runs")).scalar() or 0
            tgt_conn.execute(text("ALTER TABLE bw_jobs_runs AUTO_INCREMENT = :val"), {"val": int(max_id) + 1})
            LOGGER.info("MySQL AUTO_INCREMENT re-synchronized for bw_jobs_runs.id.")
            tgt_conn.commit()

    # Ensure primary key constraints exist after bulk data imports
    # (applies to both PostgreSQL and MySQL/MariaDB).
    _post_copy_apply_primary_keys(target_engine)

    # Rebuild index statistics after bulk data import for optimal query performance.
    # (applies to all backends).
    _post_copy_rebuild_indexes(target_engine)

    _progress_done()
    LOGGER.info("Import complete: %d tables loaded into target.", total_tables)
    return _all_skipped


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} TB"


def _check_source_size(source_engine: Engine, source_uri: str, dump_root: Path) -> None:
    """Estimate the source DB size and compare against free space in the dump directory.
    Logs a warning if free space is less than 2× the estimated source size."""
    try:
        uri_lower = source_uri.lower()
        db_bytes: Optional[int] = None

        with source_engine.connect() as conn:
            if uri_lower.startswith("sqlite"):
                # SQLite: page_count × page_size gives the actual file size
                page_count = conn.execute(text("PRAGMA page_count")).scalar()
                page_size  = conn.execute(text("PRAGMA page_size")).scalar()
                if page_count and page_size:
                    db_bytes = int(page_count) * int(page_size)
            elif "mysql" in uri_lower or "mariadb" in uri_lower:
                # MySQL/MariaDB: sum data_length + index_length from information_schema
                row = conn.execute(text(
                    "SELECT SUM(data_length + index_length) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE()"
                )).fetchone()
                if row and row[0] is not None:
                    db_bytes = int(row[0])
            elif "postgresql" in uri_lower or "psycopg" in uri_lower:
                row = conn.execute(text("SELECT pg_database_size(current_database())")).fetchone()
                if row and row[0] is not None:
                    db_bytes = int(row[0])

        if db_bytes is None:
            LOGGER.info("Source database size: (could not determine)")
            return

        LOGGER.info("Source database size: %s", _fmt_bytes(db_bytes))

        # Check free space in the dump directory's filesystem
        try:
            dump_root.mkdir(parents=True, exist_ok=True)
            stat = shutil.disk_usage(dump_root)
            free = stat.free
            needed = db_bytes * 2  # dump files (JSONL) may expand vs raw binary storage
            LOGGER.info(
                "Temp space: %s free in %s (need ~%s for dump, 2× source size)",
                _fmt_bytes(free), dump_root, _fmt_bytes(needed),
            )
            if free < needed:
                LOGGER.warning(
                    "LOW DISK SPACE: %s free in %s but ~%s needed (2× source size %s). "
                    "Migration may fail mid-way. Free up space or point /tmp to a larger filesystem.",
                    _fmt_bytes(free), dump_root, _fmt_bytes(needed), _fmt_bytes(db_bytes),
                )
        except Exception as exc:
            LOGGER.warning("Could not check free space in %s: %s", dump_root, exc)

    except Exception as exc:
        LOGGER.warning("Source size check failed (non-fatal): %s", exc)


def _print_tls_overview(tls_results: Dict[str, Dict[str, str]]) -> None:
    """Print a compact TLS summary table for all probed hosts."""
    if not tls_results:
        return
    _col_ip  = max(len("Host/IP"),  max(len(ip) for ip in tls_results))
    _col_ver = max(len("Protocol"), max(len(i.get("version", "")) for i in tls_results.values()))
    _col_cip = max(len("Cipher"),   max(len(i.get("cipher",  "")) for i in tls_results.values()))
    _col_exp = max(len("Expires"),  max(len(i.get("cert_expiry", "")) for i in tls_results.values()))
    _col_ttl = max(len("TTL"),      max(len(i.get("cert_ttl",    "")) for i in tls_results.values()))
    _col_ca  = max(len("Root CA"),  max(len(i.get("root_ca",     "")) for i in tls_results.values()))
    _col_st  = max(len("Status"),   max(len(i.get("status",      "")) for i in tls_results.values()))
    _hdr = (
        f"{'Host/IP':<{_col_ip}}  {'Protocol':<{_col_ver}}  {'Cipher':<{_col_cip}}"
        f"  {'Expires':<{_col_exp}}  {'TTL':<{_col_ttl}}  {'Root CA':<{_col_ca}}  {'Status':<{_col_st}}"
    )
    _sep = "-" * len(_hdr)
    _rows = []
    _has_warn = False
    for _ip, _info in tls_results.items():
        _status = _info.get("status", "")
        _crit_flag = " !! CRITICAL CERT EXPIRY" if _info.get("cert_critical") == "1" else ""
        if _status.startswith("WARN") or _status.startswith("FAILED") or _crit_flag:
            _has_warn = True
        _rows.append(
            "%-*s  %-*s  %-*s  %-*s  %-*s  %-*s  %-*s%s" % (
                _col_ip,  _ip,
                _col_ver, _info.get("version", ""),
                _col_cip, _info.get("cipher",  ""),
                _col_exp, _info.get("cert_expiry", ""),
                _col_ttl, _info.get("cert_ttl",    ""),
                _col_ca,  _info.get("root_ca",     ""),
                _col_st,  _status,
                _crit_flag,
            )
        )
    _table = "\n".join([_sep, _hdr, _sep] + _rows + [_sep])
    _log = LOGGER.warning if _has_warn else LOGGER.info
    _log("TLS overview:\n%s", _table)


def _main() -> int:
    """
    Entrypoint for the standalone migration script.
    """
    LOGGER.info("bw_db_migrate version %s running from: %s", __version__, Path(__file__).resolve())
    concurrent = _pid_check_concurrent()
    if concurrent:
        LOGGER.warning("Another bw_db_migrate instance appears to be running: %s", concurrent)
        LOGGER.warning("If that process is dead, remove %s and retry.", _PID_FILE)
    _pid_write("startup")
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
    parser.add_argument(
        "--auto-switch",
        action="store_true",
        help=(
            "After a successful migration, update DATABASE_URI in --env-file to point to the target URI "
            "and restart bunkerweb services via systemctl (bunkerweb*, bunkerweb-scheduler, bunkerweb-ui)."
        ),
    )
    parser.add_argument("--tui", action="store_true", help="Launch an interactive terminal UI to collect inputs.")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging (prints all messages).")
    args = parser.parse_args()

    if args.debug:
        import logging as _logging
        _logging.getLogger().setLevel(_logging.DEBUG)
        LOGGER.setLevel(_logging.DEBUG)
        LOGGER.debug("Debug logging enabled.")

    _log_file: Optional[Path] = None
    # Always write a full debug log to the temp dir (all levels, regardless of --debug flag)
    try:
        import logging as _logging2
        _log_dir = Path("/tmp/bunkerweb/bw_db_migrate")
        _log_dir.mkdir(parents=True, exist_ok=True)
        # Use a timestamped filename so each run gets its own log file.
        _log_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        _log_file = _log_dir / f"bw_db_migrate_{_log_ts}.log"
        _fh = _logging2.FileHandler(_log_file, mode="w", encoding="utf-8")
        _fh.setLevel(_logging2.DEBUG)
        _fh.setFormatter(_logging2.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        _logging2.getLogger().addHandler(_fh)
        LOGGER.info("Debug log file: %s", _log_file)
        # Prune old logs, keeping only the 5 most recent.
        _old_logs = sorted(_log_dir.glob("bw_db_migrate_*.log"), key=lambda p: p.stat().st_mtime)
        for _old in _old_logs[:-5]:
            try:
                _old.unlink()
            except Exception:
                pass
    except Exception as _fh_exc:
        LOGGER.warning("Unable to create debug log file: %s", _fh_exc)

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
    # Main migration engines get a 15-minute connect timeout so large imports are
    # not interrupted. Probe/test connections override this back to 2 s themselves.
    _main_connect_args = dict(engine_kwargs.get("connect_args") or {})  # type: ignore[arg-type]
    _main_connect_args["connect_timeout"] = 900
    engine_kwargs["connect_args"] = _main_connect_args

    # Ensure dump root exists and clean up any stale dump-* subdirs from previous runs.
    # The root itself is kept so any existing debug log is not deleted.
    try:
        _DUMP_ROOT.mkdir(parents=True, exist_ok=True)
        for _stale in _DUMP_ROOT.glob("dump-*"):
            if _stale.is_dir():
                shutil.rmtree(_stale)
    except Exception as exc:
        LOGGER.error("Unable to prepare dump directory %s: %s", _DUMP_ROOT, exc)
        return 1

    if not source_uri:
        LOGGER.error("DATABASE_URI is not set (CLI --source-uri, env file, or environment).")
        return 1
    if not target_uri and not args.dry_run:
        LOGGER.error("DB_MIGRATION_TARGET_URI is not set (CLI --target-uri, env file, or environment).")
        return 1

    LOGGER.info("Source DATABASE_URI: %r", _mask_uri_password(source_uri))
    LOGGER.info("Target DB_MIGRATION_TARGET_URI: %r", _mask_uri_password(target_uri))

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
        _all_tls_results: Dict[str, Dict[str, str]] = {}  # ip -> tls_info, populated during SSL probe
        _server_supports_ssl = False
        _server_ca_pem: Optional[str] = None

        def _emit_ssl_advisories(ssl_is_enabled: bool, server_supports: Optional[bool], ca_pem: object) -> None:
            # ca_pem is either None, a PEM string (root CA), or ("__leaf__", pem_str)
            _is_leaf = isinstance(ca_pem, tuple) and ca_pem[0] == "__leaf__"
            _pem_str: Optional[str] = ca_pem[1] if _is_leaf else (ca_pem if isinstance(ca_pem, str) else None)  # type: ignore[index]

            if not ssl_is_enabled and server_supports:
                LOGGER.warning("=" * 60)
                LOGGER.warning("ADVISORY: SSL is not enabled in your target URI, but the target")
                LOGGER.warning("database server supports SSL/TLS. Enable SSL to protect data in transit.")
                if _pem_str and not _is_leaf:
                    LOGGER.warning("The server's root CA certificate was retrieved during the probe.")
                    LOGGER.warning("Save it and reference it in your URI:")
                    LOGGER.warning("  sudo tee /etc/ssl/certs/bw-migration-ca.pem << 'EOF'")
                    for _line in _pem_str.splitlines():
                        LOGGER.warning("  %s", _line)
                    LOGGER.warning("  EOF")
                    LOGGER.warning("  DB_MIGRATION_TARGET_URI=...?ssl=true&ssl_ca=/etc/ssl/certs/bw-migration-ca.pem")
                elif _is_leaf:
                    LOGGER.warning("The server returned a leaf (server) certificate, not a root CA.")
                    LOGGER.warning("Obtain the root CA PEM from your database administrator or cluster")
                    LOGGER.warning("configuration and reference it in your URI:")
                    LOGGER.warning("  DB_MIGRATION_TARGET_URI=...?ssl=true&ssl_ca=/path/to/root-ca.pem")
                else:
                    LOGGER.warning("  DB_MIGRATION_TARGET_URI=...?ssl=true&ssl_ca=/path/to/ca.pem")
                LOGGER.warning("=" * 60)
            elif ssl_is_enabled and not ca_path:
                LOGGER.warning("=" * 60)
                LOGGER.warning("ADVISORY: SSL is enabled but no CA file is set — certificate verification")
                LOGGER.warning("is relying on the system trust store, which may not include your database")
                LOGGER.warning("server's private CA. If you see certificate errors, retrieve the root CA")
                LOGGER.warning("PEM from your database administrator and save it:")
                LOGGER.warning("  sudo tee /etc/ssl/certs/bw-migration-ca.pem << 'EOF'")
                LOGGER.warning("  <paste root CA PEM here — not the leaf/server cert>")
                LOGGER.warning("  EOF")
                LOGGER.warning("  DB_MIGRATION_TARGET_URI=...?ssl=true&ssl_ca=/etc/ssl/certs/bw-migration-ca.pem")
                LOGGER.warning("=" * 60)

        if target_uri:
            ssl_expected = _uri_uses_ssl(target_uri)
            host, port = _resolve_target_host_port(target_uri)
            ips = _resolve_ips(host)
            ca_path = _extract_ca_from_uri(target_uri)
            cafile, capath = _system_ca_summary()

            # Verify CA file exists and is readable by the nginx user.
            # This script may run as root, so we check permissions explicitly
            # against the nginx user rather than relying on open() succeeding.
            if ca_path:
                import errno as _errno
                import pwd as _pwd
                import grp as _grp
                import stat as _stat

                _ca_exists = Path(ca_path).exists()
                if not _ca_exists:
                    LOGGER.error(
                        "CA file '%s' does not exist. "
                        "Verify the path in your URI (ssl_ca= / sslrootcert=) is correct.",
                        ca_path,
                    )
                    return False

                # Determine nginx uid/gid (fall back to current process if nginx user not found)
                try:
                    _nginx_pw = _pwd.getpwnam("nginx")
                    _nginx_uid = _nginx_pw.pw_uid
                    _nginx_gid = _nginx_pw.pw_gid
                    _nginx_groups = {g.gr_gid for g in _grp.getgrall() if "nginx" in g.gr_mem}
                    _nginx_groups.add(_nginx_gid)
                    _check_user = "nginx"
                except KeyError:
                    _nginx_uid = os.getuid()
                    _nginx_gid = os.getgid()
                    _nginx_groups = {_nginx_gid}
                    _check_user = f"uid={_nginx_uid}"

                # Walk from the file up to root, checking execute (x) on each directory
                # and read (r) on the file itself for the nginx user.
                def _nginx_can_read(path: str) -> bool:
                    """Return True if the nginx user can read this file."""
                    p = Path(path).resolve()
                    # Check each component for execute permission
                    for ancestor in list(p.parents)[::-1]:
                        try:
                            _st = ancestor.stat()
                        except OSError:
                            return False
                        _m = _st.st_mode
                        if _st.st_uid == _nginx_uid:
                            if not _m & _stat.S_IXUSR:
                                return False
                        elif _st.st_gid in _nginx_groups:
                            if not _m & _stat.S_IXGRP:
                                return False
                        else:
                            if not _m & _stat.S_IXOTH:
                                return False
                    # Check read permission on the file itself
                    try:
                        _st = p.stat()
                    except OSError:
                        return False
                    _m = _st.st_mode
                    if _st.st_uid == _nginx_uid:
                        return bool(_m & _stat.S_IRUSR)
                    elif _st.st_gid in _nginx_groups:
                        return bool(_m & _stat.S_IRGRP)
                    else:
                        return bool(_m & _stat.S_IROTH)

                if not _nginx_can_read(ca_path):
                    _ca_dir = str(Path(ca_path).parent)
                    _st = Path(ca_path).stat()
                    _mode_oct = oct(_st.st_mode)[-4:]
                    try:
                        _owner = _pwd.getpwuid(_st.st_uid).pw_name
                    except KeyError:
                        _owner = str(_st.st_uid)
                    try:
                        _group = _grp.getgrgid(_st.st_gid).gr_name
                    except KeyError:
                        _group = str(_st.st_gid)
                    LOGGER.error(
                        "CA file '%s' is not readable by user '%s' (file: %s %s:%s).",
                        ca_path, _check_user, _mode_oct, _owner, _group,
                    )
                    LOGGER.error(
                        "Files in '%s' may have restricted permissions (e.g. mode 710, root:ssl-cert). "
                        "The nginx user cannot read them.",
                        _ca_dir,
                    )
                    LOGGER.error("Fix: copy the CA file to a location readable by nginx, e.g.:")
                    LOGGER.error("  sudo cp %s /etc/bunkerweb/ca.pem", ca_path)
                    LOGGER.error("  sudo chown root:nginx /etc/bunkerweb/ca.pem")
                    LOGGER.error("  sudo chmod 640 /etc/bunkerweb/ca.pem")
                    LOGGER.error(
                        "Then update your URI: ...?ssl=true&ssl_ca=/etc/bunkerweb/ca.pem"
                    )
                    return False
                else:
                    LOGGER.debug("CA file '%s' is readable by user '%s'.", ca_path, _check_user)

            LOGGER.info("Target connect details: host=%s port=%s ips=%s", host or "(unknown)", port or "(unknown)", ",".join(ips) if ips else "(unresolved)")
            LOGGER.info("Target SSL requested: %s", "yes" if ssl_expected else "no")
            if ssl_expected:
                LOGGER.info("Target CA file: %s", ca_path if ca_path else "(not set)")
                if not ca_path:
                    LOGGER.info("System CA bundle: cafile=%s capath=%s", cafile or "(none)", capath or "(none)")
                LOGGER.info("SSL verification: verifying server certificate (CA=%s).", ca_path if ca_path else "system-default")

            target_engine = _create_engine(target_uri, engine_kwargs=engine_kwargs)
            try:
                with target_engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            except Exception as ssl_exc:
                err_str = str(ssl_exc).lower()
                if ssl_expected and ("certificate" in err_str or "ssl" in err_str or "tls" in err_str):
                    # SSL cert verification failed — try falling back to system CA bundle
                    LOGGER.error("SSL certificate verification failed with configured CA: %s", ssl_exc)
                    try:
                        from sqlalchemy.engine.url import make_url as _mu

                        _url = _mu(target_uri)
                        _q = dict(_url.query or {})
                        _q.pop("sslrootcert", None)  # remove custom CA → use system bundle
                        _q.pop("ssl_ca", None)
                        _sysca_uri = str(_url.set(query=_q))
                        _sysca_engine = _create_engine(_sysca_uri, engine_kwargs=engine_kwargs)
                        with _sysca_engine.connect() as _conn:
                            _conn.execute(text("SELECT 1"))
                        # System CA succeeded — switch to it and continue
                        LOGGER.error(
                            "The configured CA file does not match the server certificate, "
                            "but the system CA bundle validates it successfully. "
                            "Remove the sslrootcert / ssl_ca parameter from your target URI to use the system CA."
                        )
                        target_engine = _sysca_engine
                        target_uri = _sysca_uri
                        LOGGER.info("Falling back to system CA bundle for target connection.")
                    except Exception as sysca_exc:
                        err_sysca = str(sysca_exc).lower()
                        if "password" in err_sysca or "authentication" in err_sysca:
                            # Auth failure means SSL handshake with system CA succeeded
                            LOGGER.error(
                                "The configured CA file does not match the server certificate, "
                                "but the system CA bundle validates it successfully. "
                                "Remove the sslrootcert / ssl_ca parameter from your target URI to use the system CA."
                            )
                            target_engine = _create_engine(_sysca_uri, engine_kwargs=engine_kwargs)
                            target_uri = _sysca_uri
                            LOGGER.info("Falling back to system CA bundle for target connection.")
                        else:
                            LOGGER.warning("System CA bundle fallback also failed: %s", sysca_exc)
                            raise ssl_exc
                else:
                    _err_lower = str(ssl_exc).lower()
                    if "password" in _err_lower or "authentication failed" in _err_lower:
                        LOGGER.error(
                            "Authentication failed for target database: %s\n"
                            "  → Check that the user exists and the password in DB_MIGRATION_TARGET_URI is correct.\n"
                            "  → If you just recreated the user/database, make sure the new password matches.",
                            _mask_uri_password(target_uri),
                        )
                        return 1
                    raise
            if ssl_expected:
                # Perform explicit verification and certificate introspection for MySQL/MariaDB+pymysql.
                _verify_mysql_ssl_and_log_details(target_uri)
                # Fetch and log the full certificate chain including root CA.
                # When multiple IPs resolve (HA cluster), probe each node so all
                # certificates are verified — nodes may have different leaf certs.
                _starttls = "postgres" if ("postgresql" in target_uri.lower() or "psycopg" in target_uri.lower()) else "mysql"
                _probe_ips = ips if ips else [host]
                _probe_port = int(port) if port else (5432 if _starttls == "postgres" else 3306)
                if len(_probe_ips) > 1:
                    LOGGER.info(
                        "HA cluster detected: %d nodes resolved for %s (%s). "
                        "Probing each node for TLS certificate and cipher verification.",
                        len(_probe_ips), host, ", ".join(_probe_ips),
                    )
                _node_tls_results: Dict[str, Dict[str, str]] = {}
                for _probe_ip in _probe_ips:  # type: ignore[assignment]
                    _connect_ip_arg = _probe_ip if _probe_ip != host else None
                    LOGGER.info("SSL chain probe: node %s (%s:%s)", _probe_ip, host, _probe_port)
                    _tls_info = _log_ssl_chain(
                        host or _probe_ip,
                        _probe_port,
                        ca_file=ca_path or None,
                        starttls=_starttls,
                        connect_ip=_connect_ip_arg,
                    )
                    if _tls_info:
                        _node_tls_results[_probe_ip] = _tls_info
                        _all_tls_results[_probe_ip] = _tls_info
                    else:
                        _failed: Dict[str, str] = {"status": "FAILED: connection error"}
                        _node_tls_results[_probe_ip] = _failed
                        _all_tls_results[_probe_ip] = _failed
                    _enumerate_node_ciphers(
                        host or _probe_ip,
                        _probe_port,
                        ca_file=ca_path or None,
                        starttls=_starttls,
                        connect_ip=_connect_ip_arg,
                    )

                # Compare TLS settings across all nodes
                _ok_tls_results = {_ip: _info for _ip, _info in _node_tls_results.items() if _info.get("version")}
                if len(_ok_tls_results) == 1:
                    # Single node: just print the PEM once
                    _solo = next(iter(_ok_tls_results.values()))
                    if _solo.get("root_ca_pem"):
                        LOGGER.info("Root CA: %s", _solo.get("root_ca", ""))
                        LOGGER.info("Root CA PEM (save to a .pem file if needed):\n%s", _solo["root_ca_pem"])
                if len(_ok_tls_results) > 1:
                    _ref_ip, _ref = next(iter(_ok_tls_results.items()))
                    _mismatches = [
                        f"  {_ip}: version={_info['version']} cipher={_info['cipher']} "
                        f"(expected version={_ref['version']} cipher={_ref['cipher']})"
                        for _ip, _info in _ok_tls_results.items()
                        if _info != _ref
                    ]
                    if _mismatches:
                        LOGGER.warning(
                            "TLS configuration MISMATCH across cluster nodes "
                            "(reference node %s: version=%s cipher=%s):\n%s",
                            _ref_ip, _ref["version"], _ref["cipher"],
                            "\n".join(_mismatches),
                        )
                    else:
                        LOGGER.info(
                            "TLS configuration consistent across all %d cluster nodes "
                            "(version=%s cipher=%s).",
                            len(_ok_tls_results), _ref["version"], _ref["cipher"],
                        )

                    # Compare root CA issuers across nodes
                    _ca_map: Dict[str, str] = {_ip: _info["root_ca"] for _ip, _info in _ok_tls_results.items() if _info.get("root_ca")}
                    _unique_cas = set(_ca_map.values())
                    if len(_unique_cas) > 1:
                        LOGGER.warning(
                            "Root CA MISMATCH across cluster nodes — nodes present certificates "
                            "from different CAs. This may cause intermittent SSL verification failures "
                            "depending on which node a client connects to:\n%s",
                            "\n".join(f"  {_ip}: {_ca}" for _ip, _ca in _ca_map.items()),
                        )
                        # Print one PEM block per distinct CA so the operator can identify them
                        _seen_pems: set = set()
                        for _ip, _info in _ok_tls_results.items():
                            _pem = _info.get("root_ca_pem", "")
                            if _pem and _pem not in _seen_pems:
                                _seen_pems.add(_pem)
                                LOGGER.warning(
                                    "Root CA PEM for %s (%s):\n%s",
                                    _info.get("root_ca", "(unknown)"), _ip, _pem,
                                )
                    elif _unique_cas:
                        _ca_issuer = next(iter(_unique_cas))
                        _ca_pem = next((i.get("root_ca_pem", "") for i in _ok_tls_results.values() if i.get("root_ca_pem")), "")
                        LOGGER.info("Root CA consistent across all %d cluster nodes: %s", len(_ca_map), _ca_issuer)
                        if _ca_pem:
                            LOGGER.info("Root CA PEM (save to a .pem file if needed):\n%s", _ca_pem)

                # Block migration if any cluster node is unreachable
                _failed_nodes = [_ip for _ip, _info in _node_tls_results.items() if _info.get("status", "").startswith("FAILED")]
                if _failed_nodes:
                    _print_tls_overview(_all_tls_results)
                    LOGGER.error(
                        "CRITICAL ERROR: cluster is unhealthy — %d node(s) could not be reached: %s. "
                        "All cluster nodes must be reachable before migration. Fix the cluster first.",
                        len(_failed_nodes), ", ".join(_failed_nodes),
                    )
                    return 1

                # Block migration if any node presents a certificate expiring in < 1 day
                for _crit_ip, _crit_info in _node_tls_results.items():
                    if _crit_info.get("cert_critical") == "1":
                        LOGGER.critical(
                            "CRITICAL ERROR: your database host %s (%s) uses a certificate that will "
                            "expire on %s which is below 1 day. As your database configuration will stop "
                            "working in %s we do NOT migrate. You need to fix your database certificates first.",
                            host, _crit_ip,
                            _crit_info.get("cert_expiry", "(unknown)"),
                            _crit_info.get("cert_ttl", "(unknown)"),
                        )
                        return 1
                LOGGER.info("Encrypted connection to target database established successfully.")
            else:
                _lower_uri = (target_uri or "").lower()
                if _lower_uri.startswith("sqlite"):
                    LOGGER.info("Target is SQLite; SSL/TLS is not applicable.")
                else:
                    LOGGER.warning(
                        "SSL is not enabled in the target URI. The migration will transfer data over an "
                        "unencrypted connection. It is strongly recommended to enable SSL, e.g.: "
                        "DB_MIGRATION_TARGET_URI=mysql+pymysql://user:pass@host/db?ssl=true&ssl_ca=/path/to/ca.pem"
                    )
                # Test that an unencrypted connection actually works.
                try:
                    if _lower_uri.startswith("sqlite"):
                        # SQLite is local (no SSL/TLS). Just verify we can open it.
                        _test_engine = _create_engine(target_uri, engine_kwargs=engine_kwargs)
                        with _test_engine.connect() as _conn:
                            _conn.execute(text("SELECT 1"))
                    else:
                        _starttls = "postgres" if ("postgresql" in _lower_uri or "psycopg" in _lower_uri) else "mysql"
                        if _starttls == "postgres":
                            # Use a fast connect timeout for this best-effort verification step.
                            _test_engine_kwargs = dict(engine_kwargs or {})
                            _ca = dict(_test_engine_kwargs.get("connect_args") or {})  # type: ignore[arg-type]
                            _ca["connect_timeout"] = 5
                            _test_engine_kwargs["connect_args"] = _ca
                            _test_engine = _create_engine(target_uri, engine_kwargs=_test_engine_kwargs)
                            with _test_engine.connect() as _conn:
                                _conn.execute(text("SELECT 1"))
                        else:
                            import pymysql as _pymysql
                            from sqlalchemy.engine.url import make_url as _make_url

                            _url = _make_url(target_uri)
                            _conn = _pymysql.connect(
                                host=_url.host or "",
                                port=int(_url.port or 3306),
                                user=_url.username or "",
                                password=_url.password or "",
                                database=_url.database or None,
                                ssl=None,
                                connect_timeout=5,
                            )
                            _conn.close()
                        LOGGER.info("Unencrypted connection to target database established successfully.")
                except Exception as _exc:
                    LOGGER.error("Unencrypted connection to target database failed: %s", _exc)
                    return 1
                # Best-effort SSL probe to detect whether the server supports SSL at all.
                _server_supports_ssl = False
                _server_ca_pem: Optional[str] = None
                # Only run the MySQL SSL probe when the target is actually a MySQL/MariaDB
                # target using the PyMySQL driver. Otherwise, the probe function may no-op
                # and we would incorrectly treat it as “supports SSL”.
                if not _lower_uri.startswith("sqlite"):
                    try:
                        from sqlalchemy.engine.url import make_url as _mu

                        _drivername = (_mu(target_uri).drivername or "").lower()
                    except Exception:
                        _drivername = ""

                    if "mysql+pymysql" in _drivername or "mariadb+pymysql" in _drivername:
                        try:
                            _verify_mysql_ssl_and_log_details(target_uri, ssl_required=False)
                            _server_supports_ssl = True
                            LOGGER.info(
                                "Target appears to support SSL/TLS; server certificate verified successfully "
                                "even though SSL is not enabled in the URI."
                            )
                        except Exception as exc:
                            # Check if failure was cert-related (server supports SSL but CA unknown)
                            _exc_str = str(exc)
                            if "certificate" in _exc_str.lower() or "ssl" in _exc_str.lower():
                                _server_supports_ssl = True
                                # Try to extract the PEM from diagnostics that were already logged
                                try:
                                    import pymysql as _pymysql2
                                    from sqlalchemy.engine.url import make_url as _mu2
                                    _u2 = _mu2(target_uri)
                                    _diag_conn = _pymysql2.connect(
                                        host=_u2.host or "",
                                        port=int(_u2.port or 3306),
                                        user=_u2.username or "",
                                        password=_u2.password or "",
                                        database=_u2.database or None,
                                        ssl={"cert_reqs": ssl.CERT_NONE, "check_hostname": False},
                                        connect_timeout=5,
                                    )
                                    _sock2 = getattr(_diag_conn, "_sock", None)
                                    if _sock2 and hasattr(_sock2, "getpeercert"):
                                        _der = _sock2.getpeercert(True)
                                        if _der:
                                            import base64 as _b64
                                            _pem = "-----BEGIN CERTIFICATE-----\n" + _b64.encodebytes(_der).decode() + "-----END CERTIFICATE-----"
                                            _server_ca_pem = _pem.strip()
                                            _cert_is_ca = False
                                            try:
                                                from cryptography import x509 as _x509
                                                from cryptography.hazmat.backends import default_backend as _db
                                                from cryptography.x509.oid import ExtensionOID as _EOID
                                                _cert_obj = _x509.load_der_x509_certificate(_der, _db())
                                                try:
                                                    _bc = _cert_obj.extensions.get_extension_for_oid(_EOID.BASIC_CONSTRAINTS)
                                                    _cert_is_ca = _bc.value.ca
                                                except Exception:
                                                    _cert_is_ca = False
                                                _self_signed = _cert_obj.subject == _cert_obj.issuer
                                                if not _cert_is_ca and _self_signed:
                                                    _cert_is_ca = True
                                            except Exception:
                                                _cert_is_ca = False
                                            if not _cert_is_ca:
                                                _server_ca_pem = ("__leaf__", _server_ca_pem)  # type: ignore[assignment]
                                    _diag_conn.close()
                                except Exception:
                                    pass
                            LOGGER.info(
                                "Best-effort SSL probe on target failed or is unsupported (SSL disabled in URI): %s",
                                exc,
                            )
            # Verify the target is writable (i.e. a primary, not a standby replica).
            # PostgreSQL standbys allow SELECT but reject all DDL with ReadOnlySqlTransaction.
            # When multiple IPs resolve for the host (HA cluster), probe each node to find
            # the primary and switch the engine/URI to it automatically.
            if "postgresql" in target_uri.lower() or "psycopg" in target_uri.lower():
                with target_engine.connect() as _wconn:
                    is_replica = _wconn.execute(text("SELECT pg_is_in_recovery()")).scalar()
                    if is_replica:
                        LOGGER.warning(
                            "Target PostgreSQL server is a standby replica (pg_is_in_recovery() = true). "
                            "Multiple IPs resolved for the host — probing each node to find the primary."
                        )
                        from sqlalchemy.engine.url import make_url as _mu

                        _url = _mu(target_uri)
                        _primary_engine = None
                        _primary_uri = None
                        for _ip in ips:
                            try:
                                # Keep hostname in URI for SSL SNI and pg_hba.conf matching;
                                # use hostaddr in connect_args to force connection to this specific IP.
                                _node_kwargs = dict(engine_kwargs or {"future": True, "pool_pre_ping": True, "pool_recycle": 1800})
                                _node_ca = dict(_node_kwargs.get("connect_args") or {})
                                _node_ca["hostaddr"] = _ip
                                _node_ca["connect_timeout"] = 2
                                _node_kwargs["connect_args"] = _node_ca
                                _node_engine = _create_engine(target_uri, engine_kwargs=_node_kwargs)
                                with _node_engine.connect() as _nc:
                                    _node_replica = _nc.execute(text("SELECT pg_is_in_recovery()")).scalar()
                                if not _node_replica:
                                    LOGGER.info("Found primary node at %s — switching target to this node.", _ip)
                                    _primary_engine = _node_engine
                                    _primary_uri = target_uri
                                    break
                                else:
                                    LOGGER.info("Node %s is a replica, skipping.", _ip)
                            except Exception as _probe_exc:
                                LOGGER.warning("Could not probe node %s: %s", _ip, _probe_exc)
                        if _primary_engine is None:
                            LOGGER.error(
                                "Could not find a writable primary among resolved nodes (%s). "
                                "Connect directly to the primary port (e.g. HAProxy port 5000 for Patroni) "
                                "or add ?target_session_attrs=read-write to the URI.",
                                ", ".join(ips),
                            )
                            return 1
                        target_engine = _primary_engine
                        target_uri = _primary_uri
                        # Persist hostaddr so schema creation and data import also hit the primary
                        engine_kwargs = dict(engine_kwargs or {"future": True, "pool_pre_ping": True, "pool_recycle": 1800})
                        _ca = dict(engine_kwargs.get("connect_args") or {})
                        _ca["hostaddr"] = _node_ca["hostaddr"]
                        engine_kwargs["connect_args"] = _ca

            # Ensure target is empty from BunkerWeb's perspective
            try:
                _ensure_target_empty(target_engine)
            except RuntimeError:
                return 1

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
            _check_source_size(source_engine, source_uri, _DUMP_ROOT)
            _emit_ssl_advisories(ssl_expected, _server_supports_ssl if not ssl_expected else None, _server_ca_pem if not ssl_expected else None)
            return 0

        if args.test_target:
            _print_tls_overview(_all_tls_results)
            _check_source_size(source_engine, source_uri, _DUMP_ROOT)
            LOGGER.info("Target database connectivity OK and target appears empty for BunkerWeb tables.")
            LOGGER.info("SUCCESS: target database test passed — ready for migration.")
            _emit_ssl_advisories(ssl_expected, _server_supports_ssl if not ssl_expected else None, _server_ca_pem if not ssl_expected else None)
            return 0

        _mig_start = datetime.now()
        _pid_write("migration-start")
        LOGGER.info("Starting database backend migration (no schema change, backend move only) ...")

        # 3. Create schema on target for current BunkerWeb version
        assert target_engine is not None, "Target engine must be initialized for real migration"
        _pid_write("schema-creation")
        LOGGER.info("Running Alembic schema upgrade...")
        try:
            _run_alembic_upgrade(target_uri, engine_kwargs=engine_kwargs)
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
        _check_source_size(source_engine, source_uri, _DUMP_ROOT)

        # 3b. Durable intermediate dump under /tmp/bunkerweb/bw_db_migrate:
        # source -> files -> target
        dump_timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dump_dir = _DUMP_ROOT / f"dump-{dump_timestamp}"
        LOGGER.info("Using intermediate dump directory at %s", dump_dir)

        # 4. Phase 1: dump from source into neutral files
        _pid_write("dump-source")
        LOGGER.info("Phase 1/2: dumping data from source database to intermediate dump files.")
        effective_source_uri = source_uri
        if source_uri.startswith("sqlite:"):
            effective_source_uri = _sqlite_snapshot_if_wal(source_uri, dump_dir)
        effective_source_engine = source_engine if effective_source_uri == source_uri else _create_engine(effective_source_uri, engine_kwargs=engine_kwargs)
        _dump_source_to_files(effective_source_engine, dump_dir)

        # 4b. Phase 2: import from files into target
        _pid_write("import-target")
        LOGGER.info("Phase 2/2: importing data from intermediate dump files into target database.")
        _import_skipped = _import_files_to_target(dump_dir, target_engine)

        # 5. Verify per-table row counts between source and target
        _verify_all_data(effective_source_engine, target_engine, skipped_orphans=_import_skipped)

        # If the target is SQLite, ensure permissions are correct so the runtime can open it.
        # This avoids scheduler retry loops when bw_db_migrate runs as root.
        if target_uri.lower().startswith("sqlite"):
            _fix_sqlite_permissions(target_uri)

        env_updated = False
        if args.tui and update_env_file and not args.test_target and not args.dry_run:
            _update_env_file_on_success(Path(args.env_file), target_uri)
            env_updated = True

        auto_switch_failed = False
        if args.auto_switch and not args.test_target and not args.dry_run:
            # Ensure the runtime config points to the migrated backend.
            if not env_updated:
                try:
                    _update_env_file_on_success(Path(args.env_file), target_uri)
                    env_updated = True
                except Exception as exc:
                    LOGGER.error("AUTO-SWITCH: failed to update %s: %s", args.env_file, exc)
                    auto_switch_failed = True

            # Restart bunkerweb services so they reload DATABASE_URI.
            if env_updated and not auto_switch_failed:
                try:
                    import subprocess as _subprocess
                    import shutil as _shutil
                    from pathlib import Path as _Path

                    service_units = ["bunkerweb", "bunkerweb-scheduler", "bunkerweb-ui"]

                    # Prefer systemd if present.
                    if _shutil.which("systemctl") and _Path("/run/systemd/system").exists():
                        # Restart only units that exist (avoid failing if a unit is absent).
                        existing_units: list[str] = []
                        for unit in service_units:
                            unit_name = f"{unit}.service"
                            _res = _subprocess.run(
                                ["systemctl", "show", "-p", "Id", unit_name],
                                stdout=_subprocess.PIPE,
                                stderr=_subprocess.DEVNULL,
                                text=True,
                            )
                            if _res.returncode == 0:
                                existing_units.append(unit_name)

                        if not existing_units:
                            LOGGER.error("AUTO-SWITCH: no matching systemd units found to restart.")
                            auto_switch_failed = True
                        else:
                            _res = _subprocess.run(
                                ["systemctl", "try-restart", *existing_units],
                                check=False,
                                stdout=_subprocess.PIPE,
                                stderr=_subprocess.STDOUT,
                                text=True,
                            )
                            if _res.returncode != 0:
                                LOGGER.error(
                                    "AUTO-SWITCH: systemctl try-restart failed (rc=%s). Output:\n%s",
                                    _res.returncode,
                                    (_res.stdout or "").strip(),
                                )
                                auto_switch_failed = True
                            else:
                                LOGGER.info("AUTO-SWITCH: restarted bunkerweb services successfully (systemd).")
                    else:
                        # Fallback for non-systemd init systems.
                        restarted_any = False
                        init_dir = _Path("/etc/init.d")
                        for unit in service_units:
                            init_script = init_dir / unit
                            if init_script.exists() and init_script.is_file():
                                _res = _subprocess.run(
                                    [str(init_script), "restart"],
                                    check=False,
                                    stdout=_subprocess.PIPE,
                                    stderr=_subprocess.STDOUT,
                                    text=True,
                                )
                                if _res.returncode == 0:
                                    restarted_any = True

                        # If no init.d scripts existed, try `service <name> restart` (SysV wrapper).
                        if not restarted_any and _shutil.which("service"):
                            for unit in service_units:
                                _res = _subprocess.run(
                                    ["service", unit, "restart"],
                                    check=False,
                                    stdout=_subprocess.PIPE,
                                    stderr=_subprocess.STDOUT,
                                    text=True,
                                )
                                if _res.returncode == 0:
                                    restarted_any = True

                        if not restarted_any:
                            LOGGER.error(
                                "AUTO-SWITCH: unable to restart bunkerweb services (no systemd units and no init scripts found)."
                            )
                            auto_switch_failed = True
                        else:
                            LOGGER.info("AUTO-SWITCH: restarted bunkerweb services successfully (non-systemd).")
                except Exception as exc:
                    LOGGER.error("AUTO-SWITCH: failed to restart services: %s", exc)
                    auto_switch_failed = True

        # Clean up only the per-run dump subdirectory on successful completion.
        # The parent _DUMP_ROOT directory is kept so the debug log file is preserved.
        try:
            if dump_dir.exists():
                shutil.rmtree(dump_dir)
                LOGGER.info("Cleaned up intermediate dump directory %s.", dump_dir)
                if _log_file:
                    LOGGER.info("Debug log retained at: %s", _log_file)
        except Exception as exc:
            LOGGER.warning("Unable to clean up dump directory %s: %s", dump_dir, exc)

        _print_tls_overview(_all_tls_results)
        _pid_write("complete")
        _mig_end = datetime.now()
        _mig_elapsed = (_mig_end - _mig_start).total_seconds() if "_mig_start" in dir() else None
        LOGGER.info("=" * 60)
        LOGGER.info("MIGRATION SUMMARY")
        LOGGER.info("=" * 60)
        LOGGER.info("  Source  : %s", _mask_uri_password(source_uri))
        LOGGER.info("  Target  : %s", _mask_uri_password(target_uri))
        LOGGER.info("  Finished: %s", _mig_end.strftime("%Y-%m-%d %H:%M:%S"))
        if _mig_elapsed is not None:
            _h, _rem = divmod(int(_mig_elapsed), 3600)
            _m, _s = divmod(_rem, 60)
            LOGGER.info("  Duration: %02d:%02d:%02d", _h, _m, _s)
        LOGGER.info("  Result  : SUCCESS")
        LOGGER.info("=" * 60)
        LOGGER.info("Database backend migration completed successfully.")
        LOGGER.info("You can now point BunkerWeb's DATABASE_URI to the target URI.")
        LOGGER.info("=" * 60)
        if args.auto_switch and not auto_switch_failed:
            LOGGER.info("AUTO-SWITCH: DATABASE_URI updated and bunkerweb services restarted successfully.")
            LOGGER.info("  Recommended : no reboot required (services should reload DATABASE_URI).")
        else:
            LOGGER.info("ACTION REQUIRED: reboot this manager to apply the new database backend.")
            LOGGER.info("  Recommended : sudo reboot")
            LOGGER.info("  Alternative : sudo systemctl restart bunkerweb bunkerweb-scheduler bunkerweb-ui")
        LOGGER.info("=" * 60)
        _emit_ssl_advisories(ssl_expected, _server_supports_ssl if not ssl_expected else None, _server_ca_pem if not ssl_expected else None)
        _pid_remove()
        if auto_switch_failed:
            LOGGER.error("AUTO-SWITCH: migration succeeded, but auto-switch (env update and/or restart) failed.")
            return 1
        return 0
    except KeyboardInterrupt:
        _pid_write("aborted")
        LOGGER.error("Database backend migration ABORTED (KeyboardInterrupt).")
        return 130
    except SystemExit as exc:
        # Some external libraries may raise SystemExit (e.g. via sys.exit()).
        # Treat it as a failure unless the exit code is explicitly 0.
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            LOGGER.warning("Database backend migration triggered SystemExit(0) unexpectedly; treating as success.")
            _pid_remove()
            return 0
        _pid_write("failed")
        LOGGER.exception("Database backend migration FAILED due to SystemExit(%s).", code)
        return code or 1
    except SQLAlchemyError as exc:
        _pid_write("failed")
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
        _pid_write("failed")
        LOGGER.exception("Unexpected error during DB migration.")
        LOGGER.error("Database backend migration FAILED due to an unexpected error.")
        return 1


def main() -> int:
    import logging as _logging
    from datetime import datetime as _datetime

    _last_errors: list = []

    class _LastErrorHandler(_logging.Handler):
        def emit(self, record: _logging.LogRecord) -> None:
            if record.levelno >= _logging.ERROR:
                _last_errors.append(self.format(record))

    _err_handler = _LastErrorHandler()
    _err_handler.setFormatter(_logging.Formatter("%(message)s"))
    LOGGER.addHandler(_err_handler)

    rc = _main()

    LOGGER.removeHandler(_err_handler)

    _ts = _datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    LOGGER.info("=" * 60)
    if rc == 0:
        if _last_errors:
            for _e in _last_errors:
                LOGGER.error("Error during run: %s", _e)
        LOGGER.info("Finished: %s — SUCCESS", _ts)
    elif rc == 130:
        LOGGER.error("Finished: %s — ABORTED (KeyboardInterrupt)", _ts)
    else:
        if _last_errors:
            LOGGER.error("Last error: %s", _last_errors[-1])
        LOGGER.error("Finished: %s — FAILED (exit code %d)", _ts, rc)
    LOGGER.info("=" * 60)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

