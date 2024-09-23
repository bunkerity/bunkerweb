#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta
from json import dumps
from os import getenv, sep
from os.path import join
from secrets import token_urlsafe
from signal import SIGINT, signal, SIGTERM
from sys import path as sys_path
from time import time

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from flask import Flask, Response, flash as flask_flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_executor import Executor
from flask_login import current_user, LoginManager, login_required, logout_user
from flask_principal import ActionNeed, identity_loaded, Permission, Principal, RoleNeed, TypeNeed, UserNeed
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.routing.exceptions import BuildError

from app.models.reverse_proxied import ReverseProxied

from app.routes.bans import bans
from app.routes.cache import cache
from app.routes.configs import configs
from app.routes.global_config import global_config
from app.routes.home import home
from app.routes.instances import instances
from app.routes.jobs import jobs
from app.routes.login import login
from app.routes.logout import logout, logout_page
from app.routes.logs import logs
from app.routes.plugins import plugins
from app.routes.profile import profile
from app.routes.reports import reports
from app.routes.services import services
from app.routes.setup import setup
from app.routes.totp import totp

from app.dependencies import BW_CONFIG, DATA, DB
from app.models.models import AnonymousUser
from app.utils import TMP_DIR, LOGGER, flash, get_blacklisted_settings, get_filtered_settings, get_latest_stable_release, get_multiples, handle_stop, stop

signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

