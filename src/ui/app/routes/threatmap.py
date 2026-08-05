from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import LOGGER

from app.routes.reports import _persist_to_db_enabled
from app.routes.utils import cors_required

threatmap = Blueprint("threatmap", __name__)

# Ticker length. The map draws an arc per recent event, so this also bounds how many arcs can be
# in flight at once; the API clamps anything larger.
RECENT_LIMIT = 50

# How many rows each top-N panel can expand to. The panels show five until an operator asks for
# more, but the payload has to be bounded up front: one row per distinct service means 5 000 rows
# on a large deployment, on every poll, to render five of them.
FACET_LIMIT = 25


@threatmap.route("/threatmap", methods=["GET"])
@login_required
def threatmap_page():
    """Shell only — the data arrives from ``/threatmap/data``, including the first paint.

    Rendering server-side would mean computing the window twice, in two timezones: the browser
    resolves "today" for every poll, and the server would have to guess for the first frame alone.
    One code path is worth an empty map for the length of one fetch.
    """
    return render_template("threatmap.html", enabled=_persist_to_db_enabled(), recent_limit=RECENT_LIMIT)


@threatmap.route("/threatmap/data", methods=["GET"])
@login_required
@cors_required
def threatmap_data():
    """Map fill, top panels, TODAY count and ticker for the requested window.

    No legacy per-instance fallback: that path returns raw rows, so feeding the map from it would
    mean re-aggregating the whole window in Python on every poll. With persistence off there is
    nothing to draw, and the page says so instead.
    """
    if not _persist_to_db_enabled():
        return jsonify({"status": "error", "message": "METRICS_PERSIST_TO_DB is disabled"}), 409

    try:
        start = int(request.args.get("start", ""))
        end = int(request.args.get("end", ""))
    except ValueError:
        return jsonify({"status": "error", "message": "start and end must be Unix epoch seconds"}), 400

    try:
        payload = API_CLIENT.get_threatmap(
            start=start,
            end=end,
            limit=RECENT_LIMIT,
            facet_limit=FACET_LIMIT,
            search_panes=request.args.get("search_panes", ""),
        )
    except ApiClientError as e:
        if e.status_code == 400:
            LOGGER.warning(f"Metrics API rejected the threatmap query ({e})")
            return jsonify({"status": "error", "message": str(e) or "Invalid range"}), 400
        LOGGER.warning(f"Metrics API unavailable ({e}); threatmap will show its empty state")
        return jsonify({"status": "error", "message": "Metrics service unavailable"}), 503
    except ApiUnavailableError as e:
        LOGGER.warning(f"Metrics API unavailable ({e}); threatmap will show its empty state")
        return jsonify({"status": "error", "message": "Metrics service unavailable"}), 503

    # The API already answers with its own {"status": "success", ...} envelope.
    return jsonify(payload)
