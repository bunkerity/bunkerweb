from contextlib import suppress
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from ..auth.guard import guard
from ..utils import get_db, reportable_config
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

    conf = reportable_config(db.get_config(methods=True, with_drafts=with_drafts, service=service), methods=methods)
    return JSONResponse(status_code=200, content={"status": "success", "service": service, "config": conf})


def _full_config_snapshot() -> Dict[str, Any]:
    """Return a full config snapshot (global + services) as flat dict of values only."""
    return get_db().get_non_default_settings(methods=False, with_drafts=True)


def _persist_config(config: Dict[str, Any], rename: Optional[tuple[str, str]] = None) -> JSONResponse:
    kwargs = {"changed": True}
    if rename is not None:
        kwargs["rename"] = rename
    ret = get_db().save_config(config, "api", **kwargs)

    if isinstance(ret, str):
        code = 400 if ("read-only" in ret or "already exists" in ret or "doesn't exist" in ret) else 500
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success", "changed_plugins": sorted(list(ret))})


def _service_method(service: str) -> Optional[str]:
    for item in get_db().get_services(with_drafts=True):
        if item.get("id") == service:
            return item.get("method")
    return None


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
    db = get_db()
    conf = _full_config_snapshot()
    services_list = (conf.get("SERVER_NAME", "") or "").split()
    if service not in services_list:
        return JSONResponse(status_code=404, content={"status": "error", "message": f"Service {service} not found"})

    target = service
    rename = None
    # Build the complete save payload from the pre-rename snapshot. Database.save_config
    # moves the service rows in the same transaction.
    if req.server_name:
        new_name = req.server_name.split(" ")[0].strip()
        if not new_name:
            return JSONResponse(status_code=422, content={"status": "error", "message": "server_name cannot be empty"})
        if new_name != service:
            if new_name in services_list:
                return JSONResponse(status_code=400, content={"status": "error", "message": f"Service {new_name} already exists"})

            # A service defined outside the API (environment, autoconf, wizard) is re-asserted
            # by its owner on the next scheduler pass, which would treat the renamed row as a
            # removed service and cascade-delete its custom configs and job cache.
            method = _service_method(service)
            if method not in ("ui", "api"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "status": "error",
                        "message": f"Service {service} is managed by {method or 'another component'} and must be renamed where it is defined",
                    },
                )

            valid, reason = db.is_valid_setting("SERVER_NAME", value=new_name, multisite=True)
            if not valid:
                return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid server_name {new_name}: {reason}"})

            own = db.get_non_default_settings(methods=True, with_drafts=True, service=service).get("SERVER_NAME")
            rewritten = {}
            prefix = f"{service}_"
            for key, value in conf.items():
                rewritten[f"{new_name}_{key[len(prefix):]}" if key.startswith(prefix) else key] = value
            conf = rewritten
            conf["SERVER_NAME"] = " ".join(new_name if token == service else token for token in str(conf.get("SERVER_NAME", "") or "").split())
            target = new_name
            rename = (service, new_name)

            if isinstance(own, dict) and own.get("global") is False:
                conf[f"{target}_SERVER_NAME"] = " ".join(new_name if token == service else token for token in str(own.get("value") or "").split()) or new_name
            else:
                conf[f"{target}_SERVER_NAME"] = new_name

    for key, value in (req.variables or {}).items():
        valid, reason = db.is_valid_setting(key, value=value, multisite=True)
        if not valid:
            return JSONResponse(status_code=422, content={"status": "error", "message": f"Invalid value for {key}: {reason}"})

    # Draft flag update
    if req.is_draft is not None:
        conf[f"{target}_IS_DRAFT"] = "yes" if bool(req.is_draft) else "no"

    # Update provided variables (unprefixed)
    for k, v in (req.variables or {}).items():
        if k == "SERVER_NAME":
            # Ignore direct edits to SERVER_NAME via variables
            continue
        conf[f"{target}_{k}"] = "" if v is None else v

    return _persist_config(conf, rename=rename)


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
    if _service_method(service) == "wizard":
        return JSONResponse(status_code=403, content={"status": "error", "message": f"Service {service} is managed by wizard and cannot be deleted"})

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
