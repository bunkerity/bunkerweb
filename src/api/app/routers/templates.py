from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db_methods.templates import TEMPLATE_ID_RULE, TEMPLATE_ID_RX  # type: ignore
from template_package import PACKAGE_FORMAT, parse_package  # type: ignore

from ..auth.guard import guard
from ..utils import get_db

router = APIRouter(prefix="/templates", tags=["templates"])


def _error_status(message: str) -> int:
    """The status a refusal from the templates DB methods answers with.

    Every message those methods return is a refusal of the REQUEST (read-only database, unknown
    or duplicate id, empty name, no step, invalid setting value, ...) except the one a failed
    commit produces. Listing the refusals instead -- the old hint list -- answered 500 for every
    message nobody had listed yet ("A template must contain at least one step", QA-UI H14).
    """
    if message.startswith("An error occurred while"):
        return 500
    if message == "Template not found":
        return 404
    # The ownership guard (`template_owner`): the request is fine, the target is not the UI's.
    if " is managed by " in message:
        return 409
    return 400


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


@router.get("/{template_id}/export", dependencies=[Depends(guard)])
def export_template(template_id: str) -> JSONResponse:
    """A template as a ``bunkerweb-template/1`` package, the body ``POST /templates/import`` takes.

    Any template exports, plugin-owned ones included: copying a core template is how it gets
    edited. Ownership (``plugin_id``, ``method``) is not part of the package -- an import is
    always the UI's.
    """
    details = get_db().get_template_details(template_id)
    if not details:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Template not found"})

    package = {
        "format": PACKAGE_FORMAT,
        "id": details["id"],
        "name": details["name"],
        "settings": {setting["key"]: setting["default"] for setting in details["settings"]},
        "steps": [
            {"title": step["title"], "subtitle": step["subtitle"], "settings": step["settings"], "configs": step["configs"]} for step in details["steps"]
        ],
        "configs": [{"type": config["type"], "name": config["name"], "data": config["data"]} for config in details["configs"]],
    }
    # Ids stored before the id rule existed may hold anything; never put one in a header.
    filename = template_id if TEMPLATE_ID_RX.fullmatch(template_id) else "template"
    return JSONResponse(status_code=200, content=package, headers={"Content-Disposition": f'attachment; filename="{filename}.bwtemplate.json"'})


@router.post("/import", dependencies=[Depends(guard)])
def import_template(package: Any = Body(...), replace: bool = False) -> JSONResponse:
    """Create a template from a ``bunkerweb-template/1`` package; with ``replace``, overwrite one.

    Only the UI's own templates are ever replaced: ``update_template`` refuses a plugin-owned
    or otherwise managed one (409). Without ``replace`` an existing id is a 409 and nothing
    changes. The package is validated structurally here and every setting against this build
    by ``create_template``/``update_template``, which refuse the whole template on any problem.
    """
    if not isinstance(package, dict):
        return JSONResponse(status_code=400, content={"status": "error", "message": "the package is not a JSON object"})
    data, problem = parse_package(package)
    if problem or data is None:
        return JSONResponse(status_code=400, content={"status": "error", "message": problem})

    db = get_db()
    template_id = data["id"]
    templates = db.get_templates()
    # The DB refuses a duplicate name too, but without saying which template holds it.
    holder = next((other for other, meta in templates.items() if other != template_id and meta.get("name") == data["name"]), None)
    if holder:
        return JSONResponse(status_code=409, content={"status": "error", "message": f"Template name {data['name']} is already used by template {holder}"})

    fields = {key: data[key] for key in ("name", "settings", "steps", "configs")}
    replaced = template_id in templates
    if not replaced:
        ret = db.create_template(template_id, method="ui", **fields)
    elif not replace:
        return JSONResponse(status_code=409, content={"status": "error", "message": f"Template {template_id} already exists"})
    else:
        ret = db.update_template(template_id, **fields)
    if ret:
        return JSONResponse(status_code=_error_status(ret), content={"status": "error", "message": ret})
    return JSONResponse(status_code=200 if replaced else 201, content={"status": "success", "id": template_id, "replaced": replaced})


@router.post("", dependencies=[Depends(guard)])
def create_template(req: TemplateCreateRequest) -> JSONResponse:
    """Create a new template."""
    # Same rule as the DB method, checked before it is reached: the id ends up in USE_TEMPLATE.
    if not TEMPLATE_ID_RX.fullmatch(req.id.strip()):
        return JSONResponse(status_code=400, content={"status": "error", "message": TEMPLATE_ID_RULE})
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
        return JSONResponse(status_code=_error_status(ret), content={"status": "error", "message": ret})
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
        return JSONResponse(status_code=_error_status(ret), content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})


@router.delete("/{template_id}", dependencies=[Depends(guard)])
def delete_template(template_id: str) -> JSONResponse:
    """Delete a template."""
    ret = get_db().delete_template(template_id)
    if ret:
        return JSONResponse(status_code=_error_status(ret), content={"status": "error", "message": ret})
    return JSONResponse(status_code=200, content={"status": "success"})
