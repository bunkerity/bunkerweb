# -*- coding: utf-8 -*-
from flask import request
from flask import make_response
from flask import redirect
from flask import abort

from flask_jwt_extended import create_access_token
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager

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

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from utils import default_error_handler, create_action_format, res_format, log_format

from logging import Logger
from os.path import join, sep
from sys import path as sys_path
from ui import UiConfig
from os import environ

deps_path = join(sep, "usr", "share", "bunkerweb", "utils")
if deps_path not in sys_path:
    sys_path.append(deps_path)

from logger import setup_logger  # type: ignore

LOGGER: Logger = setup_logger("UI")
UI_CONFIG = UiConfig("ui", **environ)


def setup_jwt(app):
    # Setup the Flask-JWT-Extended extension
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]  # How JWT is handle
    app.config["JWT_COOKIE_SECURE"] = False  # ONLY HTTPS
    app.config["JWT_SECRET_KEY"] = "super-secret"  # Change for prod
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # Add CSRF TOKEN check
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
    JWTManager(app)

    # Override default exceptions to fit standard format
    @app.errorhandler(NoAuthorizationError)
    def no_authorization_exception(e):
        return abort(401, "Token unauthorized access.")

    @app.errorhandler(JWTDecodeError)
    def jwt_decode_exception(e):
        return abort(401, "Token Decode error.")

    @app.errorhandler(RevokedTokenError)
    def revoke_token_exception(e):
        return abort(401, "Token revoke token error.")

    @app.errorhandler(JWTDecodeError)
    def jwt_decode_exception(e):
        return abort(401, "Token decode error.")

    @app.errorhandler(UserClaimsVerificationError)
    def user_claim_verif_exception(e):
        return abort(401, "Token user claims verification error.")

    @app.errorhandler(WrongTokenError)
    def wrong_token_exception(e):
        return abort(401, "Token wrong token error.")

    @app.errorhandler(UserLookupError)
    def user_lookup_exception(e):
        return abort(403, "Token user lookup error.")

    @app.errorhandler(CSRFError)
    def csrf_exception(e):
        return abort(403, "CSRF error.")

    @app.errorhandler(FreshTokenRequired)
    def fresh_token_req_exception(e):
        return abort(401, "Token fresh required error.")

    @app.errorhandler(InvalidHeaderError)
    def invalid_header_exception(e):
        return abort(403, "Token invalid header error.")

    @app.errorhandler(InvalidQueryParamError)
    def invalid_query_param_exception(e):
        return abort(403, "Invalid query param error.")

    @app.after_request
    def refresh_expiring_jwts(response):
        # Add request that aren't concern by refresh (like get periodic logs)
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=5))
            if target_timestamp > exp_timestamp:
                access_token = create_access_token(identity=get_jwt_identity())
                set_access_cookies(response, access_token)
                identity = get_jwt_identity()
                LOGGER.info(log_format("info", "", "", f"Refresh JWT for user {identity}"))
                create_action_format("success", "200", "Crendentials : refresh token", f"Refresh token for user {identity}.", ["ui", "credentials"])
            return response
        except (RuntimeError, KeyError):
            # Case where there is not a valid JWT. Just return the original response
            return response

    # Create a route to authenticate your users and return JWTs
    @app.route("/login", methods=["POST"])
    def add_jwt():
        username = request.form.get("username", None)
        password = request.form.get("password", None)
        if username != UI_CONFIG.ADMIN_USERNAME or password != UI_CONFIG.ADMIN_PASSWORD:
            LOGGER.info(log_format("info", "", "", f"User try to log in but failed"))
            create_action_format("error", "403", "Crendentials : UI failed login", f"User tried to login but failed", ["ui", "credentials"])
            return make_response(redirect("/admin/login?error=True", 302))

        access_token = create_access_token(identity=username)
        resp = make_response(redirect("/admin/home", 302))
        set_access_cookies(resp, access_token)
        LOGGER.info(log_format("info", "", "", f"User {username} login"))
        create_action_format("success", "200", "Crendentials : UI login", f"{username} login to UI", ["ui", "credentials"])
        return resp

    # Remove cookies
    @app.route("/logout", methods=["POST"])
    @jwt_required()
    def delete_jwt():
        resp = make_response(res_format("success", "200", "", "Logout succeed.", {}), 200)
        identity = get_jwt_identity()
        LOGGER.info(log_format("info", "", "", f"Try to logout user {identity}"))
        try:
            unset_jwt_cookies(resp)
            LOGGER.info(log_format("info", "", "", f"User {identity} successfully logout"))
            create_action_format("success", "200", "Crendentials : UI logout", f"User {identity} logout from UI", ["ui", "credentials"])
            return resp
        except:
            return default_error_handler("500", "", "Try to logout user {identity} but failed.", ["ui", "exception", "credentials"])
