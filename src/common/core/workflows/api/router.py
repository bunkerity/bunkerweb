#!/usr/bin/env python3
"""API router for security workflows, mounted at /workflows (guard injected by the loader).

Shipped inside the plugin rather than in ``src/api/app/routers/`` because the mount prefix
is locked to ``/<plugin_id>``: naming the plugin ``workflows`` is what gives this the typed
``/workflows`` path the design calls for, with no core router to keep in sync.
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.utils import get_db  # type: ignore
from workflow_eval import assumptions, evaluate, prepare_ladder, request_from_input  # type: ignore
from workflow_schema import service_setting, summarize_rule, uses_crowdsec  # type: ignore

from .schemas import (
    WorkflowAttachmentRequest,
    WorkflowCloneRequest,
    WorkflowCreateRequest,
    WorkflowDefinitionRequest,
    WorkflowTestRequest,
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


def _crowdsec_warnings(definition, service_ids, workflow_id: str = "") -> list:
    """Non-blocking notices for a draft that reads a CrowdSec verdict on a service without CrowdSec.

    Mirrors the compiler's warning so the operator meets it in the editor, at save time, instead
    of in the scheduler log after a push. Nothing is refused: the leaf evaluates UNKNOWN there,
    which can never make a rule match. The lookup is skipped entirely for the overwhelming
    majority of drafts, which hold no CrowdSec condition at all, and asks the database for the
    single setting it needs.
    """
    if not uses_crowdsec(definition):
        return []
    if not service_ids:
        # The editor validates a draft of ONE workflow and does not send its attachments, so
        # they are resolved here rather than making every caller carry them. One row, and only
        # for the rare draft that reads a CrowdSec verdict at all.
        details = get_db().get_workflow_details(workflow_id) if workflow_id else None
        service_ids = (details or {}).get("services") or []
    if not service_ids:
        return []
    config = get_db().get_config(methods=False, with_drafts=True, filtered_settings=("USE_CROWDSEC", "CROWDSEC_DEFER_TO_WORKFLOWS"))
    # Only a `ban` leaf: a `captcha` reaches the workflows through the antibot-delegation arm
    # (crowdsec.lua) whatever CROWDSEC_DEFER_TO_WORKFLOWS says, while a ban ends the access phase
    # in CrowdSec unless the service defers. Mirrors the compiler's second warning.
    bans = uses_crowdsec(definition, field="remediation", value="ban")
    warnings = []
    for service_id in service_ids:
        if service_setting(config, service_id, "USE_CROWDSEC") != "yes":
            warnings.append(
                {
                    "code": "crowdsec_disabled",
                    "service": service_id,
                    "message": f"This workflow reads a CrowdSec verdict, but USE_CROWDSEC is not yes on {service_id}: those conditions can never match there.",
                }
            )
        elif bans and service_setting(config, service_id, "CROWDSEC_DEFER_TO_WORKFLOWS") != "yes":
            warnings.append(
                {
                    "code": "crowdsec_defer_disabled",
                    "service": service_id,
                    "message": f"This workflow matches a CrowdSec ban, but CROWDSEC_DEFER_TO_WORKFLOWS is not yes on {service_id}: "
                    "CrowdSec applies the ban itself before the workflows run, so those conditions can never match there.",
                }
            )
    return warnings


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
            "warnings": _crowdsec_warnings(canonical, payload.service_ids, payload.workflow_id),
        },
    )


@router.post("/{workflow_id}/test")
def test_workflow(workflow_id: str, payload: WorkflowTestRequest) -> JSONResponse:
    """Evaluate a candidate against a synthetic request. Writes nothing, so it is a read.

    The whole service ladder is evaluated, not just this workflow: "is my new rule shadowed?"
    is the question operators actually have, and the rule doing the shadowing is often in a
    different workflow attached to the same service.
    """
    request, error = request_from_input(payload.request.model_dump())
    if error:
        return _error(error, field_errors=[{"path": "request", "code": "request_invalid", "message": error}])

    context, errors = get_db().test_workflow_definition(workflow_id, definition=payload.definition, service_id=payload.service_id)
    if context is None:
        if errors and errors[0].get("code") == "not_found":
            return _error(errors[0]["message"])
        # A draft that does not validate comes back in the same shape /validate uses, so the
        # editor paints it with the code it already has.
        return JSONResponse(status_code=200, content={"status": "success", "valid": False, "errors": errors})

    service = context["service"]
    if service is None:
        return JSONResponse(
            status_code=200,
            content={"status": "success", "valid": True, "outcome": {"type": "not_attached"}, "service": None, "assumptions": [], "workflows": []},
        )
    if service["is_draft"]:
        return JSONResponse(
            status_code=200,
            content={"status": "success", "valid": True, "outcome": {"type": "service_draft"}, "service": service, "assumptions": [], "workflows": []},
        )

    ladder = prepare_ladder(context["workflows"], context["group_index"])
    outcome, reported = evaluate(ladder, request)
    if outcome.get("type") == "match":
        # The rule may carry no status of its own, in which case the instance's deny status is
        # what the client actually sees.
        outcome["effective_status"] = outcome["action"].get("status") or service["deny_status"]
        outcome["enforced"] = service["security_mode"] == "block"

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "valid": True,
            "service": service,
            "assumptions": assumptions(request, ladder),
            "outcome": outcome,
            "workflows": reported,
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
