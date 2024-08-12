#!/usr/bin/env python3
from base64 import b64encode
from contextlib import suppress
from math import floor
from os import _exit, getenv, listdir, sep
from os.path import basename, dirname, isabs, join
from secrets import choice, token_urlsafe
from string import ascii_letters, digits
from sys import path as sys_path, modules as sys_modules
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bs4 import BeautifulSoup
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from flask import Flask, Response, flash, jsonify, make_response, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, LoginManager, login_required, login_user, logout_user
from flask_principal import ActionNeed, identity_loaded, Permission, Principal, RoleNeed, TypeNeed, UserNeed
from flask_wtf.csrf import CSRFProtect, CSRFError
from hashlib import sha256
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, dumps, loads as json_loads
from jinja2 import Environment, FileSystemLoader, select_autoescape
from redis import Redis, Sentinel
from regex import compile as re_compile
from requests import get
from shutil import move, rmtree
from signal import SIGINT, signal, SIGTERM
from subprocess import PIPE, Popen, call
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from threading import Thread
from time import sleep, time
from werkzeug.utils import secure_filename
from zipfile import BadZipFile, ZipFile

from src.instance import Instance, InstancesUtils
from src.custom_config import CustomConfig
from src.config import Config
from src.reverse_proxied import ReverseProxied
from src.totp import Totp
from src.ui_data import UIData

# TODO: rename to bans
from builder.bans2 import bans_builder  # type: ignore
from builder.home import home_builder  # type: ignore
from builder.instances import instances_builder  # type: ignore
from builder.global_config import global_config_builder  # type: ignore
from builder.jobs import jobs_builder  # type: ignore
from builder.services import services_builder  # type: ignore
from builder.raw_mode import raw_mode_builder  # type: ignore
from builder.advanced_mode import advanced_mode_builder  # type: ignore
from builder.easy_mode import easy_mode_builder  # type: ignore
from builder.logs import logs_builder  # type: ignore

from common_utils import get_version  # type: ignore
from logger import setup_logger  # type: ignore

from models import AnonymousUser
from ui_database import UIDatabase
from utils import USER_PASSWORD_RX, PLUGIN_KEYS, PLUGIN_ID_RX, check_settings, gen_password_hash, path_to_dict, get_remain

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")


def stop_gunicorn():
    p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
    out, _ = p.communicate()
    pid = out.strip().decode().split("\n")[0]
    call(["kill", "-SIGTERM", pid])


