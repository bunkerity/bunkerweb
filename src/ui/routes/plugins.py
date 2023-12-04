# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.validator import model_validator

from utils import get_core_format_res
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/plugins"

plugins = Blueprint("plugins", __name__)


@plugins.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_plugins():
    """Get all plugins"""
    return get_core_format_res(f"{CORE_API}/plugins", "GET", "", "Retrieve plugins")


@plugins.route(f"{PREFIX}", methods=["POST"])
@jwt_required()
@model_validator(is_body_json=False)
def add_plugin():
    """Add a plugin to BunkerWeb"""
    plugin = request.get_data()
    return get_core_format_res(f"{CORE_API}/plugins", "POST", plugin, "Adding plugin")


@plugins.route(f"{PREFIX}/<string:plugin_id>", methods=["PATCH"])
@jwt_required()
@model_validator(is_body_json=False, params={"plugin_id": "PluginId"})
def update_plugin(plugin_id):
    """Update a plugin"""
    plugin = request.get_data()
    return get_core_format_res(f"{CORE_API}/plugins/{plugin_id}", "PATCH", plugin, f"Update plugin {plugin_id}")


@plugins.route(f"{PREFIX}/<string:plugin_id>", methods=["DELETE"])
@jwt_required()
@model_validator(params={"plugin_id": "PluginId"})
def delete_plugin(plugin_id):
    """Delete a plugin"""
    return get_core_format_res(f"{CORE_API}/plugins/{plugin_id}", "DELETE", "", f"Delete plugin {plugin_id}")


@plugins.route(f"{PREFIX}/external/files", methods=["GET"])
@jwt_required()
@model_validator()
def external_files_plugin():
    """Get external files with plugins"""
    return get_core_format_res(f"{CORE_API}/plugins/external/files", "GET", "", "Plugin external files")
