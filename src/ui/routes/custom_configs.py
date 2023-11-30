# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.validator import model_validator

from utils import get_core_format_res, get_req_data
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
@model_validator(body="UpsertCustomConfigDataModel", queries={"method": "Method"})
def update_custom_configs():
    """Update one or more custom configs"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/custom_configs?method={method if method else 'ui'}", "PUT", data, "Update custom configs")


@custom_configs.route(f"{PREFIX}/<string:custom_config_name>", methods=["DELETE"])
@jwt_required()
@model_validator(body="CustomConfigModel", queries={"method": "Method"}, params={"custom_config_name": "CustomConfigName"})
def delete_custom_configs(custom_config_name):
    """Delete a custom config by name"""
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/custom_configs/{custom_config_name}?method={method if method else 'ui'}", "DELETE", data, f"Delete custom config {custom_config_name}")
