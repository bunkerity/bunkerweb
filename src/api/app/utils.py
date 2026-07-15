#!/usr/bin/env python3

from os.path import sep
from pathlib import Path
from typing import Optional

from regex import compile as re_compile

from app.models.api_database import APIDatabase
from logger import getLogger  # type: ignore
from password_utils import (  # type: ignore  # noqa: F401
    BCRYPT_HASH_RX as BCRYPT_HASH_RX,
    MAX_PASSWORD_BYTES as MAX_PASSWORD_BYTES,
    MIN_BCRYPT_COST as MIN_BCRYPT_COST,
    RECOMMENDED_BCRYPT_COST as RECOMMENDED_BCRYPT_COST,
    USER_PASSWORD_RX as USER_PASSWORD_RX,
    _bcrypt_secret as _bcrypt_secret,
    bcrypt_cost as bcrypt_cost,
    check_password as check_password,
    gen_password_hash as gen_password_hash,
    is_bcrypt_hash as is_bcrypt_hash,
    password_exceeds_bcrypt_limit as password_exceeds_bcrypt_limit,
)

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


PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")

BISCUIT_PUBLIC_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_public_key")
BISCUIT_PRIVATE_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_private_key")
