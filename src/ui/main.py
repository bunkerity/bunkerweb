#!/usr/bin/env python3
from contextlib import suppress
from atexit import register
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from ipaddress import ip_address
from itertools import chain
from json import dumps, loads
from operator import itemgetter
from os import getenv, getpid, sep
from os.path import abspath, join
from re import compile as re_compile, fullmatch, split as resplit
from secrets import token_hex, token_urlsafe
from signal import SIGINT, signal, SIGTERM
from sys import path as sys_path, modules as sys_modules
from threading import Lock
from time import time
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from app.models.plugin_activation import is_plugin_active_for_service
from app.models.safe_session_cache import SafeFileSystemCache
from flask import Blueprint, Flask, Response, flash as flask_flash, g, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, LoginManager, login_required, logout_user
from flask_session import Session
from flask_wtf.csrf import CSRFProtect, CSRFError
from jinja2 import ChoiceLoader, FileSystemLoader
from werkzeug.routing.exceptions import BuildError

from common_utils import get_redis_client as get_common_redis_client, is_newer_version_available  # type: ignore
from resource_group_resolver import kind_for_key as resource_kind_for_setting  # type: ignore

from app.models.biscuit import BiscuitMiddleware
from app.models.plugin_catalog import catalog_enabled, fetch_catalog
from app.models.reverse_proxied import ReverseProxied

from app.dependencies import API_CLIENT, BW_CONFIG, DATA, CORE_PLUGINS_PATH, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH, safe_reload_plugins
from app.api_client import ApiClientError, ApiUnavailableError
from app.models.models import AnonymousUser, UiUsers
from app.utils import (
    BISCUIT_PUBLIC_KEY_FILE,
    COLUMNS_PREFERENCES_DEFAULTS,
    LIB_DIR,
    LOGGER,
    SETTINGS_HUNGRY_PATH_PREFIXES,
    billable_service_count,
    is_static_path,
    _sanitize_internal_next,
    flash,
    get_blacklisted_settings,
    get_filtered_settings,
    get_github_stars,
    get_latest_stable_release,
    can_delete_service,
    get_multiples,
    handle_stop,
    human_readable_number,
    is_editable_method,
    is_plugin_active,
    is_session_revoked,
    is_ui_api_method,
    stop,
    restart_workers,
)
from app.i18n import browser_catalog, init_i18n
from app.lang_config import SUPPORTED_LANGUAGES

from app.routes.about import about
from app.routes.bans import bans
from app.routes.cache import cache
from app.routes.certificates import certificates
from app.routes.threatmap import threatmap
from app.routes.timings import timings
from app.routes.web_cache import web_cache
from app.routes.configs import configs
from app.routes.global_settings import global_settings
from app.routes.home import home
from app.routes.instances import instances
from app.routes.jobs import jobs
from app.routes.login import login
from app.routes.logout import logout, logout_page
from app.routes.logs import logs
from app.routes.onboarding import onboarding
from app.routes.whats_new import pending_releases, whats_new
from app import perf
from base_api_client import REQUEST_ID  # type: ignore
from app.models.onboarding import PREFERENCE_KEY as ONBOARDING_PREFERENCE_KEY
from app.routes.preferences import (
    DISMISSED_NOTICES_KEY,
    HIDDEN_CARDS_KEY,
    SESSION_KEYS as PREFERENCE_SESSION_KEYS,
    THEME_MODE_KEY,
    dismissed_notices as load_dismissed_notices,
    hidden_home_cards as load_hidden_home_cards,
    preferences,
    theme_mode as load_theme_mode,
)
from app.routes.plugins import plugins
from app.routes.pro import pro
from app.routes.profile import profile
from app.routes.redirects import redirects
from app.routes.reports import reports
from app.routes.resource_groups import resource_groups
from app.routes.services import services
from app.routes.setup import setup
from app.routes.totp import totp
from app.routes.support import support
from app.routes.templates import templates as templates_bp
from app.routes.upstreams import upstreams
from app.routes.workflows import workflows

BLUEPRINTS = (
    about,
    services,
    profile,
    jobs,
    reports,
    resource_groups,
    totp,
    home,
    logout,
    instances,
    plugins,
    global_settings,
    pro,
    cache,
    certificates,
    redirects,
    upstreams,
    workflows,
    web_cache,
    timings,
    threatmap,
    whats_new,
    logs,
    login,
    configs,
    templates_bp,
    bans,
    setup,
    support,
    onboarding,
    preferences,
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
    # New: per-request JavaScript providers from plugins
    # A hook function named `scripts` in a plugin's ui/hooks.py can return:
    # { "src": ["/path.js", {"src": "/mod.js", "type": "module"}], "inline": "console.log('hi')" }
    # These are aggregated and exposed as `extra_scripts` and `custom_js` in templates.
    "scripts": {
        "key": "SCRIPTS_HOOKS",
        "log_prefix": "Scripts",
    },
    # New: per-request CSS providers from plugins
    # A hook function named `styles` in a plugin's ui/hooks.py can return:
    # { "href": ["/path.css", {"href": "/print.css", "media": "print"}], "inline": ".x{display:none}" }
    # These are aggregated and exposed as `extra_styles` and `custom_css` in templates.
    "styles": {
        "key": "STYLES_HOOKS",
        "log_prefix": "Styles",
    },
}

# Flask serves app/static/* at the URL root (static_url_path="/"); before_request short-circuits these.
# Shared thread pool executors for background tasks to prevent thread spawning on every request
_periodic_tasks_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bw-ui-periodic")
_user_access_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bw-ui-access")
_config_tasks_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-config")

_cookie_config_lock = Lock()
_cookie_config_detected = False

_SESSION_CLEANUP_INTERVAL_SECONDS = 3600.0
_session_cleanup_last_run = 0.0

_restart_workers_lock = Lock()
_restart_workers_future = None
_restart_workers_next_allowed = 0.0
RESTART_WORKERS_MIN_INTERVAL_SECONDS = 10.0


def _shutdown_executors():
    """Shutdown all thread pool executors on application exit."""
    _periodic_tasks_executor.shutdown(wait=False)
    _user_access_executor.shutdown(wait=False)
    _config_tasks_executor.shutdown(wait=False)


register(_shutdown_executors)


SIZE_MULTIPLIERS = {
    "": 1,
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "ki": 1024,
    "kib": 1024,
    "m": 1024**2,
    "mb": 1024**2,
    "mi": 1024**2,
    "mib": 1024**2,
    "g": 1024**3,
    "gb": 1024**3,
    "gi": 1024**3,
    "gib": 1024**3,
    "t": 1024**4,
    "tb": 1024**4,
    "ti": 1024**4,
    "tib": 1024**4,
}


def parse_size_to_bytes(size: str) -> int:
    """
    Parse a size string to bytes.

    Examples:
    - "52428800"
    - "50M", "50MB", "50 MiB"
    - "1G", "1GiB"
    """
    match = fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", size)
    if not match:
        raise ValueError("invalid format")

    value = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = SIZE_MULTIPLIERS.get(unit)
    if multiplier is None:
        raise ValueError("invalid unit")

    bytes_value = int(value * multiplier)
    if bytes_value <= 0:
        raise ValueError("non-positive size")
    return bytes_value


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
                LOGGER.debug(f"Overriding blueprint '{blueprint.name}': new priority {new_priority} over {existing_priority}")
                # Remove the existing blueprint.
                del self.blueprints[blueprint.name]
                # Also remove all URL rules associated with the existing blueprint.
                rules_to_remove = [rule for rule in list(self.url_map.iter_rules()) if rule.endpoint.startswith(blueprint.name + ".")]
                for rule in rules_to_remove:
                    self.url_map._rules.remove(rule)
                    self.url_map._rules_by_endpoint.pop(rule.endpoint, None)
            else:
                LOGGER.debug(f"Skipping blueprint '{blueprint.name}' with priority {new_priority} " f"(existing priority {existing_priority})")
                return  # Do not register a lower- or equal-priority blueprint.

        # Allow registration even after first request by temporarily resetting the flag.
        original_got_first = self._got_first_request
        self._got_first_request = False
        try:
            result = super().register_blueprint(blueprint, **options)
        finally:
            self._got_first_request = original_got_first
        return result


