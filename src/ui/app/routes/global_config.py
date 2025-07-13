from contextlib import suppress
from threading import Thread
from time import time
from typing import Dict
from os import sep
from os.path import join
from sys import path as sys_path

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from bw_logger import setup_logger

# Initialize bw_logger module
logger = setup_logger(
    title="UI-global-config",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-global-config")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import get_blacklisted_settings

from app.routes.utils import handle_error, wait_applying


global_config = Blueprint("global_config", __name__)


@global_config.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config_page():
    logger.debug("global_config_page() called")
    
    global_config_data = DB.get_config(global_only=True, methods=True)
    logger.debug(f"Retrieved global configuration with {len(global_config_data)} settings")

    if request.method == "POST":
        logger.debug("Processing global configuration update")
        
        if DB.readonly:
            logger.debug("Database is in read-only mode, blocking configuration update")
            return handle_error("Database is in read-only mode", "global_config")
        
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]
        logger.debug(f"Processing {len(variables)} configuration variables")

        # Update global configuration with validation and change detection.
        # Handles variable checking, service propagation, and scheduler notification.
        def update_global_config(variables: Dict[str, str]):
            logger.debug("Starting global configuration update in background thread")
            wait_applying()

            # Edit check fields and remove already existing ones
            config = DB.get_config(methods=True, with_drafts=True)
            services = config["SERVER_NAME"]["value"].split(" ")
            variables_to_check = variables.copy()
            
            logger.debug(f"Found {len(services)} services: {services}")

            unchanged_count = 0
            for variable, value in variables.items():
                setting = config.get(variable, {"value": None, "global": True})
                if setting["global"] and value == setting["value"]:
                    del variables_to_check[variable]
                    unchanged_count += 1

            logger.debug(f"Removed {unchanged_count} unchanged variables, {len(variables_to_check)} to validate")

            variables = BW_CONFIG.check_variables(variables, config, variables_to_check, global_config=True, threaded=True)
            logger.debug(f"Variable validation completed, {len(variables)} variables to apply")

            no_removed_settings = True
            blacklist = get_blacklisted_settings(True)
            for setting in global_config_data:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            if no_removed_settings and not variables_to_check:
                logger.debug("No configuration changes detected")
                content = "The global configuration was not edited because no values were changed."
                DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "PRO_LICENSE_KEY" in variables:
                logger.debug("PRO license key change detected, enabling PRO loading")
                DATA["PRO_LOADING"] = True

            # Propagate global variables to service-specific settings
            propagated_count = 0
            for variable, value in variables.copy().items():
                for service in services:
                    setting = config.get(f"{service}_{variable}", None)
                    if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                        variables[f"{service}_{variable}"] = value
                        propagated_count += 1

            logger.debug(f"Propagated {propagated_count} variables to service-specific settings")

            with suppress(BaseException):
                if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                    logger.debug("PRO license key validation starting")
                    DATA["TO_FLASH"].append({"content": "Checking license key to upgrade.", "type": "success", "save": False})

            logger.debug("Applying global configuration changes")
            operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)

            if not error:
                operation = "Global configuration successfully saved."

            if operation:
                if operation.startswith(("Can't", "The database is read-only")):
                    logger.exception(f"Global configuration update failed: {operation}")
                    DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                else:
                    logger.info("Global configuration updated successfully")
                    DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                    DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})

            DATA["RELOADING"] = False
            logger.debug("Global configuration update thread completed")

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_global_config, args=(variables,)).start()

        # Preserve URL parameters
        arguments = {}
        if request.args.get("mode", "advanced") != "advanced":
            arguments["mode"] = request.args["mode"]
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        query_string = f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}" if arguments else ""
        logger.debug(f"Redirecting to loading page with query: {query_string}")

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config.global_config_page") + query_string,
                message="Saving global configuration",
            )
        )

    # GET request - display configuration page
    mode = request.args.get("mode", "advanced")
    search_type = request.args.get("type", "all")
    logger.debug(f"Rendering global config page with mode={mode}, type={search_type}")
    
    return render_template("global_config.html", mode=mode, type=search_type)
