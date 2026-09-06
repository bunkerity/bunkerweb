from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from secrets import token_urlsafe
from typing import Optional, List

from API import API  # type: ignore
from common_utils import parse_host  # type: ignore

from ..auth.guard import guard
from ..deps import get_instances_api_caller, get_api_for_hostname
from ..schemas import (
    BulkUpdateInstancesRequest,
    InstanceCreateRequest,
    InstanceEnrollRedeemRequest,
    InstanceEnrollRequest,
    InstancesDeleteRequest,
    InstanceStatusRequest,
    InstanceUpdateRequest,
)
from ..config import api_config
from ..utils import get_db, LOGGER

# Shared libs
from db_methods.instances import ENROLLABLE_METHODS, ENROLLMENT_REJECTED  # type: ignore

# Shared libs


router = APIRouter(prefix="/instances", tags=["instances"])
UI_API_METHODS = {"ui", "api"}
# Keep aligned with common/core/jobs/jobs/push-configs.py.
RELOAD_TIMEOUT = (5, 30)
# A rotation hands the new credential to the instance before the database keeps it; a short
# timeout is right because the alternative to failing is a divided pair of credentials.
ROTATE_TIMEOUT = (5, 10)


# ---------- Instance actions broadcasted to all instances ----------
@router.get("/ping", dependencies=[Depends(guard)])
def ping(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Ping all registered BunkerWeb instances to check their availability."""
    ok, responses = api_caller.send_to_apis("GET", "/ping", response=True)
    return JSONResponse(status_code=200 if ok else 502, content=responses or {"status": "error", "msg": "internal error"})


@router.post("/reload", dependencies=[Depends(guard)])
def reload_config(test: bool = True, api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Reload configuration on all registered BunkerWeb instances.

    Args:
        test: If True, validate the configuration before applying it (default: True)
    """
    test_arg = "yes" if test else "no"
    ok, _ = api_caller.send_to_apis("POST", f"/reload?test={test_arg}", timeout=RELOAD_TIMEOUT)
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


@router.post("/stop", dependencies=[Depends(guard)])
def stop(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Stop all registered BunkerWeb instances."""
    ok, _ = api_caller.send_to_apis("POST", "/stop")
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


@router.put("/bulk", dependencies=[Depends(guard)])
def bulk_update_instances(req: BulkUpdateInstancesRequest) -> JSONResponse:
    """Bulk update instances for a given method.

    Replaces all instances with the given method tag.
    Used by Autoconf to sync discovered instances.
    """
    db = get_db()
    if err := db.update_instances(req.instances, req.method, changed=req.changed):
        code = 400 if "read-only" in err else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success"})


# ---------- Secure enrollment ----------
# Declared before the /{hostname}/... group so the literal "enroll" segment can never be read as a
# hostname. This is the ONLY route in the service without Depends(guard): it is what a booting
# instance calls before it has any credential to authenticate with. Its protection is the join
# code itself (single use, SHA-512 at rest, short TTL), the shared rate limiter, and the API's own
# IP whitelist.
@router.post("/enroll")
def redeem_enrollment(req: InstanceEnrollRedeemRequest) -> JSONResponse:
    """Redeem a one-time enrollment code and receive this instance's credential.

    The credential is returned here and never again. Every rejection answers 401 with the same
    message on purpose: an unauthenticated caller must not be able to tell an unknown hostname
    from a wrong code from an expired one.
    """
    credential, err = get_db().redeem_enrollment_code(req.hostname, req.code)
    if err:
        if credential is None and err != ENROLLMENT_REJECTED:
            # Operational failure (read-only database, no keyring), not a rejected code.
            LOGGER.error(f"POST /instances/enroll failed for {req.hostname}: {err}")
            return JSONResponse(status_code=503, content={"status": "error", "message": err})
        return JSONResponse(status_code=401, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success", "hostname": req.hostname, "credential": credential})


@router.post("/{hostname}/enroll", dependencies=[Depends(guard)])
def issue_enrollment(hostname: str, req: Optional[InstanceEnrollRequest] = None) -> JSONResponse:
    """Issue a single-use enrollment code for an instance. The code is shown once.

    Args:
        hostname: The hostname of the instance to enroll
        req: Optional TTL override for the issued code
    """
    code, err = get_db().issue_enrollment_code(hostname, req.ttl_seconds if req else None)
    if err:
        if "does not exist" in err:
            return JSONResponse(status_code=404, content={"status": "error", "message": err})
        if "read-only" in err:
            return JSONResponse(status_code=400, content={"status": "error", "message": err})
        if "sourced from its environment" in err:
            return JSONResponse(status_code=409, content={"status": "error", "message": err})
        return JSONResponse(status_code=500, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success", "hostname": hostname, "code": code})


@router.post("/{hostname}/rotate", dependencies=[Depends(guard)])
def rotate_credential(hostname: str, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Rotate an enrolled instance's credential.

    Two phases, and the database moves last: the new credential is handed to the instance over the
    channel the OLD one still authenticates, and only stored here once the instance confirmed.

    A rotation the instance *refused* is a clean 502 with nothing changed anywhere -- it answered,
    so it never renamed its credential file. A rotation whose *answer was lost* is different: the
    instance may already have committed, so that path (and a failed database write) puts the old
    credential back -- authenticating with the NEW one, because an instance that committed is
    precisely one that stopped accepting the old. When the rollback fails too, the two sides really
    are divided and the instance has to be re-enrolled (new code plus a restart); the log says so
    rather than leaving it to be discovered by a failing push days later.

    Args:
        hostname: The hostname of the instance whose credential to rotate
    """
    db = get_db()
    instance = db.get_instance(hostname, with_credential=True)
    if not instance:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Instance {hostname} not found"})
    # `ENROLLABLE_METHODS`, not the local `UI_API_METHODS`: the two answer different questions --
    # one is "can the control plane delete this row", the other "can it own a credential on it" --
    # and they stopped being the same set on 2026-09-02, when `manual` became enrollable and stayed
    # undeletable. Importing the DB's definition keeps this guard and `issue`/`revoke`'s own
    # refusals from drifting apart silently.
    # Permission before state, and the same 409 the DB layer returns for issue/revoke. An autoconf row
    # can legitimately hold a credential (`env["API_TOKEN"]` via the reconcile), so it reads
    # "enrolled" -- but rotating it hands the instance a credential its orchestrator will never
    # re-source, the next reconcile puts the env token back in the database, and the control plane is
    # locked out of a healthy instance with no recovery from the UI. Enrollment is a
    # control-plane-owned concept; the state string is not the permission.
    # `manual` rows left this paragraph on 2026-09-02, but only PARTLY: the `save_config.py` rebuild
    # now updates a still-declared row in place instead of re-creating it, so it no longer drops a
    # minted credential by itself. It does still let a declared `BUNKERWEB_INSTANCE_API_TOKEN_<n>`
    # win over one -- see `_reconcile_credential_columns` in `db_methods/instances.py`, which logs
    # exactly this. So rotating a `manual` row that declares its own token in the environment has
    # the autoconf failure mode above: the next config save puts the declared token back and the
    # control plane is locked out until the operator drops the variable. Not refused here, because
    # the database cannot tell a declared token from a minted one -- nothing records which produced
    # `credential_ciphertext`. That is a MISSING FACT, not a missing column: `enroll_code_state` is a
    # plain `String(16)` whose value set is closed by construction (`model.py`), so a third value
    # would cost no migration. It is not free either -- it would fold credential provenance back
    # into the code-lifecycle column L-A4 deliberately split apart -- so it stays a decision, taken
    # by the PO, not a schema constraint (report-L-A3.md §6 Q1).
    if instance.get("method") not in ENROLLABLE_METHODS:
        return JSONResponse(
            status_code=409,
            content={
                "status": "error",
                "message": (
                    f"Instance {hostname} is sourced from its environment (method: {instance.get('method')}); "
                    "enrollment only applies to control-plane-owned instances"
                ),
            },
        )
    if instance.get("enrollment_state") != "enrolled":
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": f"Instance {hostname} is not enrolled; issue an enrollment code instead"},
        )

    previous_credential = instance.get("credential")
    new_credential = token_urlsafe(48)

    def _roll_back(reason: str) -> None:
        """Put the old credential back, authenticating with the NEW one.

        Reusing the `api` dependency here would be a no-op dressed up as a recovery: it carries
        the old credential, and an instance that committed has stopped accepting it.
        """
        if not previous_credential:
            return
        try:
            rollback_api = API.from_instance(instance | {"credential": new_credential})
            sent_back, _, rollback_status, _ = rollback_api.request("POST", "/credential", data={"credential": previous_credential}, timeout=ROTATE_TIMEOUT)
        except BaseException as exc:
            # This already runs inside a failure path: raising here would replace a 502/500 that
            # names the real problem with an opaque unhandled exception.
            LOGGER.critical(f"Rotation of {hostname} failed ({reason}) and the rollback itself raised: {exc}")
            return
        if sent_back and rollback_status == 200:
            LOGGER.error(f"Rotation of {hostname} failed ({reason}) and was rolled back on the instance")
            return
        LOGGER.critical(
            f"Rotation of {hostname} failed ({reason}) AND the rollback failed: the instance may hold a credential this "
            "database does not have. Issue a new enrollment code and restart it."
        )

    sent, err, status, _ = api.request("POST", "/credential", data={"credential": new_credential}, timeout=ROTATE_TIMEOUT)
    if not sent or status != 200:
        # The two cases ARE distinguishable, and treating them alike emitted a CRITICAL telling the
        # operator to re-enroll after an ordinary refusal. `API.request()` returns sent=True only
        # once it has an answer, so sent=True with a non-200 means the instance answered and never
        # renamed its credential file: nothing was written, nothing to undo. A lost answer
        # (sent=False) is the one case where the instance may have committed.
        if not sent:
            _roll_back(err or "no answer")
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": f"Instance {hostname} did not accept the new credential: {err or f'HTTP {status}'}"},
        )

    cred_err = db.set_instance_credential(hostname, new_credential)
    if cred_err:
        # The instance took the new credential and the database kept the old one: without this
        # rollback the control plane would have just locked itself out of a healthy instance.
        _roll_back(f"database write: {cred_err}")
        return JSONResponse(status_code=500, content={"status": "error", "message": cred_err})

    return JSONResponse(status_code=200, content={"status": "success", "hostname": hostname})


