from base64 import b64encode
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
from time import sleep, time
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple, Union

from flask import Response, g, has_request_context, redirect, request, url_for
from qrcode.main import QRCode
from regex import compile as re_compile

from app.api_client import ApiClientError, ApiUnavailableError
from app.dependencies import API_CLIENT, BW_CONFIG
from app.i18n import translated
from app.utils import LOGGER, flash

from common_utils import get_redis_client as get_common_redis_client  # type: ignore
from custom_configs_validation import build_env_style_key_rx  # type: ignore

LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
# `\Z`, not `$`: this validates the wizard's user-supplied `ui_host`, and `setup.py:226` then
# writes the *original* string into `REVERSE_PROXY_HOST` -- which is rendered into an nginx
# `proxy_pass`. With `$` a trailing newline passes validation and is carried through verbatim.
REVERSE_PROXY_PATH = re_compile(
    r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)\Z"
)
PLUGIN_KEYS = ["id", "name", "description", "version", "stream", "settings"]
# `\Z`, not `$`: `$` also matches before a trailing newline, so `"plugin\n"` would pass and
# become a directory name. Same defect as the config-name regexes.
PLUGIN_ID_RX = re_compile(r"^[\w_-]{1,64}\Z")
# Built by the shared validator so this stays in lockstep with its twin in
# `src/common/gen/save_config.py` -- the two have already drifted once (see
# `custom_configs_validation.build_env_style_key_rx`'s docstring). `services.py:1139` derives
# the same `http_x`-shaped key from either form, so a dirty match there would have silently
# aliased two form fields onto one config; the shared builder anchors on `\Z` to prevent it.
CUSTOM_CONF_RX = build_env_style_key_rx(with_service_prefix=False)
# Same aliasing as `CUSTOM_CONF_RX`: with `$`, `SETTING__FILE_NAME\n` matches and
# `extract_file_setting_names` derives the same `SETTING` key as the clean field.
FILE_SETTING_NAME_RX = re_compile(r"^(?P<setting>.+)__FILE_NAME(?P<suffix>_\d+)?\Z")


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
        return handle_error(translated("utils.flash.invalid_request") or "Invalid request", redirect_url, next, "error")

    LOGGER.debug(f"Verifying data in form: {data}")
    LOGGER.debug(f"Request form: {request.form}")

    # Loop on each key in data
    for key, values in (data or {}).items():
        if key not in request.form:
            return handle_error(translated("utils.flash.missing_form", key=key) or f"Missing {key} in form", redirect_url, next, "error")

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
            return Response(translated("flash.cors_or_ajax_request_required") or "CORS or AJAX request required", status=403)

        return f(*args, **kwargs)

    return decorated_function


