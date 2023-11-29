# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required
from middleware.validator import model_validator


from utils import get_core_format_res, get_req_data
import json
from os import environ
from ui import UiConfig

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

from os.path import join, sep
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from api_models import BanAdd, BanDelete, Method  # type: ignore

PREFIX = "/api/instances"

instances = Blueprint("instances", __name__)


@instances.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_instances():
    """Get BunkerWeb instances"""
    return get_core_format_res(f"{CORE_API}/instances", "GET", "", "Retrieve instances")


@instances.route(f"{PREFIX}", methods=["PUT"])
@jwt_required()
def upsert_instance():
    """Upsert one or more BunkerWeb instances"""
    args, data, method, reload_inst = [get_req_data(request, ['method', 'reload'])[k] for k in ('args','data', 'method', 'reload')]
    return get_core_format_res(f"{CORE_API}/instances?method={method if method else 'ui'}&reload={reload_inst if reload_inst else True}", "PUT", data, "Upsert instances")


@instances.route(f"{PREFIX}/<string:instance_hostname>", methods=["DELETE"])
@jwt_required()
def delete_instance(instance_hostname):
    """Delete BunkerWeb instance"""
    args, data, method = [get_req_data(request, ['method'])[k] for k in ('args','data', 'method')]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}?method={method if method else 'ui'}", "DELETE", "", f"Delete instance {instance_hostname}")


@instances.route(f"{PREFIX}/<string:instance_hostname>/<string:action>", methods=["POST"])
@jwt_required()
def action_instance(instance_hostname, action):
    """Send action to a BunkerWeb instance"""
    args, data, method = [get_req_data(request, ['method'])[k] for k in ('args','data', 'method')]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}/{action}?method={method if method else 'ui'}", "POST", "", f"Send instance {instance_hostname} action : {action}")


@instances.route(f"{PREFIX}/ban", methods=["POST"])
@jwt_required()
@model_validator(body="BanAdd", queries={"method" : "Method"})
def add_bans():
    """Add bans ip for all instances"""
    args, data, method = [get_req_data(request, ['method'])[k] for k in ('args','data', 'method')]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method if method else 'ui'}", "POST", data, "Add bans ip")


@instances.route(f"{PREFIX}/ban", methods=["DELETE"])
@jwt_required()
@model_validator(body="BanDelete", queries={"method" : "Method"})
def delete_bans():
    """Delete bans ip for all instances"""
    args, data, method = [get_req_data(request, ['method'])[k] for k in ('args','data', 'method')]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method if method else 'ui'}", "DELETE", data, "Delete bans ip")
