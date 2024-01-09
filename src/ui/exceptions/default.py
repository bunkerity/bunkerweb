# -*- coding: utf-8 -*-
from hook import hooks
from utils import format_exception

from werkzeug.exceptions import Unauthorized
from werkzeug.exceptions import NotFound
from werkzeug.exceptions import Forbidden
from werkzeug.exceptions import BadRequest
from werkzeug.exceptions import InternalServerError


# Export on main app to register
def setup_default_exceptions(app):
    # Built-in error handler
    @app.errorhandler(InternalServerError)
    @hooks(hooks=["GlobalException"])
    @format_exception()
    def handle_internal_server_error(e):
        """Internal Server Error mainly handle CORE communications or proceed errors"""
        return e

    @app.errorhandler(BadRequest)
    @hooks(hooks=["GlobalException"])
    @format_exception()
    def handle_bad_request(e):
        """Bad Request mainly handle pydantic validation error"""
        return e

    @app.errorhandler(Unauthorized)
    @hooks(hooks=["GlobalException"])
    @format_exception()
    def handle_unauthorized(e):
        """Unauthorized mainly handle JWT or CSRF errors"""
        return e

    @app.errorhandler(Forbidden)
    @hooks(hooks=["GlobalException"])
    @format_exception()
    def handle_forbidden(e):
        """Forbidden mainly handle JWT errors"""
        return e

    @app.errorhandler(NotFound)
    @hooks(hooks=["GlobalException"])
    @format_exception()
    def handle_not_found(e):
        """Not Found mainly handle html pages not found"""
        return e
