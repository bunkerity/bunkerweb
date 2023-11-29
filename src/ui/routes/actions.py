# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

from os.path import join, sep
from sys import path as sys_path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from api_models import Action  # type: ignore

PREFIX = "/api/actions"

actions = Blueprint("actions", __name__)


@actions.route(f"{PREFIX}", methods=["GET"])
@jwt_required()
def get_actions():
    """Get all actions"""
    return get_core_format_res(f"{CORE_API}/actions", "GET", "", "Retrieve actions")


@actions.route(f"{PREFIX}", methods=["POST"])
@jwt_required()
def create_action():
    """Create new action"""
    action = request.get_json()
    try:
        Action(**action)
    except:
        raise HTTPException(response=Response(status=400), description=f"Request args bad format")
    data = json.dumps(action, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/actions", "POST", data, "Create action")
