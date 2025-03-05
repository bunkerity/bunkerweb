from datetime import datetime
from json import JSONDecodeError, dumps, loads
from math import floor
from time import time
from traceback import format_exc

from flask import Blueprint, Response, flash as flask_flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DB
from app.utils import LOGGER, flash

from app.routes.utils import get_redis_client, get_remain, handle_error, verify_data_in_form

bans = Blueprint("bans", __name__)


@bans.route("/bans", methods=["GET"])
@login_required
def bans_page():
    redis_client = get_redis_client()

    bans = []
    if redis_client:
        try:
            # Get global bans
            for key in redis_client.scan_iter("bans_ip_*"):
                key_str = key.decode("utf-8", "replace")
                ip = key_str.replace("bans_ip_", "")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    ban_data["ban_scope"] = ban_data.get("ban_scope", "global")  # Default to global scope if not specified
                    bans.append({"ip": ip, "exp": exp} | ban_data)
                except Exception as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to decode ban data for {ip}: {e}")

            # Get service-specific bans
            for key in redis_client.scan_iter("bans_service_*_ip_*"):
                key_str = key.decode("utf-8", "replace")
                service, ip = key_str.replace("bans_service_", "").split("_ip_")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    ban_data["ban_scope"] = "service"  # Always service scope for these keys
                    ban_data["service"] = service
                    bans.append({"ip": ip, "exp": exp} | ban_data)
                except Exception as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to decode ban data for {ip} on service {service}: {e}")
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Couldn't get bans from redis: {e}")
            flash("Failed to fetch bans from Redis, see logs for more information.", "error")
            bans = []

    instance_bans = BW_INSTANCES_UTILS.get_bans()

    # Prepare data
    timestamp_now = time()

    for ban in instance_bans:
        if not any(b["ip"] == ban["ip"] and b.get("service", "unknown") == ban.get("service", "unknown") for b in bans):
            bans.append(ban)

    for ban in bans:
        exp = ban.pop("exp", 0)
        # Add remain
        remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        ban["remain"] = remain[0]
        # Convert stamp to date
        ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
        ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()

    # Get services list and ensure it's properly formatted as a list
    services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
    if isinstance(services, str):
        services = services.split()

    return render_template(
        "bans.html",
        bans=bans,
        services=services,
    )


