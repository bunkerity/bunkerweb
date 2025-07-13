from datetime import datetime, timezone
from ipaddress import ip_address
from os import sep
from os.path import join
from pathlib import Path
from sys import path as sys_path
from traceback import format_exc
from typing import Optional

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-biscuit",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-biscuit")

from flask import Flask, current_app, render_template, request, session
from biscuit_auth import Biscuit, BiscuitBuilder, Check, Policy, PrivateKey, PublicKey, Authorizer, Fact, BiscuitValidationError, AuthorizationError
from flask_login import current_user
from flask import redirect, url_for

from app.routes.logout import logout_page

from common_utils import get_version  # type: ignore

OPERATIONS = {
    "GET": "read",
    "POST": "write",
}


class BiscuitMiddleware:
    """
    Flask middleware for Biscuit token-based authorization.
    """

    # Initialize Biscuit middleware for Flask application.
    # Sets up token validation and authorization checking.
    def __init__(self, app: Flask):
        """
        Initializes the Biscuit middleware.

        Args:
            app: Flask application instance.
        """
        logger.debug("BiscuitMiddleware.__init__() called")
        self.root_public_key = None
        app.biscuit_middleware = self  # Register middleware instance in the app

        if app is not None:
            self.init_app(app)

    # Configure middleware with public key and request handlers.
    # Loads root public key and registers authorization checks.
    def init_app(self, app):
        logger.debug("BiscuitMiddleware.init_app() called")
        root_public_key_path = app.config.get("BISCUIT_PUBLIC_KEY_PATH")
        if root_public_key_path:
            root_public_key_path = Path(root_public_key_path)

            try:
                if root_public_key_path.exists():
                    self.root_public_key = PublicKey.from_hex(root_public_key_path.read_text().strip())
                    logger.debug(f"Loaded public key from {root_public_key_path}")
            except BaseException as e:
                logger.exception(f"Failed to load public key from {root_public_key_path}")
                raise ValueError(f"Failed to load public key from {root_public_key_path}: {e}")
        else:
            raise ValueError("BISCUIT_PUBLIC_KEY_PATH must be set in the Flask app config")

        app.before_request(self._check_authorization)

    # Check authorization for incoming requests using Biscuit tokens.
    # Validates tokens and enforces access control policies.
    def _check_authorization(self) -> None:
        """
        Flask's `before_request` hook to intercept requests and perform Biscuit authorization.
        Enhanced to handle dynamic permissions per route.
        """
        logger.debug(f"Authorization check for {request.method} {request.path}")
        
        if (
            request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/", "/cache/"))
            or request.endpoint == "logout.logout_page"
        ):
            logger.debug("Skipping authorization for static resource or logout")
            return

        token_str: Optional[str] = session.get("biscuit_token")  # Retrieve token from session

        if not token_str:
            logger.debug("No biscuit token found in session")
            if current_user.is_authenticated:
                return logout_page(), 403
            return

        try:
            token: Biscuit = Biscuit.from_base64(token_str, self.root_public_key)
        except BiscuitValidationError as e:
            current_app.logger.debug(format_exc())
            current_app.logger.warning(f"Biscuit validation error: {e}")
            logger.debug(f"Biscuit validation failed: {e}")
            return redirect(url_for("logout.logout_page"))

        current_app.logger.debug(str(token))

        # First we check if the biscuit is up to date
        max_retries = 3
        for attempt in range(max_retries):
            try:
                authorizer = Authorizer()
                authorizer.add_token(token)

                authorizer.add_check(Check(f'check if version("{get_version()}")'))
                if current_app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private:
                    authorizer.add_check(Check(f'check if client_ip("{request.remote_addr}")'))

                authorizer.add_policy(Policy("allow if true"))

                current_app.logger.debug(str(authorizer))
                authorizer.authorize()
                logger.debug("Version check passed")
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    logger.debug(f"Datalog limits reached, retry {attempt + 1}")
                    continue

                current_app.logger.warning(f"Version check error: {e}")
                logger.debug(f"Version check failed: {e}")
                return redirect(url_for("logout.logout_page"))
            except Exception as e:
                current_app.logger.debug(format_exc())
                current_app.logger.error(f"Unexpected error during version check: {e}")
                logger.exception("Unexpected error during version check")
                return redirect(url_for("logout.logout_page"))

        operation = OPERATIONS.get(request.method, "read")
        logger.debug(f"Operation determined: {operation}")

        for attempt in range(max_retries):
            try:
                authorizer = Authorizer()
                authorizer.add_token(token)

                authorizer.add_fact(Fact(f'resource("{request.path}")'))
                authorizer.add_fact(Fact(f'operation("{operation}")'))

                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path.starts_with("/profile")'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_theme"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_language"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_columns_preferences"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/clear_notifications"'))
                authorizer.add_policy(Policy("allow if role($role_name, $permissions), operation($operation_name), $permissions.contains($operation_name)"))

                current_app.logger.debug(str(authorizer))
                authorizer.authorize()
                logger.debug("Authorization successful")
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    logger.debug(f"Datalog limits reached, retry {attempt + 1}")
                    continue

                current_app.logger.warning(f"Biscuit authorization error: {e}")
                logger.debug(f"Authorization failed: {e}")
                return (
                    render_template(
                        "unauthorized.html",
                        message="You are not authorized to access this resource." if operation == "read" else "You are not authorized to perform this action.",
                        next=url_for("home.home_page"),
                        error_code=403,
                        auto_redirect=False,
                    ),
                    403,
                )
            except Exception as e:
                current_app.logger.error(f"Unexpected error during Biscuit authorization: {e}")
                logger.exception("Unexpected error during authorization")
                return (
                    render_template(
                        "unauthorized.html",
                        message="An unexpected error occurred during authorization.",
                        next=url_for("home.home_page"),
                        error_code=500,
                        auto_redirect=False,
                    ),
                    500,
                )


