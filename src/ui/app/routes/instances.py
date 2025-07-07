from concurrent.futures import ThreadPoolExecutor, as_completed
from re import compile as re_compile
from threading import Thread
from time import time
from typing import Literal
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
    logger.debug("Debug mode enabled for instances module")

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DATA, DB
from app.utils import flash

from app.models.instance import Instance
from app.routes.utils import handle_error, verify_data_in_form


instances = Blueprint("instances", __name__)

ACTIONS = {
    "reload": {"present": "Reloading", "past": "Reloaded"},
    "stop": {"present": "Stopping", "past": "Stopped"},
    "delete": {"present": "Deleting", "past": "Deleted"},
}


# Display comprehensive instances management interface with real-time status monitoring.
# Retrieves active BunkerWeb instances from management utilities and renders interactive
# dashboard with instance health, configuration details, and administrative controls.
@instances.route("/instances", methods=["GET"])
@login_required
def instances_page():
    if DEBUG_MODE:
        logger.debug("instances_page() called - initiating instance discovery and status retrieval")
        logger.debug("Accessing BW_INSTANCES_UTILS for comprehensive instance data")
    
    try:
        instances_data = BW_INSTANCES_UTILS.get_instances()
        if DEBUG_MODE:
            logger.debug(f"Successfully retrieved {len(instances_data)} instances from management utilities")
            logger.debug("Analyzing instance configurations and status information")
            for i, instance in enumerate(instances_data[:5]):  # Log first 5 instances
                logger.debug(f"Instance {i+1}: hostname='{instance.hostname}', name='{instance.name}', method='{instance.method}', port='{getattr(instance, 'port', 'unknown')}'")
            if len(instances_data) > 5:
                logger.debug(f"... and {len(instances_data) - 5} additional instances available")
        
        if DEBUG_MODE:
            logger.debug("Rendering instances.html template with instance data and management controls")
        
        return render_template("instances.html", instances=instances_data)
    except Exception as e:
        logger.exception("Error retrieving instances from BW_INSTANCES_UTILS")
        if DEBUG_MODE:
            logger.debug(f"Failed to retrieve instances: {type(e).__name__}: {e}")
        return handle_error("Failed to retrieve instances", "instances")


