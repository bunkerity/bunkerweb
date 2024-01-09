# -*- coding: utf-8 -*-

from werkzeug.exceptions import HTTPException
from hook import hooks
from utils import format_exception

from flask_jwt_extended.exceptions import CSRFError
from flask_jwt_extended.exceptions import FreshTokenRequired
from flask_jwt_extended.exceptions import InvalidHeaderError
from flask_jwt_extended.exceptions import InvalidQueryParamError
from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended.exceptions import UserLookupError
from flask_jwt_extended.exceptions import JWTDecodeError
from flask_jwt_extended.exceptions import RevokedTokenError
from flask_jwt_extended.exceptions import UserClaimsVerificationError
from flask_jwt_extended.exceptions import WrongTokenError


# Error while trying to login
class LoginFailedException(HTTPException):
    code = 403
    description = "Error while trying to login"


@hooks(hooks=["LoginException"])
@format_exception(_redirect=True)
def login_failed_exception(e):
    return e


# Error while trying to login
class LogoutFailedException(HTTPException):
    code = 500
    description = "Error while trying to logout"


@hooks(hooks=["LogoutException"])
@format_exception(_redirect=True)
def logout_failed_exception(e):
    return e


# Export on main app to register
def setup_jwt_exceptions(app):
    # Custom exceptions
    app.register_error_handler(LoginFailedException, login_failed_exception)
    app.register_error_handler(LogoutFailedException, logout_failed_exception)

    # JWT DEFAULT EXCEPTIONS
    @app.errorhandler(NoAuthorizationError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def no_authorization_exception(e):
        e.code = 401
        e.description = "Token unauthorized access."
        return e

    @app.errorhandler(JWTDecodeError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def jwt_decode_exception(e):
        e.code = 401
        e.description = "Token Decode error."
        return e

    @app.errorhandler(RevokedTokenError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def revoke_token_exception(e):
        e.code = 401
        e.description = "Token revoke token error."
        return e

    @app.errorhandler(UserClaimsVerificationError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def user_claim_verif_exception(e):
        e.code = 401
        e.description = "Token user claims verification error."
        return e

    @app.errorhandler(WrongTokenError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def wrong_token_exception(e):
        e.code = 401
        e.description = "Token wrong token error."
        return e

    @app.errorhandler(UserLookupError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def user_lookup_exception(e):
        e.code = 403
        e.description = "Token user lookup error."
        return e

    @app.errorhandler(CSRFError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def csrf_exception(e):
        e.code = 403
        e.description = "CSRF error."
        return e

    @app.errorhandler(FreshTokenRequired)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def fresh_token_req_exception(e):
        e.code = 401
        e.description = "Token fresh required error."
        return e

    @app.errorhandler(InvalidHeaderError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def invalid_header_exception(e):
        e.code = 403
        e.description = "Token invalid header error."
        return e

    @app.errorhandler(InvalidQueryParamError)
    @hooks(hooks=["TokenException"])
    @format_exception(_redirect=True)
    def invalid_query_param_exception(e):
        e.code = 403
        e.description = "Invalid query param error."
        return e
