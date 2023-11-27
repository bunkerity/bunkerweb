# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

import requests
from importlib import import_module
from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/external"

external = Blueprint("external", __name__)


@external.route(f"{PREFIX}/<string:plugin_id>", methods=["GET", "POST", "PUT", "DELETE"])
@jwt_required()
def get_config(plugin_id):
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
            raise HTTPException(response=Response(status=500), description="Plugin not find to execute action.")

    except:
        raise HTTPException(response=Response(status=500), description="Error while trying to find plugin.")

    # Try to get module
    module = None
    try:
        module = requests.get(f"{CORE_API}/plugins/external/actions")
        if not str(module.status_code).startswith("2"):
            raise HTTPException(response=Response(status=500), description="Actions module not find to execute action.")
    except:
        raise HTTPException(response=Response(status=500), description="Error while trying to get actions module.")

    # Try to execute function
    args = request.args.to_dict()
    action = args.get("action")
    body = request.get_json() or ""
    result = None
    try:
        # import module by name
        m = import_module(module.content, __name__)
        # get function by name
        f = getattr(m, action)
        # call function with params
        # Need to return a standard format response
        result = f(body, args)
        if not str(result).startswith("2"):
            raise HTTPException(response=Response(status=500), description="Action result error.")
    except:
        raise HTTPException(response=Response(status=500), description="Error while trying to execute action")

    # Return format data
    return result
