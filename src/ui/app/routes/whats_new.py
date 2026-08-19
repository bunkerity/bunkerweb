#!/usr/bin/env python3
"""What changed since the version this user last saw.

Two surfaces, one source: a modal raised once after an upgrade, and a permanent page so
dismissing the modal loses nothing. Both read the `CHANGELOG.md` bundled in the image.

The stamp is per user and lives in the same per-user KV as the walkthrough, reached through the
API — `app.dependencies.DB` is a `None` shim and `src/ui/CLAUDE.md` bans importing it. Writes
never carry a username: the route always stamps `current_user`.
"""

from traceback import format_exc

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, DATA
from app.models.changelog import PREFERENCE_KEY, load, releases_between
from app.routes.utils import cors_required
from app.utils import LOGGER

whats_new = Blueprint("whats_new", __name__)


def _running_version() -> str:
    try:
        return API_CLIENT.get_metadata().get("version", "")
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.debug(f"What's new: version unavailable: {exc}")
        return ""


@whats_new.route("/whats-new", methods=["GET"])
@login_required
def whats_new_page():
    """Every release, newest first. Deliberately not filtered by what this user has seen: the
    point of a permanent page is that nothing here is consumed by reading it."""
    releases = load()
    return render_template("whats_new.html", releases=releases, changelog_missing=not releases)


@whats_new.route("/whats-new/state", methods=["PATCH"])
@login_required
@cors_required
def update_whats_new_state():
    """Stamp the running version as seen. The modal calls this when it is closed."""
    version = (request.get_json(silent=True) or {}).get("version") or _running_version()
    if not version:
        return jsonify({"status": "error", "message": "Unknown running version"}), 503

    # Say so rather than pretending: on a read-only database the modal would otherwise vanish
    # and come back on the next login, with no explanation.
    if DATA.get("READONLY_MODE", False):
        return jsonify({"status": "success", "saved": False, "message": "The database is read-only, this was not saved"})

    try:
        API_CLIENT.update_user_preferences(current_user.get_id(), PREFERENCE_KEY, {"last_seen_version": version})
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.error(f"Couldn't stamp the what's-new version for {current_user.get_id()}: {exc}")
        return jsonify({"status": "error", "message": "Could not save"}), 502
    except BaseException as exc:  # noqa: B902 — a failed stamp must not 500 the page it sits on
        LOGGER.debug(format_exc())
        LOGGER.error(f"Couldn't stamp the what's-new version for {current_user.get_id()}: {exc}")
        return jsonify({"status": "error", "message": "Could not save"}), 502

    # The flag is cached per session; without this the modal returns on the next page render.
    session["whatsnew_pending"] = False
    return jsonify({"status": "success", "saved": True, "version": version})


def pending_releases(username: str, running: str):
    """(releases_to_show, stored_version) for this user, applying the silent-stamp rule.

    **A missing key stamps and shows nothing.** Without that, the day this ships every existing
    user is met with a modal containing the entire history — 90 releases of it. Same for a
    downgrade: running older than stored shows nothing and re-stamps, since the interval is
    empty by construction.
    """
    try:
        blob = API_CLIENT.get_user_preferences(username, PREFERENCE_KEY) or {}
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.debug(f"What's new: preferences unavailable: {exc}")
        return (), ""
    except BaseException as exc:  # noqa: B902 — this runs on every page render; it may not raise
        LOGGER.debug(format_exc())
        LOGGER.warning(f"What's new: preferences failed for {username}: {exc}")
        return (), ""

    stored = blob.get("last_seen_version") if isinstance(blob, dict) else None
    if not stored:
        if not DATA.get("READONLY_MODE", False) and running:
            try:
                API_CLIENT.update_user_preferences(username, PREFERENCE_KEY, {"last_seen_version": running})
            except BaseException as exc:  # noqa: B902 — worst case it stamps on the next visit
                LOGGER.debug(f"What's new: silent stamp failed for {username}: {exc}")
        return (), ""

    return releases_between(load(), stored, running), stored