class BiscuitTokenFactory:
    """
    Utility to create Biscuit tokens with predefined user roles and plugin extensibility.
    """

    # Initialize token factory with root private key for signing.
    # Sets up the foundation for creating role-based Biscuit tokens.
    def __init__(self, root_private_key: PrivateKey):
        """
        Initializes the BiscuitTokenFactory.

        Args:
            root_private_key: Private key used to sign the Biscuit tokens.
        """
        logger.debug("BiscuitTokenFactory.__init__() called")
        self.root_private_key = root_private_key

    # Apply role-specific permissions to token builder.
    # Defines access levels for different user roles.
    def _apply_core_role_permissions(self, builder: BiscuitBuilder, role: str) -> None:
        """
        Applies core permissions based on the user role.
        This function defines the base permissions for each predefined role.

        Args:
            builder: The BiscuitBuilder instance to modify.
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
        """
        logger.debug(f"Applying permissions for role: {role}")
        
        if role == "super_admin":
            builder.add_code(
                """
                role("super_admin", ["read", "write"]);
                """
            )

        elif role == "admin":
            # Admin role: read and write all resources
            builder.add_code(
                """
                role("admin", ["read", "write"]);
                """
            )

        elif role == "writer":
            # Writer role: read and write all resources
            builder.add_code(
                """
                role("writer", ["read", "write"]);
                """
            )

        elif role == "reader":
            # Reader role: read-only access to all resources
            builder.add_code(
                """
                role("reader", ["read"]);
                """
            )

        else:
            logger.debug(f"Unknown role: {role}")
            raise ValueError(f"Unknown role: {role}")

    # Create signed Biscuit token for specific user role.
    # Generates token with user info, permissions, and environmental context.
    def create_token_for_role(self, role: str, user_id: str) -> Biscuit:
        """
        Creates a Biscuit token for a given user role.

        Args:
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
            user_id: The user identifier to embed in the token.

        Returns:
            Biscuit: The generated Biscuit token.
        """
        logger.debug(f"Creating token for role={role}, user_id={user_id}")
        builder = BiscuitBuilder(
            f"""
            user("{user_id}");
            time({datetime.now(timezone.utc).isoformat()});
            client_ip("{request.remote_addr}");
            domain("{request.host}");
            version("{get_version()}");
            """
        )  # Start with basic user fact

        self._apply_core_role_permissions(builder, role)  # Apply core role permissions

        token: Biscuit = builder.build(self.root_private_key)  # Build and sign the token
        logger.debug(f"Token created successfully for user {user_id}")
        return token
