"""Throttle failed logins per client IP and per username (ported from dev 1.6.18~rc3, `bda10b007`).

Dev held a database handle; the 1.7 UI never touches the database, so every function here takes the
``API_CLIENT`` and talks to the three ``/users/login-throttle/*`` endpoints. The policy (``LOGIN_*``
settings) is read from the UI's own environment and sent along with each check.

Two rules differ from dev on purpose, both because the 1.7 UI depends on an API that can be down:

* the *check* fails closed. A throttle that cannot answer refuses the attempt (503, before the
  password is looked at) instead of letting it through: an attacker who can make the endpoint fail
  would otherwise switch the protection off. ``LOGIN_THROTTLE=no`` is the documented way back in.
* *recording* and *clearing* still only warn: the attempt they follow is already decided.
"""

from functools import lru_cache
from os import getenv
from typing import NamedTuple, Optional, Tuple

from app.api_client import ApiClientError, ApiUnavailableError
from app.i18n import translated
from app.utils import LOGGER

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_MINUTES = 15
DEFAULT_LOCKOUT_MINUTES = 15

# What the API accepts (`users.py`): a longer value is cut here, the same way the database cuts it.
_MAX_USERNAME = 1024
_MAX_IP = 45


class Refusal(NamedTuple):
    """Why an attempt is refused before it is looked at: a lock (429) or an unreachable throttle (503)."""

    message: str
    status: int


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


def _keys(username: str, ip: Optional[str]) -> Tuple[str, str]:
    return username[:_MAX_USERNAME], (ip or "")[:_MAX_IP]


def refusal(client, username: str, ip: Optional[str]) -> Optional[Refusal]:
    """``None`` when the attempt may go on, else the refusal to show *instead of* checking the password.

    The answer depends on the username only through the lock, and a lock exists for an unknown username
    as much as for a known one, so it never tells whether an account exists.
    """
    config = settings()
    if not config:
        return None
    max_attempts, window, lockout = config
    username, ip = _keys(username, ip)
    try:
        remaining = client.check_login_throttle(username, ip, max_attempts=max_attempts, window=window, lockout=lockout)
    except Exception as e:
        reason = e.message if isinstance(e, (ApiClientError, ApiUnavailableError)) else type(e).__name__
        LOGGER.error(f"Couldn't check the login throttle, refusing the attempt: {reason}")
        return Refusal(translated("login.flash.throttle_unavailable") or "Sign-in is temporarily unavailable, please try again shortly.", 503)
    if not remaining:
        return None
    minutes = -(-remaining // 60)
    LOGGER.warning(f"Login locked for {username.strip().casefold()!r} from {ip}, {remaining}s left")
    return Refusal(translated("login.flash.too_many_failed_attempts", minutes=minutes) or f"Too many failed attempts, try again in {minutes} min.", 429)


def record_failure(client, username: str, ip: Optional[str]) -> None:
    config = settings()
    if not config:
        return
    _, window, lockout = config
    username, ip = _keys(username, ip)
    try:
        client.record_login_failure(username, ip, retention=window + lockout)
    except Exception as e:
        reason = e.message if isinstance(e, (ApiClientError, ApiUnavailableError)) else type(e).__name__
        LOGGER.warning(f"Couldn't record the failed login, the throttle is not counting it: {reason}")


def reset(client, username: str) -> None:
    """Forget the failures of a username after a complete login."""
    if not settings():
        return
    try:
        client.clear_login_failures(username[:_MAX_USERNAME])
    except Exception as e:
        reason = e.message if isinstance(e, (ApiClientError, ApiUnavailableError)) else type(e).__name__
        LOGGER.warning(f"Couldn't clear the failed logins of the user: {reason}")