# Create and register new BunkerWeb instance with comprehensive validation and networking setup.
# Processes instance creation form with hostname validation, port configuration, and database
# registration while ensuring uniqueness constraints and proper API connectivity parameters.
@instances.route("/instances/new", methods=["POST"])
@login_required
def instances_new():
    if DEBUG_MODE:
        logger.debug("instances_new() called - initiating new instance creation workflow")
        logger.debug(f"Client request from IP: {request.remote_addr}")
        logger.debug(f"Form submission contains fields: {list(request.form.keys())}")
        logger.debug("Validating required parameters and database accessibility")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode - rejecting instance creation")
        return handle_error("Database is in read-only mode", "instances")
    
    verify_data_in_form(
        data={"hostname": None},
        err_message="Missing instance hostname parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )
    verify_data_in_form(
        data={"name": None},
        err_message="Missing instance name parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )

    if DEBUG_MODE:
        logger.debug(f"Processing hostname input: '{request.form['hostname']}'")
        logger.debug(f"Instance display name: '{request.form['name']}'")
        logger.debug("Initiating hostname normalization and port extraction")

    db_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("API_HTTP_PORT", "API_SERVER_NAME"))
    if DEBUG_MODE:
        logger.debug("Retrieved global configuration for API connectivity parameters")
        logger.debug(f"Configuration values - API_HTTP_PORT: '{db_config.get('API_HTTP_PORT', 'default: 5000')}', API_SERVER_NAME: '{db_config.get('API_SERVER_NAME', 'default: bwapi')}'")
        logger.debug("Configuration will be used for instance networking setup")

    port = None
    hostname = request.form["hostname"].replace("http://", "").replace("https://", "").lower().split(":", 1)
    if DEBUG_MODE:
        logger.debug("Hostname processing: removing protocol prefixes and normalizing case")
        logger.debug(f"Hostname components after protocol removal: {hostname}")
    
    if len(hostname) == 2:
        port = hostname[1]
        if DEBUG_MODE:
            logger.debug(f"Port number extracted from hostname: '{port}'")
            logger.debug("Hostname contains embedded port configuration")
    hostname = hostname[0]
    
    if DEBUG_MODE:
        logger.debug(f"Finalized hostname: '{hostname}', port assignment: '{port or 'will use configuration default'}'")
        logger.debug(f"Hostname length: {len(hostname)} characters")

    domain_pattern = re_compile(r"^(?!.*\.\.)[^\s\/:]{1,256}$")
    if not domain_pattern.match(hostname):
        if DEBUG_MODE:
            logger.debug(f"Hostname validation failure: '{hostname}' violates domain naming constraints")
            logger.debug("Pattern requirements: no consecutive dots, no spaces/colons/slashes, 1-256 characters")
        return handle_error(f"Invalid hostname: {hostname}. Please enter a valid domain.", "instances", True)

    if DEBUG_MODE:
        logger.debug("Hostname validation successful - meets domain naming requirements")
        logger.debug("Proceeding with instance configuration assembly")

    instance = {
        "hostname": hostname,
        "name": request.form["name"],
        "port": port or db_config.get("API_HTTP_PORT", "5000"),
        "server_name": db_config.get("API_SERVER_NAME", "bwapi"),
        "method": "ui",
    }
    
    if DEBUG_MODE:
        logger.debug("Instance configuration assembled with networking and management parameters:")
        logger.debug(f"  - Hostname: {instance['hostname']}")
        logger.debug(f"  - Display name: {instance['name']}")
        logger.debug(f"  - API port: {instance['port']}")
        logger.debug(f"  - Server name: {instance['server_name']}")
        logger.debug(f"  - Management method: {instance['method']}")
        logger.debug("Configuration ready for uniqueness validation")

    # Check for duplicate hostnames
    existing_instances = BW_INSTANCES_UTILS.get_instances()
    if DEBUG_MODE:
        logger.debug(f"Uniqueness validation: checking against {len(existing_instances)} existing instances")
        logger.debug("Scanning for hostname conflicts to ensure network uniqueness")
    
    for db_instance in existing_instances:
        if db_instance.hostname == instance["hostname"]:
            if DEBUG_MODE:
                logger.debug(f"Hostname conflict detected: '{instance['hostname']}' already exists in system")
                logger.debug(f"Conflicting instance: name='{db_instance.name}', method='{db_instance.method}'")
            return handle_error(f"The hostname {instance['hostname']} is already in use.", "instances", True)

    if DEBUG_MODE:
        logger.debug("Uniqueness validation passed - no hostname conflicts found")
        logger.debug("Proceeding with database registration")

    ret = DB.add_instance(**instance)
    if ret:
        logger.exception("Failed to create instance in database")
        if DEBUG_MODE:
            logger.debug(f"Database insertion failed: {ret}")
        return handle_error(f"Couldn't create the instance in the database: {ret}", "instances", True)

    if DEBUG_MODE:
        logger.debug(f"Instance {instance['hostname']} created successfully in database")

    flash(f"Instance {instance['hostname']} created successfully.")

    if DEBUG_MODE:
        logger.debug("Redirecting to loading page with instance creation message")

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Creating new instance {instance['hostname']}"))


# Execute comprehensive instance management operations with concurrent processing and state coordination.
# Handles ping connectivity testing, reload operations, stop commands, and deletion with proper
# UI instance filtering, background thread management, and comprehensive error reporting.
@instances.route("/instances/<string:action>", methods=["POST"])
@login_required
def instances_action(action: Literal["ping", "reload", "stop", "delete"]):  # TODO: see if we can support start and restart
    if DEBUG_MODE:
        logger.debug(f"instances_action() called with action: '{action}'")
        logger.debug(f"Request from IP: {request.remote_addr}")
        logger.debug(f"Available actions: {list(ACTIONS.keys())} + ping")
    
    if DB.readonly:
        if DEBUG_MODE:
            logger.debug("Database is in read-only mode - rejecting instance action")
        return handle_error("Database is in read-only mode", "instances")

    verify_data_in_form(
        data={"instances": None},
        err_message=f"Missing instances parameter on /instances/{action}.",
        redirect_url="instances",
        next=True,
    )
    
    instances = request.form["instances"].split(",")
    if DEBUG_MODE:
        logger.debug(f"Target instances: {instances}")
        logger.debug(f"Number of instances to process: {len(instances)}")
    
    if not instances:
        if DEBUG_MODE:
            logger.debug("No instances selected for action")
        return handle_error(f"No instance{'s' if len(instances) > 1 else ''} selected.", "instances", True)
    
    DATA.load_from_file()
    if DEBUG_MODE:
        logger.debug("Loaded DATA from file for action processing")

    if action == "ping":
        if DEBUG_MODE:
            logger.debug("Processing ping action with concurrent execution")
        
        succeed = []
        failed = []

        # Perform connectivity test on single instance with comprehensive error analysis.
        # Establishes database connection, validates instance existence, and tests API
        # connectivity while providing detailed failure diagnostics for troubleshooting.
        def ping_instance(instance):
            if DEBUG_MODE:
                logger.debug(f"Pinging instance: {instance}")
            
            ret = Instance.from_hostname(instance, DB)
            if not ret:
                if DEBUG_MODE:
                    logger.debug(f"Instance {instance} not found in database")
                return {"hostname": instance, "message": f"The instance {instance} does not exist."}
            
            ret = ret.ping()
            if DEBUG_MODE:
                logger.debug(f"Ping result for {instance}: {ret[0][:100]}{'...' if len(ret[0]) > 100 else ''}")
            
            if ret[0].startswith("Can't"):
                if DEBUG_MODE:
                    logger.debug(f"Ping failed for {instance}: {ret[0]}")
                return {"hostname": instance, "message": ret[0]}
            
            if DEBUG_MODE:
                logger.debug(f"Ping successful for {instance}")
            return instance

        with ThreadPoolExecutor() as executor:
            if DEBUG_MODE:
                logger.debug(f"Starting concurrent ping operations for {len(instances)} instances")
            
            future_to_instance = {executor.submit(ping_instance, instance): instance for instance in instances}
            for future in as_completed(future_to_instance):
                instance = future.result()
                if isinstance(instance, dict):
                    failed.append(instance)
                    if DEBUG_MODE:
                        logger.debug(f"Added to failed list: {instance['hostname']}")
                    continue
                succeed.append(instance)
                if DEBUG_MODE:
                    logger.debug(f"Added to success list: {instance}")

        if DEBUG_MODE:
            logger.debug(f"Ping operation completed - Success: {len(succeed)}, Failed: {len(failed)}")

        return jsonify({"succeed": succeed, "failed": failed}), 200
    
    elif action == "delete":
        if DEBUG_MODE:
            logger.debug("Processing delete action with UI instance filtering")
        
        delete_instances = set()
        non_ui_instances = set()
        
        db_instances = DB.get_instances()
        if DEBUG_MODE:
            logger.debug(f"Retrieved {len(db_instances)} instances from database for deletion filtering")
        
        for instance in db_instances:
            if instance["hostname"] in instances:
                if DEBUG_MODE:
                    logger.debug(f"Found instance {instance['hostname']} with method: {instance['method']}")
                
                if instance["method"] != "ui":
                    non_ui_instances.add(instance["hostname"])
                    if DEBUG_MODE:
                        logger.debug(f"Instance {instance['hostname']} is not UI-managed - excluding from deletion")
                    continue
                delete_instances.add(instance["hostname"])
                if DEBUG_MODE:
                    logger.debug(f"Instance {instance['hostname']} added to deletion list")

        for non_ui_instance in non_ui_instances:
            flash(f"Instance {non_ui_instance} is not a UI instance and will not be deleted.", "error")
            if DEBUG_MODE:
                logger.debug(f"Added error flash for non-UI instance: {non_ui_instance}")

        if not delete_instances:
            if DEBUG_MODE:
                logger.debug("No valid UI instances found for deletion")
            return handle_error(
                f"{'All selected instances' if len(delete_instances) > 1 else 'Selected instance'} could not be found or {'are not UI instances' if len(delete_instances) > 1 else 'is not an UI instance'}.",
                "instances",
                True,
            )

        if DEBUG_MODE:
            logger.debug(f"Proceeding with deletion of {len(delete_instances)} UI instances: {list(delete_instances)}")

        ret = DB.delete_instances(delete_instances)
        if ret:
            logger.exception("Failed to delete instances from database")
            if DEBUG_MODE:
                logger.debug(f"Database deletion failed: {ret}")
            return handle_error(f"Couldn't delete the instance{'s' if len(delete_instances) > 1 else ''} in the database: {ret}", "instances", True)
        
        if DEBUG_MODE:
            logger.debug("Instances deleted successfully from database")
        
        flash(f"Instance{'s' if len(delete_instances) > 1 else ''} {', '.join(delete_instances)} Deleted successfully.")
    
    else:
        if DEBUG_MODE:
            logger.debug(f"Processing {action} action with background thread execution")

        # Execute specified management action on individual instance with dynamic method resolution.
        # Validates instance existence, resolves action methods dynamically, handles execution
        # results, and manages flash message queue for user feedback and error reporting.
        def execute_action(instance):
            if DEBUG_MODE:
                logger.debug(f"Executing {action} on instance: {instance}")
            
            ret = Instance.from_hostname(instance, DB)
            if not ret:
                DATA["TO_FLASH"].append({"content": f"The instance {instance} does not exist.", "type": "error"})
                if DEBUG_MODE:
                    logger.debug(f"Instance {instance} not found for {action} action")
                return

            method = getattr(ret, action, None)
            if method is None or not callable(method):
                DATA["TO_FLASH"].append({"content": f"The instance {instance} does not have a {action} method.", "type": "error"})
                if DEBUG_MODE:
                    logger.debug(f"Instance {instance} does not support {action} method")
                return

            if DEBUG_MODE:
                logger.debug(f"Calling {action} method on instance {instance}")

            ret = method()
            if ret.startswith("Can't"):
                DATA["TO_FLASH"].append({"content": ret, "type": "error"})
                if DEBUG_MODE:
                    logger.debug(f"Action {action} failed on {instance}: {ret}")
                return
            
            DATA["TO_FLASH"].append({"content": f"Instance {instance} {ACTIONS[action]['past']} successfully.", "type": "success"})
            if DEBUG_MODE:
                logger.debug(f"Action {action} completed successfully on {instance}")

        # Coordinate concurrent execution of actions across multiple instances with state management.
        # Manages application reload state, orchestrates ThreadPoolExecutor operations, and
        # ensures proper cleanup while maintaining system consistency during bulk operations.
        def execute_actions(instances):
            if DEBUG_MODE:
                logger.debug(f"Background thread started for {action} actions on {len(instances)} instances")
            
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()
            
            if DEBUG_MODE:
                logger.debug("Set RELOADING state - starting concurrent execution")
            
            with ThreadPoolExecutor() as executor:
                executor.map(execute_action, instances)
            
            DATA["RELOADING"] = False
            
            if DEBUG_MODE:
                logger.debug(f"Background thread completed for {action} actions")

        Thread(target=execute_actions, args=(instances,)).start()
        if DEBUG_MODE:
            logger.debug("Started background thread for instance actions")

    if DEBUG_MODE:
        logger.debug(f"Redirecting to loading page with {action} message")

    return redirect(
        url_for(
            "loading",
            next=url_for("instances.instances_page"),
            message=(f"{ACTIONS[action]['present']} instance{'s' if len(instances) > 1 else ''} {', '.join(instances)}"),
        )
    )
