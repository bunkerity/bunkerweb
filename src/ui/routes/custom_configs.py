# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/custom_configs"

custom_configs = Blueprint("custom_configs", __name__)


@custom_configs.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_custom_configs():
    """Get complete custom configs"""
    return get_core_format_res(f"{CORE_API}/custom_configs", "GET", "", "Retrieve custom configs")


@custom_configs.route(f"{PREFIX}", methods=["PUT"])
@jwt_required()
def update_custom_configs():
    """Update one or more custom configs"""
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    custom_config = request.get_json()
    # is_valid_model(custom_config, Model) True | False
    data = json.dumps(custom_config, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/custom_configs?method={method}", "PUT", data, "Update custom configs")


@custom_configs.route(f"{PREFIX}/<string:custom_config_name>", methods=["DELETE"])
@jwt_required()
def delete_custom_configs(custom_config_name):
    """Delete a custom config by name"""
    # is_valid_model(custom_config_name, Model) True | False
    args = request.args.to_dict()
    method = args.get("method") or "ui"
    # is_valid_model(method, Model) True | False
    custom_config = request.get_json()
    # is_valid_model(custom_config, Model) True | False
    data = json.dumps(custom_config, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/custom_configs/{custom_config_name}?method={method}", "DELETE", data, f"Delete custom config {custom_config_name}")
