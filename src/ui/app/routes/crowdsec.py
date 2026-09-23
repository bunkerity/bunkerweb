"""CrowdSec connection status, investigation, and decision removal UI."""

from ipaddress import ip_address, ip_network

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT
from app.utils import LOGGER, is_readonly_request

crowdsec = Blueprint("crowdsec", __name__)
MAX_SAFE_INTEGER = 9007199254740991


def _unavailable_response(exc):
    prefix, _, detail = exc.message.partition(": ")
    status_text = prefix.removeprefix("API returned ")
    if status_text.isdecimal() and 500 <= int(status_text) < 600:
        return jsonify({"error": detail or "CrowdSec service unavailable"}), int(status_text)
    return jsonify({"error": "CrowdSec service unavailable"}), 503


def _call(operation):
    try:
        return jsonify(operation())
    except ApiClientError as exc:
        status = exc.status_code if exc.status_code and 400 <= exc.status_code < 500 else 502
        return jsonify({"error": exc.message or "CrowdSec request failed"}), status
    except ApiUnavailableError as exc:
        LOGGER.warning("CrowdSec API unavailable: %s", exc)
        return _unavailable_response(exc)
    except Exception:
        LOGGER.exception("Unexpected CrowdSec UI error")
        return jsonify({"error": "Unable to complete the CrowdSec request"}), 500


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {name}") from None
    if value < minimum or value > maximum:
        raise ValueError(f"Invalid {name}")
    return value


@crowdsec.route("/crowdsec", methods=["GET"])
@login_required
def crowdsec_page():
    return render_template("crowdsec.html")


@crowdsec.route("/crowdsec/connections", methods=["GET"])
@login_required
def crowdsec_connections():
    return _call(API_CLIENT.get_crowdsec_connections)


@crowdsec.route("/crowdsec/decisions", methods=["GET"])
@login_required
def crowdsec_decisions():
    ip = request.args.get("ip", "").strip()
    if ip:
        try:
            ip = str(ip_address(ip))
        except ValueError:
            return jsonify({"error": "Invalid IP address"}), 400
    origin = request.args.get("origin", "").strip()
    scenario = request.args.get("scenario", "").strip()
    if len(origin) > 512 or len(scenario) > 512:
        return jsonify({"error": "CrowdSec filter is too long"}), 400
    try:
        offset = _bounded_int("offset", 0, 0, MAX_SAFE_INTEGER)
        limit = _bounded_int("limit", 50, 1, 200)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return _call(
        lambda: API_CLIENT.get_crowdsec_decisions(request.args.get("connection", ""), ip=ip, origin=origin, scenario=scenario, offset=offset, limit=limit)
    )


@crowdsec.route("/crowdsec/investigate", methods=["GET"])
@login_required
def crowdsec_investigate():
    connection = request.args.get("connection", "")
    raw_ip = request.args.get("ip", "")
    try:
        ip = str(ip_address(raw_ip))
    except ValueError:
        return jsonify({"error": "Invalid IP address"}), 400
    return _call(lambda: API_CLIENT.get_crowdsec_investigation(connection, ip))


@crowdsec.route("/crowdsec/allowlists", methods=["GET"])
@login_required
def crowdsec_allowlists():
    try:
        offset = _bounded_int("offset", 0, 0, MAX_SAFE_INTEGER)
        limit = _bounded_int("limit", 50, 1, 200)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return _call(lambda: API_CLIENT.get_crowdsec_allowlists(request.args.get("connection", ""), offset=offset, limit=limit))


@crowdsec.route("/crowdsec/allowlists/check", methods=["GET"])
@login_required
def crowdsec_allowlist_check():
    try:
        ip = str(ip_address(request.args.get("ip", "")))
    except ValueError:
        return jsonify({"error": "Invalid IP address"}), 400
    return _call(lambda: API_CLIENT.check_crowdsec_allowlist(request.args.get("connection", ""), ip))


@crowdsec.route("/crowdsec/alerts/<int:alert_id>", methods=["GET"])
@login_required
def crowdsec_alert(alert_id: int):
    if alert_id <= 0 or alert_id > MAX_SAFE_INTEGER:
        return jsonify({"error": "Invalid alert ID"}), 400
    return _call(lambda: API_CLIENT.get_crowdsec_alerts(request.args.get("connection", ""), alert_id))


@crowdsec.route("/crowdsec/unban", methods=["POST"])
@login_required
def crowdsec_unban():
    actor = current_user.get_id()
    connection_id = request.form.get("connection", "")
    target = request.form.get("value", "")
    decision_id_raw = request.form.get("decision_id", "")

    if not current_user.admin:
        LOGGER.warning("CrowdSec removal actor=%r connection=%s outcome=denied", actor, connection_id)
        return jsonify({"error": "CrowdSec decision removal is restricted to administrators"}), 403
    if API_CLIENT.readonly:
        return jsonify({"error": "Database is in read-only mode"}), 403
    if is_readonly_request(API_CLIENT.readonly):
        return jsonify({"error": "You do not have the write permission"}), 403
    if request.form.get("confirmed") != "yes":
        return jsonify({"error": "Explicit confirmation is required"}), 400

    try:
        decision_id = int(decision_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid decision ID"}), 400
    scope = request.form.get("scope", "")
    decision_type = request.form.get("decision_type", "")
    if decision_id <= 0 or decision_id > MAX_SAFE_INTEGER or scope.lower() not in ("ip", "range") or not decision_type or len(decision_type) > 64:
        return jsonify({"error": "Invalid CrowdSec decision selection"}), 400
    try:
        ip_network(target, strict=False) if "/" in target else ip_address(target)
    except ValueError:
        return jsonify({"error": "Invalid CrowdSec decision target"}), 400
    if (scope.lower() == "range") != ("/" in target):
        return jsonify({"error": "CrowdSec decision scope does not match its target"}), 400

    selection = {"scope": scope, "value": target, "decision_type": decision_type}
    try:
        result = API_CLIENT.remove_crowdsec_decision(connection_id, decision_id, selection)
    except ApiClientError as exc:
        status = exc.status_code if exc.status_code and 400 <= exc.status_code < 500 else 502
        LOGGER.warning(
            "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=error status=%s",
            actor,
            connection_id,
            decision_id,
            target,
            status,
        )
        return jsonify({"error": exc.message or "CrowdSec decision removal failed"}), status
    except ApiUnavailableError as exc:
        LOGGER.warning("CrowdSec removal actor=%r connection=%s outcome=unavailable: %s", actor, connection_id, exc)
        return _unavailable_response(exc)

    LOGGER.info(
        "CrowdSec removal actor=%r connection=%s decision=%s target=%r outcome=removed propagation=pending",
        actor,
        connection_id,
        decision_id,
        target,
    )
    return jsonify(result)
