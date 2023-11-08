# -*- coding: utf-8 -*-
from flask import Flask
from flask import request
from flask import make_response
from flask import redirect
from flask import Blueprint

from flask_jwt_extended import create_access_token
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import get_jwt
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import JWTManager

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import requests

from routes.actions import actions
from routes.config import config
from routes.custom_configs import custom_configs
from routes.instances import instances
from routes.jobs import jobs
from routes.logs import logs
from routes.misc import misc
from routes.plugins import plugins

from werkzeug.exceptions import HTTPException
import os
import json
from pathlib import Path
from logging import Logger
from os.path import join, sep
from sys import path as sys_path
import time
from ui import UiConfig

# Setup data and logger
UI_CONFIG = UiConfig("ui", **os.environ)
CORE_API = UI_CONFIG.CORE_ADDR
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "ui.healthy")

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

# Validate some data
if not isinstance(UI_CONFIG.WAIT_RETRY_INTERVAL, int) and (not UI_CONFIG.WAIT_RETRY_INTERVAL.isdigit() or int(UI_CONFIG.WAIT_RETRY_INTERVAL) < 1):
    LOGGER.error(f"Invalid WAIT_RETRY_INTERVAL provided: {UI_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer.")
    exit(1)
if not isinstance(UI_CONFIG.MAX_WAIT_RETRIES, int) and (not UI_CONFIG.MAX_WAIT_RETRIES.isdigit() or int(UI_CONFIG.MAX_WAIT_RETRIES) < 1):
    LOGGER.error(f"Invalid MAX_WAIT_RETRIES provided: {UI_CONFIG.MAX_WAIT_RETRIES}, It must be a positive integer.")
    exit(1)

LOGGER.warning(os.environ)

# Check CORE to run UI
core_running = False

for x in range(UI_CONFIG.MAX_WAIT_RETRIES):
    if core_running:
        break

    try:
        req = requests.get(f"{CORE_API}/ping")
        LOGGER.info(f"PING {req} | TRY {x}")
        if req.status_code == 200:
            core_running = True
    except:
        LOGGER.exception(f"Impossible to connect to CORE API | TRY {x}")
        core_running = False

    time.sleep(UI_CONFIG.WAIT_RETRY_INTERVAL)

if core_running:
    LOGGER.info("PING CORE SUCCEED")

if not core_running:
    LOGGER.error("PING CORE FAILED, STOP STARTING UI")
    exit(1)

# Start UI app
app = Flask(__name__)
LOGGER.info("START RUNNING UI")

# Add API routes
try:
    app.register_blueprint(actions)
    app.register_blueprint(config)
    app.register_blueprint(custom_configs)
    app.register_blueprint(instances)
    app.register_blueprint(jobs)
    app.register_blueprint(logs)
    app.register_blueprint(misc)
    app.register_blueprint(plugins)
    LOGGER.info("ADDING API ROUTES")
except:
    LOGGER.error("ADDING API ROUTES")
    exit(1)

# Handle static files
try:
    dashboard = Blueprint("", __name__, static_folder="static")
    LOGGER.info("ADDING STATIC FILES")
except:
    LOGGER.error("ADDING STATIC FILES")
    exit(1)

### JWT TOKEN LOGIC

# Setup the Flask-JWT-Extended extension
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]  # How JWT is handle
app.config["JWT_COOKIE_SECURE"] = False  # ONLY HTTPS
app.config["JWT_SECRET_KEY"] = "super-secret"  # Change for prod
app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # Add CSRF TOKEN check
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
jwt = JWTManager(app)


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps(
        {
            "code": e.code,
            "name": e.name,
            "description": e.description,
        }
    )
    response.content_type = "application/json"
    return response


@app.after_request
def refresh_expiring_jwts(response):
    # Add request that aren't concern by refresh (like get periodic logs)
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + timedelta(minutes=5))
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(identity=get_jwt_identity())
            set_access_cookies(response, access_token)
        return response
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original response
        return response


# Create a route to authenticate your users and return JWTs. The
# create_access_token() function is used to actually generate the JWT.
#
# logs = {username : "test", password: "test"}
# fetch(window.location.origin + '/login', {method : "POST", body : JSON.stringify(logs), headers: { "Content-Type": "application/json"}})
#
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", None)
    password = request.form.get("password", None)
    if username != "test" or password != "test":
        return make_response(redirect("/", 302))

    access_token = create_access_token(identity=username)
    resp = make_response(redirect("/home", 302))
    set_access_cookies(resp, access_token)
    return resp


# Remove cookies
@app.route("/logout", methods=["POST"])
def logout():
    resp = make_response("/", 302)
    unset_jwt_cookies(resp)
    return resp


# Protect a route with jwt_required, which will kick out requests
# without a valid JWT present.
#
@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    # Access the identity of the current user with get_jwt_identity
    # current_user = get_jwt_identity() # TODO
    return "<p>Protected access</p>"


# Get data from fetch retrieving document.cookie
#
# fetch(window.location.origin + '/test', {method : "GET", headers: { "Content-Type": "application/json", 'X-CSRF-TOKEN': getCookie('csrf_access_token'),}})
#
@app.route("/test", methods=["GET"])
@jwt_required()
def test():
    return json.dumps({"test": "test"})


@app.route("/")
def hello_world():
    return "<form action='/login' method='post'><input name='username' type='text'/><input name='password' type='text'><button type='submit'>submit</button></form>"


@app.route("/home")
@jwt_required()
def homepage():
    return "<p>Connected</p><form action='/logout' method='post'><button type='submit'>logout</button></form>"


# Everything worked
if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

LOGGER.info("UI STARTED PROPERLY")
