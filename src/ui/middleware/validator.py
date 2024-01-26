# -*- coding: utf-8 -*-
from functools import wraps
from flask import request

from exceptions.validator import ValidatorFormatException
from exceptions.validator import ValidatorBodyException
from exceptions.validator import ValidatorQueryException

from hook import hooks

from logging import Logger
from os.path import join, sep
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)


from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")


# Add decorator to routes in order to validate model


# body = dict[modelName : modelKeyword || ""]: modelKeyword if we want to check data structure itself (for example, if we have a tuple, a dict...)
# in case  modelKeyword is a string, we want to check kwargs
# queries = dict[queryName, modelName] :  query and model name to check
@hooks(hooks=["BeforeValidator", "AfterValidator"])
def model_validator(body={}, queries={}, params={}, is_body_json=True):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Validate dynamic route params
            if kwargs and not params:
                raise ValidatorFormatException

            # Validate path params
            try:
                for p_name, p_value in params.items():
                    class_ = getattr(__import__("api_models"), p_value)
                    data = {p_name: kwargs[p_name]}

                    class_(**data)
            except:
                raise ValidatorFormatException

            # Validate body and queries
            req_queries = request.args.to_dict() if len(request.args) else {}
            data = request.get_json() if len(request.data) else {}

            # We need model name for body data because we can't deduce it from data itself
            if not len(data) and len(body) and is_body_json or len(data) and not len(body) and is_body_json:
                raise ValidatorFormatException

            # We need dict with { queryName : modelName } to handle queries
            if len(req_queries) and not len(queries) or not len(req_queries) and len(queries):
                raise ValidatorFormatException

            # Check model body
            if len(body) and len(data) and is_body_json:
                try:
                    body_model_name = list(body.keys())[0]
                    body_model_key = body[body_model_name]
                    class_ = getattr(__import__("api_models"), body_model_name)

                    # Case we have a body_model_key, we want to put data in a dict with body_model_key as key
                    # in order to destructure it and check data format itself (if it is a dict, a tuple, a list...)
                    # else we are gonna check kwargs (dict or list content)
                    if body_model_key:
                        data = {body_model_key: data}

                    class_(**data)

                except:
                    raise ValidatorBodyException(f"Request body ({body}) doesn't match model ({body_model_name})")

            # check model query
            if len(req_queries) and len(queries):
                try:
                    for q_name, q_value in queries.items():
                        class_ = getattr(__import__("api_models"), q_value)
                        data = {q_name: req_queries[q_name]}
                        class_(**data)

                except:
                    raise ValidatorQueryException(f"Queries ({req_queries}) doesn't match model ({queries})")

            return f(*args, **kwargs)

        return wrapped

    return decorator
