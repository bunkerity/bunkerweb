# -*- coding: utf-8 -*-
from flask import Blueprint
from flask import request

from utils import get_core_format_res
import json
from os import environ
from ui import UiConfig

UI_CONFIG = UiConfig("ui", **environ)

CORE_API = UI_CONFIG.CORE_ADDR
PREFIX = "/api/misc"

misc = Blueprint('misc', __name__)

@misc.route(f"{PREFIX}/version", methods=['GET'])
def get_version():
    """ Get BunkerWeb version used """
    return get_core_format_res(f"{CORE_API}/version", "GET", "", "Retrieve version")
