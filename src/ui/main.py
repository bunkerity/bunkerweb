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

from jinja2 import ChoiceLoader, FileSystemLoader


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from cachelib import FileSystemCache
from flask import Flask, Response, flash as flask_flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, LoginManager, login_required, logout_user
from flask_principal import ActionNeed, identity_loaded, Permission, Principal, RoleNeed, TypeNeed, UserNeed
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.routing.exceptions import BuildError

from app.models.reverse_proxied import ReverseProxied

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

from app.dependencies import BW_CONFIG, DATA, DB, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH, safe_reload_plugins
from app.models.models import AnonymousUser
from app.utils import (
    COLUMNS_PREFERENCES_DEFAULTS,
    LIB_DIR,
    LOGGER,
    flash,
    get_blacklisted_settings,
    get_filtered_settings,
    get_latest_stable_release,
    get_multiples,
    handle_stop,
    human_readable_number,
    stop,
)

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


class DynamicFlask(Flask):
    def create_global_jinja_loader(self):
        """
        Override Flask's default template loader creation so that
        blueprint template folders (especially plugins) take precedence
        over the application's global template folder.
        """
        LOGGER.debug("Creating global jinja loader with custom blueprint priority handling")
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
                    LOGGER.debug(f"Created FileSystemLoader for blueprint '{name}' with path: {template_path}")
                else:
                    LOGGER.debug(f"Using existing jinja_loader for blueprint '{name}'")
                # Priority: higher means we want it searched first.
                priority = getattr(bp, "plugin_priority", 0)
                LOGGER.debug(f"Blueprint '{name}' has plugin_priority: {priority}")
                blueprint_loaders.append((priority, loader))

        # Sort blueprint loaders descending by priority
        blueprint_loaders.sort(key=itemgetter(0), reverse=True)
        loaders_in_order = [ldr for (_prio, ldr) in blueprint_loaders]
        LOGGER.debug(f"Blueprint loaders sorted by priority: {[p for p, _ in blueprint_loaders]}")

        # Finally, add the app's own jinja_loader (which handles the global templates folder)
        # at the end. This ensures plugin templates overshadow global templates if names clash.
        if self.jinja_loader is not None:
            loaders_in_order.append(self.jinja_loader)
            LOGGER.debug("App's jinja_loader appended to the end of loaders list")

        final_loader = ChoiceLoader(loaders_in_order)
        LOGGER.debug("Global jinja loader created successfully")
        return final_loader

    def register_blueprint(self, blueprint, **options):
        # Check if a blueprint with this name is already registered.
        if blueprint.name in self.blueprints:
            existing_bp = self.blueprints[blueprint.name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(blueprint, "plugin_priority", 0)
            if new_priority > existing_priority:
                LOGGER.info(f"Overriding blueprint '{blueprint.name}': new priority {new_priority} over {existing_priority}")
                # Remove the existing blueprint.
                del self.blueprints[blueprint.name]
                # Also remove all URL rules associated with the existing blueprint.
                rules_to_remove = [rule for rule in list(self.url_map.iter_rules()) if rule.endpoint.startswith(blueprint.name + ".")]
                for rule in rules_to_remove:
                    self.url_map._rules.remove(rule)
                    self.url_map._rules_by_endpoint.pop(rule.endpoint, None)
            else:
                LOGGER.info(f"Skipping blueprint '{blueprint.name}' with priority {new_priority} " f"(existing priority {existing_priority})")
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

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    if not LIB_DIR.joinpath(".flask_secret").is_file():
        LOGGER.error("The .flask_secret file is missing, exiting ...")
        stop(1)
    FLASK_SECRET = LIB_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

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
    app.config["SESSION_ID_LENGTH"] = 64
    app.config["SESSION_CACHELIB"] = FileSystemCache(threshold=500, cache_dir=LIB_DIR.joinpath("ui_sessions_cache"))
    sess = Session()
    sess.init_app(app)

    principal = Principal()
    principal.init_app(app)

    admin_permission = Permission(TypeNeed("super_admin"))
    manage_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"))
    edit_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"))
    read_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"), ActionNeed("read"))

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
                LOGGER.debug(f"Couldn't build the URL for {endpoint}: {e}")
        return "#"

    # Declare functions for jinja2
    app.jinja_env.globals.update(
        get_multiples=get_multiples,
        get_filtered_settings=get_filtered_settings,
        get_blacklisted_settings=get_blacklisted_settings,
        get_plugins_settings=BW_CONFIG.get_plugins_settings,
        human_readable_number=human_readable_number,
        url_for=custom_url_for,
    )

    app.config.update({hook_info["key"]: [] for hook_info in HOOKS.values()})

    DATA.load_from_file()
    if "WORKERS" not in DATA:
        DATA["WORKERS"] = {}
    DATA["WORKERS"][getpid()] = {"refresh_context": False}
    DATA["FORCE_RELOAD_PLUGIN"] = True
    DB.checked_changes(["ui_plugins"], value=True)


@app.context_processor
def inject_variables():
    for hook in app.config["CONTEXT_PROCESSOR_HOOKS"]:
        resp = hook()
        if resp:
            app.config["ENV"] = {**app.config["ENV"], **resp}

    return app.config["ENV"]


@login_manager.user_loader
def load_user(username):
    ui_user = DB.get_ui_user(username=username)
    if not ui_user:
        LOGGER.warning(f"Couldn't get the user {username} from the database.")
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


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    identity.provides.add(UserNeed(current_user.get_id()))

    for role in current_user.list_roles:
        identity.provides.add(RoleNeed(role))

    for action in current_user.list_permissions:
        identity.provides.add(ActionNeed(action))

    if current_user.admin:
        identity.provides.add(TypeNeed("super_admin"))


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    LOGGER.debug(format_exc())
    LOGGER.error(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    session.clear()
    logout_user()
    flask_flash("Wrong CSRF token !", "error")
    if not current_user:
        return redirect(url_for("setup.setup_page")), 403
    return redirect(url_for("login.login_page")), 403


def update_latest_stable_release():
    DATA["LATEST_VERSION"] = get_latest_stable_release()


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
            LOGGER.info("The database is no longer read-only, defaulting to read-write mode")
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
    LOGGER.debug("Refreshing app context")
    DATA.load_from_file()

    # Reset all hooks before reloading
    for hook_info in HOOKS.values():
        app.config[hook_info["key"]] = []

    # Track active plugin paths to detect removed plugins
    active_plugin_paths = set()

    external_hooks = EXTERNAL_PLUGINS_PATH.rglob("*/ui/hooks.py")
    pro_hooks = PRO_PLUGINS_PATH.rglob("*/ui/hooks.py")

    for hook_file in chain(external_hooks, pro_hooks):
        if hook_file.is_file():
            try:
                active_plugin_paths.add(hook_file.parent.parent.parent)
                # Create a unique module name based on the hook file path
                module_name = f"hooks_{hook_file.parent.name}_{hook_file.stem}"
                spec = spec_from_file_location(module_name, hook_file)
                if spec is None or spec.loader is None:
                    LOGGER.warning(f"Could not load spec for hook file: {hook_file}")
                    continue
                hook_module = module_from_spec(spec)
                spec.loader.exec_module(hook_module)
                for attr_name in dir(hook_module):
                    for hook_type, hook_info in HOOKS.items():
                        if attr_name.startswith(hook_type):
                            hook_function = getattr(hook_module, attr_name)
                            if callable(hook_function):
                                app.config.setdefault(hook_info["key"], []).append(hook_function)
                                LOGGER.info(f"{hook_info['log_prefix']} hook '{attr_name}' from {hook_file} loaded successfully.")
                            else:
                                LOGGER.warning(f"Attribute '{attr_name}' in {hook_file} is not callable and was skipped.")
                            break
            except Exception as exc:
                LOGGER.error(f"Error loading before-request hooks from {hook_file}: {exc}")

    # Preserve the original (built-in) blueprints once.
    if not hasattr(app, "original_blueprints"):
        # Use the BLUEPRINTS constant imported/defined earlier.
        app.original_blueprints = {bp.name: bp for bp in BLUEPRINTS}

    # Temporary dictionary to collect plugin blueprints keyed by name.
    blueprint_registry = {}
    # Set to record blueprint names found in plugin directories.
    plugin_blueprints = set()

    # --- LOAD PLUGIN BLUEPRINTS ---
    for bp_dir in chain(PRO_PLUGINS_PATH.rglob("*/ui/blueprints"), EXTERNAL_PLUGINS_PATH.rglob("*/ui/blueprints")):
        if bp_dir.is_dir():
            # Optionally, track plugin paths
            active_plugin_paths.add(bp_dir.parent.parent.parent)
            for bp_file in bp_dir.glob("*.py"):
                try:
                    # Add blueprint directory to sys.path BEFORE loading the module
                    blueprint_dir = str(bp_dir)
                    if blueprint_dir not in sys_path:
                        LOGGER.debug(f"Adding {blueprint_dir} to sys.path before loading blueprint from {bp_file}")
                        sys_path.append(blueprint_dir)

                    # Create a unique module name.
                    module_name = f"blueprint_{bp_dir.parent.name}_{bp_file.stem}"
                    spec = spec_from_file_location(module_name, bp_file)
                    if spec is None or spec.loader is None:
                        LOGGER.warning(f"Could not load spec for blueprint file: {bp_file}")
                        continue
                    bp_module = module_from_spec(spec)
                    spec.loader.exec_module(bp_module)
                    # Assume the blueprint variable is named the same as the file stem.
                    blueprint_var_name = bp_file.stem
                    bp = getattr(bp_module, blueprint_var_name, None)
                    if bp:
                        plugin_blueprints.add(bp.name)
                        # Set plugin priority: 2 for PRO, 1 for External.
                        new_priority = 2 if PRO_PLUGINS_PATH in bp_file.parents else 1
                        bp.plugin_priority = new_priority

                        # Set the import path to the blueprint directory
                        bp.import_path = blueprint_dir
                        LOGGER.debug(f"Set import_path to {bp.import_path} for blueprint {bp.name}")

                        # Ensure the blueprint's template_folder is an absolute path.
                        if bp.template_folder:
                            bp.template_folder = abspath(bp.template_folder)

                        # Track this blueprint's sys.path entry
                        if not hasattr(app, "plugin_sys_paths"):
                            app.plugin_sys_paths = {}  # Map blueprint names to their sys.path entries
                        app.plugin_sys_paths[bp.name] = blueprint_dir

                        # In the registry, only keep the highest-priority blueprint for a given name.
                        if bp.name in blueprint_registry:
                            existing_bp = blueprint_registry[bp.name]
                            existing_priority = getattr(existing_bp, "plugin_priority", 0)
                            if new_priority > existing_priority and bp != existing_bp:
                                blueprint_registry[bp.name] = bp
                                LOGGER.info(f"Overriding blueprint '{bp.name}' with higher priority from {bp_file}.")
                            else:
                                LOGGER.info(f"Skipping blueprint '{bp.name}' from {bp_file} due to lower priority or duplicate.")
                        else:
                            blueprint_registry[bp.name] = bp
                            LOGGER.info(f"Blueprint '{bp.name}' from {bp_file} loaded successfully.")
                    else:
                        LOGGER.warning(f"No blueprint variable named '{bp_file.stem}' found in {bp_file}.")
                except Exception as exc:
                    LOGGER.error(f"Error loading blueprint from {bp_file}: {exc}")

    # Track plugin directories that have been added to sys.path
    if not hasattr(app, "plugin_sys_paths"):
        app.plugin_sys_paths = {}  # Map blueprint names to their sys.path entries

    def remove_blueprint(bp_name):
        """Helper to completely remove a blueprint and its associated rules and endpoints."""
        app.blueprints.pop(bp_name, None)

        # Remove blueprint directory from sys.path if it was added
        if bp_name in app.plugin_sys_paths and app.plugin_sys_paths[bp_name] in sys_path:
            LOGGER.debug(f"Removing {app.plugin_sys_paths[bp_name]} from sys.path for blueprint {bp_name}")
            sys_path.remove(app.plugin_sys_paths[bp_name])
            del app.plugin_sys_paths[bp_name]

        for rule in list(app.url_map.iter_rules()):
            if rule.endpoint.startswith(bp_name + ".") and str(rule) == f"/{bp_name}" and bp_name in app.config["EXTRA_PAGES"]:
                app.config["EXTRA_PAGES"].remove(bp_name)

            if rule.endpoint.startswith(bp_name + "."):
                try:
                    LOGGER.debug(f"Removing rule: {rule}")
                    app.url_map._rules.remove(rule)
                except ValueError:
                    LOGGER.warning(f"Rule already removed: {rule}")
                app.url_map._rules_by_endpoint.pop(rule.endpoint, None)

        for endpoint in [ep for ep in list(app.view_functions.keys()) if ep.startswith(bp_name + ".")]:
            LOGGER.debug(f"Removing endpoint: {endpoint}")
            app.view_functions.pop(endpoint, None)

        LOGGER.debug(f"Blueprint '{bp_name}' was completely removed.")

    # --- REMOVE BLUEPRINTS FOR DELETED PLUGINS ---
    for bp_name in app.blueprints.copy():
        if bp_name not in plugin_blueprints:
            remove_blueprint(bp_name)

    for bp_name in app.original_blueprints:
        if bp_name not in app.blueprints:
            # Re-register default blueprint if available.
            default_bp = app.original_blueprints[bp_name]
            app.register_blueprint(default_bp)

    # --- REGISTER OR OVERRIDE PLUGIN BLUEPRINTS ---
    for bp_name, bp in blueprint_registry.items():
        new_priority = getattr(bp, "plugin_priority", 0)
        if bp_name in app.blueprints:
            existing_bp = app.blueprints[bp_name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            LOGGER.info(f"Existing blueprint '{bp_name}' priority: {existing_priority}; new blueprint priority: {new_priority}")
            if new_priority > existing_priority:
                remove_blueprint(bp_name)
                app.register_blueprint(bp)
                LOGGER.info(f"Replaced blueprint '{bp_name}' with new priority {new_priority} (overriding {existing_priority}).")
            else:
                LOGGER.info(
                    f"Skipping registration for blueprint '{bp_name}' from plugins " f"(new priority {new_priority} <= existing priority {existing_priority})."
                )
        else:
            app.register_blueprint(bp)
            LOGGER.info(f"Registered new blueprint '{bp_name}' with priority {new_priority}.")

        for rule in list(app.url_map.iter_rules()):
            if rule.endpoint.startswith(bp_name + ".") and str(rule) == f"/{bp_name}" and bp_name not in app.config["EXTRA_PAGES"]:
                app.config["EXTRA_PAGES"].append(bp_name)

        # Clear Jinja2 cache to force reloading templates.
        app.jinja_env.cache = {}
        app.register_blueprint(bp)
        LOGGER.info(f"Registered blueprint '{bp_name}' with priority {new_priority}")

    app.jinja_env.loader = app.create_global_jinja_loader()

    worker_pid = getpid()
    if worker_pid not in DATA.get("WORKERS", {}):
        DATA["WORKERS"][worker_pid] = {}
    DATA["WORKERS"][getpid()]["refresh_context"] = False
    DATA.write_to_file()


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

    if not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/")):
        metadata = DB.get_metadata()

        if DATA.get("FORCE_RELOAD_PLUGIN", False) or (
            not DATA.get("RELOADING", False) and metadata.get("reload_ui_plugins", False) and not DATA.get("IS_RELOADING_PLUGINS", False)
        ):
            safe_reload_plugins()
            refresh_app_context()
        elif not DATA.get("RELOADING", False) and DATA.get("WORKERS", {}).get(getpid(), {}).get("refresh_context", False):
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
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session["user_agent"] != request.headers.get("User-Agent"):
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False
            elif "session_id" in session and session["session_id"] in DATA.get("REVOKED_SESSIONS", []):
                LOGGER.warning(f"User {current_user.get_id()} tried to access a revoked session.")
                passed = False

            if not passed:
                return logout_page()

    current_endpoint = request.path.split("/")[-1]
    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp")):
        app.config["ENV"] = dict(current_endpoint=current_endpoint, script_nonce=app.config["SCRIPT_NONCE"])
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
                    "The last changes could not be applied because it creates a configuration error on NGINX, please check BunkerWeb's logs for more information. The configuration fell back to the last working one.",
                    "error",
                )
            elif not changes_ongoing and not metadata["failover"] and DATA.get("CONFIG_CHANGED", False):
                flash("The last changes have been applied successfully.", "success")
                DATA["CONFIG_CHANGED"] = False

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
            is_readonly=DATA.get("READONLY_MODE", False) or "write" not in current_user.list_permissions,
            user_readonly="write" not in current_user.list_permissions,
            theme=current_user.theme if current_user.is_authenticated else "dark",
            columns_preferences_defaults=COLUMNS_PREFERENCES_DEFAULTS,
            extra_pages=app.config["EXTRA_PAGES"],
        )

        if current_endpoint in COLUMNS_PREFERENCES_DEFAULTS:
            data["columns_preferences"] = DB.get_ui_user_columns_preferences(current_user.get_id(), current_endpoint)

        app.config["ENV"] = data

    for hook in app.config["BEFORE_REQUEST_HOOKS"]:
        resp = hook()
        if resp:
            return resp


def mark_user_access(user, session_id):
    if user and "write" not in user.list_permissions or DB.readonly:
        return

    ret = DB.mark_ui_user_access(session_id, datetime.now().astimezone())
    if ret:
        LOGGER.error(f"Couldn't mark the user access: {ret}")
    LOGGER.debug(f"Marked the user access for session {session_id}")


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
        resp = hook(response)
        if resp:
            return resp

    return response


@app.teardown_request
def teardown_request(_):
    if not request.path.startswith(("/css/", "/img/", "/js/", "/json/", "/fonts/", "/libs/")) and current_user.is_authenticated and "session_id" in session:
        Thread(target=mark_user_access, args=(current_user, session["session_id"])).start()

    for hook in app.config["TEARDOWN_REQUEST_HOOKS"]:
        hook()


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
            LOGGER.warning("Reloading took too long, forcing the state to be reloaded")
            flask_flash("Forced the status to be reloaded", "error")
            DATA["RELOADING"] = False

    seen = set()
    for f in DATA.get("TO_FLASH", []):
        content = f["content"]
        if content in seen:
            continue
        seen.add(content)
        flash(content, f["type"], save=f.get("save", True))
    DATA["TO_FLASH"] = []

    return jsonify({"reloading": DATA.get("RELOADING", False)})


@app.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    if "write" not in current_user.list_permissions:
        return Response(
            status=403, response=dumps({"message": "You don't have the required permissions to change the theme."}), content_type="application/json"
        )
    elif DB.readonly:
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
    }

    ret = DB.update_ui_user(**user_data, old_username=current_user.get_id())
    if ret:
        LOGGER.error(f"Couldn't update the user {current_user.get_id()}: {ret}")
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
        "write" not in current_user.list_permissions
        or DB.readonly
        or table_name not in COLUMNS_PREFERENCES_DEFAULTS
        or any(column not in COLUMNS_PREFERENCES_DEFAULTS[table_name] for column in columns_preferences)
    ):
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    ret = DB.update_ui_user_columns_preferences(current_user.get_id(), table_name, columns_preferences)
    if ret:
        LOGGER.error(f"Couldn't update the user {current_user.get_id()}'s columns preferences: {ret}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)