def stop(status, _stop=True):
    Path(sep, "var", "run", "bunkerweb", "ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    if _stop is True:
        stop_gunicorn()
    _exit(status)


def handle_stop(signum, frame):
    app.logger.info("Caught stop operation")
    app.logger.info("Stopping web ui ...")
    stop(0, False)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

sbin_nginx_path = Path(sep, "usr", "sbin", "nginx")

# Flask app
app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)
    app.logger = setup_logger("UI", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

    FLASK_SECRET = getenv("FLASK_SECRET")
    if not FLASK_SECRET:
        if not TMP_DIR.joinpath(".flask_secret").is_file():
            app.logger.error("The FLASK_SECRET environment variable is missing and the .flask_secret file is missing, exiting ...")
            stop(1)
        FLASK_SECRET = TMP_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

    TOTP_SECRETS = getenv("TOTP_SECRETS", "")
    if TOTP_SECRETS:
        try:
            TOTP_SECRETS = json_loads(TOTP_SECRETS)
        except JSONDecodeError:
            x = 1
            tmp_secrets = {}
            for secret in TOTP_SECRETS.strip().split(" "):
                if secret:
                    tmp_secrets[x] = secret
                    x += 1
            TOTP_SECRETS = tmp_secrets.copy()
            del tmp_secrets

    if not TOTP_SECRETS:
        if not LIB_DIR.joinpath(".totp_secrets.json").is_file():
            app.logger.error("The TOTP_SECRETS environment variable is missing and the .totp_secrets.json file is missing, exiting ...")
            stop(1)
        TOTP_SECRETS = json_loads(LIB_DIR.joinpath(".totp_secrets.json").read_text(encoding="utf-8"))

    app.config["SECRET_KEY"] = FLASK_SECRET

    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["SESSION_COOKIE_SECURE"] = True  # Required for __Host- prefix
    app.config["SESSION_COOKIE_HTTPONLY"] = True  # Recommended for security
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["WTF_CSRF_SSL_STRICT"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["SCRIPT_NONCE"] = ""

    principal = Principal()
    principal.init_app(app)

    admin_permission = Permission(TypeNeed("super_admin"))
    manage_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"))
    edit_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"))
    read_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"), ActionNeed("read"))

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.anonymous_user = AnonymousUser

    app.db = UIDatabase(app.logger, log=False)

    # Declare functions for jinja2
    app.jinja_env.globals.update(check_settings=check_settings)

    # CSRF protection
    csrf = CSRFProtect()
    csrf.init_app(app)

    app.bw_instances_utils = InstancesUtils(app.db)
    app.bw_config = Config(app.db)
    app.bw_custom_configs = CustomConfig()
    app.data = UIData(TMP_DIR.joinpath("ui_data.json"))
    app.totp = Totp(app, TOTP_SECRETS)

LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
REVERSE_PROXY_PATH = re_compile(r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$")


# TODO: Move this to a utils file
def wait_applying():
    current_time = datetime.now()
    ready = False
    while not ready and (datetime.now() - current_time).seconds < 120:
        db_metadata = app.db.get_metadata()
        if isinstance(db_metadata, str):
            app.logger.error(f"An error occurred when checking for changes in the database : {db_metadata}")
        elif not any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            ready = True
            continue
        else:
            app.logger.warning("Scheduler is already applying a configuration, retrying in 1s ...")
        sleep(1)

    if not ready:
        app.logger.error("Too many retries while waiting for scheduler to apply configuration...")


# TODO: Find a more elegant way to handle this
def manage_bunkerweb(method: str, *args, operation: str = "reloads", is_draft: bool = False, was_draft: bool = False, threaded: bool = False) -> int:
    # Do the operation
    error = 0

    if "TO_FLASH" not in app.data:
        app.data["TO_FLASH"] = []

    if method == "services":
        if operation == "new":
            operation, error = app.bw_config.new_service(args[0], is_draft=is_draft)
        elif operation == "edit":
            operation, error = app.bw_config.edit_service(args[1], args[0], check_changes=(was_draft != is_draft or not is_draft), is_draft=is_draft)
        elif operation == "delete":
            operation, error = app.bw_config.delete_service(args[2], check_changes=(was_draft != is_draft or not is_draft))
    elif method == "global_config":
        operation, error = app.bw_config.edit_global_conf(args[0], check_changes=True)

    if operation == "reload":
        instance = Instance.from_hostname(args[0], app.db)
        if instance:
            operation = instance.reload()
        else:
            operation = "The instance does not exist."
    elif operation == "start":
        instance = Instance.from_hostname(args[0], app.db)
        if instance:
            operation = instance.start()
        else:
            operation = "The instance does not exist."
    elif operation == "stop":
        instance = Instance.from_hostname(args[0], app.db)
        if instance:
            operation = instance.stop()
        else:
            operation = "The instance does not exist."
    elif operation == "restart":
        instance = Instance.from_hostname(args[0], app.db)
        if instance:
            operation = instance.restart()
        else:
            operation = "The instance does not exist."
    elif not error:
        operation = "The scheduler will be in charge of applying the changes."

    if operation:
        if isinstance(operation, list):
            for op in operation:
                app.data["TO_FLASH"].append({"content": f"Reload failed for the instance {op}", "type": "error"})
        elif operation.startswith(("Can't", "The database is read-only")):
            app.data["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            app.data["TO_FLASH"].append({"content": operation, "type": "success"})

    if not threaded:
        for f in app.data.get("TO_FLASH", []):
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

        app.data["TO_FLASH"] = []

    app.data["RELOADING"] = False

    return error


# UTILS
# TODO: move this to a utils file
def run_action(plugin: str, function_name: str = "", *, tmp_dir: Optional[Path] = None) -> Union[dict, Response]:
    message = ""
    if not tmp_dir:
        page = app.db.get_plugin_page(plugin)

        if not page:
            return {"status": "ko", "code": 404, "message": "The plugin does not have a page"}

        try:
            # Try to import the plugin's custom page
            tmp_dir = TMP_DIR.joinpath("ui", "action", str(uuid4()))
            tmp_dir.mkdir(parents=True, exist_ok=True)

            with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                tar.extractall(tmp_dir)

            tmp_dir = tmp_dir.joinpath("ui")
        except BaseException as e:
            app.logger.error(f"An error occurred while extracting the plugin: {e}")
            return {"status": "ko", "code": 500, "message": "An error occurred while extracting the plugin, see logs for more details"}

    try:
        action_file = tmp_dir.joinpath("actions.py")
        if not action_file.is_file():
            return {"status": "ko", "code": 404, "message": "The plugin does not have an action file"}

        sys_path.append(tmp_dir.as_posix())
        loader = SourceFileLoader("actions", action_file.as_posix())
        actions = loader.load_module()
    except BaseException as e:
        sys_path.pop()
        if function_name != "pre_render":
            rmtree(tmp_dir, ignore_errors=True)

        app.logger.error(f"An error occurred while importing the plugin: {e}")
        return {"status": "ko", "code": 500, "message": "An error occurred while importing the plugin, see logs for more details"}

    exception = None
    res = None
    message = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, function_name or plugin)
        queries = request.args.to_dict()
        try:
            data = request.json or {}
        except BaseException:
            data = {}

        res = method(app=app, args=queries, data=data)
    except AttributeError as e:
        if function_name == "pre_render":
            sys_path.pop()
            return {"status": "ok", "code": 200, "message": "The plugin does not have a pre_render method"}

        message = "The plugin does not have a method"
        exception = e
    except BaseException as e:
        message = "An error occurred while executing the plugin"
        exception = e
    finally:
        if sbin_nginx_path.is_file():
            # Remove the custom plugin from the shared library
            sys_modules.pop("actions", None)
            del actions

        sys_path.pop()

        if function_name != "pre_render":
            rmtree(tmp_dir, ignore_errors=True)

        if message:
            app.logger.error(message + (f": {exception}" if exception else ""))
        if message or not isinstance(res, dict) and not res:
            return {
                "status": "ko",
                "code": 500,
                "message": message + ", see logs for more details" if message else "The plugin did not return a valid response",
            }

    if isinstance(res, Response):
        return res

    return {"status": "ok", "code": 200, "data": res}


# TODO: move this to a utils file
def verify_data_in_form(data: dict[str, Union[tuple, any]] = {}, err_message: str = "", redirect_url: str = "", next: bool = False) -> Union[bool, Response]:
    # Loop on each key in data
    for key, values in data.items():
        if key not in request.form:
            return handle_error(f"Missing {key} in form", redirect_url, next, "error")

        # Case we want to only check if key is in form, we can skip the values check by setting values to falsy value
        if not values:
            continue

        if request.form[key] not in values:
            return handle_error(err_message, redirect_url, next, "error")

    return True


# TODO: move this to a utils file
def handle_error(err_message: str = "", redirect_url: str = "", next: bool = False, log: Union[bool, str] = False) -> Union[bool, Response]:
    """Handle error message, flash it, log it if needed and redirect to redirect_url if provided or return False."""
    flash(err_message, "error")

    if log == "error":
        app.logger.error(err_message)

    if log == "exception":
        app.logger.exception(err_message)

    if not redirect_url:
        return False

    if next:
        return redirect(url_for("loading", next=url_for(redirect_url)))

    return redirect(url_for(redirect_url))


# TODO: move this to a utils file
def error_message(msg: str):
    app.logger.error(msg)
    return {"status": "ko", "message": msg}


@app.context_processor
def inject_variables():
    app.data.load_from_file()
    metadata = app.db.get_metadata()

    changes_ongoing = any(
        v
        for k, v in app.db.get_metadata().items()
        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
    )

    if not changes_ongoing and app.data.get("PRO_LOADING"):
        app.data["PRO_LOADING"] = False

    if not changes_ongoing and metadata["failover"]:
        flash(
            "The last changes could not be applied because it creates a configuration error on NGINX, please check the logs for more information. The configured fell back to the last working one.",
            "error",
        )
    elif not changes_ongoing and not metadata["failover"] and app.data.get("CONFIG_CHANGED", False):
        flash("The last changes have been applied successfully.", "success")
        app.data["CONFIG_CHANGED"] = False

    # Keep only plugins with a page to display on sidebar
    plugins_page = [{"id": plugin.get("id"), "name": plugin.get("name")} for plugin in app.bw_config.get_plugins() if plugin.get("page", False)]

    # check that is value is in tuple
    return dict(
        data_server_global=dumps({"username": current_user.get_id() if current_user.is_authenticated else "", "plugins_page": plugins_page}),
        script_nonce=app.config["SCRIPT_NONCE"],
        is_pro_version=metadata["is_pro"],
        pro_status=metadata["pro_status"],
        pro_services=metadata["pro_services"],
        pro_expire=metadata["pro_expire"].strftime("%d-%m-%Y") if metadata["pro_expire"] else "Unknown",
        pro_overlapped=metadata["pro_overlapped"],
        plugins=app.bw_config.get_plugins(),
        pro_loading=app.data.get("PRO_LOADING", False),
        bw_version=metadata["version"],
        is_readonly=app.data.get("READONLY_MODE", False),
        username=current_user.get_id() if current_user.is_authenticated else "",
    )


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # * Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com;"
        + f" script-src 'self' 'nonce-{app.config['SCRIPT_NONCE']}';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: https://assets.bunkerity.com;"
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

    return response


@login_manager.user_loader
def load_user(username):
    ui_user = app.db.get_ui_user(username=username)
    if not ui_user:
        app.logger.warning(f"Couldn't get the user {username} from the database.")
        return None

    ui_user.list_roles = [role.role_name for role in ui_user.roles]
    for role in ui_user.list_roles:
        ui_user.list_permissions.extend(app.db.get_ui_role_permissions(role))

    if ui_user.totp_secret:
        ui_user.list_recovery_codes = [recovery_code.code for recovery_code in ui_user.recovery_codes]

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
    app.logger.error(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    logout()
    flash("Wrong CSRF token !", "error")
    if not current_user:
        return render_template("setup.html"), 403
    return render_template("login.html", is_totp=bool(current_user.totp_secret)), 403


@app.before_request
def before_request():
    app.data.load_from_file()
    if app.data.get("SERVER_STOPPING", False):
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    app.config["SCRIPT_NONCE"] = token_urlsafe(32)

    if not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts")):
        if (
            app.db.database_uri
            and app.db.readonly
            and (
                datetime.now(timezone.utc) - datetime.fromisoformat(app.data.get("LAST_DATABASE_RETRY", "1970-01-01T00:00:00")).replace(tzinfo=timezone.utc)
                > timedelta(minutes=1)
            )
        ):
            try:
                app.db.retry_connection(pool_timeout=1)
                app.db.retry_connection(log=False)
                app.data["READONLY_MODE"] = False
                app.logger.info("The database is no longer read-only, defaulting to read-write mode")
            except BaseException:
                try:
                    app.db.retry_connection(readonly=True, pool_timeout=1)
                    app.db.retry_connection(readonly=True, log=False)
                except BaseException:
                    if app.db.database_uri_readonly:
                        with suppress(BaseException):
                            app.db.retry_connection(fallback=True, pool_timeout=1)
                            app.db.retry_connection(fallback=True, log=False)
                app.data["READONLY_MODE"] = True
            app.data["LAST_DATABASE_RETRY"] = app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now().isoformat()
        elif not app.data.get("READONLY_MODE", False) and request.method == "POST" and not ("/totp" in request.path or "/login" in request.path):
            try:
                app.db.test_write()
                app.data["READONLY_MODE"] = False
            except BaseException:
                app.data["READONLY_MODE"] = True
                app.data["LAST_DATABASE_RETRY"] = app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now().isoformat()
        else:
            try:
                app.db.test_read()
            except BaseException:
                app.data["LAST_DATABASE_RETRY"] = app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now().isoformat()

        app.db.readonly = app.data.get("READONLY_MODE", False)

        if app.db.readonly:
            flash("Database connection is in read-only mode : no modification possible.", "error")

        if current_user.is_authenticated:
            passed = True

            # Case not login page, keep on 2FA before any other access
            if not session.get("totp_validated", False) and bool(current_user.totp_secret) and "/totp" not in request.path:
                if not request.path.endswith("/login"):
                    return redirect(url_for("totp", next=request.form.get("next")))
                passed = False
            elif current_user.last_login_ip != request.remote_addr:
                app.logger.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session.get("user_agent") != request.headers.get("User-Agent"):
                app.logger.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False

            if not passed:
                return logout()


### * ROUTES * ###


@app.route("/", strict_slashes=False)
def index():
    if app.db.get_ui_user():
        if current_user.is_authenticated:  # type: ignore
            return redirect(url_for("home"))
        return redirect(url_for("login"), 301)
    return redirect(url_for("setup"))


@app.route("/loading")
@login_required
def loading():
    return render_template("loading.html", message=request.values.get("message", "Loading"), next=request.values.get("next", None) or url_for("home"))


@app.route("/check", methods=["GET"])
def check():
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/setup", methods=["GET", "POST"])
def setup():
    db_config = app.bw_config.get_config(methods=False, filtered_settings=("SERVER_NAME", "MULTISITE", "USE_UI", "UI_HOST", "AUTO_LETS_ENCRYPT"))

    admin_user = app.db.get_ui_user()

    ui_reverse_proxy = False
    for server_name in db_config["SERVER_NAME"].split(" "):
        if server_name and db_config.get(f"{server_name}_USE_UI", db_config.get("USE_UI", "no")) == "yes":
            if admin_user:
                return redirect(url_for("login"), 301)
            ui_reverse_proxy = True
            break

    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "setup")

        required_keys = []
        if not ui_reverse_proxy:
            required_keys.extend(["server_name", "ui_host", "ui_url"])
        if not admin_user:
            required_keys.extend(["admin_username", "admin_password", "admin_password_check"])

        if not any(key in request.form for key in required_keys):
            return handle_error(f"Missing either one of the following parameters: {', '.join(required_keys)}.", "setup")

        if not admin_user:
            if len(request.form["admin_username"]) > 256:
                return handle_error("The admin username is too long. It must be less than 256 characters.", "setup")

            if request.form["admin_password"] != request.form["admin_password_check"]:
                return handle_error("The passwords do not match.", "setup")

            if not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return handle_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                    "setup",
                )

            ret = app.db.create_ui_user(request.form["admin_username"], gen_password_hash(request.form["admin_password"]), ["admin"], method="ui", admin=True)
            if ret:
                return handle_error(f"Couldn't create the admin user in the database: {ret}", "setup", False, "error")

            flash("The admin user was created successfully", "success")

        if not ui_reverse_proxy:
            server_names = db_config["SERVER_NAME"].split(" ")
            if request.form["server_name"] in server_names:
                return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")
            else:
                for server_name in server_names:
                    if request.form["server_name"] in db_config.get(f"{server_name}_SERVER_NAME", "").split(" "):
                        return handle_error(f"The hostname {request.form['server_name']} is already in use.", "setup")

            if not REVERSE_PROXY_PATH.match(request.form["ui_host"]):
                return handle_error("The hostname is not valid.", "setup")

            app.data["RELOADING"] = True
            app.data["LAST_RELOAD"] = time()

            config = {
                "SERVER_NAME": request.form["server_name"],
                "USE_UI": "yes",
                "USE_REVERSE_PROXY": "yes",
                "REVERSE_PROXY_HOST": request.form["ui_host"],
                "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                "INTERCEPTED_ERROR_CODES": "400 404 405 413 429 500 501 502 503 504",
                "MAX_CLIENT_SIZE": "50m",
                "KEEP_UPSTREAM_HEADERS": "Content-Security-Policy Strict-Transport-Security X-Frame-Options X-Content-Type-Options Referrer-Policy",
            }

            if request.form.get("auto_lets_encrypt", "no") == "yes":
                config["AUTO_LETS_ENCRYPT"] = "yes"
            else:
                config["GENERATE_SELF_SIGNED_SSL"] = "yes"
                config["SELF_SIGNED_SSL_SUBJ"] = f"/CN={request.form['server_name']}/"

            if not config.get("MULTISITE", "no") == "yes":
                app.bw_config.edit_global_conf({"MULTISITE": "yes"}, check_changes=False)

            # deepcode ignore MissingAPI: We don't need to check to wait for the thread to finish
            Thread(
                target=manage_bunkerweb,
                name="Reloading instances",
                args=("services", config, request.form["server_name"], request.form["server_name"]),
                kwargs={"operation": "new", "threaded": True},
            ).start()

        return Response(status=200)

    return render_template(
        "setup.html",
        ui_user=admin_user,
        ui_reverse_proxy=ui_reverse_proxy,
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        auto_lets_encrypt=db_config.get("AUTO_LETS_ENCRYPT", getenv("AUTO_LETS_ENCRYPT", "no")) == "yes",
        random_url=f"/{''.join(choice(ascii_letters + digits) for _ in range(10))}",
    )


@app.route("/setup/loading", methods=["GET"])
def setup_loading():
    return render_template("setup_loading.html")


@app.route("/totp", methods=["GET", "POST"])
@login_required
def totp():
    if request.method == "POST":
        verify_data_in_form(data={"totp_token": None}, err_message="No token provided on /totp.", redirect_url="totp")

        if not app.totp.verify_totp(request.form["totp_token"], user=current_user):
            recovery_code = app.totp.verify_recovery_code(request.form["totp_token"], user=current_user)
            if not recovery_code:
                return handle_error("The token is invalid.", "totp")
            app.db.use_ui_user_recovery_code(current_user.get_id(), recovery_code)

        session["totp_validated"] = True
        redirect(url_for("loading", next=request.form.get("next") or url_for("home")))

    if not bool(current_user.totp_secret) or session.get("totp_validated", False):
        return redirect(url_for("home"))

    return render_template("totp.html")


@app.route("/home")
@login_required
def home():
    """
    It returns the home page
    :return: The home.html template is being rendered with the following variables:
        check_version: a boolean indicating whether the local version is the same as the remote version
        remote_version: the remote version
        version: the local version
        instances_number: the number of instances
        services_number: the number of services
        posts: a list of posts
    """
    try:
        r = get("https://github.com/bunkerity/bunkerweb/releases/latest", allow_redirects=True, timeout=5)
        r.raise_for_status()
    except BaseException:
        r = None
    remote_version = None

    if r and r.status_code == 200:
        remote_version = basename(r.url).strip().replace("v", "")

    config = app.bw_config.get_config(with_drafts=True, filtered_settings=("SERVER_NAME",))
    instances = app.bw_instances_utils.get_instances()

    instance_health_count = 0

    for instance in instances:
        if instance.status == "up":
            instance_health_count += 1

    services = 0
    services_scheduler_count = 0
    services_ui_count = 0
    services_autoconf_count = 0

    for service in config["SERVER_NAME"]["value"].split(" "):
        service_method = config.get(f"{service}_SERVER_NAME", {"method": "scheduler"})["method"]

        if service_method == "scheduler":
            services_scheduler_count += 1
        elif service_method == "ui":
            services_ui_count += 1
        elif service_method == "autoconf":
            services_autoconf_count += 1
        services += 1

    metadata = app.db.get_metadata()

    data = {
        "check_version": not remote_version or get_version() == remote_version,
        "remote_version": remote_version,
        "version": metadata["version"],
        "instances_number": len(instances),
        "services_number": services,
        "instance_health_count": instance_health_count,
        "services_scheduler_count": services_scheduler_count,
        "services_ui_count": services_ui_count,
        "services_autoconf_count": services_autoconf_count,
        "is_pro_version": metadata["is_pro"],
        "pro_status": metadata["pro_status"],
        "pro_services": metadata["pro_services"],
        "pro_overlapped": metadata["pro_overlapped"],
        "plugins_number": len(app.bw_config.get_plugins()),
        "plugins_errors": app.db.get_plugins_errors(),
    }

    builder = home_builder(data)
    return render_template("home.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "account")

        verify_data_in_form(
            data={"operation": ("username", "password", "totp", "activate-key")}, err_message="Invalid operation parameter.", redirect_url="account"
        )

        if request.form["operation"] not in ("username", "password", "totp", "activate-key"):
            return handle_error("Invalid operation parameter.", "account")

        if request.form["operation"] == "activate-key":
            verify_data_in_form(data={"license": None}, err_message="Missing license for operation activate key on /account.", redirect_url="account")

            if len(request.form["license"]) == 0:
                return handle_error("The license key is empty", "account")

            variable = {}
            variable["PRO_LICENSE_KEY"] = request.form["license"]

            variable = app.bw_config.check_variables(variable, {"PRO_LICENSE_KEY": request.form["license"]})

            if not variable:
                return handle_error("The license key variable checks returned error", "account", True)

            # Force job to contact PRO API
            # by setting the last check to None
            metadata = app.db.get_metadata()
            metadata["last_pro_check"] = None
            app.db.set_pro_metadata(metadata)

            curr_changes = app.db.check_changes()

            # Reload instances
            def update_global_config(threaded: bool = False):
                wait_applying()

                if not manage_bunkerweb("global_config", variable, threaded=threaded):
                    message = "Checking license key to upgrade."
                    if threaded:
                        app.data["TO_FLASH"].append({"content": message, "type": "success"})
                    else:
                        flash(message)

            app.data["PRO_LOADING"] = True
            app.data["CONFIG_CHANGED"] = True

            if any(curr_changes.values()):
                app.data["RELOADING"] = True
                app.data["LAST_RELOAD"] = time()
                Thread(target=update_global_config, args=(True,)).start()
            else:
                update_global_config()

            return redirect(url_for("account"))

        verify_data_in_form(data={"curr_password": None}, err_message="Missing current password parameter on /account.", redirect_url="account")

        if not current_user.check_password(request.form["curr_password"]):
            return handle_error(f"The current password is incorrect. ({request.form['operation']})", "account")

        username = current_user.get_id()
        password = request.form["curr_password"]
        totp_secret = current_user.totp_secret
        totp_recovery_codes = current_user.list_recovery_codes

        if request.form["operation"] == "username":
            verify_data_in_form(data={"admin_username": None}, err_message="Missing admin username parameter on /account.", redirect_url="account")

            if len(request.form["admin_username"]) > 256:
                return handle_error("The admin username is too long. It must be less than 256 characters. (username)", "account")

            username = request.form["admin_username"]

            logout()

        if request.form["operation"] == "password":
            verify_data_in_form(
                data={"admin_password": None, "admin_password_check": None},
                err_message="Missing admin password or confirm password parameter on /account.",
                redirect_url="account",
            )

            if request.form["admin_password"] != request.form["admin_password_check"]:
                return handle_error("The passwords do not match. (password)", "account")

            if not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return handle_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). (password)",
                    "account",
                )

            password = request.form["admin_password"]

            logout()

        if request.form["operation"] == "totp":
            verify_data_in_form(data={"totp_token": None}, err_message="Missing totp token parameter on /account.", redirect_url="account")

            if not app.totp.verify_totp(
                request.form["totp_token"], totp_secret=session.get("tmp_totp_secret", ""), user=current_user
            ) and not app.totp.verify_recovery_code(request.form["totp_token"], user=current_user):
                return handle_error("The totp token is invalid. (totp)", "account")

            session["totp_validated"] = not bool(current_user.totp_secret)
            totp_secret = None if bool(current_user.totp_secret) else session.pop("tmp_totp_secret", "")

            if totp_secret and totp_secret != current_user.totp_secret:
                totp_recovery_codes = app.totp.generate_recovery_codes()
                flash(
                    "The recovery codes have been refreshed.\nPlease save them in a safe place. They will not be displayed again."
                    + "\n".join(totp_recovery_codes),
                    "info",
                )  # TODO: Remove this when we have a way to display the recovery codes

            app.logger.debug(f"totp recovery codes: {totp_recovery_codes}")

        ret = app.db.update_ui_user(
            username,
            gen_password_hash(password),
            totp_secret,
            totp_recovery_codes=totp_recovery_codes,
            method=current_user.method if request.form["operation"] == "totp" else "ui",
        )
        if ret:
            return handle_error(f"Couldn't update the admin user in the database: {ret}", "account", False, "error")

        flash(
            (
                f"The {request.form['operation']} has been successfully updated."
                if request.form["operation"] != "totp"
                else f"The two-factor authentication was successfully {'disabled' if bool(current_user.totp_secret) else 'enabled'}."
            ),
        )

        return redirect(url_for("account" if request.form["operation"] == "totp" else "login"))

    totp_qr_image = ""
    if not bool(current_user.totp_secret):
        session["tmp_totp_secret"] = app.totp.generate_totp_secret()
        totp_qr_image = app.totp.generate_qrcode(current_user.get_id(), session["tmp_totp_secret"])

    # TODO: Show user backup codes after TOTP refresh + add refresh feature
    return render_template(
        "account.html",
        username=current_user.get_id(),
        is_totp=bool(current_user.totp_secret),
        secret_token=app.totp.get_totp_pretty_key(session.get("tmp_totp_secret", "")),
        totp_qr_image=totp_qr_image,
        recovery_codes_needs_refresh=bool(current_user.totp_secret) and not current_user.list_recovery_codes,
    )


@app.route("/instances", methods=["GET", "POST"])
@login_required
def instances():
    # Manage instances
    if request.method == "POST":

        verify_data_in_form(data={"INSTANCE_ID": None}, err_message="Missing instance id parameter on /instances.", redirect_url="instances", next=True)
        verify_data_in_form(
            data={
                "operation": (
                    "reload",
                    "start",
                    "stop",
                    "restart",
                )
            },
            err_message="Missing operation parameter on /instances.",
            redirect_url="instances",
            next=True,
        )

        app.data["RELOADING"] = True
        app.data["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("instances", request.form["INSTANCE_ID"]),
            kwargs={"operation": request.form["operation"], "threaded": True},
        ).start()

        return redirect(
            url_for(
                "loading",
                next=url_for("instances"),
                message=(f"{request.form['operation'].title()}ing" if request.form["operation"] != "stop" else "Stopping") + " instance",
            )
        )

    # Display instances
    instances = app.bw_instances_utils.get_instances()

    builder = instances_builder(instances)
    return render_template("instances.html", title="Instances", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


def get_service_data(page_name: str):

    verify_data_in_form(
        data={"csrf_token": None},
        err_message=f"Missing csrf_token parameter on /{page_name}.",
        redirect_url="services",
    )

    verify_data_in_form(
        data={"operation": None},
        err_message=f"Missing operation parameter on /{page_name}.",
        redirect_url="services",
    )

    verify_data_in_form(
        data={"operation": ("edit", "new", "delete")},
        err_message="Invalid operation parameter on /{page_name}.",
        redirect_url="services",
    )

    config = app.db.get_config(methods=True, with_drafts=True)
    # Check variables
    variables = deepcopy(request.form.to_dict())
    mode = variables.pop("mode", None)

    del variables["csrf_token"]
    operation = variables.pop("operation")

    # Delete custom client variables
    variables.pop("SECURITY_LEVEL", None)

    # Get server name and old one
    old_server_name = ""
    if variables.get("OLD_SERVER_NAME"):
        old_server_name = variables.get("OLD_SERVER_NAME", "")
        del variables["OLD_SERVER_NAME"]

    server_name = variables["SERVER_NAME"].split(" ")[0] if "SERVER_NAME" in variables else old_server_name

    # Get draft if exists
    was_draft = config.get(f"{server_name}_IS_DRAFT", {"value": "no"})["value"] == "yes"
    is_draft = was_draft if not variables.get("is_draft") else variables.get("is_draft") == "yes"
    if variables.get("is_draft"):
        del variables["is_draft"]

    is_draft_unchanged = is_draft == was_draft

    # Get all variables starting with custom_config and delete them from variables
    custom_configs = []
    config_types = (
        "http",
        "stream",
        "server-http",
        "server-stream",
        "default-server-http",
        "default-server-stream",
        "modsec",
        "modsec-crs",
        "crs-plugins-before",
        "crs-plugins-after",
    )

    for variable in variables:
        if variable.startswith("custom_config_"):
            custom_configs.append(variable)
            del variables[variable]

    # custom_config variable format is custom_config_<type>_<filename>
    # we want a list of dict with each dict containing type, filename, action and server name
    # after getting all configs, we want to save them after the end of current service action
    # to avoid create config for none existing service or in case editing server name
    format_configs = []
    for custom_config in custom_configs:
        # first remove custom_config_ prefix
        custom_config = custom_config.split("custom_config_")[1]
        # then split the config into type, filename, action
        custom_config = custom_config.split("_")
        # check if the config is valid
        if len(custom_config) == 2 and custom_config[0] in config_types:
            format_configs.append({"type": custom_config[0], "filename": custom_config[1], "action": operation, "server_name": server_name})
        else:
            return handle_error(err_message=f"Invalid custom config {custom_config}", redirect_url="services", next=True)

    # Edit check fields and remove already existing ones
    for variable, value in variables.copy().items():
        if (
            variable in variables
            and variable != "SERVER_NAME"
            and value == config.get(f"{server_name}_{variable}" if request.form["operation"] == "edit" else variable, {"value": None})["value"]
        ):
            del variables[variable]

    variables = app.bw_config.check_variables(variables, config)
    return config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode


def update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged):
    if request.form["operation"] == "edit":
        if is_draft_unchanged and len(variables) == 1 and "SERVER_NAME" in variables and server_name == old_server_name:
            return handle_error("The service was not edited because no values were changed.", "services", True)

    if request.form["operation"] == "new" and not variables:
        return handle_error("The service was not created because all values had the default value.", "services", True)

    # Delete
    if request.form["operation"] == "delete":

        is_service = app.bw_config.check_variables({"SERVER_NAME": request.form["SERVER_NAME"]}, config)

        if not is_service:
            error_message(f"Error while deleting the service {request.form['SERVER_NAME']}")

        if config.get(f"{request.form['SERVER_NAME'].split(' ')[0]}_SERVER_NAME", {"method": "scheduler"})["method"] != "ui":
            return handle_error("The service cannot be deleted because it has not been created with the UI.", "services", True)

    db_metadata = app.db.get_metadata()

    def update_services(threaded: bool = False):
        wait_applying()

        manage_bunkerweb(
            "services",
            variables,
            old_server_name,
            variables.get("SERVER_NAME", ""),
            operation=operation,
            is_draft=is_draft,
            was_draft=was_draft,
            threaded=threaded,
        )

        if any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            app.data["RELOADING"] = True
            app.data["LAST_RELOAD"] = time()
            Thread(target=update_services, args=(True,)).start()
        else:
            update_services()

        app.data["CONFIG_CHANGED"] = True

    message = ""

    if request.form["operation"] == "new":
        message = f"Creating {'draft ' if is_draft else ''}service {variables.get('SERVER_NAME', '').split(' ')[0]}"
    elif request.form["operation"] == "edit":
        message = f"Saving configuration for {'draft ' if is_draft else ''}service {old_server_name.split(' ')[0]}"
    elif request.form["operation"] == "delete":
        message = f"Deleting {'draft ' if was_draft and is_draft else ''}service {request.form.get('SERVER_NAME', '').split(' ')[0]}"

    return message


@app.route("/modes", methods=["GET", "POST"])
@login_required
def services_modes():
    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "services")

        config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode = get_service_data("modes")
        message = update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged)
        # print(message, flush=True)
        # print("mode", mode, "service name", server_name, flush=True)
        # TODO: redirect to /mode?service_name=my_service&mode=my_mode
        # Following is not working :
        # return redirect(url_for("loading", next=url_for("modes", mode=mode, service_name=server_name), message=message))
        # or
        # return redirect(url_for("loading", next=url_for(f"modes?service_name={server_name}&mode={mode}"), message=message))
        return redirect(url_for("loading", next=url_for(request.endpoint), message=message))

    if not request.args.get("mode"):
        return handle_error("Mode type is missing to access /modes.", "services")

    mode = request.args.get("mode")
    service_name = request.args.get("service_name")
    total_config = app.db.get_config(methods=True, with_drafts=True)
    service_names = total_config["SERVER_NAME"]["value"].split(" ")

    if service_name and service_name not in service_names:
        return handle_error("Service name not found to access advanced mode.", "services")

    global_config = app.bw_config.get_config(global_only=True, methods=True)
    plugins = app.bw_config.get_plugins()

    builder = None
    templates_db = app.db.get_templates()

    if mode == "raw":
        builder = raw_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)
    elif mode == "advanced":
        builder = advanced_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)
    elif mode == "easy":
        builder = easy_mode_builder(templates_db, plugins, global_config, total_config, service_name or "new", not service_name)

    return render_template("modes.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/services", methods=["GET", "POST"])
