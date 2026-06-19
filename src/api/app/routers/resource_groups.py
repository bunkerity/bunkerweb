from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/resource_groups", tags=["resource_groups"])


# ── Schemas ─────────────────────────────────────────────────────────


class ResourceGroupCreateRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    entries: List[Dict[str, Any]] = Field(default_factory=list)
    method: str = "ui"
    plugin_id: Optional[str] = None


class ResourceGroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entries: Optional[List[Dict[str, Any]]] = None
    plugin_id: Optional[str] = None


class ResourceGroupCloneRequest(BaseModel):
    id: str
    name: str


def _serialize_dates(data: Dict[str, Any]) -> Dict[str, Any]:
    for field in ("creation_date", "last_update"):
        if hasattr(data.get(field), "isoformat"):
            data[field] = data[field].isoformat()
    return data


# Substrings that map a DB-layer error string to a 400 (client) rather than a 500.
_CLIENT_ERROR_HINTS = (
    "already exists",
    "read-only",
    "is required",
    "cannot be empty",
    "cannot be modified",
    "cannot be deleted",
    "Invalid",
    "must be",
    "does not exist",
    "referenced",
)


def _error_response(ret: str) -> JSONResponse:
    if "not found" in ret:
        code = 404
    elif any(hint in ret for hint in _CLIENT_ERROR_HINTS):
        code = 400
    else:
        code = 500
    return JSONResponse(status_code=code, content={"status": "error", "message": ret})


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(guard)])
def list_resource_groups() -> JSONResponse:
    """List all resource groups with their entries."""
    groups = get_db().get_resource_groups()
    for data in groups.values():
        _serialize_dates(data)
    return JSONResponse(status_code=200, content={"status": "success", "resource_groups": groups})


@router.get("/{group_id}", dependencies=[Depends(guard)])
def get_resource_group(group_id: str) -> JSONResponse:
    """Get a single resource group with its entries."""
    details = get_db().get_resource_group_details(group_id)
    if not details:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Resource group not found"})
    _serialize_dates(details)
    return JSONResponse(status_code=200, content={"status": "success", "resource_group": details})


@router.post("", dependencies=[Depends(guard)])
def create_resource_group(req: ResourceGroupCreateRequest) -> JSONResponse:
    """Create a new resource group."""
    ret = get_db().create_resource_group(
        req.id,
        name=req.name,
        description=req.description,
        entries=req.entries,
        method=req.method,
        plugin_id=req.plugin_id,
    )
    if ret:
        return _error_response(ret)
    return JSONResponse(status_code=201, content={"status": "success"})


@router.patch("/{group_id}", dependencies=[Depends(guard)])
def update_resource_group(group_id: str, req: ResourceGroupUpdateRequest) -> JSONResponse:
    """Update an existing resource group."""
    ret = get_db().update_resource_group(
        group_id,
        name=req.name,
        description=req.description,
        entries=req.entries,
        plugin_id=req.plugin_id,
    )
    if ret:
        return _error_response(ret)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.delete("/{group_id}", dependencies=[Depends(guard)])
def delete_resource_group(group_id: str) -> JSONResponse:
    """Delete a resource group when it is not referenced by any setting."""
    ret = get_db().delete_resource_group(group_id)
    if ret:
        return _error_response(ret)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{group_id}/clone", dependencies=[Depends(guard)])
def clone_resource_group(group_id: str, req: ResourceGroupCloneRequest) -> JSONResponse:
    """Clone a resource group (e.g. a core group) into a new editable user group."""
    ret = get_db().clone_resource_group(group_id, req.id, name=req.name)
    if ret:
        return _error_response(ret)
    return JSONResponse(status_code=201, content={"status": "success"})
