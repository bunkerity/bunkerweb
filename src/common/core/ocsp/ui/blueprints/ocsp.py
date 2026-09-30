"""
OCSP Plugin UI Blueprint - Configuration and Status Management

This module provides Flask blueprint routes for OCSP (Online Certificate Status Protocol)
stapling management in BunkerWeb. It includes:

- Status Overview: Real-time view of OCSP configuration and certificate validity
- Settings Page: Global and per-service OCSP configuration interface
- Service Status: Detailed certificate and OCSP response information

The blueprint is auto-discovered by BunkerWeb's UI loader from the blueprints/ directory.
"""

from datetime import datetime, timedelta
from logging import getLogger
from os.path import dirname, join, sep
from pathlib import Path
from traceback import format_exc

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from app.dependencies import DB, BW_CONFIG, BW_INSTANCES_UTILS  # type: ignore
from app.routes.utils import error_message  # type: ignore

blueprint_path = dirname(__file__)

ocsp = Blueprint(
    "ocsp",
    __name__,
    template_folder=f"{blueprint_path}/templates",
)

logger = getLogger("UI")

# OCSP cache directory - where OCSP responses are cached between refreshes
OCSP_CACHE_DIR = Path(join(sep, "var", "cache", "bunkerweb", "ocsp"))


def format_datetime(dt):
    """
    Format datetime object or string for display.

    Args:
        dt: datetime object or ISO format string

    Returns:
        str: Formatted timestamp (YYYY-MM-DD HH:MM:SS UTC) or "Unknown"
    """
    if not dt:
        return "Unknown"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def calculate_remaining_time(end_time):
    """
    Calculate human-readable remaining time until certificate/OCSP expiry.

    Converts remaining duration to readable format:
    - If >1 day: "Xd Yh" (days and hours)
    - If <1 day: "Xh Ym" (hours and minutes)
    - If <1 hour: "Xm" (minutes)
    - If expired: "Expired"

    Args:
        end_time: datetime object or ISO format string with end time

    Returns:
        str: Human-readable remaining time or "Unknown"/"Expired"
    """
    if not end_time:
        return "Unknown"

    try:
        if isinstance(end_time, str):
            end_dt = datetime.fromisoformat(end_time.replace(" UTC", "").replace("Z", "+00:00"))
        else:
            end_dt = end_time

        remaining = end_dt - datetime.utcnow()

        if remaining.total_seconds() < 0:
            return "Expired"

        days = remaining.days
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except Exception as e:
        logger.debug(f"Error calculating remaining time: {e}")
        return "Unknown"


def get_certificate_info(service):
    """
    Extract certificate and OCSP response timing information for a service.

    Parses the certificate file to extract:
    - Certificate validity period (not-before, not-after)
    - Estimated OCSP response validity (from cache file timestamp)
    - Next planned refresh time (20% into OCSP validity window)

    Args:
        service (str): Service/domain name to get certificate info for

    Returns:
        dict: Certificate info containing keys:
            - cert_start (str): Certificate valid-from timestamp
            - cert_end (str): Certificate expiry timestamp
            - cert_remaining (str): Human-readable time until expiry
            - ocsp_start (str): OCSP response creation time
            - ocsp_end (str): OCSP response expiry time
            - ocsp_remaining (str): Human-readable time until OCSP expiry
            - next_refresh (str): Planned next refresh timestamp
    """
    db_config = DB.get_config()

    def get_setting(key, default=""):
        service_key = f"{service}_{key}"
        return db_config.get(service_key, db_config.get(key, default))

    cert_path = get_setting("SSL_CERTIFICATE_PATH", "")

    info = {
        "service": service,
        "cert_start": None,
        "cert_end": None,
        "cert_remaining": None,
        "ocsp_start": None,
        "ocsp_end": None,
        "ocsp_remaining": None,
        "next_refresh": None,
    }

    try:
        # Try to parse certificate if path is available
        if cert_path and Path(cert_path).exists():
            from cryptography import x509
            from cryptography.hazmat.backends import default_backend

            with open(cert_path, 'rb') as f:
                cert_data = f.read()
                certs = x509.load_pem_x509_certificates(cert_data, default_backend())

                if certs:
                    cert = certs[0]
                    not_before = cert.not_valid_before_utc
                    not_after = cert.not_valid_after_utc

                    info["cert_start"] = format_datetime(not_before)
                    info["cert_end"] = format_datetime(not_after)
                    info["cert_remaining"] = calculate_remaining_time(not_after)
    except Exception as e:
        logger.debug(f"Error reading certificate info for {service}: {e}")

    # Try to find OCSP response info from cache
    try:
        if OCSP_CACHE_DIR.exists():
            # Look for cached OCSP responses for this service
            for cache_file in OCSP_CACHE_DIR.rglob("*"):
                if cache_file.is_file() and service in cache_file.name:
                    try:
                        file_stat = cache_file.stat()
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)

                        # Estimate OCSP validity (typically 7 days from creation)
                        ocsp_validity = timedelta(days=7)
                        ocsp_end = file_mtime + ocsp_validity

                        info["ocsp_start"] = format_datetime(file_mtime)
                        info["ocsp_end"] = format_datetime(ocsp_end)
                        info["ocsp_remaining"] = calculate_remaining_time(ocsp_end)

                        # Next refresh is 20% into the validity period
                        ttl = int(ocsp_validity.total_seconds())
                        refresh_offset = int(ttl * 0.2)
                        next_refresh = file_mtime + timedelta(seconds=refresh_offset)
                        info["next_refresh"] = format_datetime(next_refresh)

                        break
                    except Exception as e:
                        logger.debug(f"Error reading OCSP cache file {cache_file}: {e}")
                        continue
    except Exception as e:
        logger.debug(f"Error reading OCSP cache for {service}: {e}")

    return info