def refresh_app_context():
    """Refresh Flask app context by loading hooks and blueprints from plugins."""
    worker_pid = str(getpid())
    LOGGER.debug(f"Worker {worker_pid} refreshing context")
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

    # Find all python files in ui directories (sorted for deterministic load order)
    core_ui_py_files = sorted(CORE_PLUGINS_PATH.glob("*/ui/hooks.py"))
    external_ui_py_files = sorted(EXTERNAL_PLUGINS_PATH.glob("*/ui/hooks.py"))
    pro_ui_py_files = sorted(PRO_PLUGINS_PATH.glob("*/ui/hooks.py"))
    core_bp_dirs = sorted(CORE_PLUGINS_PATH.glob("*/ui/blueprints"))
    external_bp_dirs = sorted(EXTERNAL_PLUGINS_PATH.glob("*/ui/blueprints"))
    pro_bp_dirs = sorted(PRO_PLUGINS_PATH.glob("*/ui/blueprints"))

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
        # Namespace the module name with the plugin directory to avoid collisions
        plugin_root = py_file.parents[1] if len(py_file.parents) >= 2 else py_file.parent
        module_name = f"bw_ui_hooks_{plugin_root.name}_{py_file.stem}"
        active_hook_modules.add(module_name)
        hook_dir = str(py_file.parent)

        try:
            proxy_file = py_file.parent / "hooks_proxy.py"
            target_file = proxy_file if proxy_file.exists() else py_file

            # Prepend plugin hook dir to sys.path for correct import resolution
            added_to_path = False
            if hook_dir not in sys_path:
                sys_path.insert(0, hook_dir)
                added_to_path = True
                app.hook_sys_paths[module_name] = hook_dir

            # Ensure we don't keep stale modules with the same dynamic name around
            if module_name in sys_modules:
                del sys_modules[module_name]

            # Also isolate a preloaded top-level "hooks" to avoid proxy importing the wrong one
            prev_hooks_mod = sys_modules.pop("hooks", None)

            spec = spec_from_file_location(module_name, target_file)
            if not spec or not spec.loader:
                LOGGER.warning(f"Could not load spec for file: {target_file}")
                # Restore any prior 'hooks' module
                if prev_hooks_mod is not None:
                    sys_modules["hooks"] = prev_hooks_mod
                continue

            hook_module = module_from_spec(spec)
            try:
                spec.loader.exec_module(hook_module)
            except Exception as exec_err:
                LOGGER.warning(f"Error executing module {target_file}: {exec_err}")
                # Restore any prior 'hooks' module
                if prev_hooks_mod is not None:
                    sys_modules["hooks"] = prev_hooks_mod
                else:
                    # Ensure we don't keep a plugin-specific 'hooks' leaked
                    sys_modules.pop("hooks", None)
                continue

            # Restore any prior 'hooks' module (avoid leaking current plugin 'hooks' globally)
            if prev_hooks_mod is not None:
                sys_modules["hooks"] = prev_hooks_mod
            else:
                sys_modules.pop("hooks", None)

            for hook_type, hook_info in HOOKS.items():
                if hasattr(hook_module, hook_type) and callable(getattr(hook_module, hook_type)):
                    hook_function = getattr(hook_module, hook_type)
                    app.config.setdefault(hook_info["key"], []).append(hook_function)
                    LOGGER.debug(f"{hook_info['log_prefix']} hook '{hook_type}' from {py_file} loaded")

            # Remove the path we added
            if added_to_path and hook_dir in sys_path:
                sys_path.remove(hook_dir)
                app.hook_sys_paths.pop(module_name, None)
        except Exception as exc:
            LOGGER.error(f"Error loading potential hooks from {py_file}: {exc}")
            # Best-effort cleanup of 'hooks'
            with suppress(Exception):
                if "hooks" in sys_modules:
                    del sys_modules["hooks"]

    # --- CLEAN UP OBSOLETE HOOK PATHS ---
    for module_name, hook_dir in list(app.hook_sys_paths.items()):
        if module_name not in active_hook_modules and hook_dir in sys_path:
            sys_path.remove(hook_dir)
            del app.hook_sys_paths[module_name]
            LOGGER.debug(f"Removed {hook_dir} from sys.path for obsolete hook {module_name}")

    # Dedupe all hook lists by (module, qualname) to avoid duplicates across refreshes
    for hook_info in HOOKS.values():
        key = hook_info["key"]
        dedup, seen = [], set()
        for fn in app.config.get(key, []):
            ident = (getattr(fn, "__module__", ""), getattr(fn, "__qualname__", getattr(fn, "__name__", "")))
            if ident in seen:
                continue
            seen.add(ident)
            dedup.append(fn)
        app.config[key] = dedup

    # --- LOAD BLUEPRINTS ---
    base_pro = str(PRO_PLUGINS_PATH.resolve())
    base_ext = str(EXTERNAL_PLUGINS_PATH.resolve())
    # base_core not needed explicitly for detection, default priority is 0

    for bp_dir in chain(pro_bp_dirs, external_bp_dirs, core_bp_dirs):
        if not bp_dir.is_dir():
            continue

        active_plugin_paths.add(bp_dir.parent.parent.parent)
        blueprint_dir = str(bp_dir)

        # Compute priority based on directory location: pro (2) > external (1) > core (0)
        dir_str = str(bp_dir.resolve())
        priority = 2 if dir_str.startswith(base_pro) else (1 if dir_str.startswith(base_ext) else 0)

        # Prepend for correct import precedence during this load
        added_to_path = False
        if blueprint_dir not in sys_path:
            sys_path.insert(0, blueprint_dir)
            added_to_path = True

        for bp_file in bp_dir.glob("*.py"):
            if bp_file.name.endswith("_proxy.py"):
                continue

            try:
                proxy_file = bp_file.parent / f"{bp_file.stem}_proxy.py"
                # Namespace module name with plugin directory to avoid collisions
                plugin_root = bp_dir.parents[1] if len(bp_dir.parents) >= 2 else bp_dir.parent
                module_name = f"bw_ui_blueprint_{plugin_root.name}_{bp_file.stem}"
                target_file = proxy_file if proxy_file.exists() else bp_file

                # Clear stale dynamic module if present
                if module_name in sys_modules:
                    del sys_modules[module_name]

                spec = spec_from_file_location(module_name, target_file)
                if not spec or not spec.loader:
                    continue

                bp_module = module_from_spec(spec)
                spec.loader.exec_module(bp_module)

                bp_name = bp_file.stem
                if hasattr(bp_module, bp_name):
                    bp = getattr(bp_module, bp_name)
                    if isinstance(bp, Blueprint) or (
                        hasattr(bp, "name")
                        and hasattr(bp, "route")
                        and callable(getattr(bp, "route"))
                        and hasattr(bp, "register")
                        and callable(getattr(bp, "register"))
                    ):
                        plugin_blueprints.add(bp_name)

                        bp.plugin_priority = priority
                        bp.import_path = blueprint_dir
                        app.plugin_sys_paths[bp_name] = blueprint_dir

                        if bp.template_folder:
                            bp.template_folder = abspath(bp.template_folder)

                        if bp_name not in blueprint_registry or bp.plugin_priority > getattr(blueprint_registry[bp_name], "plugin_priority", 0):
                            blueprint_registry[bp_name] = bp
                            LOGGER.debug(f"Blueprint '{bp_name}' from {bp_file} registered with priority {bp.plugin_priority}")
                    else:
                        LOGGER.warning(f"Object '{bp_name}' in {bp_file} is not a valid Blueprint")
                else:
                    LOGGER.debug(f"No blueprint named '{bp_name}' found in {bp_file}")
            except Exception as exc:
                LOGGER.error(f"Error loading blueprint from {bp_file}: {exc}")

        # Remove the path we added
        if added_to_path and blueprint_dir in sys_path:
            sys_path.remove(blueprint_dir)

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

            LOGGER.debug(f"Blueprint '{bp_name}' was completely removed")

    # Restore original blueprints if missing
    for bp_name, bp in app.original_blueprints.items():
        if bp_name not in app.blueprints:
            app.register_blueprint(bp)
            LOGGER.debug(f"Re-registered original blueprint '{bp_name}'")

    # Register new and updated plugin blueprints
    for bp_name, bp in blueprint_registry.items():
        # Check if we should replace existing blueprint
        if bp_name in app.blueprints:
            existing_bp = app.blueprints[bp_name]
            existing_priority = getattr(existing_bp, "plugin_priority", 0)
            new_priority = getattr(bp, "plugin_priority", 0)

            if new_priority <= existing_priority:
                LOGGER.debug(f"Skipping registration for '{bp_name}' (priority {new_priority} <= {existing_priority})")
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
        LOGGER.debug(f"Registered blueprint '{bp_name}' with priority {getattr(bp, 'plugin_priority', 0)}")

        # Add to extra pages if it has a root route
        for rule in app.url_map.iter_rules():
            if rule.endpoint.startswith(f"{bp_name}.") and str(rule) == f"/{bp_name}" and bp_name not in app.config["EXTRA_PAGES"]:
                app.config["EXTRA_PAGES"].append(bp_name)
                break

    # Reset Jinja2 environment to apply template changes
    app.jinja_env.cache = {}
    app.jinja_env.loader = app.create_global_jinja_loader()

    # Remove other legacy flags
    if "NEEDS_CONTEXT_REFRESH" in DATA:
        del DATA["NEEDS_CONTEXT_REFRESH"]

    LOGGER.debug(f"Worker {worker_pid} completed context refresh")


