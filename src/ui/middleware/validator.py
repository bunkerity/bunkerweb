# -*- coding: utf-8 -*-
from functools import wraps
from flask import request
from flask import abort

from logging import Logger
from os.path import join, sep
from sys import path as sys_path

from os.path import join, sep
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)


from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")


# body = str : name of the model to check body data
# queries = dict[queryName, modelName] :  query and model name to check
def model_validator(body=None, queries=None, is_body_json=True, params=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Validate dynamic route params
            if kwargs and not params:
                return abort(400, "Bad format, missing parameters")

            try:
                for p_name, p_value in params.items():
                    p_model_name = queries[p_name]
                    class_ = getattr(__import__("api_models"), p_model_name)
                    data = {p_name: p_value}
                    class_(**data)

            except:
                return abort(400, "Bad format request path params")

            # Validate body and queries
            req_queries = request.args.to_dict() or None
            data = request.get_json() or None

            # We need model name for body data because we can't deduce it from data itself
            if not len(data) and len(body) and is_body_json or len(data) and len(body) and is_body_json:
                return abort(400, "Bad format, missing parameters")

            # We need dict with { queryName : modelName } to handle queries
            if len(req_queries) and not len(queries):
                return abort(400, "Bad format, missing parameters")

            # Check model body
            if len(body) and len(data) and is_body_json:
                try:
                    class_ = getattr(__import__("api_models"), body)

                    if isinstance(data, list):
                        data = {"list": data}

                    class_(**data)

                except:
                    return abort(400, "Bad format request body")

            # check model query
            if len(req_queries) and len(queries):
                try:
                    for q_name, q_value in req_queries.items():
                        q_model_name = queries[q_name]
                        class_ = getattr(__import__("api_models"), q_model_name)
                        data = {q_name: q_value}
                        class_(**data)

                except:
                    return abort(400, "Bad format request queries")

            return f(*args, **kwargs)

        return wrapped

    return decorator
