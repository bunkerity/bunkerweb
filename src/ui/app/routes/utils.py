from base64 import b64encode
from datetime import datetime
from functools import wraps
from io import BytesIO
from os import getenv, sep
from os.path import join
from sys import path as sys_path
from time import sleep
from typing import Any, Dict, Optional, Tuple, Union

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for app utils module")

from flask import Response, redirect, request, url_for
from qrcode.main import QRCode
from regex import compile as re_compile

from app.dependencies import BW_CONFIG, DB
from app.utils import flash

from common_utils import get_redis_client as get_common_redis_client  # type: ignore


LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
REVERSE_PROXY_PATH = re_compile(r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$")
PLUGIN_KEYS = ["id", "name", "description", "version", "stream", "settings"]
PLUGIN_ID_RX = re_compile(r"^[\w_-]{1,64}$")
CUSTOM_CONF_RX = re_compile(
    r"^CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(?P<name>.+)$"
)


# Wait for scheduler to finish applying configuration changes.
# Polls database metadata for up to 120 seconds to ensure no pending
# configuration changes before proceeding with operations.
def wait_applying():
    if DEBUG_MODE:
        logger.debug("wait_applying() called")
    
    current_time = datetime.now().astimezone()
    ready = False
    while not ready and (datetime.now().astimezone() - current_time).seconds < 120:
        db_metadata = DB.get_metadata()
        if isinstance(db_metadata, str):
            logger.error(f"An error occurred when checking for changes in the database : {db_metadata}")
        elif not any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            ready = True
            continue
        else:
            logger.warning("Scheduler is already applying a configuration, retrying in 1s ...")
        sleep(1)

    if not ready:
        logger.error("Too many retries while waiting for scheduler to apply configuration...")


# Verify required form data is present and contains valid values.
# Validates request.form against expected data structure and handles
# error cases with appropriate redirects and flash messages.
def verify_data_in_form(
    data: Optional[Dict[str, Union[Tuple, Any]]] = None, err_message: str = "", redirect_url: str = "", next: bool = False
) -> Union[bool, Response]:
    if DEBUG_MODE:
        logger.debug(f"verify_data_in_form() called")
    
    if not request.form:
        return handle_error("Invalid request", redirect_url, next, "error")

    logger.debug(f"Verifying data in form: {data}")
    logger.debug(f"Request form: {request.form}")

    # Loop on each key in data
    for key, values in (data or {}).items():
        if key not in request.form:
            return handle_error(f"Missing {key} in form", redirect_url, next, "error")

        # Case we want to only check if key is in form, we can skip the values check by setting values to falsy value
        if not values:
            continue

        if request.form[key] not in values:
            return handle_error(err_message, redirect_url, next, "error")

    return True


# Handle error message display, logging, and redirection.
# Centralizes error handling with flash messages, logging options,
# and conditional redirects based on provided parameters.
def handle_error(err_message: str = "", redirect_url: str = "", next: bool = False, log: Union[bool, str] = False) -> Union[bool, Response]:
    """Handle error message, flash it, log it if needed and redirect to redirect_url if provided or return False."""
    flash(err_message, "error")

    if log == "error":
        logger.error(err_message)

    if log == "exception":
        logger.exception(err_message)

    if not redirect_url:
        return False

    redirect_url = f"{redirect_url}.{redirect_url}_page" if "." not in redirect_url else redirect_url
    if next:
        return redirect(url_for("loading", next=url_for(redirect_url)))

    return redirect(url_for(redirect_url))


# Create standardized error response with message and status.
# Returns dictionary format error response for API endpoints
# and logs the error message for debugging purposes.
def error_message(msg: str):
    if DEBUG_MODE:
        logger.debug(f"error_message() called")
    
    logger.error(msg)
    return {"status": "ko", "message": msg}


# Generate base64-encoded QR code image from string data.
# Creates QR code with BunkerWeb styling and returns base64 string
# suitable for embedding in HTML img src attributes.
def get_b64encoded_qr_image(data: str):
    if DEBUG_MODE:
        logger.debug("get_b64encoded_qr_image() called")
    
    qr = QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b5577", back_color="white")
    buffered = BytesIO()
    img.save(buffered)
    return b64encode(buffered.getvalue()).decode("utf-8")


# Convert seconds to human-readable time duration string.
# Formats time periods into years, months, days, hours, and minutes
# with appropriate grammar and returns both string and primary unit.
def get_remain(seconds):
    if DEBUG_MODE:
        logger.debug("get_remain() called")
    
    term = "minute(s)"
    years, seconds = divmod(seconds, 60 * 60 * 24 * 365)
    months, seconds = divmod(seconds, 60 * 60 * 24 * 30)
    while months >= 12:
        years += 1
        months -= 12
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if years > 0:
        term = "year(s)"
        time_parts.append(f"{int(years)} year{'' if years == 1 else 's'}")
    if months > 0:
        if term == "minute(s)":
            term = "month(s)"
        time_parts.append(f"{int(months)} month{'' if months == 1 else 's'}")
    if days > 0:
        if term == "minute(s)":
            term = "day(s)"
        time_parts.append(f"{int(days)} day{'' if days == 1 else 's'}")
    if hours > 0:
        if term == "minute(s)":
            term = "hour(s)"
        time_parts.append(f"{int(hours)} hour{'' if hours == 1 else 's'}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'' if minutes == 1 else 's'}")

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts), term