@router.post("/{hostname}/revoke", dependencies=[Depends(guard)])
def revoke_enrollment(hostname: str) -> JSONResponse:
    """Revoke an instance's credential. Pushes to it are refused afterwards.

    Args:
        hostname: The hostname of the instance to revoke
    """
    db = get_db()
    if not db.get_instance(hostname):
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Instance {hostname} not found"})
    err = db.revoke_instance_enrollment(hostname)
    if err:
        if "sourced from its environment" in err:
            return JSONResponse(status_code=409, content={"status": "error", "message": err})
        code = 400 if ("does not exist" in err or "read-only" in err) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": err})
    return JSONResponse(status_code=200, content={"status": "success", "hostname": hostname, "enrollment_state": "revoked"})


# ---------- Instance actions for a single instance ----------
@router.get("/{hostname}/ping", dependencies=[Depends(guard)])
def ping_one(hostname: str, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Ping a specific BunkerWeb instance to check its availability.

    Args:
        hostname: The hostname of the instance to ping
    """
    sent, err, status, resp = api.request("GET", "/ping")
    if not sent or status != 200:
        return JSONResponse(status_code=502, content={"status": "error", "msg": (err or getattr(resp, "get", lambda _k: None)("msg")) or "internal error"})
    return JSONResponse(status_code=200, content=resp if isinstance(resp, dict) else {"status": "ok"})


@router.get("/{hostname}/health", dependencies=[Depends(guard)])
def health_one(hostname: str, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Report a specific BunkerWeb instance's own state.

    Where /ping only answers "reachable", this forwards what the instance says about itself:
    "ok", "loading", "reloading" or "needs_config". The scheduler needs the difference — an instance that
    restarted comes back reachable while still stuck in its loading state, where every
    timer-driven plugin is disabled, and no ping can tell that apart from a healthy one.

    Args:
        hostname: The hostname of the instance to query
    """
    sent, err, status, resp = api.request("GET", "/health")
    if not sent or status != 200:
        return JSONResponse(status_code=502, content={"status": "error", "msg": (err or getattr(resp, "get", lambda _k: None)("msg")) or "internal error"})
    return JSONResponse(status_code=200, content=resp if isinstance(resp, dict) else {"status": "ok"})


@router.post("/{hostname}/reload", dependencies=[Depends(guard)])
def reload_one(hostname: str, test: bool = True, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Reload configuration on a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to reload
        test: If True, validate the configuration before applying it (default: True)
    """
    test_arg = "yes" if test else "no"
    sent, _err, status, _resp = api.request("POST", f"/reload?test={test_arg}", timeout=RELOAD_TIMEOUT)
    ok = bool(sent and status == 200)
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


@router.post("/{hostname}/stop", dependencies=[Depends(guard)])
def stop_one(hostname: str, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Stop a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to stop
    """
    sent, _err, status, _resp = api.request("POST", "/stop")
    ok = bool(sent and status == 200)
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


@router.patch("/{hostname}/status", dependencies=[Depends(guard)])
def update_instance_status(hostname: str, payload: InstanceStatusRequest) -> JSONResponse:
    """Update the status of a specific BunkerWeb instance (up/down/failover).

    Args:
        hostname: The hostname of the instance to update
        payload: New status value
    """
    ret = get_db().update_instance(hostname, payload.status)
    if ret:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(ret)})
    return JSONResponse(status_code=200, content={"status": "success"})


