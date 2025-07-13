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

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI")

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
    def create_global_jinja_loader(self):
        """
        Override Flask's default template loader creation so that
        blueprint template folders (especially plugins) take precedence
        over the application's global template folder.
        """
        logger.debug("Creating global jinja loader with custom blueprint priority handling")
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
                else:
                    logger.debug(f"Using existing jinja_loader for blueprint '{name}'")
                # Priority: higher means we want it searched first.
                priority = getattr(bp, "plugin_priority", 0)
                logger.debug(f"Blueprint '{name}' has plugin_priority: {priority}")
                blueprint_loaders.append((priority, loader))

        # Sort blueprint loaders descending by priority
        blueprint_loaders.sort(key=itemgetter(0), reverse=True)
        loaders_in_order = [ldr for (_prio, ldr) in blueprint_loaders]
        logger.debug(f"Blueprint loaders sorted by priority: {[p for p, _ in blueprint_loaders]}")

        # Finally, add the app's own jinja_loader (which handles the global templates folder)
        # at the end. This ensures plugin templates overshadow global templates if names clash.
        if self.jinja_loader is not None:
            loaders_in_order.append(self.jinja_loader)
            logger.debug("App's jinja_loader appended to the end of loaders list")

        final_loader = ChoiceLoader(loaders_in_order)
        logger.debug("Global jinja loader created successfully")
        return final_loader

    def register_blueprint(self, blueprint, **options):
        # Check if a blueprint with this name is already registered.
        if blueprint.name in self.blueprints:
            existing_bp = self.blueprints[blueprint.name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(blueprint, "plugin_priority", 0)
            if new_priority > existing_priority:
                logger.info(f"Overriding blueprint '{blueprint.name}': new priority {new_priority} over {existing_priority}")
                # Remove the existing blueprint.
                del self.blueprints[blueprint.name]
                # Also remove all URL rules associated with the existing blueprint.
                rules_to_remove = [rule for rule in list(self.url_map.iter_rules()) if rule.endpoint.startswith(blueprint.name + ".")]
                for rule in rules_to_remove:
                    self.url_map._rules.remove(rule)
                    self.url_map._rules_by_endpoint.pop(rule.endpoint, None)
            else:
                logger.info(f"Skipping blueprint '{blueprint.name}' with priority {new_priority} " f"(existing priority {existing_priority})")
                return  # Do not register a lower- or equal-priority blueprint.

        # Allow registration even after first request by temporarily resetting the flag.
        original_got_first = self._got_first_request
        self._got_first_request = False
        try:
            result = super().register_blueprint(blueprint, **options)
        finally:
            self._got_first_request = original_got_first
        return result


# Flask app
app = DynamicFlask(__name__, static_url_path="/", static_folder="app/static", template_folder="app/templates")
app.logger = logger

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    if not LIB_DIR.joinpath(".flask_secret").is_file():
        logger.error("The .flask_secret file is missing, exiting ...")
        stop(1)
    FLASK_SECRET = LIB_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

    app.config["BISCUIT_PUBLIC_KEY_PATH"] = BISCUIT_PUBLIC_KEY_FILE.as_posix()

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

    # Session management
    app.config["SESSION_TYPE"] = "cachelib"
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_ID_LENGTH"] = 64
    app.config["SESSION_CACHELIB"] = FileSystemCache(threshold=500, cache_dir=LIB_DIR.joinpath("ui_sessions_cache"))
    sess = Session()
    sess.init_app(app)

    biscuit = BiscuitMiddleware(app)

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    login_manager.login_view = "login.login_page"
    login_manager.anonymous_user = AnonymousUser

    # CSRF protection
    app.config["WTF_CSRF_METHODS"] = ("POST",)
    app.config["WTF_CSRF_SSL_STRICT"] = False
    csrf = CSRFProtect()
    csrf.init_app(app)

    app.config["EXTRA_PAGES"] = []

    def custom_url_for(endpoint, **values):
        if endpoint:
            try:
                if endpoint not in ("static", "index", "loading", "check", "check_reloading") and "_page" not in endpoint:
                    return url_for(f"{endpoint}.{endpoint}_page", **values)
                return url_for(endpoint, **values)
            except BuildError as e:
                logger.exception(f"Couldn't build the URL for {endpoint}")
        return "#"

    # Declare functions for jinja2
    app.jinja_env.globals.update(
        get_multiples=get_multiples,
        get_filtered_settings=get_filtered_settings,
        get_blacklisted_settings=get_blacklisted_settings,
        get_plugins_settings=BW_CONFIG.get_plugins_settings,
        human_readable_number=human_readable_number,
        url_for=custom_url_for,
        is_plugin_active=is_plugin_active,
    )

    app.config.update({hook_info["key"]: [] for hook_info in HOOKS.values()})

    DATA.load_from_file()
    if "WORKERS" not in DATA:
        DATA["WORKERS"] = {}
    DATA["FORCE_RELOAD_PLUGIN"] = True
    DB.checked_changes(["ui_plugins"], value=True)


@app.context_processor
def inject_variables():
    app_env = app.config["ENV"].copy()
    for hook in app.config["CONTEXT_PROCESSOR_HOOKS"]:
        try:
            resp = hook()
            if resp:
                app_env = {**app_env, **resp}
        except Exception:
            logger.exception("Error in context_processor hook")

    app.config["ENV"] = app_env

    return app_env


@login_manager.user_loader
def load_user(username):
    ui_user = DB.get_ui_user(username=username)
    if not ui_user:
        logger.warning(f"Couldn't get the user {username} from the database.")
        return None

    ui_user.list_roles = [role.role_name for role in ui_user.roles]
    ui_user.list_permissions = []
    for role in ui_user.list_roles:
        ui_user.list_permissions.extend(DB.get_ui_role_permissions(role))
    ui_user.list_permissions = set(ui_user.list_permissions)

    if ui_user.totp_secret:
        ui_user.list_recovery_codes = [recovery_code.code for recovery_code in ui_user.recovery_codes]

        if (
            "totp-disable" not in request.path
            and "totp-refresh" not in request.path
            and session.get("totp_validated", False)
            and not ui_user.list_recovery_codes
        ):
            flask_flash(
                f"""The two-factor authentication is enabled but no recovery codes are available, please refresh them:
<div class="mt-2 pt-2 border-top border-white">
    <a role='button' class='btn btn-sm btn-dark d-flex align-items-center' aria-pressed='true' href='{url_for('profile.profile_page')}'>here</a>
</div>""",
                "error",
            )

    return ui_user


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    logger.exception(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    if not current_user:
        return redirect(url_for("setup.setup_page")), 403
    return logout_page(), 403


def update_latest_stable_release():
    latest_release = get_latest_stable_release()
    if latest_release:
        DATA["LATEST_VERSION"] = latest_release


def check_database_state(request_method: str, request_path: str):
    DATA.load_from_file()
    if (
        DB.database_uri
        and DB.readonly
        and (datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LAST_DATABASE_RETRY", "1970-01-01T00:00:00")).astimezone() > timedelta(minutes=1))
    ):
        failed = False
        try:
            DB.retry_connection(pool_timeout=1)
            DB.retry_connection(log=False)
            logger.info("The database is no longer read-only, defaulting to read-write mode")
        except BaseException:
            failed = True
            try:
                DB.retry_connection(readonly=True, pool_timeout=1)
                DB.retry_connection(readonly=True, log=False)
            except BaseException:
                if DB.database_uri_readonly:
                    with suppress(BaseException):
                        DB.retry_connection(fallback=True, pool_timeout=1)
                        DB.retry_connection(fallback=True, log=False)
        DATA.update(
            {
                "READONLY_MODE": failed,
                "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
            }
        )
    elif (
        DB.database_uri
        and not DATA.get("READONLY_MODE", False)
        and request_method == "POST"
        and not ("/totp" in request_path or "/login" in request_path or request_path.startswith("/plugins/upload"))
    ):
        try:
            DB.test_write()
            DATA["READONLY_MODE"] = False
        except BaseException:
            DATA.update(
                {
                    "READONLY_MODE": True,
                    "LAST_DATABASE_RETRY": DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat(),
                }
            )
    else:
        try:
            DB.test_read()
        except BaseException:
            DATA["LAST_DATABASE_RETRY"] = DB.last_connection_retry.isoformat() if DB.last_connection_retry else datetime.now().astimezone().isoformat()


def refresh_app_context():
    """Refresh Flask app context by loading hooks and blueprints from plugins."""
    worker_pid = str(getpid())
    current_generation = DATA.get("REFRESH_GENERATION", 0)
    worker_generation = DATA.get("WORKERS", {}).get(worker_pid, {}).get("refresh_generation", 0)

    logger.debug(f"Worker {worker_pid} refreshing context (generation {worker_generation} → {current_generation})")
    DATA.load_from_file()

    # Initialize tracking structures if they don't exist
    if not hasattr(app, "original_blueprints"):
        app.original_blueprints = {bp.name: bp for bp in BLUEPRINTS}
    if not hasattr(app, "hook_sys_paths"):
        app.hook_sys_paths = {}
    if not hasattr(app, "plugin_sys_paths"):
        app.plugin_sys_paths = {}

    # Reset hooks
    for hook_info in HOOKS.values():
        app.config[hook_info["key"]] = []

    # Find all python files in ui directories
    core_ui_py_files = list(CORE_PLUGINS_PATH.glob("*/ui/hooks.py"))
    external_ui_py_files = list(EXTERNAL_PLUGINS_PATH.glob("*/ui/hooks.py"))
    pro_ui_py_files = list(PRO_PLUGINS_PATH.glob("*/ui/hooks.py"))
    core_bp_dirs = list(CORE_PLUGINS_PATH.glob("*/ui/blueprints"))
    external_bp_dirs = list(EXTERNAL_PLUGINS_PATH.glob("*/ui/blueprints"))
    pro_bp_dirs = list(PRO_PLUGINS_PATH.glob("*/ui/blueprints"))

    # Track active plugin paths and blueprints
    active_plugin_paths = set()
    active_hook_modules = set()
    plugin_blueprints = set()
    blueprint_registry = {}

    # --- LOAD HOOKS ---
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

            # Add to sys.path if not already there
            if hook_dir not in sys_path:
                sys_path.append(hook_dir)
                app.hook_sys_paths[module_name] = hook_dir

            # Load the module
            spec = spec_from_file_location(module_name, target_file)
            if not spec or not spec.loader:
                logger.warning(f"Could not load spec for file: {target_file}")
                continue

            hook_module = module_from_spec(spec)
            try:
                spec.loader.exec_module(hook_module)
            except Exception as exec_err:
                logger.warning(f"Error executing module {target_file}: {exec_err}")
                continue

            for hook_type, hook_info in HOOKS.items():
                if hasattr(hook_module, hook_type) and callable(getattr(hook_module, hook_type)):
                    hook_function = getattr(hook_module, hook_type)
                    app.config.setdefault(hook_info["key"], []).append(hook_function)
                    logger.info(f"{hook_info['log_prefix']} hook '{hook_type}' from {py_file} loaded")

            if hook_dir in sys_path:
                sys_path.remove(hook_dir)
        except Exception as exc:
            logger.error(f"Error loading potential hooks from {py_file}: {exc}")

    # --- CLEAN UP OBSOLETE HOOK PATHS ---
    for module_name, hook_dir in list(app.hook_sys_paths.items()):
        if module_name not in active_hook_modules and hook_dir in sys_path:
            sys_path.remove(hook_dir)
            del app.hook_sys_paths[module_name]
            logger.debug(f"Removed {hook_dir} from sys.path for obsolete hook {module_name}")

    # --- LOAD BLUEPRINTS ---
    for bp_dir in chain(pro_bp_dirs, external_bp_dirs, core_bp_dirs):
        if not bp_dir.is_dir():
            continue

        # Track plugin path
        active_plugin_paths.add(bp_dir.parent.parent.parent)
        blueprint_dir = str(bp_dir)
        is_pro = bp_dir in (p.parent for p in pro_bp_dirs)
        is_external = bp_dir in (p.parent for p in external_bp_dirs)

        # Add directory to sys_path
        if blueprint_dir not in sys_path:
            sys_path.append(blueprint_dir)

        # Load blueprints from Python files
        for bp_file in bp_dir.glob("*.py"):
            if bp_file.name.endswith("_proxy.py"):
                continue

            try:
                # Check for a proxy file first
                proxy_file = bp_file.parent / f"{bp_file.stem}_proxy.py"
                module_name = f"blueprint_{bp_dir.parent.name}_{bp_file.stem}"

                # Use the proxy file if it exists, otherwise use the original file
                target_file = proxy_file if proxy_file.exists() else bp_file

                spec = spec_from_file_location(module_name, target_file)
                if not spec or not spec.loader:
                    continue

                bp_module = module_from_spec(spec)
                spec.loader.exec_module(bp_module)

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

                        # Set plugin priority and path
                        bp.plugin_priority = 2 if is_pro else (1 if is_external else 0)
                        bp.import_path = blueprint_dir
                        app.plugin_sys_paths[bp_name] = blueprint_dir

                        # Make template folder absolute
                        if bp.template_folder:
                            bp.template_folder = abspath(bp.template_folder)

                        # Register in our blueprint registry by priority
                        if bp_name not in blueprint_registry or bp.plugin_priority > getattr(blueprint_registry[bp_name], "plugin_priority", 0):
                            blueprint_registry[bp_name] = bp
                            logger.info(f"Blueprint '{bp_name}' from {bp_file} registered with priority {bp.plugin_priority}")
                    else:
                        logger.warning(f"Object '{bp_name}' in {bp_file} is not a valid Blueprint")
                else:
                    logger.debug(f"No blueprint named '{bp_name}' found in {bp_file}")
            except Exception as exc:
                logger.error(f"Error loading blueprint from {bp_file}: {exc}")

    # --- HANDLE BLUEPRINT CHANGES ---
    # Remove blueprints for deleted plugins
    for bp_name in list(app.blueprints.keys()):
        if bp_name not in plugin_blueprints and bp_name not in app.original_blueprints:
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

    # Restore original blueprints if missing
    for bp_name, bp in app.original_blueprints.items():
        if bp_name not in app.blueprints:
            app.register_blueprint(bp)
            logger.debug(f"Re-registered original blueprint '{bp_name}'")

    # Register new and updated plugin blueprints
    for bp_name, bp in blueprint_registry.items():
        # Check if we should replace existing blueprint
        if bp_name in app.blueprints:
            existing_bp = app.blueprints[bp_name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(bp, "plugin_priority", 0)

            if new_priority <= existing_priority:
                logger.debug(f"Skipping registration for '{bp_name}' (priority {new_priority} <= {existing_priority})")
                continue

            # Remove existing blueprint before registering the new one
            for rule in list(app.url_map.iter_rules()):
                if rule.endpoint.startswith(f"{bp_name}."):
                    app.url_map._rules.remove(rule)
                    app.url_map._rules_by_endpoint.pop(rule.endpoint, None)

            for endpoint in [ep for ep in app.view_functions if ep.startswith(f"{bp_name}.")]:
                app.view_functions.pop(endpoint, None)

        # Register the blueprint
        app.register_blueprint(bp)
        logger.info(f"Registered blueprint '{bp_name}' with priority {getattr(bp, 'plugin_priority', 0)}")

        # Add to extra pages if it has a root route
        for rule in app.url_map.iter_rules():
            if rule.endpoint.startswith(f"{bp_name}.") and str(rule) == f"/{bp_name}" and bp_name not in app.config["EXTRA_PAGES"]:
                app.config["EXTRA_PAGES"].append(bp_name)
                break

    # Reset Jinja2 environment to apply template changes
    app.jinja_env.cache = {}
    app.jinja_env.loader = app.create_global_jinja_loader()

    # Update the worker's refresh generation using set_nested to ensure it's saved properly
    DATA.set_nested(["WORKERS", worker_pid, "refresh_generation"], current_generation)

    # Remove legacy keys if they exist
    if "refresh_context" in DATA.get("WORKERS", {}).get(worker_pid, {}):
        # Use set_nested again to ensure proper update
        DATA.set_nested(["WORKERS", worker_pid, "refresh_context"], None)
        DATA["WORKERS"][worker_pid].pop("refresh_context", None)

    # Remove other legacy flags
    if "NEEDS_CONTEXT_REFRESH" in DATA:
        del DATA["NEEDS_CONTEXT_REFRESH"]

    logger.debug(f"Worker {worker_pid} completed context refresh to generation {current_generation}")


@app.before_request
def before_request():
    DATA.load_from_file()
    if DATA.get("SERVER_STOPPING", False):
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    if request.environ.get("HTTP_X_FORWARDED_FOR") is not None:
        # Requests from the reverse proxy
        app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_NAME"] = "__Host-bw_ui_remember_token"
        app.config["REMEMBER_COOKIE_SECURE"] = True
    else:
        # Requests from other sources
        app.config["SESSION_COOKIE_NAME"] = "bw_ui_session"
        app.config["SESSION_COOKIE_SECURE"] = False
        app.config["REMEMBER_COOKIE_NAME"] = "bw_ui_remember_token"
        app.config["REMEMBER_COOKIE_SECURE"] = False

    metadata = None
    app.config["SCRIPT_NONCE"] = token_urlsafe(32)

    if not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/")):
        metadata = DB.get_metadata()
        worker_pid = str(getpid())

        # Ensure worker exists in DATA structure
        if "WORKERS" not in DATA:
            DATA["WORKERS"] = {}
        if worker_pid not in DATA["WORKERS"]:
            # Use set_nested to properly initialize the worker data
            DATA.set_nested(["WORKERS", worker_pid, "refresh_generation"], 0)

        # Get current refresh generation and worker's refresh generation
        current_generation = DATA.get("REFRESH_GENERATION", 0)
        worker_generation = DATA["WORKERS"][worker_pid].get("refresh_generation", 0)

        # Plugin reload trigger
        if DATA.get("FORCE_RELOAD_PLUGIN", False) or (
            not DATA.get("RELOADING", False) and metadata.get("reload_ui_plugins", False) and not DATA.get("IS_RELOADING_PLUGINS", False)
        ):
            safe_reload_plugins()
            # Increment refresh generation to trigger refresh for all workers
            DATA["REFRESH_GENERATION"] = current_generation + 1
            logger.info(f"Incremented refresh generation to {DATA['REFRESH_GENERATION']}")
            # Refresh this worker immediately
            refresh_app_context()
        # Normal request - check if this worker needs to refresh
        elif not DATA.get("RELOADING", False) and worker_generation < current_generation:
            logger.debug(f"Worker {worker_pid} refreshing (generation {worker_generation} < {current_generation})")
            refresh_app_context()

        if datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LATEST_VERSION_LAST_CHECK", "1970-01-01T00:00:00")).astimezone() > timedelta(hours=1):
            DATA["LATEST_VERSION_LAST_CHECK"] = datetime.now().astimezone().isoformat()
            Thread(target=update_latest_stable_release).start()

        Thread(target=check_database_state, args=(request.method, request.path)).start()

        DB.readonly = DATA.get("READONLY_MODE", False)

        if not request.path.startswith(("/check", "/loading", "/login", "/totp")) and DB.readonly:
            flask_flash("Database connection is in read-only mode : no modifications possible.", "error")

        if current_user.is_authenticated:
            passed = True

            if "ip" not in session:
                session["ip"] = request.remote_addr
            if "user_agent" not in session:
                session["user_agent"] = request.headers.get("User-Agent")

            # Case not login page, keep on 2FA before any other access
            if not session.get("totp_validated", False) and bool(current_user.totp_secret) and "/totp" not in request.path:
                if not request.path.endswith("/login"):
                    return redirect(url_for("totp.totp_page", next=request.form.get("next")))
                passed = False
            elif (app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private) and session["ip"] != request.remote_addr:
                logger.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session["user_agent"] != request.headers.get("User-Agent"):
                logger.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False
            elif "session_id" in session and session["session_id"] in DATA.get("REVOKED_SESSIONS", []):
                logger.warning(f"User {current_user.get_id()} tried to access a revoked session.")
                passed = False

            if not passed:
                return logout_page(), 403

    current_endpoint = request.path.split("/")[-1]
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp")):
        app.config["ENV"] = dict(current_endpoint=current_endpoint, script_nonce=app.config["SCRIPT_NONCE"], supported_languages=SUPPORTED_LANGUAGES)
    else:
        if not metadata:
            metadata = DB.get_metadata()

        changes_ongoing = any(
            v
            for k, v in metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        )

        if not changes_ongoing and DATA.get("PRO_LOADING"):
            DATA["PRO_LOADING"] = False

        if not request.path.startswith("/loading"):
            if not changes_ongoing and metadata["failover"]:
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
                flash("The last changes have been applied successfully.")
                DATA["CONFIG_CHANGED"] = False

        # Determine if this is a CORS or AJAX request
        fetch_mode = request.headers.get("Sec-Fetch-Mode")
        x_requested_with = request.headers.get("X-Requested-With")
        is_cors = fetch_mode == "cors" or (x_requested_with and x_requested_with.lower() == "xmlhttprequest")

        if not is_cors:
            seen = set()
            for f in DATA.get("TO_FLASH", []):
                content = f["content"]
                if content in seen:
                    continue
                seen.add(content)
                flash(content, f["type"], save=f.get("save", True))
            DATA["TO_FLASH"] = []

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

        if current_endpoint in COLUMNS_PREFERENCES_DEFAULTS:
            data["columns_preferences"] = DB.get_ui_user_columns_preferences(current_user.get_id(), current_endpoint)

        app.config["ENV"] = data

    for hook in app.config["BEFORE_REQUEST_HOOKS"]:
        try:
            resp = hook()
            if resp:
                return resp
        except Exception:
            logger.exception("Error in before_request hook")


def mark_user_access(user, session_id):
    if user and "write" not in user.list_permissions or DB.readonly:
        return

    ret = DB.mark_ui_user_access(session_id, datetime.now().astimezone())
    if ret:
        logger.error(f"Couldn't mark the user access: {ret}")
    logger.debug(f"Marked the user access for session {session_id}")


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # * Content-Security-Policy header to prevent XSS attacks
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

    if request.headers.get("X-Forwarded-Proto") == "https":
        if not request.path.startswith("/setup/loading"):
            response.headers["Content-Security-Policy"] += " upgrade-insecure-requests;"

        # * Strict-Transport-Security header to force HTTPS if accessed via a reverse proxy
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    # * X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # * X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # * Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # * Permissions-Policy header to prevent unwanted behavior
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), compute-pressure=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), fullscreen=(), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), local-fonts=(), magnetometer=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), publickey-credentials-create=(), publickey-credentials-get=(), screen-wake-lock=(), serial=(), speaker-selection=(), storage-access=(), usb=(), web-share=(), window-management=(), xr-spatial-tracking=(), interest-cohort=()"
    )

    for hook in app.config["AFTER_REQUEST_HOOKS"]:
        try:
            resp = hook(response)
            if resp:
                return resp
        except Exception:
            logger.exception("Error in after_request hook")

    return response


