from contextlib import suppress
from threading import Thread
from time import time
from typing import Dict
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

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for global_config module")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import get_blacklisted_settings

from app.routes.utils import handle_error, wait_applying


global_config = Blueprint("global_config", __name__)


# Handle global configuration management with form processing and background updates.
# Displays configuration interface and processes POST requests with validation, change detection,
# and asynchronous configuration updates while maintaining scheduler coordination.
@global_config.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config_page():
    if DEBUG_MODE:
        logger.debug(f"global_config_page() called with method: {request.method}")
        logger.debug(f"Request args: {dict(request.args)}")
    
    # Retrieve current global configuration including method-specific settings for form population
    global_config = DB.get_config(global_only=True, methods=True)
    if DEBUG_MODE:
        logger.debug(f"Retrieved global config with {len(global_config)} settings")

    if request.method == "POST":
        if DEBUG_MODE:
            logger.debug("Processing POST request for configuration update")
            logger.debug(f"Form contains {len(request.form)} fields")
        
        if DB.readonly:
            if DEBUG_MODE:
                logger.debug("Database is in read-only mode - rejecting configuration change")
            return handle_error("Database is in read-only mode", "global_config")
        
        DATA.load_from_file()
        if DEBUG_MODE:
            logger.debug("Loaded DATA from file for configuration processing")

        # Extract configuration variables from form data excluding CSRF token
        # Creates clean dictionary for validation and processing operations
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        if DEBUG_MODE:
            logger.debug(f"Extracted {len(variables)} configuration variables from form")

        # Execute global configuration update in background thread with comprehensive validation.
        # Handles variable checking, change detection, service-specific propagation, and
        # scheduler coordination while providing detailed user feedback through flash messages.
        def update_global_config(variables: Dict[str, str]):
            if DEBUG_MODE:
                logger.debug("update_global_config() background thread started")
                logger.debug(f"Processing {len(variables)} configuration variables")

            wait_applying()
            if DEBUG_MODE:
                logger.debug("Completed wait_applying() - proceeding with configuration update")

            # Retrieve comprehensive configuration including drafts for validation and comparison
            config = DB.get_config(methods=True, with_drafts=True)
            services = config["SERVER_NAME"]["value"].split(" ")
            variables_to_check = variables.copy()
            
            if DEBUG_MODE:
                logger.debug(f"Retrieved full config with {len(config)} settings")
                logger.debug(f"Active services: {services}")

            # Remove variables that haven't changed to optimize processing and avoid unnecessary updates
            for variable, value in variables.items():
                setting = config.get(variable, {"value": None, "global": True})
                if setting["global"] and value == setting["value"]:
                    del variables_to_check[variable]
                    if DEBUG_MODE:
                        logger.debug(f"Skipping unchanged variable: {variable}")

            if DEBUG_MODE:
                logger.debug(f"Variables requiring validation: {len(variables_to_check)}")

            # Validate configuration variables against schema and constraints
            variables = BW_CONFIG.check_variables(variables, config, variables_to_check, global_config=True, threaded=True)
            if DEBUG_MODE:
                logger.debug(f"Variable validation completed - final count: {len(variables)}")

            # Check for removed settings by comparing against blacklisted items
            no_removed_settings = True
            blacklist = get_blacklisted_settings(True)
            if DEBUG_MODE:
                logger.debug(f"Blacklist contains {len(blacklist)} protected settings")
            
            for setting in global_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    if DEBUG_MODE:
                        logger.debug(f"Detected removed setting: {setting}")
                    break

            # Skip update if no actual changes detected after comprehensive analysis
            if no_removed_settings and not variables_to_check:
                content = "The global configuration was not edited because no values were changed."
                DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                if DEBUG_MODE:
                    logger.debug("No configuration changes detected - skipping update")
                return

            # Enable PRO loading indicator if license key is being updated
            if "PRO_LICENSE_KEY" in variables:
                DATA["PRO_LOADING"] = True
                if DEBUG_MODE:
                    logger.debug("PRO_LICENSE_KEY detected - enabling PRO loading state")

            # Propagate global settings to service-specific configurations when inheritance applies
            for variable, value in variables.copy().items():
                for service in services:
                    setting = config.get(f"{service}_{variable}", None)
                    if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                        variables[f"{service}_{variable}"] = value
                        if DEBUG_MODE:
                            logger.debug(f"Propagated {variable} to service {service}")

            # Handle PRO license key changes with special notification processing
            with suppress(BaseException):
                if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                    DATA["TO_FLASH"].append({"content": "Checking license key to upgrade.", "type": "success", "save": False})
                    if DEBUG_MODE:
                        logger.debug("PRO license key change detected - added upgrade notification")

            if DEBUG_MODE:
                logger.debug("Executing global configuration edit operation")

            # Execute configuration update with change validation and error handling
            operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)
            if DEBUG_MODE:
                logger.debug(f"Configuration edit result - operation: {operation}, error: {error}")

            # Provide default success message if operation completed without explicit message
            if not error:
                operation = "Global configuration successfully saved."
                if DEBUG_MODE:
                    logger.debug("Configuration update successful - using default success message")

            # Process operation results and provide appropriate user feedback
            if operation:
                if operation.startswith(("Can't", "The database is read-only")):
                    DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                    if DEBUG_MODE:
                        logger.debug(f"Configuration update failed: {operation}")
                else:
                    DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                    DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})
                    if DEBUG_MODE:
                        logger.debug("Configuration update successful - added scheduler notification")

            DATA["RELOADING"] = False
            if DEBUG_MODE:
                logger.debug("update_global_config() background thread completed")

        # Initialize background processing state and start configuration update thread
        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        if DEBUG_MODE:
            logger.debug("Set RELOADING state and starting background configuration update")
        
        Thread(target=update_global_config, args=(variables,)).start()
        if DEBUG_MODE:
            logger.debug("Background thread started for configuration processing")

        # Preserve URL parameters for post-update redirect to maintain user interface state
        arguments = {}
        if request.args.get("mode", "advanced") != "advanced":
            arguments["mode"] = request.args["mode"]
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]
        
        if DEBUG_MODE:
            logger.debug(f"Preserving URL arguments for redirect: {arguments}")

        # Redirect to loading page with preserved parameters and update message
        return redirect(
            url_for(
                "loading",
                next=url_for("global_config.global_config_page") + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}",
                message="Saving global configuration",
            )
        )

    # Handle GET requests by rendering configuration form with current parameters
    mode = request.args.get("mode", "advanced")
    search_type = request.args.get("type", "all")
    
    if DEBUG_MODE:
        logger.debug(f"Rendering configuration form - mode: {mode}, type: {search_type}")
    
    return render_template("global_config.html", mode=mode, type=search_type)