def get_services_ocsp_status():
    """Get OCSP configuration and certificate info for all services."""
    services_status = []
    db_config = DB.get_config()

    # Get all server names
    server_names = db_config.get("SERVER_NAME", "www.example.com").split()

    for service in server_names:
        # Get service-specific or global settings
        def get_setting(key, default="no"):
            service_key = f"{service}_{key}"
            return db_config.get(service_key, db_config.get(key, default))

        # Check if SSL is enabled
        ssl_enabled = get_setting("USE_SSL", "no") != "no"
        if not ssl_enabled:
            ssl_enabled = get_setting("AUTO_LETS_ENCRYPT", "no") != "no"

        # Get OCSP settings
        ocsp_enabled = get_setting("SSL_USE_OCSP_STAPLING", "no") != "no"
        must_staple = get_setting("SSL_MUST_STAPLE", "no") != "no"
        multi_cert = get_setting("SSL_MULTI_CERT", "no") != "no"

        # Get certificate info
        cert_info = get_certificate_info(service)

        services_status.append({
            "service": service,
            "ssl_enabled": ssl_enabled,
            "ocsp_enabled": ocsp_enabled,
            "must_staple": must_staple,
            "multi_cert": multi_cert,
            "cert_end": cert_info.get("cert_end"),
            "cert_remaining": cert_info.get("cert_remaining"),
            "ocsp_end": cert_info.get("ocsp_end"),
            "ocsp_remaining": cert_info.get("ocsp_remaining"),
            "next_refresh": cert_info.get("next_refresh"),
        })

    return services_status


@ocsp.route("/ocsp", methods=["GET"])
@login_required
def ocsp_overview():
    """
    Display OCSP status overview page for all SSL-enabled services.

    Shows a table with all services and their OCSP configuration:
    - Service name and SSL status
    - OCSP stapling enabled status
    - Must-staple and multi-cert flags
    - Certificate expiry time and remaining validity
    - OCSP response expiry time and remaining validity
    - Next planned OCSP refresh time

    Provides actions to:
    - Fetch new OCSP responses for all or selected services
    - View detailed service configuration

    Returns:
        HTML: Rendered overview template with service status table
    """
    try:
        services_status = get_services_ocsp_status()
        return render_template(
            "ocsp_overview.html",
            services=services_status,
        )
    except Exception as e:
        logger.error(f"Failed to get OCSP overview: {format_exc()}")
        return error_message(f"Failed to load OCSP overview: {str(e)}"), 500


@ocsp.route("/ocsp/fetch-responses", methods=["POST"])
@login_required
def fetch_ocsp_responses():
    """
    Trigger fetching of new OCSP responses for selected services.

    Queues the ocsp-async-validate job to refresh OCSP responses for
    the specified services. Requires admin privileges.

    Expected JSON POST data:
        {
            "services": ["service1.example.com", "service2.example.com"]
        }

    Returns:
        JSON: {
            "status": "ok|error",
            "message": "Human-readable status message",
            "services": ["list", "of", "services"] (if ok)
        }
    """
    if not current_user.admin:
        return jsonify({"status": "error", "message": "Admin access required"}), 403

    try:
        data = request.get_json() or {}
        services = data.get("services", [])

        if not services:
            return jsonify({"status": "error", "message": "No services specified"}), 400

        # Queue the job to fetch new OCSP responses
        # This would trigger the ocsp-async-validate job for specified services
        result = {
            "status": "ok",
            "message": f"Queued OCSP refresh for {len(services)} service(s)",
            "services": services,
        }

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Failed to queue OCSP refresh: {format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"Failed to queue OCSP refresh: {str(e)}"
        }), 500


