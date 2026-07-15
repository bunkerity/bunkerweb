"""Shared bcrypt password validation and hashing helpers."""

from bcrypt import checkpw, gensalt, hashpw
from regex import compile as re_compile

USER_PASSWORD_RX = re_compile(r"^(?=.*\p{Ll})(?=.*\p{Lu})(?=.*\d)(?=.*\P{Alnum}).{8,}$")
BCRYPT_HASH_RX = re_compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}\Z")
RECOMMENDED_BCRYPT_COST = 12
MIN_BCRYPT_COST = 10
MAX_PASSWORD_BYTES = 72


def _bcrypt_secret(password: str) -> bytes:
    """Return the bytes bcrypt consumes, including its 72-byte limit."""
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]


def password_exceeds_bcrypt_limit(password: str) -> bool:
    """Return whether ``password`` exceeds bcrypt's byte limit."""
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def gen_password_hash(password: str) -> bytes:
    return hashpw(_bcrypt_secret(password), gensalt(rounds=13))


def is_bcrypt_hash(value: str) -> bool:
    """Return whether ``value`` is a bcrypt hash supported by this build."""
    if not BCRYPT_HASH_RX.match(value):
        return False
    try:
        checkpw(b"bunkerweb-bcrypt-probe", value.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    return True


def bcrypt_cost(value: str) -> int:
    """Return a validated bcrypt hash's cost factor."""
    return int(value[4:6])


def check_password(password: str, hashed: bytes) -> bool:
    return checkpw(_bcrypt_secret(password), hashed)
