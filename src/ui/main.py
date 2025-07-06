#!/usr/bin/env python3
from contextlib import suppress
from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from ipaddress import ip_address
from itertools import chain
from json import dumps, loads
from operator import itemgetter
from os import getenv, getpid, sep
from os.path import abspath, join
from secrets import token_urlsafe
from signal import SIGINT, signal, SIGTERM
from sys import path as sys_path
from threading import Thread
from time import time
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from your module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="SCHEDULER: ",
    log_file_path="/var/log/bunkerweb/scheduler.log"
)

from cachelib import FileSystemCache
from flask import Blueprint, Flask, Response, flash as flask_flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, LoginManager, login_required
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.routing.exceptions import BuildError

from app.models.biscuit import BiscuitMiddleware
from app.models.reverse_proxied import ReverseProxied

from app.dependencies import BW_CONFIG, DATA, DB, CORE_PLUGINS_PATH, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH, safe_reload_plugins
from app.models.models import AnonymousUser
from app.utils import (
    BISCUIT_PUBLIC_KEY_FILE,
    COLUMNS_PREFERENCES_DEFAULTS,
    LIB_DIR,
    flash,
    get_blacklisted_settings,
    get_filtered_settings,
    get_latest_stable_release,
    get_multiples,
    handle_stop,
    human_readable_number,
    is_plugin_active,
    stop,
)
from app.lang_config import SUPPORTED_LANGUAGES


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

logger.debug("Signal handlers registered for SIGINT and SIGTERM")
if getenv("LOG_LEVEL") == "debug":
    logger.debug("[DEBUG] Signal handlers initialized for graceful shutdown")

HOOKS = {
    "before_request": {
        "key": "BEFORE_REQUEST_HOOKS",
        "log_prefix": "Before-request",
    },
    "after_request": {
        "key": "AFTER_REQUEST_HOOKS",
        "log_prefix": "After-request",
    },
    "teardown_request": {
        "key": "TEARDOWN_REQUEST_HOOKS",
        "log_prefix": "Teardown-request",
    },
    "context_processor": {
        "key": "CONTEXT_PROCESSOR_HOOKS",
        "log_prefix": "Context-processor",
    },
}


class DynamicFlask(Flask):
    # Custom Flask class that handles blueprint priority and template loading
    # Override Flask's default template loader to prioritize blueprint
    # templates over global templates
    def create_global_jinja_loader(self):
        # Override Flask's default template loader creation so that
        # blueprint template folders (especially plugins) take precedence
        # over the application's global template folder.
        logger.debug("Creating global jinja loader with custom blueprint priority handling")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Initializing custom jinja loader with blueprint prioritization")
        
        # Collect loaders from each blueprint in descending order of 'plugin_priority'
        # (or zero if not set).
        blueprint_loaders = []
        for name, bp in self.blueprints.items():
            if bp.template_folder is not None:
                # If the blueprint doesn't provide a custom loader,
                # create a FileSystemLoader pointed at its template folder.
                loader = bp.jinja_loader
                if loader is None:
                    template_path = abspath(bp.template_folder)
                    loader = FileSystemLoader(template_path)
                    logger.debug(f"Created FileSystemLoader for blueprint '{name}' with path: {template_path}")
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] FileSystemLoader created for blueprint '{name}': {template_path}")
                else:
                    logger.debug(f"Using existing jinja_loader for blueprint '{name}'")
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] Using existing jinja_loader for blueprint '{name}'")
                
                # Priority: higher means we want it searched first.
                priority = getattr(bp, "plugin_priority", 0)
                logger.debug(f"Blueprint '{name}' has plugin_priority: {priority}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Blueprint '{name}' priority set to: {priority}")
                blueprint_loaders.append((priority, loader))

        # Sort blueprint loaders descending by priority
        blueprint_loaders.sort(key=itemgetter(0), reverse=True)
        loaders_in_order = [ldr for (_prio, ldr) in blueprint_loaders]
        logger.debug(f"Blueprint loaders sorted by priority: {[p for p, _ in blueprint_loaders]}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Sorted blueprint loaders by priority: {[p for p, _ in blueprint_loaders]}")

        # Finally, add the app's own jinja_loader (which handles the global templates folder)
        # at the end. This ensures plugin templates overshadow global templates if names clash.
        if self.jinja_loader is not None:
            loaders_in_order.append(self.jinja_loader)
            logger.debug("App's jinja_loader appended to the end of loaders list")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] App's jinja_loader appended to loaders list")

        final_loader = ChoiceLoader(loaders_in_order)
        logger.debug("Global jinja loader created successfully")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Global jinja loader creation completed successfully")
        return final_loader

    # Register blueprint with priority support, allowing higher priority
    # blueprints to override lower priority ones
    def register_blueprint(self, blueprint, **options):
        # Register a blueprint with priority support, allowing higher priority
        # blueprints to replace lower priority ones with the same name
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Attempting to register blueprint '{blueprint.name}' with options: {options}")
        
        # Check if a blueprint with this name is already registered.
        if blueprint.name in self.blueprints:
            existing_bp = self.blueprints[blueprint.name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(blueprint, "plugin_priority", 0)
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Blueprint '{blueprint.name}' exists - existing priority: {existing_priority}, new priority: {new_priority}")
            
            if new_priority > existing_priority:
                logger.info(f"Overriding blueprint '{blueprint.name}': new priority {new_priority} over {existing_priority}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Overriding blueprint '{blueprint.name}' due to higher priority")
                logger.debug(f"Removing existing blueprint '{blueprint.name}' and its URL rules")
                # Remove the existing blueprint.
                del self.blueprints[blueprint.name]
                # Also remove all URL rules associated with the existing blueprint.
                rules_to_remove = [rule for rule in list(self.url_map.iter_rules()) if rule.endpoint.startswith(blueprint.name + ".")]
                logger.debug(f"Found {len(rules_to_remove)} URL rules to remove for blueprint '{blueprint.name}'")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Removing {len(rules_to_remove)} URL rules for blueprint '{blueprint.name}'")
                for rule in rules_to_remove:
                    self.url_map._rules.remove(rule)
                    self.url_map._rules_by_endpoint.pop(rule.endpoint, None)
            else:
                logger.info(f"Skipping blueprint '{blueprint.name}' with priority {new_priority} " f"(existing priority {existing_priority})")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Skipping blueprint '{blueprint.name}' registration due to lower/equal priority")
                return  # Do not register a lower- or equal-priority blueprint.

        # Allow registration even after first request by temporarily resetting the flag.
        original_got_first = self._got_first_request
        self._got_first_request = False
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Temporarily setting _got_first_request to False for blueprint registration")
        try:
            result = super().register_blueprint(blueprint, **options)
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Successfully registered blueprint '{blueprint.name}'")
        finally:
            self._got_first_request = original_got_first
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Restored _got_first_request to {original_got_first}")
        return result


# Create Flask app instance with custom static and template folders
app = DynamicFlask(__name__, static_url_path="/", static_folder="app/static", template_folder="app/templates")
app.logger = logger

with app.app_context():
    logger.debug("Initializing Flask app context")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Starting Flask app context initialization")
    
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    logger.debug(f"PROXY_NUMBERS set to {PROXY_NUMBERS}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Proxy numbers configuration: {PROXY_NUMBERS}")
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    if not LIB_DIR.joinpath(".flask_secret").is_file():
        logger.error("The .flask_secret file is missing, exiting ...")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Flask secret file not found, application will exit")
        stop(1)
    FLASK_SECRET = LIB_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()
    logger.debug(f"Flask secret loaded from {LIB_DIR.joinpath('.flask_secret')}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Flask secret successfully loaded from file")

    app.config["BISCUIT_PUBLIC_KEY_PATH"] = BISCUIT_PUBLIC_KEY_FILE.as_posix()
    logger.debug(f"Biscuit public key path set to {app.config['BISCUIT_PUBLIC_KEY_PATH']}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Biscuit public key path configured: {app.config['BISCUIT_PUBLIC_KEY_PATH']}")

    app.config["ENV"] = {}

    app.config["CHECK_PRIVATE_IP"] = getenv("CHECK_PRIVATE_IP", "yes").lower() == "yes"
    app.config["SECRET_KEY"] = FLASK_SECRET

    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["REMEMBER_COOKIE_PATH"] = "/"
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB
    app.config["SCRIPT_NONCE"] = ""

    # Session management configuration using file-based cache
    app.config["SESSION_TYPE"] = "cachelib"
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_ID_LENGTH"] = 64
    app.config["SESSION_CACHELIB"] = FileSystemCache(threshold=500, cache_dir=LIB_DIR.joinpath("ui_sessions_cache"))
    logger.debug(f"Session cache directory: {LIB_DIR.joinpath('ui_sessions_cache')}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Session cache directory configured: {LIB_DIR.joinpath('ui_sessions_cache')}")
    sess = Session()
    sess.init_app(app)
    logger.debug("Session management initialized")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Session management system initialized")

    biscuit = BiscuitMiddleware(app)
    logger.debug("Biscuit middleware initialized")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Biscuit middleware setup completed")

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    login_manager.login_view = "login.login_page"
    login_manager.anonymous_user = AnonymousUser
    logger.debug("Login manager initialized with strong session protection")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Login manager configured with strong session protection")

    # CSRF protection configuration
    app.config["WTF_CSRF_METHODS"] = ("POST",)
    app.config["WTF_CSRF_SSL_STRICT"] = False
    csrf = CSRFProtect()
    csrf.init_app(app)
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] CSRF protection enabled for POST requests")

    app.config["EXTRA_PAGES"] = []

    # Custom URL building function that appends _page suffix for
    # non-special endpoints to maintain consistent routing patterns
    def custom_url_for(endpoint, **values):
        # Custom URL builder that automatically appends '_page' suffix
        # for non-special endpoints to maintain routing consistency
        # Handles BuildError exceptions gracefully by returning '#' as fallback
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Building URL for endpoint: {endpoint}")
        if endpoint:
            try:
                if endpoint not in ("static", "index", "loading", "check", "check_reloading") and "_page" not in endpoint:
                    result = url_for(f"{endpoint}.{endpoint}_page", **values)
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] Built URL with _page suffix: {result}")
                    return result
                result = url_for(endpoint, **values)
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Built standard URL: {result}")
                return result
            except BuildError as e:
                logger.debug(f"Couldn't build the URL for {endpoint}: {e}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] URL build failed for {endpoint}: {e}")
        return "#"

    # Register global template functions for jinja2 rendering
    app.jinja_env.globals.update(
        get_multiples=get_multiples,
        get_filtered_settings=get_filtered_settings,
        get_blacklisted_settings=get_blacklisted_settings,
        get_plugins_settings=BW_CONFIG.get_plugins_settings,
        human_readable_number=human_readable_number,
        url_for=custom_url_for,
        is_plugin_active=is_plugin_active,
    )
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Jinja2 global functions registered")

    # Initialize hook configuration for all supported hook types
    app.config.update({hook_info["key"]: [] for hook_info in HOOKS.values()})
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Initialized hook configurations: {list(HOOKS.keys())}")

    DATA.load_from_file()
    if "WORKERS" not in DATA:
        DATA["WORKERS"] = {}
        logger.debug("Initialized WORKERS in DATA")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] WORKERS data structure initialized")
    DATA["FORCE_RELOAD_PLUGIN"] = True
    DB.checked_changes(["ui_plugins"], value=True)
    logger.debug("Initial data and database setup complete")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Initial data and database setup completed successfully")


