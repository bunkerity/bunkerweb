#!/usr/bin/env python3

from contextlib import suppress
from os import _exit, getenv, listdir, sep, urandom
from os.path import basename, dirname, join
from secrets import choice
from string import ascii_letters, digits
from sys import path as sys_path, modules as sys_modules
from pathlib import Path

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
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
from glob import glob
from hashlib import sha256
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, dumps, loads as json_loads
from jinja2 import Template
from kubernetes import client as kube_client
from kubernetes import config as kube_config
from kubernetes.client.exceptions import ApiException as kube_ApiException
from regex import compile as re_compile, match as regex_match
from requests import get
from shutil import move, rmtree
from signal import SIGINT, signal, SIGTERM
from subprocess import PIPE, Popen, call
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from threading import Thread
from tempfile import NamedTemporaryFile
from time import sleep, time
from traceback import format_exc
from zipfile import BadZipFile, ZipFile

from src.Instances import Instances
from src.ConfigFiles import ConfigFiles
from src.Config import Config
from src.ReverseProxied import ReverseProxied
from src.User import AnonymousUser, User

from utils import check_settings, get_b64encoded_qr_image, path_to_dict
from Database import Database  # type: ignore
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
gunicorn_logger = getLogger("gunicorn.error")
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)


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
            app.logger.error("The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).")
            stop(1)

    user_name = getenv("ADMIN_USERNAME", "admin")
    USER = User(user_name, getenv("ADMIN_PASSWORD", "changeme"))
    ret = db.create_ui_user(user_name, USER.password_hash)

    if ret:
        app.logger.error(f"Couldn't create the admin user in the database: {ret}")
        stop(1)

app.logger.info("Database is ready")
Path(sep, "var", "tmp", "bunkerweb", "ui.healthy").write_text("ok", encoding="utf-8")
bw_version = Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text(encoding="utf-8").strip()

