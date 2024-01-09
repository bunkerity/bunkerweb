# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request
from flask_jwt_extended import jwt_required

from utils import get_core_format_res, get_req_data

from middleware.validator import model_validator

from hook import hooks

from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/account"

account = Blueprint("account", __name__)


@account.route(f"{PREFIX}/account", methods=["GET"])
@jwt_required()
@model_validator(queries={"method": "Method"})
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_account():
    # Check if plugin id exists
    args, data, method = [get_req_data(request, ["method"])[k] for k in ("args", "data", "method")]
    return get_core_format_res(f"{CORE_API}/account?method={method or 'ui'}", "GET", data, "Get account info from database")
