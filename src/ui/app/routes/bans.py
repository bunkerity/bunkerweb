from datetime import datetime
from json import JSONDecodeError, dumps, loads
from math import floor
from time import time
from traceback import format_exc

from flask import Blueprint, flash as flask_flash, redirect, render_template, request, url_for
from flask_login import login_required

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
            # Retrieve global bans from Redis (stored with prefix "bans_ip_")
            for key in redis_client.scan_iter("bans_ip_*"):
                key_str = key.decode("utf-8", "replace")
                ip = key_str.replace("bans_ip_", "")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    # Ensure consistent scope for frontend display
                    ban_data["ban_scope"] = "global"
                    bans.append({"ip": ip, "exp": exp} | ban_data)
                except Exception as e:
                    LOGGER.debug(format_exc())
                    LOGGER.error(f"Failed to decode ban data for {ip}: {e}")

            # Retrieve service-specific bans from Redis (stored with prefix "bans_service_*_ip_")
            for key in redis_client.scan_iter("bans_service_*_ip_*"):
                key_str = key.decode("utf-8", "replace")
                service, ip = key_str.replace("bans_service_", "").split("_ip_")
                data = redis_client.get(key)
                if not data:
                    continue
                exp = redis_client.ttl(key)
                try:
                    ban_data = loads(data.decode("utf-8", "replace"))
                    # Ensure consistent scope for frontend display
                    ban_data["ban_scope"] = "service"
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

    # Also fetch bans from all connected BunkerWeb instances
    instance_bans = BW_INSTANCES_UTILS.get_bans()

    # Current timestamp for calculating remaining times
    timestamp_now = time()

    # Process instance bans and avoid duplicates with Redis bans
    for ban in instance_bans:
        # Normalize ban scope to ensure consistent frontend display
        if "ban_scope" not in ban:
            if ban.get("service", "_") == "_":
                ban["ban_scope"] = "global"
            else:
                ban["ban_scope"] = "service"

        # Skip if this ban already exists in the list (checking IP, scope and service combination)
        if not any(b["ip"] == ban["ip"] and b["ban_scope"] == ban["ban_scope"] and (b.get("service", "_") == ban.get("service", "_")) for b in bans):
            bans.append(ban)

    # Format ban times for display
    for ban in bans:
        exp = ban.pop("exp", 0)
        # Calculate human-readable remaining time
        remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        ban["remain"] = remain[0]
        # Format timestamps for start and end dates
        ban["start_date"] = datetime.fromtimestamp(floor(ban["date"])).astimezone().isoformat()
        ban["end_date"] = datetime.fromtimestamp(floor(timestamp_now + exp)).astimezone().isoformat()

    # Get list of services for the service dropdown in the UI
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
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
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
        # Validate ban structure
        if not isinstance(ban, dict) or "ip" not in ban:
            flask_flash(f"Invalid ban: {ban}, skipping it ...", "error")
            continue

        # Extract and normalize ban parameters
        ip = ban.get("ip", "")
        reason = ban.get("reason", "ui")
        ban_scope = ban.get("ban_scope", "global")
        service = ban.get("service", "")

        # Validate service name for service-specific bans
        if ban_scope == "service":
            services = BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("SERVER_NAME",))["SERVER_NAME"]
            if isinstance(services, str):
                services = services.split()

            # Force global ban if service is invalid
            if not service or service == "Web UI" or service not in services:
                flask_flash(f"Invalid service '{service}' for IP {ip}, defaulting to global ban", "warning")
                ban_scope = "global"
                service = "Web UI"

        try:
            # Parse and normalize the ban end date from ISO format
            ban_end_str = ban["end_date"]
            if "." in ban_end_str and "Z" in ban_end_str:
                ban_end_str = ban_end_str.split(".")[0] + "Z"

            ban_end = datetime.fromisoformat(ban_end_str.replace("Z", "+00:00"))
            # Ensure timezone awareness
            if ban_end.tzinfo is None:
                ban_end = ban_end.replace(tzinfo=datetime.timezone.utc)

            # Calculate seconds from now until ban end
            current_time = datetime.now().astimezone()
            ban_end = (ban_end - current_time).total_seconds()

            # Ensure ban duration is positive
            if ban_end <= 0:
                flask_flash(f"Invalid ban duration for IP {ip}, must be in the future", "error")
                continue

        except ValueError as e:
            flask_flash(f"Invalid ban date format: {ban['end_date']}, error: {e}", "error")
            continue

        if redis_client:
            try:
                # Generate the appropriate Redis key based on ban scope
                if ban_scope == "service" and service != "Web UI":
                    ban_key = f"bans_service_{service}_ip_{ip}"
                else:
                    ban_key = f"bans_ip_{ip}"
                    ban_scope = "global"

                # Store ban data in Redis with proper expiration
                ban_data = {"reason": reason, "date": time(), "service": service, "ban_scope": ban_scope}
                ok = redis_client.set(ban_key, dumps(ban_data))
                if not ok:
                    flash(f"Couldn't ban {ip} on redis", "error")
                redis_client.expire(ban_key, int(ban_end))
            except BaseException as e:
                LOGGER.error(f"Couldn't ban {ip} on redis: {e}")
                flash(f"Failed to ban {ip} on redis, see logs for more information.", "error")

        # Propagate ban to all connected BunkerWeb instances
        resp = BW_INSTANCES_UTILS.ban(ip, ban_end, reason, service, ban_scope)
        if resp:
            flash(f"Couldn't ban {ip} on the following instances: {', '.join(resp)}", "error")
        else:
            if ban_scope == "service":
                flash(f"Successfully banned {ip} for service {service}")
            else:
                flash(f"Successfully banned {ip} globally")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Banning {len(bans)} IP{'s' if len(bans) > 1 else ''}"))