@login_required
def services():
    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "services")

        config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode = get_service_data("services")

        message = update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged)

        return redirect(url_for("loading", next=url_for("services"), message=message))

    # Display services
    services = []
    tmp_config = app.db.get_config(methods=True, with_drafts=True).copy()
    service_names = tmp_config["SERVER_NAME"]["value"].split(" ")

    table_settings = (
        "USE_REVERSE_PROXY",
        "IS_DRAFT",
        "SERVE_FILES",
        "REMOTE_PHP",
        "AUTO_LETS_ENCRYPT",
        "USE_CUSTOM_SSL",
        "USE_MODSECURITY",
        "USE_BAD_BEHAVIOR",
        "USE_LIMIT_REQ",
        "USE_DNSBL",
        "SERVER_NAME",
    )

    for service in service_names:
        service_settings = {}

        # For each needed setting, get the service value if one, else the global (value), else default value
        for setting in table_settings:
            value = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"value": None}))["value"]
            method = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"method": None}))["method"]
            is_global = tmp_config.get(f"{service}_{setting}", tmp_config.get(setting, {"global": None}))["global"]
            service_settings[setting] = {"value": value, "method": method, "global": is_global}

        services.append(service_settings)

    services.sort(key=lambda x: x["SERVER_NAME"]["value"])

    builder = services_builder(services)
    return render_template("services.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config():
    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "global_config")

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        # Edit check fields and remove already existing ones
        config = app.db.get_config(methods=True, with_drafts=True)
        services = config["SERVER_NAME"]["value"].split(" ")
        for variable, value in variables.copy().items():
            setting = config.get(variable, {"value": None, "global": True})
            if setting["global"] and value == setting["value"]:
                del variables[variable]
                continue

        variables = app.bw_config.check_variables(variables, config)

        if not variables:
            return handle_error("The global configuration was not edited because no values were changed.", "global_config", True)

        for variable, value in variables.copy().items():
            for service in services:
                setting = config.get(f"{service}_{variable}", None)
                if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                    variables[f"{service}_{variable}"] = value

        db_metadata = app.db.get_metadata()

        def update_global_config(threaded: bool = False):
            wait_applying()

            manage_bunkerweb("global_config", variables, threaded=threaded)

        if "PRO_LICENSE_KEY" in variables:
            app.data["PRO_LOADING"] = True

        if any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            app.data["RELOADING"] = True
            app.data["LAST_RELOAD"] = time()
            Thread(target=update_global_config, args=(True,)).start()
        else:
            update_global_config()

        app.data["CONFIG_CHANGED"] = True

        with suppress(BaseException):
            if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                flash("Checking license key to upgrade.", "success")

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config"),
                message="Saving global configuration",
            )
        )

    global_config = app.bw_config.get_config(global_only=True, methods=True)
    plugins = app.bw_config.get_plugins()
    builder = global_config_builder({}, plugins, global_config)
    return render_template("global-config.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/configs", methods=["GET", "POST"])
