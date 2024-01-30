# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import redirect
from flask import request
from flask import render_template

from middleware.jwt import jwt_additionnal_checks
from middleware.validator import model_validator

from flask_jwt_extended import jwt_required
from flask_jwt_extended import verify_jwt_in_request

from hook import hooks

from werkzeug.exceptions import NotFound

from utils import get_core_format_res, get_req_data

from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)
PREFIX = "/admin/"
CORE_API = UI_CONFIG.CORE_ADDR

dashboard = Blueprint("dashboard", __name__)


@dashboard.route(f"{PREFIX}/setup", methods=["GET"])
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


@dashboard.route(f"{PREFIX}/setup", methods=["POST"])
@model_validator(body="SetupWizard")
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def setup_wizard():
    args, data = [get_req_data(request, [])[k] for k in ("args", "data")]
    return get_core_format_res(f"{CORE_API}/setup", "POST", data, "Setting up using setup wizard")


@dashboard.route(f"{PREFIX}/login", methods=["GET"])
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def login():
    # Case user logged
    if verify_jwt_in_request(True) is not None:
        return redirect(f"{PREFIX}/home", 302)

    # Case user not logged
    return render_template("login.html")


@dashboard.route(f"{PREFIX}/home", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def home():
    return render_template("home.html")


@dashboard.route(f"{PREFIX}/bans", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def bans():
    return render_template("bans.html")


@dashboard.route(f"{PREFIX}/configs", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def configs():
    return render_template("configs.html")


@dashboard.route(f"{PREFIX}/global-config", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def global_config():
    return render_template("global-config.html")


@dashboard.route(f"{PREFIX}/instances", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def instances():
    return render_template("instances.html")


@dashboard.route(f"{PREFIX}/jobs", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def jobs():
    return render_template("jobs.html")


@dashboard.route(f"{PREFIX}/services", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def services():
    return render_template("services.html")


@dashboard.route(f"{PREFIX}/actions", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def actions():
    return render_template("actions.html")


@dashboard.route(f"{PREFIX}/plugins", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def plugins():
    return render_template("plugins.html")


@dashboard.route(f"{PREFIX}/account", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def account():
    return render_template("account.html")


@dashboard.route(f"{PREFIX}/reporting", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def reporting():
    return render_template("reporting.html")


@dashboard.route(f"{PREFIX}/sitemap", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def sitemap():
    return render_template("sitemap.html")


@dashboard.route(f"{PREFIX}/plugins/<string:plugin_id>", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def plugin_page(plugin_id):
    return render_template(f"{plugin_id}.html")


@dashboard.route(f"{PREFIX}/<string:page>", methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeAccessPage", "AfterAccessPage"])
def not_found(page):
    raise NotFound(f"Page {page} Not found")
