#!/usr/bin/env python3

from os.path import sep
from pathlib import Path
from typing import Optional

from bcrypt import checkpw, gensalt, hashpw
from regex import compile as re_compile

from app.models.api_database import APIDatabase
from logger import getLogger  # type: ignore

from Database import Database  # type: ignore

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")

LOGGER = getLogger("API")

# Cached singletons for pooled DB engines
_DB_INSTANCE: Optional[Database] = None  # type: ignore
_API_DB_INSTANCE = None  # Late-bound type to avoid import cycles


def get_db(*, log: bool = True) -> Database:
    """Return a shared pooled Database instance.

    Creates it on first use; reuses the same engine/session factory afterwards.
    """
    global _DB_INSTANCE
    if _DB_INSTANCE is None or getattr(_DB_INSTANCE, "sql_engine", None) is None:  # type: ignore[attr-defined]
        from Database import Database  # type: ignore

        _DB_INSTANCE = Database(LOGGER, log=log)  # type: ignore
    return _DB_INSTANCE  # type: ignore


def get_api_db(*, log: bool = True) -> APIDatabase:
    """Return a shared pooled APIDatabase instance for API models."""
    global _API_DB_INSTANCE
    if _API_DB_INSTANCE is None or getattr(_API_DB_INSTANCE, "sql_engine", None) is None:  # type: ignore[attr-defined]
        from .models.api_database import APIDatabase

        _API_DB_INSTANCE = APIDatabase(LOGGER, log=log)
    return _API_DB_INSTANCE


USER_PASSWORD_RX = re_compile(r"^(?=.*\p{Ll})(?=.*\p{Lu})(?=.*\d)(?=.*\P{Alnum}).{8,}$")
BCRYPT_HASH_RX = re_compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z")
RECOMMENDED_BCRYPT_COST = 12  # below this, a supplied pre-hashed credential triggers a warning
MIN_BCRYPT_COST = 10  # absolute floor; a supplied pre-hashed credential below this is refused
MAX_PASSWORD_BYTES = 72  # bcrypt only consumes the first 72 bytes of a secret; 5.x raises ValueError on more
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")

BISCUIT_PUBLIC_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_public_key")
BISCUIT_PRIVATE_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_private_key")


def _bcrypt_secret(password: str) -> bytes:
    # bcrypt only ever consumes the first 72 bytes of a secret. bcrypt 4.x truncated
    # longer input silently; bcrypt 5.x raises ValueError instead. Truncate explicitly
    # so behaviour (and every already-stored hash) stays identical across both versions.
    # Set-time flows reject >72 bytes up front (see password_exceeds_bcrypt_limit); this
    # truncation only matters for verifying legacy hashes created before that cap existed.
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]


def password_exceeds_bcrypt_limit(password: str) -> bool:
    """True if the password is longer than bcrypt's MAX_PASSWORD_BYTES-byte limit.

    bcrypt 5.x raises a ValueError past 72 bytes (4.x silently truncated). Password
    set/change flows reject overly long input with this check so nothing is silently
    truncated going forward; verification still truncates so pre-cap hashes keep working.
    """
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def gen_password_hash(password: str) -> bytes:
    return hashpw(_bcrypt_secret(password), gensalt(rounds=13))


def is_bcrypt_hash(value: str) -> bool:
    """True if value is a well-formed bcrypt hash this build's bcrypt lib can verify."""
    if not BCRYPT_HASH_RX.match(value):
        return False
    try:
        checkpw(b"bunkerweb-bcrypt-probe", value.encode("utf-8"))
    except (ValueError, TypeError):
        return False  # prefix/format the installed bcrypt lib cannot parse -> treat as plaintext
    return True


def bcrypt_cost(value: str) -> int:
    """Cost factor of a bcrypt hash. Caller must ensure value passed is_bcrypt_hash() first."""
    return int(value[4:6])


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(_bcrypt_secret(password), hashed)