# Flask app
app = DynamicFlask(__name__, static_url_path="/", static_folder="app/static", template_folder="app/templates")
app.logger = LOGGER

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)

    if not LIB_DIR.joinpath(".flask_secret").is_file():
        LOGGER.error("The .flask_secret file is missing, exiting ...")
        stop(1)
    FLASK_SECRET = LIB_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

    app.config["BISCUIT_PUBLIC_KEY_PATH"] = BISCUIT_PUBLIC_KEY_FILE.as_posix()

    # Server-side translation. Templates that have been converted render already translated;
    # the rest still carry `data-i18n` and are handled by i18next in the browser. See app/i18n.py.
    init_i18n(app)

    app.config["CHECK_PRIVATE_IP"] = getenv("CHECK_PRIVATE_IP", "yes").lower() == "yes"
    app.config["SECRET_KEY"] = FLASK_SECRET

    # Host header allowlist (defense-in-depth). Space/comma separated list of allowed
    # Host values (wildcards like "*.example.com" supported). Empty = disabled/permissive.
    _raw_allowed_hosts = getenv("UI_ALLOWED_HOSTS", "").strip()
    app.config["ALLOWED_HOSTS"] = [h for h in resplit(r"[\s,]+", _raw_allowed_hosts) if h] if _raw_allowed_hosts else []
    if app.config["ALLOWED_HOSTS"]:
        LOGGER.info(f"UI Host header allowlist enabled: {app.config['ALLOWED_HOSTS']}")

    # WebAuthn Relying Party identity. The RP ID is part of the security boundary: credentials are
    # cryptographically bound to it, so it must be a stable public domain and it can never be
    # derived from the (attacker-controllable) Host header. Resolution order:
    #   1. UI_WEBAUTHN_RP_ID, when the operator wants to be explicit;
    #   2. the sole entry of UI_ALLOWED_HOSTS, when there is exactly one and it is not a wildcard;
    #   3. nothing -> the whole passkey feature stays off.
    app.config["WEBAUTHN_RP_NAME"] = "BunkerWeb UI"
    _webauthn_rp_id = getenv("UI_WEBAUTHN_RP_ID", "").strip().lower() or None
    if not _webauthn_rp_id and len(app.config["ALLOWED_HOSTS"]) == 1 and not app.config["ALLOWED_HOSTS"][0].startswith("*."):
        # Strip any :port -- the RP ID is a bare domain, never a URL or an authority.
        _webauthn_rp_id = app.config["ALLOWED_HOSTS"][0].strip().lower().rsplit(":", 1)[0] or None
    app.config["WEBAUTHN_RP_ID"] = _webauthn_rp_id

    _raw_webauthn_origins = getenv("UI_WEBAUTHN_ORIGINS", "").strip()
    if _raw_webauthn_origins:
        app.config["WEBAUTHN_ORIGINS"] = [o.rstrip("/") for o in resplit(r"[\s,]+", _raw_webauthn_origins) if o]
    elif _webauthn_rp_id:
        app.config["WEBAUTHN_ORIGINS"] = [f"https://{_webauthn_rp_id}"]
        if _webauthn_rp_id == "localhost":
            # localhost is the only origin the spec exempts from HTTPS, which is what makes the dev
            # compose stack (http://localhost:7000) testable without a certificate.
            app.config["WEBAUTHN_ORIGINS"].append(f"http://localhost:{getenv('UI_LISTEN_PORT', getenv('LISTEN_PORT', '7000'))}")
    else:
        app.config["WEBAUTHN_ORIGINS"] = []

    if app.config["WEBAUTHN_RP_ID"]:
        LOGGER.info(f"WebAuthn enabled (RP ID: {app.config['WEBAUTHN_RP_ID']}, origins: {app.config['WEBAUTHN_ORIGINS']})")
    else:
        LOGGER.info("WebAuthn disabled: set UI_WEBAUTHN_RP_ID, or a single non-wildcard UI_ALLOWED_HOSTS entry, to enable passkeys")

    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Secure by default — auto-detection in before_request may downgrade if no proxy detected
    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
    app.config["SESSION_COOKIE_SECURE"] = True

    # The Flask-Login remember cookie is disabled. It carried only the username, HMAC'd with a
    # static secret, for 365 days, touched no server-side state, and so outlived logout, password
    # change and session revocation. "Remember me" is now session.permanent (login.py), bounded by
    # SESSION_LIFETIME_HOURS / SESSION_ABSOLUTE_HOURS and revocable like any other session.
    # Pointing REMEMBER_COOKIE_NAME at a name no browser will ever send keeps has_cookie in
    # flask_login's _load_user permanently False, so a legacy token already sitting in a browser is
    # dead on the first request after upgrade rather than getting one free authenticated request.
    # The name deliberately has no __Host- prefix: strong session protection can still emit a
    # deletion header for it, which is inert unprefixed but would be rejected outright by the UA
    # if prefixed.
    app.config["REMEMBER_COOKIE_NAME"] = "bw_ui_remember_disabled"

    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    default_max_content_length = 50 * 1024 * 1024  # 50 MB
    raw_max_content_length = getenv("UI_MAX_CONTENT_LENGTH", getenv("MAX_CONTENT_LENGTH", str(default_max_content_length)))
    try:
        max_content_length = parse_size_to_bytes(raw_max_content_length)
    except ValueError:
        max_content_length = default_max_content_length
        LOGGER.warning(f"Invalid MAX_CONTENT_LENGTH value ({raw_max_content_length}), defaulting to {default_max_content_length} bytes (50 MB)")
    app.config["MAX_CONTENT_LENGTH"] = max_content_length

    # Session management
    try:
        session_lifetime_hours = float(getenv("SESSION_LIFETIME_HOURS", "12"))
    except ValueError:
        session_lifetime_hours = 12.0
        LOGGER.warning("Invalid SESSION_LIFETIME_HOURS, defaulting to 12h")

    try:
        session_absolute_hours = float(getenv("SESSION_ABSOLUTE_HOURS", "168"))
    except ValueError:
        session_absolute_hours = 168.0
        LOGGER.warning("Invalid SESSION_ABSOLUTE_HOURS, defaulting to 168h (7 days)")
    if session_absolute_hours < session_lifetime_hours:
        LOGGER.warning(
            "SESSION_ABSOLUTE_HOURS (%s) is lower than SESSION_LIFETIME_HOURS (%s); clamping to the latter", session_absolute_hours, session_lifetime_hours
        )
        session_absolute_hours = session_lifetime_hours

    try:
        session_rolling_hours = float(getenv("SESSION_ROLLING_HOURS", "0"))
    except ValueError:
        session_rolling_hours = 0.0
        LOGGER.warning("Invalid SESSION_ROLLING_HOURS, defaulting to 0 (disabled)")
    if session_rolling_hours < 0:
        session_rolling_hours = 0.0

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=session_lifetime_hours)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["SESSION_ABSOLUTE_SECONDS"] = int(session_absolute_hours * 3600)
    app.config["SESSION_ROLLING_SECONDS"] = int(session_rolling_hours * 3600)
    app.config["SESSION_ID_LENGTH"] = 64

    session_cache_dir = LIB_DIR.joinpath("ui_sessions_cache")
    session_timeout = int(app.config["PERMANENT_SESSION_LIFETIME"].total_seconds())

    redis_settings = BW_CONFIG.get_config(
        global_only=True,
        methods=False,
        filtered_settings=(
            "USE_REDIS",
            "REDIS_HOST",
            "REDIS_PORT",
            "REDIS_DATABASE",
            "REDIS_TIMEOUT",
            "REDIS_KEEPALIVE_POOL",
            "REDIS_SSL",
            "REDIS_SSL_VERIFY",
            "REDIS_SSL_CA",
            "REDIS_USERNAME",
            "REDIS_PASSWORD",
            "REDIS_SENTINEL_HOSTS",
            "REDIS_SENTINEL_USERNAME",
            "REDIS_SENTINEL_PASSWORD",
            "REDIS_SENTINEL_MASTER",
        ),
    )

    redis_client = None
    if redis_settings.get("USE_REDIS", "no").lower() == "yes":
        redis_client = get_common_redis_client(
            use_redis=True,
            redis_host=redis_settings.get("REDIS_HOST"),
            redis_port=redis_settings.get("REDIS_PORT", "6379"),
            redis_db=redis_settings.get("REDIS_DATABASE", "0"),
            redis_timeout=redis_settings.get("REDIS_TIMEOUT", "1000.0"),
            redis_keepalive_pool=redis_settings.get("REDIS_KEEPALIVE_POOL", "10"),
            redis_ssl=redis_settings.get("REDIS_SSL", "no") == "yes",
            redis_ssl_verify=(redis_settings.get("REDIS_SSL_VERIFY", "yes") or "yes").lower() == "yes",
            redis_ssl_ca=redis_settings.get("REDIS_SSL_CA") or None,
            redis_username=redis_settings.get("REDIS_USERNAME") or None,
            redis_password=redis_settings.get("REDIS_PASSWORD") or None,
            redis_sentinel_hosts=redis_settings.get("REDIS_SENTINEL_HOSTS", []),
            redis_sentinel_username=redis_settings.get("REDIS_SENTINEL_USERNAME") or None,
            redis_sentinel_password=redis_settings.get("REDIS_SENTINEL_PASSWORD") or None,
            redis_sentinel_master=redis_settings.get("REDIS_SENTINEL_MASTER", ""),
        )
        if redis_client:
            LOGGER.debug("Using Redis as session backend")
            app.config["SESSION_TYPE"] = "redis"
            app.config["SESSION_REDIS"] = redis_client
            app.config["SESSION_KEY_PREFIX"] = "bunkerweb_ui_session:"
        else:
            LOGGER.warning("Redis configured but unavailable for sessions, falling back to FileSystemCache")

    if not redis_client:
        app.config["SESSION_TYPE"] = "cachelib"
        app.config["SESSION_CACHELIB"] = SafeFileSystemCache(cache_dir=session_cache_dir, threshold=0, default_timeout=session_timeout)
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

    # Templates name a *page* by its short name — `url_for("bans")` means `bans.bans_page` — which
    # is why this exists at all. But an endpoint that is already fully qualified and is not a page
    # (`onboarding.onboarding_state`, `plugins.plugin_icon`, `threatmap.threatmap_data`) does not
    # fit that convention: expanding it produces `onboarding.onboarding_state.onboarding.
    # onboarding_state_page`, which cannot build.
    #
    # The old version treated that as unresolvable and returned "#". That is not an inert
    # placeholder — `fetch("#")` re-requests the *current page*, so the onboarding drawer was
    # pulling a second full render of every page in the UI on every visit, ~118 KB and a complete
    # server render thrown away, with nothing in the log above DEBUG to say so.
    #
    # So: try the page convention, then the endpoint exactly as written, and only then give up. And
    # give up loudly — a "#" reaching a template is always a bug, either a wrong endpoint name or a
    # blueprint that failed to register, and it is invisible in the rendered page.
    ENDPOINTS_WITHOUT_A_PAGE_SUFFIX = ("static", "index", "loading", "check", "check_reloading", "i18n_catalog")

    def _build_url(endpoint, **values):
        """The URL for `endpoint` under the page convention, or None when nothing matches."""
        if not endpoint:
            return None

        candidates = [endpoint]
        if endpoint not in ENDPOINTS_WITHOUT_A_PAGE_SUFFIX and not endpoint.endswith("_page"):
            candidates.insert(0, f"{endpoint}.{endpoint}_page")

        for candidate in candidates:
            try:
                return url_for(candidate, **values)
            except BuildError as e:
                LOGGER.debug(f"Couldn't build the URL for {candidate}: {e}")
        return None

    def custom_url_for(endpoint, **values):
        url = _build_url(endpoint, **values)
        if url is not None:
            return url
        if endpoint:
            LOGGER.warning(f"No route matches {endpoint!r}; rendering '#', which resolves to the current page when fetched")
        return "#"

    def endpoint_exists(endpoint):
        """Whether `endpoint` resolves, asked as a question rather than answered with a warning.

        `menu.html` decides how to link a plugin by testing whether it has a page of its own. Asking
        that with `url_for(plugin) == "#"` gave the right answer and logged a warning every time it
        was no — one line per pageless plugin per page render, ~17 per render here, which is noise
        that makes the real warnings unfindable. The warning is right for an *unintended* miss and
        wrong for a deliberate probe, so the probe gets its own door.
        """
        return _build_url(endpoint) is not None

    # Declare functions for jinja2
    def to_iso(val):
        """Jinja2 filter: convert datetime or ISO string to local ISO format."""
        if isinstance(val, str):
            val = datetime.fromisoformat(val)
        if isinstance(val, datetime):
            return val.astimezone().isoformat()
        return str(val)

    app.jinja_env.filters["to_iso"] = to_iso

    app.jinja_env.globals.update(
        get_multiples=get_multiples,
        get_filtered_settings=get_filtered_settings,
        get_blacklisted_settings=get_blacklisted_settings,
        get_plugins_settings=BW_CONFIG.get_plugins_settings,
        human_readable_number=human_readable_number,
        is_editable_method=is_editable_method,
        url_for=custom_url_for,
        endpoint_exists=endpoint_exists,
        is_plugin_active=is_plugin_active,
        is_plugin_active_for_service=is_plugin_active_for_service,
        is_ui_api_method=is_ui_api_method,
        can_delete_service=can_delete_service,
        resource_kind_for_setting=resource_kind_for_setting,
    )

    app.config.update({hook_info["key"]: [] for hook_info in HOOKS.values()})

    DATA.load_from_file()
    DATA.update({"FORCE_RELOAD_PLUGIN": False, "IS_RELOADING_PLUGINS": False})
    refresh_app_context()


