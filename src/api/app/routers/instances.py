from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from typing import Optional, List, Tuple
import re
from urllib.parse import urlsplit

from ..auth.guard import guard
from ..deps import get_instances_api_caller, get_api_for_hostname
from ..schemas import InstanceCreateRequest, InstancesDeleteRequest, InstanceUpdateRequest
from ..config import api_config
from ..utils import get_db, LOGGER

# Shared libs


router = APIRouter(prefix="/instances", tags=["instances"])


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
        test: If True, validate configuration without applying it (default: True)
    """
    test_arg = "yes" if test else "no"
    ok, _ = api_caller.send_to_apis("POST", f"/reload?test={test_arg}")
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


@router.post("/stop", dependencies=[Depends(guard)])
def stop(api_caller=Depends(get_instances_api_caller)) -> JSONResponse:
    """Stop all registered BunkerWeb instances."""
    ok, _ = api_caller.send_to_apis("POST", "/stop")
    return JSONResponse(status_code=200 if ok else 502, content={"status": "success" if ok else "error"})


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


@router.post("/{hostname}/reload", dependencies=[Depends(guard)])
def reload_one(hostname: str, test: bool = True, api=Depends(get_api_for_hostname)) -> JSONResponse:
    """Reload configuration on a specific BunkerWeb instance.

    Args:
        hostname: The hostname of the instance to reload
        test: If True, validate configuration without applying it (default: True)
    """
    test_arg = "yes" if test else "no"
    sent, _err, status, _resp = api.request("POST", f"/reload?test={test_arg}")
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


# -------------------- CRUD over BunkerWeb instances --------------------
_DOMAIN_RE = re.compile(r"^(?!.*\\.\\.)[^\\s\/:]{1,256}$")


def _normalize_hostname_and_port(hostname: str, port: Optional[int]) -> Tuple[str, Optional[int]]:
    # Robustly parse scheme/host/port
    try:
        parsed = urlsplit(hostname)
        host = (parsed.hostname or hostname).lower()
        eff_port = parsed.port or port
        return host, eff_port
    except Exception:
        host = hostname.replace("http://", "").replace("https://", "").lower()
        if ":" in host:
            h, p = host.split(":", 1)
            try:
                return h, int(p)
            except ValueError:
                return h, port
        return host, port


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
def list_instances() -> JSONResponse:
    """List all registered BunkerWeb instances with their details."""
    instances = get_db().get_instances()
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
    parsed = urlsplit(req.hostname)
    hostname, port = _normalize_hostname_and_port(req.hostname, req.port)

    if not _DOMAIN_RE.match(hostname):
        return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid hostname: {hostname}"})

    server_name = req.server_name or api_config.internal_api_host_header

    # Determine scheme and ports
    # Infer HTTPS if scheme is https and listen_https not explicitly provided
    inferred_https = parsed.scheme.lower() == "https"
    listen_https = bool(req.listen_https) if req.listen_https is not None else inferred_https
    https_port: Optional[int] = req.https_port if req.https_port is not None else (parsed.port if inferred_https else None)

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
    )
    if err:
        code = 400 if ("does not exist" in err or "read-only" in err) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": err})

    instance = db.get_instance(hostname)
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
    if inst.get("method") != "api":
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Instance {hostname} is not an API instance"})

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

    # Only delete instances created via API
    existing = {inst["hostname"]: inst for inst in db.get_instances()}

    to_delete: List[str] = []
    skipped: List[str] = []
    for h in req.instances:
        inst = existing.get(h)
        if not inst:
            skipped.append(h)
            continue
        if inst.get("method") != "api":
            skipped.append(h)
            continue
        to_delete.append(h)

    if not to_delete:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "message": "No deletable API instances found among selection",
                "skipped": skipped,
            },
        )

    err = db.delete_instances(to_delete)
    if err:
        return JSONResponse(status_code=500, content={"status": "error", "message": err, "skipped": skipped})

    return JSONResponse(status_code=200, content={"status": "success", "deleted": to_delete, "skipped": skipped})
