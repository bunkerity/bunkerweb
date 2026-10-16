from contextlib import suppress
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from os import environ
from typing import List, Optional, Union
import json

from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore
from crowdsec_unban import apply, collect_runtime, find_leases, involved, preview, redis_client_from, revalidate  # type: ignore

from ..auth.biscuit import authorize_resource
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


@router.get("/timeseries", dependencies=[Depends(guard)])
def query_bans_timeseries(start: int, end: int, bucket: str = "hour") -> JSONResponse:
    """Active bans per interval over ``[start, end)``.

    Occupancy, not creations: ``bw_bans`` keeps one row per ``(ip, ban_scope, service_id)`` and a
    re-ban rewrites ``created_at`` on it, so the table cannot back an event history. See
    ``DatabaseBansMixin.get_bans_timeseries``.

    No ACL wiring: ``_resolve_bans`` falls back to a per-verb mapping for any unlisted path under
    ``/bans``, so this ``GET`` resolves ``ban_read`` on its own (pinned by
    ``tests/unit/api/test_bans_timeseries.py``).
    """
    try:
        result = get_db().get_bans_timeseries(start=start, end=end, bucket=bucket)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
    return JSONResponse(status_code=200, content={"status": "success", **result})


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


LEASE_FIELDS = frozenset({"remove_crowdsec_decisions", "confirmed", "decision_keys"})
LEASE_FLAGS_MESSAGE = (
    "This IP is blocked by a CrowdSec ban. Unbanning it also deletes the CrowdSec decisions behind it: review the preview, "
    "then resend with remove_crowdsec_decisions=true, confirmed=true and decision_keys set to the keys of the preview."
)


def _error(status_code: int, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": "error", "message": message} | extra)


def _redis_client():
    """The Redis client for the ban keys: the environment over the global configuration, None when Redis is off or unreachable."""
    try:
        settings = (get_db(log=False).get_config(global_only=True) or {}) | {k: v for k, v in environ.items() if k.startswith("REDIS_") or k == "USE_REDIS"}
        return redis_client_from(settings)
    except Exception as exc:
        LOGGER.warning(f"Couldn't open Redis to look for CrowdSec bans: {exc}")
        return None


def _prepare_lease(request: Request, client, entry: dict, admin: bool, runtime: dict, redis_client) -> Optional[JSONResponse]:
    """Compute the preview internally, then authorize crowdsec_delete on every connection it names, failed ones included.

    Nothing leaves the server before this returns. Returns an error response, or None with entry["preview"] and
    entry["allowed"] (None for an admin) set.
    """
    try:
        entry["preview"] = preview(client, entry["ip"], entry["ban_scope"], entry["service"], runtime, redis_client)
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
    return not (item.remove_crowdsec_decisions and item.confirmed and item.decision_keys is not None)


@router.post("/unban", dependencies=[Depends(guard)])
@router.delete("", dependencies=[Depends(guard)])
def unban(req: Union[List[UnbanRequest], UnbanRequest, str], request: Request, api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Remove one or multiple bans across all BunkerWeb instances.

    Explicit bans are removed on every instance. A CrowdSec lease also deletes the CrowdSec decisions behind it, after
    the caller confirmed the preview; a plain unban of a lease answers 409 with that preview. Leases are found in the
    runtime view of the instances (and Redis), never taken from the request. A lease is removed and revoked by its
    ``lease_id`` only, so an explicit ban on the same IP is never touched. Nothing is changed until every lease passed
    authorization and revalidation, and the database revoke of a lease is the last step.

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
    entries = []
    for it in items:
        payload = it.model_dump(exclude=LEASE_FIELDS)
        _derive_scope(payload)
        entries.append({"item": it, "payload": payload, "ip": payload["ip"], "ban_scope": payload["ban_scope"], "service": payload.get("service")})

    # Prepare: find the leases in the runtime view (one snapshot for the whole request), then authorize. Nothing here mutates.
    client = runtime = None
    redis_client = _redis_client()
    with suppress(CrowdSecError):
        client = CrowdSecClient(get_db(log=False))
        runtime = collect_runtime(client)
    for entry in entries:
        if runtime is None:
            entry["lease_check"] = "incomplete"
            continue
        leases, failures = find_leases(runtime, entry["ip"], entry["ban_scope"], entry["service"], redis_client)
        if not leases:
            if failures:
                entry["lease_check"] = "incomplete"
            continue
        entry["lease_item"] = True
        failure = _prepare_lease(request, client, entry, admin, runtime, redis_client)
        if failure is not None:
            return failure

    blocking = [entry for entry in entries if entry.get("lease_item") and _lease_flags_missing(entry)]
    if blocking:
        shown = [{"ip": e["ip"], "ban_scope": e["ban_scope"], "service": e["service"], "preview": e["preview"]} for e in blocking]
        return _error(409, LEASE_FLAGS_MESSAGE, preview=shown[0]["preview"], previews=shown)

    # Prepare barrier: every lease is revalidated against a fresh snapshot before the first mutation
    leased = [entry for entry in entries if entry.get("lease_item")]
    fresh = collect_runtime(client) if leased else None
    for entry in leased:
        try:
            checked = revalidate(client, entry["ip"], entry["ban_scope"], entry["service"], entry["item"].decision_keys, entry["allowed"], fresh, redis_client)
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
        if entry.get("lease_item"):
            outcome = apply(client, entry["ip"], entry["ban_scope"], entry["service"], entry["preview"], db=get_db(), actor=str(actor))
            ok = outcome.get("status") == "success"
            (LOGGER.info if ok else LOGGER.warning)(
                "CrowdSec unban actor=%r ip=%s scope=%s service=%r outcome=%s deleted=%d failed=%d",
                actor,
                entry["ip"],
                entry["ban_scope"],
                entry["service"],
                outcome.get("status"),
                len(outcome.get("deleted", [])) + len(outcome.get("already_absent", [])),
                len(outcome.get("failed", [])) + len(outcome.get("lease_failed", [])) + len(outcome.get("db_failed", [])),
            )
            results.append({"kind": "crowdsec_lease", "ip": entry["ip"], "ban_scope": entry["ban_scope"], "service": entry["service"], **outcome})
            all_ok = all_ok and ok
            continue
        # Unlike ban, a revoke that is not durable is refused. Without the tombstone the next
        # convergence pass re-learns the ban from an instance that missed this unban and re-pushes
        # it to the whole fleet — the operator's unban would be silently undone.
        db_error = get_db().revoke_ban(entry["ip"], ban_scope=entry["ban_scope"], service_id=entry["service"] or "")
        if db_error:
            LOGGER.error(f"Refusing to unban {entry['ip']}: {db_error}")
            all_ok = False
            continue
        ok, _ = api_caller.send_to_apis("POST", "/unban", data=entry["payload"])
        if entry.get("lease_check") == "incomplete":
            ok = False
            results.append(
                {"kind": "ban", "ip": entry["ip"], "ban_scope": entry["ban_scope"], "service": entry["service"], "status": "error", "lease_check": "incomplete"}
            )
        all_ok = all_ok and ok
    content = {"status": "success" if all_ok else "error"}
    if results:
        content["results"] = results
    return JSONResponse(status_code=200 if all_ok else 502, content=content)
