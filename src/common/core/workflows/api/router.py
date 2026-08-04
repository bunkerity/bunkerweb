#!/usr/bin/env python3
"""API router for security workflows, mounted at /workflows (guard injected by the loader).

Shipped inside the plugin rather than in ``src/api/app/routers/`` because the mount prefix
is locked to ``/<plugin_id>``: naming the plugin ``workflows`` is what gives this the typed
``/workflows`` path the design calls for, with no core router to keep in sync.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.utils import get_db  # type: ignore
from workflow_schema import summarize_rule  # type: ignore

from .schemas import (
    WorkflowAttachmentRequest,
    WorkflowCloneRequest,
    WorkflowCreateRequest,
    WorkflowDefinitionRequest,
    WorkflowUpdateRequest,
    WorkflowValidateRequest,
)

router = APIRouter(tags=["workflows"])


def _error(message: str, default: int = 400, field_errors=None) -> JSONResponse:
    # The status is inferred from the message text, which only holds because every message
    # db_methods/workflows.py returns is an English literal built there. Translating those
    # would silently change these status codes: translate in the UI, never in the mixin.
    if "not found" in message.lower():
        default = 404
    elif "read-only" in message.lower():
        default = 409
    elif "already exists" in message.lower() or "attached to a service" in message.lower():
        default = 409
    content = {"status": "error", "message": message}
    if field_errors:
        # The editor anchors each entry on the node its ``path`` addresses.
        content["errors"] = field_errors
    return JSONResponse(status_code=default, content=content)


@router.get("")
def list_workflows(
    search: str = "",
    service_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> JSONResponse:
    result = get_db().get_workflows(search=search, service_id=service_id, offset=offset, limit=limit)
    return JSONResponse(
        status_code=200, content={"status": "success", "workflows": result["items"], **{key: result[key] for key in ("total", "offset", "limit")}}
    )


@router.post("/validate")
def validate_workflow(payload: WorkflowValidateRequest) -> JSONResponse:
    """Validate a draft without saving it — what the editor calls on every change.

    Writes nothing, so it is a read permission. Returns the canonical form the save would
    store plus a human summary per rule, which is what the editor shows before saving.
    """
    canonical, errors = get_db().validate_workflow_definition(payload.definition, resource_id=payload.workflow_id, service_ids=payload.service_ids)
    if canonical is None or errors:
        # Budget and provider refusals arrive here as anchored triplets too, so what the editor
        # reports as valid is exactly what the save accepts.
        return JSONResponse(status_code=200, content={"status": "success", "valid": False, "errors": errors})
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "valid": True,
            "definition": canonical,
            "summaries": [{"id": rule["id"], "summary": summarize_rule(rule)} for rule in canonical["rules"]],
        },
    )


@router.post("")
def create_workflow(payload: WorkflowCreateRequest) -> JSONResponse:
    db = get_db()
    resource_id, error = db.create_workflow(name=payload.name, description=payload.description, definition=payload.definition)
    if error:
        return _error(error)

    for service_id in payload.service_ids:
        if attach_error := db.attach_workflow(resource_id, service_id):
            # All-or-nothing, as for redirects: a policy attached to only some of the
            # requested services is a half-applied mutation the caller cannot see.
            for attached in payload.service_ids:
                db.detach_workflow(resource_id, attached)
            db.delete_workflow(resource_id)
            return _error(attach_error)

    return JSONResponse(status_code=201, content={"status": "success", "workflow": db.get_workflow_details(resource_id)})


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str) -> JSONResponse:
    workflow = get_db().get_workflow_details(workflow_id)
    if workflow is None:
        return _error("Workflow not found", 404)
    return JSONResponse(status_code=200, content={"status": "success", "workflow": workflow})


@router.patch("/{workflow_id}")
def update_workflow(workflow_id: str, payload: WorkflowUpdateRequest) -> JSONResponse:
    db = get_db()
    if error := db.update_workflow(workflow_id, **payload.model_dump(exclude_unset=True)):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "workflow": db.get_workflow_details(workflow_id)})


@router.delete("/{workflow_id}")
def delete_workflow(workflow_id: str) -> JSONResponse:
    if error := get_db().delete_workflow(workflow_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success"})


@router.get("/{workflow_id}/definition")
def get_workflow_definition(workflow_id: str) -> JSONResponse:
    workflow = get_db().get_workflow_details(workflow_id)
    if workflow is None:
        return _error("Workflow not found", 404)
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "definition": workflow["definition"],
            "summaries": [{"id": rule["id"], "summary": summarize_rule(rule)} for rule in workflow["definition"].get("rules", [])],
        },
    )


@router.put("/{workflow_id}/definition")
def save_workflow_definition(workflow_id: str, payload: WorkflowDefinitionRequest) -> JSONResponse:
    db = get_db()
    error, field_errors = db.save_workflow_definition(workflow_id, payload.definition)
    if error:
        return _error(error, field_errors=field_errors)
    return JSONResponse(status_code=200, content={"status": "success", "workflow": db.get_workflow_details(workflow_id)})


@router.post("/{workflow_id}/clone")
def clone_workflow(workflow_id: str, payload: WorkflowCloneRequest) -> JSONResponse:
    db = get_db()
    new_id, error = db.clone_workflow(workflow_id, name=payload.name)
    if error:
        return _error(error)
    return JSONResponse(status_code=201, content={"status": "success", "workflow": db.get_workflow_details(new_id)})


@router.post("/{workflow_id}/attachments")
def attach_workflow(workflow_id: str, payload: WorkflowAttachmentRequest) -> JSONResponse:
    db = get_db()
    if error := db.attach_workflow(workflow_id, payload.service_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "workflow": db.get_workflow_details(workflow_id)})


@router.delete("/{workflow_id}/attachments/{service_id}")
def detach_workflow(workflow_id: str, service_id: str) -> JSONResponse:
    db = get_db()
    if error := db.detach_workflow(workflow_id, service_id):
        return _error(error)
    return JSONResponse(status_code=200, content={"status": "success", "workflow": db.get_workflow_details(workflow_id)})
