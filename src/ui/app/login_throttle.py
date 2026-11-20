from functools import lru_cache
from os import getenv
from typing import Optional, Tuple

from app.utils import LOGGER

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_MINUTES = 15
DEFAULT_LOCKOUT_MINUTES = 15


@lru_cache(maxsize=8)
def _parse(enabled: str, max_attempts: str, window: str, lockout: str) -> Optional[Tuple[int, int, int]]:
    if enabled.strip().lower() == "no":
        return None

    values = []
    for name, raw, default in (
        ("LOGIN_MAX_ATTEMPTS", max_attempts, DEFAULT_MAX_ATTEMPTS),
        ("LOGIN_WINDOW_MINUTES", window, DEFAULT_WINDOW_MINUTES),
        ("LOGIN_LOCKOUT_MINUTES", lockout, DEFAULT_LOCKOUT_MINUTES),
    ):
        try:
            value = int(raw)
            if value < 1:
                raise ValueError
        except ValueError:
            LOGGER.warning(f"Invalid {name} ({raw!r}), defaulting to {default}")
            value = default
        values.append(value)
    return values[0], values[1] * 60, values[2] * 60


def settings() -> Optional[Tuple[int, int, int]]:
    """``(max attempts, window seconds, lockout seconds)``, or ``None`` when ``LOGIN_THROTTLE=no``."""
    return _parse(
        getenv("LOGIN_THROTTLE", "yes"),
        getenv("LOGIN_MAX_ATTEMPTS", str(DEFAULT_MAX_ATTEMPTS)),
        getenv("LOGIN_WINDOW_MINUTES", str(DEFAULT_WINDOW_MINUTES)),
        getenv("LOGIN_LOCKOUT_MINUTES", str(DEFAULT_LOCKOUT_MINUTES)),
    )


def _key(username: str) -> str:
    # Case and trailing blanks are folded because MariaDB/MySQL collations match the account that way
    return username.strip().casefold()[:256]


def locked_message(db, username: str, ip: Optional[str]) -> str:
    """The message to show when this username or IP is locked, ``""`` when the attempt may go on.

    The throttle never gets in the way of a login it cannot track: a database error is logged and lets the attempt through.
    """
    config = settings()
    if not config:
        return ""
    max_attempts, window, lockout = config
    try:
        remaining = db.get_ui_login_lock(_key(username), (ip or "")[:45], max_attempts=max_attempts, window=window, lockout=lockout)
    except Exception as e:
        LOGGER.warning(f"Couldn't check the login throttle ({type(e).__name__}), letting the attempt through")
        return ""
    if not remaining:
        return ""
    LOGGER.warning(f"Login locked for {_key(username)!r} from {ip}, {remaining}s left")
    return f"Too many failed attempts, try again in {-(-remaining // 60)} min."


def record_failure(db, username: str, ip: Optional[str]) -> None:
    config = settings()
    if not config:
        return
    _, window, lockout = config
    try:
        ret = db.add_ui_login_failure(_key(username), (ip or "")[:45], retention=window + lockout)
    except Exception as e:
        ret = type(e).__name__
    if ret:
        LOGGER.warning(f"Couldn't record the failed login, the throttle is not counting it: {ret}")


def reset(db, username: str) -> None:
    if not settings():
        return
    try:
        ret = db.clear_ui_login_failures(_key(username))
    except Exception as e:
        ret = type(e).__name__
    if ret:
        LOGGER.warning(f"Couldn't clear the failed logins of the user: {ret}")
