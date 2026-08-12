from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
import json

from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..schemas import BanRequest, UnbanRequest
from ..utils import LOGGER, get_db

router = APIRouter(prefix="/bans", tags=["bans"])

RESERVED_SERVICE_NAMES = frozenset({"unknown", "Web UI", "bwcli", "default server", ""})


def _expires_at(exp: int) -> Optional[datetime]:
    """Absolute expiry from the wire's TTL. ``exp == 0`` means permanent — the wire cannot say
    "expires in under a second" and "never expires" differently, so 0 is read as permanent
    everywhere, exactly like ``utils.add_ban`` does in Lua."""
    return None if not exp else datetime.now(timezone.utc) + timedelta(seconds=exp)


def _derive_scope(payload: dict) -> None:
    """Derive ban_scope from service presence and validate reserved service names."""
    service = (payload.get("service") or "").strip() if isinstance(payload.get("service"), str) else payload.get("service")
    if service and service not in RESERVED_SERVICE_NAMES:
        payload["ban_scope"] = "service"
    else:
        payload["ban_scope"] = "global"
        payload.pop("service", None)


@router.get("", dependencies=[Depends(guard)])
def list_bans() -> JSONResponse:
    """List all active bans, read from the database.

    The database is the source of truth: an instance that has just restarted enumerates an empty
    shared dict (and, under Redis, only re-materializes a ban when a request from that IP arrives),
    so asking the instances would under-report. Use ``GET /bans/instances`` to see what each
    instance is actually enforcing right now.
    """
    return JSONResponse(status_code=200, content={"status": "success", "data": get_db().get_bans()})


@router.get("/instances", dependencies=[Depends(guard)])
def list_instance_bans(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """List the bans each BunkerWeb instance is currently enforcing (runtime view, not durable
    state). This is the pre-1.7 shape of ``GET /bans``."""
    ok, responses = api_caller.send_to_apis("GET", "/bans", response=True)
    return JSONResponse(status_code=200 if ok else 502, content=responses or {"status": "error", "msg": "internal error"})


@router.post("/ban", dependencies=[Depends(guard)])
@router.post("", dependencies=[Depends(guard)])
def ban(req: Union[List[BanRequest], BanRequest, str], api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Ban one or multiple IP addresses across all BunkerWeb instances.

    Args:
        req: Ban request(s) containing IP, expiration, reason, and optional service
    """
    # Support body as JSON object, list, or stringified JSON
    if isinstance(req, str):
        try:
            loaded = json.loads(req)
            if isinstance(loaded, list):
                items: List[BanRequest] = [BanRequest(**it) for it in loaded]
            elif isinstance(loaded, dict):
                items = [BanRequest(**loaded)]
            else:
                return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid request body"})
        except Exception:
            return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid request body"})
    else:
        items = req if isinstance(req, list) else [req]

    all_ok = True
    for it in items:
        payload = it.model_dump()
        _derive_scope(payload)
        # Persist first, then fan out. A failed DB write is logged and the fan-out still runs:
        # losing durability is bad, refusing to block an attacker is worse, and that degradation
        # is exactly the pre-1.7 behaviour.
        db_error = get_db().upsert_ban(
            payload["ip"],
            ban_scope=payload["ban_scope"],
            service_id=payload.get("service") or "",
            reason=payload.get("reason") or "",
            expires_at=_expires_at(payload.get("exp") or 0),
            origin="api",
        )
        if db_error:
            LOGGER.error(f"Couldn't persist the ban for {payload['ip']}: {db_error}")
        ok, _ = api_caller.send_to_apis("POST", "/ban", data=payload)
        all_ok = all_ok and ok
    return JSONResponse(status_code=200 if all_ok else 502, content={"status": "success" if all_ok else "error"})


@router.post("/unban", dependencies=[Depends(guard)])
@router.delete("", dependencies=[Depends(guard)])
def unban(req: Union[List[UnbanRequest], UnbanRequest, str], api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Remove one or multiple bans across all BunkerWeb instances.

    Args:
        req: Unban request(s) containing IP and optional service
    """
    if isinstance(req, str):
        try:
            loaded = json.loads(req)
            if isinstance(loaded, list):
                items: List[UnbanRequest] = [UnbanRequest(**it) for it in loaded]
            elif isinstance(loaded, dict):
                items = [UnbanRequest(**loaded)]
            else:
                return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid request body"})
        except Exception:
            return JSONResponse(status_code=422, content={"status": "error", "message": "Invalid request body"})
    else:
        items = req if isinstance(req, list) else [req]

    all_ok = True
    for it in items:
        payload = it.model_dump()
        _derive_scope(payload)
        # Unlike ban, a revoke that is not durable is refused. Without the tombstone the next
        # convergence pass re-learns the ban from an instance that missed this unban and re-pushes
        # it to the whole fleet — the operator's unban would be silently undone.
        db_error = get_db().revoke_ban(payload["ip"], ban_scope=payload["ban_scope"], service_id=payload.get("service") or "")
        if db_error:
            LOGGER.error(f"Refusing to unban {payload['ip']}: {db_error}")
            all_ok = False
            continue
        ok, _ = api_caller.send_to_apis("POST", "/unban", data=payload)
        all_ok = all_ok and ok
    return JSONResponse(status_code=200 if all_ok else 502, content={"status": "success" if all_ok else "error"})
