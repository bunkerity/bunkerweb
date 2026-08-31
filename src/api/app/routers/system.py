from os import getenv
from typing import List, Optional, Union

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..auth.guard import guard
from ..utils import LOGGER, get_db

router = APIRouter(prefix="/system", tags=["system"])

# The key `bwcli plugin backup quiesce` sets while a controlled downgrade is being prepared.
# Duplicated from src/common/core/backup/downgrade.py rather than imported: the core plugins
# are not on this image's import path. tests/unit/backup/test_downgrade_hold.py asserts the two
# literals are still equal, because two constants that drift apart would not error anywhere --
# the CLI would set a key nobody reads and the hold would be silently inert.
DOWNGRADE_HOLD_KEY = "bw:downgrade_hold"

# Memoized like `app/celery_app.py` does, and for the same reason: this endpoint is polled by the
# scheduler, the autoconf and every UI worker, so building a client per request meant a new
# ConnectionPool and a fresh TCP connect on each poll. No lock -- two threads racing here at worst
# build one client twice and keep the second, and redis-py clients are thread-safe.
_hold_client = None
_hold_client_url = ""
# Last known broker health, so an outage logs once per transition instead of once per poll. During
# a Valkey outage -- the scenario fail-open exists for -- the per-request version produced one
# ERROR line per poll per process, forever.
_hold_broker_readable = True


def downgrade_hold_active() -> bool:
    """Whether a controlled downgrade is holding the writers still.

    FAILS OPEN, deliberately. A broker blip must not freeze every write fleet-wide: that would read
    as a permanent read-only outage with no operator action that clears it. The safety for a
    downgrade lives on the other side instead -- the CLI verifies through this endpoint that its
    hold is actually observable and refuses to proceed when it is not -- so an unreadable broker
    costs a refused downgrade, never a frozen fleet.

    No default broker URL here, matching `app/celery_app.py`: an API with no broker configured has
    no Celery either. The Linux unit exports one (`src/linux/scripts/bunkerweb-api.sh:241`), so the
    packages are covered.
    """
    global _hold_client, _hold_client_url, _hold_broker_readable

    broker_url = getenv("CELERY_BROKER_URL", "").strip()
    if not broker_url:
        return False

    try:
        if _hold_client is None or _hold_client_url != broker_url:
            import redis

            # Never `from_url` bare: a black-holed broker with redis-py's default absence of a
            # socket timeout would hang this request handler instead of failing it.
            _hold_client = redis.Redis.from_url(broker_url, socket_timeout=2, socket_connect_timeout=2)
            _hold_client_url = broker_url

        held = bool(_hold_client.exists(DOWNGRADE_HOLD_KEY))
        if not _hold_broker_readable:
            LOGGER.info("The broker is readable again, the downgrade hold is being honoured once more")
            _hold_broker_readable = True
        return held
    except BaseException as e:
        # Drop the client so the next call rebuilds it rather than reusing a poisoned pool.
        _hold_client = None
        _hold_client_url = ""
        if _hold_broker_readable:
            from Database import scrub_db_secret  # type: ignore

            # The broker URL carries credentials and clients echo it back inside their errors.
            LOGGER.error(
                "Could not read the downgrade hold from the broker, answering with the boot-time read-only state alone "
                f"(logged once until it recovers): {scrub_db_secret(str(e), broker_url)}"
            )
            _hold_broker_readable = False
        return False


@router.get("/readonly", dependencies=[Depends(guard)])
def check_readonly() -> JSONResponse:
    """Check if the database is in read-only mode.

    Two orthogonal reasons to be read-only: the boot-time one (DATABASE_URI_READONLY, unchanged
    in meaning and in when it is read) and a downgrade hold, which is additive and reverses as
    soon as the hold is released or expires.
    """
    db = get_db()
    return JSONResponse(status_code=200, content={"status": "success", "readonly": db.readonly or downgrade_hold_active()})


class CheckedChangesRequest(BaseModel):
    changes: Optional[List[str]] = None
    plugins_changes: Optional[Union[str, List[str]]] = None
    value: bool = False


@router.post("/checked-changes", dependencies=[Depends(guard)])
def checked_changes(payload: CheckedChangesRequest) -> JSONResponse:
    """Mark changes in the database.

    Args:
        payload.changes: List of change keys (e.g. ["config", "custom_configs", "ui_plugins"])
        payload.plugins_changes: Plugin IDs to mark, or "all" for all plugins
        payload.value: True to mark as changed, False to mark as checked (default: False)
    """
    db = get_db()
    if ret := db.checked_changes(payload.changes, plugins_changes=payload.plugins_changes, value=payload.value):
        return JSONResponse(status_code=500, content={"status": "error", "message": str(ret)})
    return JSONResponse(status_code=200, content={"status": "success"})
