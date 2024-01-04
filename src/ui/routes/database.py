# -*- coding: utf-8 -*-
from flask import Blueprint
from flask_jwt_extended import jwt_required

from hook import hooks

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
