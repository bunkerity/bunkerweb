# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import render_template
from flask_jwt_extended import jwt_required

PREFIX = "/admin/"

dashboard = Blueprint("dashboard", __name__)


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


@dashboard.route(f"{PREFIX}/plugins")
@jwt_required()
def plugins():
    return render_template("plugins.html")


@dashboard.route(f"{PREFIX}/services")
@jwt_required()
def services():
    return render_template("services.html")