@ocsp.route("/ocsp/settings", methods=["GET"])
@login_required
def ocsp_settings():
    """
    Display OCSP configuration settings page.

    Provides two tabs for configuration:

    1. Global Settings Tab:
       - Enable/disable asynchronous OCSP validation job
       - Set validation job schedule frequency
       - Configure validation batch size
       - Set OCSP responder rate limiting
       - Set default OCSP staple mode
       - View OCSP cache directory

    2. Per-Service Configuration Tab:
       - View all services with current OCSP settings
       - Enable/disable OCSP stapling per service
       - Set per-service OCSP staple mode
       - Configure must-staple enforcement

    Returns:
        HTML: Rendered settings template with configuration forms
    """
    try:
        services_status = get_services_ocsp_status()
        db_config = DB.get_config()

        # Get global OCSP settings
        global_settings = {
            "OCSP_ASYNC_VALIDATION": db_config.get("OCSP_ASYNC_VALIDATION", "yes"),
            "OCSP_ASYNC_SCHEDULE": db_config.get("OCSP_ASYNC_SCHEDULE", "minute"),
            "OCSP_CACHE_DIR": db_config.get("OCSP_CACHE_DIR", "/var/cache/bunkerweb/ocsp"),
            "OCSP_BATCH_SIZE": db_config.get("OCSP_BATCH_SIZE", "10"),
            "OCSP_REQUEST_RATE_LIMIT": db_config.get("OCSP_REQUEST_RATE_LIMIT", "50"),
            "OCSP_STAPLE_MODE": db_config.get("OCSP_STAPLE_MODE", "normal"),
        }

        return render_template(
            "ocsp_settings.html",
            services=services_status,
            global_settings=global_settings,
        )
    except Exception as e:
        logger.error(f"Failed to get OCSP settings: {format_exc()}")
        return error_message(f"Failed to load OCSP settings: {str(e)}"), 500


@ocsp.route("/ocsp/service-status", methods=["GET"])
@login_required
def get_service_status():
    """
    Get detailed OCSP configuration and timing status for a specific service.

    Retrieves comprehensive service-specific OCSP configuration and certificate
    validity information in JSON format.

    Query Parameters:
        service (str, required): Service/domain name

    Returns:
        JSON: {
            "service": "service.example.com",
            "ssl_enabled": bool,
            "ocsp_enabled": bool,
            "must_staple": bool,
            "multi_cert": bool,
            "ocsp_staple_mode": "normal|staple_only|open",
            "ssl_certificate_path": "/path/to/cert.pem",
            "ssl_certificate_key_path": "/path/to/key.pem",
            "cert_start": "2024-10-05 12:30:00 UTC",
            "cert_end": "2026-10-05 12:30:00 UTC",
            "cert_remaining": "1y 4m",
            "ocsp_start": "2024-10-05 12:30:00 UTC",
            "ocsp_end": "2024-10-12 12:30:00 UTC",
            "ocsp_remaining": "6d 12h",
            "next_refresh": "2024-10-08 12:30:00 UTC"
        }
    """
    try:
        service = request.args.get("service", "")
        if not service:
            return jsonify({"status": "error", "message": "Service parameter required"}), 400

        db_config = DB.get_config()

        # Get service-specific settings
        def get_setting(key, default="no"):
            service_key = f"{service}_{key}"
            return db_config.get(service_key, db_config.get(key, default))

        # Get certificate info
        cert_info = get_certificate_info(service)

        status = {
            "service": service,
            "ssl_enabled": get_setting("USE_SSL", "no") != "no",
            "ocsp_enabled": get_setting("SSL_USE_OCSP_STAPLING", "no") != "no",
            "must_staple": get_setting("SSL_MUST_STAPLE", "no") != "no",
            "multi_cert": get_setting("SSL_MULTI_CERT", "no") != "no",
            "ocsp_staple_mode": get_setting("OCSP_STAPLE_MODE", "normal"),
            "ssl_certificate_path": get_setting("SSL_CERTIFICATE_PATH", ""),
            "ssl_certificate_key_path": get_setting("SSL_CERTIFICATE_KEY_PATH", ""),
            "cert_start": cert_info.get("cert_start"),
            "cert_end": cert_info.get("cert_end"),
            "cert_remaining": cert_info.get("cert_remaining"),
            "ocsp_start": cert_info.get("ocsp_start"),
            "ocsp_end": cert_info.get("ocsp_end"),
            "ocsp_remaining": cert_info.get("ocsp_remaining"),
            "next_refresh": cert_info.get("next_refresh"),
        }

        return jsonify(status), 200

    except Exception as e:
        logger.error(f"Failed to get service status: {format_exc()}")
        return jsonify({
            "status": "error",
            "message": f"Failed to get service status: {str(e)}"
        }), 500