# Context processor to inject common variables into all templates
@app.context_processor
def inject_variables():
    # Inject common template variables and execute context processor hooks
    # This function runs before every template render to provide shared data
    # Merges environment variables from hooks with base application config
    app_env = app.config["ENV"].copy()
    logger.debug(f"Processing {len(app.config['CONTEXT_PROCESSOR_HOOKS'])} context processor hooks")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Processing {len(app.config['CONTEXT_PROCESSOR_HOOKS'])} context processor hooks")
    
    for hook in app.config["CONTEXT_PROCESSOR_HOOKS"]:
        try:
            logger.debug(f"Executing context_processor hook: {hook.__name__}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Executing context_processor hook: {hook.__name__}")
            resp = hook()
            if resp:
                logger.debug(f"Context_processor hook {hook.__name__} returned {len(resp)} variables")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Hook {hook.__name__} returned {len(resp)} variables")
                app_env = {**app_env, **resp}
        except Exception:
            logger.exception("Error in context_processor hook")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Error occurred in context_processor hook: {hook.__name__}")

    app.config["ENV"] = app_env

    logger.debug(f"Injected {len(app_env)} variables into template context")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Injected {len(app_env)} variables into template context")

    return app_env


# Load user from database by username for Flask-Login authentication
@login_manager.user_loader
def load_user(username):
    # Load user from database and populate roles and permissions
    # This function is called by Flask-Login to load user sessions
    # Also handles TOTP recovery codes and permission aggregation
    logger.debug(f"Loading user: {username}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Loading user from database: {username}")
    
    ui_user = DB.get_ui_user(username=username)
    if not ui_user:
        logger.warning(f"Couldn't get the user {username} from the database.")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] User {username} not found in database")
        return None

    ui_user.list_roles = [role.role_name for role in ui_user.roles]
    logger.debug(f"User {username} has roles: {ui_user.list_roles}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] User {username} roles loaded: {ui_user.list_roles}")
    
    ui_user.list_permissions = []
    for role in ui_user.list_roles:
        role_permissions = DB.get_ui_role_permissions(role)
        ui_user.list_permissions.extend(role_permissions)
        logger.debug(f"Role '{role}' has permissions: {role_permissions}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Role '{role}' permissions: {role_permissions}")
    ui_user.list_permissions = set(ui_user.list_permissions)

    if ui_user.totp_secret:
        ui_user.list_recovery_codes = [recovery_code.code for recovery_code in ui_user.recovery_codes]
        logger.debug(f"User {username} has TOTP enabled with {len(ui_user.list_recovery_codes)} recovery codes")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] User {username} TOTP enabled with {len(ui_user.list_recovery_codes)} recovery codes")

        if (
            "totp-disable" not in request.path
            and "totp-refresh" not in request.path
            and session.get("totp_validated", False)
            and not ui_user.list_recovery_codes
        ):
            logger.debug(f"User {username} has TOTP enabled but no recovery codes available")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] User {username} missing recovery codes, showing warning")
            flask_flash(
                f"""The two-factor authentication is enabled but no recovery codes are available, please refresh them:
<div class="mt-2 pt-2 border-top border-white">
    <a role='button' class='btn btn-sm btn-dark d-flex align-items-center' aria-pressed='true' href='{url_for('profile.profile_page')}'>here</a>
</div>""",
                "error",
            )

    logger.debug(f"Loaded user {username} with {len(ui_user.list_permissions)} permissions")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] User {username} loaded with {len(ui_user.list_permissions)} permissions")

    return ui_user


