# -*- coding: utf-8 -*-
from hook import hooks


# Register to main
def setup_default_middleware(app):
    @app.before_request
    @hooks(hooks=["BeforeReq"])
    def before_req_middleware():
        """Security middleware for login users."""

    @app.after_request
    @hooks(hooks=["AfterReq"])
    def after_req_middleware(response):
        """Set the Content-Security-Policy header to prevent XSS attacks."""
        response.headers["Content-Security-Policy"] = "object-src 'none'; frame-ancestors 'self';"
        return response
