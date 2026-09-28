from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path
from traceback import format_exc
from typing import Optional

from flask import Flask, current_app, render_template, request, session
from biscuit_auth import (
    Biscuit,
    BiscuitBuilder,
    Check,
    Policy,
    PrivateKey,
    PublicKey,
    AuthorizerBuilder,
    Fact,
    BiscuitValidationError,
    AuthorizationError,
)
from flask_login import current_user
from flask import redirect, url_for

from app.routes.logout import logout_page
from app.utils import BISCUIT_PRIVATE_KEY_FILE, is_static_path

from common_utils import get_version  # type: ignore

OPERATIONS = {
    "GET": "read",
    "POST": "write",
}

# Some UI endpoints use POST for datatable/query payloads but are read-only operations.
READ_ONLY_POST_ENDPOINTS = frozenset(
    {
        "bans.bans_fetch",
        "reports.reports_fetch",
        "reports.reports_filters",
        "reports.report_data_fetch",
    }
)
READ_ONLY_POST_RULES = frozenset(
    {
        "/bans/fetch",
        "/reports/fetch",
        "/reports/filters",
        "/reports/data",
    }
)
READ_ONLY_POST_PATH_SUFFIXES = (
    "/bans/fetch",
    "/reports/fetch",
    "/reports/filters",
    "/reports/data",
)

# biscuit-rust authorizes under a wall-clock budget defaulting to 1 ms, and reports blowing it as
# the same AuthorizationError a policy denial raises. An honest token authorizes in ~0.01 ms, but a
# CPU-starved host still overran 1 ms often enough to log valid sessions out. Raise the clock only:
# max_facts and max_iterations bound the work a token's own Datalog can demand, so they keep their
# defaults. Duplicated from the API guard rather than shared: src/ui and src/api ship as separate
# images with no common package.
AUTHORIZE_MAX_TIME = timedelta(milliseconds=100)

# Whole-message marker for a run-limit abort. Unlike the API, this token is never attacker-supplied
# (it is minted server-side and kept in the signed session), so a residual abort here means the host
# is still starved, not that the token is hostile. Match the whole message: a denial quotes back
# check text that token content can influence, so a substring test would misclassify a real denial.
RUN_LIMIT_ERROR = "Reached Datalog execution limits"


def _raise_time_budget(authorizer: AuthorizerBuilder) -> None:
    # limits() hands back a copy, so set_limits() is what actually applies the change.
    limits = authorizer.limits()
    limits.max_time = AUTHORIZE_MAX_TIME
    authorizer.set_limits(limits)


def _internal_error_response():
    # A failure to reach a verdict is not a verdict. Returning the logout redirect (or a 403) would
    # destroy or disown a session that is still perfectly valid, so surface it as the server-side
    # error it is and leave the session intact for the retry.
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


def _normalize_path(path: str) -> str:
    # Normalize path to tolerate duplicate/trailing slashes (e.g. /reports//fetch/).
    return "/" + "/".join(segment for segment in path.split("/") if segment)


