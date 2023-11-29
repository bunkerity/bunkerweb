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

from utils import setupUIException, default_error_handler, create_action_format, log_format

from werkzeug.exceptions import HTTPException
import os
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

LOGGER.warning(os.environ)

# Check CORE to run UI
core_running = False

LOGGER.info(log_format("info", "", "", "Check if CORE API is setup."))

for x in range(UI_CONFIG.MAX_WAIT_RETRIES):
    if core_running:
        LOGGER.info(log_format("info", "", "", "CORE API ping succeed."))
        break

    try:
        req = requests.get(f"{CORE_API}/ping")
        if req.status_code == 200:
            core_running = True
    except:
        core_running = False

    LOGGER.warn(log_format("warn", "", "", f"Ping CORE API, try={x}"))
    time.sleep(UI_CONFIG.WAIT_RETRY_INTERVAL)

if not core_running:
    raise setupUIException("exception", "PING CORE FAILED, STOP STARTING UI", False)

# Start UI app
app = Flask(__name__)

LOGGER.info(log_format("info", "", "", "START UI SETUP"))

try:
    setup_jwt(app)
    LOGGER.info(log_format("info", "", "", "ADDING JWT MIDDLEWARE"))
except:
    raise setupUIException("exception", "ADDING JWT MIDDLEWARE")


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
    LOGGER.info(log_format("info", "", "", "ADDING API ROUTES"))
except:
    raise setupUIException("exception", "ADDING API ROUTES")


# Add dashboard routes and related templates / files
try:
    app.register_blueprint(dashboard)
    templates = Blueprint("static", __name__, template_folder="static")
    assets = Blueprint("assets", __name__, static_folder="static/assets")
    images = Blueprint("images", __name__, static_folder="static/images")
    style = Blueprint("style", __name__, static_folder="static/css")
    js = Blueprint("js", __name__, static_folder="static/js")
    fonts = Blueprint("webfonts", __name__, static_folder="static/webfonts")
    flags = Blueprint("flags", __name__, static_folder="static/flags")
    app.register_blueprint(templates)
    app.register_blueprint(assets)
    app.register_blueprint(images)
    app.register_blueprint(style)
    app.register_blueprint(js)
    app.register_blueprint(fonts)
    app.register_blueprint(flags)
    LOGGER.info(log_format("info", "", "", "ADDING TEMPLATES AND STATIC FILES"))
except:
    raise setupUIException("exception", "ADDING TEMPLATES AND STATIC FILES")


@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""
    return default_error_handler(e.code, "", e.description)


# Everything worked
if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

LOGGER.info(log_format("info", "", "", "UI STARTED PROPERLY"))
create_action_format("success", "200", "UI started", "UI started properly.", ["ui", "setup"])
