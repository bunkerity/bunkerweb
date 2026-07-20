from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/templates", tags=["templates"])


# ── Schemas ─────────────────────────────────────────────────────────


class TemplateCreateRequest(BaseModel):
    id: str
    name: str
    plugin_id: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    configs: Optional[List[Dict[str, Any]]] = None
    method: str = "ui"


class TemplateUpdateRequest(BaseModel):
    plugin_id: Optional[str] = None
    name: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    configs: Optional[List[Dict[str, Any]]] = None


# ── Endpoints ───────────────────────────────────────────────────────


@router.get("", dependencies=[Depends(guard)])
def list_templates() -> JSONResponse:
    """List all templates with their settings, configs, and steps."""
    templates = get_db().get_templates()

    # Serialize datetime fields
    for _tid, tdata in templates.items():
        if hasattr(tdata.get("creation_date"), "isoformat"):
            tdata["creation_date"] = tdata["creation_date"].isoformat()
        if hasattr(tdata.get("last_update"), "isoformat"):
            tdata["last_update"] = tdata["last_update"].isoformat()

    return JSONResponse(status_code=200, content={"status": "success", "templates": templates})


@router.get("/{template_id}", dependencies=[Depends(guard)])
def get_template(template_id: str) -> JSONResponse:
    """Get template details including settings, steps, and configs."""
    details = get_db().get_template_details(template_id)
    if not details:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": "Template not found"},
        )

    # Serialize datetime fields
    if hasattr(details.get("creation_date"), "isoformat"):
        details["creation_date"] = details["creation_date"].isoformat()
    if hasattr(details.get("last_update"), "isoformat"):
        details["last_update"] = details["last_update"].isoformat()

    return JSONResponse(status_code=200, content={"status": "success", "template": details})


@router.post("", dependencies=[Depends(guard)])
def create_template(req: TemplateCreateRequest) -> JSONResponse:
    """Create a new template."""
    ret = get_db().create_template(
        req.id,
        plugin_id=req.plugin_id,
        name=req.name,
        settings=req.settings,
        steps=req.steps,
        configs=req.configs,
        method=req.method,
    )
    if ret:
        code = (
            400
            if any(
                hint in ret.lower()
                for hint in (
                    "already exists",
                    "read-only",
                    "required",
                    "cannot be empty",
                    "resource group",
                )
            )
            else 500
        )
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=201, content={"status": "success"})


@router.patch("/{template_id}", dependencies=[Depends(guard)])
def update_template(template_id: str, req: TemplateUpdateRequest) -> JSONResponse:
    """Update an existing template."""
    ret = get_db().update_template(
        template_id,
        plugin_id=req.plugin_id,
        name=req.name,
        settings=req.settings,
        steps=req.steps,
        configs=req.configs,
    )
    if ret:
        code = 404 if "not found" in ret else (400 if "read-only" in ret.lower() or "resource group" in ret.lower() else 500)
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.delete("/{template_id}", dependencies=[Depends(guard)])
def delete_template(template_id: str) -> JSONResponse:
    """Delete a template."""
    ret = get_db().delete_template(template_id)
    if ret:
        code = 404 if "not found" in ret else (400 if "read-only" in ret or "currently used" in ret else 500)
        return JSONResponse(status_code=code, content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})
