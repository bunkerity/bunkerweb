from threading import Thread
from time import time
from typing import Literal
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DATA, DB

from app.routes.utils import handle_error, manage_bunkerweb, verify_data_in_form


instances = Blueprint("instances", __name__)


@instances.route("/instances", methods=["GET"])
@login_required
def instances_page():
    return render_template("instances.html", instances=BW_INSTANCES_UTILS.get_instances())


@instances.route("/instances/new", methods=["PUT"])
@login_required
def instances_new():
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

    db_config = BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("API_HTTP_PORT", "API_SERVER_NAME"))

    instance = {
        "hostname": request.form["instance_hostname"].replace("http://", "").replace("https://", ""),
        "name": request.form["instance_name"],
        "port": db_config["API_HTTP_PORT"],
        "server_name": db_config["API_SERVER_NAME"],
        "method": "ui",
    }

    for db_instance in BW_INSTANCES_UTILS.get_instances():
        if db_instance.hostname == instance["hostname"]:
            return handle_error(f"The hostname {instance['hostname']} is already in use.", "instances", True)

    ret = DB.add_instance(**instance)
    if ret:
        return handle_error(f"Couldn't create the instance in the database: {ret}", "instances", True)

    return redirect(url_for("loading", next=url_for("instances.instances_page"), message=f"Creating new instance {instance['hostname']}"))


@instances.route("/instances/<string:instance_hostname>/<string:action>", methods=["POST"])
@login_required
def instances_action(instance_hostname: str, action: Literal["ping", "reload", "stop", "delete"]):  # TODO: see if we can support start and restart
    if action == "delete":
        delete_instance = None
        for instance in BW_INSTANCES_UTILS.get_instances():
            if instance.hostname == instance_hostname:
                delete_instance = instance
                break

        if not delete_instance:
            return handle_error(f"Instance {instance_hostname} not found.", "instances", True)
        if delete_instance.method != "ui":
            return handle_error(f"Instance {instance_hostname} is not a UI instance.", "instances", True)

        ret = DB.delete_instance(instance_hostname)
        if ret:
            return handle_error(f"Couldn't delete the instance in the database: {ret}", "instances", True)
    else:
        DATA["RELOADING"] = True
        DATA["LAST_RELOAD"] = time()
        Thread(
            target=manage_bunkerweb,
            args=("instances", instance_hostname),
            kwargs={"operation": action, "threaded": True},
        ).start()

    return redirect(
        url_for(
            "loading",
            next=url_for("instances.instances_page"),
            message=(
                f"{action.title()}ing"
                if action not in ("delete", "stop")
                else ("Deleting" if action == "delete" else "Stopping") + f" instance {instance_hostname}"
            ),
        )
    )
