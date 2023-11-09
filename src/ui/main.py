# -*- coding: utf-8 -*-
from flask import Flask
from flask import Blueprint

import requests

from routes.actions import actions
from routes.config import config
from routes.custom_configs import custom_configs
from routes.instances import instances
from routes.jobs import jobs
from routes.logs import logs
from routes.misc import misc
from routes.plugins import plugins
from routes.dashboard import dashboard

from middleware.jwt import setup_jwt


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
        if req.status_code == 200:
            core_running = True
    except:
        core_running = False

    LOGGER.info(f"PING {CORE_API}/ping | TRY {x}")
    time.sleep(UI_CONFIG.WAIT_RETRY_INTERVAL)

if core_running:
    LOGGER.info("PING CORE SUCCEED")

if not core_running:
    LOGGER.error("PING CORE FAILED, STOP STARTING UI")
    exit(1)

# Start UI app
app = Flask(__name__)
LOGGER.info("START UI SETUP")

try:
    setup_jwt(app)
    LOGGER.info("ADDING MIDDLEWARE")
except:
    LOGGER.exception("ADDING API ROUTES")
    exit(1)

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
    LOGGER.exception("ADDING API ROUTES")
    exit(1)

# Add dashboard routes and related templates / files
try:
    app.register_blueprint(dashboard)
    templates = Blueprint("static", __name__, template_folder="static")
    assets = Blueprint("assets", __name__, static_folder="static/assets")
    images = Blueprint("images", __name__, static_folder="static/images")
    style = Blueprint("style", __name__, static_folder="static/css")
    js = Blueprint("js", __name__, static_folder="static/js")
    json_ = Blueprint("json", __name__, static_folder="static/json")
    fonts = Blueprint("webfonts", __name__, static_folder="static/webfonts")
    app.register_blueprint(templates)
    app.register_blueprint(assets)
    app.register_blueprint(images)
    app.register_blueprint(style)
    app.register_blueprint(js)
    app.register_blueprint(json_)
    app.register_blueprint(fonts)
    LOGGER.info("ADDING TEMPLATES AND STATIC FILES")
except:
    LOGGER.exception("ADDING API ROUTES")
    exit(1)


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


# Everything worked
if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

LOGGER.info("UI RUNNING")
