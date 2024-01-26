# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.jwt import jwt_additionnal_checks
from middleware.validator import model_validator

from hook import hooks

from utils import get_core_format_res, get_req_data
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

PREFIX = "/api/instances"

instances = Blueprint("instances", __name__)


@instances.route(PREFIX, methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_instances():
    """Get BunkerWeb instances"""
    return get_core_format_res(f"{CORE_API}/instances", "GET", "", "Retrieve instances")


@instances.route(PREFIX, methods=["PUT"])
@jwt_required()
@jwt_additionnal_checks()
@model_validator(body={"UpsertInstance": ""}, queries={"method": "Method", "reload": "ReloadInstance"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def upsert_instance():
    """Upsert one or more BunkerWeb instances"""
    args, data, method, reload_inst = [get_req_data(request, ["method", "reload"])[k] for k in ("args", "data", "method", "reload")]
    return get_core_format_res(f"{CORE_API}/instances?method={method or 'ui'}&reload={reload_inst or ''}", "PUT", data, "Upsert instances")


@instances.route(f"{PREFIX}/<string:instance_hostname>", methods=["DELETE"])
@jwt_required()
@jwt_additionnal_checks()
@model_validator(queries={"method": "Method"}, params={"instance_hostname": "InstanceHostname"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def delete_instance(instance_hostname):
    """Delete BunkerWeb instance"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}?method={method or 'ui'}", "DELETE", "", f"Delete instance {instance_hostname}")


@instances.route(f"{PREFIX}/<string:instance_hostname>/<string:instance_action>", methods=["POST"])
@jwt_required()
@jwt_additionnal_checks()
@model_validator(queries={"method": "Method"}, params={"instance_hostname": "InstanceHostname", "instance_action": "InstanceAction"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def action_instance(instance_hostname, instance_action):
    """Send action to a BunkerWeb instance"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/{instance_hostname}/{instance_action}?method={method or 'ui'}", "POST", "", f"Send instance {instance_hostname} action : {instance_action}")


@instances.route(f"{PREFIX}/ban", methods=["POST"])
@jwt_required()
@jwt_additionnal_checks()
@model_validator(body={"BanAdd": "ban_add"}, queries={"method": "Method"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def add_bans():
    """Add bans ip for all instances"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method or 'ui'}", "POST", data, "Add bans ip")


@instances.route(f"{PREFIX}/ban", methods=["DELETE"])
@jwt_required()
@jwt_additionnal_checks()
@model_validator(body={"BanDelete": "ban_delete"}, queries={"method": "Method"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def delete_bans():
    """Delete bans ip for all instances"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/instances/ban?method={method or 'ui'}", "DELETE", data, "Delete bans ip")
