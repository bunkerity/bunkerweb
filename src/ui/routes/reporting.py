# -*- coding: utf-8 -*-
from flask import Blueprint
from flask_jwt_extended import jwt_required

from middleware.jwt import jwt_additionnal_checks

from hook import hooks

from utils import get_core_format_res
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR

PREFIX = "/api/reporting"

reporting = Blueprint("reporting", __name__)


@reporting.route(PREFIX, methods=["GET"])
@jwt_required()
@jwt_additionnal_checks()
@hooks(hooks=["BeforeReqAPI", "AfterReqAPI"])
def get_reports():
    """Get all reports"""
    return get_core_format_res(f"{CORE_API}/reports", "GET", "", "Retrieve reports")