# Handle CSRF errors by logging and redirecting to appropriate page
@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    # Handle CSRF token validation errors by logging the incident
    # and redirecting user to appropriate authentication page
    # Distinguishes between authenticated and unauthenticated users
    logger.exception(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] CSRF error for path {request.path} by user {current_user.get_id()}")
    if not current_user:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] CSRF error with unauthenticated user, redirecting to setup")
        return redirect(url_for("setup.setup_page")), 403
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] CSRF error with authenticated user, logging out")
    return logout_page(), 403


# Update the cached latest stable release version from GitHub
def update_latest_stable_release():
    # Fetch and cache the latest stable release version from GitHub API
    # This runs asynchronously to avoid blocking the main request thread
    logger.debug("Checking for latest stable release from GitHub")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Starting GitHub API call for latest release version")
    latest_release = get_latest_stable_release()
    if latest_release:
        DATA["LATEST_VERSION"] = latest_release
        logger.debug(f"Latest stable release is {latest_release}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Updated latest version cache to: {latest_release}")
    else:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Failed to retrieve latest release version from GitHub")


# Check database connection state and switch to readonly mode if needed
def check_database_state(request_method: str, request_path: str):
    # Monitor database connectivity and switch between read-write and read-only modes
    # Attempts to restore write access periodically and handles fallback connections
    DATA.load_from_file()
    logger.debug(f"Checking database state for {request_method} {request_path}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Database state check for {request_method} {request_path}")
    logger.debug(f"Current DB readonly state: {DB.readonly}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Current database readonly status: {DB.readonly}")
    
    if (
        DB.database_uri
        and DB.readonly
        and (datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LAST_DATABASE_RETRY", "1970-01-01T00:00:00")).astimezone() > timedelta(minutes=1))
    ):
        logger.debug("Database is readonly, attempting to retry connection")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Attempting database connection retry from readonly mode")
        failed = False
        try:
            DB.retry_connection(pool_timeout=1)
            DB.retry_connection(log=False)
            logger.info("The database is no longer read-only, defaulting to read-write mode")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database connection restored to read-write mode")
        except BaseException:
            failed = True
            logger.exception("Primary database connection failed")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Primary database connection failed, trying readonly")
            try:
                DB.retry_connection(readonly=True, pool_timeout=1)
                DB.retry_connection(readonly=True, log=False)
                logger.debug("Successfully connected to readonly database")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug("[DEBUG] Connected to readonly database successfully")
            except BaseException:
                logger.exception("Readonly database connection failed")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug("[DEBUG] Readonly database connection also failed, trying fallback")
                if DB.database_uri_readonly:
                    with suppress(BaseException):
                        DB.retry_connection(fallback=True, pool_timeout=1)
                        DB.retry_connection(fallback=True, log=False)
                        logger.debug("Connected to fallback database")
                        if getenv("LOG_LEVEL") == "debug":
                            logger.debug("[DEBUG] Connected to fallback database")
        DATA.update(
            {
                "READONLY_MODE": failed,
                "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
            }
        )
        logger.debug(f"Database readonly mode set to: {failed}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Database readonly mode updated to: {failed}")
    elif (
        DB.database_uri
        and not DATA.get("READONLY_MODE", False)
        and request_method == "POST"
        and not ("/totp" in request_path or "/login" in request_path or request_path.startswith("/plugins/upload"))
    ):
        logger.debug("Testing database write capability for POST request")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Testing database write capability for POST {request_path}")
        try:
            DB.test_write()
            DATA["READONLY_MODE"] = False
            logger.debug("Database write test successful")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database write test passed")
        except BaseException:
            logger.exception("Database write test failed")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database write test failed, switching to readonly mode")
            DATA.update(
                {
                    "READONLY_MODE": True,
                    "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
                }
            )
    else:
        try:
            DB.test_read()
            logger.debug("Database read test successful")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database read test successful")
        except BaseException:
            logger.exception("Database read test failed")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database read test failed")
            DATA["LAST_DATABASE_RETRY"] = DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat()


# Refresh Flask app context by reloading hooks and blueprints from plugins
def refresh_app_context():
    # Refresh Flask app context by loading hooks and blueprints from plugins.
    # This handles dynamic plugin loading and unloading without requiring app restart
    # Uses generation-based tracking to ensure workers stay synchronized
    worker_pid = str(getpid())
    current_generation = DATA.get("REFRESH_GENERATION", 0)
    worker_generation = DATA.get("WORKERS", {}).get(worker_pid, {}).get("refresh_generation", 0)

    logger.debug(f"Worker {worker_pid} refreshing context (generation {worker_generation} → {current_generation})")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Worker {worker_pid} starting context refresh from generation {worker_generation} to {current_generation}")
    DATA.load_from_file()

    # Initialize tracking structures if they don't exist
    if not hasattr(app, "original_blueprints"):
        app.original_blueprints = {bp.name: bp for bp in BLUEPRINTS}
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Initialized original_blueprints with {len(BLUEPRINTS)} blueprints")
    if not hasattr(app, "hook_sys_paths"):
        app.hook_sys_paths = {}
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Initialized hook_sys_paths tracking")
    if not hasattr(app, "plugin_sys_paths"):
        app.plugin_sys_paths = {}
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Initialized plugin_sys_paths tracking")

    # Reset hooks to clean state before reloading
    for hook_info in HOOKS.values():
        app.config[hook_info["key"]] = []
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Reset all hook configurations")

    # Find all python files in ui directories for hooks and blueprints
    core_ui_py_files = list(CORE_PLUGINS_PATH.glob("*/ui/hooks.py"))
    external_ui_py_files = list(EXTERNAL_PLUGINS_PATH.glob("*/ui/hooks.py"))
    pro_ui_py_files = list(PRO_PLUGINS_PATH.glob("*/ui/hooks.py"))
    core_bp_dirs = list(CORE_PLUGINS_PATH.glob("*/ui/blueprints"))
    external_bp_dirs = list(EXTERNAL_PLUGINS_PATH.glob("*/ui/blueprints"))
    pro_bp_dirs = list(PRO_PLUGINS_PATH.glob("*/ui/blueprints"))
    
    logger.debug(f"Found {len(core_ui_py_files)} core hook files")
    logger.debug(f"Found {len(external_ui_py_files)} external hook files")
    logger.debug(f"Found {len(pro_ui_py_files)} pro hook files")
    logger.debug(f"Found {len(core_bp_dirs)} core blueprint directories")
    logger.debug(f"Found {len(external_bp_dirs)} external blueprint directories")
    logger.debug(f"Found {len(pro_bp_dirs)} pro blueprint directories")
    
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Plugin file discovery: {len(core_ui_py_files)} core hooks, {len(external_ui_py_files)} external hooks, {len(pro_ui_py_files)} pro hooks")
        logger.debug(f"[DEBUG] Blueprint directory discovery: {len(core_bp_dirs)} core, {len(external_bp_dirs)} external, {len(pro_bp_dirs)} pro")

    # Track active plugin paths and blueprints for cleanup purposes
    active_plugin_paths = set()
    active_hook_modules = set()
    plugin_blueprints = set()
    blueprint_registry = {}

    # Load hooks from discovered hook files
    for py_file in chain(core_ui_py_files, external_ui_py_files, pro_ui_py_files):
        if not py_file.is_file():
            continue

        active_plugin_paths.add(py_file.parent.parent.parent)
        module_name = f"hooks_{py_file.parent.name}_{py_file.stem}"
        active_hook_modules.add(module_name)
        hook_dir = str(py_file.parent)

        try:
            # Check for a proxy file first
            proxy_file = py_file.parent / "hooks_proxy.py"
            target_file = proxy_file if proxy_file.exists() else py_file
            logger.debug(f"Loading hooks from {target_file} (proxy: {proxy_file.exists()})")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Loading hooks from {target_file} (using proxy: {proxy_file.exists()})")

            # Add to sys.path if not already there
            if hook_dir not in sys_path:
                sys_path.append(hook_dir)
                app.hook_sys_paths[module_name] = hook_dir
                logger.debug(f"Added {hook_dir} to sys.path")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Added {hook_dir} to sys.path for module {module_name}")

            # Load the module dynamically
            spec = spec_from_file_location(module_name, target_file)
            if not spec or not spec.loader:
                logger.warning(f"Could not load spec for file: {target_file}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Failed to create module spec for {target_file}")
                continue

            hook_module = module_from_spec(spec)
            try:
                spec.loader.exec_module(hook_module)
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Successfully loaded hook module {module_name}")
            except Exception:
                logger.exception(f"Error executing module {target_file}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Error executing hook module {target_file}")
                continue

            # Register discovered hook functions
            for hook_type, hook_info in HOOKS.items():
                if hasattr(hook_module, hook_type) and callable(getattr(hook_module, hook_type)):
                    hook_function = getattr(hook_module, hook_type)
                    app.config.setdefault(hook_info["key"], []).append(hook_function)
                    logger.info(f"{hook_info['log_prefix']} hook '{hook_type}' from {py_file} loaded")
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] Registered {hook_type} hook from {py_file}")

            if hook_dir in sys_path:
                sys_path.remove(hook_dir)
        except Exception:
            logger.exception(f"Error loading potential hooks from {py_file}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Exception occurred loading hooks from {py_file}")

    # Clean up obsolete hook paths from sys.path
    for module_name, hook_dir in list(app.hook_sys_paths.items()):
        if module_name not in active_hook_modules and hook_dir in sys_path:
            sys_path.remove(hook_dir)
            del app.hook_sys_paths[module_name]
            logger.debug(f"Removed {hook_dir} from sys.path for obsolete hook {module_name}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Cleaned up obsolete hook path: {hook_dir} for {module_name}")

    # Load blueprints from discovered blueprint directories
    for bp_dir in chain(pro_bp_dirs, external_bp_dirs, core_bp_dirs):
        if not bp_dir.is_dir():
            continue

        # Track plugin path and determine plugin type
        active_plugin_paths.add(bp_dir.parent.parent.parent)
        blueprint_dir = str(bp_dir)
        is_pro = bp_dir in (p.parent for p in pro_bp_dirs)
        is_external = bp_dir in (p.parent for p in external_bp_dirs)
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Processing blueprint directory: {blueprint_dir} (pro: {is_pro}, external: {is_external})")

        # Add directory to sys_path for imports
        if blueprint_dir not in sys_path:
            sys_path.append(blueprint_dir)

        # Load blueprints from Python files in the directory
        for bp_file in bp_dir.glob("*.py"):
            if bp_file.name.endswith("_proxy.py"):
                continue

            try:
                # Check for a proxy file first
                proxy_file = bp_file.parent / f"{bp_file.stem}_proxy.py"
                module_name = f"blueprint_{bp_dir.parent.name}_{bp_file.stem}"
                
                # Use the proxy file if it exists, otherwise use the original file
                target_file = proxy_file if proxy_file.exists() else bp_file
                logger.debug(f"Loading blueprint from {target_file} (proxy: {proxy_file.exists()})")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Loading blueprint from {target_file} (using proxy: {proxy_file.exists()})")

                spec = spec_from_file_location(module_name, target_file)
                if not spec or not spec.loader:
                    logger.debug(f"Could not create spec for {target_file}")
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] Failed to create spec for blueprint file {target_file}")
                    continue

                bp_module = module_from_spec(spec)
                spec.loader.exec_module(bp_module)
                logger.debug(f"Successfully loaded module {module_name}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Successfully loaded blueprint module {module_name}")

                # Look for a blueprint object with the same name as the file
                bp_name = bp_file.stem
                if hasattr(bp_module, bp_name):
                    bp = getattr(bp_module, bp_name)
                    # Verify it's a Blueprint or has blueprint-like characteristics
                    if isinstance(bp, Blueprint) or (
                        hasattr(bp, "name")
                        and hasattr(bp, "route")
                        and callable(getattr(bp, "route"))
                        and hasattr(bp, "register")
                        and callable(getattr(bp, "register"))
                    ):
                        plugin_blueprints.add(bp_name)

                        # Set plugin priority and path for blueprint registration
                        bp.plugin_priority = 2 if is_pro else (1 if is_external else 0)
                        bp.import_path = blueprint_dir
                        app.plugin_sys_paths[bp_name] = blueprint_dir
                        if getenv("LOG_LEVEL") == "debug":
                            logger.debug(f"[DEBUG] Blueprint {bp_name} configured with priority {bp.plugin_priority}")

                        # Make template folder absolute for proper template loading
                        if bp.template_folder:
                            bp.template_folder = abspath(bp.template_folder)

                        # Register in our blueprint registry by priority
                        if bp_name not in blueprint_registry or bp.plugin_priority > getattr(blueprint_registry[bp_name], "plugin_priority", 0):
                            blueprint_registry[bp_name] = bp
                            logger.info(f"Blueprint '{bp_name}' from {bp_file} registered with priority {bp.plugin_priority}")
                            if getenv("LOG_LEVEL") == "debug":
                                logger.debug(f"[DEBUG] Added blueprint {bp_name} to registry with priority {bp.plugin_priority}")
                    else:
                        logger.warning(f"Object '{bp_name}' in {bp_file} is not a valid Blueprint")
                        if getenv("LOG_LEVEL") == "debug":
                            logger.debug(f"[DEBUG] Invalid blueprint object {bp_name} in {bp_file}")
                else:
                    logger.debug(f"No blueprint named '{bp_name}' found in {bp_file}")
                    if getenv("LOG_LEVEL") == "debug":
                        logger.debug(f"[DEBUG] No blueprint object named {bp_name} found in {bp_file}")
            except Exception:
                logger.exception(f"Error loading blueprint from {bp_file}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Exception occurred loading blueprint from {bp_file}")

    # Remove blueprints for deleted plugins and clean up resources
    logger.debug(f"Checking for blueprints to remove. Current: {list(app.blueprints.keys())}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Current registered blueprints: {list(app.blueprints.keys())}")
    for bp_name in list(app.blueprints.keys()):
        if bp_name not in plugin_blueprints and bp_name not in app.original_blueprints:
            logger.debug(f"Removing blueprint '{bp_name}' - not in plugin or original blueprints")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Removing obsolete blueprint: {bp_name}")
            # Remove blueprint and clean up
            app.blueprints.pop(bp_name, None)

            # Clean up sys.path
            if bp_name in app.plugin_sys_paths and app.plugin_sys_paths[bp_name] in sys_path:
                sys_path.remove(app.plugin_sys_paths[bp_name])
                del app.plugin_sys_paths[bp_name]

            # Remove URL rules and endpoints
            for rule in list(app.url_map.iter_rules()):
                if rule.endpoint.startswith(f"{bp_name}."):
                    if str(rule) == f"/{bp_name}" and bp_name in app.config["EXTRA_PAGES"]:
                        app.config["EXTRA_PAGES"].remove(bp_name)

                    with suppress(ValueError):
                        app.url_map._rules.remove(rule)
                        app.url_map._rules_by_endpoint.pop(rule.endpoint, None)

            # Remove view functions
            for endpoint in [ep for ep in app.view_functions if ep.startswith(f"{bp_name}.")]:
                app.view_functions.pop(endpoint, None)

            logger.debug(f"Blueprint '{bp_name}' was completely removed")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Completely removed blueprint {bp_name} and its resources")

    # Restore original blueprints if missing after cleanup
    for bp_name, bp in app.original_blueprints.items():
        if bp_name not in app.blueprints:
            app.register_blueprint(bp)
            logger.debug(f"Re-registered original blueprint '{bp_name}'")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Restored original blueprint: {bp_name}")

    # Register new and updated plugin blueprints
    for bp_name, bp in blueprint_registry.items():
        # Check if we should replace existing blueprint
        if bp_name in app.blueprints:
            existing_bp = app.blueprints[bp_name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(bp, "plugin_priority", 0)
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Blueprint {bp_name} priority comparison: existing {existing_priority} vs new {new_priority}")

            if new_priority <= existing_priority:
                logger.debug(f"Skipping registration for '{bp_name}' (priority {new_priority} <= {existing_priority})")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Skipping blueprint {bp_name} due to lower/equal priority")
                continue

            # Remove existing blueprint before registering the new one
            for rule in list(app.url_map.iter_rules()):
                if rule.endpoint.startswith(f"{bp_name}."):
                    app.url_map._rules.remove(rule)
                    app.url_map._rules_by_endpoint.pop(rule.endpoint, None)

            for endpoint in [ep for ep in app.view_functions if ep.startswith(f"{bp_name}.")]:
                app.view_functions.pop(endpoint, None)

        # Register the blueprint with Flask
        app.register_blueprint(bp)
        logger.info(f"Registered blueprint '{bp_name}' with priority {getattr(bp, 'plugin_priority', 0)}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Registered blueprint {bp_name} with priority {getattr(bp, 'plugin_priority', 0)}")

        # Add to extra pages if it has a root route
        for rule in app.url_map.iter_rules():
            if rule.endpoint.startswith(f"{bp_name}.") and str(rule) == f"/{bp_name}" and bp_name not in app.config["EXTRA_PAGES"]:
                app.config["EXTRA_PAGES"].append(bp_name)
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Added blueprint {bp_name} to extra pages")
                break

    # Reset Jinja2 environment to apply template changes
    app.jinja_env.cache = {}
    app.jinja_env.loader = app.create_global_jinja_loader()
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Reset Jinja2 environment and template loader")

    # Update the worker's refresh generation using set_nested to ensure it's saved properly
    DATA.set_nested(["WORKERS", worker_pid, "refresh_generation"], current_generation)
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Updated worker {worker_pid} refresh generation to {current_generation}")

    # Remove legacy keys if they exist
    if "refresh_context" in DATA.get("WORKERS", {}).get(worker_pid, {}):
        # Use set_nested again to ensure proper update
        DATA.set_nested(["WORKERS", worker_pid, "refresh_context"], None)
        DATA["WORKERS"][worker_pid].pop("refresh_context", None)
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Removed legacy refresh_context key for worker {worker_pid}")

    # Remove other legacy flags
    if "NEEDS_CONTEXT_REFRESH" in DATA:
        del DATA["NEEDS_CONTEXT_REFRESH"]
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Removed legacy NEEDS_CONTEXT_REFRESH flag")

    logger.debug(f"Worker {worker_pid} completed context refresh to generation {current_generation}")
    logger.debug(f"Total active plugins: {len(active_plugin_paths)}")
    logger.debug(f"Total registered blueprints: {len(blueprint_registry)}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Context refresh completed for worker {worker_pid}: {len(active_plugin_paths)} plugins, {len(blueprint_registry)} blueprints")


# Run before each request to check auth, database state, and refresh context
@app.before_request
def before_request():
    # Execute pre-request checks including authentication, database state,
    # plugin reloading, and context refresh before processing each request
    # Handles session validation, security checks, and environment setup
    logger.debug(f"Processing request: {request.method} {request.path}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Before request processing: {request.method} {request.path}")
    DATA.load_from_file()
    
    if DATA.get("SERVER_STOPPING", False):
        logger.debug("Server is stopping, returning 503")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Server shutdown in progress, returning 503 service unavailable")
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    # Configure session cookies based on request source (reverse proxy or direct)
    if request.environ.get("HTTP_X_FORWARDED_FOR") is not None:
        # Requests from the reverse proxy
        logger.debug(f"Request from reverse proxy, X-Forwarded-For: {request.environ.get('HTTP_X_FORWARDED_FOR')}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Request from reverse proxy detected, using secure cookies")
        app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_NAME"] = "__Host-bw_ui_remember_token"
        app.config["REMEMBER_COOKIE_SECURE"] = True
    else:
        # Requests from other sources
        logger.debug("Direct request, not from reverse proxy")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Direct request detected, using standard cookies")
        app.config["SESSION_COOKIE_NAME"] = "bw_ui_session"
        app.config["SESSION_COOKIE_SECURE"] = False
        app.config["REMEMBER_COOKIE_NAME"] = "bw_ui_remember_token"
        app.config["REMEMBER_COOKIE_SECURE"] = False

    metadata = None
    app.config["SCRIPT_NONCE"] = token_urlsafe(32)
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Generated script nonce: {app.config['SCRIPT_NONCE'][:10]}...")

    # Skip heavy processing for static assets
    if not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/")):
        metadata = DB.get_metadata()
        worker_pid = str(getpid())
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Processing dynamic request for worker {worker_pid}")

        # Ensure worker exists in DATA structure
        if "WORKERS" not in DATA:
            DATA["WORKERS"] = {}
        if worker_pid not in DATA["WORKERS"]:
            # Use set_nested to properly initialize the worker data
            DATA.set_nested(["WORKERS", worker_pid, "refresh_generation"], 0)
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Initialized worker {worker_pid} in DATA structure")

        # Get current refresh generation and worker's refresh generation
        current_generation = DATA.get("REFRESH_GENERATION", 0)
        worker_generation = DATA["WORKERS"][worker_pid].get("refresh_generation", 0)
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Generation check: current {current_generation}, worker {worker_generation}")

        # Plugin reload trigger
        if DATA.get("FORCE_RELOAD_PLUGIN", False) or (
            not DATA.get("RELOADING", False) and metadata.get("reload_ui_plugins", False) and not DATA.get("IS_RELOADING_PLUGINS", False)
        ):
            logger.debug(f"Plugin reload triggered - FORCE_RELOAD_PLUGIN: {DATA.get('FORCE_RELOAD_PLUGIN', False)}, reload_ui_plugins: {metadata.get('reload_ui_plugins', False)}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Plugin reload triggered: force={DATA.get('FORCE_RELOAD_PLUGIN', False)}, metadata={metadata.get('reload_ui_plugins', False)}")
            safe_reload_plugins()
            # Increment refresh generation to trigger refresh for all workers
            DATA["REFRESH_GENERATION"] = current_generation + 1
            logger.info(f"Incremented refresh generation to {DATA['REFRESH_GENERATION']}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Incremented refresh generation to {DATA['REFRESH_GENERATION']}")
            # Refresh this worker immediately
            refresh_app_context()
        # Normal request - check if this worker needs to refresh
        elif not DATA.get("RELOADING", False) and worker_generation < current_generation:
            logger.debug(f"Worker {worker_pid} refreshing (generation {worker_generation} < {current_generation})")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Worker {worker_pid} needs refresh due to generation mismatch")
            refresh_app_context()

        # Check for GitHub release updates periodically
        if datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LATEST_VERSION_LAST_CHECK", "1970-01-01T00:00:00")).astimezone() > timedelta(hours=1):
            DATA["LATEST_VERSION_LAST_CHECK"] = datetime.now().astimezone().isoformat()
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Starting background thread for latest version check")
            Thread(target=update_latest_stable_release).start()

        # Start database state monitoring in background thread
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Starting background thread for database state check")
        Thread(target=check_database_state, args=(request.method, request.path)).start()

        DB.readonly = DATA.get("READONLY_MODE", False)

        # Show readonly mode warning for non-auth pages
        if not request.path.startswith(("/check", "/loading", "/login", "/totp")) and DB.readonly:
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Database in readonly mode, showing warning message")
            flask_flash("Database connection is in read-only mode : no modifications possible.", "error")

        # Perform authentication and session validation for authenticated users
        if current_user.is_authenticated:
            logger.debug(f"User {current_user.get_id()} is authenticated")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Processing authenticated user: {current_user.get_id()}")
            passed = True

            # Initialize session tracking data
            if "ip" not in session:
                session["ip"] = request.remote_addr
                logger.debug(f"Setting session IP to {request.remote_addr}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Initialized session IP: {request.remote_addr}")
            if "user_agent" not in session:
                session["user_agent"] = request.headers.get("User-Agent")
                logger.debug(f"Setting session User-Agent")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug("[DEBUG] Initialized session User-Agent")

            # Case not login page, keep on 2FA before any other access
            if not session.get("totp_validated", False) and bool(current_user.totp_secret) and "/totp" not in request.path:
                logger.debug(f"User {current_user.get_id()} needs TOTP validation")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] User {current_user.get_id()} requires TOTP validation")
                if not request.path.endswith("/login"):
                    return redirect(url_for("totp.totp_page", next=request.form.get("next")))
                passed = False
            # Validate session IP for security (configurable for private networks)
            elif (app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private) and session["ip"] != request.remote_addr:
                logger.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                logger.debug(f"Session IP: {session['ip']}, Request IP: {request.remote_addr}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] IP mismatch for user {current_user.get_id()}: session {session['ip']} vs request {request.remote_addr}")
                passed = False
            # Validate User-Agent for session security
            elif session["user_agent"] != request.headers.get("User-Agent"):
                logger.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                logger.debug(f"Session UA: {session['user_agent'][:50]}..., Request UA: {request.headers.get('User-Agent', '')[:50]}...")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] User-Agent mismatch for user {current_user.get_id()}")
                passed = False
            # Check for revoked sessions
            elif "session_id" in session and session["session_id"] in DATA.get("REVOKED_SESSIONS", []):
                logger.warning(f"User {current_user.get_id()} tried to access a revoked session.")
                logger.debug(f"Session ID: {session['session_id']}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Revoked session access attempt by user {current_user.get_id()}")
                passed = False

            if not passed:
                logger.debug(f"Authentication check failed for user {current_user.get_id()}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Authentication validation failed for user {current_user.get_id()}")
                return logout_page(), 403
            else:
                logger.debug(f"Authentication check passed for user {current_user.get_id()}")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Authentication validation passed for user {current_user.get_id()}")

    # Set current endpoint for template context
    current_endpoint = request.path.split("/")[-1]
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Current endpoint identified as: {current_endpoint}")
    
    # Configure environment for special pages (minimal context)
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp")):
        app.config["ENV"] = dict(current_endpoint=current_endpoint, script_nonce=app.config["SCRIPT_NONCE"], supported_languages=SUPPORTED_LANGUAGES)
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Configured minimal environment for special page")
    else:
        if not metadata:
            metadata = DB.get_metadata()

        # Check for ongoing configuration changes
        changes_ongoing = any(
            v
            for k, v in metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        )
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Configuration changes ongoing: {changes_ongoing}")

        if not changes_ongoing and DATA.get("PRO_LOADING"):
            DATA["PRO_LOADING"] = False
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Cleared PRO_LOADING flag")

        # Handle configuration change notifications
        if not request.path.startswith("/loading"):
            if not changes_ongoing and metadata["failover"]:
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug("[DEBUG] Showing failover error messages")
                flask_flash(
                    "<p class='p-0 m-0 fst-italic'>The last changes could not be applied because it creates a configuration error on NGINX, please check BunkerWeb's logs for more information. The configuration fell back to the last working one.</p>",
                    "error",
                )
                flask_flash(
                    f"""<div class='d-flex flex-column'>
                        <h6 class='fw-bold mb-1'>Failover Message:</h6>
                        <p class='p-0 m-0 fst-italic'>{metadata['failover_message']}</p>
                    </div>""",
                    "error",
                )
            elif not changes_ongoing and not metadata["failover"] and DATA.get("CONFIG_CHANGED", False):
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug("[DEBUG] Showing configuration success message")
                flash("The last changes have been applied successfully.")
                DATA["CONFIG_CHANGED"] = False

        # Determine if this is a CORS or AJAX request
        fetch_mode = request.headers.get("Sec-Fetch-Mode")
        x_requested_with = request.headers.get("X-Requested-With")
        is_cors = fetch_mode == "cors" or (x_requested_with and x_requested_with.lower() == "xmlhttprequest")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Request type detection - CORS/AJAX: {is_cors}, fetch_mode: {fetch_mode}, x_requested_with: {x_requested_with}")

        # Process pending flash messages for non-CORS requests
        if not is_cors:
            seen = set()
            logger.debug(f"Processing {len(DATA.get('TO_FLASH', []))} pending flash messages")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Processing {len(DATA.get('TO_FLASH', []))} pending flash messages")
            for f in DATA.get("TO_FLASH", []):
                content = f["content"]
                if content in seen:
                    continue
                seen.add(content)
                flash(content, f["type"], save=f.get("save", True))
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Processed flash message of type: {f['type']}")
            DATA["TO_FLASH"] = []

        # Build comprehensive environment data for template rendering
        data = dict(
            current_endpoint=current_endpoint,
            script_nonce=app.config["SCRIPT_NONCE"],
            bw_version=metadata["version"],
            latest_version=DATA.get("LATEST_VERSION", "unknown"),
            is_pro_version=metadata["is_pro"],
            pro_status=metadata["pro_status"],
            pro_services=metadata["pro_services"],
            pro_expire=metadata["pro_expire"].strftime("%Y/%m/%d") if isinstance(metadata["pro_expire"], datetime) else "Unknown",
            pro_overlapped=metadata["pro_overlapped"],
            plugins=BW_CONFIG.get_plugins(),
            flash_messages=session.get("flash_messages", []),
            is_readonly=DATA.get("READONLY_MODE", False) or ("write" not in current_user.list_permissions and not request.path.startswith("/profile")),
            db_readonly=DATA.get("READONLY_MODE", False),
            user_readonly="write" not in current_user.list_permissions,
            theme=current_user.theme if current_user.is_authenticated else "dark",
            language=current_user.language if current_user.is_authenticated else "en",
            supported_languages=SUPPORTED_LANGUAGES,
            columns_preferences_defaults=COLUMNS_PREFERENCES_DEFAULTS,
            extra_pages=app.config["EXTRA_PAGES"],
            extra_scripts=DATA.get("EXTRA_SCRIPTS", []),
            config=DB.get_config(global_only=True, methods=True),
        )
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Built environment data with {len(data)} variables")

        # Add column preferences for supported endpoints
        if current_endpoint in COLUMNS_PREFERENCES_DEFAULTS:
            data["columns_preferences"] = DB.get_ui_user_columns_preferences(current_user.get_id(), current_endpoint)
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Added column preferences for endpoint: {current_endpoint}")

        app.config["ENV"] = data

    # Execute registered before_request hooks
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Executing {len(app.config['BEFORE_REQUEST_HOOKS'])} before_request hooks")
    for hook in app.config["BEFORE_REQUEST_HOOKS"]:
        try:
            logger.debug(f"Executing before_request hook: {hook.__name__}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Executing before_request hook: {hook.__name__}")
            resp = hook()
            if resp:
                logger.debug(f"Before_request hook {hook.__name__} returned response")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] Before_request hook {hook.__name__} returned early response")
                return resp
        except Exception:
            logger.exception("Error in before_request hook")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Exception in before_request hook: {hook.__name__}")


