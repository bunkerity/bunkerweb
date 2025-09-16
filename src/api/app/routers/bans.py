from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from typing import List, Union
import json

from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..schemas import BanRequest, UnbanRequest


router = APIRouter(prefix="/bans", tags=["bans"])


@router.get("", dependencies=[Depends(guard)])
def list_bans(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """List all active bans across all BunkerWeb instances."""
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
        # Derive ban_scope from service presence: if no service, scope is global
        service = (payload.get("service") or "").strip() if isinstance(payload.get("service"), str) else payload.get("service")
        if service:
            payload["ban_scope"] = "service"
        else:
            payload["ban_scope"] = "global"
            # Remove empty service to avoid ambiguity downstream
            payload.pop("service", None)
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
        ok, _ = api_caller.send_to_apis("POST", "/unban", data=it.model_dump())
        all_ok = all_ok and ok
    return JSONResponse(status_code=200 if all_ok else 502, content={"status": "success" if all_ok else "error"})