@bans.route("/bans/unban", methods=["POST"])
@login_required
def bans_unban():
    # Check database state
    if DB.readonly:
        return handle_error("Database is in read-only mode", "bans")

    # Validate input parameters
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
        # Validate unban structure
        if "ip" not in unban:
            flask_flash(f"Invalid unban: {unban}, skipping it ...", "error")
            continue

        # Extract and normalize unban parameters
        ip = unban.get("ip")
        ban_scope = unban.get("ban_scope", "global")
        service = unban.get("service")

        # Normalize Web UI and default services to global scope
        if service in ("default server", "Web UI", "unknown"):
            if ban_scope == "service":
                flask_flash(f"Invalid service for IP {ip}, defaulting to global unban", "warning")
            service = None
            ban_scope = "global"

        if redis_client:
            try:
                # For service-specific unbans, only remove that service's ban
                # For global unbans, remove both global and all service-specific bans
                if service and ban_scope == "service":
                    redis_client.delete(f"bans_service_{service}_ip_{ip}")
                else:
                    # Remove global ban
                    redis_client.delete(f"bans_ip_{ip}")
                    # Also remove all service-specific bans for this IP
                    for key in redis_client.scan_iter(f"bans_service_*_ip_{ip}"):
                        redis_client.delete(key)
            except BaseException as e:
                LOGGER.error(f"Couldn't unban {ip} on redis: {e}")
                flash(f"Failed to unban {ip} on redis, see logs for more information.", "error")

        # Propagate unban to all connected BunkerWeb instances
        resp = BW_INSTANCES_UTILS.unban(ip, service)
        if resp:
            service_text = f" for service {service}" if service else ""
            flash(f"Couldn't unban {ip}{service_text} on the following instances: {', '.join(resp)}", "error")
        else:
            service_text = f" for service {service}" if service else ""
            flash(f"Successfully unbanned {ip}{service_text}")

    return redirect(url_for("loading", next=url_for("bans.bans_page"), message=f"Unbanning {len(unbans)} IP{'s' if len(unbans) > 1 else ''}"))