# Mark user access time in database asynchronously
def mark_user_access(user, session_id):
    # Record user access timestamp in database for audit and session tracking
    # This runs asynchronously to avoid blocking the main request thread
    logger.debug(f"Marking user access for session {session_id}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Marking user access for session: {session_id}")
    
    if user and "write" not in user.list_permissions or DB.readonly:
        logger.debug(f"Skipping user access marking - user write permission: {'write' in user.list_permissions if user else 'N/A'}, DB readonly: {DB.readonly}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Skipping user access marking due to permissions or readonly DB")
        return

    ret = DB.mark_ui_user_access(session_id, datetime.now().astimezone())
    if ret:
        logger.error(f"Couldn't mark the user access: {ret}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Failed to mark user access: {ret}")
    else:
        logger.debug(f"Marked the user access for session {session_id}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Successfully marked user access for session {session_id}")


# Set security headers on all responses to prevent common attacks
@app.after_request
def set_security_headers(response):
    # Set comprehensive security headers on all responses to prevent
    # XSS, clickjacking, CSRF, and other common web vulnerabilities
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Setting security headers on response")
    
    # Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src https: http: 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com https://api.github.com;"
        + f" script-src https: http: 'self' 'nonce-{app.config['SCRIPT_NONCE']}' 'strict-dynamic' 'unsafe-inline';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: blob: https://www.bunkerweb.io https://assets.bunkerity.com https://*.tile.openstreetmap.org;"
        + " font-src 'self' data:;"
        + " base-uri 'self';"
        + " block-all-mixed-content;"
        + (
            " connect-src *;"
            if request.path.startswith(("/check", "/setup"))
            else " connect-src https: http: 'self' https://api.github.com/repos/bunkerity/bunkerweb https://www.bunkerweb.io/api/posts/0/3;"
        )
    )
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Set Content-Security-Policy header")

    # HTTPS-specific security headers when behind reverse proxy
    if request.headers.get("X-Forwarded-Proto") == "https":
        if not request.path.startswith("/setup/loading"):
            response.headers["Content-Security-Policy"] += " upgrade-insecure-requests;"

        # Strict-Transport-Security header to force HTTPS if accessed via a reverse proxy
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Set HTTPS-specific security headers")

    # X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions-Policy header to prevent unwanted behavior
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()"
    )
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Set additional security headers (X-Frame-Options, X-Content-Type-Options, etc.)")

    # Execute registered after_request hooks
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Executing {len(app.config['AFTER_REQUEST_HOOKS'])} after_request hooks")
    for hook in app.config["AFTER_REQUEST_HOOKS"]:
        try:
            logger.debug(f"Executing after_request hook: {hook.__name__}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Executing after_request hook: {hook.__name__}")
            resp = hook(response)
            if resp:
                logger.debug(f"After_request hook {hook.__name__} returned response")
                if getenv("LOG_LEVEL") == "debug":
                    logger.debug(f"[DEBUG] After_request hook {hook.__name__} returned modified response")
                return resp
        except Exception:
            logger.exception("Error in after_request hook")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Exception in after_request hook: {hook.__name__}")

    return response