@app.context_processor
def inject_variables():
    app_env = getattr(g, "_env", {}).copy()
    for hook in app.config["CONTEXT_PROCESSOR_HOOKS"]:
        try:
            resp = hook()
            if resp:
                app_env = {**app_env, **resp}
        except Exception:
            LOGGER.exception("Error in context_processor hook")

    # Aggregate JavaScript from plugin `scripts` hooks
    extra_scripts = list(app_env.get("extra_scripts", []))
    custom_js = []

    for hook in app.config.get("SCRIPTS_HOOKS", []):
        try:
            payload = hook()
            if not payload:
                continue
            # Collect external script URLs or mappings
            srcs = payload.get("src") if isinstance(payload, dict) else None
            if isinstance(srcs, (list, tuple)):
                for s in srcs:
                    extra_scripts.append(s)
            elif isinstance(srcs, str):
                extra_scripts.append(srcs)

            # Collect inline JS (string or list)
            inline = payload.get("inline") if isinstance(payload, dict) else None
            if isinstance(inline, str):
                custom_js.append(inline)
            elif isinstance(inline, (list, tuple)):
                for chunk in inline:
                    if chunk:
                        custom_js.append(chunk)
        except Exception:
            LOGGER.exception("Error in scripts hook")

    # Aggregate CSS from plugin `styles` hooks
    extra_styles = list(app_env.get("extra_styles", []))
    custom_css = []

    for hook in app.config.get("STYLES_HOOKS", []):
        try:
            payload = hook()
            if not payload:
                continue
            # Collect external stylesheet URLs or mappings
            hrefs = payload.get("href") if isinstance(payload, dict) else None
            if isinstance(hrefs, (list, tuple)):
                for h in hrefs:
                    extra_styles.append(h)
            elif isinstance(hrefs, str):
                extra_styles.append(hrefs)

            # Collect inline CSS (string or list)
            inline = payload.get("inline") if isinstance(payload, dict) else None
            if isinstance(inline, str):
                custom_css.append(inline)
            elif isinstance(inline, (list, tuple)):
                for chunk in inline:
                    if chunk:
                        custom_css.append(chunk)
        except Exception:
            LOGGER.exception("Error in styles hook")

    # Always provide keys for templates
    app_env["extra_scripts"] = extra_scripts
    app_env["custom_js"] = custom_js
    app_env["extra_styles"] = extra_styles
    app_env["custom_css"] = custom_css

    g._env = app_env

    return app_env


