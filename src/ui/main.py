#!/usr/bin/env python3

from contextlib import suppress
from math import floor
from os import _exit, getenv, getpid, listdir, sep, urandom
from os.path import basename, dirname, join
from secrets import choice
from string import ascii_letters, digits
from sys import path as sys_path, modules as sys_modules
from pathlib import Path
from typing import Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bs4 import BeautifulSoup
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse as dateutil_parse
from docker import DockerClient
from docker.errors import NotFound as docker_NotFound, APIError as docker_APIError, DockerException
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, LoginManager, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from glob import glob
from hashlib import sha256
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, dumps, loads as json_loads
from jinja2 import Environment, FileSystemLoader
from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.exceptions import ApiException as kube_ApiException
from redis import Redis, Sentinel
from regex import compile as re_compile, match as regex_match
from requests import get
from shutil import move, rmtree
from signal import SIGINT, signal, SIGTERM
from subprocess import PIPE, Popen, call
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from threading import Thread
from tempfile import NamedTemporaryFile
from time import sleep, time
from zipfile import BadZipFile, ZipFile

from src.Instances import Instances
from src.ConfigFiles import ConfigFiles
from src.Config import Config
from src.ReverseProxied import ReverseProxied
from src.User import AnonymousUser, User

from utils import check_settings, get_b64encoded_qr_image, path_to_dict, get_remain
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from logging import getLogger


def stop_gunicorn():
    p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
    out, _ = p.communicate()
    pid = out.strip().decode().split("\n")[0]
    call(["kill", "-SIGTERM", pid])


def stop(status, _stop=True):
    Path(sep, "var", "run", "bunkerweb", "ui.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "ui.healthy").unlink(missing_ok=True)
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
app.config["SECRET_KEY"] = getenv("FLASK_SECRET", urandom(32))

PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)
app.logger = setup_logger("UI")

gunicorn_access_logger = getLogger("gunicorn.access")
gunicorn_access_logger.setLevel(app.logger.level)
gunicorn_logger = getLogger("gunicorn.error")
gunicorn_logger.setLevel(app.logger.level)
werkzeug_logger = getLogger("werkzeug")
werkzeug_logger.setLevel(app.logger.level)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.anonymous_user = AnonymousUser
PLUGIN_KEYS = ["id", "name", "description", "version", "stream", "settings"]

INTEGRATION = "Linux"
integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
if getenv("KUBERNETES_MODE", "no").lower() == "yes":
    INTEGRATION = "Kubernetes"
elif getenv("SWARM_MODE", "no").lower() == "yes":
    INTEGRATION = "Swarm"
elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
    INTEGRATION = "Autoconf"
elif integration_path.is_file():
    INTEGRATION = integration_path.read_text(encoding="utf-8").strip()

del integration_path

docker_client = None
kubernetes_client = None
if INTEGRATION in ("Docker", "Swarm", "Autoconf"):
    try:
        docker_client: DockerClient = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))
    except (docker_APIError, DockerException):
        app.logger.warning("No docker host found")
elif INTEGRATION == "Kubernetes":
    kube_config.load_incluster_config()
    kubernetes_client = kube_client.CoreV1Api()

db = Database(app.logger, ui=True)

if INTEGRATION in ("Swarm", "Kubernetes", "Autoconf"):
    while not db.is_autoconf_loaded():
        app.logger.warning("Autoconf is not loaded yet in the database, retrying in 5s ...")
        sleep(5)

while not db.is_initialized():
    app.logger.warning("Database is not initialized, retrying in 5s ...")
    sleep(5)

USER = "Error"
while USER == "Error":
    with suppress(Exception):
        USER = db.get_ui_user()