def get_redis_client():
    """
    Get a Redis client using configuration from BW_CONFIG.

    The client itself is memoised process-wide by ``common_utils.get_redis_client``,
    keyed on the connection parameters, so background executor threads share the
    same pool as request threads. The ``flask.g`` cache on top of it only saves the
    repeated BW_CONFIG DB query within a single request, and stores ``None`` too
    (Redis disabled or unreachable) so we don't keep re-probing. Outside of a
    request context (e.g. background executor threads, CLI) nothing is cached on
    ``g`` and ``flash`` is skipped.
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
            "REDIS_SSL_VERIFY",
            "REDIS_SSL_CA",
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
        redis_ssl_verify=(db_config.get("REDIS_SSL_VERIFY", "yes") or "yes").lower() == "yes",
        redis_ssl_ca=db_config.get("REDIS_SSL_CA") or None,
        redis_username=db_config.get("REDIS_USERNAME") or None,
        redis_password=db_config.get("REDIS_PASSWORD") or None,
        redis_sentinel_hosts=db_config.get("REDIS_SENTINEL_HOSTS", []),
        redis_sentinel_username=db_config.get("REDIS_SENTINEL_USERNAME") or None,
        redis_sentinel_password=db_config.get("REDIS_SENTINEL_PASSWORD") or None,
        redis_sentinel_master=db_config.get("REDIS_SENTINEL_MASTER", ""),
        logger=LOGGER,
    )

    if use_redis and not redis_client and has_request_context():
        flash(translated("utils.flash.couldn_t_connect_redis") or "Couldn't connect to redis", "error")

    if has_request_context():
        g.bw_redis_client = redis_client

    return redis_client


# Fraction of PERMANENT_SESSION_LIFETIME an unmodified session's stored copy may burn
# before it is written back purely to slide its expiry. At the 12h default that is one
# write every 3h per session instead of one per request, and it leaves 9h of TTL slack
# behind every skipped write: flask-session's save_session returns before
# should_set_cookie when storage is skipped, so the browser cookie and the store entry
# only ever slide together and a client can never hold a cookie for an expired key.
# The cost is that a session idle for longer than lifetime * (1 - ratio) after its last
# write can expire early: 9h instead of 12h in the worst case.
SESSION_STORAGE_REFRESH_RATIO = 0.25
SESSION_LAST_STORED_KEY = "_last_stored_at"


def session_storage_due(session: Any, lifetime_seconds: float, now: Optional[float] = None) -> bool:
    """Decide whether a server-side session must be written back to storage.

    flask-session's ``should_set_storage`` returns ``session.modified or
    SESSION_REFRESH_EACH_REQUEST``, and the Web UI sets that flag, so every request with a
    non-empty session rewrites the whole payload, static assets included, since Flask
    serves them at the URL root here.

    A modified session still writes immediately: login, logout and session id rotation all
    depend on it. An unmodified one writes only once its stored copy is old enough, tracked
    by a stamp inside the payload so no extra read is needed.
    """
    now = time() if now is None else now

    if not session.modified:
        last_stored = session.get(SESSION_LAST_STORED_KEY)
        if isinstance(last_stored, (int, float)) and not isinstance(last_stored, bool) and now - last_stored < lifetime_seconds * SESSION_STORAGE_REFRESH_RATIO:
            return False

    session[SESSION_LAST_STORED_KEY] = now
    return True


# The session cookie is named per request, not per worker. Behind a proxy (X-Forwarded-For set)
# it is a `__Host-` cookie, which the browser only accepts over HTTPS with `Secure`; a direct
# http://host:7000 visit cannot use that prefix at all, so it gets the plain name. This used to be
# decided once per worker, in before_request, on the worker's first request -- but flask-session
# opens the session *before* before_request runs, so the first request of every fresh worker was
# read under the default name, came up anonymous, and its response overwrote the user's cookie
# with an empty session: a logout on every gunicorn max_requests recycle (H10). It also let the
# first request of a worker choose the name for every user of that worker.
PROXIED_SESSION_COOKIE = "__Host-bw_ui_session"
DIRECT_SESSION_COOKIE = "bw_ui_session"


def session_cookie_for(environ: Dict[str, Any]) -> Tuple[str, bool]:
    """The (name, secure) pair of the session cookie for the request described by ``environ``."""
    if environ.get("HTTP_X_FORWARDED_FOR") is not None:
        return PROXIED_SESSION_COOKIE, True
    return DIRECT_SESSION_COOKIE, False


def bind_session_cookie_per_request(interface: Any) -> None:
    """Make a flask-session interface read and write the per-request cookie of `session_cookie_for`.

    flask-session 0.8 reads the cookie in ``open_session`` straight from
    ``app.config["SESSION_COOKIE_NAME"]``, a key every thread of the worker shares, so it is handed
    a view of the request whose only cookie is this request's session id under that configured name.
    ``save_session`` goes through ``get_cookie_name``/``get_cookie_secure``, overridden here.
    """
    open_session = interface.open_session

    def _open_session(flask_app, req):
        name, _ = session_cookie_for(req.environ)
        return open_session(flask_app, SimpleNamespace(cookies={flask_app.config["SESSION_COOKIE_NAME"]: req.cookies.get(name)}))

    interface.open_session = _open_session
    interface.get_cookie_name = lambda flask_app: session_cookie_for(request.environ)[0]
    interface.get_cookie_secure = lambda flask_app: session_cookie_for(request.environ)[1]


def chain_session_fallback(primary: Any, fallback: Any) -> None:
    """Let a flask-session interface find the sessions another backend holds, and move them over.

    A session missing from ``primary`` is read from ``fallback``; any write to ``primary`` drops the
    fallback copy, and any delete hits both, so a logout can never leave a live copy behind to be
    read back. Used with Redis as primary and the file store as fallback: an upgrade from file
    sessions, or a worker that booted before the scheduler stored ``USE_REDIS`` (H18), then costs
    nobody their session when Redis takes over.
    """
    retrieve, upsert, delete = primary._retrieve_session_data, primary._upsert_session, primary._delete_session

    def _fallback_id(store_id: str) -> str:
        return fallback._get_store_id(store_id[len(primary.key_prefix) :])  # noqa: E203

    def _retrieve(store_id):
        data = retrieve(store_id)
        return fallback._retrieve_session_data(_fallback_id(store_id)) if data is None else data

    def _upsert(session_lifetime, session, store_id):
        upsert(session_lifetime, session, store_id)
        fallback._delete_session(_fallback_id(store_id))

    def _delete(store_id):
        delete(store_id)
        fallback._delete_session(_fallback_id(store_id))

    primary._retrieve_session_data, primary._upsert_session, primary._delete_session = _retrieve, _upsert, _delete


# A session with nobody logged in carries only what the login page needs: its form's CSRF token and a
# language picked there. Flask-WTF refuses that token after an hour (WTF_CSRF_TIME_LIMIT's default),
# so keeping the session longer keeps nothing usable -- it only let anyone who can reach /login fill
# the non-evicting broker with 12 h keys, one per request (H17).
ANONYMOUS_SESSION_SECONDS = 3600


def cap_anonymous_session_lifetime(interface: Any) -> None:
    """Store a session that no user is logged into (no Flask-Login `_user_id`) for an hour at most."""
    upsert = interface._upsert_session

    def _upsert(session_lifetime, session, store_id):
        if "_user_id" not in session:
            session_lifetime = min(session_lifetime, timedelta(seconds=ANONYMOUS_SESSION_SECONDS))
        upsert(session_lifetime, session, store_id)

    interface._upsert_session = _upsert


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
