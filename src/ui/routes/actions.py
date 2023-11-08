# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/actions"

actions = Blueprint('actions', __name__)

@actions.route(f"{PREFIX}", methods=['GET'])
def get_actions():
    """ Get all actions """
    return get_core_format_res(f"{CORE_API}/actions", "GET", "", "Retrieve actions")

@actions.route(f"{PREFIX}", methods=['POST'])
def create_action():
    """ Create new action """
    action_data = request.get_json()
    # is_valid_model(json_data, Model) True | False
    data = json.dumps(action_data, skipkeys=True, allow_nan=True, indent=6)
    return get_core_format_res(f"{CORE_API}/actions", "POST", data, "Create action")