USER_PASSWORD_RX = re_compile(r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,./:;<=>?@[\\\]^_`{|}~-]).{8,}$")

if USER:
    USER = User(**USER)

    if getenv("ADMIN_USERNAME") or getenv("ADMIN_PASSWORD"):
        if USER.method == "manual":
            updated = False
            if getenv("ADMIN_USERNAME", "") and USER.get_id() != getenv("ADMIN_USERNAME", ""):
                USER.id = getenv("ADMIN_USERNAME", "")
                updated = True
            if getenv("ADMIN_PASSWORD", "") and not USER.check_password(getenv("ADMIN_PASSWORD", "")):
                USER.update_password(getenv("ADMIN_PASSWORD", ""))
                updated = True

            if updated:
                ret = db.update_ui_user(USER.get_id(), USER.password_hash, USER.is_two_factor_enabled, USER.secret_token)
                if ret:
                    app.logger.error(f"Couldn't update the admin user in the database: {ret}")
                    stop(1)
                app.logger.info("The admin user was updated successfully")
        else:
            app.logger.warning("The admin user wasn't created manually. You can't change it from the environment variables.")
elif getenv("ADMIN_USERNAME") and getenv("ADMIN_PASSWORD"):
    if not getenv("FLASK_DEBUG", False):
        if len(getenv("ADMIN_USERNAME", "admin")) > 256:
            app.logger.error("The admin username is too long. It must be less than 256 characters.")
            stop(1)
        elif not USER_PASSWORD_RX.match(getenv("ADMIN_PASSWORD", "changeme")):
            app.logger.error(
                "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
            )
            stop(1)

    user_name = getenv("ADMIN_USERNAME", "admin")
    USER = User(user_name, getenv("ADMIN_PASSWORD", "changeme"))
    ret = db.create_ui_user(user_name, USER.password_hash)

    if ret:
        app.logger.error(f"Couldn't create the admin user in the database: {ret}")
        stop(1)

app.logger.info("Database is ready")
Path(sep, "var", "run", "bunkerweb", "ui.pid").write_text(str(getpid()), encoding="utf-8")
Path(sep, "var", "tmp", "bunkerweb", "ui.healthy").write_text("ok", encoding="utf-8")
bw_version = Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()

try:
    app.config.update(
        DEBUG=True,
        INSTANCES=Instances(docker_client, kubernetes_client, INTEGRATION),
        CONFIG=Config(db),
        CONFIGFILES=ConfigFiles(),
        WTF_CSRF_SSL_STRICT=False,
        USER=USER,
        SEND_FILE_MAX_AGE_DEFAULT=86400,
        RELOADING=False,
        LAST_RELOAD=0,
        TO_FLASH=[],
        DARK_MODE=False,
        CURRENT_TOTP_TOKEN=None,
        SCRIPT_NONCE=sha256(urandom(32)).hexdigest(),
        DB=db,
    )
except FileNotFoundError as e:
    app.logger.error(repr(e), e.filename)
    stop(1)

plugin_id_rx = re_compile(r"^[\w_-]{1,64}$")

# Declare functions for jinja2
app.jinja_env.globals.update(check_settings=check_settings)

# CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
REVERSE_PROXY_PATH = re_compile(r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$")


def manage_bunkerweb(method: str, *args, operation: str = "reloads", is_draft: bool = False, was_draft: bool = False):
    # Do the operation
    error = False
    if method == "services":
        service_custom_confs = glob(join(sep, "etc", "bunkerweb", "configs", "*", args[1].split(" ")[0]))
        moved = False
        deleted = False

        if operation == "new":
            operation, error = app.config["CONFIG"].new_service(args[0], is_draft=is_draft)
        elif operation == "edit":
            if args[1].split(" ")[0] != args[2].split(" ")[0] and service_custom_confs:
                for service_custom_conf in service_custom_confs:
                    if listdir(service_custom_conf):
                        move(service_custom_conf, service_custom_conf.replace(f"{sep}{args[1].split(' ')[0]}", f"{sep}{args[2].split(' ')[0]}"))
                        moved = True
            operation, error = app.config["CONFIG"].edit_service(
                args[1], args[0], check_changes=(was_draft != is_draft or not is_draft) and not moved, is_draft=is_draft
            )
        elif operation == "delete":
            for service_custom_conf in glob(join(sep, "etc", "bunkerweb", "configs", "*", args[2].split(" ")[0])):
                if listdir(service_custom_conf):
                    rmtree(service_custom_conf, ignore_errors=True)
                    deleted = True
            operation, error = app.config["CONFIG"].delete_service(args[2], check_changes=(was_draft != is_draft or not is_draft) and not deleted)

        if error:
            app.config["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            app.config["TO_FLASH"].append({"content": operation, "type": "success"})

            if (was_draft != is_draft or not is_draft) and (moved or deleted):
                # update changes in db
                ret = db.checked_changes(["config", "custom_configs"], value=True)
                if ret:
                    app.logger.error(f"Couldn't set the changes to checked in the database: {ret}")
                    app.config["TO_FLASH"].append(
                        {"content": f"An error occurred when setting the changes to checked in the database : {ret}", "type": "error"}
                    )
    if method == "global_config":
        operation = app.config["CONFIG"].edit_global_conf(args[0])
    elif method == "plugins":
        app.config["CONFIG"].reload_config()

    if operation == "reload":
        operation = app.config["INSTANCES"].reload_instance(args[0])
    elif operation == "start":
        operation = app.config["INSTANCES"].start_instance(args[0])
    elif operation == "stop":
        operation = app.config["INSTANCES"].stop_instance(args[0])
    elif operation == "restart":
        operation = app.config["INSTANCES"].restart_instance(args[0])
    elif not error:
        operation = "The scheduler will be in charge of reloading the instances."
    else:
        operation = ""

    if operation:
        if isinstance(operation, list):
            for op in operation:
                app.config["TO_FLASH"].append({"content": f"Reload failed for the instance {op}", "type": "error"})
        elif operation.startswith("Can't"):
            app.config["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            app.config["TO_FLASH"].append({"content": operation, "type": "success"})

    app.config["RELOADING"] = False


# UTILS
def run_action(plugin: str, function_name: str = ""):
    message = ""
    module = db.get_plugin_actions(plugin)

    if module is None:
        return {"status": "ko", "code": 404, "message": "The actions.py file for the plugin does not exist"}

    try:
        # Try to import the custom plugin
        with NamedTemporaryFile(mode="wb", suffix=".py", delete=True) as temp:
            temp.write(module)
            temp.flush()
            temp.seek(0)
            loader = SourceFileLoader("actions", temp.name)
            actions = loader.load_module()
    except:
        return {"status": "ko", "code": 500, "message": "An error occurred while importing the plugin, see logs for more details"}

    res = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, function_name or plugin)
        queries = request.args.to_dict()
        try:
            data = request.json or False
        except:
            data = {}

        res = method(app=app, args=queries, data=data)
    except AttributeError:
        message = "The plugin does not have a method, see logs for more details"
    except:
        message = "An error occurred while executing the plugin, see logs for more details"
    finally:
        if sbin_nginx_path.is_file():
            # Remove the custom plugin from the shared library
            if sys_path:
                sys_path.pop()
            sys_modules.pop("actions", None)
            del actions

        if message or not isinstance(res, dict) and not res:
            return {"status": "ko", "code": 500, "message": message or "The plugin did not return a valid response"}

    return {"status": "ok", "code": 200, "data": res}


def is_request_form(url_name: str, next: bool = False):
    if not request.form:
        flash("Missing form data.", "error")
        return redirect(url_for(url_name))


def is_request_params(params: list, url_name: str, next: bool = False):
    for param in params:
        if param not in request.form:
            flash(f"Missing {param} parameter.", "error")
            if next:
                return redirect(url_for("loading", next=url_for(url_name)))

            return redirect(url_for(url_name))


def redirect_flash_error(message: str, url_name: str, next: bool = False, log: Union[bool, str] = False):
    flash(message, "error")

    if log == "error":
        app.logger.error(message)

    if log == "exception":
        app.logger.exception(message)

    if next:
        return redirect(url_for("loading", next=url_for(url_name)))

    return redirect(url_for(url_name))


def error_message(msg: str):
    app.logger.error(msg)
    return {"status": "ko", "message": msg}


@app.before_request
def generate_nonce():
    app.config["SCRIPT_NONCE"] = sha256(urandom(32)).hexdigest()


@app.context_processor
def inject_variables():
    metadata = db.get_metadata()

    # check that is value is in tuple
    return dict(
        dark_mode=app.config["DARK_MODE"],
        script_nonce=app.config["SCRIPT_NONCE"],
        is_pro_version=metadata["is_pro"],
        pro_status=metadata["pro_status"],
        pro_services=metadata["pro_services"],
        pro_expire=metadata["pro_expire"],
        pro_overlapped=metadata["pro_overlapped"],
        plugins=app.config["CONFIG"].get_plugins(),
    )


@app.after_request
def set_csp_header(response):
    """Set the Content-Security-Policy header to prevent XSS attacks."""
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com;"
        + f" script-src 'self' 'nonce-{app.config['SCRIPT_NONCE']}';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: https://assets.bunkerity.com;"
        + " font-src 'self' data:;"
        + (" connect-src *;" if not app.config["USER"] else "")
    )
    return response


@login_manager.user_loader
def load_user(user_id):
    db_user = db.get_ui_user()
    if not db_user:
        app.logger.warning("Couldn't get the admin user from the database.")
        return None
    user = User(**db_user)
    return user if user_id == user.get_id() else None


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    session.clear()
    logout_user()
    flash("Wrong CSRF token !", "error")
    if not app.config["USER"]:
        return render_template("setup.html"), 403
    return render_template("login.html", is_totp=current_user.is_two_factor_enabled), 403


@app.before_request
def before_request():
    if current_user.is_authenticated:
        passed = True

        # Go back from totp to login
        if (
            not session.get("totp_validated", False)
            and current_user.is_two_factor_enabled
            and "/totp" not in request.path
            and not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts"))
            and request.path.endswith("/login")
        ):
            return redirect(url_for("login", next=request.path))

        # Case not login page, keep on 2FA before any other access
        if (
            not session.get("totp_validated", False)
            and current_user.is_two_factor_enabled
            and "/totp" not in request.path
            and not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts"))
        ):
            return redirect(url_for("totp", next=request.form.get("next")))
        elif session.get("ip") != request.remote_addr:
            passed = False
        elif session.get("user_agent") != request.headers.get("User-Agent"):
            passed = False

        if not passed:
            logout_user()
            session.clear()


@app.route("/", strict_slashes=False)
def index():
    if app.config["USER"]:
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
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home"))

    db_config = app.config["CONFIG"].get_config(methods=False)

    for server_name in db_config["SERVER_NAME"].split(" "):
        if db_config.get(f"{server_name}_USE_UI", "no") == "yes":
            return redirect(url_for("login"), 301)

    if request.method == "POST":

        is_request_form("setup")

        if not any(key in request.form for key in ("admin_username", "admin_password", "admin_password_check", "server_name", "ui_host", "ui_url")):
            return redirect_flash_error(
                "Missing either admin_username, admin_password, admin_password_check, server_name, ui_host, ui_url or auto_lets_encrypt parameter.", "setup"
            )

        if len(request.form["admin_username"]) > 256:
            return redirect_flash_error("The admin username is too long. It must be less than 256 characters.", "setup")

        if request.form["admin_password"] != request.form["admin_password_check"]:
            return redirect_flash_error("The passwords do not match.", "setup")

        if not USER_PASSWORD_RX.match(request.form["admin_password"]):
            return redirect_flash_error(
                "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).",
                "setup",
            )

        server_names = db_config["SERVER_NAME"].split(" ")
        if request.form["server_name"] in server_names:
            return redirect_flash_error(f"The hostname {request.form['server_name']} is already in use.", "setup")
        else:
            for server_name in server_names:
                if request.form["server_name"] in db_config.get(f"{server_name}_SERVER_NAME", "").split(" "):
                    return redirect_flash_error(f"The hostname {request.form['server_name']} is already in use.", "setup")

        if not REVERSE_PROXY_PATH.match(request.form["ui_host"]):
            return redirect_flash_error("The hostname is not valid.", "setup")

        app.config["USER"] = User(request.form["admin_username"], request.form["admin_password"], method="ui")

        ret = db.create_ui_user(request.form["admin_username"], app.config["USER"].password_hash, method="ui")
        if ret:
            return redirect_flash_error(f"Couldn't create the admin user in the database: {ret}", "setup", False, "error")

        flash("The admin user was created successfully", "success")

        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=(
                "services",
                {
                    "SERVER_NAME": request.form["server_name"],
                    "USE_UI": "yes",
                    "USE_REVERSE_PROXY": "yes",
                    "REVERSE_PROXY_HOST": request.form["ui_host"],
                    "REVERSE_PROXY_URL": request.form["ui_url"] or "/",
                    "AUTO_LETS_ENCRYPT": request.form.get("auto_lets_encrypt", "no"),
                    "INTERCEPTED_ERROR_CODES": "400 404 405 413 429 500 501 502 503 504",
                },
                request.form["server_name"],
                request.form["server_name"],
            ),
            kwargs={"operation": "new"},
        ).start()

        return Response(status=200)

    return render_template(
        "setup.html",
        username=getenv("ADMIN_USERNAME", ""),
        password=getenv("ADMIN_PASSWORD", ""),
        ui_host=db_config.get("UI_HOST", getenv("UI_HOST", "")),
        random_url=f"/{''.join(choice(ascii_letters + digits) for _ in range(10))}",
    )


@app.route("/totp", methods=["GET", "POST"])
@login_required
def totp():
    if request.method == "POST":

        is_request_form("totp")

        is_request_params(["totp_token"], "totp")

        if not current_user.check_otp(request.form["totp_token"]):
            return redirect_flash_error("The token is invalid.", "totp")

        session["totp_validated"] = True
        redirect(url_for("loading", next=request.form.get("next") or url_for("home")))

    if not current_user.is_two_factor_enabled or session.get("totp_validated", False):
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

    instances = app.config["INSTANCES"].get_instances()
    config = app.config["CONFIG"].get_config(with_drafts=True)
    instance_health_count = 0

    for instance in instances:
        if instance.health is True:
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

    return render_template(
        "home.html",
        check_version=not remote_version or bw_version == remote_version,
        remote_version=remote_version,
        version=bw_version,
        instances_number=len(instances),
        services_number=services,
        plugins_errors=db.get_plugins_errors(),
        instance_health_count=instance_health_count,
        services_scheduler_count=services_scheduler_count,
        services_ui_count=services_ui_count,
        services_autoconf_count=services_autoconf_count,
        username=current_user.get_id(),
    )


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        # Check form data validity
        is_request_form("account")

        if request.form["operation"] not in ("username", "password", "totp", "activate-key"):
            return redirect_flash_error("Invalid operation parameter.", "account")

        if request.form["operation"] == "activate-key":
            is_request_params(["license"], "account")

            if len(request.form["license"]) == 0:
                return redirect_flash_error("The license key is empty", "account")

            variable = {}
            variable["PRO_LICENSE_KEY"] = request.form["license"]

            error = app.config["CONFIG"].check_variables(variable)

            if error:
                return redirect_flash_error("The license key variable checks returned error", "account", True)

            # Force job to contact PRO API
            # by setting the last check to None
            metadata = db.get_metadata()
            metadata["last_pro_check"] = None
            db.set_pro_metadata(metadata)

            # Reload instances
            app.config["RELOADING"] = True
            app.config["LAST_RELOAD"] = time()
            Thread(
                target=manage_bunkerweb,
                name="Reloading instances",
                args=(
                    "global_config",
                    variable,
                ),
            ).start()

            flash("Checking license key to upgrade.", "success")

            return redirect(
                url_for(
                    "loading",
                    next=url_for("account"),
                    message="Saving license key",
                )
            )

        is_request_params(["operation", "curr_password"], "account")

        if not current_user.check_password(request.form["curr_password"]):
            return redirect_flash_error(f"The current password is incorrect. ({request.form['operation']})", "account")

        username = current_user.get_id()
        password = request.form["curr_password"]
        is_two_factor_enabled = current_user.is_two_factor_enabled
        secret_token = current_user.secret_token

        if request.form["operation"] == "username":
            is_request_params(["admin_username"], "account")

            if len(request.form["admin_username"]) > 256:
                return redirect_flash_error("The admin username is too long. It must be less than 256 characters. (username)", "account")

            username = request.form["admin_username"]

            session.clear()
            logout_user()

        if request.form["operation"] == "password":

            is_request_params(["admin_password", "admin_password_check"], "account")

            if request.form["admin_password"] != request.form["admin_password_check"]:
                return redirect_flash_error("The passwords do not match. (password)", "account")

            if not USER_PASSWORD_RX.match(request.form["admin_password"]):
                return redirect_flash_error(
                    "The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). (password)",
                    "account",
                )

            password = request.form["admin_password"]

            session.clear()
            logout_user()

        if request.form["operation"] == "totp":

            is_request_params(["totp_token"], "account")

            if not current_user.check_otp(request.form["totp_token"], secret=app.config["CURRENT_TOTP_TOKEN"]):
                return redirect_flash_error("The totp token is invalid. (totp)", "account")

            session["totp_validated"] = not current_user.is_two_factor_enabled
            is_two_factor_enabled = session["totp_validated"]
            secret_token = None if current_user.is_two_factor_enabled else app.config["CURRENT_TOTP_TOKEN"]
            app.config["CURRENT_TOTP_TOKEN"] = None

        user = User(username, password, is_two_factor_enabled=is_two_factor_enabled, secret_token=secret_token, method=current_user.method)
        ret = db.update_ui_user(
            username, user.password_hash, is_two_factor_enabled, secret_token, current_user.method if request.form["operation"] == "totp" else "ui"
        )
        if ret:
            return redirect_flash_error(f"Couldn't update the admin user in the database: {ret}", "account", False, "error")

        flash(
            (
                f"The {request.form['operation']} has been successfully updated."
                if request.form["operation"] != "totp"
                else f"The two-factor authentication was successfully {'disabled' if current_user.is_two_factor_enabled else 'enabled'}."
            ),
        )

        return redirect(url_for("account" if request.form["operation"] == "totp" else "login"))

    secret_token = ""
    totp_qr_image = ""

    if not current_user.is_two_factor_enabled:
        current_user.refresh_totp()
        secret_token = current_user.secret_token
        totp_qr_image = get_b64encoded_qr_image(current_user.get_authentication_setup_uri())
        app.config["CURRENT_TOTP_TOKEN"] = secret_token

    return render_template(
        "account.html",
        username=current_user.get_id(),
        is_totp=current_user.is_two_factor_enabled,
        secret_token=secret_token,
        totp_qr_image=totp_qr_image,
    )


@app.route("/instances", methods=["GET", "POST"])
@login_required
def instances():
    # Manage instances
    if request.method == "POST":

        is_request_params(["operation", "INSTANCE_ID"], "instances", True)

        # Check operation
        if request.form["operation"] not in (
            "reload",
            "start",
            "stop",
            "restart",
        ):
            return redirect_flash_error("Missing operation parameter on /instances.", "instances")
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("instances", request.form["INSTANCE_ID"]),
            kwargs={"operation": request.form["operation"]},
        ).start()

        return redirect(
            url_for(
                "loading",
                next=url_for("instances"),
                message=(f"{request.form['operation'].title()}ing" if request.form["operation"] != "stop" else "Stopping") + " instance",
            )
        )

    # Display instances
    instances = app.config["INSTANCES"].get_instances()
    return render_template("instances.html", title="Instances", instances=instances, username=current_user.get_id())


@app.route("/services", methods=["GET", "POST"])
@login_required
def services():
    if request.method == "POST":

        is_request_params(["operation", "is_draft"], "services", True)

        # Check operation
        if request.form["operation"] not in ("new", "edit", "delete"):
            return redirect_flash_error("Missing operation parameter on /services.", "services")

        if request.form["is_draft"] not in ("yes", "no"):
            return redirect_flash_error("Missing is_draft parameter on /services.", "services")

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]
        is_draft = variables.pop("is_draft", "no") == "yes"

        if "OLD_SERVER_NAME" not in request.form and request.form["operation"] == "edit":
            return redirect_flash_error("Missing OLD_SERVER_NAME parameter.", "services", True)

        if "SERVER_NAME" not in variables:
            variables["SERVER_NAME"] = variables["OLD_SERVER_NAME"]

        config = app.config["CONFIG"].get_config(methods=False, with_drafts=True)
        server_name = variables["SERVER_NAME"].split(" ")[0]
        was_draft = config.get(f"{server_name}_IS_DRAFT", "no") == "yes"

        if request.form["operation"] in ("new", "edit"):
            del variables["operation"]
            del variables["OLD_SERVER_NAME"]

            # Edit check fields and remove already existing ones
            for variable, value in deepcopy(variables).items():
                if variable == "IS_DRAFT" or variable.endswith("SCHEMA"):
                    del variables[variable]
                    continue

                if value == "on":
                    value = "yes"
                elif value == "off":
                    value = "no"

                if (
                    variable in variables
                    and variable != "SERVER_NAME"
                    and value == config.get(f"{server_name}_{variable}" if request.form["operation"] == "edit" else variable, None)
                ):
                    del variables[variable]

            if (
                was_draft == is_draft
                and request.form["operation"] == "edit"
                and len(variables) == 1
                and "SERVER_NAME" in variables
                and variables["SERVER_NAME"] == request.form.get("OLD_SERVER_NAME", "")
            ):
                return redirect_flash_error("The service was not edited because no values were changed.", "services", True)

            elif request.form["operation"] == "new" and not variables:
                return redirect_flash_error("The service was not created because all values had the default value.", "services", True)

            error = app.config["CONFIG"].check_variables(variables)

            if error:
                error_message("The config variable checks returned error")

        # Delete
        if request.form["operation"] == "delete":

            is_request_params(["SERVER_NAME"], "services", True)

            error = app.config["CONFIG"].check_variables({"SERVER_NAME": request.form["SERVER_NAME"]})

            if error:
                error_message(f"Error while deleting the service {request.form['SERVER_NAME']}")

        error = 0

        # Reload instances
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("services", variables, request.form.get("OLD_SERVER_NAME", ""), variables.get("SERVER_NAME", "")),
            kwargs={"operation": request.form["operation"], "is_draft": is_draft, "was_draft": was_draft},
        ).start()

        message = ""

        if request.form["operation"] == "new":
            message = f"Creating {'draft ' if is_draft else ''}service {variables.get('SERVER_NAME', '').split(' ')[0]}"
        elif request.form["operation"] == "edit":
            message = f"Saving configuration for {'draft ' if is_draft else ''}service {request.form.get('OLD_SERVER_NAME', '').split(' ')[0]}"
        elif request.form["operation"] == "delete":
            message = f"Deleting {'draft ' if was_draft and is_draft else ''}service {request.form.get('SERVER_NAME', '').split(' ')[0]}"

        return redirect(url_for("loading", next=url_for("services"), message=message))

    # Display services
    services = []
    global_config = app.config["CONFIG"].get_config(with_drafts=True)
    service_names = global_config["SERVER_NAME"]["value"].split(" ")
    for service in service_names:
        service_settings = []
        tmp_config = global_config.copy()

        for key, value in tmp_config.copy().items():
            if key.startswith(f"{service}_"):
                setting = key.replace(f"{service}_", "")
                service_settings.append(setting)
                tmp_config[setting] = tmp_config.pop(key)
            elif any(key.startswith(f"{s}_") for s in service_names):
                tmp_config.pop(key)
            elif key not in service_settings:
                tmp_config[key] = {"value": value["value"], "global": value["global"], "method": value["method"]}

        services.append(
            {
                "SERVER_NAME": {
                    "value": tmp_config["SERVER_NAME"]["value"].split(" ")[0],
                    "full_value": tmp_config["SERVER_NAME"]["value"],
                    "method": tmp_config["SERVER_NAME"]["method"],
                },
                "IS_DRAFT": tmp_config.pop("IS_DRAFT", {"value": "no"})["value"],
                "USE_REVERSE_PROXY": tmp_config["USE_REVERSE_PROXY"],
                "SERVE_FILES": tmp_config["SERVE_FILES"],
                "REMOTE_PHP": tmp_config["REMOTE_PHP"],
                "AUTO_LETS_ENCRYPT": tmp_config["AUTO_LETS_ENCRYPT"],
                "USE_CUSTOM_SSL": tmp_config["USE_CUSTOM_SSL"],
                "GENERATE_SELF_SIGNED_SSL": tmp_config["GENERATE_SELF_SIGNED_SSL"],
                "USE_MODSECURITY": tmp_config["USE_MODSECURITY"],
                "USE_BAD_BEHAVIOR": tmp_config["USE_BAD_BEHAVIOR"],
                "USE_LIMIT_REQ": tmp_config["USE_LIMIT_REQ"],
                "USE_DNSBL": tmp_config["USE_DNSBL"],
                "settings": dumps(tmp_config),
            }
        )

    return render_template(
        "services.html",
        services=services,
        global_config=global_config,
        username=current_user.get_id(),
    )


@app.route("/global_config", methods=["GET", "POST"])
@login_required
def global_config():
    if request.method == "POST":
        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        # Edit check fields and remove already existing ones
        config = app.config["CONFIG"].get_config(methods=True, with_drafts=True)
        services = config["SERVER_NAME"]["value"].split(" ")
        for variable, value in variables.copy().items():
            if variable in ("AUTOCONF_MODE", "SWARM_MODE", "KUBERNETES_MODE", "SERVER_NAME", "IS_LOADING", "IS_DRAFT") or variable.endswith("SCHEMA"):
                del variables[variable]
                continue

            if value == "on":
                value = "yes"
            elif value == "off":
                value = "no"

            setting = config.get(variable, {"value": None, "global": True})
            if setting["global"] and value == setting["value"]:
                del variables[variable]

        if not variables:
            return redirect_flash_error("The global configuration was not edited because no values were changed.", "global_config", True)

        error = app.config["CONFIG"].check_variables(variables)

        if error:
            return redirect_flash_error("The global configuration variable checks returned error", "global_config", True)

        for variable, value in variables.copy().items():
            for service in services:
                setting = config.get(f"{service}_{variable}", None)
                if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                    variables[f"{service}_{variable}"] = value

        # Reload instances
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=(
                "global_config",
                variables,
            ),
        ).start()

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

    global_config = app.config["CONFIG"].get_config()
    for service in global_config["SERVER_NAME"]["value"].split(" "):
        for key in global_config.copy():
            if key.startswith(f"{service}_"):
                global_config.pop(key)
    # Display global config
    return render_template("global_config.html", username=current_user.get_id(), global_config=global_config, dumped_global_config=dumps(global_config))


@app.route("/configs", methods=["GET", "POST"])
@login_required
def configs():
    db_configs = db.get_custom_configs()

    if request.method == "POST":
        operation = ""

        is_request_params(["operation"], "configs", True)

        # Check operation
        if request.form["operation"] not in (
            "new",
            "edit",
            "delete",
        ):
            return redirect_flash_error("Operation parameter is invalid on /configs.", "configs", True)

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        if variables["type"] != "file":
            return redirect_flash_error("Invalid type parameter on /configs.", "configs", True)

        operation = app.config["CONFIGFILES"].check_path(variables["path"])

        if operation:
            return redirect_flash_error(operation, "configs", True)

        old_name = variables.get("old_name", "").replace(".conf", "")
        name = variables.get("name", old_name).replace(".conf", "")
        path_exploded = variables["path"].split(sep)
        service_id = (path_exploded[5] if len(path_exploded) > 6 else None) or None
        root_dir = path_exploded[4].replace("-", "_").lower()

        if not old_name and not name:
            return redirect_flash_error("Missing name parameter on /configs.", "configs", True)

        index = -1
        for i, db_config in enumerate(db_configs):
            if db_config["type"] == root_dir and db_config["name"] == name and db_config["service_id"] == service_id:
                if request.form["operation"] == "new":
                    return redirect_flash_error(f"Config {name} already exists{f' for service {service_id}' if service_id else ''}", "configs", True)
                elif db_config["method"] not in ("ui", "manual"):
                    return redirect_flash_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it was not created by the UI or manually",
                        "configs",
                        True,
                    )
                index = i
                break

        # New or edit a config
        if request.form["operation"] in ("new", "edit"):
            if not app.config["CONFIGFILES"].check_name(name):
                return redirect_flash_error(
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
                    return redirect_flash_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True
                    )

                if old_name != name:
                    db_configs[index]["name"] = name
                elif db_configs[index]["data"] == content:
                    return redirect_flash_error(
                        f"Config {name} was not edited because no values were changed{f' for service {service_id}' if service_id else ''}",
                        "configs",
                        True,
                    )

                db_configs[index]["data"] = content
                operation = f"Edited config {name}{f' for service {service_id}' if service_id else ''}"

        # Delete a config
        elif request.form["operation"] == "delete":
            if index == -1:
                return redirect_flash_error(
                    f"Can't delete config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True
                )

            del db_configs[index]
            operation = f"Deleted config {name}{f' for service {service_id}' if service_id else ''}"

        error = db.save_custom_configs([config for config in db_configs if config["method"] == "ui"], "ui")
        if error:
            app.logger.error(f"Could not save custom configs: {error}")
            return redirect_flash_error("Couldn't save custom configs", "configs", True)

        flash(operation)

        return redirect(url_for("loading", next=url_for("configs")))

    return render_template(
        "configs.html",
        folders=[
            path_to_dict(
                join(sep, "etc", "bunkerweb", "configs"),
                db_data=db_configs,
                services=app.config["CONFIG"].get_config(methods=False).get("SERVER_NAME", "").split(" "),
            )
        ],
        username=current_user.get_id(),
    )


@app.route("/plugins", methods=["GET", "POST"])
@login_required
def plugins():
    tmp_ui_path = Path(sep, "var", "tmp", "bunkerweb", "ui")

    if request.method == "POST":
        error = 0
        # Delete plugin
        if "operation" in request.form and request.form["operation"] == "delete":

            is_request_params(["type"], "plugins", True)

            # Check variables
            variables = deepcopy(request.form.to_dict())
            del variables["csrf_token"]

            if variables["type"] in ("core", "pro"):
                return redirect_flash_error(f"Can't delete {variables['type']} plugin {variables['name']}", "plugins", True)

            plugins = app.config["CONFIG"].get_plugins(_type="external", with_data=True)
            for x, plugin in enumerate(plugins):
                if plugin["id"] == variables["name"]:
                    del plugins[x]

            err = db.update_external_plugins(plugins)
            if err:
                error_message(f"Couldn't update external plugins to database: {err}")
            else:
                flash(f"Deleted plugin {variables['name']} successfully")
        else:
            # Upload plugins
            if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
                return redirect_flash_error("Please upload new plugins to reload plugins", "plugins", True)

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
                            flash(
                                f"{file} is not a valid zip file. ({folder_name or temp_folder_name})",
                                "error",
                            )
                    else:
                        try:
                            with tar_open(str(tmp_ui_path.joinpath(file)), errorlevel=2) as tar_file:
                                try:
                                    tar_file.getmember("plugin.json")
                                except KeyError:
                                    is_dir = True
                                try:
                                    tar_file.extractall(str(temp_folder_path), filter="data")
                                except TypeError:
                                    tar_file.extractall(str(temp_folder_path))
                        except ReadError:
                            errors += 1
                            error = 1
                            flash(
                                f"Couldn't read file {file} ({folder_name or temp_folder_name})",
                                "error",
                            )
                        except CompressionError:
                            errors += 1
                            error = 1
                            flash(
                                f"{file} is not a valid tar file ({folder_name or temp_folder_name})",
                                "error",
                            )
                        except HeaderError:
                            errors += 1
                            error = 1
                            flash(
                                f"The file plugin.json in {file} is not valid ({folder_name or temp_folder_name})",
                                "error",
                            )

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

                    if not app.config["CONFIGFILES"].check_name(folder_name):
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

            plugins = app.config["CONFIG"].get_plugins(_type="external", with_data=True)
            for plugin in deepcopy(plugins):
                if plugin["id"] in new_plugins_ids:
                    flash(f"Plugin {plugin['id']} already exists", "error")
                    del new_plugins[new_plugins_ids.index(plugin["id"])]

            err = db.update_external_plugins(new_plugins, delete_missing=False)
            if err:
                flash(f"Couldn't update external plugins to database: {err}", "error")
            else:
                flash("Plugins uploaded successfully")

        # Reload instances
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("plugins",),
        ).start()

        return redirect(url_for("loading", next=url_for("plugins"), message="Reloading plugins"))

    # Remove tmp folder
    if tmp_ui_path.is_dir():
        rmtree(tmp_ui_path, ignore_errors=True)

    plugins = app.config["CONFIG"].get_plugins()
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
        username=current_user.get_id(),
    )


@app.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if not request.files:
        return {"status": "ko"}, 400

    tmp_ui_path = Path(sep, "var", "tmp", "bunkerweb", "ui")
    tmp_ui_path.mkdir(parents=True, exist_ok=True)

    for uploaded_file in request.files.values():
        if not uploaded_file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        with BytesIO(uploaded_file.read()) as io:
            io.seek(0, 0)
            plugins = []
            if uploaded_file.filename.endswith(".zip"):
                with ZipFile(io) as zip_file:
                    for file in zip_file.namelist():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        zip_file.extractall(str(tmp_ui_path) + "/")
                folder_name = uploaded_file.filename.replace(".zip", "")
            else:
                with tar_open(fileobj=io) as tar_file:
                    for file in tar_file.getnames():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        try:
                            tar_file.extractall(str(tmp_ui_path) + "/", filter="data")
                        except TypeError:
                            tar_file.extractall(str(tmp_ui_path) + "/")
                folder_name = uploaded_file.filename.replace(".tar.gz", "").replace(".tar.xz", "")

            if len(plugins) <= 1:
                io.seek(0, 0)
                tmp_ui_path.joinpath(uploaded_file.filename).write_bytes(io.read())
                return {"status": "ok"}, 201

        for plugin in plugins:
            with BytesIO() as tgz:
                with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                    tf.add(str(tmp_ui_path.joinpath(folder_name, plugin)), arcname=plugin)
                tgz.seek(0, 0)
                tmp_ui_path.joinpath(f"{plugin}.tar.gz").write_bytes(tgz.read())

        rmtree(str(tmp_ui_path.joinpath(folder_name)), ignore_errors=True)

    return {"status": "ok"}, 201


@app.route("/plugins/<plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin(plugin: str):
    if not plugin_id_rx.match(plugin):
        return error_message("Invalid plugin id, (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)"), 400

    # Case we ware looking for a plugin template
    # We need to check if a page exists, and if it does, we need to check if the plugin is activated and metrics are on
    if request.method == "GET":

        # Check template
        page = db.get_plugin_template(plugin)

        if not page:
            return error_message("The plugin does not have a template"), 404

        # Case template, prepare data
        plugins = app.config["CONFIG"].get_plugins()
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

        config = app.config["CONFIG"].get_config(methods=False)

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
        pre_render = run_action(plugin, "pre_render")
        return render_template(
            Environment(loader=FileSystemLoader(join(sep, "usr", "share", "bunkerweb", "ui", "templates") + "/")).from_string(page.decode("utf-8")),
            username=current_user.get_id(),
            current_endpoint=plugin,
            plugin=curr_plugin,
            pre_render=pre_render,
            is_used=is_used,
            is_metrics=is_metrics_on,
            **app.jinja_env.globals,
        )

    action_result = run_action(plugin)
    # case error
    if action_result["status"] == "ko":
        return error_message(action_result["message"]), action_result["code"]

    app.logger.info(f"Plugin {plugin} action executed successfully")
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
                db_data=db.get_jobs_cache_files(),
                services=app.config["CONFIG"].get_config(methods=False).get("SERVER_NAME", "").split(" "),
            )
        ],
        username=current_user.get_id(),
    )


@app.route("/logs", methods=["GET"])
@login_required
def logs():
    return render_template("logs.html", instances=app.config["INSTANCES"].get_instances(), username=current_user.get_id())


@app.route("/logs/local", methods=["GET"])
@login_required
def logs_linux():
    if not sbin_nginx_path.is_file():
        return (
            jsonify(
                {
                    "status": "ko",
                    "message": "There are no linux instances running",
                }
            ),
            404,
        )

    last_update = request.args.get("last_update", "0.0")
    from_date = request.args.get("from_date", None)
    to_date = request.args.get("to_date", None)
    logs_error = []
    temp_multiple_lines = []
    NGINX_LOG_LEVELS = [
        "debug",
        "notice",
        "info",
        "warn",
        "error",
        "crit",
        "alert",
        "emerg",
    ]

    nginx_error_file = Path(sep, "var", "log", "bunkerweb", "error.log")
    if nginx_error_file.is_file():
        with open(nginx_error_file, encoding="utf-8") as f:
            for line in f.readlines()[int(last_update.split(".")[0]) if last_update else 0 :]:  # noqa: E203
                match = LOG_RX.search(line)
                if not match:
                    continue
                date = match.group("date")
                level = match.group("level")

                if not date:
                    if logs_error:
                        logs_error[-1] += f"\n{line}"
                        continue
                    logs_error.append(line)
                elif all(f"[{log_level}]" != level for log_level in NGINX_LOG_LEVELS) and temp_multiple_lines:
                    temp_multiple_lines.append(line)
                else:
                    logs_error.append(f"{datetime.strptime(date, '%Y/%m/%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()} {line}")

    if temp_multiple_lines:
        logs_error.append("\n".join(temp_multiple_lines))

    logs_access = []
    nginx_access_file = Path(sep, "var", "log", "bunkerweb", "access.log")
    if nginx_access_file.is_file():
        with open(nginx_access_file, encoding="utf-8") as f:
            for line in f.readlines()[int(last_update.split(".")[1]) if last_update else 0 :]:  # noqa: E203
                logs_access.append(
                    f"{datetime.strptime(line[line.find('[') + 1: line.find(']')], '%d/%b/%Y:%H:%M:%S %z').replace(tzinfo=timezone.utc).timestamp()} {line}"
                )

    raw_logs = logs_error + logs_access

    if from_date and from_date.isdigit():
        from_date = int(from_date) // 1000
    else:
        from_date = 0

    if to_date and to_date.isdigit():
        to_date = int(to_date) // 1000
    else:
        to_date = None

    def date_filter(log: str):
        log_date = log.split(" ")[0]
        log_date = float(log_date) if regex_match(r"^\d+\.\d+$", log_date) else 0
        if to_date is not None and log_date > int(to_date):
            return False
        return log_date > from_date

    logs = []
    for log in filter(date_filter, raw_logs):
        if "[48;2" in log or not log.strip():
            continue

        log_lower = log.lower()
        error_type = (
            "error"
            if "[error]" in log_lower or "[crit]" in log_lower or "[alert]" in log_lower or "❌" in log_lower
            else (("warn" if "[warn]" in log_lower or "⚠️" in log_lower else ("info" if "[info]" in log_lower or "ℹ️" in log_lower else "message")))
        )

        logs.append(
            {
                "content": " ".join(log.strip().split(" ")[1:]),
                "type": error_type,
            }
        )

    count_error_logs = 0
    for log in logs_error:
        if "\n" in log:
            for _ in log.split("\n"):
                count_error_logs += 1
        else:
            count_error_logs += 1

    return jsonify(
        {
            "logs": logs,
            "last_update": (
                f"{count_error_logs + int(last_update.split('.')[0])}.{len(logs_access) + int(last_update.split('.')[1])}"
                if last_update
                else f"{count_error_logs}.{len(logs_access)}"
            ),
        }
    )


@app.route("/logs/<container_id>", methods=["GET"])
@login_required
def logs_container(container_id):
    last_update = request.args.get("last_update", None)
    from_date = request.args.get("from_date", None)
    to_date = request.args.get("to_date", None)

    if from_date is not None:
        last_update = from_date

    if any(arg and not arg.isdigit() for arg in (last_update, from_date, to_date)):
        return (
            jsonify(
                {
                    "status": "ko",
                    "message": "arguments must all be integers (timestamps)",
                }
            ),
            422,
        )
    elif not last_update:
        last_update = int(datetime.now().timestamp() - timedelta(days=1).total_seconds())  # 1 day before
    else:
        last_update = int(last_update) // 1000

    to_date = int(to_date) // 1000 if to_date else None

    logs = []
    tmp_logs = []
    if docker_client:
        try:
            if INTEGRATION != "Swarm":
                docker_logs = docker_client.containers.get(container_id).logs(
                    stdout=True,
                    stderr=True,
                    since=datetime.fromtimestamp(last_update),
                    timestamps=True,
                )
            else:
                docker_logs = docker_client.services.get(container_id).logs(
                    stdout=True,
                    stderr=True,
                    since=datetime.fromtimestamp(last_update),
                    timestamps=True,
                )

            tmp_logs = docker_logs.decode("utf-8", errors="replace").split("\n")[0:-1]
        except docker_NotFound:
            return (
                jsonify(
                    {
                        "status": "ko",
                        "message": f"Container with ID {container_id} not found!",
                    }
                ),
                404,
            )
    elif kubernetes_client:
        try:
            kubernetes_logs = kubernetes_client.read_namespaced_pod_log(
                container_id,
                getenv("KUBERNETES_NAMESPACE", "default"),
                since_seconds=int(datetime.now().timestamp() - last_update),
                timestamps=True,
            )
            tmp_logs = kubernetes_logs.split("\n")[0:-1]
        except kube_ApiException:
            return (
                jsonify(
                    {
                        "status": "ko",
                        "message": f"Pod with ID {container_id} not found!",
                    }
                ),
                404,
            )

    for log in tmp_logs:
        split = log.split(" ")
        timestamp = split[0]

        if to_date is not None and dateutil_parse(timestamp).timestamp() > to_date:
            break

        log = " ".join(split[1:])
        log_lower = log.lower()

        if "[48;2" in log or not log.strip():
            continue

        logs.append(
            {
                "content": log,
                "type": (
                    "error"
                    if "[error]" in log_lower or "[crit]" in log_lower or "[alert]" in log_lower or "❌" in log_lower
                    else ("warn" if "[warn]" in log_lower or "⚠️" in log_lower else ("info" if "[info]" in log_lower or "ℹ️" in log_lower else "message"))
                ),
            }
        )

    return jsonify({"logs": logs, "last_update": int(time() * 1000)})


@app.route("/reports", methods=["GET"])
@login_required
def reports():
    reports = app.config["INSTANCES"].get_reports()
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
        username=current_user.get_id(),
    )


@app.route("/bans", methods=["GET", "POST"])
@login_required
def bans():
    redis_client = None
    db_config = app.config["CONFIG"].get_config(methods=False)
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
            sentinel_hosts = [host.split(":") if ":" in host else host for host in sentinel_hosts.split(" ") if host]

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

    if request.method == "POST":
        # Check variables
        is_request_form("bans")

        is_request_params(["operation", "data"], "bans")

        try:
            data = json_loads(request.form["data"])
            assert isinstance(data, list)
        except BaseException:
            return redirect_flash_error("Data must be a list of dict", "bans", False, "exception")

        if request.form["operation"] not in ("ban", "unban"):
            return redirect_flash_error("Operation unknown", "bans")

        if request.form["operation"] == "unban":
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

                resp = app.config["INSTANCES"].unban(unban["ip"])
                if resp:
                    flash(f"Couldn't unban {unban['ip']} on the following instances: {', '.join(resp)}", "error")
                else:
                    flash(f"Successfully unbanned {unban['ip']}")

        if request.form["operation"] == "ban":
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

                resp = app.config["INSTANCES"].ban(ban["ip"], ban_end, reason)
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
    instance_bans = app.config["INSTANCES"].get_bans()

    # Prepare data
    reasons = {}
    timestamp_now = time()

    for ban in instance_bans:
        if not any(b["ip"] == ban["ip"] for b in bans):
            bans.append(ban)

    bans = bans[:100]

    for ban in bans:
        exp = ban.pop("exp", 0)
        # Add remain
        ban["remain"], ban["term"] = ("unknown", "unknown") if exp <= 0 else get_remain(exp)
        # Convert stamp to date
        ban["ban_start"] = datetime.fromtimestamp(floor(ban["date"])).strftime("%d/%m/%Y %H:%M:%S")
        ban["ban_end"] = datetime.fromtimestamp(floor(timestamp_now + exp)).strftime("%d/%m/%Y %H:%M:%S")
        # Get top reason
        if not ban["reason"] in reasons:
            reasons[ban["reason"]] = 0
        reasons[ban["reason"]] = reasons[ban["reason"]] + 1

    top_reason = ([k for k, v in reasons.items() if v == max(reasons.values())] or [""])[0]

    return render_template("bans.html", bans=bans, top_reason=top_reason, username=current_user.get_id())


@app.route("/jobs", methods=["GET"])
@login_required
def jobs():
    return render_template("jobs.html", jobs=db.get_jobs(), jobs_errors=db.get_plugins_errors(), username=current_user.get_id())


@app.route("/jobs/download", methods=["GET"])
@login_required
def jobs_download():
    plugin_id = request.args.get("plugin_id", "")
    job_name = request.args.get("job_name", None)
    file_name = request.args.get("file_name", None)
    service_id = request.args.get("service_id", "")

    if not plugin_id or not job_name or not file_name:
        return jsonify({"status": "ko", "message": "plugin_id, job_name and file_name are required"}), 422

    cache_file = db.get_job_cache_file(job_name, file_name, service_id=service_id, plugin_id=plugin_id)

    if not cache_file:
        return jsonify({"status": "ko", "message": "file not found"}), 404

    file = BytesIO(cache_file)
    return send_file(file, as_attachment=True, download_name=file_name)


@app.route("/login", methods=["GET", "POST"])
def login():
    if not app.config["USER"]:
        return redirect(url_for("setup"))
    elif current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home"))

    fail = False
    if request.method == "POST" and "username" in request.form and "password" in request.form:
        app.logger.warning(f"Login attempt from {request.remote_addr} with username \"{request.form['username']}\"")
        db_user = db.get_ui_user()
        if not db_user:
            app.logger.error("Couldn't get user from database")
            stop(1)
        user = User(**db_user)

        if user.get_id() == request.form["username"] and user.check_password(request.form["password"]):
            # log the user in
            session["ip"] = request.remote_addr
            session["user_agent"] = request.headers.get("User-Agent")
            session["totp_validated"] = False
            login_user(user, duration=timedelta(hours=1))

            # redirect him to the page he originally wanted or to the home page
            return redirect(url_for("loading", next=request.form.get("next") or url_for("home")))
        else:
            flash("Invalid username or password", "error")
            fail = True

    kwargs = {
        "is_totp": current_user.is_two_factor_enabled,
    } | ({"error": "Invalid username or password"} if fail else {})

    return render_template("login.html", **kwargs), 401 if fail else 200


@app.route("/darkmode", methods=["POST"])
@login_required
def darkmode():
    if not request.is_json:
        return jsonify({"status": "ko", "message": "invalid request"}), 400

    if "darkmode" in request.json:
        app.config["DARK_MODE"] = request.json["darkmode"] == "true"
    else:
        return jsonify({"status": "ko", "message": "darkmode is required"}), 422

    return jsonify({"status": "ok"}), 200


@app.route("/check_reloading")
@login_required
def check_reloading():
    if not app.config["RELOADING"] or app.config["LAST_RELOAD"] + 60 < time():
        if app.config["RELOADING"]:
            app.logger.warning("Reloading took too long, forcing the state to be reloaded")
            flash("Forced the status to be reloaded", "error")
            app.config["RELOADING"] = False

        for f in app.config["TO_FLASH"]:
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

        app.config["TO_FLASH"].clear()

    return jsonify({"reloading": app.config["RELOADING"]})


@app.route("/logout")
@login_required
def logout():
    session.clear()
    logout_user()
    return redirect(url_for("login"))
