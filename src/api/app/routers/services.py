from contextlib import suppress
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db
from ..schemas import ServiceCreateRequest, ServiceUpdateRequest


router = APIRouter(prefix="/services", tags=["services"])


def _iso(dt) -> Optional[str]:
    with suppress(Exception):
        return dt.astimezone().isoformat()
    return None


@router.get("", dependencies=[Depends(guard)])
def list_services(with_drafts: bool = True) -> JSONResponse:
    """List all services with their configurations.

    Args:
        with_drafts: Include draft services in the results (default: True)
    """
    services = get_db().get_services(with_drafts=with_drafts)
    for it in services:
        it["creation_date"] = _iso(it.get("creation_date"))
        it["last_update"] = _iso(it.get("last_update"))
    return JSONResponse(status_code=200, content={"status": "success", "services": services})


@router.get("/{service}", dependencies=[Depends(guard)])
def get_service(service: str, full: bool = False, methods: bool = True, with_drafts: bool = True) -> JSONResponse:
    """Get configuration for a specific service.

    Args:
        service: Service identifier
        full: Return complete configuration including defaults
        methods: Include method metadata for each setting
        with_drafts: Include draft services when computing templates
    """
    db = get_db()
    # Check existence
    exists = any(s.get("id") == service for s in db.get_services(with_drafts=True))
    if not exists:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    if full:
        conf = db.get_config(methods=methods, with_drafts=with_drafts, service=service)
        return JSONResponse(status_code=200, content={"status": "success", "service": service, "config": conf})

    conf = db.get_non_default_settings(methods=methods, with_drafts=with_drafts, service=service)
    return JSONResponse(status_code=200, content={"status": "success", "service": service, "config": conf})


def _full_config_snapshot() -> Dict[str, Any]:
    """Return a full config snapshot (global + services) as flat dict of values only."""
    return get_db().get_non_default_settings(methods=False, with_drafts=True)


def _persist_config(config: Dict[str, Any]) -> JSONResponse:
    ret = get_db().save_config(config, "api", changed=True)

    if isinstance(ret, str):
        code = 400 if ("read-only" in ret or "already exists" in ret or "doesn't exist" in ret) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success", "changed_plugins": sorted(list(ret))})


@router.post("", dependencies=[Depends(guard)])
def create_service(req: ServiceCreateRequest) -> JSONResponse:
    """Create a new service with the specified configuration.

    Args:
        req: Service creation request with server_name, variables, and draft status
    """
    conf = _full_config_snapshot()
    name = req.server_name.split(" ")[0].strip()
    if not name:
        return JSONResponse(status_code=422, content={"status": "error", "message": "server_name is required"})

    # Reject duplicates
    existing = set((conf.get("SERVER_NAME", "") or "").split())
    if name in existing:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Service {name} already exists"})

    # Draft flag
    conf[f"{name}_IS_DRAFT"] = "yes" if req.is_draft else "no"

    # Set provided variables (unprefixed)
    for k, v in (req.variables or {}).items():
        if isinstance(v, (dict, list)):
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid value for {k}: must be scalar"})
        conf[f"{name}_{k}"] = "" if v is None else v

    if "SERVER_NAME" not in (req.variables or {}):
        conf[f"{name}_SERVER_NAME"] = name

    conf["SERVER_NAME"] = " ".join(sorted(existing | {name}))

    return _persist_config(conf)


@router.patch("/{service}", dependencies=[Depends(guard)])
def update_service(service: str, req: ServiceUpdateRequest) -> JSONResponse:
    """Update an existing service's configuration.

    Args:
        service: Current service identifier
        req: Update request with new server_name, variables, and draft status
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    if service not in services_list:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    target = service
    # Handle rename
    if req.server_name:
        new_name = req.server_name.split(" ")[0].strip()
        if not new_name:
            return JSONResponse(status_code=422, content={"status": "error", "message": "server_name cannot be empty"})
        if new_name != service and new_name in services_list:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Service {new_name} already exists"})

        # Replace in SERVER_NAME and prefix keys
        services_list = [new_name if s == service else s for s in services_list]
        conf["SERVER_NAME"] = " ".join(services_list)
        # Rename prefixed keys
        renames: List[tuple[str, str]] = []
        for key in list(conf.keys()):
            if key.startswith(f"{service}_"):
                suffix = key[len(service) + 1 :]  # noqa: E203
                renames.append((key, f"{new_name}_{suffix}"))
        for old, new in renames:
            conf[new] = conf.pop(old)
        target = new_name

    # Draft flag update
    if req.is_draft is not None:
        conf[f"{target}_IS_DRAFT"] = "yes" if bool(req.is_draft) else "no"

    # Update provided variables (unprefixed)
    for k, v in (req.variables or {}).items():
        if k == "SERVER_NAME":
            # Ignore direct edits to SERVER_NAME via variables
            continue
        if isinstance(v, (dict, list)):
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid value for {k}: must be scalar"})
        conf[f"{target}_{k}"] = "" if v is None else v

    return _persist_config(conf)


@router.delete("/{service}", dependencies=[Depends(guard)])
def delete_service(service: str) -> JSONResponse:
    """Delete a service and all its configuration.

    Args:
        service: Service identifier to delete
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    if service not in services_list:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    # Remove from server list
    conf["SERVER_NAME"] = " ".join([s for s in services_list if s != service])
    # Drop prefixed keys
    for key in list(conf.keys()):
        if key.startswith(f"{service}_"):
            conf.pop(key)

    return _persist_config(conf)


@router.post("/{service}/convert", dependencies=[Depends(guard)])
def convert_service(service: str, convert_to: str = Query(..., pattern="^(online|draft)$")) -> JSONResponse:
    """Convert a service between online and draft status.

    Args:
        service: Service identifier
        convert_to: Target status ("online" or "draft")
    """
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    to_convert = [s for s in (service,) if s in services_list]
    if not to_convert:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No valid services to convert"})
    to_val = "no" if convert_to == "online" else "yes"
    for s in to_convert:
        conf[f"{s}_IS_DRAFT"] = to_val
    return _persist_config(conf)
