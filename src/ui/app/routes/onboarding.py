#!/usr/bin/env python3
"""Guided-walkthrough state: what the current user still has to do, and what it dismissed.

The catalog lives in `app.models.onboarding` and owns every step. This blueprint only builds
the signals dict completion is derived from, and reads/writes the per-user blob.

Storage goes through the API like everything else the UI persists: `app.dependencies.DB` is a
`None` shim and `src/ui/CLAUDE.md` bans importing it, so the key/value store is reached with
the same `get_user_preferences` / `update_user_preferences` pair `/set_columns_preferences`
already uses. Writes never carry a username — the route always stamps `current_user`, so no
account can write another's blob.
"""

from time import time
from traceback import format_exc

from flask import Blueprint, jsonify, request, session, url_for
from flask_login import current_user, login_required
from werkzeug.routing import BuildError

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, DATA
from app.models.onboarding import HINT_PAGE_IDS, PREFERENCE_KEY, is_complete, progress, resolve_track, visible_steps
from app.routes.utils import cors_required
from app.utils import LOGGER

onboarding = Blueprint("onboarding", __name__)

_BLANK = {"opened_at": None, "dismissed_at": None, "completed_at": None, "acked_hints": []}


def _guarded(label, default, call, *args, **kwargs):
    """Run one signal call. A failure leaves its step pending rather than erroring the page —
    an unreachable certificates endpoint must not hide the other six steps."""
    try:
        return call(*args, **kwargs)
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.debug(f"Onboarding signal '{label}' unavailable: {exc}")
        return default
    except BaseException as exc:  # noqa: B902 — same rule, one bad signal is not a broken page
        LOGGER.debug(format_exc())
        LOGGER.warning(f"Onboarding signal '{label}' failed: {exc}")
        return default


def _load_blob():
    stored = _guarded("preferences", {}, API_CLIENT.get_user_preferences, current_user.get_id(), PREFERENCE_KEY)
    blob = dict(_BLANK)
    if isinstance(stored, dict):
        blob.update(stored)
    # A crafted or corrupted blob must not make the catalog blow up on `in`.
    if not isinstance(blob.get("acked_hints"), list):
        blob["acked_hints"] = []
    return blob


def _collect_signals(blob):
    metadata = _guarded("metadata", {}, API_CLIENT.get_metadata)
    certificates = _guarded("certificates", {}, API_CLIENT.get_certificates, limit=1)
    blocks = _guarded("blocks", {}, API_CLIENT.get_metrics_requests, length=1, count_only=True)

    # `workflows_available` is the call succeeding, not a manifest lookup: what the step needs
    # to know is whether the user can actually reach the page, and that is the same question.
    workflows = _guarded("workflows", None, API_CLIENT.get_workflows, limit=1)

    return {
        "is_initialized": metadata.get("is_initialized", False),
        "first_config_saved": metadata.get("first_config_saved", False),
        "is_pro": metadata.get("is_pro", False),
        "instances": len(_guarded("instances", [], API_CLIENT.get_instances)),
        "services": len(_guarded("services", [], API_CLIENT.get_services, with_drafts=True)),
        "certificates_total": certificates.get("total", 0),
        "blocks_total": blocks.get("total", 0),
        "workflows_total": (workflows or {}).get("total", 0),
        "workflows_available": workflows is not None,
        "mfa": getattr(current_user, "totp_secret", None),
        "acked_hints": blob["acked_hints"],
    }


def _serialize(step, signals):
    """A step with an unbuildable target is dropped, not rendered pointing at nothing: the
    workflows blueprint can be pulled out from under us by the plugin machinery."""
    try:
        target = url_for(step.endpoint)
    except BuildError:
        LOGGER.debug(f"Onboarding step '{step.id}' dropped: endpoint '{step.endpoint}' does not resolve")
        return None
    return {
        "id": step.id,
        "i18n_key": step.i18n_key,
        "en": step.en,
        "done": bool(step.done(signals)),
        "optional": step.optional,
        "target": target,
        "anchor": step.anchor,
    }


@onboarding.route("/onboarding/state", methods=["GET"])
@login_required
@cors_required
def onboarding_state():
    blob = _load_blob()
    signals = _collect_signals(blob)
    track = resolve_track(admin=bool(current_user.admin), readonly="write" not in current_user.list_permissions)

    steps = visible_steps(track, signals)
    payload = [entry for entry in (_serialize(step, signals) for step in steps) if entry]
    done, total = progress(steps, signals)

    return jsonify(
        {
            "status": "success",
            "track": track,
            "steps": payload,
            "done": done,
            "total": total,
            "completed": is_complete(steps, signals),
            "dismissed": bool(blob["dismissed_at"]),
            "opened": bool(blob["opened_at"]),
            "acked_hints": blob["acked_hints"],
        }
    )


@onboarding.route("/onboarding/state", methods=["PATCH"])
@login_required
@cors_required
def update_onboarding_state():
    body = request.get_json(silent=True) or {}
    blob = _load_blob()
    now = int(time())
    changed = False

    if body.get("dismissed"):
        blob["dismissed_at"], changed = now, True
    if body.get("opened"):
        blob["opened_at"], changed = now, True
    if body.get("completed"):
        blob["completed_at"], changed = now, True
    if body.get("restart"):
        # Profile's "Restart walkthrough": clearing both stamps is the whole feature.
        blob["dismissed_at"], blob["completed_at"], changed = None, None, True

    hint = body.get("ack_hint")
    if hint is not None:
        # Validated against the catalog's own ids: the blob is compared against them later,
        # and an unchecked value lets a crafted request grow it without bound.
        if hint not in HINT_PAGE_IDS:
            return jsonify({"status": "error", "message": "Unknown hint"}), 400
        if hint not in blob["acked_hints"]:
            blob["acked_hints"] = sorted(blob["acked_hints"] + [hint])
            changed = True

    if not changed:
        return jsonify({"status": "success", "saved": False, "message": "Nothing to change"})

    # Say so rather than pretending: the caller keeps its tab-local state and can tell the user.
    if DATA.get("READONLY_MODE", False):
        return jsonify({"status": "success", "saved": False, "message": "The database is read-only, this was not saved"})

    try:
        API_CLIENT.update_user_preferences(current_user.get_id(), PREFERENCE_KEY, blob)
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.error(f"Couldn't save the onboarding state for {current_user.get_id()}: {exc}")
        return jsonify({"status": "error", "message": "Could not save"}), 502

    # The chrome flag is cached per session; a state change has to invalidate it or the
    # pill survives its own dismissal until the user logs out.
    session["onboarding_active"] = not (blob["dismissed_at"] or blob["completed_at"])

    return jsonify({"status": "success", "saved": True, "state": blob})
