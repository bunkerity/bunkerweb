# -*- coding: utf-8 -*-
from functools import wraps
from flask import request
from flask import make_response
from flask import abort

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

from logging import Logger
from os.path import join, sep
from sys import path as sys_path
from ui import UiConfig
from os import environ

from utils import default_error_handler

from os.path import join, sep
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)


from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")

# body = str : name of the model to check body data
# queries = dict[queryName, modelName] :  query and model name to check
def model_validator(body=None, queries=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            req_queries = request.args.to_dict() or None
            data = request.get_json() or None

            # We need model name for body data because we can't deduce it from data itself
            if len(data) != 0 and body == 0:
                return abort(400, "Bad format, missing parameters")

            # We need dict with { queryName : modelName } to handle queries
            if len(req_queries) != 0 and len(queries) == 0:
                return abort(400, "Bad format, missing parameters")

            # Check model body
            if len(body) != 0 and len(data) != 0:
                try:
                    class_ = getattr(__import__("api_models"), body)

                    if isinstance(data, list):
                        data = {"list": data}

                    class_(**data)

                except:
                    return abort(400, "Bad format request body")

            # check model query
            if len(req_queries) != 0 and len(queries) != 0:
                try:
                    for q_name, value in req_queries.items():
                        q_model_name = queries[q_name.lower()]
                        class_ = getattr(__import__("api_models"), q_model_name)
                        data = {q_name: value}
                        class_(**data)

                except:
                    return abort(400, "Bad format request queries")
            
            return f(*args, **kwargs)
        return wrapped 
    return decorator