@login_manager.user_loader
def load_user(username):
    try:
        # Use the auth variant: the plain /users/<name> endpoint strips password,
        # totp_secret and recovery_codes, which would leave current_user.check_password()
        # raising "Invalid salt" on every profile action AND the 2FA before_request gate
        # (bool(current_user.totp_secret)) silently bypassed. Flask-Login rebuilds the user
        # per request server-side (only the username is in the cookie), so carrying the hash
        # here is the same exposure as the login request itself.
        user_data = API_CLIENT.get_user_for_auth(username)
    except (ApiClientError, ApiUnavailableError):
        LOGGER.warning(f"Couldn't get the user {username} from the API.")
        return None
    except Exception:
        LOGGER.error(f"Unexpected error loading user {username} from the API.")
        return None

    if not user_data:
        LOGGER.warning(f"User {username} not found via API.")
        return None

    ui_user = UiUsers(
        username=user_data["username"],
        email=user_data.get("email"),
        password=user_data.get("password") or "",
        method=user_data.get("method", "manual"),
        admin=user_data.get("admin", False),
        theme=user_data.get("theme", "light"),
        language=user_data.get("language", "en"),
        totp_secret=user_data.get("totp_secret"),
    )

    try:
        permissions = API_CLIENT.get_user_permissions(username)
        ui_user.list_permissions = set(permissions)
    except (ApiClientError, ApiUnavailableError):
        LOGGER.warning(f"Couldn't get permissions for user {username}, defaulting to empty.")
        ui_user.list_permissions = set()
    except Exception:
        LOGGER.error(f"Unexpected error getting permissions for user {username}, defaulting to empty.")
        ui_user.list_permissions = set()

    ui_user.list_roles = user_data.get("roles", [])
    ui_user.list_recovery_codes = user_data.get("recovery_codes", [])
    ui_user.webauthn_credentials_count = user_data.get("webauthn_credentials_count", 0)

    if ui_user.totp_secret:
        if (
            "totp-disable" not in request.path
            and "totp-refresh" not in request.path
            and session.get("mfa_validated", False)
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
    LOGGER.debug(format_exc())
    try:
        user_id = current_user.get_id()
    except (AssertionError, RuntimeError):
        user_id = "unknown"
    LOGGER.error(f"CSRF token is missing or invalid for {request.path} by {user_id}")
    try:
        if not current_user:
            return redirect(url_for("setup.setup_page"), 303)
    except (AssertionError, RuntimeError):
        return redirect(url_for("setup.setup_page"), 303)
    response = logout_page()
    response.status_code = 303
    if request.method == "POST":
        # A submitted form dies here rather than at the login check, because the CSRF token lives
        # in the session that just went away. logout_page() clears the session and the response
        # tells the browser to drop its cookies, so a flash would not survive: the reason has to
        # travel in the URL. logout_page() cannot read it off this request, so it is set here.
        response.headers["Location"] = url_for("login.login_page", reason="session_expired")
    return response


def update_github_metadata():
    """Refresh the values the UI shows from GitHub, on the hourly gate in `before_request`.

    Each source is fetched independently: one being unreachable must not cost us the other, and
    a failure leaves the previous value in place rather than blanking the page. Air-gapped
    installs never reach GitHub at all, which is why the failure path logs at debug — an hourly
    warning there would be noise about a deployment choice, not a fault.
    """
    # `PLUGIN_CATALOG` rides along here rather than growing its own timer: the gate, the
    # off-thread submission, the fail-soft semantics and the cross-worker sharing through
    # ui_data.json are exactly what a listing cache needs, and re-implementing them would be
    # a second copy of all four. `fetch_catalog` returns None when the kill switch is off (it
    # issues no request at all) or when neither repository could be resolved and enumerated,
    # and None means "keep what we have" -- the same contract the other two entries follow.
    #
    # Fail-soft is right for the *refresh*; it is not right for installing. That is what the
    # `fetched_at` stamp and the staleness gate in the install routes are for: a listing that
    # has not been confirmed for 24h stops being installable even though it stays on screen.
    for key, fetch in (("LATEST_VERSION", get_latest_stable_release), ("GITHUB_STARS", get_github_stars), ("PLUGIN_CATALOG", fetch_catalog)):
        try:
            value = fetch()
        except BaseException as e:  # noqa: B036 - a background refresh must never take a worker down
            LOGGER.debug(f"Couldn't refresh {key} from GitHub: {e}")
            continue
        if value:
            DATA[key] = value


def check_api_readonly_state():
    """Check API readonly state and update DATA accordingly."""
    with suppress(Exception):
        DATA["READONLY_MODE"] = API_CLIENT.readonly


def schedule_restart_workers():
    global _restart_workers_future, _restart_workers_next_allowed
    with _restart_workers_lock:
        now = time()
        if now < _restart_workers_next_allowed:
            return
        if _restart_workers_future and not _restart_workers_future.done():
            return
        _restart_workers_future = _periodic_tasks_executor.submit(restart_workers)
        _restart_workers_next_allowed = now + RESTART_WORKERS_MIN_INTERVAL_SECONDS


def _delete_session_store_entry(sid: str) -> None:
    """Best-effort delete of a session store entry (Redis key or filesystem cache)."""
    if not sid:
        return
    interface = app.session_interface
    try:
        client = getattr(interface, "client", None)
        key_prefix = getattr(interface, "key_prefix", None)
        if client is not None and key_prefix is not None:
            client.delete(f"{key_prefix}{sid}")
            return
        cache = getattr(interface, "cache", None)
        if cache is not None:
            cache.delete(sid)
    except Exception:
        LOGGER.exception("Failed to delete session store entry during rotation/expiry")


def _rotate_session_id() -> None:
    """Mirror lua-resty-session rolling_timeout: generate a fresh session ID and drop the old store entry."""
    interface = app.session_interface
    regenerate = getattr(interface, "regenerate", None)
    if callable(regenerate):
        try:
            regenerate(session)
            session.modified = True
            return
        except Exception:
            LOGGER.exception("Failed to regenerate session id via session_interface; falling back to manual rotation")

    old_sid = getattr(session, "sid", None)
    new_sid = token_urlsafe(app.config.get("SESSION_ID_LENGTH", 64))
    _delete_session_store_entry(old_sid)
    try:
        session.sid = new_sid  # type: ignore[attr-defined]
    except Exception:
        LOGGER.exception("Failed to assign new session id during rotation; aborting rotation")
        return
    session.modified = True


def _enforce_session_lifetime() -> bool:
    """Mirror lua-resty-session absolute/rolling timeouts. Returns True if the session was invalidated."""
    if not current_user.is_authenticated:
        return False

    creation_date = session.get("creation_date")
    if not isinstance(creation_date, datetime):
        return False

    now = datetime.now().astimezone()
    absolute_seconds = app.config.get("SESSION_ABSOLUTE_SECONDS", 0)
    if absolute_seconds > 0 and (now - creation_date).total_seconds() > absolute_seconds:
        LOGGER.info("UI session for user %s exceeded SESSION_ABSOLUTE_HOURS, forcing logout", current_user.get_id())
        old_sid = getattr(session, "sid", None)
        logout_user()
        session.clear()
        _delete_session_store_entry(old_sid)
        return True

    rolling_seconds = app.config.get("SESSION_ROLLING_SECONDS", 0)
    if rolling_seconds > 0:
        last_rotated_at = session.get("last_rotated_at", creation_date)
        if isinstance(last_rotated_at, datetime) and (now - last_rotated_at).total_seconds() > rolling_seconds:
            _rotate_session_id()
            session["last_rotated_at"] = now
            session.permanent = True  # ensure the new id inherits the sliding TTL

    return False


def _host_allowed(host: str, allowed: list) -> bool:
    """Return True if the request Host matches the configured allowlist.

    Supports exact matches and "*.example.com" wildcards (which also match the bare
    domain). The port, if present, is ignored for comparison.
    """
    if not host:
        return False
    hostname = host.split(":", 1)[0].strip().lower()
    for entry in allowed:
        e = entry.strip().lower()
        if not e:
            continue
        if e == "*":
            return True
        e = e.split(":", 1)[0]
        if e.startswith("*."):
            base = e[2:]
            if hostname == base or hostname.endswith("." + base):
                return True
        elif hostname == e:
            return True
    return False


# An inbound correlation id is whatever the caller sent. It is echoed in a response header and
# written to the logs of two services, so it is accepted only in this shape and generated
# otherwise — never trusted verbatim.
_REQUEST_ID_RE = re_compile(r"[A-Za-z0-9._-]{1,64}")


@app.before_request
def before_request():
    # Skip the per-request lifecycle (UIData lock, CSP nonce, get_metadata) for static assets;
    # returning None lets the static view still serve the file (after_request supplies the nonce).
    if is_static_path(request.path):
        return

    # Defense-in-depth: reject unexpected Host headers when an allowlist is configured.
    allowed_hosts = app.config.get("ALLOWED_HOSTS") or []
    if allowed_hosts and not _host_allowed(request.host, allowed_hosts):
        LOGGER.warning(f"Blocking UI request with disallowed Host header: {request.host!r}")
        return make_response(jsonify({"message": "Invalid host"}), 400)

    # Opened before anything else this request does, so the totals cover the whole render and
    # not just the part after the checks above. `token_hex(8)` rather than a uuid: it lands in
    # a response header and in two services' logs, and 16 characters are enough to grep for.
    inbound = request.headers.get("X-Request-ID", "")
    request_id = inbound if _REQUEST_ID_RE.fullmatch(inbound) else token_hex(8)
    perf.start(request_id)
    REQUEST_ID.set(request_id)

    DATA.load_from_file()
    if DATA.get("SERVER_STOPPING", False):
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    metadata = None
    g.script_nonce = token_urlsafe(32)

    # Auto-detect cookie config once on the first real request using double-checked locking.
    # The proxy status never changes during a process's lifetime, so detecting once is correct.
    global _cookie_config_detected
    if not _cookie_config_detected:
        with _cookie_config_lock:
            if not _cookie_config_detected:
                if request.environ.get("HTTP_X_FORWARDED_FOR") is not None:
                    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
                    app.config["SESSION_COOKIE_SECURE"] = True
                else:
                    app.config["SESSION_COOKIE_NAME"] = "bw_ui_session"
                    app.config["SESSION_COOKIE_SECURE"] = False
                    app.config["SESSION_COOKIE_DOMAIN"] = None
                _cookie_config_detected = True

    if not is_static_path(request.path):
        try:
            metadata = API_CLIENT.get_metadata()
        except Exception:
            LOGGER.warning("Failed to fetch metadata from API.")
            metadata = {}

        # Plugin reload trigger
        if not DATA.get("RELOADING", False) and metadata.get("reload_ui_plugins", False):
            if API_CLIENT.readonly:
                LOGGER.warning("reload_ui_plugins is set but database is read-only, skipping plugin reload to prevent infinite loop")
            else:
                safe_reload_plugins()
                # Reset the flag BEFORE sending SIGHUP so new workers see it cleared
                err = API_CLIENT.checked_changes(changes=["ui_plugins"], value=False)
                if err:
                    LOGGER.error(f"Couldn't reset reload_ui_plugins flag: {err}, skipping worker restart to prevent loop")
                else:
                    schedule_restart_workers()

        # Stamped before the fetch is submitted, not after: a slow or failing refresh must not let
        # every request in the meantime queue another one.
        if datetime.now().astimezone() - datetime.fromisoformat(DATA.get("LATEST_VERSION_LAST_CHECK", "1970-01-01T00:00:00")).astimezone() > timedelta(hours=1):
            DATA["LATEST_VERSION_LAST_CHECK"] = datetime.now().astimezone().isoformat()
            _periodic_tasks_executor.submit(update_github_metadata)

        # Periodic expired session file cleanup (FileSystemCache only, where _prune is disabled via threshold=0)
        if app.config.get("SESSION_TYPE") == "cachelib":
            global _session_cleanup_last_run
            now_ts = time()
            if now_ts - _session_cleanup_last_run > _SESSION_CLEANUP_INTERVAL_SECONDS:
                _session_cleanup_last_run = now_ts
                _periodic_tasks_executor.submit(app.config["SESSION_CACHELIB"]._remove_expired, now_ts)

        # Check API readonly state (uses TTL-cached property)
        check_api_readonly_state()

        if not request.path.startswith(("/check", "/loading", "/login", "/totp")) and DATA.get("READONLY_MODE", False) and current_user.is_authenticated:
            flask_flash("Database connection is in read-only mode : no modifications possible.", "error")

        if current_user.is_authenticated:
            passed = True

            # Ensure essential session fields are present for consistent UI behavior
            if "creation_date" not in session:
                session["creation_date"] = datetime.now().astimezone()
            if "ip" not in session:
                session["ip"] = request.remote_addr
            if "user_agent" not in session:
                session["user_agent"] = request.headers.get("User-Agent")
            if "last_rotated_at" not in session:
                session["last_rotated_at"] = session["creation_date"]
            if "mfa_validated" not in session and "totp_validated" in session:
                # Sessions created before passkeys existed carry the old flag name; migrate them in
                # place so an upgrade doesn't bounce every logged-in user back through /totp.
                session["mfa_validated"] = session.pop("totp_validated")

            # Enforce absolute and rolling session lifetimes (mirrors lua-resty-session)
            if _enforce_session_lifetime():
                # The third producer of a session destroyed out from under the user, after the CSRF
                # handler and the password change. `_enforce_session_lifetime` has just called
                # `session.clear()`, so a flash cannot survive to explain it -- the reason travels
                # in the URL, same mechanism, different message. See LOGIN_NOTICES.
                return redirect(url_for("login.login_page", reason="session_timeout"))

            # Case not login page, keep on 2FA before any other access.
            #
            # Deliberately keyed on TOTP alone, not on registered passkeys. A passkey is an
            # alternative *primary* credential (it replaces the password outright), not a second
            # factor bolted onto it -- and unlike TOTP it has no recovery codes, so gating password
            # logins on it would lock a user out for good the day they lose the device. A passkey
            # holder who has TOTP enabled can still satisfy this gate with their key, on /totp.
            if not session.get("mfa_validated", False) and bool(current_user.totp_secret) and request.endpoint != "totp.totp_page":
                if not request.path.endswith("/login"):
                    raw_next = request.values.get("next")
                    try:
                        safe_next = _sanitize_internal_next(raw_next, url_for("home.home_page"))
                    except ValueError:
                        safe_next = url_for("home.home_page")

                    return redirect(url_for("totp.totp_page", next=safe_next))
                passed = False
            elif (app.config["CHECK_PRIVATE_IP"] or not ip_address(request.remote_addr).is_private) and session["ip"] != request.remote_addr:
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session["user_agent"] != request.headers.get("User-Agent"):
                LOGGER.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False
            elif "session_id" in session and is_session_revoked(session["session_id"]):
                LOGGER.warning(f"User {current_user.get_id()} tried to access a revoked session.")
                passed = False

            if not passed:
                return logout_page(), 403

    current_endpoint = request.path.split("/")[-1]
    theme_value = current_user.theme if current_user.is_authenticated else "dark"
    language_value = current_user.language if current_user.is_authenticated else "en"
    base_env = dict(
        current_endpoint=current_endpoint,
        script_nonce=g.script_nonce,
        supported_languages=SUPPORTED_LANGUAGES,
        theme=theme_value,
        language=language_value,
        # The comfort preferences are per user, so the anonymous/login pages get the neutral
        # defaults rather than nothing: base.html renders `theme_mode | tojson`, and an
        # Undefined there is a 500, not a missing feature.
        theme_mode=theme_value,
        dismissed_notices={},
        hidden_home_cards=[],
    )

    if request.path.startswith(("/check", "/setup", "/loading", "/login", "/totp")):
        g._env = base_env
    else:
        if not metadata:
            try:
                metadata = API_CLIENT.get_metadata()
            except Exception:
                LOGGER.warning("Failed to fetch metadata from API in before_request.")
                metadata = {}

        changes_ongoing = any(
            v
            for k, v in metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        )

        if not changes_ongoing and DATA.get("PRO_LOADING"):
            DATA["PRO_LOADING"] = False

        if not request.path.startswith("/loading") and current_user.is_authenticated:
            if not changes_ongoing and metadata.get("failover", False):
                flask_flash(
                    "<p class='p-0 m-0 fst-italic'>The last changes could not be applied because it creates a configuration error on NGINX, please check BunkerWeb's logs for more information. The configuration fell back to the last working one.</p>",
                    "error",
                )
                flask_flash(
                    f"""<div class='d-flex flex-column'>
                        <h6 class='fw-bold mb-1'>Failover Message:</h6>
                        <p class='p-0 m-0 fst-italic'>{metadata.get('failover_message', '')}</p>
                    </div>""",
                    "error",
                )
            elif not changes_ongoing and not metadata.get("failover", False) and DATA.get("CONFIG_CHANGED", False):
                flash("The last changes have been applied successfully.")
                DATA["CONFIG_CHANGED"] = False

        # Determine if this is a CORS or AJAX request
        fetch_mode = request.headers.get("Sec-Fetch-Mode")
        x_requested_with = request.headers.get("X-Requested-With")
        is_cors = fetch_mode == "cors" or (x_requested_with and x_requested_with.lower() == "xmlhttprequest")

        # Default to the scheduler-computed flag; refined to a live count below on real page requests.
        pro_overlapped = metadata["pro_overlapped"]

        if not is_cors and current_user.is_authenticated:
            seen = set()
            for f in DATA.get("TO_FLASH", []):
                content = f["content"]
                if content in seen:
                    continue
                seen.add(content)
                flash(content, f["type"], save=f.get("save", True))
            DATA["TO_FLASH"] = []

            # Live, every-request overlap check — the metadata flag is only refreshed daily by the scheduler.
            # UI is API-only (DB is a None shim), so count services through BW_CONFIG (API-backed).
            # The count MUST be the shared classifier's billable figure, not len(services): the
            # license path bills the same number, and a UI that recounts its own way is exactly the
            # divergence the shared module exists to kill. `full=False` is the input contract —
            # the non-default persisted config, never the fully-defaulted one.
            if metadata.get("is_pro") and metadata.get("pro_services"):
                pro_overlapped = billable_service_count() > metadata["pro_services"]
                if pro_overlapped and current_endpoint != "pro":
                    flash(
                        "You have more services than allowed by your pro license. "
                        "Upgrade your license or move some services to draft mode to unlock your pro license.",
                        "pro",
                        i18n_key="flash.pro_services_exceeded",
                        save=False,  # transient toast; keep it out of the notification history
                    )

        try:
            # Identities only unless this page actually renders settings from them — see
            # SETTINGS_HUNGRY_PATH_PREFIXES. The schema is 95% of the payload and every page
            # was paying for it to draw a sidebar list of plugin names.
            plugins = BW_CONFIG.get_plugins(with_settings=request.path.startswith(SETTINGS_HUNGRY_PATH_PREFIXES))
        except Exception:
            plugins = {}

        bw_version = metadata.get("version", "unknown")
        pro_expire_val = metadata.get("pro_expire")

        # Whether to render the walkthrough pill + drawer at all. Cached in the session so a
        # page render costs no extra API call: the blob only changes through
        # /onboarding/state, which clears the flag itself. A user who finished or dismissed
        # the walkthrough therefore downloads none of that markup and issues no request.
        onboarding_active = session.get("onboarding_active")
        onboarding_autoopen = False
        if onboarding_active is None:
            try:
                blob = API_CLIENT.get_user_preferences(current_user.get_id(), ONBOARDING_PREFERENCE_KEY) or {}
            except Exception:
                blob = {}
            onboarding_active = not (blob.get("dismissed_at") or blob.get("completed_at"))
            # Auto-open is off, and the mechanism below it is left intact so it can come back.
            #
            # The drawer is `offcanvas-end`: 400 px of fixed overlay pinned to the right edge,
            # with no backdrop. The first page a session renders is whatever the user asked for —
            # a bookmarked list page as readily as the dashboard — so it opened itself on top of
            # that page's toolbar. Measured on the perf stack at 1920 and 1280 wide, with
            # `document.elementFromPoint` at each control's centre rather than by eye:
            #
            #   /services  Create new service, Import services, Show/Hide filters, language picker
            #   /configs   Create custom config, Actions, Show/Hide filters, language picker
            #
            # covered 100% and not clickable — the click lands on the drawer. `onboarding.js`
            # already holds the rule this breaks: `spotlight()` hides the drawer before pointing
            # at anything, because "the drawer covers the chrome it is pointing at". A panel
            # teaching someone to create their first service must not sit on the button that
            # creates it.
            #
            # The pill (`#onboarding-button`) is untouched, so the walkthrough stays one click
            # away and every other surface — hints, spotlight, progress — is unaffected. Turning
            # auto-open back on means giving the drawer somewhere to open *into*: the page would
            # have to reflow, and the navbar it would push is `position: fixed` and shared by
            # every page. That is a layout change, not a flag, and it is the PO's call.
            onboarding_autoopen = False
            session["onboarding_active"] = onboarding_active

        # Per-user comfort preferences (#3820): dismissed notices, the theme mode, and the
        # hidden Home cards. Resolved once per session for the same reason the walkthrough flag
        # is -- these change only through /preferences/* and /set_theme, which clear their own
        # session key -- so a page render costs no extra API call.
        notices_session_key = PREFERENCE_SESSION_KEYS[DISMISSED_NOTICES_KEY]
        if notices_session_key not in session:
            session[notices_session_key] = load_dismissed_notices(current_user.get_id())
        dismissed = session[notices_session_key]

        cards_session_key = PREFERENCE_SESSION_KEYS[HIDDEN_CARDS_KEY]
        if cards_session_key not in session:
            session[cards_session_key] = load_hidden_home_cards(current_user.get_id())
        hidden_cards = session[cards_session_key]

        mode_session_key = PREFERENCE_SESSION_KEYS[THEME_MODE_KEY]
        if mode_session_key not in session:
            session[mode_session_key] = load_theme_mode(current_user.get_id())
        # No stored mode means the pre-1.7 behaviour: whatever `bw_ui_users.theme` holds is an
        # explicit choice.
        mode = session[mode_session_key] or theme_value

        # The post-upgrade recap. Resolved once per session like the walkthrough flag; the
        # releases themselves come from a parsed-and-cached CHANGELOG.md, so the extra cost
        # of a pending recap is a dict lookup, and of a caught-up user nothing at all.
        whatsnew_releases = ()
        if session.get("whatsnew_pending") is not False:
            releases, stored = pending_releases(current_user.get_id(), bw_version)
            session["whatsnew_pending"] = bool(releases)
            if releases:
                whatsnew_releases = releases
                LOGGER.debug(f"What's new: {len(releases)} release(s) between {stored} and {bw_version} for {current_user.get_id()}")

        data = dict(
            current_endpoint=current_endpoint,
            script_nonce=g.script_nonce,
            bw_version=bw_version,
            latest_version=DATA.get("LATEST_VERSION", "unknown"),
            new_version_available=is_newer_version_available(bw_version, DATA.get("LATEST_VERSION", "unknown")),
            is_pro_version=metadata.get("is_pro", False),
            pro_status=metadata.get("pro_status", "unknown"),
            pro_services=metadata.get("pro_services", 0),
            pro_expire=pro_expire_val.strftime("%Y/%m/%d") if isinstance(pro_expire_val, datetime) else "Unknown",
            pro_overlapped=pro_overlapped,
            plugins=plugins,
            flash_messages=session.get("flash_messages", []),
            is_readonly=DATA.get("READONLY_MODE", False) or ("write" not in current_user.list_permissions and not request.path.startswith("/profile")),
            db_readonly=DATA.get("READONLY_MODE", False),
            user_readonly="write" not in current_user.list_permissions,
            user_admin=current_user.admin,
            # One flag for every page: the catalogue sections read it, and so does the
            # navigation, so the kill switch cannot be honoured on one page and forgotten on
            # another. The routes re-check it server-side -- this only decides what is drawn.
            catalog_enabled=catalog_enabled(),
            theme=theme_value,
            language=language_value,
            supported_languages=SUPPORTED_LANGUAGES,
            columns_preferences_defaults=COLUMNS_PREFERENCES_DEFAULTS,
            extra_pages=app.config["EXTRA_PAGES"],
            extra_scripts=DATA.get("EXTRA_SCRIPTS", []),
            extra_styles=DATA.get("EXTRA_STYLES", []),
            dismissed_notices=dismissed,
            hidden_home_cards=hidden_cards,
            theme_mode=mode,
            onboarding_active=onboarding_active,
            onboarding_autoopen=onboarding_autoopen,
            whatsnew_releases=whatsnew_releases,
        )

        try:
            data["config"] = BW_CONFIG.get_config(global_only=True, methods=True)
        except Exception:
            data["config"] = {}

        data["resource_groups"] = {}
        if request.path.startswith(("/global-config", "/global-settings", "/services/")):
            try:
                data["resource_groups"] = API_CLIENT.get_resource_groups()
            except (ApiClientError, ApiUnavailableError):
                LOGGER.warning("Failed to fetch resource groups for settings selectors.")

        if current_endpoint in COLUMNS_PREFERENCES_DEFAULTS:
            try:
                data["columns_preferences"] = API_CLIENT.get_user_preferences(current_user.get_id(), current_endpoint)
            except Exception:
                data["columns_preferences"] = {}

        g._env = data

    for hook in app.config["BEFORE_REQUEST_HOOKS"]:
        try:
            resp = hook()
            if resp:
                return resp
        except Exception:
            LOGGER.exception("Error in before_request hook")


def mark_user_access(user, session_id):
    if not user or DATA.get("READONLY_MODE", False):
        return

    try:
        API_CLIENT.mark_user_access(user.get_id(), session_id)
        LOGGER.debug(f"Marked the user access for session {session_id}")
    except Exception:
        LOGGER.debug(f"Couldn't mark the user access for session {session_id}")


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # Ensure script_nonce is available even if before_request didn't complete
    # (e.g., when CSRF validation fails before our before_request runs)
    script_nonce = getattr(g, "script_nonce", None) or token_urlsafe(32)

    # * Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src https: http: 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com;"
        + f" script-src https: http: 'self' 'nonce-{script_nonce}' 'strict-dynamic' 'unsafe-inline';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: blob: https://www.bunkerweb.io https://assets.bunkerity.com https://*.tile.openstreetmap.org;"
        + " font-src 'self' data:;"
        + " base-uri 'self';"
        + " block-all-mixed-content;"
        + (" connect-src *;" if request.path.startswith(("/check", "/setup")) else " connect-src https: http: 'self' https://www.bunkerweb.io/api/posts/0/3;")
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
    #
    # Everything is denied outright except four features, all narrowed to `self` (same-origin only
    # -- an embedded cross-origin frame still gets nothing):
    #   * fullscreen        -- the /threatmap "Fullscreen" control. Without it the API is blocked
    #                          and the button is inert. (F11 is unaffected either way: browser
    #                          chrome fullscreen is not governed by this header.)
    #   * screen-wake-lock  -- keeps a monitor left on /threatmap from blanking. Requested only
    #                          by that page, only while it is visible, and released on hide.
    #   * publickey-credentials-create / publickey-credentials-get
    #                       -- WebAuthn enrollment and assertion. Denying either one disables
    #                          passkey login and security keys outright, with no error the user
    #                          can act on. The private key never leaves the authenticator, and the
    #                          browser's own UI gates every ceremony.
    # None of them grants access to data, hardware or the user's environment; all are reversible by
    # putting `fullscreen=()` / `screen-wake-lock=()` / `publickey-credentials-*=()` back.
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), ambient-light-sensor=(), attribution-reporting=(), autoplay=(), battery=(), bluetooth=(), browsing-topics=(), camera=(), ch-device-memory=(), ch-downlink=(), ch-dpr=(), ch-ect=(), ch-prefers-color-scheme=(), ch-prefers-reduced-motion=(), ch-prefers-reduced-transparency=(), ch-rtt=(), ch-save-data=(), ch-ua-arch=(), ch-ua-bitness=(), ch-ua-form-factors=(), ch-ua-full-version-list=(), ch-ua-full-version=(), ch-ua-mobile=(), ch-ua-model=(), ch-ua-platform-version=(), ch-ua-platform=(), ch-ua-wow64=(), ch-ua=(), ch-viewport-height=(), ch-viewport-width=(), ch-width=(), compute-pressure=(), device-attributes=(), digital-credentials-create=(), digital-credentials-get=(), display-capture=(), encrypted-media=(), execution-while-not-rendered=(), execution-while-out-of-viewport=(), focus-without-user-activation=(), fullscreen=(self), gamepad=(), geolocation=(), gyroscope=(), hid=(), identity-credentials-get=(), idle-detection=(), interest-cohort=(), keyboard-map=(), language-detector=(), language-model=(), local-fonts=(), magnetometer=(), manual-text=(), media-playback-while-not-visible=(), microphone=(), midi=(), otp-credentials=(), payment=(), picture-in-picture=(), proofreader=(), publickey-credentials-create=(self), publickey-credentials-get=(self), rewriter=(), screen-wake-lock=(self), serial=(), shared-storage-select-url=(), shared-storage=(), speaker-selection=(), storage-access=(), tools=(), translator=(), unload=(), usb=(), vertical-scroll=(), web-app-installation=(), web-share=(), webnn=(), window-management=(), writer=(), xr-spatial-tracking=()"
    )

    # Out of search indexes. robots.txt stops a crawler fetching the page; it does not stop the URL
    # being indexed once it has been discovered somewhere else, and this header does.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    # Sever the opener relationship and refuse cross-origin embedding of any UI response.
    # COEP is left out on purpose: it would break the third-party resources the CSP allows.
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    # Keep authenticated pages out of the browser cache, so the back button cannot redraw the panel
    # after a logout. Two exemptions, both deliberate:
    #   * static assets keep the far-future max-age the static handler gave them -- no-store there
    #     would re-download every asset on every page;
    #   * `setdefault`, so a route that already answered this question wins. /plugins/<p>/icon
    #     (private, max-age=3600), the log streams (no-cache) and logout (a stricter no-store) all
    #     set their own, and this must not flatten them.
    if not is_static_path(request.path):
        response.headers.setdefault("Cache-Control", "no-store")

    # What this page cost, where a browser can read it without any tooling. Deliberately not
    # gated on DEBUG: a number you have to switch on is a number nobody has when it matters.
    timing = perf.server_timing()
    if timing:
        response.headers["Server-Timing"] = timing
        response.headers["X-Request-ID"] = g.request_id
        calls, api_ms, total_ms = perf.totals()
        LOGGER.debug(f"{request.method} {request.path} rid={g.request_id} api_calls={calls} api_ms={api_ms:.1f} total_ms={total_ms:.1f}")

    for hook in app.config["AFTER_REQUEST_HOOKS"]:
        try:
            resp = hook(response)
            if resp is not None:
                response = resp
        except Exception:
            LOGGER.exception("Error in after_request hook")

    # Evict a pre-upgrade Flask-Login remember token still sitting in a browser. It is already
    # inert (REMEMBER_COOKIE_NAME points at a sentinel), so this is hygiene, not the fix itself.
    # Done directly rather than through flask_login's _clear_cookie, which now targets the
    # sentinel name and so cannot reach these two, and which omits secure= -- werkzeug's
    # delete_cookie defaults it to False and a __Host- deletion without Secure is rejected by
    # the UA. Skipped on static paths so no Set-Cookie lands on a cacheable response.
    # ponytail: hard-coded name list; drop this block once no issued token can still be live.
    if not is_static_path(request.path):
        for legacy_cookie in ("__Host-bw_ui_remember_token", "bw_ui_remember_token"):
            if legacy_cookie in request.cookies:
                response.delete_cookie(legacy_cookie, path="/", secure=legacy_cookie.startswith("__Host-"))

    return response