@login_required
def configs():
    db_configs = app.db.get_custom_configs()

    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "configs")

        operation = ""

        verify_data_in_form(
            data={"operation": ("new", "edit", "delete"), "type": "file", "path": None},
            err_message="Invalid operation parameter on /configs.",
            redirect_url="configs",
            next=True,
        )

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        if variables["type"] != "file":
            return handle_error("Invalid type parameter on /configs.", "configs", True)

        # TODO: revamp this to use a path but a form to edit the content

        operation = app.bw_custom_configs.check_path(variables["path"])

        if operation:
            return handle_error(operation, "configs", True)

        old_name = variables.get("old_name", "").replace(".conf", "")
        name = variables.get("name", old_name).replace(".conf", "")
        path_exploded = variables["path"].split(sep)
        service_id = (path_exploded[5] if len(path_exploded) > 6 else None) or None
        root_dir = path_exploded[4].replace("-", "_").lower()

        if not old_name and not name:
            return handle_error("Missing name parameter on /configs.", "configs", True)

        index = -1
        for i, db_config in enumerate(db_configs):
            if db_config["type"] == root_dir and db_config["name"] == name and db_config["service_id"] == service_id:
                if request.form["operation"] == "new":
                    return handle_error(f"Config {name} already exists{f' for service {service_id}' if service_id else ''}", "configs", True)
                elif db_config["method"] not in ("ui", "manual"):
                    return handle_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it was not created by the UI or manually",
                        "configs",
                        True,
                    )
                index = i
                break

        # New or edit a config
        if request.form["operation"] in ("new", "edit"):
            if not app.bw_custom_configs.check_name(name):
                return handle_error(
                    f"Invalid {variables['type']} name. (Can only contain numbers, letters, underscores, dots and hyphens (min 4 characters and max 64))",
                    "configs",
                    True,
                )

            content = BeautifulSoup(variables["content"], "html.parser").get_text()

            if request.form["operation"] == "new":
                db_configs.append({"type": root_dir, "name": name, "service_id": service_id, "data": content, "method": "ui"})
                operation = f"Created config {name}{f' for service {service_id}' if service_id else ''}"
            elif request.form["operation"] == "edit":
                if index == -1:
                    return handle_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True
                    )

                if old_name != name:
                    db_configs[index]["name"] = name
                elif db_configs[index]["data"] == content:
                    return handle_error(
                        f"Config {name} was not edited because no values were changed{f' for service {service_id}' if service_id else ''}",
                        "configs",
                        True,
                    )

                db_configs[index]["data"] = content
                operation = f"Edited config {name}{f' for service {service_id}' if service_id else ''}"

        # Delete a config
        elif request.form["operation"] == "delete":
            if index == -1:
                return handle_error(f"Can't delete config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True)

            del db_configs[index]
            operation = f"Deleted config {name}{f' for service {service_id}' if service_id else ''}"

        error = app.db.save_custom_configs([config for config in db_configs if config["method"] == "ui"], "ui")
        if error:
            app.logger.error(f"Could not save custom configs: {error}")
            return handle_error("Couldn't save custom configs", "configs", True)

        app.data["CONFIG_CHANGED"] = True

        flash(operation)

        return redirect(url_for("loading", next=url_for("configs")))

    return render_template(
        "configs.html",
        folders=[
            path_to_dict(
                join(sep, "etc", "bunkerweb", "configs"),
                db_data=db_configs,
                services=app.bw_config.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",)).get("SERVER_NAME", "").split(" "),
            )
        ],
    )


@app.route("/plugins", methods=["GET", "POST"])
@login_required
def plugins():
    tmp_ui_path = TMP_DIR.joinpath("ui")

    if request.method == "POST":
        if app.db.readonly:
            return handle_error("Database is in read-only mode", "plugins")

        verify_data_in_form(
            data={"operation": ("delete"), "type": None},
            err_message="Missing type parameter for operation delete on /plugins.",
            redirect_url="plugins",
            next=True,
        )

        error = 0
        # Delete plugin
        if request.form["operation"] == "delete":

            # Check variables
            variables = deepcopy(request.form.to_dict())
            del variables["csrf_token"]

            if variables["type"] in ("core", "pro"):
                return handle_error(f"Can't delete {variables['type']} plugin {variables['name']}", "plugins", True)

            db_metadata = app.db.get_metadata()

            def update_plugins(threaded: bool = False):  # type: ignore
                wait_applying()

                plugins = app.bw_config.get_plugins(_type="external", with_data=True)
                for x, plugin in enumerate(plugins):
                    if plugin["id"] == variables["name"]:
                        del plugins[x]

                err = app.db.update_external_plugins(plugins)
                if err:
                    message = f"Couldn't update external plugins to database: {err}"
                    if threaded:
                        app.data["TO_FLASH"].append({"content": message, "type": "error"})
                    else:
                        error_message(message)
                else:
                    message = f"Deleted plugin {variables['name']} successfully"
                    if threaded:
                        app.data["TO_FLASH"].append({"content": message, "type": "success"})
                    else:
                        flash(message)

                app.data["RELOADING"] = False

            if any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            ):
                app.data["RELOADING"] = True
                app.data["LAST_RELOAD"] = time()

                Thread(target=update_plugins, args=(True,)).start()
            else:
                update_plugins()
        else:
            # Upload plugins
            if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
                return handle_error("Please upload new plugins to reload plugins", "plugins", True)

            errors = 0
            files_count = 0
            new_plugins = []
            new_plugins_ids = []

            for file in listdir(str(tmp_ui_path)):
                if not tmp_ui_path.joinpath(file).is_file():
                    continue

                files_count += 1
                folder_name = ""
                temp_folder_name = file.split(".")[0]
                temp_folder_path = tmp_ui_path.joinpath(temp_folder_name)
                is_dir = False

                try:
                    if file.endswith(".zip"):
                        try:
                            with ZipFile(str(tmp_ui_path.joinpath(file))) as zip_file:
                                try:
                                    zip_file.getinfo("plugin.json")
                                except KeyError:
                                    is_dir = True
                                zip_file.extractall(str(temp_folder_path))
                        except BadZipFile:
                            errors += 1
                            error = 1
                            message = f"{file} is not a valid zip file. ({folder_name or temp_folder_name})"
                            app.logger.exception(message)
                            flash(message, "error")
                    else:
                        try:
                            with tar_open(str(tmp_ui_path.joinpath(file)), errorlevel=2) as tar_file:
                                try:
                                    tar_file.getmember("plugin.json")
                                except KeyError:
                                    is_dir = True
                                try:
                                    # deepcode ignore TarSlip: We don't need to check for tar slip as we are checking the files when they are uploaded
                                    tar_file.extractall(str(temp_folder_path), filter="data")
                                except TypeError:
                                    # deepcode ignore TarSlip: We don't need to check for tar slip as we are checking the files when they are uploaded
                                    tar_file.extractall(str(temp_folder_path))
                        except ReadError:
                            errors += 1
                            error = 1
                            message = f"Couldn't read file {file} ({folder_name or temp_folder_name})"
                            app.logger.exception(message)
                            flash(message, "error")
                        except CompressionError:
                            errors += 1
                            error = 1
                            message = f"{file} is not a valid tar file ({folder_name or temp_folder_name})"
                            app.logger.exception(message)
                            flash(message, "error")
                        except HeaderError:
                            errors += 1
                            error = 1
                            message = f"The file plugin.json in {file} is not valid ({folder_name or temp_folder_name})"
                            app.logger.exception(message)
                            flash(message, "error")

                    if is_dir:
                        dirs = [d for d in listdir(str(temp_folder_path)) if temp_folder_path.joinpath(d).is_dir()]

                        if not dirs or len(dirs) > 1 or not temp_folder_path.joinpath(dirs[0], "plugin.json").is_file():
                            raise KeyError

                        for file_name in listdir(str(temp_folder_path.joinpath(dirs[0]))):
                            move(
                                str(temp_folder_path.joinpath(dirs[0], file_name)),
                                str(temp_folder_path.joinpath(file_name)),
                            )
                        rmtree(
                            str(temp_folder_path.joinpath(dirs[0])),
                            ignore_errors=True,
                        )

                    plugin_file = json_loads(temp_folder_path.joinpath("plugin.json").read_text(encoding="utf-8"))

                    if not all(key in plugin_file.keys() for key in PLUGIN_KEYS):
                        raise ValueError

                    folder_name = plugin_file["id"]

                    if not app.bw_custom_configs.check_name(folder_name):
                        errors += 1
                        error = 1
                        flash(
                            f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 64))",
                            "error",
                        )
                        raise Exception

                    plugin_content = BytesIO()
                    with tar_open(
                        fileobj=plugin_content,
                        mode="w:gz",
                        compresslevel=9,
                    ) as tar:
                        tar.add(
                            str(temp_folder_path),
                            arcname=temp_folder_name,
                            recursive=True,
                        )
                    plugin_content.seek(0)
                    value = plugin_content.getvalue()

                    new_plugins.append(
                        plugin_file
                        | {
                            "type": "external",
                            "page": "ui" in listdir(str(temp_folder_path)),
                            "method": "ui",
                            "data": value,
                            "checksum": sha256(value).hexdigest(),
                        }
                    )
                    new_plugins_ids.append(folder_name)
                except KeyError:
                    errors += 1
                    error = 1
                    flash(
                        f"{file} is not a valid plugin (plugin.json file is missing) ({folder_name or temp_folder_name})",
                        "error",
                    )
                except JSONDecodeError as e:
                    errors += 1
                    error = 1
                    flash(
                        f"The file plugin.json in {file} is not valid ({e.msg}: line {e.lineno} column {e.colno} (char {e.pos})) ({folder_name or temp_folder_name})",
                        "error",
                    )
                except ValueError:
                    errors += 1
                    error = 1
                    flash(
                        f"The file plugin.json is missing one or more of the following keys: <i>{', '.join(PLUGIN_KEYS)}</i> ({folder_name or temp_folder_name})",
                        "error",
                    )
                except FileExistsError:
                    errors += 1
                    error = 1
                    flash(
                        f"A plugin named {folder_name} already exists",
                        "error",
                    )
                except (TarError, OSError) as e:
                    errors += 1
                    error = 1
                    flash(str(e), "error")
                except Exception as e:
                    errors += 1
                    error = 1
                    flash(str(e), "error")
                finally:
                    if error != 1:
                        flash(f"Successfully created plugin: <b><i>{folder_name}</i></b>")

                    error = 0

            if errors >= files_count:
                return redirect(url_for("loading", next=url_for("plugins")))

            db_metadata = app.db.get_metadata()

            def update_plugins(threaded: bool = False):
                wait_applying()

                plugins = app.bw_config.get_plugins(_type="external", with_data=True)
                for plugin in deepcopy(plugins):
                    if plugin["id"] in new_plugins_ids:
                        flash(f"Plugin {plugin['id']} already exists", "error")
                        del new_plugins[new_plugins_ids.index(plugin["id"])]

                err = app.db.update_external_plugins(new_plugins, delete_missing=False)
                if err:
                    message = f"Couldn't update external plugins to database: {err}"
                    if threaded:
                        app.data["TO_FLASH"].append({"content": message, "type": "error"})
                    else:
                        flash(message, "error")
                else:
                    message = "Plugins uploaded successfully"
                    if threaded:
                        app.data["TO_FLASH"].append({"content": message, "type": "success"})
                    else:
                        flash("Plugins uploaded successfully")

                app.data["RELOADING"] = False

            if any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            ):
                app.data["RELOADING"] = True
                app.data["LAST_RELOAD"] = time()

                Thread(target=update_plugins, args=(True,)).start()
            else:
                update_plugins()

        return redirect(url_for("loading", next=url_for("plugins"), message="Reloading plugins"))

    # Remove tmp folder
    if tmp_ui_path.is_dir():
        rmtree(tmp_ui_path, ignore_errors=True)

    plugins = app.bw_config.get_plugins()
    plugins_internal = 0
    plugins_external = 0
    plugins_pro = 0

    for plugin in plugins:
        if plugin["type"] == "external":
            plugins_external += 1
        elif plugin["type"] == "pro":
            plugins_pro += 1
        else:
            plugins_internal += 1

    return render_template(
        "plugins.html",
        plugins_count_internal=plugins_internal,
        plugins_count_external=plugins_external,
        plugins_count_pro=plugins_pro,
    )


