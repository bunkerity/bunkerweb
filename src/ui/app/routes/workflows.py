from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.routes.utils import cors_required
from app.utils import flash

workflows = Blueprint("workflows", __name__)

MAX_SERVICES = 100


def _redirect():
    return redirect(url_for("workflows.workflows_page"))


def _readonly():
    if not API_CLIENT.readonly:
        return False
    flash("Database is in read-only mode", "error")
    return True


def _services():
    values = list(dict.fromkeys(value.strip() for value in request.form.getlist("service_ids") if value.strip()))
    if len(values) > MAX_SERVICES:
        raise ValueError(f"A workflow cannot be attached to more than {MAX_SERVICES} services")
    return values


def _identity(*, required=True):
    """Read the name/description fields. ``required=False`` returns only what was submitted."""
    payload = {}
    name = (request.form.get("name") or "").strip()
    if name:
        payload["name"] = name
    elif required:
        raise ValueError("The workflow name is required")

    # Keyed on presence, not truthiness: the edit modal always submits the textarea, so an
    # emptied description must reach the API as "" instead of being silently dropped.
    if "description" in request.form or required:
        description = (request.form.get("description") or "").strip()
        if len(description) > 4000:
            raise ValueError("The description cannot exceed 4000 characters")
        payload["description"] = description
    return payload


@workflows.route("/workflows", methods=["GET"])
@login_required
def workflows_page():
    try:
        result = API_CLIENT.get_workflows(limit=500)
        rows = result.get("workflows", [])
        total = result.get("total", len(rows))
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch workflows: {exc.message}", "error")
        rows, total = [], 0

    try:
        services = API_CLIENT.get_services(with_drafts=True)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch services for workflow assignments: {exc.message}", "error")
        services = []

    return render_template("workflows.html", workflows=rows, total=total, truncated=total > len(rows), services=services)


@workflows.route("/workflows/<string:workflow_id>", methods=["GET"])
@login_required
def workflows_editor(workflow_id):
    try:
        workflow = API_CLIENT.get_workflow(workflow_id)
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch the workflow: {exc.message}", "error")
        return _redirect()

    try:
        # Only groups holding a kind a rule can evaluate are offered, so the editor cannot
        # build a reference the validator would refuse.
        groups = API_CLIENT.get_resource_groups()
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not fetch resource groups: {exc.message}", "error")
        groups = {}

    return render_template("workflow_editor.html", workflow=workflow, groups=groups)


@workflows.route("/workflows/create", methods=["POST"])
@login_required
def workflows_create():
    if _readonly():
        return _redirect()
    try:
        payload = _identity()
        payload["service_ids"] = _services()
        API_CLIENT.create_workflow(**payload)
        flash(f"Workflow {payload['name']} created successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not create the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/update", methods=["POST"])
@login_required
def workflows_update():
    if _readonly():
        return _redirect()
    workflow_id = (request.form.get("workflow_id") or "").strip()
    if not workflow_id:
        flash("The workflow is required", "error")
        return _redirect()
    try:
        API_CLIENT.update_workflow(workflow_id, **_identity(required=False))
        flash("Workflow updated successfully")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not update the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/clone", methods=["POST"])
@login_required
def workflows_clone():
    if _readonly():
        return _redirect()
    workflow_id = (request.form.get("workflow_id") or "").strip()
    name = (request.form.get("name") or "").strip()
    if not workflow_id or not name:
        flash("The workflow and the new name are required", "error")
        return _redirect()
    try:
        API_CLIENT.clone_workflow(workflow_id, name)
        flash(f"Workflow cloned as {name}")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not clone the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/delete", methods=["POST"])
