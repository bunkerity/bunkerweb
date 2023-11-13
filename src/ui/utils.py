# -*- coding: utf-8 -*-
import requests, traceback, json  # noqa: E401
from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response
from werkzeug.exceptions import HTTPException
import json
from logging import Logger
from os.path import join, sep
from sys import path as sys_path
import os
from ui import UiConfig

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

UI_CONFIG = UiConfig("ui", **os.environ)


def get_core_format_res(path, method, data, message, retry=1):
    # Retry limit
    if retry == 5:
        raise HTTPException(response=Response(status=500), description="Max retry to core for same request exceeded")

    req = None
    # Try request core
    try:
        req = req_core(path, method)
        # Case 503, retry request
        if req.status_code == 503:
            return get_core_format_res(path, method, data, message, retry + 1)
        # Case error
        if req == "error":
            raise HTTPException(response=Response(status=500), description="Impossible to connect to CORE API")
    except:
        raise HTTPException(response=Response(status=500), description="Impossible to connect to CORE API")

    # Case response from core, format response for client
    try:
        data = req.text

        obj = json.loads(req.text)
        if isinstance(obj, dict):
            data = obj.get("message", obj)
            if isinstance(data, dict):
                data = data.get("data", data)

            data = json.dumps(data, skipkeys=True, allow_nan=True, indent=6)

        print(req.status_code)
        print(req.status_code == requests.codes.ok)

        return {"type": "success" if str(req.status_code).startswith("2") else "error", "status": str(req.status_code), "message": message, "data": data}
    # Case impossible to format
    except:
        print(traceback.format_exc())


def req_core(path, method, data=None):
    # Request core api and store response
    req = None
    try:
        if method.upper() == "GET":
            req = requests.get(path)

        if method.upper() == "POST":
            req = requests.post(path, data=data)

        if method.upper() == "DELETE":
            req = requests.delete(path, data=data)

        if method.upper() == "PATCH":
            req = requests.patch(path, data=data)

        if method.upper() == "PUT":
            req = requests.put(path, data=data)

        return req
    # Case no response from core
    except:
        return "error"


def default_res(type="error", status_code="500", path="", detail="Internal Server Error", data={}):
    return {"type": type, "status": status_code, "message": f"{path} {detail}", "data": data}


def validate_env_data():
    if not isinstance(UI_CONFIG.WAIT_RETRY_INTERVAL, int) and (not UI_CONFIG.WAIT_RETRY_INTERVAL.isdigit() or int(UI_CONFIG.WAIT_RETRY_INTERVAL) < 1):
        raise setupUIException("error", f"Invalid WAIT_RETRY_INTERVAL provided: {UI_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer.")

    if not isinstance(UI_CONFIG.MAX_WAIT_RETRIES, int) and (not UI_CONFIG.MAX_WAIT_RETRIES.isdigit() or int(UI_CONFIG.MAX_WAIT_RETRIES) < 1):
        raise setupUIException("error", f"Invalid MAX_WAIT_RETRIES provided: {UI_CONFIG.MAX_WAIT_RETRIES}, It must be a positive integer.")


class setupUIException(Exception):
    def __init__(self, log_type, msg):
        if log_type == "error":
            LOGGER.error(msg)

        if log_type == "exception":
            LOGGER.exception(msg)

        if not UI_CONFIG.EXIT_ON_FAILURE or UI_CONFIG.EXIT_ON_FAILURE == "yes":
            exit(1)