# -------------------- CRUD over BunkerWeb instances --------------------
def _validate_port(port: Optional[int]) -> Optional[int]:
    """Validate a TCP port (1..65535). Returns the int or raises ValueError."""
    if port is None:
        return None
    try:
        p = int(port)
    except Exception:
        raise ValueError("Port must be an integer")
    if p < 1 or p > 65535:
        raise ValueError("Port must be between 1 and 65535")
    return p


@router.get("", dependencies=[Depends(guard)])
def list_instances(autoconf: bool = False) -> JSONResponse:
    """List all registered BunkerWeb instances with their details."""
    instances = get_db().get_instances(autoconf=autoconf)
    for instance in instances:
        instance["creation_date"] = instance["creation_date"].astimezone().isoformat()
        instance["last_seen"] = instance["last_seen"].astimezone().isoformat() if instance.get("last_seen") else None

    return JSONResponse(status_code=200, content={"status": "success", "instances": instances})


@router.post("", dependencies=[Depends(guard)])
def create_instance(req: InstanceCreateRequest) -> JSONResponse:
    """Create a new BunkerWeb instance.

    Args:
        req: Instance creation request with hostname, port, server_name, etc.
    """
    db = get_db()

    # Derive defaults from api_config when not provided
    name = req.name or "manual instance"
    method = req.method or "api"
    try:
        scheme, hostname, provided_port = parse_host(req.hostname)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"status": "error", "message": str(e)})

    server_name = req.server_name or api_config.internal_api_host_header

    # Determine scheme and ports
    # Infer HTTPS if scheme is https and listen_https not explicitly provided
    inferred_https = scheme == "https"
    listen_https = bool(req.listen_https) if req.listen_https is not None else inferred_https
    port = provided_port if provided_port is not None and not inferred_https else req.port
    https_port: Optional[int] = provided_port if provided_port is not None and inferred_https else req.https_port

    # Validate provided ports or use defaults
    if port is not None:
        try:
            port = _validate_port(port)
        except ValueError as ve:
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid port: {ve}"})
    else:
        try:
            port = _validate_port(int(api_config.internal_api_port))
        except Exception:
            LOGGER.exception("Invalid API_HTTP_PORT in api_config; must be 1..65535")
            return JSONResponse(status_code=500, content={"status": "error", "message": "internal error"})

    if https_port is not None:
        try:
            https_port = _validate_port(https_port)
        except ValueError as ve:
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid https_port: {ve}"})
    else:
        try:
            cfg = db.get_config(global_only=True, methods=False, filtered_settings=("API_HTTPS_PORT",))
            https_port = _validate_port(int(cfg.get("API_HTTPS_PORT", "5443")))
        except Exception:
            https_port = 5443

    err = db.add_instance(
        hostname=hostname,
        port=port,
        server_name=server_name,
        method=method,
        name=name,
        listen_https=listen_https,
        https_port=https_port,
    )
    if err:
        code = 400 if "already exists" in err or "read-only" in err else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": err})

    if req.credential:
        cred_err = db.set_instance_credential(hostname, req.credential)
        if cred_err:
            LOGGER.warning(f"Instance {hostname} created but its credential could not be stored: {cred_err}")
    if req.tls_mode is not None or req.tls_fingerprint is not None:
        tls_err = db.update_instance_fields(hostname, tls_mode=req.tls_mode, tls_fingerprint=req.tls_fingerprint)
        if tls_err:
            LOGGER.warning(f"Instance {hostname} created but its TLS settings could not be applied: {tls_err}")

    return JSONResponse(
        status_code=201,
        content={
            "status": "success",
            "instance": {
                "hostname": hostname,
                "name": name,
                "port": port,
                "server_name": server_name,
                "method": method,
                "listen_https": listen_https,
                "https_port": https_port,
                "tls_mode": req.tls_mode or "off",
                "credential_set": bool(req.credential),
            },
        },
    )