@login_required
def workflows_delete():
    if _readonly():
        return _redirect()
    workflow_id = (request.form.get("workflow_id") or "").strip()
    if not workflow_id:
        flash("The workflow is required", "error")
        return _redirect()
    try:
        API_CLIENT.delete_workflow(workflow_id)
        flash("Workflow deleted successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        # A workflow still attached to a service is refused by the API on purpose: detaching
        # is the operator's decision, not a side effect of a delete.
        flash(f"Could not delete the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/attach", methods=["POST"])
@login_required
def workflows_attach():
    if _readonly():
        return _redirect()
    workflow_id = (request.form.get("workflow_id") or "").strip()
    try:
        if not workflow_id:
            raise ValueError("The workflow is required")
        service_ids = _services()
        workflow = API_CLIENT.get_workflow(workflow_id)
        attached = set(workflow.get("services", []))
        selected = set(service_ids)
        for service_id in sorted(selected - attached):
            API_CLIENT.attach_workflow(workflow_id, service_id)
        for service_id in sorted(attached - selected):
            API_CLIENT.detach_workflow(workflow_id, service_id)
        flash(f"Workflow services updated ({len(selected)} attached)")
    except ValueError as exc:
        flash(str(exc), "error")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not attach the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/detach", methods=["POST"])
@login_required
def workflows_detach():
    if _readonly():
        return _redirect()
    workflow_id = (request.form.get("workflow_id") or "").strip()
    service_id = (request.form.get("service_id") or "").strip()
    if not workflow_id or not service_id:
        flash("The workflow and the service are required", "error")
        return _redirect()
    try:
        API_CLIENT.detach_workflow(workflow_id, service_id)
        flash("Workflow detached successfully")
    except (ApiClientError, ApiUnavailableError) as exc:
        flash(f"Could not detach the workflow: {exc.message}", "error")
    return _redirect()


@workflows.route("/workflows/<string:workflow_id>/test", methods=["POST"])
@login_required
@cors_required
def workflows_test(workflow_id):
    """Answers "would this rule fire?" for the editor's drawer. Stores nothing."""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload.get("request"), dict):
        return jsonify({"status": "error", "message": "A request object is required"}), 400
    try:
        return jsonify(API_CLIENT.test_workflow(workflow_id, payload))
    except (ApiClientError, ApiUnavailableError) as exc:
        return jsonify({"status": "error", "message": exc.message}), 502


@workflows.route("/workflows/<string:workflow_id>/validate", methods=["POST"])
@login_required
@cors_required
def workflows_validate(workflow_id):
    """Live check for the editor: proxies the API's validate-without-save, writes nothing."""
    definition = (request.get_json(silent=True) or {}).get("definition")
    if not isinstance(definition, dict):
        return jsonify({"status": "error", "message": "A definition object is required"}), 400
    try:
        return jsonify(API_CLIENT.validate_workflow(definition, workflow_id=workflow_id))
    except (ApiClientError, ApiUnavailableError) as exc:
        return jsonify({"status": "error", "message": exc.message}), 502


@workflows.route("/workflows/<string:workflow_id>/save", methods=["POST"])
@login_required
@cors_required
def workflows_save(workflow_id):
    """Store the rules. The API re-validates: this endpoint never trusts the editor."""
    if API_CLIENT.readonly:
        return jsonify({"status": "error", "message": "Database is in read-only mode"}), 409
    definition = (request.get_json(silent=True) or {}).get("definition")
    if not isinstance(definition, dict):
        return jsonify({"status": "error", "message": "A definition object is required"}), 400
    try:
        API_CLIENT.save_workflow_definition(workflow_id, definition)
    except (ApiClientError, ApiUnavailableError) as exc:
        # Only the message survives the client's error type. That is enough here: the editor
        # validates on every change through /validate, which answers 200 with the errors
        # anchored on their nodes, so a save only fails on a race or a stale draft.
        return jsonify({"status": "error", "message": exc.message}), 400
    # No flash: this is an XHR endpoint, so the message would sit in the session and ambush the
    # operator on whatever page they opened next. The editor announces the save in place.
    return jsonify({"status": "success"})
