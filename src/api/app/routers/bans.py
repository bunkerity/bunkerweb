from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Union
import json

from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore
from crowdsec_unban import apply, find_lease, involved, preview, revalidate  # type: ignore

from ..auth.biscuit import authorize_resource
from ..auth.guard import guard
from ..deps import get_instances_api_caller
from ..schemas import BanRequest, UnbanRequest
from ..utils import LOGGER, get_db

router = APIRouter(prefix="/bans", tags=["bans"])

RESERVED_SERVICE_NAMES = frozenset({"unknown", "Web UI", "bwcli", "default server", ""})


def _derive_scope(payload: dict) -> None:
    """Derive ban_scope from service presence and validate reserved service names."""
    service = (payload.get("service") or "").strip() if isinstance(payload.get("service"), str) else payload.get("service")
    if service and service not in RESERVED_SERVICE_NAMES:
        payload["ban_scope"] = "service"
    else:
        payload["ban_scope"] = "global"
        payload.pop("service", None)


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
        _derive_scope(payload)
        ok, _ = api_caller.send_to_apis("POST", "/ban", data=payload)
        all_ok = all_ok and ok
    return JSONResponse(status_code=200 if all_ok else 502, content={"status": "success" if all_ok else "error"})


LEASE_FIELDS = frozenset({"kind", "remove_crowdsec_decisions", "confirmed", "decision_keys"})
LEASE_FLAGS_MESSAGE = (
    "This IP is blocked by a CrowdSec ban. Unbanning it also deletes the CrowdSec decisions behind it: review the preview, "
    "then resend with kind=crowdsec_lease, remove_crowdsec_decisions=true, confirmed=true and decision_keys set to the keys of the preview."
)


def _explicit_ban_state(api_caller, ip: str, ban_scope: str, service: Optional[str]) -> Optional[bool]:
    """True when an explicit ban exists on any instance, False when none does, None when the listing is incomplete."""
    ok, responses = api_caller.send_to_apis("GET", "/bans", response=True)
    for resp in (responses or {}).values():
        rows = resp.get("data") if isinstance(resp, dict) else None
        for row in rows or []:
            if not isinstance(row, dict) or row.get("kind", "ban") != "ban" or row.get("ip") != ip:
                continue
            row_service = row.get("service")
            row_scope = row.get("ban_scope") or ("global" if row_service in (None, "_") else "service")
            if row_scope == ban_scope and (ban_scope == "global" or row_service == service):
                return True
    return False if ok else None


def _error(status_code: int, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message} | extra)


def _prepare_lease(request: Request, client, entry: dict, admin: bool) -> Optional[JSONResponse]:
    """Compute the preview internally, then authorize crowdsec_delete on every connection it names, failed ones included.

    Nothing leaves the server before this returns. Returns an error response, or None with entry["preview"] and
    entry["allowed"] (None for an admin) set.
    """
    try:
        entry["preview"] = preview(client, entry["ip"], entry["ban_scope"], entry["service"])
    except CrowdSecError as exc:
        if not admin:
            # The connections are unknown: only a caller allowed on every connection may learn why it failed
            authorize_resource(request, "bans", "crowdsec_delete", "*")
        return _error(exc.status, str(exc))
    entry["allowed"] = None
    if not admin:
        connections, wildcard = involved(entry["preview"])
        if wildcard:
            # An unavailable entry with no connection id cannot be matched to a grant
            authorize_resource(request, "bans", "crowdsec_delete", "*")
            connections.add("*")
        for connection_id in sorted(connections - {"*"}):
            authorize_resource(request, "bans", "crowdsec_delete", connection_id)
        entry["allowed"] = connections
    return None


def _lease_flags_missing(entry: dict) -> bool:
    item = entry["item"]
    if entry.get("needs_lease_flags"):
        return True
    return entry["lease_item"] and not (item.remove_crowdsec_decisions and item.confirmed and item.decision_keys is not None)