# Clean up after request and mark user access asynchronously
@app.teardown_request
def teardown_request(teardown):
    # Perform cleanup operations after request processing including
    # user access logging and execution of teardown hooks
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Teardown request processing, teardown object: {teardown}")
    
    # Mark user access for authenticated users on non-static requests
    if (
        not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/"))
        and current_user.is_authenticated
        and "session_id" in session
    ):
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Starting user access marking for session {session['session_id']}")
        Thread(target=mark_user_access, args=(current_user, session["session_id"])).start()

    # Execute registered teardown_request hooks
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Executing {len(app.config['TEARDOWN_REQUEST_HOOKS'])} teardown_request hooks")
    for hook in app.config["TEARDOWN_REQUEST_HOOKS"]:
        try:
            logger.debug(f"Executing teardown_request hook: {hook.__name__}")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Executing teardown_request hook: {hook.__name__}")
            hook(teardown)
        except Exception:
            logger.exception("Error in teardown_request hook")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug(f"[DEBUG] Exception in teardown_request hook: {hook.__name__}")


### * MISC ROUTES * ###


# Root route - redirect to appropriate page based on auth state
@app.route("/", strict_slashes=False, methods=["GET"])
def index():
    # Handle root route by redirecting users to appropriate page
    # based on their authentication status and system setup state
    # Determines if setup is needed or user should go to login/home
    logger.debug("Root route accessed")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Processing root route request")
    
    if DB.get_ui_user():
        if current_user.is_authenticated:  # type: ignore
            logger.debug("Authenticated user, redirecting to home page")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Authenticated user detected, redirecting to home")
            return redirect(url_for("home.home_page"))
        logger.debug("User exists but not authenticated, redirecting to login page")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] User exists but not authenticated, redirecting to login")
        return redirect(url_for("login.login_page"), 301)
    logger.debug("No users in database, redirecting to setup page")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] No users found, redirecting to setup")
    return redirect(url_for("setup.setup_page"), 301)