@app.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if app.db.readonly:
        return {"status": "ko", "message": "Database is in read-only mode"}, 403

    if not request.files:
        return {"status": "ko"}, 400

    tmp_ui_path = TMP_DIR.joinpath("ui")
    tmp_ui_path.mkdir(parents=True, exist_ok=True)

    for uploaded_file in request.files.values():
        if not uploaded_file.filename:
            continue

        if not uploaded_file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        file_name = Path(secure_filename(uploaded_file.filename)).name
        folder_name = file_name.replace(".tar.gz", "").replace(".tar.xz", "").replace(".zip", "")

        with BytesIO(uploaded_file.read()) as io:
            io.seek(0, 0)
            plugins = []
            if uploaded_file.filename.endswith(".zip"):
                with ZipFile(io) as zip_file:
                    for file in zip_file.namelist():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for file in zip_file.namelist():
                            if isabs(file) or ".." in file:
                                return {"status": "ko"}, 422

                        zip_file.extractall(str(tmp_ui_path) + "/")
            else:
                with tar_open(fileobj=io) as tar_file:
                    for file in tar_file.getnames():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for member in tar_file.getmembers():
                            if isabs(member.name) or ".." in member.name:
                                return {"status": "ko"}, 422

                        try:
                            # deepcode ignore TarSlip: The files in the tar are being inspected before extraction
                            tar_file.extractall(str(tmp_ui_path) + "/", filter="data")
                        except TypeError:
                            # deepcode ignore TarSlip: The files in the tar are being inspected before extraction
                            tar_file.extractall(str(tmp_ui_path) + "/")

            if len(plugins) <= 1:
                io.seek(0, 0)
                # deepcode ignore PT: The folder name is being sanitized before
                tmp_ui_path.joinpath(file_name).write_bytes(io.read())
                return {"status": "ok"}, 201

        for plugin in plugins:
            with BytesIO() as tgz:
                with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                    tf.add(str(tmp_ui_path.joinpath(folder_name, plugin)), arcname=plugin)
                tgz.seek(0, 0)
                tmp_ui_path.joinpath(f"{plugin}.tar.gz").write_bytes(tgz.read())

        # deepcode ignore PT: The folder name is being sanitized before
        rmtree(tmp_ui_path.joinpath(folder_name), ignore_errors=True)

    return {"status": "ok"}, 201