@router.post("/unban", dependencies=[Depends(guard)])
@router.delete("", dependencies=[Depends(guard)])
def unban(req: Union[List[UnbanRequest], UnbanRequest, str], request: Request, api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Remove one or multiple bans across all BunkerWeb instances.

    Explicit bans are removed on every instance. A CrowdSec lease (kind "crowdsec_lease") also deletes the CrowdSec
    decisions behind it, after the caller confirmed the preview. Nothing is changed until every lease passed
    authorization and revalidation.

    Args:
        req: Unban request(s) containing IP and optional service. For a lease: remove_crowdsec_decisions, confirmed
            and decision_keys.
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

    admin = bool(getattr(request.state, "auth_admin", False))
    actor = getattr(request.state, "auth_subject", "biscuit")
    client = None
    entries = []
    for it in items:
        payload = it.model_dump(exclude=LEASE_FIELDS)
        _derive_scope(payload)
        entries.append(
            {
                "item": it,
                "payload": payload,
                "ip": payload["ip"],
                "ban_scope": payload["ban_scope"],
                "service": payload.get("service"),
                "lease_item": it.kind == "crowdsec_lease",
            }
        )

    # Prepare: classify and authorize. Nothing here mutates.
    for entry in entries:
        if not entry["lease_item"]:
            # kind is selection intent, never trusted: look for a lease behind an explicit unban too
            try:
                client = client or CrowdSecClient(get_db(log=False))
                lease = find_lease(client, entry["ip"], entry["ban_scope"], entry["service"])
            except CrowdSecError:
                entry["lease_check"] = "incomplete"
                continue
            if not lease:
                continue
            state = _explicit_ban_state(api_caller, entry["ip"], entry["ban_scope"], entry["service"])
            if state is None:
                entry["lease_check"] = "incomplete"
                continue
            if state:
                entry["lease_remains"] = True
                continue
            entry["needs_lease_flags"] = True
        client = client or CrowdSecClient(get_db(log=False))
        failure = _prepare_lease(request, client, entry, admin)
        if failure is not None:
            return failure

    blocking = [entry for entry in entries if _lease_flags_missing(entry)]
    if blocking:
        shown = [{"ip": e["ip"], "ban_scope": e["ban_scope"], "service": e["service"], "preview": e["preview"]} for e in blocking]
        return _error(409, LEASE_FLAGS_MESSAGE, preview=shown[0]["preview"], previews=shown)

    # Prepare barrier: every lease is revalidated before the first mutation
    for entry in entries:
        if not entry["lease_item"]:
            continue
        try:
            checked = revalidate(client, entry["ip"], entry["ban_scope"], entry["service"], entry["item"].decision_keys, entry["allowed"])
        except CrowdSecError as exc:
            return _error(exc.status, str(exc))
        if checked["status"] != "ready":
            body = {"preview": checked["preview"]} if "preview" in checked else {}
            return _error(409, "The CrowdSec bans for this IP changed since the preview; review it again.", **body)
        entry["preview"] = checked["preview"]

    # Apply: failures from here on are operational, never selection changes
    all_ok = True
    results = []
    for entry in entries:
        if entry["lease_item"]:
            outcome = apply(client, entry["ip"], entry["ban_scope"], entry["service"], entry["preview"])
            ok = outcome.get("status") == "success"
            (LOGGER.info if ok else LOGGER.warning)(
                "CrowdSec unban actor=%r ip=%s scope=%s service=%r outcome=%s deleted=%d failed=%d",
                actor,
                entry["ip"],
                entry["ban_scope"],
                entry["service"],
                outcome.get("status"),
                len(outcome.get("deleted", [])) + len(outcome.get("already_absent", [])),
                len(outcome.get("failed", [])) + len(outcome.get("lease_failed", [])),
            )
            results.append({"kind": "crowdsec_lease", "ip": entry["ip"], "ban_scope": entry["ban_scope"], "service": entry["service"], **outcome})
        else:
            ok, _ = api_caller.send_to_apis("POST", "/unban", data=entry["payload"])
            note = {key: entry[key] for key in ("lease_check", "lease_remains") if key in entry}
            if note:
                ok = ok and entry.get("lease_check") != "incomplete"
                results.append(
                    {
                        "kind": "ban",
                        "ip": entry["ip"],
                        "ban_scope": entry["ban_scope"],
                        "service": entry["service"],
                        "status": "success" if ok else "error",
                    }
                    | note
                )
        all_ok = all_ok and ok
    content = {"status": "success" if all_ok else "error"}
    if results:
        content["results"] = results
    return JSONResponse(status_code=200 if all_ok else 502, content=content)
