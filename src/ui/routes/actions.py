# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from middleware.validator import model_validator
from middleware.jwt import jwt_additionnal_checks

from hook import hooks

from utils import get_core_format_res, get_req_data
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

PREFIX = "/api/actions"

actions = Blueprint("actions", __name__)


@actions.route(PREFIX, methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_actions():
    """Get all actions"""
    return get_core_format_res(f"{CORE_API}/actions", "GET", "", "Retrieve actions")


@actions.route(PREFIX, methods=["POST"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
@model_validator(body={"Action": ""})
def create_action():
    """Create new action"""
    args, data = [get_req_data(request)[k] for k in ("args", "data")]
    return get_core_format_res(f"{CORE_API}/actions", "POST", data, "Create action")
