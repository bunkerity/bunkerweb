# -*- coding: utf-8 -*-
from flask import Response

from utils import default_error_handler

from werkzeug.exceptions import Unauthorized
from werkzeug.exceptions import NotFound
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import InternalServerError


def setup_exceptions(app):
    @app.errorhandler(InternalServerError)
    def handle_exception(e):
        """Internal Server Error mainly handle CORE communications or proceed errors"""
        return default_error_handler(e.code, "", e.description)

    @app.errorhandler(BadRequest)
    def handle_exception(e):
        """Bad Request mainly handle pydantic validation error"""
        default_error_handler(e.code, "", e.description)
        res = Response(status=e.code)
        return res

    @app.errorhandler(Unauthorized)
    def handle_exception(e):
        """Unauthorized mainly handle JWT or CSRF errors"""
        default_error_handler(e.code, "", e.description)
        res = Response(status=e.code)
        return res

    @app.errorhandler(Forbidden)
    def handle_exception(e):
        """Forbidden mainly handle JWT errors"""
        default_error_handler(e.code, "", e.description)
        res = Response(status=e.code)
        return res

    @app.errorhandler(NotFound)
    def handle_exception(e):
        """Not Found mainly handle html pages not found"""
        default_error_handler(e.code, "", e.description)
        res = Response(status=e.code)
        return res
