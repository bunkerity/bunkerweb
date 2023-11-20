# -*- coding: utf-8 -*-
from flask import request
from flask import make_response
from flask import redirect

from flask_jwt_extended import create_access_token
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import JWTManager

from flask_jwt_extended.exceptions import NoAuthorizationError
from flask_jwt_extended.exceptions import UserLookupError
from flask_jwt_extended.exceptions import CSRFError
from flask_jwt_extended.exceptions import FreshTokenRequired
from flask_jwt_extended.exceptions import InvalidHeaderError
from flask_jwt_extended.exceptions import InvalidQueryParamError

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from utils import default_error_handler

from logging import Logger
from os.path import join, sep
from sys import path as sys_path
from ui import UiConfig
from os import environ
from ui import UiConfig

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
    jwt = JWTManager(app)

    # Override default exceptions to fit standard format
    @app.errorhandler(NoAuthorizationError)
    def no_authorization_exception(e):
        return default_error_handler(403, "", "No authorization after token verification")

    @app.errorhandler(UserLookupError)
    def user_lookup_exception(e):
        return default_error_handler(403, "", "Impossible to verify user identity")

    @app.errorhandler(CSRFError)
    def csrf_exception(e):
        return default_error_handler(403, "", "Error with CSRF token")

    @app.errorhandler(FreshTokenRequired)
    def fresh_token_req_exception(e):
        return default_error_handler(403, "", "Token doesn't fit all conditions to get access")

    @app.errorhandler(InvalidHeaderError)
    def invaid_header_exception(e):
        return default_error_handler(403, "", "Invalid request format, impossible to check token")

    @app.errorhandler(InvalidQueryParamError)
    def invaid_query_param_exception(e):
        return default_error_handler(403, "", "Invalid request format, impossible to check token")

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
                LOGGER.info(f"Refresh JWT for user {get_jwt_identity()}")
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
            return make_response(redirect("/admin/login?error=True", 302))

        access_token = create_access_token(identity=username)
        resp = make_response(redirect("/admin/home", 302))
        set_access_cookies(resp, access_token)
        LOGGER.info(f"User {username} login")
        return resp

    # Remove cookies
    @app.route("/logout", methods=["POST"])
    def delete_jwt():
        resp = make_response(redirect("/admin/login", 302))
        try:
            identity = get_jwt_identity()
            unset_jwt_cookies(resp)
            LOGGER.info(f"User {identity} logout")
            return resp
        except:
            return resp
