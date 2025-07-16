from concurrent.futures import ThreadPoolExecutor, as_completed
from re import compile as re_compile
from threading import Thread
from time import time
from typing import Literal
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
    title="UI-instances",
    log_file_path="/var/log/bunkerweb/ui.log"
)

logger.debug("Debug mode enabled for UI-instances")

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


@instances.route("/instances", methods=["GET"])
@login_required
def instances_page():
    logger.debug("instances_page() called")
    instances_list = BW_INSTANCES_UTILS.get_instances()
    logger.debug(f"Retrieved {len(instances_list)} instances")
    return render_template("instances.html", instances=instances_list)


@instances.route("/instances/new", methods=["POST"])
@login_required
def instances_new():
    logger.debug("instances_new() called")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking instance creation")
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

    db_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("API_HTTP_PORT", "API_SERVER_NAME"))

    port = None
    hostname = request.form["hostname"].replace("http://", "").replace("https://", "").lower().split(":", 1)
    if len(hostname) == 2:
        port = hostname[1]
    hostname = hostname[0]

    logger.debug(f"Creating new instance: hostname={hostname}, port={port}, name={request.form['name']}")

    domain_pattern = re_compile(r"^(?!.*\.\.)[^\s\/:]{1,256}$")
    if not domain_pattern.match(hostname):
        logger.debug(f"Invalid hostname format: {hostname}")
        return handle_error(f"Invalid hostname: {hostname}. Please enter a valid domain.", "instances", True)

    instance = {
        "hostname": hostname,
        "name": request.form["name"],
        "port": port or db_config.get("API_HTTP_PORT", "5000"),
        "server_name": db_config.get("API_SERVER_NAME", "bwapi"),
        "method": "ui",
    }

    logger.debug(f"Instance configuration: {instance}")

    # Check for hostname conflicts
    existing_instances = BW_INSTANCES_UTILS.get_instances()
    for db_instance in existing_instances:
        if db_instance.hostname == instance["hostname"]:
            logger.debug(f"Hostname conflict detected: {instance['hostname']}")
            return handle_error(f"The hostname {instance['hostname']} is already in use.", "instances", True)

    logger.debug(f"No hostname conflicts found, creating instance in database")
    ret = DB.add_instance(**instance)
    if ret:
        logger.exception(f"Failed to create instance in database: {ret}")
        return handle_error(f"Couldn't create the instance in the database: {ret}", "instances", True)

    logger.info(f"Instance {instance['hostname']} created successfully")
    flash(f"Instance {instance['hostname']} created successfully.")

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Creating new instance {instance['hostname']}"))