@app.route("/plugins/<plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin(plugin: str):
    if not PLUGIN_ID_RX.match(plugin):
        return error_message("Invalid plugin id, (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)"), 400

    # Case we ware looking for a plugin template
    # We need to check if a page exists, and if it does, we need to check if the plugin is activated and metrics are on
    if request.method == "GET":

        # Check plugin's page
        page = app.db.get_plugin_page(plugin)

        if not page:
            return error_message("The plugin does not have a page"), 404

        tmp_page_dir = TMP_DIR.joinpath("ui", "page", str(uuid4()))
        tmp_page_dir.mkdir(parents=True, exist_ok=True)

        with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar_file:
            tar_file.extractall(tmp_page_dir)

        tmp_page_dir = tmp_page_dir.joinpath("ui")

        app.logger.debug(f"Plugin {plugin} page extracted successfully")

        # Case template, prepare data
        plugins = app.bw_config.get_plugins()
        plugin_id = None
        curr_plugin = {}
        is_used = False
        use_key = False
        is_metrics_on = False
        context = "multisite"

        for plug in plugins:
            if plug["id"] == plugin:
                plugin_id = plug["id"]
                curr_plugin = plug
                break

        # Case no plugin found
        if plugin_id is None:
            return error_message("Plugin not found"), 404

        config = app.db.get_config()

        # Check if we are using metrics
        for service in config.get("SERVER_NAME", "").split(" "):
            # specific case
            if config.get(f"{service}_USE_METRICS", "yes") != "no":
                is_metrics_on = True
                break

        # Check if the plugin is used

        # Here we have specific cases for some plugins
        # {plugin_id: [[setting_name, setting_false], ...]}
        specific_cases = {
            "limit": [["USE_LIMIT_REQ", "no"], ["USE_LIMIT_CONN", "no"]],
            "misc": [["DISABLE_DEFAULT_SERVER", "no"], ["ALLOWED_METHODS", ""]],
            "modsecurity": [["USE_MODSECURITY", "no"]],
            "realip": [["USE_REALIP", "no"]],
            "reverseproxy": [["USE_REVERSE_PROXY", "no"]],
            "selfsigned": [["GENERATE_SELF_SIGNED_SSL", "no"]],
            "letsencrypt": [["AUTO_LETS_ENCRYPT", "no"]],
            "country": [["BLACKLIST_COUNTRY", ""], ["WHITELIST_COUNTRY", ""]],
        }

        # specific cases
        for key, data in curr_plugin["settings"].items():
            # specific cases
            if plugin_id in specific_cases:
                use_key = "SPECIFIC"
                context = data["context"]
                break

            # default case (one USE_)
            if key.upper().startswith("USE_"):
                use_key = key
                context = data["context"]
                break

        # Case USE_<NAME>, it means show only if used by one service
        if context == "global":
            if plugin_id in specific_cases:
                for key in specific_cases[plugin_id]:
                    setting_name = key[0]
                    setting_false = key[1]
                    if config.get(setting_name, setting_false) != setting_false:
                        is_used = True
                        break

            if config.get(use_key, "no") != "no":
                is_used = True

        if context == "multisite":
            for service in config.get("SERVER_NAME", "").split(" "):
                # specific case
                if plugin_id in specific_cases:
                    for key in specific_cases[plugin_id]:
                        setting_name = key[0]
                        setting_false = key[1]
                        if config.get(f"{service}_{setting_name}", setting_false) != setting_false:
                            is_used = True
                            break

                # general case
                if config.get(f"{service}_{use_key}", "no") != "no":
                    is_used = True
                    break

        # Get prerender from action.py
        pre_render = run_action(plugin, "pre_render", tmp_dir=tmp_page_dir)
        return render_template(
            # deepcode ignore Ssti: We trust the plugin template
            Environment(
                loader=FileSystemLoader((tmp_page_dir.as_posix() + "/", join(sep, "usr", "share", "bunkerweb", "ui", "templates") + "/")),
                autoescape=select_autoescape(["html"]),
            ).from_string(tmp_page_dir.joinpath("template.html").read_text(encoding="utf-8")),
            current_endpoint=plugin,
            plugin=curr_plugin,
            pre_render=pre_render,
            is_used=is_used,
            is_metrics=is_metrics_on,
            **app.jinja_env.globals,
        )

    rmtree(TMP_DIR.joinpath("ui", "page"), ignore_errors=True)

    action_result = run_action(plugin)

    if isinstance(action_result, Response):
        app.logger.info(f"Plugin {plugin} action executed successfully")
        return action_result

    # case error
    if action_result["status"] == "ko":
        return error_message(action_result["message"]), action_result["code"]

    app.logger.info(f"Plugin {plugin} action executed successfully")

    if request.content_type == "application/x-www-form-urlencoded":
        return redirect(f"{url_for('plugins')}/{plugin}", code=303)
    return jsonify({"message": "ok", "data": action_result["data"]}), 200


@app.route("/cache", methods=["GET"])
@login_required
def cache():
    return render_template(
        "cache.html",
        folders=[
            path_to_dict(
                join(sep, "var", "cache", "bunkerweb"),
                is_cache=True,
                db_data=app.db.get_jobs_cache_files(),
                services=app.bw_config.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",)).get("SERVER_NAME", "").split(" "),
            )
        ],
    )


@app.route("/logs", methods=["GET"])
@login_required
def logs():
    logs_path = Path(sep, "var", "log", "bunkerweb")

    files = []
    if logs_path.is_dir():
        for file in logs_path.glob("*.log"):
            if file.is_file():
                files.append(file.name)

    current_file = secure_filename(request.args.get("file", ""))

    if current_file and current_file not in files:
        return Response("No such file", 404)

    if isabs(current_file) or ".." in current_file:
        return error_message("Invalid file path", 400)

    raw_logs = ""
    if current_file:
        with logs_path.joinpath(current_file).open(encoding="utf-8") as f:
            raw_logs = f.read()

    builder = logs_builder(files, current_file, raw_logs)
    return render_template("logs.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/reports", methods=["GET"])
@login_required
def reports():
    reports = app.bw_instances_utils.get_reports()
    total_reports = len(reports)
    reports = reports[:100]

    # Prepare data
    reasons = {}
    codes = {}
    for i, report in enumerate(deepcopy(reports)):
        reports[i]["date"] = datetime.fromtimestamp(floor(reports[i]["date"])).strftime("%d/%m/%Y %H:%M:%S")
        # Get top reasons
        if not report["reason"] in reasons:
            reasons[report["reason"]] = 0
        reasons[report["reason"]] = reasons[report["reason"]] + 1
        # Get top status code
        if not report["status"] in codes:
            codes[report["status"]] = 0
        codes[report["status"]] = codes[report["status"]] + 1

    top_reason = ([k for k, v in reasons.items() if v == max(reasons.values())] or [""])[0]
    top_code = ([k for k, v in codes.items() if v == max(codes.values())] or [""])[0]

    return render_template(
        "reports.html",
        reports=reports,
        total_reports=total_reports,
        top_code=top_code,
        top_reason=top_reason,
    )


@app.route("/bans", methods=["GET", "POST"])
@login_required
def bans():
    if request.method == "POST":

        if app.db.readonly:
            return handle_error("Database is in read-only mode", "bans")

        # Check variables
        verify_data_in_form(data={"operation": ("ban", "unban")}, err_message="Invalid operation parameter on /bans.", redirect_url="bans")
        verify_data_in_form(data={"data": None}, err_message="Missing data parameter on /bans.", redirect_url="bans")

    redis_client = None
    db_config = app.bw_config.get_config(
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
    redis_host = db_config.get("REDIS_HOST")
    if use_redis and redis_host:
        redis_port = db_config.get("REDIS_PORT", "6379")
        if not redis_port.isdigit():
            redis_port = "6379"
        redis_port = int(redis_port)

        redis_db = db_config.get("REDIS_DB", "0")
        if not redis_db.isdigit():
            redis_db = "0"
        redis_db = int(redis_db)

        redis_timeout = db_config.get("REDIS_TIMEOUT", "1000.0")
        try:
            redis_timeout = float(redis_timeout)
        except ValueError:
            redis_timeout = 1000.0

        redis_keepalive_pool = db_config.get("REDIS_KEEPALIVE_POOL", "10")
        if not redis_keepalive_pool.isdigit():
            redis_keepalive_pool = "10"
        redis_keepalive_pool = int(redis_keepalive_pool)

        redis_ssl = db_config.get("REDIS_SSL", "no") == "yes"
        username = db_config.get("REDIS_USERNAME", None) or None
        password = db_config.get("REDIS_PASSWORD", None) or None
        sentinel_hosts = db_config.get("REDIS_SENTINEL_HOSTS", [])

        if isinstance(sentinel_hosts, str):
            sentinel_hosts = [host.split(":") if ":" in host else (host, "26379") for host in sentinel_hosts.split(" ") if host]

        if sentinel_hosts:
            sentinel_username = db_config.get("REDIS_SENTINEL_USERNAME", None) or None
            sentinel_password = db_config.get("REDIS_SENTINEL_PASSWORD", None) or None
            sentinel_master = db_config.get("REDIS_SENTINEL_MASTER", "")

            sentinel = Sentinel(
                sentinel_hosts,
                username=sentinel_username,
                password=sentinel_password,
                ssl=redis_ssl,
                socket_timeout=redis_timeout,
                socket_connect_timeout=redis_timeout,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
            )
            redis_client = sentinel.slave_for(sentinel_master, db=redis_db, username=username, password=password)
        else:
            redis_client = Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                username=username,
                password=password,
                socket_timeout=redis_timeout,
                socket_connect_timeout=redis_timeout,
                socket_keepalive=True,
                max_connections=redis_keepalive_pool,
                ssl=redis_ssl,
            )

        try:
            redis_client.ping()
        except BaseException:
            redis_client = None
            flash("Couldn't connect to redis, ban list might be incomplete", "error")

    def get_load_data():
        try:
            data = json_loads(request.form["data"])
            assert isinstance(data, list)
            return data
        except BaseException:
            return handle_error("Data must be a list of dict", "bans", False, "exception")

    if request.method == "POST" and request.form["operation"] == "unban":

        data = get_load_data()

        for unban in data:
            try:
                unban = json_loads(unban.replace('"', '"').replace("'", '"'))
            except BaseException:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                app.logger.exception(f"Couldn't unban {unban['ip']}")
                continue

            if "ip" not in unban:
                flash(f"Invalid unban: {unban}, skipping it ...", "error")
                continue

            if redis_client:
                if not redis_client.delete(f"bans_ip_{unban['ip']}"):
                    flash(f"Couldn't unban {unban['ip']} on redis", "error")

            resp = app.bw_instances_utils.unban(unban["ip"])
            if resp:
                flash(f"Couldn't unban {unban['ip']} on the following instances: {', '.join(resp)}", "error")
            else:
                flash(f"Successfully unbanned {unban['ip']}")

        return redirect(url_for("loading", next=url_for("bans"), message="Update bans"))

    if request.method == "POST" and request.form["operation"] == "ban":

        data = get_load_data()

        for ban in data:
            if not isinstance(ban, dict) or "ip" not in ban:
                flash(f"Invalid ban: {ban}, skipping it ...", "error")
                continue

            reason = ban.get("reason", "ui")
            ban_end = 86400.0
            if "ban_end" in ban:
                try:
                    ban_end = float(ban["ban_end"])
                except ValueError:
                    continue
                ban_end = (datetime.fromtimestamp(ban_end) - datetime.now()).total_seconds()

            if redis_client:
                ok = redis_client.set(f"bans_ip_{ban['ip']}", dumps({"reason": reason, "date": time()}))
                if not ok:
                    flash(f"Couldn't ban {ban['ip']} on redis", "error")
                redis_client.expire(f"bans_ip_{ban['ip']}", int(ban_end))

            resp = app.bw_instances_utils.ban(ban["ip"], ban_end, reason)
            if resp:
                flash(f"Couldn't ban {ban['ip']} on the following instances: {', '.join(resp)}", "error")
            else:
                flash(f"Successfully banned {ban['ip']}")

        return redirect(url_for("loading", next=url_for("bans"), message="Update bans"))

    bans = []
    if redis_client:
        for key in redis_client.scan_iter("bans_ip_*"):
            ip = key.decode("utf-8").replace("bans_ip_", "")
            data = redis_client.get(key)
            if not data:
                continue
            exp = redis_client.ttl(key)
            bans.append({"ip": ip, "exp": exp} | json_loads(data))  # type: ignore
    instance_bans = app.bw_instances_utils.get_bans()

    # Prepare data
    timestamp_now = time()

    for ban in instance_bans:
        if not any(b["ip"] == ban["ip"] for b in bans):
            bans.append(ban)

    # Get the last 100 bans
    bans = bans[:100]
    reasons = {"all"}
    remains = {"all"}

    for ban in bans:
        exp = ban.pop("exp", 0)
        # Add remain
        remain = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        ban["remain"] = remain[0]
        if remain[1] != "unknown":
            remains.add(remain[1])
        # Convert stamp to date
        ban["ban_start"] = datetime.fromtimestamp(floor(ban["date"])).strftime("%d/%m/%Y %H:%M:%S")
        ban["ban_end"] = datetime.fromtimestamp(floor(timestamp_now + exp)).strftime("%d/%m/%Y %H:%M:%S")
        reasons.add(["reason"])

    builder = bans_builder(bans, list(reasons), list(remains))
    return render_template("bans.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/jobs", methods=["GET"])
@login_required
def jobs():
    builder = jobs_builder(app.db.get_jobs())
    return render_template("jobs.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@app.route("/jobs/download", methods=["GET"])
@login_required
def jobs_download():
    plugin_id = request.args.get("plugin_id", "")
    job_name = request.args.get("job_name", None)
    file_name = request.args.get("file_name", None)
    service_id = request.args.get("service_id", "")

    if not plugin_id or not job_name or not file_name:
        return jsonify({"status": "ko", "message": "plugin_id, job_name and file_name are required"}), 422

    cache_file = app.db.get_job_cache_file(job_name, file_name, service_id=service_id, plugin_id=plugin_id)

    if not cache_file:
        return jsonify({"status": "ko", "message": "file not found"}), 404

    file = BytesIO(cache_file)
    # deepcode ignore PT: We sanitize the file name
    return send_file(file, as_attachment=True, download_name=file_name)


@app.route("/login", methods=["GET", "POST"])
def login():
    admin_user = app.db.get_ui_user()
    if not admin_user:
        return redirect(url_for("setup"))
    elif current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home"))

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        app.logger.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")

        ui_user = app.db.get_ui_user(username=request.form["username"])
        if ui_user and ui_user.username == request.form["username"] and ui_user.check_password(request.form["password"]):
            # log the user in
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False

            ui_user.last_login_at = datetime.now()
            ui_user.last_login_ip = request.remote_addr
            ui_user.login_count += 1

            app.db.mark_ui_user_login(ui_user.username, ui_user.last_login_at, ui_user.last_login_ip)

            if not login_user(ui_user, remember=request.form.get("remember") == "on"):
                flash("Couldn't log you in, please try again", "error")
                return (render_template("login.html", error="Couldn't log you in, please try again"),)

            app.logger.info(
                f"User {ui_user.username} logged in successfully for the {str(ui_user.login_count) + ('th' if 10 <= ui_user.login_count % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(ui_user.login_count % 10, 'th'))} time"
                + (" with remember me" if request.form.get("remember") == "on" else "")
            )

            # redirect him to the page he originally wanted or to the home page
            return redirect(url_for("loading", next=request.form.get("next") or url_for("home")))
        else:
            flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": bool(current_user.totp_secret),
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200


@app.route("/check_reloading")
@login_required
def check_reloading():
    app.data.load_from_file()

    if not app.data.get("RELOADING", False) or app.data.get("LAST_RELOAD", 0) + 60 < time():
        if app.data.get("RELOADING", False):
            app.logger.warning("Reloading took too long, forcing the state to be reloaded")
            flash("Forced the status to be reloaded", "error")
            app.data["RELOADING"] = False

        for f in app.data.get("TO_FLASH", []):
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

        app.data["TO_FLASH"] = []

    return jsonify({"reloading": app.data.get("RELOADING", False)})


@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    response = redirect(url_for("login"))
    response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage", "executionContexts"'
    return response
