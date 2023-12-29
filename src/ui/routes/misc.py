# -*- coding: utf-8 -*-
from flask import Blueprint
from flask_jwt_extended import jwt_required

from hook import hooks

from utils import get_core_format_res, log_format
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/misc"

misc = Blueprint("misc", __name__)


@misc.route(f"{PREFIX}/version", methods=["GET"])
@jwt_required()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_version():
    """Get BunkerWeb version used"""
    return get_core_format_res(f"{CORE_API}/version", "GET", "", "Retrieve version")


@misc.route(f"{PREFIX}/health", methods=["GET"])
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_health():
    """Get BunkerWeb UI api health"""
    return log_format("success", "200", "/api/misc/health", {})
