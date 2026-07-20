from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/resource_groups", tags=["resource_groups"])

MAX_ENTRIES = 5000
MAX_VALUE_LENGTH = 8192
MAX_COMMENT_LENGTH = 1000
MAX_DESCRIPTION_LENGTH = 4000


# ── Schemas ─────────────────────────────────────────────────────────


class ResourceGroupEntryRequest(BaseModel):
    kind: Literal["ip", "country", "asn", "rdns", "user_agent", "uri"]
    value: str = Field(min_length=1, max_length=MAX_VALUE_LENGTH)
    comment: Optional[str] = Field(default=None, max_length=MAX_COMMENT_LENGTH)


class ResourceGroupCreateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    entries: List[ResourceGroupEntryRequest] = Field(default_factory=list, max_length=MAX_ENTRIES)


class ResourceGroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)
    entries: Optional[List[ResourceGroupEntryRequest]] = Field(default=None, max_length=MAX_ENTRIES)


class ResourceGroupCloneRequest(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


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


def _signal_config_reload(db: Any, action: str) -> Optional[JSONResponse]:
    """Mark every plugin config dirty after a group mutation.

    A group may be referenced by settings owned by several plugins, so a
    targeted reload is not sufficient. The mutation is already durable when
    this runs; report that explicitly if scheduling the reload fails so API
    clients do not mistake the outcome for an entirely rejected write.
    """
    if ret := db.checked_changes(["config"], plugins_changes="all", value=True):
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Resource group {action}, but the config reload could not be scheduled: {ret}",
                "persisted": True,
            },
        )
    return None


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(guard)])
def list_resource_groups(include_usage: bool = False) -> JSONResponse:
    """List all resource groups with their entries."""
    db = get_db()
    groups = db.get_resource_groups()
    references = db.get_resource_group_references() if include_usage else {}
    for data in groups.values():
        _serialize_dates(data)
    if include_usage:
        for group_id, data in groups.items():
            data["usage_count"] = len(references.get(group_id, []))
    return JSONResponse(status_code=200, content={"status": "success", "resource_groups": groups})


@router.get("/{group_id}", dependencies=[Depends(guard)])
def get_resource_group(group_id: str) -> JSONResponse:
    """Get a single resource group with its entries."""
    details = get_db().get_resource_group_details(group_id)
    if not details:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Resource group not found"})
    _serialize_dates(details)
    return JSONResponse(status_code=200, content={"status": "success", "resource_group": details})


@router.get("/{group_id}/references", dependencies=[Depends(guard)])
def get_resource_group_references(group_id: str) -> JSONResponse:
    """List global and service settings that reference a group."""
    db = get_db()
    if not db.get_resource_group_details(group_id):
        return JSONResponse(status_code=404, content={"status": "error", "message": "Resource group not found"})
    references = db.get_resource_group_references(group_id).get(group_id, [])
    return JSONResponse(status_code=200, content={"status": "success", "references": references})


@router.post("", dependencies=[Depends(guard)])
def create_resource_group(req: ResourceGroupCreateRequest) -> JSONResponse:
    """Create a new resource group."""
    db = get_db()
    ret = db.create_resource_group(
        req.id,
        name=req.name,
        description=req.description,
        entries=[entry.model_dump(exclude_none=True) for entry in req.entries],
        method="api",
    )
    if ret:
        return _error_response(ret)
    if response := _signal_config_reload(db, "was created"):
        return response
    return JSONResponse(status_code=201, content={"status": "success"})


@router.patch("/{group_id}", dependencies=[Depends(guard)])
def update_resource_group(group_id: str, req: ResourceGroupUpdateRequest) -> JSONResponse:
    """Update an existing resource group."""
    db = get_db()
    ret = db.update_resource_group(
        group_id,
        name=req.name,
        description=req.description,
        entries=None if req.entries is None else [entry.model_dump(exclude_none=True) for entry in req.entries],
    )
    if ret:
        return _error_response(ret)
    if response := _signal_config_reload(db, "was updated"):
        return response
    return JSONResponse(status_code=200, content={"status": "success"})


@router.delete("/{group_id}", dependencies=[Depends(guard)])
def delete_resource_group(group_id: str) -> JSONResponse:
    """Delete a resource group when it is not referenced by any setting."""
    db = get_db()
    ret = db.delete_resource_group(group_id)
    if ret:
        return _error_response(ret)
    if response := _signal_config_reload(db, "was deleted"):
        return response
    return JSONResponse(status_code=200, content={"status": "success"})


@router.post("/{group_id}/clone", dependencies=[Depends(guard)])
def clone_resource_group(group_id: str, req: ResourceGroupCloneRequest) -> JSONResponse:
    """Clone a resource group (e.g. a core group) into a new editable user group."""
    db = get_db()
    ret = db.clone_resource_group(group_id, req.id, name=req.name)
    if ret:
        return _error_response(ret)
    if response := _signal_config_reload(db, "was cloned"):
        return response
    return JSONResponse(status_code=201, content={"status": "success"})
