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
PLUGIN_NAME_RX = re_compile(r"^[\w.-]{4,64}$")

BISCUIT_PUBLIC_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_public_key")
BISCUIT_PRIVATE_KEY_FILE = LIB_DIR.joinpath(".api_biscuit_private_key")


def gen_password_hash(password: str) -> bytes:
    return hashpw(password.encode("utf-8"), gensalt(rounds=13))


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(password.encode("utf-8"), hashed)
