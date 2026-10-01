from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time
from typing import Literal
from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from common_utils import parse_host  # type: ignore
from app.dependencies import API_CLIENT, BW_CONFIG, BW_INSTANCES_UTILS, CONFIG_TASKS_EXECUTOR, DATA
from app.i18n import LocaleThreadPoolExecutor, translated
from app.api_client import ApiClientError, ApiUnavailableError
from app.form_retry import keep_form, take_form_retry
from app.utils import flash, is_readonly_request, is_ui_api_method

from app.models.instance import Instance
from app.routes.utils import handle_error, verify_data_in_form

instances = Blueprint("instances", __name__)

# One whole sentence per action: the verb is part of the translation, never interpolated.
MISSING_PARAMETER_KEYS = {
    "ping": "instances.flash.missing_instances_parameter_instances_ping",
    "reload": "instances.flash.missing_instances_parameter_instances_reload",
    "stop": "instances.flash.missing_instances_parameter_instances_stop",
    "delete": "instances.flash.missing_instances_parameter_instances_delete",
}
NO_METHOD_KEYS = {
    "reload": "instances.flash.instance_does_not_have_reload_method",
    "stop": "instances.flash.instance_does_not_have_stop_method",
}

ACTIONS = {
    "reload": {"present": "Reloading", "past": "Reloaded"},
    "stop": {"present": "Stopping", "past": "Stopped"},
    "delete": {"present": "Deleting", "past": "Deleted"},
}


@instances.route("/instances", methods=["GET"])
@login_required
def instances_page():
    try:
        instances_list = BW_INSTANCES_UTILS.get_instances()
    except (ApiClientError, ApiUnavailableError):
        flash(translated("instances.flash.could_not_fetch_instances_api") or "Could not fetch instances from the API.", "error")
        instances_list = []

    return render_template("instances.html", instances=instances_list, form_retry=take_form_retry())