def resolve_operation(method: str, path: str, endpoint: Optional[str] = None, rule: Optional[str] = None) -> str:
    normalized_path = _normalize_path(path).rstrip("/")
    normalized_rule = _normalize_path(rule or "").rstrip("/") if rule else ""

    if method == "POST" and endpoint in READ_ONLY_POST_ENDPOINTS:
        return "read"
    if method == "POST" and normalized_rule in READ_ONLY_POST_RULES:
        return "read"
    if method == "POST" and any(normalized_path.rstrip("/").endswith(suffix) for suffix in READ_ONLY_POST_PATH_SUFFIXES):
        return "read"
    return OPERATIONS.get(method, "read")


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
                    self.root_public_key = PublicKey(root_public_key_path.read_text().strip())
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
        # Only truly static assets and logout bypass authorization. NOTE: "/cache/" is
        # deliberately NOT excluded -- its routes carry real privilege (GET serves job
        # cache file contents = read; POST /cache/delete purges cache = write). Excluding
        # it would let any authenticated non-admin (e.g. a PRO "reader") delete cache,
        # because these routes have no role check of their own. Let them flow through the
        # operation policy below (GET->read, POST->write) like every other route.
        if is_static_path(request.path, "/logout"):
            return

        token_str: Optional[str] = session.get("biscuit_token")  # Retrieve token from session

        if not token_str:
            if current_user.is_authenticated:
                # Token may have been lost due to a session race condition
                # (concurrent requests on different workers). Try to regenerate it.
                try:
                    if BISCUIT_PRIVATE_KEY_FILE.exists():
                        current_app.logger.warning(f"Biscuit token missing from session for authenticated user {current_user.get_id()}, regenerating")
                        private_key = PrivateKey(BISCUIT_PRIVATE_KEY_FILE.read_text().strip())
                        token_factory = BiscuitTokenFactory(private_key)
                        role = "super_admin" if current_user.admin else current_user.list_roles[0]
                        token_str = token_factory.create_token_for_role(role, current_user.get_id()).to_base64()
                        session["biscuit_token"] = token_str
                    else:
                        return logout_page(), 403
                except Exception as e:
                    current_app.logger.error(f"Failed to regenerate Biscuit token: {e}")
                    return logout_page(), 403
            else:
                return

        try:
            token: Biscuit = Biscuit.from_base64(token_str, self.root_public_key)
        except BiscuitValidationError as e:
            current_app.logger.debug(format_exc())
            current_app.logger.warning(f"Biscuit validation error: {e}")
            return redirect(url_for("logout.logout_page"))

        current_app.logger.debug(str(token))

        # First we check if the biscuit is up to date
        try:
            authorizer = AuthorizerBuilder()

            authorizer.add_check(Check(f'check if version("{get_version()}")'))
            if current_app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private:
                authorizer.add_check(Check("check if client_ip({client_ip})", {"client_ip": request.remote_addr or "0.0.0.0"}))

            authorizer.add_policy(Policy("allow if true"))
            _raise_time_budget(authorizer)

            current_app.logger.debug(str(authorizer))
            authorizer.build(token).authorize()
        except AuthorizationError as e:
            if str(e) == RUN_LIMIT_ERROR:
                current_app.logger.error(f"Datalog run limits hit during version check on {request.method} {request.path}; session kept")
                return _internal_error_response()

            current_app.logger.warning(f"Version check error: {e}")
            return redirect(url_for("logout.logout_page"))
        except Exception as e:
            current_app.logger.debug(format_exc())
            current_app.logger.error(f"Unexpected error during version check: {e}")
            return redirect(url_for("logout.logout_page"))

        route_rule = request.url_rule.rule if request.url_rule else None
        resource_path = route_rule or request.path
        operation = resolve_operation(request.method, request.path, request.endpoint, route_rule)

        try:
            authorizer = AuthorizerBuilder()

            # resource_path can fall back to the attacker-controlled request path, so
            # bind it (and the operation) as parameters to prevent Datalog injection.
            authorizer.add_fact(Fact("resource({resource_path})", {"resource_path": resource_path}))
            authorizer.add_fact(Fact("operation({operation})", {"operation": operation}))

            authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path.starts_with("/profile")'))
            authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_theme"'))
            authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_language"'))
            authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/set_columns_preferences"'))
            authorizer.add_policy(Policy('allow if resource($resource_path), $resource_path == "/clear_notifications"'))
            authorizer.add_policy(Policy("allow if role($role_name, $permissions), operation($operation_name), $permissions.contains($operation_name)"))
            _raise_time_budget(authorizer)

            current_app.logger.debug(str(authorizer))
            authorizer.build(token).authorize()
        except AuthorizationError as e:
            if str(e) == RUN_LIMIT_ERROR:
                current_app.logger.error(f"Datalog run limits hit authorizing {request.method} {request.path}; not a permission denial")
                return _internal_error_response()

            current_app.logger.warning(
                f"Biscuit authorization error on {request.method} {request.path} endpoint={request.endpoint} rule={route_rule} (operation={operation}): {e}"
            )
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
            return _internal_error_response()


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
            builder.add_code("""
                role("super_admin", ["read", "write"]);
                """)

        elif role == "admin":
            # Admin role: read and write all resources
            builder.add_code("""
                role("admin", ["read", "write"]);
                """)

        elif role == "writer":
            # Writer role: read and write all resources
            builder.add_code("""
                role("writer", ["read", "write"]);
                """)

        elif role == "reader":
            # Reader role: read-only access to all resources
            builder.add_code("""
                role("reader", ["read"]);
                """)

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
        # Bind untrusted values (Host header, client IP, user id) through the biscuit
        # parameter API so they cannot inject additional signed Datalog facts.
        builder = BiscuitBuilder(
            """
            user({user});
            time({time});
            client_ip({client_ip});
            domain({domain});
            version({version});
            """,
            {
                "user": user_id,
                "time": datetime.now(timezone.utc),
                "client_ip": request.remote_addr or "0.0.0.0",
                # Clamp the attacker-controlled Host to a sane length so it cannot bloat the signed token.
                "domain": (request.host or "")[:255],
                "version": get_version(),
            },
        )  # Start with basic user facts

        self._apply_core_role_permissions(builder, role)  # Apply core role permissions

        token: Biscuit = builder.build(self.root_private_key)  # Build and sign the token
        return token
