# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import redirect
from flask import render_template


from flask_jwt_extended import jwt_required
from flask_jwt_extended import verify_jwt_in_request

from hook import hooks

from werkzeug.exceptions import NotFound

from utils import get_core_format_res

from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)
PREFIX = "/admin/"
CORE_API = UI_CONFIG.CORE_ADDR

dashboard = Blueprint("dashboard", __name__)


@dashboard.route(f"{PREFIX}/setup")
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def setup():
    is_setup = get_core_format_res(f"{CORE_API}/setup", "GET", "", "Check if setup is done")

    # Case setup is done and user is not logged in
    if is_setup["data"]["setup"] and verify_jwt_in_request(True) is None:
        return redirect(f"{PREFIX}/login", 302)

    # Case setup is done and user logged
    if is_setup["data"]["setup"] and verify_jwt_in_request(True) is not None:
        return redirect(f"{PREFIX}/home", 302)

    # Case setup not done
    return render_template("setup.html")


@dashboard.route(f"{PREFIX}/login")
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def login():
    # Case user logged
    if verify_jwt_in_request(True) is not None:
        return redirect(f"{PREFIX}/home", 302)

    # Case user not logged
    return render_template("login.html")


@dashboard.route(f"{PREFIX}/home")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def home():
    return render_template("home.html")


@dashboard.route(f"{PREFIX}/bans")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def bans():
    return render_template("bans.html")


@dashboard.route(f"{PREFIX}/configs")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def configs():
    return render_template("configs.html")


@dashboard.route(f"{PREFIX}/global-config")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def global_config():
    return render_template("global-config.html")


@dashboard.route(f"{PREFIX}/instances")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def instances():
    return render_template("instances.html")


@dashboard.route(f"{PREFIX}/jobs")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def jobs():
    return render_template("jobs.html")


@dashboard.route(f"{PREFIX}/services")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def services():
    return render_template("services.html")


@dashboard.route(f"{PREFIX}/actions")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def actions():
    return render_template("actions.html")


@dashboard.route(f"{PREFIX}/plugins")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def plugins():
    return render_template("plugins.html")


@dashboard.route(f"{PREFIX}/<string:page>")
@jwt_required()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def not_found(page):
    raise NotFound(code=404, description=f"Page {page} Not found")