@router.get("/{hostname}", dependencies=[Depends(guard)])
def get_instance(hostname: str) -> JSONResponse:
    """Get details of a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to retrieve
    """
    instance = get_db().get_instance(hostname)
    if not instance:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Instance {hostname} not found"})

    instance["creation_date"] = instance["creation_date"].astimezone().isoformat()
    instance["last_seen"] = instance["last_seen"].astimezone().isoformat() if instance.get("last_seen") else None
    return JSONResponse(status_code=200, content={"status": "success", "instance": instance})


@router.patch("/{hostname}", dependencies=[Depends(guard)])
def update_instance(hostname: str, req: InstanceUpdateRequest) -> JSONResponse:
    """Update properties of a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to update
        req: Update request with new values for name, port, server_name, method
    """
    db = get_db()
    instance = db.get_instance(hostname)
    if not instance:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Instance {hostname} not found"})

    tls_mode = req.tls_mode if req.tls_mode is not None else instance.get("tls_mode", "off")
    tls_fingerprint = req.tls_fingerprint if "tls_fingerprint" in req.model_fields_set else instance.get("tls_fingerprint")
    if tls_mode == "pinned" and not tls_fingerprint:
        return JSONResponse(status_code=422, content={"status": "error", "message": "tls_fingerprint is required when tls_mode=pinned"})

    # Validate optional port if provided
    if req.port is not None:
        try:
            _ = _validate_port(req.port)
        except ValueError as ve:
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid port: {ve}"})

    err = db.update_instance_fields(
        hostname,
        name=req.name,
        port=int(req.port) if req.port is not None else None,
        server_name=req.server_name,
        method=req.method,
        listen_https=bool(req.listen_https) if req.listen_https is not None else None,
        https_port=int(req.https_port) if req.https_port is not None else None,
        tls_mode=req.tls_mode,
        tls_fingerprint="" if "tls_fingerprint" in req.model_fields_set and req.tls_fingerprint is None else req.tls_fingerprint,
    )
    if err:
        code = 400 if ("does not exist" in err or "read-only" in err) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": err})

    # A credential of "" explicitly clears it; None means "leave unchanged".
    if req.credential is not None:
        cred_err = db.set_instance_credential(hostname, req.credential)
        if cred_err:
            code = 400 if ("does not exist" in cred_err or "read-only" in cred_err) else 500
            return JSONResponse(status_code=code, content={"status": "error", "message": cred_err})

    instance = db.get_instance(hostname)
    if instance:
        instance["creation_date"] = instance["creation_date"].astimezone().isoformat() if instance.get("creation_date") else None
        instance["last_seen"] = instance["last_seen"].astimezone().isoformat() if instance.get("last_seen") else None
    return JSONResponse(status_code=200, content={"status": "success", "instance": instance})


