# -*- coding: utf-8 -*-
from pathlib import Path
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required
from flask import render_template_string


from hook import hooks

import requests
from utils import get_core_format_res

from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/database"

database = Blueprint("database", __name__)


@database.route(f"{PREFIX}/database", methods=["GET"])
@jwt_required()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def communicate_database():
    # Check if plugin id exists
    pass
  