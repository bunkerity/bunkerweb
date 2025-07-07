from datetime import datetime
from threading import Thread
from time import time
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
    logger.debug("Debug mode enabled for pro module")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.routes.utils import get_remain, handle_error, verify_data_in_form, wait_applying
from app.utils import flash


pro = Blueprint("pro", __name__)


# Display comprehensive BunkerWeb PRO dashboard with service analytics and license management.
# Calculates service statistics, validates PRO license expiration, and renders management interface.
@pro.route("/pro", methods=["GET"])
@login_required
def pro_page():
    if DEBUG_MODE:
        logger.debug("pro_page() called")
    
    online_services = 0
    draft_services = 0
    if DEBUG_MODE:
        logger.debug("Starting service count analysis")
    
    for service in DB.get_services(with_drafts=True):
        if service["is_draft"]:
            draft_services += 1
            continue
        online_services += 1
    
    if DEBUG_MODE:
        logger.debug(f"Service counts - online: {online_services}, draft: {draft_services}")

    metadata = DB.get_metadata()
    if DEBUG_MODE:
        logger.debug(f"Retrieved metadata with PRO expire: {metadata.get('pro_expire') is not None}")
    
    current_day = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    pro_expires_in = "Unknown"
    if metadata["pro_expire"]:
        exp = (metadata["pro_expire"].astimezone() - current_day).total_seconds()
        remain = ("Unknown", "Unknown") if exp <= 0 else get_remain(exp)
        pro_expires_in = remain[0]
        if DEBUG_MODE:
            logger.debug(f"PRO license expires in: {pro_expires_in}")
    elif DEBUG_MODE:
        logger.debug("No PRO expiration date found in metadata")

    if DEBUG_MODE:
        logger.debug("Retrieving PRO license key from global configuration")

    if DEBUG_MODE:
        logger.debug(f"PRO license key present: {bool(BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=('PRO_LICENSE_KEY',)).get('PRO_LICENSE_KEY', ''))}")

    return render_template(
        "pro.html",
        online_services=online_services,
        draft_services=draft_services,
        pro_expires_in=pro_expires_in,
        pro_license_key=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("PRO_LICENSE_KEY",)).get(
            "PRO_LICENSE_KEY", ""
        ),
    )


# Process and validate PRO license key updates with comprehensive error handling.
# Performs license validation, configuration updates, and asynchronous plugin management.
@pro.route("/pro/key", methods=["POST"])
@login_required
def pro_key():
    if DEBUG_MODE:
        logger.debug("pro_key() called")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode")
        return handle_error("Database is in read-only mode", "pro")

    verify_data_in_form(
        data={"PRO_LICENSE_KEY": None},
        err_message="Missing license key parameter on /pro/key.",
        redirect_url="pro",
        next=True,
    )
    license_key = request.form["PRO_LICENSE_KEY"]
    if not license_key:
        if DEBUG_MODE:
            logger.debug("Empty license key provided")
        return handle_error("Invalid license key", "pro")

    if DEBUG_MODE:
        logger.debug(f"Processing license key validation and configuration check (length: {len(license_key)})")

    global_config = DB.get_config(global_only=True)
    global_config_methods = DB.get_config(global_only=True, methods=True)
    if DEBUG_MODE:
        logger.debug("Retrieved global configuration for license key validation")
    
    variables = BW_CONFIG.check_variables(
        global_config | {"PRO_LICENSE_KEY": license_key},
        global_config_methods,
        {"PRO_LICENSE_KEY": license_key},
        global_config=True,
    )
    
    if DEBUG_MODE:
        logger.debug(f"License key validation result: {bool(variables)} - will proceed with update: {bool(variables)}")

    if not variables:
        if DEBUG_MODE:
            logger.debug("License key validation failed - same as current key")
        flash("The license key is the same as the current one.", "warning")
        return redirect(url_for("pro.pro_page"))

    DATA.load_from_file()
    if DEBUG_MODE:
        logger.debug("Loaded application DATA from file for license key processing")

    # Execute PRO license key configuration update in separate thread with scheduler coordination.
    # Manages global configuration changes, plugin downloads, and provides user feedback.
    def update_license_key(variables: dict):
        if DEBUG_MODE:
            logger.debug("update_license_key() background thread initiated for configuration update")
        
        wait_applying()
        if DEBUG_MODE:
            logger.debug("Completed wait_applying() - proceeding with configuration edit")

        operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)
        
        if DEBUG_MODE:
            logger.debug(f"Global configuration edit completed - operation: {operation}, error: {error}")

        if not error:
            operation = "The PRO license key was updated successfully."
            if DEBUG_MODE:
                logger.debug("License key update successful - setting success message")

        if operation:
            if operation.startswith(("Can't", "The database is read-only")):
                DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                if DEBUG_MODE:
                    logger.debug(f"Added error flash message to DATA queue: {operation}")
            else:
                DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                DATA["TO_FLASH"].append(
                    {"content": "The Scheduler will be in charge of applying the changes and downloading the PRO plugins.", "type": "success", "save": False}
                )
                if DEBUG_MODE:
                    logger.debug("Added success flash messages for license key update and scheduler notification")

        DATA["RELOADING"] = False
        if DEBUG_MODE:
            logger.debug("update_license_key() background thread completed successfully")

    if DEBUG_MODE:
        logger.debug("Setting application state for license key processing and PRO plugin management")
    
    DATA.update(
        {
            "RELOADING": True,
            "LAST_RELOAD": time(),
            "CONFIG_CHANGED": True,
            "PRO_LOADING": True,
        }
    )
    
    if DEBUG_MODE:
        logger.debug("Updated DATA state - RELOADING, CONFIG_CHANGED, and PRO_LOADING flags set")
    
    flash("Checking license key.")
    Thread(target=update_license_key, args=(variables,)).start()
    
    if DEBUG_MODE:
        logger.debug("License key validation thread started - redirecting to loading page with update message")
    
    return redirect(
        url_for(
            "loading",
            next=url_for("pro.pro_page"),
            message="Updating license key",
        )
    )