@instances.route("/instances/new", methods=["POST"])
@login_required
def instances_new():
    if API_CLIENT.readonly:
        return handle_error(translated("flash.database_read_only_mode") or "Database is in read-only mode", "instances")
    if is_readonly_request(API_CLIENT.readonly):
        return handle_error(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "instances")
    verify_data_in_form(
        data={"hostname": None},
        err_message=translated("instances.flash.missing_instance_hostname_parameter_instances_new") or "Missing instance hostname parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )
    verify_data_in_form(
        data={"name": None},
        err_message=translated("instances.flash.missing_instance_name_parameter_instances_new") or "Missing instance name parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )

    # Fetch API defaults, including new HTTPS-related settings
    db_config = BW_CONFIG.get_config(
        global_only=True,
        methods=False,
        filtered_settings=["API_HTTP_PORT", "API_SERVER_NAME", "API_LISTEN_HTTPS", "API_HTTPS_PORT"],
    )

    # Parse provided hostname, optional scheme and port (robustly)
    # Every refusal below keeps the modal's input for the page to reopen it with (QA-UI M22):
    # the form posts natively, and the redirect used to come back with the modal closed and empty.
    def refuse(message: str):
        keep_form("instance-create", message)
        return handle_error(message, "instances", True)

    raw_input = request.form["hostname"].strip()
    try:
        scheme, hostname, provided_port = parse_host(raw_input)
    except ValueError as e:
        return refuse(f"{e}.")
    explicit_scheme = bool(scheme)
    scheme_https = scheme == "https"

    # Derive defaults
    default_http_port = str(db_config.get("API_HTTP_PORT", "5000"))
    default_listen_https = str(db_config.get("API_LISTEN_HTTPS", "no")).lower() == "yes"
    default_https_port = str(db_config.get("API_HTTPS_PORT", "5443"))

    # Apply explicit scheme rules when user provided it; otherwise use defaults
    listen_https = scheme_https if explicit_scheme else default_listen_https

    # Determine ports based on explicit scheme and provided port
    if explicit_scheme and scheme_https:
        # https://host[:port] -> use provided port for HTTPS
        https_port = str(provided_port) if provided_port else default_https_port
        http_port = default_http_port
    elif explicit_scheme and not scheme_https:
        # http://host[:port] -> use provided port for HTTP
        https_port = default_https_port
        http_port = str(provided_port) if provided_port else default_http_port
    else:
        # host[:port] with no scheme -> treat as HTTP port
        https_port = default_https_port
        http_port = str(provided_port) if provided_port else default_http_port

    instance = {
        "hostname": hostname,
        "name": request.form["name"],
        "port": http_port,
        "server_name": db_config.get("API_SERVER_NAME", "bwapi"),
        "method": "ui",
        "listen_https": listen_https,
        "https_port": https_port,
    }

    for db_instance in BW_INSTANCES_UTILS.get_instances():
        if db_instance.hostname == instance["hostname"]:
            return refuse(
                translated("instances.flash.hostname_already_in_use", hostname=instance["hostname"])
                or f"The hostname {instance['hostname']} is already in use."
            )

    try:
        API_CLIENT.create_instance(**instance)
    except (ApiClientError, ApiUnavailableError) as e:
        return refuse(translated("instances.flash.could_not_create_instance", message=e.message) or f"Couldn't create the instance: {e.message}")

    flash(translated("instances.flash.instance_created_successfully", value=instance["hostname"]) or f"Instance {instance['hostname']} created successfully.")

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Creating new instance {instance['hostname']}"))


# Credential lifecycle. JSON rather than the form/redirect flow the other actions use: the
# enrollment code is shown exactly once, in a modal, and must never end up in a flash message or a
# redirect URL where it would survive in history or the server log.
@instances.route("/instances/<string:hostname>/enroll", methods=["POST"])
@login_required
def instances_enroll(hostname: str):
    if API_CLIENT.readonly:
        return jsonify({"status": "error", "message": "Database is in read-only mode"}), 403
    if is_readonly_request(API_CLIENT.readonly):
        return jsonify({"status": "error", "message": "You do not have the write permission"}), 403
    try:
        data = API_CLIENT.enroll_instance(hostname)
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), 502
    return jsonify({"status": "success", "hostname": hostname, "code": data.get("code")}), 200


@instances.route("/instances/<string:hostname>/rotate", methods=["POST"])
@login_required
def instances_rotate(hostname: str):
    if API_CLIENT.readonly:
        return jsonify({"status": "error", "message": "Database is in read-only mode"}), 403
    if is_readonly_request(API_CLIENT.readonly):
        return jsonify({"status": "error", "message": "You do not have the write permission"}), 403
    try:
        API_CLIENT.rotate_instance_credential(hostname)
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), 502
    return jsonify({"status": "success", "hostname": hostname}), 200


@instances.route("/instances/<string:hostname>/revoke", methods=["POST"])
@login_required
def instances_revoke(hostname: str):
    if API_CLIENT.readonly:
        return jsonify({"status": "error", "message": "Database is in read-only mode"}), 403
    if is_readonly_request(API_CLIENT.readonly):
        return jsonify({"status": "error", "message": "You do not have the write permission"}), 403
    try:
        API_CLIENT.revoke_instance_credential(hostname)
    except (ApiClientError, ApiUnavailableError) as e:
        return jsonify({"status": "error", "message": e.message}), 502
    return jsonify({"status": "success", "hostname": hostname}), 200


