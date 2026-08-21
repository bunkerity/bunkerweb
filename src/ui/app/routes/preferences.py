#!/usr/bin/env python3
"""Per-user comfort preferences for the dashboard (#3820).

Three things the operator can now decide for themselves, all stored in the existing
``bw_ui_user_preferences`` key/value table — no model change, no migration:

* ``dismissed_notices``  -- "I know about 2FA / I already subscribed", per user.
* ``hidden_home_cards``  -- Home cards the user does not want to see.
* ``theme_mode``         -- ``light`` / ``dark`` / ``system`` (written by ``/set_theme``,
                            read here so one module owns the key names).

Storage goes through the API like everything else the UI persists (``app.dependencies.DB`` is a
``None`` shim and ``src/ui/CLAUDE.md`` bans importing it), using the same
``get_user_preferences`` / ``update_user_preferences`` pair the walkthrough and the column
preferences already use. Writes never carry a username: the route always stamps
``current_user``, so no account can write another's blob.

Dismissing is not disabling. The default is "show it", the preference is per user (a new
account sees the reminder again), and the MFA state stays visible in the profile and in the
guided walkthrough — this only stops the repetition for someone who has already decided.
"""

from flask import Blueprint, jsonify, request, session
from flask_login import current_user, login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, DATA
from app.routes.utils import cors_required
from app.utils import LOGGER

preferences = Blueprint("preferences", __name__)

DISMISSED_NOTICES_KEY = "dismissed_notices"
HIDDEN_CARDS_KEY = "hidden_home_cards"
THEME_MODE_KEY = "theme_mode"

# Closed set: an unchecked notice id lets a crafted request grow the blob without bound.
DISMISSIBLE_NOTICES = frozenset({"mfa", "newsletter"})

# Same reasoning for card ids, and it is also what makes "a card that leaves the product" and
# "a card added later" safe: an unknown id is ignored on read, so a stale entry hides nothing
# and a new card is visible by default.
HIDEABLE_HOME_CARDS = frozenset(
    {
        "home-card-timeseries",
        "home-card-status-codes",
        "home-card-top-reasons",
        "home-card-world-map",
        "home-card-blocking",
        "home-card-news",
    }
)

# Session keys mirroring the three blobs, so a page render costs no API call. Every write route
# below clears the one it touched; without that the user's own change would not show until the
# session ended.
SESSION_KEYS = {DISMISSED_NOTICES_KEY: "bw_dismissed_notices", HIDDEN_CARDS_KEY: "bw_hidden_home_cards", THEME_MODE_KEY: "bw_theme_mode"}


def load_preference(username, key, default):
    """Read one preference blob. Any failure returns the default: a preference the UI cannot
    reach must degrade to "show everything", never to a broken page."""
    try:
        stored = API_CLIENT.get_user_preferences(username, key)
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.debug(f"Preference '{key}' unavailable for {username}: {exc}")
        return default
    except Exception as exc:  # one unreadable preference is not a broken page
        LOGGER.warning(f"Preference '{key}' failed for {username}: {exc}")
        return default
    return stored if isinstance(stored, dict) and stored else default


def dismissed_notices(username):
    """``{"mfa": bool, "newsletter": bool}`` — absent means "not dismissed"."""
    blob = load_preference(username, DISMISSED_NOTICES_KEY, {})
    return {notice: bool(blob.get(notice)) for notice in DISMISSIBLE_NOTICES}


def hidden_home_cards(username):
    """The set of Home card ids to skip. Unknown ids are dropped, so a card that leaves the
    product stops mattering and one added later is visible by default."""
    blob = load_preference(username, HIDDEN_CARDS_KEY, {})
    stored = blob.get("ids")
    if not isinstance(stored, list):
        return []
    return sorted({card for card in stored if card in HIDEABLE_HOME_CARDS})


def theme_mode(username):
    """``light`` / ``dark`` / ``system``. Anything else is read as an explicit choice, which is
    what ``bw_ui_users.theme`` already holds — so a corrupt blob degrades to today's behaviour."""
    mode = load_preference(username, THEME_MODE_KEY, {}).get("mode")
    return mode if mode in ("light", "dark", "system") else None


def _persist(key, blob):
    """Write one blob back, invalidating its session cache. Returns a JSON response."""
    if DATA.get("READONLY_MODE", False):
        # Say so rather than pretending: the caller keeps its state and can tell the user.
        return jsonify({"status": "success", "saved": False, "message": "The database is read-only, this was not saved"})
    try:
        API_CLIENT.update_user_preferences(current_user.get_id(), key, blob)
    except (ApiClientError, ApiUnavailableError) as exc:
        LOGGER.error(f"Couldn't save '{key}' for {current_user.get_id()}: {exc}")
        return jsonify({"status": "error", "message": "Could not save"}), 502
    session.pop(SESSION_KEYS[key], None)
    return jsonify({"status": "success", "saved": True, "state": blob})


@preferences.route("/preferences/notice", methods=["POST"])
@login_required
@cors_required
def dismiss_notice():
    """Dismiss (or restore) one repeating notice for the current user."""
    body = request.get_json(silent=True) or request.form
    notice = body.get("notice")
    if notice not in DISMISSIBLE_NOTICES:
        return jsonify({"status": "error", "message": "Unknown notice"}), 400

    blob = dict(load_preference(current_user.get_id(), DISMISSED_NOTICES_KEY, {}))
    dismissed = body.get("dismissed", True)
    blob[notice] = dismissed not in (False, "false", "0", 0)
    return _persist(DISMISSED_NOTICES_KEY, blob)


@preferences.route("/preferences/home-cards", methods=["POST"])
@login_required
@cors_required
def set_home_cards():
    """Hide one Home card, or restore every hidden one.

    Hidden-by-default never happens: the stored list is what the user explicitly hid, so an
    empty blob (a new account, an unreachable API) shows the whole dashboard.
    """
    body = request.get_json(silent=True) or request.form
    hidden = set(hidden_home_cards(current_user.get_id()))

    if body.get("restore") in (True, "true", "1", 1):
        hidden = set()
    else:
        card = body.get("card")
        if card not in HIDEABLE_HOME_CARDS:
            return jsonify({"status": "error", "message": "Unknown card"}), 400
        if body.get("hidden", True) in (False, "false", "0", 0):
            hidden.discard(card)
        else:
            hidden.add(card)

    return _persist(HIDDEN_CARDS_KEY, {"ids": sorted(hidden)})
