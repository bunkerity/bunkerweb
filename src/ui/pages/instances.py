from base64 import b64encode
from json import dumps
from threading import Thread
from time import time
from typing import Literal
from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import login_required

from builder.instances import instances_builder  # type: ignore

from pages.utils import handle_error, manage_bunkerweb, verify_data_in_form


instances = Blueprint("instances", __name__)


@instances.route("/instances", methods=["GET"])
@login_required
def instances_page():
    instances = []
    instances_types = set()
    instances_methods = set()
    instances_healths = set()

    for instance in current_app.bw_instances_utils.get_instances():
        instances.append(
            {
                "hostname": instance.hostname,
                "name": instance.name,
                "method": instance.method,
                "health": instance.status,
                "type": instance.type,
                "creation_date": instance.creation_date.strftime("%Y-%m-%d at %H:%M:%S %Z"),
                "last_seen": instance.last_seen.strftime("%Y-%m-%d at %H:%M:%S %Z"),
            }
        )

        instances_types.add(instance.type)
        instances_methods.add(instance.method)
        instances_healths.add(instance.status)

    builder = instances_builder(instances, list(instances_types), list(instances_methods), list(instances_healths))
    return render_template("instances.html", title="Instances", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@instances.route("/instances/new", methods=["PUT"])
@login_required
def instances_new():
    verify_data_in_form(
        data={"csrf_token": None},
        err_message="Missing csrf_token parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )
    verify_data_in_form(
        data={"instance_hostname": None},
        err_message="Missing instance hostname parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )
    verify_data_in_form(
        data={"instance_name": None},
        err_message="Missing instance name parameter on /instances/new.",
        redirect_url="instances",
        next=True,
    )

    db_config = current_app.bw_config.get_config(global_only=True, methods=False, filtered_settings=("API_HTTP_PORT", "API_SERVER_NAME"))

    instance = {
        "hostname": request.form["instance_hostname"].replace("http://", "").replace("https://", ""),
        "name": request.form["instance_name"],
        "port": db_config["API_HTTP_PORT"],
        "server_name": db_config["API_SERVER_NAME"],
        "method": "ui",
    }

    for db_instance in current_app.bw_instances_utils.get_instances():
        if db_instance.hostname == instance["hostname"]:
            return handle_error(f"The hostname {instance['hostname']} is already in use.", "instances", True)

    ret = current_app.db.add_instance(**instance)
    if ret:
        return handle_error(f"Couldn't create the instance in the database: {ret}", "instances", True)

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Creating new instance {instance['hostname']}"))


@instances.route("/instances/<string:instance_hostname>", methods=["DELETE"])
@login_required
def instances_delete(instance_hostname: str):
    verify_data_in_form(
        data={"csrf_token": None},
        err_message="Missing csrf_token parameter on /instances/delete.",
        redirect_url="instances",
        next=True,
    )

    delete_instance = None
    for instance in current_app.bw_instances_utils.get_instances():
        if instance.hostname == instance_hostname:
            delete_instance = instance
            break

    if not delete_instance:
        return handle_error(f"Instance {instance_hostname} not found.", "instances", True)
    if delete_instance.method != "ui":
        return handle_error(f"Instance {instance_hostname} is not a UI instance.", "instances", True)

    ret = current_app.db.delete_instance(instance_hostname)
    if ret:
        return handle_error(f"Couldn't delete the instance in the database: {ret}", "instances", True)

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Deleting instance {instance_hostname}"))


@instances.route("/instances/<string:action>", methods=["POST"])
@login_required
def instances_action(action: Literal["ping", "reload", "stop"]):  # TODO: see if we can support start and restart
    verify_data_in_form(
        data={"instance_hostname": None, "csrf_token": None},
        err_message="Missing instance hostname parameter on /instances/reload.",
        redirect_url="instances",
        next=True,
    )

    current_app.data["RELOADING"] = True
    current_app.data["LAST_RELOAD"] = time()
    Thread(
        target=manage_bunkerweb,
        name=f"Reloading instance {request.form['instance_hostname']}",
        args=("instances", request.form["instance_hostname"]),
        kwargs={"operation": action, "threaded": True},
    ).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("instances.instances_page"),
            message=(f"{action.title()}ing" if action != "stop" else "Stopping") + " instance",
        )
    )
