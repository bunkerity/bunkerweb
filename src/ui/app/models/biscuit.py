from datetime import UTC, datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Optional
from os import getenv, sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from flask import Flask, current_app, render_template, request, session
from biscuit_auth import Biscuit, BiscuitBuilder, Check, Policy, PrivateKey, PublicKey, Authorizer, Fact, BiscuitValidationError, AuthorizationError
from flask_login import current_user
from flask import redirect, url_for

from app.routes.logout import logout_page

from common_utils import get_version  # type: ignore

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for biscuit module")

OPERATIONS = {
    "GET": "read",
    "POST": "write",
}


class BiscuitMiddleware:
    # Flask middleware for Biscuit token-based authorization.
    # Provides request interception and authorization validation using Biscuit tokens with role-based access control.

    # Initializes the Biscuit middleware.
    # Sets up Flask application instance registration and prepares for public key loading and authorization hooks.
    def __init__(self, app: Flask):
        """
        Initializes the Biscuit middleware.

        Args:
            app: Flask application instance.
        """
        if DEBUG_MODE:
            logger.debug("BiscuitMiddleware.__init__() called - initializing Biscuit authorization middleware")
        
        self.root_public_key = None
        app.biscuit_middleware = self  # Register middleware instance in the app

        if app is not None:
            self.init_app(app)
            if DEBUG_MODE:
                logger.debug("BiscuitMiddleware initialized and registered with Flask app")

    # Initialize Flask app configuration and load Biscuit public key for token validation.
    # Sets up before_request hook and validates public key file accessibility and format.
    def init_app(self, app):
        if DEBUG_MODE:
            logger.debug("init_app() called - loading Biscuit public key and setting up authorization hooks")
        
        root_public_key_path = app.config.get("BISCUIT_PUBLIC_KEY_PATH")
        if root_public_key_path:
            root_public_key_path = Path(root_public_key_path)
            
            if DEBUG_MODE:
                logger.debug(f"Loading Biscuit public key from: {root_public_key_path}")

            try:
                if root_public_key_path.exists():
                    self.root_public_key = PublicKey.from_hex(root_public_key_path.read_text().strip())
                    if DEBUG_MODE:
                        logger.debug("Successfully loaded Biscuit public key")
                else:
                    logger.error(f"Biscuit public key file not found: {root_public_key_path}")
                    raise ValueError(f"Public key file not found: {root_public_key_path}")
            except BaseException as e:
                logger.exception(f"Failed to load Biscuit public key from {root_public_key_path}")
                raise ValueError(f"Failed to load public key from {root_public_key_path}: {e}")
        else:
            logger.error("BISCUIT_PUBLIC_KEY_PATH not configured in Flask app config")
            raise ValueError("BISCUIT_PUBLIC_KEY_PATH must be set in the Flask app config")

        app.before_request(self._check_authorization)
        if DEBUG_MODE:
            logger.debug("Registered Biscuit authorization check as Flask before_request hook")

    # Flask's before_request hook to intercept requests and perform Biscuit authorization.
    # Enhanced to handle dynamic permissions per route with version checking and retry logic for Datalog limits.
    def _check_authorization(self) -> None:
        """
        Flask's `before_request` hook to intercept requests and perform Biscuit authorization.
        Enhanced to handle dynamic permissions per route.
        """
        if DEBUG_MODE:
            logger.debug(f"_check_authorization() called for {request.method} {request.path}")
        
        if (
            request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/", "/cache/"))
            or request.endpoint == "logout.logout_page"
        ):
            if DEBUG_MODE:
                logger.debug(f"Skipping authorization for static resource or logout: {request.path}")
            return

        token_str: Optional[str] = session.get("biscuit_token")  # Retrieve token from session

        if not token_str:
            if current_user.is_authenticated:
                if DEBUG_MODE:
                    logger.debug("No Biscuit token found for authenticated user, redirecting to logout")
                return logout_page(), 403
            if DEBUG_MODE:
                logger.debug("No Biscuit token found for unauthenticated user, allowing request")
            return

        if DEBUG_MODE:
            logger.debug("Found Biscuit token in session, validating...")

        try:
            token: Biscuit = Biscuit.from_base64(token_str, self.root_public_key)
            if DEBUG_MODE:
                logger.debug("Successfully parsed Biscuit token from base64")
        except BiscuitValidationError as e:
            logger.exception("Biscuit token validation failed")
            current_app.logger.warning(f"Biscuit validation error: {e}")
            return redirect(url_for("logout.logout_page"))

        current_app.logger.debug(str(token))

        # First we check if the biscuit is up to date
        max_retries = 3
        if DEBUG_MODE:
            logger.debug(f"Starting version check with max_retries: {max_retries}")
        
        for attempt in range(max_retries):
            try:
                authorizer = Authorizer()
                authorizer.add_token(token)

                version_check = f'check if version("{get_version()}")'
                authorizer.add_check(Check(version_check))
                
                if current_app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private:
                    ip_check = f'check if client_ip("{request.remote_addr}")'
                    authorizer.add_check(Check(ip_check))
                    if DEBUG_MODE:
                        logger.debug(f"Added IP check: {ip_check}")

                authorizer.add_policy(Policy("allow if true"))

                current_app.logger.debug(str(authorizer))
                authorizer.authorize()
                
                if DEBUG_MODE:
                    logger.debug(f"Version check passed on attempt {attempt + 1}")
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Datalog execution limits reached during version check, retrying... (attempt {attempt + 1}/{max_retries})")
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    continue

                logger.warning(f"Version check authorization failed: {e}")
                current_app.logger.warning(f"Version check error: {e}")
                return redirect(url_for("logout.logout_page"))
            except Exception as e:
                logger.exception("Unexpected error during Biscuit version check")
                current_app.logger.error(f"Unexpected error during version check: {e}")
                return redirect(url_for("logout.logout_page"))

        operation = OPERATIONS.get(request.method, "read")
        if DEBUG_MODE:
            logger.debug(f"Starting resource authorization check - operation: {operation}, path: {request.path}")

        for attempt in range(max_retries):
            try:
                authorizer = Authorizer()
                authorizer.add_token(token)

                resource_fact = f'resource("{request.path}")'
                operation_fact = f'operation("{operation}")'
                authorizer.add_fact(Fact(resource_fact))
                authorizer.add_fact(Fact(operation_fact))

                if DEBUG_MODE:
                    logger.debug(f"Added facts - resource: {resource_fact}, operation: {operation_fact}")

                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path.starts_with("/profile")'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_theme"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_language"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_columns_preferences"'))
                authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/clear_notifications"'))
                authorizer.add_policy(Policy("allow if role($role_name, $permissions), operation($operation_name), $permissions.contains($operation_name)"))

                current_app.logger.debug(str(authorizer))
                authorizer.authorize()
                
                if DEBUG_MODE:
                    logger.debug(f"Resource authorization passed on attempt {attempt + 1}")
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    logger.warning(f"Datalog execution limits reached during resource check, retrying... (attempt {attempt + 1}/{max_retries})")
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    continue

                logger.warning(f"Resource authorization failed for {operation} on {request.path}: {e}")
                current_app.logger.warning(f"Biscuit authorization error: {e}")
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
                logger.exception(f"Unexpected error during Biscuit resource authorization for {request.path}")
                current_app.logger.error(f"Unexpected error during Biscuit authorization: {e}")
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
    # Utility to create Biscuit tokens with predefined user roles and plugin extensibility.
    # Provides role-based token generation with core permissions and user identification for authorization systems.

    # Initializes the BiscuitTokenFactory.
    # Sets up private key for token signing and prepares role-based permission application.
    def __init__(self, root_private_key: PrivateKey):
        """
        Initializes the BiscuitTokenFactory.

        Args:
            root_private_key: Private key used to sign the Biscuit tokens.
        """
        if DEBUG_MODE:
            logger.debug("BiscuitTokenFactory.__init__() called - initializing token factory")
        
        self.root_private_key = root_private_key
        
        if DEBUG_MODE:
            logger.debug("BiscuitTokenFactory initialized with private key")

    # Applies core permissions based on the user role.
    # This function defines the base permissions for each predefined role with role-specific access control rules.
    def _apply_core_role_permissions(self, builder: BiscuitBuilder, role: str) -> None:
        """
        Applies core permissions based on the user role.
        This function defines the base permissions for each predefined role.

        Args:
            builder: The BiscuitBuilder instance to modify.
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
        """
        if DEBUG_MODE:
            logger.debug(f"_apply_core_role_permissions() called for role: {role}")
        
        if role == "super_admin":
            builder.add_code(
                """
                role("super_admin", ["read", "write"]);
                """
            )
            if DEBUG_MODE:
                logger.debug("Applied super_admin role permissions: read, write")

        elif role == "admin":
            # Admin role: read and write all resources
            builder.add_code(
                """
                role("admin", ["read", "write"]);
                """
            )
            if DEBUG_MODE:
                logger.debug("Applied admin role permissions: read, write")

        elif role == "writer":
            # Writer role: read and write all resources
            builder.add_code(
                """
                role("writer", ["read", "write"]);
                """
            )
            if DEBUG_MODE:
                logger.debug("Applied writer role permissions: read, write")

        elif role == "reader":
            # Reader role: read-only access to all resources
            builder.add_code(
                """
                role("reader", ["read"]);
                """
            )
            if DEBUG_MODE:
                logger.debug("Applied reader role permissions: read only")

        else:
            logger.error(f"Unknown role requested: {role}")
            raise ValueError(f"Unknown role: {role}")

    # Creates a Biscuit token for a given user role.
    # Generates signed token with user identification, timestamp, client info, and role-based permissions for authorization.
    def create_token_for_role(self, role: str, user_id: str) -> Biscuit:
        """
        Creates a Biscuit token for a given user role.

        Args:
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
            user_id: The user identifier to embed in the token.

        Returns:
            Biscuit: The generated Biscuit token.
        """
        if DEBUG_MODE:
            logger.debug(f"create_token_for_role() called - role: {role}, user_id: {user_id}")
        
        try:
            builder = BiscuitBuilder(
                f"""
                user("{user_id}");
                time({datetime.now(UTC).isoformat()});
                client_ip("{request.remote_addr}");
                domain("{request.host}");
                version("{get_version()}");
                """
            )  # Start with basic user fact

            if DEBUG_MODE:
                logger.debug(f"Created BiscuitBuilder with user facts for {user_id}")

            self._apply_core_role_permissions(builder, role)  # Apply core role permissions

            token: Biscuit = builder.build(self.root_private_key)  # Build and sign the token
            
            if DEBUG_MODE:
                logger.debug(f"Successfully created Biscuit token for user {user_id} with role {role}")
            
            return token
        except Exception as e:
            logger.exception(f"Failed to create Biscuit token for user {user_id} with role {role}")
            raise