# Loading page displayed during system operations
@app.route("/loading", methods=["GET"])
@login_required
def loading():
    # Display loading page during system operations with configurable message
    # and redirect target for user experience during background processing
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Loading page requested")
    home_url = url_for("home.home_page")
    next_url = request.values.get("next", None) or home_url
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Loading page: next_url={next_url}, home_url={home_url}")

    if not next_url.startswith(home_url.replace("/home", "/", 1).replace("//", "/")):
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Invalid next_url provided, returning 400")
        return Response(status=400)

    message = request.values.get("message", "Loading...")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Rendering loading page with message: {message}")
    return render_template("loading.html", message=message, next=next_url)


# Health check endpoint for wizard/external monitoring
@app.route("/check", methods=["GET"])
def check():
    # Simple health check endpoint for external monitoring systems
    # Returns basic OK status with CORS headers for wizard compatibility
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Health check endpoint accessed")
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


# Conditional healthcheck endpoint for container orchestration
if getenv("ENABLE_HEALTHCHECK", "no").lower() == "yes":
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Healthcheck endpoint enabled via environment variable")
    
    # Simple healthcheck endpoint for container orchestration systems
    @app.route("/healthcheck", methods=["GET"])
    def healthcheck():
        # Container orchestration healthcheck endpoint that returns
        # basic service status and timestamp information
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Container healthcheck endpoint accessed")
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().astimezone().isoformat(),
            "service": "bunkerweb-ui",
        }
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Returning healthcheck data: {health_data}")

        return Response(status=200, response=dumps(health_data), content_type="application/json")


