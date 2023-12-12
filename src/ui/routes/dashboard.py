# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask import render_template
from flask_jwt_extended import jwt_required
from flask import render_template_string
import requests

from werkzeug.exceptions import NotFound
from werkzeug.exceptions import InternalServerError
from werkzeug.sansio.response import Response

PREFIX = "/admin/"

dashboard = Blueprint("dashboard", __name__)


@dashboard.route(f"{PREFIX}/setup")
def setup():
    return render_template("setup.html")


@dashboard.route(f"{PREFIX}/login")
def login():
    return render_template("login.html")


@dashboard.route(f"{PREFIX}/home")
@jwt_required()
def home():
    return render_template("home.html")


@dashboard.route(f"{PREFIX}/bans")
@jwt_required()
def bans():
    return render_template("bans.html")


@dashboard.route(f"{PREFIX}/configs")
@jwt_required()
def configs():
    return render_template("configs.html")


@dashboard.route(f"{PREFIX}/global-config")
@jwt_required()
def global_config():
    return render_template("global-config.html")


@dashboard.route(f"{PREFIX}/instances")
@jwt_required()
def instances():
    return render_template("instances.html")


@dashboard.route(f"{PREFIX}/jobs")
@jwt_required()
def jobs():
    return render_template("jobs.html")


@dashboard.route(f"{PREFIX}/services")
@jwt_required()
def services():
    return render_template("services.html")


@dashboard.route(f"{PREFIX}/actions")
@jwt_required()
def actions():
    return render_template("actions.html")


@dashboard.route(f"{PREFIX}/plugins")
@jwt_required()
def plugins():
    return render_template("plugins.html")


@dashboard.route(f"{PREFIX}/<string:page>")
@jwt_required()
def not_found(page):
    raise NotFound(response=Response(status=404), description=f"Not found")