@router.delete("/{hostname}", dependencies=[Depends(guard)])
def delete_instance(hostname: str) -> JSONResponse:
    """Delete a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to delete
    """
    db = get_db()

    inst = db.get_instance(hostname)
    if not inst:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Instance {hostname} not found"})
    if inst.get("method") not in UI_API_METHODS:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Instance {hostname} is not a UI/API instance"})

    err = db.delete_instance(hostname)
    if err:
        LOGGER.exception(f"DELETE /instances/{hostname} failed: {err}")
        return JSONResponse(status_code=500, content={"status": "error", "message": err})

    return JSONResponse(status_code=200, content={"status": "success", "deleted": hostname})


@router.delete("", dependencies=[Depends(guard)])
def delete_instances(req: InstancesDeleteRequest) -> JSONResponse:
    """Delete multiple BunkerWeb instances.

    Args:
        req: Request containing list of hostnames to delete
    """
    db = get_db()

    # Only delete instances created via UI/API
    existing = {inst["hostname"]: inst for inst in db.get_instances()}

    to_delete: List[str] = []
    skipped: List[str] = []
    for h in req.instances:
        inst = existing.get(h)
        if not inst:
            skipped.append(h)
            continue
        if inst.get("method") not in UI_API_METHODS:
            skipped.append(h)
            continue
        to_delete.append(h)

    if not to_delete:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "No deletable UI/API instances found among selection",
                "skipped": skipped,
            },
        )

    err = db.delete_instances(to_delete)
    if err:
        return JSONResponse(status_code=500, content={"status": "error", "message": err, "skipped": skipped})

    return JSONResponse(status_code=200, content={"status": "success", "deleted": to_delete, "skipped": skipped})
