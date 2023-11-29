# -*- coding: utf-8 -*-
from functools import wraps
from flask import request

from werkzeug.exceptions import HTTPException
from werkzeug.sansio.response import Response

from logging import Logger
from os.path import join, sep
from sys import path as sys_path
from ui import UiConfig
from os import environ


from os.path import join, sep
from sys import path as sys_path

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from api_models import BanAdd, BanDelete, Method  # type: ignore


def model_validator(f, body_model_name=None, q_model_dict=None):
    @wraps(f)
    def validate_user_data(*args, **kwargs):
        queries = request.args.to_dict() or None
        data = request.get_json() or None

        # We need model name for body data because we can't deduce it from data itself
        if len(data) != 0 and body_model_name:
            raise HTTPException(response=Response(status=400), description="Missing parameters to check format")

        # We need dict with { queryName : modelName } to handle queries
        if len(queries) != 0 and len(q_model_dict) == 0:
            raise HTTPException(response=Response(status=400), description="Missing parameters to check format")

        if body_model_name and len(data) != 0:
            try:
                class_ = getattr(__import__("models"), body_model_name)

                if isinstance(data, list):
                    data = {"list": data}

                class_(**data)

            except:
                raise HTTPException(response=Response(status=400), description="Request body bad format")

        if len(queries) != 0 and len(q_model_dict) != 0:
            # queries data list to check model
            try:
                for q_name, value in queries.items():
                    q_model_name = q_model_dict[q_name.lower()]
                    class_ = getattr(__import__("models"), q_model_name)
                    data = {[q_name]: value}
                    class_(**data)

            except:
                raise HTTPException(response=Response(status=400), description="Request queries bad format")
        return f(*args, **kwargs)

    return validate_user_data