try:
    app.config.update(
        DEBUG=True,
        INSTANCES=Instances(docker_client, kubernetes_client, INTEGRATION),
        CONFIG=Config(db),
        CONFIGFILES=ConfigFiles(app.logger, db),
        WTF_CSRF_SSL_STRICT=False,
        USER=USER,
        SEND_FILE_MAX_AGE_DEFAULT=86400,
        PLUGIN_ARGS={},
        RELOADING=False,
        LAST_RELOAD=0,
        TO_FLASH=[],
        DARK_MODE=False,
        CURRENT_TOTP_TOKEN=None,
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


def manage_bunkerweb(method: str, *args, operation: str = "reloads"):
    # Do the operation
    error = False
    if method == "services":
        service_custom_confs = glob(join(sep, "etc", "bunkerweb", "configs", "*", args[1].split(" ")[0]))
        moved = False
        deleted = False

        if operation == "new":
            operation, error = app.config["CONFIG"].new_service(args[0])
        elif operation == "edit":
            if args[1].split(" ")[0] != args[2].split(" ")[0] and service_custom_confs:
                for service_custom_conf in service_custom_confs:
                    if listdir(service_custom_conf):
                        move(service_custom_conf, service_custom_conf.replace(f"{sep}{args[1].split(' ')[0]}", f"{sep}{args[2].split(' ')[0]}"))
                        moved = True
            operation, error = app.config["CONFIG"].edit_service(args[1], args[0], check_changes=not moved)
        elif operation == "delete":
            for service_custom_conf in glob(join(sep, "etc", "bunkerweb", "configs", "*", args[2].split(" ")[0])):
                if listdir(service_custom_conf):
                    rmtree(service_custom_conf, ignore_errors=True)
                    deleted = True
            operation, error = app.config["CONFIG"].delete_service(args[2], check_changes=not deleted)

        if error:
            app.config["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            app.config["TO_FLASH"].append({"content": operation, "type": "success"})

            if moved or deleted:
                changes = ["config", "custom_configs"]
                error = app.config["CONFIGFILES"].save_configs(check_changes=False)
                if error:
                    app.config["TO_FLASH"].append({"content": error, "type": "error"})
                    changes.pop()

                # update changes in db
                ret = db.checked_changes(changes, value=True)
                if ret:
                    app.logger.error(f"Couldn't set the changes to checked in the database: {ret}")
                    app.config["TO_FLASH"].append({"content": f"An error occurred when setting the changes to checked in the database : {ret}", "type": "error"})
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


@app.after_request
def set_csp_header(response):
    """Set the Content-Security-Policy header to prevent XSS attacks."""
    response.headers["Content-Security-Policy"] = "object-src 'none'; frame-ancestors 'self';"
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
        if not session.get("totp_validated", False) and current_user.is_two_factor_enabled and "/totp" not in request.path and not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts")) and request.path.endswith("/login"):
            return redirect(url_for("login", next=request.path))

        # Case not login page, keep on 2FA before any other access
        if not session.get("totp_validated", False) and current_user.is_two_factor_enabled and "/totp" not in request.path and not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts")):
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
    if "Origin" not in request.headers:
        return Response(status=403)

    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"})


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if current_user.is_authenticated:  # type: ignore
        return redirect(url_for("home"))

    db_config = app.config["CONFIG"].get_config(methods=False)

    for server_name in db_config["SERVER_NAME"].split(" "):
        if db_config.get(f"{server_name}_USE_UI", "no") == "yes":
            return redirect(url_for("login"), 301)

    if request.method == "POST":
        if not request.form:
            flash("Missing form data.", "error")
            return redirect(url_for("setup"))

        if not any(key in request.form for key in ("admin_username", "admin_password", "admin_password_check", "server_name", "ui_host", "ui_url")):
            flash("Missing either admin_username, admin_password, admin_password_check, server_name, ui_host, ui_url or auto_lets_encrypt parameter.", "error")
            return redirect(url_for("setup"))

        error = False

        if len(request.form["admin_username"]) > 256:
            flash("The admin username is too long. It must be less than 256 characters.", "error")
            error = True

        if request.form["admin_password"] != request.form["admin_password_check"]:
            flash("The passwords do not match.", "error")
            error = True

        if not USER_PASSWORD_RX.match(request.form["admin_password"]):
            flash("The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-).", "error")
            error = True

        server_names = db_config["SERVER_NAME"].split(" ")
        if request.form["server_name"] in server_names:
            flash(f"The hostname {request.form['server_name']} is already in use.", "error")
            error = True
        else:
            for server_name in server_names:
                if request.form["server_name"] in db_config.get(f"{server_name}_SERVER_NAME", "").split(" "):
                    flash(f"The hostname {request.form['server_name']} is already in use.", "error")
                    error = True
                    break

        if not REVERSE_PROXY_PATH.match(request.form["ui_host"]):
            flash("The hostname is not valid.", "error")
            error = True

        if error:
            return redirect(url_for("setup"))

        app.config["USER"] = User(request.form["admin_username"], request.form["admin_password"], method="ui")

        ret = db.create_ui_user(request.form["admin_username"], app.config["USER"].password_hash, method="ui")
        if ret:
            app.logger.error(f"Couldn't create the admin user in the database: {ret}")
            flash(f"Couldn't create the admin user in the database: {ret}", "error")
            return redirect(url_for("setup"))

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
        if not request.form:
            flash("Missing form data.", "error")
            return redirect(url_for("totp"))

        if "totp_token" not in request.form:
            flash("Missing token parameter.", "error")
            return redirect(url_for("totp"))

        if not current_user.check_otp(request.form["totp_token"]):
            flash("The token is invalid.", "error")
            return redirect(url_for("totp"))

        session["totp_validated"] = True
        redirect(url_for("loading", next=request.form.get("next") or url_for("home")))

    if not current_user.is_two_factor_enabled or session.get("totp_validated", False):
        return redirect(url_for("home"))

    return render_template("totp.html", dark_mode=app.config["DARK_MODE"])


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
    services = app.config["CONFIG"].get_services()
    instance_health_count = 0

    for instance in instances:
        if instance.health is True:
            instance_health_count += 1

    services_scheduler_count = 0
    services_ui_count = 0
    services_autoconf_count = 0

    for service in services:
        if service["SERVER_NAME"]["method"] == "scheduler":
            services_scheduler_count += 1
        elif service["SERVER_NAME"]["method"] == "ui":
            services_ui_count += 1
        elif service["SERVER_NAME"]["method"] == "autoconf":
            services_autoconf_count += 1

    return render_template(
        "home.html",
        check_version=not remote_version or bw_version == remote_version,
        remote_version=remote_version,
        version=bw_version,
        instances_number=len(instances),
        services_number=len(services),
        plugins_errors=db.get_plugins_errors(),
        instance_health_count=instance_health_count,
        services_scheduler_count=services_scheduler_count,
        services_ui_count=services_ui_count,
        services_autoconf_count=services_autoconf_count,
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        # Check form data validity
        if not request.form:
            flash("Missing form data.", "error")
            return redirect(url_for("account"))
        elif "operation" not in request.form:
            flash("Missing operation parameter.", "error")
            return redirect(url_for("account"))

        if "curr_password" not in request.form or not current_user.check_password(request.form["curr_password"]):
            flash(f"The current password is incorrect. ({request.form['operation']})", "error")
            return redirect(url_for("account"))

        username = current_user.get_id()
        password = request.form["curr_password"]
        is_two_factor_enabled = current_user.is_two_factor_enabled
        secret_token = current_user.secret_token

        if request.form["operation"] == "username":
            if "admin_username" not in request.form:
                flash("Missing admin_username parameter. (username)", "error")
                return redirect(url_for("account"))
            elif len(request.form["admin_username"]) > 256:
                flash("The admin username is too long. It must be less than 256 characters. (username)", "error")
                return redirect(url_for("account"))

            username = request.form["admin_username"]

            session.clear()
            logout_user()
        elif request.form["operation"] == "password":
            if "admin_password" not in request.form:
                flash("Missing admin_password parameter. (password)", "error")
                return redirect(url_for("account"))
            elif request.form.get("admin_password"):
                if not request.form.get("admin_password_check"):
                    flash("Missing admin_password_check parameter. (password)", "error")
                    return redirect(url_for("account"))
                elif request.form["admin_password"] != request.form["admin_password_check"]:
                    flash("The passwords does not match. (password)", "error")
                    return redirect(url_for("account"))
                elif not USER_PASSWORD_RX.match(request.form["admin_password"]):
                    flash("The admin password is not strong enough. It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-). (password)", "error")
                    return redirect(url_for("account"))
            elif request.form.get("admin_password_check"):
                flash("Missing admin_password parameter. (password)", "error")
                return redirect(url_for("account"))

            password = request.form["admin_password"]

            session.clear()
            logout_user()
        elif request.form["operation"] == "totp":
            if "totp_token" not in request.form:
                flash("Missing totp_token parameter. (totp)", "error")
                return redirect(url_for("account"))
            elif not current_user.check_otp(request.form["totp_token"], secret=app.config["CURRENT_TOTP_TOKEN"]):
                flash("The totp token is invalid. (totp)", "error")
                return redirect(url_for("account"))

            session["totp_validated"] = not current_user.is_two_factor_enabled
            is_two_factor_enabled = session["totp_validated"]
            secret_token = None if current_user.is_two_factor_enabled else app.config["CURRENT_TOTP_TOKEN"]
            app.config["CURRENT_TOTP_TOKEN"] = None
        else:
            flash("Invalid operation parameter.", "error")
            return redirect(url_for("account"))

        user = User(username, password, is_two_factor_enabled=is_two_factor_enabled, secret_token=secret_token, method=current_user.method)
        ret = db.update_ui_user(username, user.password_hash, is_two_factor_enabled, secret_token, current_user.method if request.form["operation"] == "totp" else "ui")
        if ret:
            app.logger.error(f"Couldn't update the admin user in the database: {ret}")
            flash(f"Couldn't update the admin user in the database: {ret}", "error")
            return redirect(url_for("account"))

        flash(
            f"The {request.form['operation']} has been successfully updated." if request.form["operation"] != "totp" else f"The two-factor authentication was successfully {'disabled' if current_user.is_two_factor_enabled else 'enabled'}.",
        )

        return redirect(url_for("account" if request.form["operation"] == "totp" else "login"))

    secret_token = ""
    totp_qr_image = ""

    if not current_user.is_two_factor_enabled:
        current_user.refresh_totp()
        secret_token = current_user.secret_token
        totp_qr_image = get_b64encoded_qr_image(current_user.get_authentication_setup_uri())
        app.config["CURRENT_TOTP_TOKEN"] = secret_token

    return render_template("account.html", username=current_user.get_id(), is_totp=current_user.is_two_factor_enabled, secret_token=secret_token, totp_qr_image=totp_qr_image, dark_mode=app.config["DARK_MODE"])


@app.route("/instances", methods=["GET", "POST"])
@login_required
def instances():
    # Manage instances
    if request.method == "POST":
        # Check operation
        if "operation" not in request.form or request.form["operation"] not in (
            "reload",
            "start",
            "stop",
            "restart",
        ):
            flash("Missing operation parameter on /instances.", "error")
            return redirect(url_for("loading", next=url_for("instances")))

        # Check that all fields are present
        if "INSTANCE_ID" not in request.form:
            flash("Missing INSTANCE_ID parameter.", "error")
            return redirect(url_for("loading", next=url_for("instances")))

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
    return render_template(
        "instances.html",
        title="Instances",
        instances=instances,
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/services", methods=["GET", "POST"])
@login_required
def services():
    if request.method == "POST":
        # Check operation
        if "operation" not in request.form or request.form["operation"] not in (
            "new",
            "edit",
            "delete",
        ):
            flash("Missing operation parameter on /services.", "error")
            return redirect(url_for("loading", next=url_for("services")))

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        if "OLD_SERVER_NAME" not in request.form and request.form["operation"] == "edit":
            flash("Missing OLD_SERVER_NAME parameter.", "error")
            return redirect(url_for("loading", next=url_for("services")))

        if "SERVER_NAME" not in variables:
            variables["SERVER_NAME"] = variables["OLD_SERVER_NAME"]

        if request.form["operation"] in ("new", "edit"):
            del variables["operation"]
            del variables["OLD_SERVER_NAME"]

            # Edit check fields and remove already existing ones
            config = app.config["CONFIG"].get_config(methods=False)
            server_name = variables["SERVER_NAME"].split(" ")[0]
            for variable, value in deepcopy(variables).items():
                if variable.endswith("SCHEMA"):
                    del variables[variable]
                    continue

                if value == "on":
                    value = "yes"
                elif value == "off":
                    value = "no"

                if variable in variables and variable != "SERVER_NAME" and value == config.get(f"{server_name}_{variable}" if request.form["operation"] == "edit" else variable, None):
                    del variables[variable]

            if request.form["operation"] == "edit" and len(variables) == 1 and "SERVER_NAME" in variables and variables["SERVER_NAME"] == request.form.get("OLD_SERVER_NAME", ""):
                flash(
                    "The service was not edited because no values were changed.",
                    "error",
                )
                return redirect(url_for("loading", next=url_for("services")))
            elif request.form["operation"] == "new" and not variables:
                flash("The service was not created because all values had the default value.", "error")
                return redirect(url_for("loading", next=url_for("services")))

            error = app.config["CONFIG"].check_variables(variables)

            if error:
                return redirect(url_for("loading", next=url_for("services")))

        # Delete
        elif request.form["operation"] == "delete":
            if "SERVER_NAME" not in request.form:
                flash("Missing SERVER_NAME parameter.", "error")
                return redirect(url_for("loading", next=url_for("services")))

            error = app.config["CONFIG"].check_variables({"SERVER_NAME": request.form["SERVER_NAME"]})

            if error:
                return redirect(url_for("loading", next=url_for("services")))

        error = 0

        # Reload instances
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("services", variables, request.form.get("OLD_SERVER_NAME", ""), variables.get("SERVER_NAME", "")),
            kwargs={"operation": request.form["operation"]},
        ).start()

        message = ""

        if request.form["operation"] == "new":
            message = f"Creating service {variables.get('SERVER_NAME', '').split(' ')[0]}"
        elif request.form["operation"] == "edit":
            message = f"Saving configuration for service {request.form.get('OLD_SERVER_NAME', '').split(' ')[0]}"
        elif request.form["operation"] == "delete":
            message = f"Deleting service {request.form.get('SERVER_NAME', '').split(' ')[0]}"

        return redirect(url_for("loading", next=url_for("services"), message=message))

    # Display services
    services = app.config["CONFIG"].get_services()
    return render_template(
        "services.html",
        services=[
            {
                "SERVER_NAME": {
                    "value": service["SERVER_NAME"]["value"].split(" ")[0],
                    "full_value": service["SERVER_NAME"]["value"],
                    "method": service["SERVER_NAME"]["method"],
                },
                "USE_REVERSE_PROXY": service["USE_REVERSE_PROXY"],
                "SERVE_FILES": service["SERVE_FILES"],
                "REMOTE_PHP": service["REMOTE_PHP"],
                "AUTO_LETS_ENCRYPT": service["AUTO_LETS_ENCRYPT"],
                "USE_CUSTOM_SSL": service["USE_CUSTOM_SSL"],
                "GENERATE_SELF_SIGNED_SSL": service["GENERATE_SELF_SIGNED_SSL"],
                "USE_MODSECURITY": service["USE_MODSECURITY"],
                "USE_BAD_BEHAVIOR": service["USE_BAD_BEHAVIOR"],
                "USE_LIMIT_REQ": service["USE_LIMIT_REQ"],
                "USE_DNSBL": service["USE_DNSBL"],
                "settings": dumps(service),
            }
            for service in services
        ],
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/global_config", methods=["GET", "POST"])
@login_required
def global_config():
    if request.method == "POST":
        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        # Edit check fields and remove already existing ones
        config = app.config["CONFIG"].get_config(methods=False)
        for variable, value in deepcopy(variables).items():
            if value == "on":
                value = "yes"
            elif value == "off":
                value = "no"

            if value == config.get(variable, None) or not value.strip():
                del variables[variable]

        if not variables:
            flash("The global configuration was not edited because no values were changed.")
            return redirect(url_for("loading", next=url_for("global_config")))

        error = app.config["CONFIG"].check_variables(variables, True)

        if error:
            return redirect(url_for("loading", next=url_for("global_config")))

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

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config"),
                message="Saving global configuration",
            )
        )

    # Display global config
    return render_template(
        "global_config.html",
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/configs", methods=["GET", "POST"])
@login_required
def configs():
    if request.method == "POST":
        operation = ""

        # Check operation
        if "operation" not in request.form or request.form["operation"] not in (
            "new",
            "edit",
            "delete",
        ):
            flash("Missing operation parameter on /configs.", "error")
            return redirect(url_for("loading", next=url_for("configs")))

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        operation = app.config["CONFIGFILES"].check_path(variables["path"])

        if operation:
            flash(operation, "error")
            return redirect(url_for("loading", next=url_for("configs")))

        if request.form["operation"] in ("new", "edit"):
            if not app.config["CONFIGFILES"].check_name(variables["name"]):
                flash(
                    f"Invalid {variables['type']} name. (Can only contain numbers, letters, underscores, dots and hyphens (min 4 characters and max 64))",
                    "error",
                )
                return redirect(url_for("loading", next=url_for("configs")))

            if variables["type"] == "file":
                variables["name"] = f"{variables['name']}.conf"

                if "old_name" in variables:
                    variables["old_name"] = f"{variables['old_name']}.conf"

                variables["content"] = BeautifulSoup(variables["content"], "html.parser").get_text()

            error = False

            if request.form["operation"] == "new":
                if variables["type"] == "folder":
                    operation, error = app.config["CONFIGFILES"].create_folder(variables["path"], variables["name"])
                elif variables["type"] == "file":
                    operation, error = app.config["CONFIGFILES"].create_file(variables["path"], variables["name"], variables["content"])
            elif request.form["operation"] == "edit":
                if variables["type"] == "folder":
                    operation, error = app.config["CONFIGFILES"].edit_folder(
                        variables["path"],
                        variables["name"],
                        variables.get("old_name", variables["name"]),
                    )
                elif variables["type"] == "file":
                    operation, error = app.config["CONFIGFILES"].edit_file(
                        variables["path"],
                        variables["name"],
                        variables.get("old_name", variables["name"]),
                        variables["content"],
                    )

            if error:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("configs")))
        else:
            operation, error = app.config["CONFIGFILES"].delete_path(variables["path"])

            if error:
                flash(operation, "error")
                return redirect(url_for("loading", next=url_for("configs")))

        flash(operation)

        error = app.config["CONFIGFILES"].save_configs()
        if error:
            flash("Couldn't save custom configs to database", "error")

        return redirect(url_for("loading", next=url_for("configs")))

    return render_template(
        "configs.html",
        folders=[
            path_to_dict(
                join(sep, "etc", "bunkerweb", "configs"),
                db_data=db.get_custom_configs(),
                services=app.config["CONFIG"].get_config(methods=False).get("SERVER_NAME", "").split(" "),
            )
        ],
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/plugins", methods=["GET", "POST"])
@login_required
def plugins():
    tmp_ui_path = Path(sep, "var", "tmp", "bunkerweb", "ui")
    if request.method == "POST":
        operation = ""
        error = 0

        if "operation" in request.form and request.form["operation"] == "delete":
            # Check variables
            variables = deepcopy(request.form.to_dict())
            del variables["csrf_token"]

            if variables["external"] != "True":
                flash(f"Can't delete internal plugin {variables['name']}", "error")
                return redirect(url_for("loading", next=url_for("plugins")))

            plugins = app.config["CONFIG"].get_plugins()
            for plugin in deepcopy(plugins):
                if plugin["external"] is False or plugin["id"] == variables["name"]:
                    del plugins[plugins.index(plugin)]

            err = db.update_external_plugins(plugins)
            if err:
                flash(
                    f"Couldn't update external plugins to database: {err}",
                    "error",
                )
            flash(f"Deleted plugin {variables['name']} successfully")
        else:
            if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
                flash("Please upload new plugins to reload plugins", "error")
                return redirect(url_for("loading", next=url_for("plugins")))

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
                            "external": True,
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

            plugins = app.config["CONFIG"].get_plugins(external=True, with_data=True)
            for plugin in deepcopy(plugins):
                if plugin["id"] in new_plugins_ids:
                    flash(f"Plugin {plugin['id']} already exists", "error")
                    del new_plugins[new_plugins_ids.index(plugin["id"])]

            err = db.update_external_plugins(new_plugins, delete_missing=False)
            if err:
                flash(
                    f"Couldn't update external plugins to database: {err}",
                    "error",
                )

        if operation:
            flash(operation)

        # Reload instances
        app.config["RELOADING"] = True
        app.config["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            name="Reloading instances",
            args=("plugins",),
        ).start()

        # Remove tmp folder
        if tmp_ui_path.exists():
            rmtree(str(tmp_ui_path), ignore_errors=True)

        return redirect(url_for("loading", next=url_for("plugins"), message="Reloading plugins"))

    plugin_args = app.config["PLUGIN_ARGS"]
    app.config["PLUGIN_ARGS"] = {}

    if request.args.get("plugin_id", False):
        plugin_id = request.args.get("plugin_id")
        template = None

        page = db.get_plugin_template(plugin_id)

        if page is not None:
            template = Template(page.decode("utf-8"))

        if template is not None:
            return template.render(
                csrf_token=generate_csrf,
                url_for=url_for,
                username=current_user.get_id(),
                dark_mode=app.config["DARK_MODE"],
                **(plugin_args["args"] if plugin_args.get("plugin", None) == plugin_id else {}),
            )

    plugins = app.config["CONFIG"].get_plugins()
    plugins_internal = 0
    plugins_external = 0

    for plugin in plugins:
        if plugin["external"] is True:
            plugins_external += 1
        else:
            plugins_internal += 1

    return render_template(
        "plugins.html",
        plugins=plugins,
        plugins_internal=plugins_internal,
        plugins_external=plugins_external,
        plugins_errors=db.get_plugins_errors(),
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
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
def custom_plugin(plugin):
    if not plugin_id_rx.match(plugin):
        flash(
            f"Invalid plugin id, <b>{plugin}</b> (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))

    module = db.get_plugin_actions(plugin)

    if module is None:
        flash(
            f"The <i>actions.py</i> file for the plugin <b>{plugin}</b> does not exist",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))

    try:
        # Try to import the custom plugin
        with NamedTemporaryFile(mode="wb", suffix=".py", delete=True) as temp:
            temp.write(module)
            temp.flush()
            temp.seek(0)
            loader = SourceFileLoader("actions", temp.name)
            actions = loader.load_module()
    except:
        flash(
            f"An error occurred while importing the plugin <b>{plugin}</b>:<br/>{format_exc()}",
            "error",
        )
        return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))

    error = False
    res = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, plugin)
        res = method()
    except AttributeError:
        flash(
            f"The plugin <b>{plugin}</b> does not have a <i>{plugin}</i> method",
            "error",
        )
        error = True
        return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))
    except:
        flash(
            f"An error occurred while executing the plugin <b>{plugin}</b>:<br/>{format_exc()}",
            "error",
        )
        error = True
    finally:
        if sbin_nginx_path.is_file():
            # Remove the custom plugin from the shared library
            sys_path.pop()
            sys_modules.pop("actions")
            del actions

        if request.method != "POST" or error is True or res is None or isinstance(res, dict) is False:
            return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))

    app.config["PLUGIN_ARGS"] = {"plugin": plugin, "args": res}

    flash(f"Your action <b>{plugin}</b> has been executed")
    return redirect(url_for("loading", next=url_for("plugins", plugin_id=plugin)))


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
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/logs", methods=["GET"])
@login_required
def logs():
    return render_template(
        "logs.html",
        instances=app.config["INSTANCES"].get_instances(),
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


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
                logs_access.append(f"{datetime.strptime(line[line.find('[') + 1: line.find(']')], '%d/%b/%Y:%H:%M:%S %z').replace(tzinfo=timezone.utc).timestamp()} {line}")

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
            else ("warn" if "[warn]" in log_lower or "⚠️" in log_lower else ("info" if "[info]" in log_lower or "ℹ️" in log_lower else "message"))
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
            "last_update": f"{count_error_logs + int(last_update.split('.')[0])}.{len(logs_access) + int(last_update.split('.')[1])}" if last_update else f"{count_error_logs}.{len(logs_access)}",
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
                "type": "error"
                if "[error]" in log_lower or "[crit]" in log_lower or "[alert]" in log_lower or "❌" in log_lower
                else ("warn" if "[warn]" in log_lower or "⚠️" in log_lower else ("info" if "[info]" in log_lower or "ℹ️" in log_lower else "message")),
            }
        )

    return jsonify({"logs": logs, "last_update": int(time() * 1000)})


@app.route("/jobs", methods=["GET"])
@login_required
def jobs():
    return render_template(
        "jobs.html",
        jobs=db.get_jobs(),
        jobs_errors=db.get_plugins_errors(),
        username=current_user.get_id(),
        dark_mode=app.config["DARK_MODE"],
    )


@app.route("/jobs/download", methods=["GET"])
@login_required
def jobs_download():
    job_name = request.args.get("job_name", None)
    file_name = request.args.get("file_name", None)

    if not job_name or not file_name:
        return (
            jsonify(
                {
                    "status": "ko",
                    "message": "job_name and file_name are required",
                }
            ),
            422,
        )

    cache_file = db.get_job_cache_file(job_name, file_name)

    if not cache_file:
        return (
            jsonify(
                {
                    "status": "ko",
                    "message": "file not found",
                }
            ),
            404,
        )

    file = BytesIO(cache_file.data)
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
