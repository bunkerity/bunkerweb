# -*- coding: utf-8 -*-
from pathlib import Path
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

import requests
from utils import get_core_format_res

from os import environ
from ui import UiConfig

from tempfile import TemporaryFile
from importlib.machinery import SourceFileLoader

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/external"

external = Blueprint("external", __name__)


# Communicate with CORE retrieving ui api file and executing a specific function (action name)
@external.route(f"{PREFIX}/<string:plugin_id>/action", methods=["GET", "POST", "PUT", "DELETE"])
@jwt_required()
def exec_ext_plugin_action(plugin_id):
    """Execute custom external plugin action"""
    # Check if plugin id exists
    is_plugin = False
    try:
        plugins = get_core_format_res(f"{CORE_API}/plugins")
        for item in plugins["data"]:
            if plugin_id == item["id"]:
                is_plugin = True
                break

        if not is_plugin:
            raise HTTPException(response=Response(status=500), description=f"Plugin {plugin_id} not find to execute action.")

    except:
        raise HTTPException(response=Response(status=500), description=f"Error while trying to find plugin {plugin_id}.")

    # Try to get module (python file)
    module = None
    try:
        module = requests.get(f"{CORE_API}/plugins/external/{plugin_id}/action")
        if not str(module.status_code).startswith("2"):
            raise HTTPException(response=Response(status=500), description=f"Actions module not find to execute action for plugin {plugin_id}.")
    except:
        raise HTTPException(response=Response(status=500), description=f"Error while trying to get actions module for plugin {plugin_id}.")

    # Try to execute function
    args = request.args.to_dict()
    action = args.get("action") or ""
    if not action:
        raise HTTPException(response=Response(status=400), description=f"No action query found to execute action for plugin {plugin_id}.")
    body = request.get_json() or ""
    # Create temp file that can be use as module to execute action (action = function name on the module)
    try:
        content = module.content.decode("utf-8")
        with TemporaryFile(mode="wb", suffix=".py", delete=False) as temp:
            Path(temp.name).write_text(content)
            loader = SourceFileLoader("actions", temp.name)
            actions = loader.load_module()
            f = getattr(actions, action)
            # Send body and args
            result = f(body, args, request.method)
            return result
    except:
        raise HTTPException(response=Response(status=500), description=f"Error while trying to execute action for plugin {plugin_id}.")
