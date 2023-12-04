# -*- coding: utf-8 -*-
from contextlib import suppress
import requests, json  # noqa: E401
from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response
from logging import Logger
from os.path import join, sep
from sys import path as sys_path
import os
from ui import UiConfig
from datetime import datetime

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

UI_CONFIG = UiConfig("ui", **os.environ)
CORE_API = UI_CONFIG.CORE_ADDR


def get_req_data(req, queries=[]):
    # get body json or fallback
    try:
        body = req.get_json()
    except:
        body = None

    data = {}
    if body and len(body) > 0:
        data = json.dumps(body, skipkeys=True, allow_nan=True, indent=6)

    # get queries
    args = req.args.to_dict()

    # Set data
    result = {}

    for query in queries:
        result[query] = args.get(query) if args.get(query) else ""

    result["args"] = args
    result["data"] = data

    return result


# Communicate with core and send response to client
def get_core_format_res(path, method, data=None, message=None, retry=1):
    # Retry limit
    if retry == 5:
        raise HTTPException(response=Response(status=500), description="Max retry to CORE  API for same request exceeded")

    # Try request core
    req = None
    try:
        req = req_core(path, method, data)
        # Case 503, retry request
        if req.status_code == 503:
            LOGGER.warn(log_format("warn", "503", path, f"Communicate with {path} {method} retry={retry}. Maybe CORE is setting something up on background.", data))
            return get_core_format_res(path, method, data, message, retry + 1)
    except:
        raise HTTPException(response=Response(status=500), description="Impossible to connect to CORE API")

    # Case response from core, format response for client
    try:
        # Proceed data
        data = req.text

        obj = json.loads(req.text)
        if isinstance(obj, dict):
            data = obj.get("message", obj)
            if isinstance(data, dict):
                data = data.get("data", data)

            data = json.dumps(data, skipkeys=True, allow_nan=True, indent=6)

        # Additional info
        res_type = "success" if str(req.status_code).startswith("2") else "error"
        res_status = str(req.status_code)

        if res_type == "error":
            LOGGER.error(log_format(res_type, res_status, path, message, data))

        return res_format(res_type, res_status, "", message, data)
    # Case impossible to format
    except:
        raise HTTPException(response=Response(status=500), description="Impossible for UI API to proceed data send by CORE API")


def req_core(path, method, data=None):
    # Request core api and store response
    req = None
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


# Standard response format
def res_format(type="error", status_code="500", path="", detail="Internal Server Error", data={"message": "error"}):
    return json.dumps({"type": type, "status": status_code, "message": f"{path} {detail}", "data": data}, skipkeys=True, allow_nan=True, indent=6)


# Standard log format
def log_format(type="", status_code="500", path="", detail="Internal Server Error", data=""):
    return f"[UI] {status_code} {path} || {detail} || {f'data : {data}' if data else ''}"


# Send action to CORE
def create_action_format(type="info", status_code="500", title="", detail="", tags=["ui", "exception"], exception_logger=True):
    data = json.dumps(
        {"date": datetime.now().isoformat(), "api_method": "UNKNOWN", "method": "ui", "title": title, "description": f"{detail} { f'(status {status_code})' if status_code else ''}", "status": type, "tags": tags},
        skipkeys=True,
        allow_nan=True,
        indent=6,
    )
    try:
        requests.post(f"{CORE_API}/actions", data=data)
    except:
        if exception_logger:
            LOGGER.error(log_format("error", "500", "", f"Try to send action to CORE but failed. CORE down or data invalid ({data})."))


# Handle error and exception with default format
# We need to log, send action and error response
def default_error_handler(code="500", path="", desc="Internal server error.", tags=["ui", "exception"]):
    # Try to send details
    try:
        LOGGER.error(log_format("error", code, path, desc))
        create_action_format("error", code, f"UI exception {'path : ' + path if path else ''}", desc, tags)
        return res_format("error", code, path, desc)
    # Case impossible to send custom data and detail, send fallback
    except:
        LOGGER.error(log_format("error", "500", "", "Internal server error but impossible to get detail."))
        create_action_format("error", "500", "UI exception", "Internal server error but impossible to get detail.", tags)
        return res_format("error", "500", "", "Internal server error.")


# Exception on main.py when we are starting UI
class setupUIException(Exception):
    def __init__(self, log_type, msg, send_action=True):
        # We can specify error or exception (traceback)
        if log_type == "error":
            LOGGER.error(log_format("exception", "500", "", msg))

        if log_type == "exception":
            LOGGER.exception(log_format("exception", "500", "", msg))

        # Try to store exception as action on core to keep track
        with suppress(BaseException):
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Impossible to execute UI properly.", ["exception", "ui", "setup"])

        # Exit or not on failure
        if not UI_CONFIG.EXIT_ON_FAILURE or UI_CONFIG.EXIT_ON_FAILURE == "yes":
            LOGGER.warn(log_format("warn", "500", "", "Error while UI setup and exit on failure. Impossible to access UI."))
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Error while UI setup and exit on failure. Impossible to access UI.", ["exception", "ui", "setup"])
            exit(1)
        else:
            LOGGER.warn(log_format("warn", "500", "", "Error while UI setup but keep running on failure. UI could not run correctly."))
            if send_action:
                create_action_format("error", "500", "UI setup exception", "Error while UI setup but keep running on failure. UI could not run correctly.", ["exception", "ui", "setup"])