# Check if system is reloading configuration
@app.route("/check_reloading", methods=["GET"])
@login_required
def check_reloading():
    # Check system reload status for UI polling during configuration changes
    # Handles timeout logic and forced reload state management
    # Returns JSON response indicating if system is currently reloading
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Checking reload status")
    DATA.load_from_file()
    current_time = time()

    db_metadata = DB.get_metadata()
    changes_ongoing = any(
        v
        for k, v in db_metadata.items()
        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
    )
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Changes ongoing: {changes_ongoing}, last reload: {DATA.get('LAST_RELOAD', 0)}")
    
    if (
        not changes_ongoing
        and DATA.get("LAST_RELOAD", 0) + 2 < current_time
    ):
        DATA["RELOADING"] = False
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Cleared RELOADING flag due to completed changes")

    # Handle reload timeout (force completion after 60 seconds)
    if not DATA.get("RELOADING", False) or DATA.get("LAST_RELOAD", 0) + 60 < current_time:
        if DATA.get("RELOADING", False):
            logger.warning("Reloading took too long, forcing the state to be reloaded")
            if getenv("LOG_LEVEL") == "debug":
                logger.debug("[DEBUG] Forced reload completion due to timeout")
            flask_flash("Forced the status to be reloaded", "error")
            DATA["RELOADING"] = False

    reload_status = DATA.get("RELOADING", False)
    logger.debug(f"Reloading check: {reload_status}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Returning reload status: {reload_status}")

    return jsonify({"reloading": reload_status})