@instances.route("/instances/<string:action>", methods=["POST"])
@login_required
def instances_action(action: Literal["ping", "reload", "stop", "delete"]):  # TODO: see if we can support start and restart
    # `ping` reads instance health and changes nothing, so a view-only session keeps it; the
    # other three actions mutate the instances and stay behind both gates.
    if action != "ping":
        if API_CLIENT.readonly:
            return handle_error(translated("flash.database_read_only_mode") or "Database is in read-only mode", "instances")
        if is_readonly_request(API_CLIENT.readonly):
            return handle_error(translated("flash.do_not_have_write_permission") or "You do not have the write permission", "instances")

    verify_data_in_form(
        data={"instances": None},
        err_message=translated(MISSING_PARAMETER_KEYS[action]) or f"Missing instances parameter on /instances/{action}.",
        redirect_url="instances",
        next=True,
    )
    instances = request.form["instances"].split(",")
    if not instances:
        return handle_error(
            translated("instances.flash.no_instance_selected") or "No instance selected.",
            "instances",
            True,
        )
    DATA.load_from_file()

    if action == "ping":
        succeed = []
        failed = []

        def ping_instance(instance):
            ret = Instance.from_hostname(instance, API_CLIENT)
            if not ret:
                return {"hostname": instance, "message": f"The instance {instance} does not exist."}
            ret_tuple = ret.ping()
            msg = ret_tuple[0] if isinstance(ret_tuple, tuple) else ret_tuple
            if not isinstance(msg, str):
                msg = str(msg)
            if msg.startswith("Can't"):
                return {"hostname": instance, "message": msg}
            return instance

        with ThreadPoolExecutor() as executor:
            future_to_instance = {executor.submit(ping_instance, instance): instance for instance in instances}
            for future in as_completed(future_to_instance):
                instance = future.result()
                if isinstance(instance, dict):
                    failed.append(instance)
                    continue
                succeed.append(instance)

        return jsonify({"succeed": succeed, "failed": failed}), 200
    elif action == "delete":
        delete_instances = set()
        non_deletable_instances = set()
        for instance in API_CLIENT.get_instances():
            if instance["hostname"] in instances:
                if not is_ui_api_method(instance["method"]):
                    non_deletable_instances.add(instance["hostname"])
                    continue
                delete_instances.add(instance["hostname"])

        for non_deletable_instance in non_deletable_instances:
            flash(
                translated("instances.flash.instance_not_ui_api_instance_will", non_deletable_instance=non_deletable_instance)
                or f"Instance {non_deletable_instance} is not a UI/API instance and will not be deleted.",
                "error",
            )

        if not delete_instances:
            return handle_error(
                (
                    translated("instances.flash.could_not_found_other" if len(instances) > 1 else "instances.flash.could_not_found_one")
                    or (
                        "All selected instances could not be found or are not UI/API instances."
                        if len(instances) > 1
                        else "Selected instance could not be found or is not a UI/API instance."
                    )
                ),
                "instances",
                True,
            )

        try:
            API_CLIENT.delete_instances(list(delete_instances))
        except (ApiClientError, ApiUnavailableError) as e:
            return handle_error(
                translated(
                    "instances.flash.couldn_t_delete_instances" if len(delete_instances) > 1 else "instances.flash.couldn_t_delete_instance", message=e.message
                )
                or f"Couldn't delete the instance{'s' if len(delete_instances) > 1 else ''}: {e.message}",
                "instances",
                True,
            )
        instance_names = ", ".join(delete_instances)
        if len(delete_instances) > 1:
            flash(translated("instances.flash.instances_deleted", instance=instance_names) or f"Instances {instance_names} Deleted successfully.")
        else:
            flash(translated("instances.flash.instance_deleted", instance=instance_names) or f"Instance {instance_names} Deleted successfully.")
    else:

        def execute_action(instance):
            ret = Instance.from_hostname(instance, API_CLIENT)
            if not ret:
                DATA["TO_FLASH"].append(
                    {
                        "content": translated("instances.flash.instance_does_not_exist", instance=instance) or f"The instance {instance} does not exist.",
                        "type": "error",
                    }
                )
                return

            method = getattr(ret, action, None)
            if method is None or not callable(method):
                DATA["TO_FLASH"].append(
                    {
                        "content": translated(NO_METHOD_KEYS[action], instance=instance) or f"The instance {instance} does not have a {action} method.",
                        "type": "error",
                    }
                )
                return

            ret = method()
            if str(ret).startswith("Can't"):
                DATA["TO_FLASH"].append({"content": ret, "type": "error"})
                return
            message = (
                translated("instances.flash.instance_reloaded", instance=instance)
                if action == "reload"
                else translated("instances.flash.instance_stopped", instance=instance)
            )
            DATA["TO_FLASH"].append(
                {
                    "content": message or f"Instance {instance} {ACTIONS[action]['past']} successfully.",
                    "type": "success",
                }
            )

        def execute_actions(instances):
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()
            # Nested pool: LocaleThreadPoolExecutor hands this task's forced locale to each flash.
            with LocaleThreadPoolExecutor() as executor:
                executor.map(execute_action, instances)
            DATA["RELOADING"] = False

        CONFIG_TASKS_EXECUTOR.submit(execute_actions, instances)

    return redirect(
        url_for(
            "loading",
            next=url_for("instances.instances_page"),
            message=(f"{ACTIONS[action]['present']} instance{'s' if len(instances) > 1 else ''} {', '.join(instances)}"),
        )
    )