@app.teardown_request
def teardown_request(teardown):
    # Runs even when before_request returned early, which is what keeps a reused worker thread
    # from starting its next request holding the previous one's memo.
    perf.finish()

    with suppress(AssertionError, RuntimeError):
        if not is_static_path(request.path) and current_user.is_authenticated and "session_id" in session:
            _user_access_executor.submit(mark_user_access, current_user, session["session_id"])

    for hook in app.config["TEARDOWN_REQUEST_HOOKS"]:
        try:
            hook(teardown)
        except Exception:
            LOGGER.exception("Error in teardown_request hook")


### * MISC ROUTES * ###


@app.route("/", strict_slashes=False, methods=["GET"])
def index():
    try:
        admin_user = API_CLIENT.get_admin_user()
    except Exception:
        admin_user = None

    if admin_user:
        if current_user.is_authenticated:  # type: ignore
            return redirect(url_for("home.home_page"))
        return redirect(url_for("login.login_page"), 303)
    return redirect(url_for("setup.setup_page"), 303)


@app.route("/loading", methods=["GET"])
@login_required
def loading():
    home_url = url_for("home.home_page")

    raw_next = request.values.get("next")
    try:
        next_url = _sanitize_internal_next(raw_next, home_url)
    except ValueError:
        return Response(status=400)

    return render_template("loading.html", message=request.values.get("message", "Loading..."), next=next_url)


