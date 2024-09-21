from contextlib import suppress
from re import match
from threading import Thread
from time import time
from typing import Dict

from flask import Blueprint, flash as flask_flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import flash

from app.routes.utils import handle_error, manage_bunkerweb, wait_applying


global_config = Blueprint("global_config", __name__)


@global_config.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config_page():
    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "global_config")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        def update_global_config(variables: Dict[str, str], threaded: bool = False):
            wait_applying()

            # Edit check fields and remove already existing ones
            config = DB.get_config(methods=True, with_drafts=True, filtered_settings=list(variables.keys()))
            services = config["SERVER_NAME"]["value"].split(" ")
            ignored_multiples = set()

            for variable, value in variables.copy().items():
                setting = config.get(variable, {"value": None, "global": True})
                if setting["global"] and value == setting["value"]:
                    if match(r"^.+_\d+$", variable):
                        ignored_multiples.add(variable)
                    del variables[variable]
                    continue

            variables = BW_CONFIG.check_variables(variables, config, global_config=True, ignored_multiples=ignored_multiples, threaded=threaded)

            if not variables:
                content = "The global configuration was not edited because no values were changed."
                if threaded:
                    DATA["TO_FLASH"].append({"content": content, "type": "warning"})
                else:
                    flash(content, "warning")
                DATA.update({"RELOADING": False, "CONFIG_CHANGED": False})
                return

            if "PRO_LICENSE_KEY" in variables:
                DATA["PRO_LOADING"] = True

            for variable, value in variables.copy().items():
                for service in services:
                    setting = config.get(f"{service}_{variable}", None)
                    if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                        variables[f"{service}_{variable}"] = value

            with suppress(BaseException):
                if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                    if threaded:
                        DATA["TO_FLASH"].append({"content": "Checking license key to upgrade.", "type": "success", "save": False})
                    else:
                        flask_flash("Checking license key to upgrade.", "success")

            manage_bunkerweb("global_config", variables, threaded=threaded)

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_global_config, args=(variables, True)).start()

        arguments = {}
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config.global_config_page") + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}",
                message="Saving global configuration",
            )
        )

    search_type = request.args.get("type", "all")
    global_config = DB.get_config(global_only=True, methods=True)
    return render_template("global_config.html", config=global_config, type=search_type)
