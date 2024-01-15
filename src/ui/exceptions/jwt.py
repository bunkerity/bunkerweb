# -*- coding: utf-8 -*-

from werkzeug.exceptions import HTTPException
from hook import hooks
from utils import log_exception
from utils import redirect_page

from jwt import DecodeError as DecodeErrorJWT
from jwt import ExpiredSignatureError as ExpiredSignatureErrorJWT
from jwt import InvalidAudienceError as InvalidAudienceErrorJWT
from jwt import InvalidIssuerError as InvalidIssuerErrorJWT
from jwt import InvalidTokenError as InvalidTokenErrorJWT
from jwt import MissingRequiredClaimError as MissingRequiredClaimErrorJWT

from flask_jwt_extended.exceptions import CSRFError as CSRFErrorJWT
from flask_jwt_extended.exceptions import FreshTokenRequired as FreshTokenRequiredJWT
from flask_jwt_extended.exceptions import InvalidHeaderError as InvalidHeaderErrorJWT
from flask_jwt_extended.exceptions import InvalidQueryParamError as InvalidQueryParamErrorJWT
from flask_jwt_extended.exceptions import NoAuthorizationError as NoAuthorizationErrorJWT
from flask_jwt_extended.exceptions import UserLookupError as UserLookupErrorJWT
from flask_jwt_extended.exceptions import JWTDecodeError as JWTDecodeErrorJWT
from flask_jwt_extended.exceptions import RevokedTokenError as RevokedTokenErrorJWT
from flask_jwt_extended.exceptions import UserClaimsVerificationError as UserClaimsVerificationErrorJWT
from flask_jwt_extended.exceptions import WrongTokenError as WrongTokenErrorJWT


# Error while trying to login
class LoginFailedException(HTTPException):
    code = 403
    description = "Error while trying to login"


@hooks(hooks=["LoginException"])
@log_exception(LoginFailedException)
def login_failed_exception(e):
    return redirect_page()


# Error while trying to login
class LogoutFailedException(HTTPException):
    code = 500
    description = "Error while trying to logout"


@hooks(hooks=["LogoutException"])
@log_exception(LogoutFailedException)
def logout_failed_exception(e):
    return redirect_page()


class DecodeError(HTTPException):
    code = 401
    description = "Token decode error."


class ExpiredSignatureError(HTTPException):
    code = 403
    description = "Token expired."


class InvalidAudienceError(HTTPException):
    code = 401
    description = "Token invalid audience."


class InvalidIssuerError(HTTPException):
    code = 401
    description = "Token invalid issuer."


class InvalidTokenError(HTTPException):
    code = 401
    description = "Token invalid."


class MissingRequiredClaimError(HTTPException):
    code = 401
    description = "Token missing required claim."


class NoAuthorizationError(HTTPException):
    code = 401
    description = "Token unauthorized access."


class JWTDecodeError(HTTPException):
    code = 401
    description = "Token Decode error."


class RevokedTokenError(HTTPException):
    code = 403
    description = "Token revoked."


class UserClaimsVerificationError(HTTPException):
    code = 401
    description = "Token user claims verification error."


class WrongTokenError(HTTPException):
    code = 401
    description = "Token wrong."


class UserLookupError(HTTPException):
    code = 403
    description = "Token user lookup error."


class CSRFError(HTTPException):
    code = 403
    description = "CSRF error."


class FreshTokenRequired(HTTPException):
    code = 401
    description = "Token fresh required error."


class InvalidHeaderError(HTTPException):
    code = 403
    description = "Token invalid header error."


class InvalidQueryParamError(HTTPException):
    code = 403
    description = "Token invalid query param error."


# Export on main app to register
def setup_jwt_exceptions(app):
    # Custom exceptions
    app.register_error_handler(LoginFailedException, login_failed_exception)
    app.register_error_handler(LogoutFailedException, logout_failed_exception)

    # JWT EXCEPTIONS
    @app.errorhandler(DecodeErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(DecodeError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(ExpiredSignatureErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(ExpiredSignatureError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(InvalidAudienceErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(InvalidAudienceError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(InvalidIssuerErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(InvalidIssuerError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(InvalidTokenErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(InvalidTokenError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(MissingRequiredClaimErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(MissingRequiredClaimError)
    def no_authorization_exception(e):
        return redirect_page()

    # JWT EXTENEDED DEFAULT EXCEPTIONS
    @app.errorhandler(NoAuthorizationErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(NoAuthorizationError)
    def no_authorization_exception(e):
        return redirect_page()

    @app.errorhandler(JWTDecodeErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(JWTDecodeError)
    def jwt_decode_exception(e):
        return redirect_page()

    @app.errorhandler(RevokedTokenErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(RevokedTokenError)
    def revoke_token_exception(e):
        return redirect_page()

    @app.errorhandler(UserClaimsVerificationErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(UserClaimsVerificationError)
    def user_claim_verif_exception(e):
        return redirect_page()

    @app.errorhandler(WrongTokenErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(WrongTokenError)
    def wrong_token_exception(e):
        return redirect_page()

    @app.errorhandler(UserLookupErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(UserLookupError)
    def user_lookup_exception(e):
        return redirect_page()

    @app.errorhandler(CSRFErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(CSRFError)
    def csrf_exception(e):
        return redirect_page()

    @app.errorhandler(FreshTokenRequiredJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(FreshTokenRequired)
    def fresh_token_req_exception(e):
        return redirect_page()

    @app.errorhandler(InvalidHeaderErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(InvalidHeaderError)
    def invalid_header_exception(e):
        return redirect_page()

    @app.errorhandler(InvalidQueryParamErrorJWT)
    @hooks(hooks=["TokenException"])
    @log_exception(InvalidQueryParamError)
    def invalid_query_param_exception(e):
        return redirect_page()
