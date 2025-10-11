from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path
from traceback import format_exc
from typing import Optional

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

    def __init__(self, app: Flask):
        """
        Initializes the Biscuit middleware.

        Args:
            app: Flask application instance.
        """
        self.root_public_key = None
        app.biscuit_middleware = self  # Register middleware instance in the app

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        root_public_key_path = app.config.get("BISCUIT_PUBLIC_KEY_PATH")
        if root_public_key_path:
            root_public_key_path = Path(root_public_key_path)

            try:
                if root_public_key_path.exists():
                    self.root_public_key = PublicKey.from_hex(root_public_key_path.read_text().strip())
            except BaseException as e:
                raise ValueError(f"Failed to load public key from {root_public_key_path}: {e}")
        else:
            raise ValueError("BISCUIT_PUBLIC_KEY_PATH must be set in the Flask app config")

        app.before_request(self._check_authorization)

    def _check_authorization(self) -> None:
        """
        Flask's `before_request` hook to intercept requests and perform Biscuit authorization.
        Enhanced to handle dynamic permissions per route.
        """
        if request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/", "/cache/", "/logout")):
            return

        token_str: Optional[str] = session.get("biscuit_token")  # Retrieve token from session

        if not token_str:
            if current_user.is_authenticated:
                return logout_page(), 403
            return

        try:
            token: Biscuit = Biscuit.from_base64(token_str, self.root_public_key)
        except BiscuitValidationError as e:
            current_app.logger.debug(format_exc())
            current_app.logger.warning(f"Biscuit validation error: {e}")
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
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    continue

                current_app.logger.warning(f"Version check error: {e}")
                return redirect(url_for("logout.logout_page"))
            except Exception as e:
                current_app.logger.debug(format_exc())
                current_app.logger.error(f"Unexpected error during version check: {e}")
                return redirect(url_for("logout.logout_page"))

        operation = OPERATIONS.get(request.method, "read")

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
                break  # Success, exit retry loop
            except AuthorizationError as e:
                if "Reached Datalog execution limits" in str(e) and attempt < max_retries - 1:
                    current_app.logger.warning(f"Datalog execution limits reached, retrying... (attempt {attempt + 1}/{max_retries})")
                    continue

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
    """
    Utility to create Biscuit tokens with predefined user roles and plugin extensibility.
    """

    def __init__(self, root_private_key: PrivateKey):
        """
        Initializes the BiscuitTokenFactory.

        Args:
            root_private_key: Private key used to sign the Biscuit tokens.
        """
        self.root_private_key = root_private_key

    def _apply_core_role_permissions(self, builder: BiscuitBuilder, role: str) -> None:
        """
        Applies core permissions based on the user role.
        This function defines the base permissions for each predefined role.

        Args:
            builder: The BiscuitBuilder instance to modify.
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
        """
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
            raise ValueError(f"Unknown role: {role}")

    def create_token_for_role(self, role: str, user_id: str) -> Biscuit:
        """
        Creates a Biscuit token for a given user role.

        Args:
            role: The user role string (e.g., "super_admin", "admin", "writer", "reader").
            user_id: The user identifier to embed in the token.

        Returns:
            Biscuit: The generated Biscuit token.
        """
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
        return token