@app.route("/check", methods=["GET"])
def check():
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/.well-known/security.txt", methods=["GET"])
def security_txt():
    """RFC 9116. Generated rather than shipped as a static file, because `Expires` is mandatory and
    a stale one makes the whole document invalid -- a file committed today expires unattended."""
    expires = (datetime.now().astimezone() + timedelta(days=365)).replace(microsecond=0).isoformat()
    fields = [
        "Contact: mailto:security@bunkerity.com",
        "Contact: https://github.com/bunkerity/bunkerweb/security/advisories/new",
        f"Expires: {expires}",
        "Acknowledgments: https://github.com/bunkerity/bunkerweb/security/advisories",
        "Preferred-Languages: en, fr",
        "Policy: https://github.com/bunkerity/bunkerweb/blob/master/SECURITY.md",
    ]

    # Canonical is derived from the request, so it is only emitted once the Host header has been
    # vetted against a real allowlist: this path is in STATIC_EXACT_PATHS, so `before_request`
    # returns before its Host check ever runs, and "*" vets nothing. Unvetted, the field would
    # echo whatever Host the caller sent back into a signed-looking security document.
    allowed_hosts = app.config.get("ALLOWED_HOSTS") or []
    if allowed_hosts and "*" not in allowed_hosts and _host_allowed(request.host, allowed_hosts):
        fields.append(f"Canonical: {url_for('security_txt', _external=True)}")

    return Response(content_type="text/plain; charset=utf-8", response="\n".join(fields) + "\n")