# Decorator to enforce CORS or AJAX request requirements.
# Validates request headers to ensure proper fetch mode or AJAX
# request type before allowing access to protected endpoints.
def cors_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if DEBUG_MODE:
            logger.debug("cors_required decorator called")
        
        fetch_mode = request.headers.get("Sec-Fetch-Mode")
        x_requested_with = request.headers.get("X-Requested-With")

        # Check for CORS mode or AJAX request
        if fetch_mode != "cors" and (not x_requested_with or x_requested_with.lower() != "xmlhttprequest"):
            return Response("CORS or AJAX request required", status=403)

        return f(*args, **kwargs)

    return decorated_function


# Get Redis client configured with BunkerWeb settings.
# Retrieves Redis configuration from BW_CONFIG and creates client
# with support for standalone and sentinel configurations.
def get_redis_client():
    """
    Get a Redis client using configuration from BW_CONFIG.
    """
    if DEBUG_MODE:
        logger.debug("get_redis_client() called")
    
    db_config = BW_CONFIG.get_config(
        global_only=True,
        methods=False,
        filtered_settings=(
            "USE_REDIS",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_DB",
            "REDIS_TIMEOUT",
            "REDIS_KEEPALIVE_POOL",
            "REDIS_SSL",
            "REDIS_USERNAME",
            "REDIS_PASSWORD",
            "REDIS_SENTINEL_HOSTS",
            "REDIS_SENTINEL_USERNAME",
            "REDIS_SENTINEL_PASSWORD",
            "REDIS_SENTINEL_MASTER",
        ),
    )

    use_redis = db_config.get("USE_REDIS", "no") == "yes"

    redis_client = get_common_redis_client(
        use_redis=use_redis,
        redis_host=db_config.get("REDIS_HOST"),
        redis_port=db_config.get("REDIS_PORT", "6379"),
        redis_db=db_config.get("REDIS_DB", "0"),
        redis_timeout=db_config.get("REDIS_TIMEOUT", "1000.0"),
        redis_keepalive_pool=db_config.get("REDIS_KEEPALIVE_POOL", "10"),
        redis_ssl=db_config.get("REDIS_SSL", "no") == "yes",
        redis_username=db_config.get("REDIS_USERNAME") or None,
        redis_password=db_config.get("REDIS_PASSWORD") or None,
        redis_sentinel_hosts=db_config.get("REDIS_SENTINEL_HOSTS", []),
        redis_sentinel_username=db_config.get("REDIS_SENTINEL_USERNAME") or None,
        redis_sentinel_password=db_config.get("REDIS_SENTINEL_PASSWORD") or None,
        redis_sentinel_master=db_config.get("REDIS_SENTINEL_MASTER", ""),
    )

    if use_redis and not redis_client:
        flash("Couldn't connect to redis", "error")

    return redis_client
