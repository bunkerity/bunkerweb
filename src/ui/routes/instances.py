# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.validator import model_validator

from utils import get_core_format_res, get_req_data
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

PREFIX = "/api/instances"

instances = Blueprint("instances", __name__)


@instances.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_instances():
    """Get BunkerWeb instances"""
    return get_core_format_res(f"{CORE_API}/instances", "GET", "", "Retrieve instances")


@instances.route(f"{PREFIX}", methods=["PUT"])
@jwt_required()
@model_validator(queries={"method": "Method", "reload": "ReloadInstance"})
def upsert_instance():
    """Upsert one or more BunkerWeb instances"""
    args, data, method, reload_inst = [get_req_data(request, ["method", "reload"])[k] for k in ("args", "data", "method", "reload")]
    return get_core_format_res(f"{CORE_API}/instances?method={method if method else 'ui'}&reload={reload_inst if reload_inst else ''}", "PUT", data, "Upsert instances")


@instances.route(f"{PREFIX}/<string:instance_hostname>", methods=["DELETE"])
@jwt_required()
@model_validator(queries={"method": "Method"}, params={"instance_hostname": "InstanceHostname"})
def delete_instance(instance_hostname):
    """Delete BunkerWeb instance"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}?method={method if method else 'ui'}", "DELETE", "", f"Delete instance {instance_hostname}")


@instances.route(f"{PREFIX}/<string:instance_hostname>/<string:instance_action>", methods=["POST"])
@jwt_required()
@model_validator(queries={"method": "Method"}, params={"instance_hostname": "InstanceHostname", "instance_action": "InstanceAction"})
def action_instance(instance_hostname, instance_action):
    """Send action to a BunkerWeb instance"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}/{instance_action}?method={method if method else 'ui'}", "POST", "", f"Send instance {instance_hostname} action : {instance_action}")


@instances.route(f"{PREFIX}/ban", methods=["POST"])
@jwt_required()
@model_validator(body="BanAdd", queries={"method": "Method"})
def add_bans():
    """Add bans ip for all instances"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method if method else 'ui'}", "POST", data, "Add bans ip")


@instances.route(f"{PREFIX}/ban", methods=["DELETE"])
@jwt_required()
@model_validator(body="BanDelete", queries={"method": "Method"})
def delete_bans():
    """Delete bans ip for all instances"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method if method else 'ui'}", "DELETE", data, "Delete bans ip")
