# -*- coding: utf-8 -*-
from flask import request
from flask import make_response
from flask import redirect

from flask_jwt_extended.exceptions import NoAuthorizationError

from flask_jwt_extended import verify_jwt_in_request
from flask_jwt_extended import create_access_token
from flask_jwt_extended import set_access_cookies
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import get_jwt
from flask_jwt_extended import unset_jwt_cookies
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from utils import create_action_format, res_format, log_format
from hook import hooks

from exceptions.jwt import LoginFailedException
from exceptions.jwt import LogoutFailedException

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


# Register to main
def setup_jwt(app):
    # Setup the Flask-JWT-Extended extension
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]  # How JWT is handle
    app.config["JWT_COOKIE_SECURE"] = False  # ONLY HTTPS
    app.config["JWT_SECRET_KEY"] = "super-secret"  # Change for prod
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # Add CSRF TOKEN check
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
    JWTManager(app)

    @app.before_request
    def jwt_additionnal_checks():
        """Security middleware for login users."""
        # Case user is not logged in
        if verify_jwt_in_request(True) is None:
            return

        LOGGER.info(log_format("info", "", "", f"Find jwt"))

        # Case user is logged in, look for security check
        try:
            jwt = get_jwt()
            LOGGER.info(log_format("info", "", "", f"JWT is {jwt}"))

            if jwt["ip"] != request.remote_addr or jwt["user_agent"] != request.headers.get("User-Agent"):
                raise NoAuthorizationError("fail.")

        except:
            raise NoAuthorizationError("Some security check failed after checking JWT data.")

    @app.after_request
    @hooks(hooks=["BeforeRefreshToken", "AfterRefreshToken"])
    def refresh_expiring_jwts(response):
        # Add request that aren't concern by refresh (like get periodic logs)
        try:
            exp_timestamp = get_jwt()["exp"]
            now = datetime.now(timezone.utc)
            target_timestamp = datetime.timestamp(now + timedelta(minutes=5))
            if target_timestamp > exp_timestamp:
                # We will check for loggin user ip and user agent matching (on default middleware)
                security_data = {"ip": request.remote_addr, "user_agent": request.headers.get("User-Agent")}
                identity = get_jwt_identity()

                access_token = create_access_token(identity=identity, additional_claims=security_data)
                set_access_cookies(response, access_token)

                LOGGER.info(log_format("info", "", "", f"Refresh JWT for user {identity}"))
                create_action_format("success", "200", "Crendentials : refresh token", f"Refresh token for user {identity}.", ["ui", "credentials"])
            return response
        except (RuntimeError, KeyError):
            # Case where there is not a valid JWT. Just return the original response
            return response

    # Create a route to authenticate your users and return JWTs
    @app.route("/login", methods=["POST"])
    @hooks(hooks=["BeforeLogin", "AfterLogin"])
    def add_jwt():
        username = request.form.get("username", None)
        password = request.form.get("password", None)
        if username != UI_CONFIG.ADMIN_USERNAME or password != UI_CONFIG.ADMIN_PASSWORD:
            LOGGER.info(log_format("info", "", "", f"User try to log in but failed"))  # type: ignore
            create_action_format("error", "403", "Crendentials : UI failed login", f"User tried to login but failed", ["ui", "credentials"])  # type: ignore
            raise LoginFailedException

        # We will check for loggin user ip and user agent matching (on default middleware)
        security_data = {"ip": request.remote_addr, "user_agent": request.headers.get("User-Agent")}

        access_token = create_access_token(identity=username, additional_claims=security_data)
        resp = make_response(redirect("/admin/home", 302))
        set_access_cookies(resp, access_token)
        LOGGER.info(log_format("info", "", "", f"User {username} login"))
        create_action_format("success", "200", "Crendentials : UI login", f"{username} login to UI", ["ui", "credentials"])
        return resp

    # Remove cookies
    @app.route("/logout", methods=["POST"])
    @jwt_required()
    @hooks(hooks=["BeforeLogout", "AfterLogout"])
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
            raise LogoutFailedException("Try to logout user {identity} but failed.")