# Flask app
app = Flask(__name__, static_url_path="/", static_folder="app/static", template_folder="app/templates")

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    FLASK_SECRET = getenv("FLASK_SECRET")
    if not FLASK_SECRET:
        if not TMP_DIR.joinpath(".flask_secret").is_file():
            LOGGER.error("The FLASK_SECRET environment variable is missing and the .flask_secret file is missing, exiting ...")
            stop(1)
        FLASK_SECRET = TMP_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

    app.config["SECRET_KEY"] = FLASK_SECRET

    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["REMEMBER_COOKIE_NAME"] = "__Host-bw_ui_remember_token"
    app.config["REMEMBER_COOKIE_PATH"] = "/"
    app.config["REMEMBER_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

    app.config["WTF_CSRF_SSL_STRICT"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["SCRIPT_NONCE"] = ""

    app.config["EXECUTOR_MAX_WORKERS"] = 4

    principal = Principal()
    principal.init_app(app)

    admin_permission = Permission(TypeNeed("super_admin"))
    manage_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"))
    edit_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"))
    read_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"), ActionNeed("read"))

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    login_manager.login_view = "login.login_page"
    login_manager.anonymous_user = AnonymousUser

    def custom_url_for(endpoint, **values):
        try:
            if endpoint not in ("static", "index", "loading", "check", "check_reloading") and "_page" not in endpoint:
                return url_for(f"{endpoint}.{endpoint}_page", **values)
            return url_for(endpoint, **values)
        except BuildError as e:
            LOGGER.debug(f"Couldn't build the URL for {endpoint}: {e}")
            return "#"

    # Declare functions for jinja2
    app.jinja_env.globals.update(
        get_multiples=get_multiples,
        get_filtered_settings=get_filtered_settings,
        get_blacklisted_settings=get_blacklisted_settings,
        get_plugins_settings=BW_CONFIG.get_plugins_settings,
        url_for=custom_url_for,
    )

    # CSRF protection
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Executor
    executor = Executor(app)


@app.context_processor
def inject_variables():
    if request.path.startswith(("/check_reloading", "/setup", "/loading", "/login", "/totp")):
        return dict(script_nonce=app.config["SCRIPT_NONCE"])

    DATA.load_from_file()
    metadata = DB.get_metadata()

    changes_ongoing = any(
        v
        for k, v in DB.get_metadata().items()
        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
    )

    if not changes_ongoing and DATA.get("PRO_LOADING"):
        DATA["PRO_LOADING"] = False

    if not request.path.startswith("/loading"):
        if not changes_ongoing and metadata["failover"]:
            flash(
                "The last changes could not be applied because it creates a configuration error on NGINX, please check the logs for more information. The configured fell back to the last working one.",
                "error",
            )
        elif not changes_ongoing and not metadata["failover"] and DATA.get("CONFIG_CHANGED", False):
            flash("The last changes have been applied successfully.", "success")
            DATA["CONFIG_CHANGED"] = False

    return dict(
        script_nonce=app.config["SCRIPT_NONCE"],
        bw_version=metadata["version"],
        latest_version=DATA.get("LATEST_VERSION", "unknown"),
        is_pro_version=metadata["is_pro"],
        plugins=BW_CONFIG.get_plugins(),
        flash_messages=session.get("flash_messages", []),
        is_readonly=DATA.get("READONLY_MODE", False),
    )


@login_manager.user_loader
def load_user(username):
    ui_user = DB.get_ui_user(username=username)
    if not ui_user:
        LOGGER.warning(f"Couldn't get the user {username} from the database.")
        return None

    ui_user.list_roles = [role.role_name for role in ui_user.roles]
    for role in ui_user.list_roles:
        ui_user.list_permissions.extend(DB.get_ui_role_permissions(role))

    if ui_user.totp_secret:
        ui_user.list_recovery_codes = [recovery_code.code for recovery_code in ui_user.recovery_codes]

        if (
            "totp-disable" not in request.path
            and "totp-refresh" not in request.path
            and session.get("totp_validated", False)
            and not ui_user.list_recovery_codes
        ):
            flask_flash(
                f"""The two-factor authentication is enabled but no recovery codes are available, please refresh them:
<div class="mt-2 pt-2 border-top border-white">
    <a role='button' class='btn btn-sm btn-dark d-flex align-items-center' aria-pressed='true' href='{url_for('profile.profile_page')}'>here</a>
</div>""",
                "error",
            )

    return ui_user


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    identity.provides.add(UserNeed(current_user.get_id()))

    for role in current_user.list_roles:
        identity.provides.add(RoleNeed(role))

    for action in current_user.list_permissions:
        identity.provides.add(ActionNeed(action))

    if current_user.admin:
        identity.provides.add(TypeNeed("super_admin"))


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    LOGGER.error(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    session.clear()
    logout_user()
    flask_flash("Wrong CSRF token !", "error")
    if not current_user:
        return redirect(url_for("setup.setup_page")), 403
    return redirect(url_for("login.login_page")), 403


def update_latest_stable_release():
    DATA["LATEST_VERSION"] = get_latest_stable_release()


def check_database_state():
    DATA.load_from_file()
    if (
        DB.database_uri
        and DB.readonly
        and (datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LAST_DATABASE_RETRY", "1970-01-01T00:00:00")).astimezone() > timedelta(minutes=1))
    ):
        failed = False
        try:
            DB.retry_connection(pool_timeout=1)
            DB.retry_connection(log=False)
            LOGGER.info("The database is no longer read-only, defaulting to read-write mode")
        except BaseException:
            failed = True
            try:
                DB.retry_connection(readonly=True, pool_timeout=1)
                DB.retry_connection(readonly=True, log=False)
            except BaseException:
                if DB.database_uri_readonly:
                    with suppress(BaseException):
                        DB.retry_connection(fallback=True, pool_timeout=1)
                        DB.retry_connection(fallback=True, log=False)
        DATA.update(
            {
                "READONLY_MODE": failed,
                "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
            }
        )
    elif DB.database_uri and not DATA.get("READONLY_MODE", False) and request.method == "POST" and not ("/totp" in request.path or "/login" in request.path):
        try:
            DB.test_write()
            DATA["READONLY_MODE"] = False
        except BaseException:
            DATA.update(
                {
                    "READONLY_MODE": True,
                    "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
                }
            )
    else:
        try:
            DB.test_read()
        except BaseException:
            DATA["LAST_DATABASE_RETRY"] = DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat()


@app.before_request
def before_request():
    DATA.load_from_file()
    if DATA.get("SERVER_STOPPING", False):
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    app.config["SCRIPT_NONCE"] = token_urlsafe(32)

    if not request.path.startswith(("/css", "/img", "/js", "/fonts", "/libs")):
        if datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LATEST_VERSION_LAST_CHECK", "1970-01-01T00:00:00")).astimezone() > timedelta(hours=1):
            DATA["LATEST_VERSION_LAST_CHECK"] = datetime.now().astimezone().isoformat()
            executor.submit(update_latest_stable_release)

        executor.submit(check_database_state)

        DB.readonly = DATA.get("READONLY_MODE", False)

        if not request.path.startswith(("/check_reloading", "/loading", "/login", "/totp")) and DB.readonly:
            flask_flash("Database connection is in read-only mode : no modifications possible.", "error")

        if current_user.is_authenticated:
            passed = True

            # Case not login page, keep on 2FA before any other access
            if not session.get("totp_validated", False) and bool(current_user.totp_secret) and "/totp" not in request.path:
                if not request.path.endswith("/login"):
                    return redirect(url_for("totp.totp_page", next=request.form.get("next")))
                passed = False
            elif session["ip"] != request.remote_addr:
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session["user_agent"] != request.headers.get("User-Agent"):
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False
            elif "session_id" in session and session["session_id"] in DATA.get("REVOKED_SESSIONS", []):
                LOGGER.warning(f"User {current_user.get_id()} tried to access a revoked session.")
                passed = False

            if not passed:
                return logout_page()


def mark_user_access(session_id):
    if DB.readonly:
        return

    ret = DB.mark_ui_user_access(session_id, datetime.now().astimezone())
    if ret:
        LOGGER.error(f"Couldn't mark the user access: {ret}")
    LOGGER.debug(f"Marked the user access for session {session_id}")


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # * Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com https://api.github.com;"
        + f" script-src 'self' 'nonce-{app.config['SCRIPT_NONCE']}';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: blob: https://assets.bunkerity.com;"
        + " font-src 'self' data:;"
        + " base-uri 'self';"
        + " block-all-mixed-content;"
        + (" connect-src *;" if request.path.startswith(("/check", "/setup")) else "")
    )

    if request.headers.get("X-Forwarded-Proto") == "https":
        if not request.path.startswith("/setup/loading"):
            response.headers["Content-Security-Policy"] += " upgrade-insecure-requests;"

        # * Strict-Transport-Security header to force HTTPS if accessed via a reverse proxy
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    # * X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # * X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # * Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if not request.path.startswith(("/css", "/img", "/js", "/fonts", "/libs")) and current_user.is_authenticated and "session_id" in session:
        executor.submit(mark_user_access, session["session_id"])

    return response


### * MISC ROUTES * ###


@app.route("/", strict_slashes=False)
def index():
    if DB.get_ui_user():
        if current_user.is_authenticated:  # type: ignore
            return redirect(url_for("home.home_page"))
        return redirect(url_for("login.login_page"), 301)
    return redirect(url_for("setup.setup_page"), 301)


@app.route("/loading")
@login_required
def loading():
    return render_template("loading.html", message=request.values.get("message", "Loading"), next=request.values.get("next", None) or url_for("home.home_page"))


@app.route("/check", methods=["GET"])
def check():
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/check_reloading")
@login_required
def check_reloading():
    DATA.load_from_file()

    if not DATA.get("RELOADING", False) or DATA.get("LAST_RELOAD", 0) + 60 < time():
        if DATA.get("RELOADING", False):
            LOGGER.warning("Reloading took too long, forcing the state to be reloaded")
            flask_flash("Forced the status to be reloaded", "error")
            DATA["RELOADING"] = False

        for f in DATA.get("TO_FLASH", []):
            flash(f["content"], f["type"], save=f.get("save", True))

        DATA["TO_FLASH"] = []

    return jsonify({"reloading": DATA.get("RELOADING", False)})


BLUEPRINTS = (bans, cache, configs, global_config, home, instances, jobs, login, logout, logs, plugins, profile, reports, services, setup, totp)
for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)