@bans.route("/bans/ban", methods=["POST"])
@login_required
def bans_ban():
    if "write" not in current_user.list_permissions:
        return Response("You don't have the required permissions to ban IPs.", 403)
    elif DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    verify_data_in_form(
        data={"bans": None},
        err_message="Missing bans parameter on /bans/ban.",
        redirect_url="bans",
        next=True,
    )
    bans = request.form["bans"]
    if not bans:
        return handle_error("No bans.", "bans", True)
    try:
        bans = loads(bans)
    except JSONDecodeError:
        return handle_error("Invalid bans parameter on /bans/ban.", "bans", True)

    redis_client = get_redis_client()
    for ban in bans:
        if not isinstance(ban, dict) or "ip" not in ban:
            flask_flash(f"Invalid ban: {ban}, skipping it ...", "error")
            continue

        reason = ban.get("reason", "ui")
        ban_scope = ban.get("ban_scope", "global")
        service = ban.get("service", "Web UI")

        # Validate service name if service-specific ban is requested
        if ban_scope == "service":
            services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
            if isinstance(services, str):
                services = services.split()

            if not service or service == "Web UI" or service not in services:
                flask_flash(f"Invalid service '{service}' for IP {ban['ip']}, defaulting to global ban", "warning")
                ban_scope = "global"
                service = "Web UI"

        try:
            # Handle ISO date string that already includes timezone info
            ban_end_str = ban["end_date"]
            # Remove milliseconds if present for better compatibility
            if "." in ban_end_str and "Z" in ban_end_str:
                ban_end_str = ban_end_str.split(".")[0] + "Z"

            ban_end = datetime.fromisoformat(ban_end_str.replace("Z", "+00:00"))
            # Ensure the datetime is timezone aware
            if ban_end.tzinfo is None:
                # Default to UTC if no timezone info
                ban_end = ban_end.replace(tzinfo=datetime.timezone.utc)

            # Get current time with timezone
            current_time = datetime.now().astimezone()
            # Calculate seconds until ban end
            ban_end = (ban_end - current_time).total_seconds()

            # Ensure ban duration is positive
            if ban_end <= 0:
                flask_flash(f"Invalid ban duration for IP {ban['ip']}, must be in the future", "error")
                continue

        except ValueError as e:
            flask_flash(f"Invalid ban date format: {ban['end_date']}, error: {e}", "error")
            continue

        if redis_client:
            try:
                # Determine key based on ban scope from the request
                if ban_scope == "service" and service != "Web UI":
                    ban_key = f"bans_service_{service}_ip_{ban['ip']}"
                else:
                    ban_key = f"bans_ip_{ban['ip']}"
                    ban_scope = "global"  # Ensure consistency if service is missing

                ok = redis_client.set(ban_key, dumps({"reason": reason, "date": time(), "service": service, "ban_scope": ban_scope}))
                if not ok:
                    flash(f"Couldn't ban {ban['ip']} on redis", "error")
                redis_client.expire(ban_key, int(ban_end))
            except BaseException as e:
                LOGGER.error(f"Couldn't ban {ban['ip']} on redis: {e}")
                flash(f"Failed to ban {ban['ip']} on redis, see logs for more information.", "error")

        resp = BW_INSTANCES_UTILS.ban(ban["ip"], ban_end, reason, service, ban_scope)
        if resp:
            flash(f"Couldn't ban {ban['ip']} on the following instances: {', '.join(resp)}", "error")
        else:
            flash(f"Successfully banned {ban['ip']} with scope {ban_scope}")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Banning {len(bans)} IP{'s' if len(bans) > 1 else ''}"))


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    if "write" not in current_user.list_permissions:
        return Response("You don't have the required permissions to unban IPs.", 403)
    elif DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    verify_data_in_form(
        data={"ips": None},
        err_message="Missing bans parameter on /bans/unban.",
        redirect_url="bans",
        next=True,
    )
    unbans = request.form["ips"]
    if not unbans:
        return handle_error("No bans.", "ips", True)
    try:
        unbans = loads(unbans)
    except JSONDecodeError:
        return handle_error("Invalid ips parameter on /bans/unban.", "bans", True)

    redis_client = get_redis_client()
    for unban in unbans:
        if "ip" not in unban:
            flask_flash(f"Invalid unban: {unban}, skipping it ...", "error")
            continue

        # Extract service from the unban data if available
        service = unban.get("service")
        if service == "default server":
            service = None

        if redis_client:
            try:
                # Delete global ban
                redis_client.delete(f"bans_ip_{unban['ip']}")

                # If service is specified, only delete that service-specific ban
                if service and service not in ("unknown", "Web UI"):
                    redis_client.delete(f"bans_service_{service}_ip_{unban['ip']}")
                else:
                    # Otherwise, scan and delete all service-specific bans for this IP
                    for key in redis_client.scan_iter(f"bans_service_*_ip_{unban['ip']}"):
                        redis_client.delete(key)
            except BaseException as e:
                LOGGER.error(f"Couldn't unban {unban['ip']} on redis: {e}")
                flash(f"Failed to unban {unban['ip']} on redis, see logs for more information.", "error")

        # Pass the service to the unban method
        resp = BW_INSTANCES_UTILS.unban(unban["ip"], service)
        if resp:
            service_text = f" for service {service}" if service else ""
            flash(f"Couldn't unban {unban['ip']}{service_text} on the following instances: {', '.join(resp)}", "error")
        else:
            service_text = f" for service {service}" if service else ""
            flash(f"Successfully unbanned {unban['ip']}{service_text}")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {len(unbans)} IP{'s' if len(unbans) > 1 else ''}"))