# Update user theme preference
@app.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    # Update user's theme preference (dark/light mode) in database
    # Validates theme value and handles database readonly state
    # Returns JSON response indicating success or failure
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Theme change request: {request.form.get('theme')}")
    
    if DB.readonly:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Theme change rejected due to readonly database")
        return Response(status=423, response=dumps({"message": "Database is in read-only mode"}), content_type="application/json")
    elif request.form["theme"] not in ("dark", "light"):
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Invalid theme value: {request.form.get('theme')}")
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    user_data = {
        "username": current_user.get_id(),
        "password": current_user.password.encode("utf-8"),
        "email": current_user.email,
        "totp_secret": current_user.totp_secret,
        "method": current_user.method,
        "theme": request.form["theme"],
        "language": current_user.language,
    }

    ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
    if ret:
        logger.error(f"Couldn't update the user {current_user.get_id()}: {ret}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Database error updating user theme: {ret}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    logger.debug(f"Updated theme to {request.form['theme']} for user {current_user.get_id()}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Successfully updated theme to {request.form['theme']} for user {current_user.get_id()}")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


# Update user language preference
@app.route("/set_language", methods=["POST"])
@login_required
def set_language():
    # Update user's language preference in database with validation
    # against supported languages list and readonly state checking
    # Converts language code to lowercase for consistency
    lang = request.form["language"].lower()
    allowed_languages = {lang["code"] for lang in SUPPORTED_LANGUAGES}
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Language change request: {lang}, allowed: {allowed_languages}")
    
    if DB.readonly:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Language change rejected due to readonly database")
        return Response(status=423, response=dumps({"message": "Database is in read-only mode"}), content_type="application/json")
    elif lang not in allowed_languages:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Invalid language code: {lang}")
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    user_data = {
        "username": current_user.get_id(),
        "password": current_user.password.encode("utf-8"),
        "email": current_user.email,
        "totp_secret": current_user.totp_secret,
        "method": current_user.method,
        "theme": current_user.theme,
        "language": lang,
    }

    ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
    if ret:
        logger.error(f"Couldn't update the user {current_user.get_id()}: {ret}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Database error updating user language: {ret}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    logger.debug(f"Updated language to {lang} for user {current_user.get_id()}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Successfully updated language to {lang} for user {current_user.get_id()}")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


# Update user table column preferences
@app.route("/set_columns_preferences", methods=["POST"])
@login_required
def set_columns_preferences():
    # Update user's table column visibility preferences for data tables
    # Validates table name and column names against allowed defaults
    # Parses JSON string containing column preference settings
    table_name = request.form.get("table_name")
    columns_preferences = request.form.get("columns_preferences", "{}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Column preferences update: table={table_name}")

    try:
        columns_preferences = loads(columns_preferences)
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Parsed column preferences: {len(columns_preferences)} columns")
    except BaseException:
        if getenv("LOG_LEVEL") == "debug":
            logger.debug("[DEBUG] Failed to parse column preferences JSON")
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    if (
        DB.readonly
        or table_name not in COLUMNS_PREFERENCES_DEFAULTS
        or any(column not in COLUMNS_PREFERENCES_DEFAULTS[table_name] for column in columns_preferences)
    ):
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Invalid column preferences request: readonly={DB.readonly}, table_valid={table_name in COLUMNS_PREFERENCES_DEFAULTS}")
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    ret = DB.update_ui_user_columns_preferences(current_user.get_id(), table_name, columns_preferences)
    if ret:
        logger.error(f"Couldn't update the user {current_user.get_id()}'s columns preferences: {ret}")
        if getenv("LOG_LEVEL") == "debug":
            logger.debug(f"[DEBUG] Database error updating column preferences: {ret}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    logger.debug(f"Updated column preferences for table {table_name} for user {current_user.get_id()}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Successfully updated column preferences for table {table_name}")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


# Clear all flash notifications from session
@app.route("/clear_notifications", methods=["POST"])
@login_required
def clear_notifications():
    # Clear all pending flash notifications from user's session
    # Used by frontend to dismiss notification messages
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Clearing notifications for user {current_user.get_id()}")
    session["flash_messages"] = []
    session.modified = True
    logger.debug(f"Cleared notifications for user {current_user.get_id()}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug("[DEBUG] Successfully cleared all flash notifications")
    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


# Import all route blueprints for the application
from app.routes.about import about
from app.routes.bans import bans
from app.routes.cache import cache
from app.routes.configs import configs
from app.routes.global_config import global_config
from app.routes.home import home
from app.routes.instances import instances
from app.routes.jobs import jobs
from app.routes.login import login
from app.routes.logout import logout, logout_page
from app.routes.logs import logs
from app.routes.plugins import plugins
from app.routes.pro import pro
from app.routes.profile import profile
from app.routes.reports import reports
from app.routes.services import services
from app.routes.setup import setup
from app.routes.totp import totp
from app.routes.support import support

# Define all default application blueprints in order
BLUEPRINTS = (
    about,
    services,
    profile,
    jobs,
    reports,
    totp,
    home,
    logout,
    instances,
    plugins,
    global_config,
    pro,
    cache,
    logs,
    login,
    configs,
    bans,
    setup,
    support,
)

# Register all default blueprints with the Flask application
logger.debug(f"Registering {len(BLUEPRINTS)} default blueprints")
if getenv("LOG_LEVEL") == "debug":
    logger.debug(f"[DEBUG] Starting registration of {len(BLUEPRINTS)} default blueprints")
for blueprint in BLUEPRINTS:
    logger.debug(f"Registering blueprint: {blueprint.name}")
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] Registering blueprint: {blueprint.name}")
    app.register_blueprint(blueprint)
logger.debug("Default blueprint registration complete")
if getenv("LOG_LEVEL") == "debug":
    logger.debug("[DEBUG] Default blueprint registration completed successfully")
