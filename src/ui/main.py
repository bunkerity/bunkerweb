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
from routes.external import external
from routes.account import account

from exceptions.setup import setupUIException
from exceptions.default import setup_default_exceptions
from exceptions.hook import setup_hook_exceptions
from exceptions.jwt import setup_jwt_exceptions
from exceptions.database import setup_db_exceptions
from exceptions.api import setup_api_exceptions
from exceptions.validator import setup_validator_exceptions

from middleware.jwt import setup_jwt
from middleware.default import setup_default_middleware

from utils import log_format
from utils import create_action_format

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
        req = requests.get(f"{CORE_API}/ping", headers={"Authorization": f"Bearer {UI_CONFIG.core_token}"} if UI_CONFIG.core_token else {})
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
    LOGGER.info(log_format("info", "", "", "ADDING JWT MIDDLEWARE"))
    setup_jwt(app)
    setup_default_middleware(app)
except:
    raise setupUIException("exception", "ADDING JWT MIDDLEWARE")

# Setup exceptions
try:
    LOGGER.info(log_format("info", "", "", "ADDING EXCEPTIONS"))
    setup_default_exceptions(app)
    setup_jwt_exceptions(app)
    setup_hook_exceptions(app)
    setup_db_exceptions(app)
    setup_api_exceptions(app)
    setup_validator_exceptions(app)
except:
    raise setupUIException("exception", "ADDING EXCEPTIONS")

# Add API routes
api_routes = [actions, config, custom_configs, instances, jobs, logs, misc, plugins, external, account]

try:
    LOGGER.info(log_format("info", "", "", "ADDING API ROUTES"))
    for route in api_routes:
        app.register_blueprint(route)
except:
    raise setupUIException("exception", "ADDING API ROUTES")


# Add dashboard routes and statics
try:
    LOGGER.info(log_format("info", "", "", "ADDING TEMPLATES AND STATIC FILES"))
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
except:
    raise setupUIException("exception", "ADDING TEMPLATES AND STATIC FILES")


# Everything worked
if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")

LOGGER.info(log_format("info", "", "", "UI STARTED PROPERLY"))
create_action_format("success", "200", "UI started", "UI started properly.", ["ui", "setup"])
