# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/config"

config = Blueprint("config", __name__)


@config.route(f"{PREFIX}", methods=["GET"])
def get_config():
    """Get complete config"""
    args = request.args.to_dict()
    methods = args.get("methods") or False
    # is_valid_model(methods, Model) True | False
    new_format = args.get("new_format") or False
    # is_valid_model(new_format, Model) True | False
    return get_core_format_res(f"{CORE_API}/config?methods={methods}&new_format={new_format}", "GET", "", "Retrieve config")


@config.route(f"{PREFIX}", methods=["PUT"])
def update_config():
    """Update whole config"""
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    config = request.get_json()
    # is_valid_model(config, Model) True | False
    # data = json.dumps(config, skipkeys=True, allow_nan=True, indent=6) # TODO
    return get_core_format_res(f"{CORE_API}/config?method={method}", "PUT", config, "Update config")


@config.route(f"{PREFIX}/global", methods=["PUT"])
def update_global_config():
    """Update global config"""
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    config = request.get_json()
    # is_valid_model(config, Model) True | False
    data = json.dumps(config, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/config/global?method={method}", "PUT", data, "Update global config")


@config.route(f"{PREFIX}/service/<str:service_name>", methods=["PUT"])
def update_service_config(service_name):
    """Update service config"""
    # is_valid_model(service_name, Model) True | False
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    config = request.get_json()
    # is_valid_model(config, Model) True | False
    data = json.dumps(config, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/config/service/{service_name}?method={method}", "PUT", data, f"Update service config {service_name}")


@config.route(f"{PREFIX}/service/<str:service_name>", methods=["DELETE"])
def delete_service_config(service_name):
    """Delete service config"""
    # is_valid_model(service_name, Model) True | False
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    return get_core_format_res(f"{CORE_API}/config/service/{service_name}?method={method}", "DELETE", "", f"Delete service config {service_name}")