@app.teardown_request
def teardown_request(teardown):
    if (
        not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/", "/locales/"))
        and current_user.is_authenticated
        and "session_id" in session
    ):
        Thread(target=mark_user_access, args=(current_user, session["session_id"])).start()

    for hook in app.config["TEARDOWN_REQUEST_HOOKS"]:
        try:
            hook(teardown)
        except Exception:
            logger.exception("Error in teardown_request hook")


### * MISC ROUTES * ###


@app.route("/", strict_slashes=False, methods=["GET"])
def index():
    if DB.get_ui_user():
        if current_user.is_authenticated:  # type: ignore
            return redirect(url_for("home.home_page"))
        return redirect(url_for("login.login_page"), 301)
    return redirect(url_for("setup.setup_page"), 301)


@app.route("/loading", methods=["GET"])
@login_required
def loading():
    home_url = url_for("home.home_page")
    next_url = request.values.get("next", None) or home_url

    if not next_url.startswith(home_url.replace("/home", "/", 1).replace("//", "/")):
        return Response(status=400)

    return render_template("loading.html", message=request.values.get("message", "Loading..."), next=next_url)


@app.route("/check", methods=["GET"])
def check():
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


if getenv("ENABLE_HEALTHCHECK", "no").lower() == "yes":

    @app.route("/healthcheck", methods=["GET"])
    def healthcheck():
        """Simple healthcheck endpoint that returns 200 OK with basic status information"""
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().astimezone().isoformat(),
            "service": "bunkerweb-ui",
        }

        return Response(status=200, response=dumps(health_data), content_type="application/json")


