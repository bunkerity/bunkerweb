from base64 import b64encode
from collections import defaultdict
from datetime import datetime
from functools import wraps
from io import BytesIO
from time import sleep
from typing import Any, Dict, Optional, Tuple, Union

from flask import Response, g, has_request_context, redirect, request, url_for
from qrcode.main import QRCode
from regex import compile as re_compile

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, BW_CONFIG
from app.utils import LOGGER, flash

from common_utils import get_redis_client as get_common_redis_client  # type: ignore

LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
REVERSE_PROXY_PATH = re_compile(r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$")
PLUGIN_KEYS = ["id", "name", "description", "version", "stream", "settings"]
PLUGIN_ID_RX = re_compile(r"^[\w_-]{1,64}$")
CUSTOM_CONF_RX = re_compile(
    r"^CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(?P<name>.+)$"
)
FILE_SETTING_NAME_RX = re_compile(r"^(?P<setting>.+)__FILE_NAME(?P<suffix>_\d+)?$")


def _sanitize_filename(name: str) -> str:
    """Strip path separators, null bytes, and control characters from an uploaded filename."""
    return "".join(ch for ch in name if ch >= " " and ch != "\x7f").replace("/", "").replace("\\", "").strip()


def wait_applying():
    current_time = datetime.now().astimezone()
    ready = False
    while not ready and (datetime.now().astimezone() - current_time).seconds < 120:
        try:
            db_metadata = API_CLIENT.get_metadata()
        except (ApiClientError, ApiUnavailableError) as e:
            LOGGER.error(f"An error occurred when checking for changes in the database : {e}")
            sleep(1)
            continue
        if not any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            ready = True
            continue
        else:
            LOGGER.warning("Scheduler is already applying a configuration, retrying in 1s ...")
        sleep(1)

    if not ready:
        LOGGER.error("Too many retries while waiting for scheduler to apply configuration...")


def verify_data_in_form(
    data: Optional[Dict[str, Union[Tuple, Any]]] = None, err_message: str = "", redirect_url: str = "", next: bool = False
) -> Union[bool, Response]:
    if not request.form:
        return handle_error("Invalid request", redirect_url, next, "error")

    LOGGER.debug(f"Verifying data in form: {data}")
    LOGGER.debug(f"Request form: {request.form}")

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


def handle_error(err_message: str = "", redirect_url: str = "", next: bool = False, log: Union[bool, str] = False) -> Union[bool, Response]:
    """Handle error message, flash it, log it if needed and redirect to redirect_url if provided or return False."""
    flash(err_message, "error")

    if log == "error":
        LOGGER.error(err_message)

    if log == "exception":
        LOGGER.exception(err_message)

    if not redirect_url:
        return False

    redirect_url = f"{redirect_url}.{redirect_url}_page" if "." not in redirect_url else redirect_url
    if next:
        return redirect(url_for("loading", next=url_for(redirect_url)))

    return redirect(url_for(redirect_url))


def error_message(msg: str):
    LOGGER.error(msg)
    return {"status": "ko", "message": msg}


def get_b64encoded_qr_image(data: str):
    qr = QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b5577", back_color="white")
    buffered = BytesIO()
    img.save(buffered)
    return b64encode(buffered.getvalue()).decode("utf-8")


def get_remain(seconds):
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


def cors_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fetch_mode = request.headers.get("Sec-Fetch-Mode")
        x_requested_with = request.headers.get("X-Requested-With")

        # Check for CORS mode or AJAX request
        if fetch_mode != "cors" and (not x_requested_with or x_requested_with.lower() != "xmlhttprequest"):
            return Response("CORS or AJAX request required", status=403)

        return f(*args, **kwargs)

    return decorated_function


def get_redis_client():
    """
    Get a Redis client using configuration from BW_CONFIG.

    The client is cached on ``flask.g`` for the duration of the current request,
    so a single request that touches Redis multiple times only pays one
    BW_CONFIG DB query and one connection PING. The cache stores ``None`` too
    (Redis disabled or unreachable), so we don't keep re-probing within a
    request. Outside of a request context (e.g. background executor threads,
    CLI) the client is never cached and ``flash`` is skipped.
    """
    if has_request_context() and "bw_redis_client" in g:
        return g.bw_redis_client

    db_config = BW_CONFIG.get_config(
        global_only=True,
        methods=False,
        filtered_settings=(
            "USE_REDIS",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_DATABASE",
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
        redis_db=db_config.get("REDIS_DATABASE", "0"),
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

    if use_redis and not redis_client and has_request_context():
        flash("Couldn't connect to redis", "error")

    if has_request_context():
        g.bw_redis_client = redis_client

    return redis_client


def extract_file_setting_names(variables: Dict[str, str]) -> Dict[str, str]:
    """
    Extract `<SETTING>__FILE_NAME` metadata fields from a form payload.

    Supported keys:
    - `SETTING__FILE_NAME`
    - `SETTING__FILE_NAME_<suffix>` (for multiple settings)
    """
    file_setting_names: Dict[str, str] = {}
    for key in list(variables.keys()):
        match = FILE_SETTING_NAME_RX.match(key)
        if not match:
            continue

        setting_name = match.group("setting") + (match.group("suffix") or "")
        file_setting_names[setting_name] = _sanitize_filename(variables.pop(key, ""))

    return file_setting_names


def parse_search_panes(source, *, sort_values: bool = False) -> str:
    """Parse `searchPanes[field][i]=value` keys from a Werkzeug MultiDict-like
    source (request.form, request.args, ...) into the `field1:value1,value2;field2:value3`
    format expected by data-collection helpers (BW_INSTANCES_UTILS.get_reports_query, etc.)."""
    search_panes = defaultdict(list)
    for key, value in source.items():
        if not key.startswith("searchPanes["):
            continue
        try:
            field = key.split("[", 1)[1].split("]", 1)[0]
        except IndexError:
            continue
        if field:
            search_panes[field].append(value)

    if not search_panes:
        return ""

    if sort_values:
        items = sorted(search_panes.items())
        return ";".join(f"{field}:{','.join(sorted(values))}" for field, values in items)

    return ";".join(f"{field}:{','.join(values)}" for field, values in search_panes.items())


def get_default_ban_time(config: dict, server_name: str) -> int:
    """Resolve the Bad Behavior ban duration for a report service."""
    try:
        if server_name and server_name not in ("_", ""):
            service_key = f"{server_name}_BAD_BEHAVIOR_BAN_TIME"
            if service_key in config:
                return int(config[service_key])
        return int(config.get("BAD_BEHAVIOR_BAN_TIME", 86400))
    except (AttributeError, TypeError, ValueError):
        return 86400


def parse_search_panes_dict(source) -> Dict[str, list]:
    """Same as `parse_search_panes` but returns the parsed mapping for callers
    that need to apply the filter in-process rather than forwarding a string."""
    parsed: Dict[str, list] = defaultdict(list)
    for key, value in source.items():
        if not key.startswith("searchPanes["):
            continue
        try:
            field = key.split("[", 1)[1].split("]", 1)[0]
        except IndexError:
            continue
        if field:
            parsed[field].append(value)
    return parsed
