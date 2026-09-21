"""CrowdSec connection status, investigation, and decision removal UI."""

from ipaddress import ip_address, ip_network

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from CrowdSec import CrowdSecClient, CrowdSecError  # type: ignore

from app.dependencies import DB
from app.utils import LOGGER

crowdsec = Blueprint("crowdsec", __name__)


def _call(operation):
    try:
        return jsonify(operation(CrowdSecClient(DB)))
    except CrowdSecError as exc:
        return jsonify({"error": str(exc)}), exc.status
    except Exception:
        LOGGER.exception("Unexpected CrowdSec UI error")
        return jsonify({"error": "Unable to complete the CrowdSec request"}), 500


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        raise CrowdSecError(f"Invalid {name}", 400) from None
    if value < minimum or value > maximum:
        raise CrowdSecError(f"Invalid {name}", 400)
    return value


@crowdsec.route("/crowdsec", methods=["GET"])
@login_required
def crowdsec_page():
    return render_template("crowdsec.html")


@crowdsec.route("/crowdsec/connections", methods=["GET"])
@login_required
def crowdsec_connections():
    return _call(lambda client: client.connections())


@crowdsec.route("/crowdsec/decisions", methods=["GET"])
@login_required
def crowdsec_decisions():
    def query(client):
        ip = request.args.get("ip", "").strip()
        if ip:
            try:
                ip = str(ip_address(ip))
            except ValueError:
                raise CrowdSecError("Invalid IP address", 400) from None
        origin = request.args.get("origin", "").strip()
        scenario = request.args.get("scenario", "").strip()
        if len(origin) > 512 or len(scenario) > 512:
            raise CrowdSecError("CrowdSec filter is too long", 400)
        return client.query(
            request.args.get("connection", ""),
            "decisions",
            {
                "ip": ip,
                "origin": origin,
                "scenario": scenario,
                "offset": _bounded_int("offset", 0, 0, 9007199254740991),
                "limit": _bounded_int("limit", 50, 1, 200),
            },
        )

    return _call(query)


@crowdsec.route("/crowdsec/investigate", methods=["GET"])
@login_required
def crowdsec_investigate():
    return _call(lambda client: client.investigate(request.args.get("connection", ""), request.args.get("ip", "")))


@crowdsec.route("/crowdsec/allowlists", methods=["GET"])
@login_required
def crowdsec_allowlists():
    return _call(
        lambda client: client.query(
            request.args.get("connection", ""),
            "allowlists",
            {
                "offset": _bounded_int("offset", 0, 0, 9007199254740991),
                "limit": _bounded_int("limit", 50, 1, 200),
            },
        )
    )


@crowdsec.route("/crowdsec/alerts/<int:alert_id>", methods=["GET"])
@login_required
def crowdsec_alert(alert_id: int):
    if alert_id <= 0 or alert_id > 9007199254740991:
        return jsonify({"error": "Invalid alert ID"}), 400
    return _call(lambda client: client.query(request.args.get("connection", ""), "alerts", {"alert_id": alert_id}))


@crowdsec.route("/crowdsec/unban", methods=["POST"])
@login_required
def crowdsec_unban():
    actor = current_user.get_id()
    connection_id = request.form.get("connection", "")
    target = request.form.get("value", "")
    decision_id_raw = request.form.get("decision_id", "")

    if not current_user.admin or "write" not in current_user.list_permissions:
        LOGGER.warning("CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=denied", actor, connection_id, decision_id_raw, target)
        return jsonify({"error": "CrowdSec decision removal is restricted to administrators"}), 403
    if DB.readonly:
        LOGGER.warning("CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=readonly", actor, connection_id, decision_id_raw, target)
        return jsonify({"error": "Database is in read-only mode"}), 403
    if request.form.get("confirmed") != "yes":
        return jsonify({"error": "Explicit confirmation is required"}), 400

    try:
        decision_id = int(decision_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid decision ID"}), 400
    scope = request.form.get("scope", "")
    decision_type = request.form.get("decision_type", "")
    if decision_id <= 0 or decision_id > 9007199254740991 or scope.lower() not in ("ip", "range") or not decision_type or len(decision_type) > 64:
        return jsonify({"error": "Invalid CrowdSec decision selection"}), 400
    try:
        ip_network(target, strict=False) if "/" in target else ip_address(target)
    except ValueError:
        return jsonify({"error": "Invalid CrowdSec decision target"}), 400

    client = CrowdSecClient(DB)
    try:
        connection = next((item for item in client.connections()["connections"] if item.get("id") == connection_id), None)
        if not connection:
            raise CrowdSecError("CrowdSec connection is no longer available", 404)
        if not connection.get("management_configured"):
            raise CrowdSecError("CrowdSec management credentials are not configured for this connection", 403)
        result = client.query(
            connection_id,
            "unban",
            {"decision_id": decision_id, "scope": scope, "value": target, "decision_type": decision_type},
        )
    except CrowdSecError as exc:
        LOGGER.warning(
            "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=error status=%s",
            actor,
            connection_id,
            decision_id,
            target,
            exc.status,
        )
        return jsonify({"error": str(exc)}), exc.status
    except Exception:
        LOGGER.exception("CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=error", actor, connection_id, decision_id, target)
        return jsonify({"error": "Unable to complete the CrowdSec removal"}), 500

    LOGGER.info(
        "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=removed propagation=pending",
        actor,
        connection_id,
        decision_id,
        target,
    )
    return jsonify(result)