@app.route("/check_reloading", methods=["GET"])
@login_required
def check_reloading():
    DATA.load_from_file()
    current_time = time()

    db_metadata = DB.get_metadata()
    if (
        not any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        )
        and DATA.get("LAST_RELOAD", 0) + 2 < current_time
    ):
        DATA["RELOADING"] = False

    if not DATA.get("RELOADING", False) or DATA.get("LAST_RELOAD", 0) + 60 < current_time:
        if DATA.get("RELOADING", False):
            logger.warning("Reloading took too long, forcing the state to be reloaded")
            flask_flash("Forced the status to be reloaded", "error")
            DATA["RELOADING"] = False

    return jsonify({"reloading": DATA.get("RELOADING", False)})


@app.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    if DB.readonly:
        return Response(status=423, response=dumps({"message": "Database is in read-only mode"}), content_type="application/json")
    elif request.form["theme"] not in ("dark", "light"):
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
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/set_language", methods=["POST"])
@login_required
def set_language():
    allowed_languages = {lang["code"] for lang in SUPPORTED_LANGUAGES}
    lang = request.form["language"].lower()
    if DB.readonly:
        return Response(status=423, response=dumps({"message": "Database is in read-only mode"}), content_type="application/json")
    elif lang not in allowed_languages:
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
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/set_columns_preferences", methods=["POST"])
@login_required
def set_columns_preferences():
    table_name = request.form.get("table_name")
    columns_preferences = request.form.get("columns_preferences", "{}")

    try:
        columns_preferences = loads(columns_preferences)
    except BaseException:
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    if (
        DB.readonly
        or table_name not in COLUMNS_PREFERENCES_DEFAULTS
        or any(column not in COLUMNS_PREFERENCES_DEFAULTS[table_name] for column in columns_preferences)
    ):
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    ret = DB.update_ui_user_columns_preferences(current_user.get_id(), table_name, columns_preferences)
    if ret:
        logger.error(f"Couldn't update the user {current_user.get_id()}'s columns preferences: {ret}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/clear_notifications", methods=["POST"])
@login_required
def clear_notifications():
    session["flash_messages"] = []
    session.modified = True
    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


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

for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)