@instances.route("/instances/<string:action>", methods=["POST"])
@login_required
def instances_action(action: Literal["ping", "reload", "stop", "delete"]):  # TODO: see if we can support start and restart
    logger.debug(f"instances_action() called with action: {action}")
    
    if DB.readonly:
        logger.debug("Database is in read-only mode, blocking instance action")
        return handle_error("Database is in read-only mode", "instances")

    verify_data_in_form(
        data={"instances": None},
        err_message=f"Missing instances parameter on /instances/{action}.",
        redirect_url="instances",
        next=True,
    )
    
    instances_param = request.form["instances"].split(",")
    if not instances_param:
        logger.debug(f"No instances selected for action: {action}")
        return handle_error(f"No instance{'s' if len(instances_param) > 1 else ''} selected.", "instances", True)
    
    logger.debug(f"Processing {action} action for instances: {instances_param}")
    DATA.load_from_file()

    if action == "ping":
        logger.debug("Starting ping operation")
        succeed = []
        failed = []

        # Ping individual instance and return result with error handling.
        # Tests connectivity and validates instance configuration.
        def ping_instance(instance):
            logger.debug(f"Pinging instance: {instance}")
            ret = Instance.from_hostname(instance, DB)
            if not ret:
                logger.debug(f"Instance {instance} does not exist")
                return {"hostname": instance, "message": f"The instance {instance} does not exist."}
            
            ping_result = ret.ping()
            if ping_result[0].startswith("Can't"):
                logger.debug(f"Ping failed for instance {instance}: {ping_result[0]}")
                return {"hostname": instance, "message": ping_result[0]}
            
            logger.debug(f"Ping successful for instance: {instance}")
            return instance

        with ThreadPoolExecutor() as executor:
            future_to_instance = {executor.submit(ping_instance, instance): instance for instance in instances_param}
            for future in as_completed(future_to_instance):
                instance = future.result()
                if isinstance(instance, dict):
                    failed.append(instance)
                    continue
                succeed.append(instance)

        logger.debug(f"Ping results: {len(succeed)} successful, {len(failed)} failed")
        return jsonify({"succeed": succeed, "failed": failed}), 200
    
    elif action == "delete":
        logger.debug("Starting delete operation")
        delete_instances = set()
        non_ui_instances = set()
        
        for instance in DB.get_instances():
            if instance["hostname"] in instances_param:
                if instance["method"] != "ui":
                    non_ui_instances.add(instance["hostname"])
                    logger.debug(f"Instance {instance['hostname']} is not a UI instance, skipping deletion")
                    continue
                delete_instances.add(instance["hostname"])

        for non_ui_instance in non_ui_instances:
            flash(f"Instance {non_ui_instance} is not a UI instance and will not be deleted.", "error")

        if not delete_instances:
            logger.debug("No valid UI instances found for deletion")
            return handle_error(
                f"{'All selected instances' if len(delete_instances) > 1 else 'Selected instance'} could not be found or {'are not UI instances' if len(delete_instances) > 1 else 'is not an UI instance'}.",
                "instances",
                True,
            )

        logger.debug(f"Deleting {len(delete_instances)} instances: {delete_instances}")
        ret = DB.delete_instances(delete_instances)
        if ret:
            logger.exception(f"Failed to delete instances in database: {ret}")
            return handle_error(f"Couldn't delete the instance{'s' if len(delete_instances) > 1 else ''} in the database: {ret}", "instances", True)
        
        logger.info(f"Instances deleted successfully: {delete_instances}")
        flash(f"Instance{'s' if len(delete_instances) > 1 else ''} {', '.join(delete_instances)} Deleted successfully.")
    
    else:
        logger.debug(f"Starting {action} operation")

        # Execute specified action on instance with comprehensive error handling.
        # Supports reload and stop operations with status reporting.
        def execute_action(instance):
            logger.debug(f"Executing {action} on instance: {instance}")
            ret = Instance.from_hostname(instance, DB)
            if not ret:
                logger.debug(f"Instance {instance} does not exist")
                DATA["TO_FLASH"].append({"content": f"The instance {instance} does not exist.", "type": "error"})
                return

            method = getattr(ret, action, None)
            if method is None or not callable(method):
                logger.debug(f"Instance {instance} does not have {action} method")
                DATA["TO_FLASH"].append({"content": f"The instance {instance} does not have a {action} method.", "type": "error"})
                return

            result = method()
            if result.startswith("Can't"):
                logger.debug(f"Action {action} failed for instance {instance}: {result}")
                DATA["TO_FLASH"].append({"content": result, "type": "error"})
                return
            
            logger.debug(f"Action {action} successful for instance: {instance}")
            DATA["TO_FLASH"].append({"content": f"Instance {instance} {ACTIONS[action]['past']} successfully.", "type": "success"})

        # Execute actions on multiple instances concurrently with status tracking.
        # Uses thread pool for parallel execution and progress monitoring.
        def execute_actions(instances):
            logger.debug(f"Starting parallel execution of {action} on {len(instances)} instances")
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()
            with ThreadPoolExecutor() as executor:
                executor.map(execute_action, instances)
            DATA["RELOADING"] = False
            logger.debug(f"Completed parallel execution of {action}")

        Thread(target=execute_actions, args=(instances_param,)).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("instances.instances_page"),
            message=(f"{ACTIONS[action]['present']} instance{'s' if len(instances_param) > 1 else ''} {', '.join(instances_param)}"),
        )
    )
