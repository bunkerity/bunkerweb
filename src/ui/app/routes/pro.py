from datetime import datetime
from threading import Thread
from time import time
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
    title="UI-pro",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-pro")

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.routes.utils import get_remain, handle_error, verify_data_in_form, wait_applying
from app.utils import flash


pro = Blueprint("pro", __name__)


@pro.route("/pro", methods=["GET"])
@login_required
def pro_page():
    logger.debug("pro_page() called")
    online_services = 0
    draft_services = 0
    for service in DB.get_services(with_drafts=True):
        if service["is_draft"]:
            draft_services += 1
            continue
        online_services += 1

    logger.debug(f"Services count - online: {online_services}, draft: {draft_services}")

    metadata = DB.get_metadata()
    current_day = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    pro_expires_in = "Unknown"
    if metadata["pro_expire"]:
        exp = (metadata["pro_expire"].astimezone() - current_day).total_seconds()
        remain = ("Unknown", "Unknown") if exp <= 0 else get_remain(exp)
        pro_expires_in = remain[0]
        logger.debug(f"PRO license expires in: {pro_expires_in}")
    else:
        logger.debug("No PRO license expiration date found")

    return render_template(
        "pro.html",
        online_services=online_services,
        draft_services=draft_services,
        pro_expires_in=pro_expires_in,
        pro_license_key=BW_CONFIG.get_config(global_only=True, methods=False, with_drafts=True, filtered_settings=("PRO_LICENSE_KEY",)).get(
            "PRO_LICENSE_KEY", ""
        ),
    )


@pro.route("/pro/key", methods=["POST"])
@login_required
def pro_key():
    logger.debug("pro_key() called")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking PRO key update")
        return handle_error("Database is in read-only mode", "pro")

    verify_data_in_form(
        data={"PRO_LICENSE_KEY": None},
        err_message="Missing license key parameter on /pro/key.",
        redirect_url="pro",
        next=True,
    )
    license_key = request.form["PRO_LICENSE_KEY"]
    if not license_key:
        logger.debug("Empty license key provided")
        return handle_error("Invalid license key", "pro")

    logger.debug("Validating license key and checking for changes")
    global_config = DB.get_config(global_only=True)
    global_config_methods = DB.get_config(global_only=True, methods=True)
    variables = BW_CONFIG.check_variables(
        global_config | {"PRO_LICENSE_KEY": license_key},
        global_config_methods,
        {"PRO_LICENSE_KEY": license_key},
        global_config=True,
    )

    if not variables:
        logger.debug("License key is same as current one")
        flash("The license key is the same as the current one.", "warning")
        return redirect(url_for("pro.pro_page"))

    logger.debug("License key change detected, starting update process")
    DATA.load_from_file()

    # Update license key in background thread with comprehensive error handling.
    # Validates key and triggers scheduler to apply changes and download PRO plugins.
    def update_license_key(variables: dict):
        logger.debug("Starting license key update in background thread")
        wait_applying()

        operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)
        logger.debug(f"License key update result - operation: {operation}, error: {error}")

        if not error:
            operation = "The PRO license key was updated successfully."

        if operation:
            if operation.startswith(("Can't", "The database is read-only")):
                logger.debug(f"License key update failed: {operation}")
                DATA["TO_FLASH"].append({"content": operation, "type": "error"})
            else:
                logger.debug("License key update successful")
                DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                DATA["TO_FLASH"].append(
                    {"content": "The Scheduler will be in charge of applying the changes and downloading the PRO plugins.", "type": "success", "save": False}
                )

        DATA["RELOADING"] = False
        logger.debug("License key update thread completed")

    DATA.update(
        {
            "RELOADING": True,
            "LAST_RELOAD": time(),
            "CONFIG_CHANGED": True,
            "PRO_LOADING": True,
        }
    )
    logger.debug("Starting license key update thread")
    flash("Checking license key.")
    Thread(target=update_license_key, args=(variables,)).start()
    return redirect(
        url_for(
            "loading",
            next=url_for("pro.pro_page"),
            message="Updating license key",
        )
    )