@app.route("/security.txt", methods=["GET"])
def security_txt_redirect():
    # RFC 9116 keeps the root location for legacy fetchers and points it at the canonical one.
    return redirect(url_for("security_txt"), 301)


@app.route("/.well-known/change-password", methods=["GET"])
def change_password_redirect():
    # https://w3c.github.io/webappsec-change-password-url/ -- what a password manager follows to
    # offer "change password". Not permanent on purpose: the page holding the form may move.
    return redirect(url_for("profile.profile_page"))


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

    try:
        db_metadata = API_CLIENT.get_metadata()
    except Exception:
        db_metadata = {}

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

    return jsonify({"reloading": DATA.get("RELOADING", False)})


@app.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    if DATA.get("READONLY_MODE", False):
        return Response(status=423, response=dumps({"message": "Database is in read-only mode"}), content_type="application/json")
    elif request.form["theme"] not in ("dark", "light"):
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    # The MODE (light/dark/system) is a per-user preference; the column keeps storing the
    # RESOLVED value so the server-rendered first paint stays correct and THEMES_ENUM -- and
    # therefore the schema -- does not move. An absent `mode` means an explicit choice, which
    # is exactly what the resolved value already says.
    mode = request.form.get("mode", request.form["theme"])
    if mode not in ("dark", "light", "system"):
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    try:
        API_CLIENT.update_user(current_user.get_id(), theme=request.form["theme"])
        API_CLIENT.update_user_preferences(current_user.get_id(), THEME_MODE_KEY, {"mode": mode})
    except Exception as e:
        LOGGER.error(f"Couldn't update the user {current_user.get_id()}: {e}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    session.pop(PREFERENCE_SESSION_KEYS[THEME_MODE_KEY], None)

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/set_language", methods=["POST"])
def set_language():
    """Record the chosen language, in the session always and on the user when that is possible.

    No `@login_required`, and no early return on a read-only database: since the chrome is
    rendered server-side, this endpoint is the *only* way the server can learn which language to
    render in. Refusing it would leave three kinds of user unable to change language at all —
    someone on the login page, someone whose database is read-only, and someone whose API write
    fails. The session is not the database, so recording it there is always allowed.

    Saving to the user record is the part that needs an account and a writable database; it is
    what makes the choice follow them to another browser.
    """
    allowed_languages = {lang["code"] for lang in SUPPORTED_LANGUAGES}
    lang = (request.form.get("language") or "").lower()
    if lang not in allowed_languages:
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    # Read by `app/i18n.resolve_locale` on the very next request — including the reload the
    # language switcher issues, which is what makes the change visible at all.
    session["language"] = lang

    if not current_user.is_authenticated or DATA.get("READONLY_MODE", False):
        return Response(status=200, response=dumps({"message": "ok", "saved": False}), content_type="application/json")

    try:
        API_CLIENT.update_user(current_user.get_id(), language=lang)
    except Exception as e:
        # The session already carries the choice, so the language does change; it just will not
        # outlive the session. Worth a log, not worth failing the request.
        LOGGER.error(f"Couldn't save the language preference of user {current_user.get_id()}: {e}")
        return Response(status=200, response=dumps({"message": "ok", "saved": False}), content_type="application/json")

    # Saved: drop the session override so it can never shadow a *newer* choice made from another
    # browser. The user record is the durable answer from here on.
    session.pop("language", None)

    return Response(status=200, response=dumps({"message": "ok", "saved": True}), content_type="application/json")


@app.route("/locales/<string:lang>.js")
def i18n_catalog(lang: str):
    """The message catalog as a synchronous script, so `t()` is defined before any page script runs.

    Public by construction: `/locales/` is in `STATIC_PATH_PREFIXES`, so this is reachable from
    the login page and the setup wizard, which need it as much as any authenticated page does.
    """
    catalog = browser_catalog(app.static_folder or "", lang)
    if catalog is None:
        return Response(status=404)

    # Explicit charset: the catalogs are full of non-ASCII copy and a script tag with no
    # charset inherits the document's, which is not always what the file is.
    response = Response(catalog, content_type="application/javascript; charset=utf-8")
    response.headers["Cache-Control"] = f"public, max-age={app.config['SEND_FILE_MAX_AGE_DEFAULT']}"
    return response


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
        DATA.get("READONLY_MODE", False)
        or table_name not in COLUMNS_PREFERENCES_DEFAULTS
        or any(column not in COLUMNS_PREFERENCES_DEFAULTS[table_name] for column in columns_preferences)
    ):
        return Response(status=400, response=dumps({"message": "Bad request"}), content_type="application/json")

    try:
        API_CLIENT.update_user_preferences(current_user.get_id(), table_name, columns_preferences)
    except Exception as e:
        LOGGER.error(f"Couldn't update the user {current_user.get_id()}'s columns preferences: {e}")
        return Response(status=500, response=dumps({"message": "Internal server error"}), content_type="application/json")

    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/clear_notifications", methods=["POST"])
@login_required
def clear_notifications():
    session["flash_messages"] = []
    session.modified = True
    return Response(status=200, response=dumps({"message": "ok"}), content_type="application/json")


for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)
