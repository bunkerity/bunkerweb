from contextlib import suppress
from threading import Thread
from time import time
from typing import Dict

from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import get_blacklisted_settings

from app.routes.utils import handle_error, wait_applying


global_config = Blueprint("global_config", __name__)


@global_config.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config_page():
    global_config = DB.get_config(global_only=True, methods=True)

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "global_config")
        DATA.load_from_file()

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        def update_global_config(variables: Dict[str, str]):
            wait_applying()

            # Edit check fields and remove already existing ones
            config = DB.get_config(methods=True, with_drafts=True)
            services = config["SERVER_NAME"]["value"].split(" ")
            variables_to_check = variables.copy()

            for variable, value in variables.items():
                setting = config.get(variable, {"value": None, "global": True})
                if setting["global"] and value == setting["value"]:
                    del variables_to_check[variable]

            variables = BW_CONFIG.check_variables(variables, config, variables_to_check, global_config=True, threaded=True)

            no_removed_settings = True
            blacklist = get_blacklisted_settings(True)
            for setting in global_config:
                if setting not in blacklist and setting not in variables:
                    no_removed_settings = False
                    break

            if no_removed_settings and not variables_to_check:
                content = "The global configuration was not edited because no values were changed."
                DATA["TO_FLASH"].append({"content": content, "type": "warning"})
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
                    DATA["TO_FLASH"].append({"content": "Checking license key to upgrade.", "type": "success", "save": False})

            operation, error = BW_CONFIG.edit_global_conf(variables, check_changes=True)

            if not error:
                operation = "Global configuration successfully saved."

            if operation:
                if operation.startswith(("Can't", "The database is read-only")):
                    DATA["TO_FLASH"].append({"content": operation, "type": "error"})
                else:
                    DATA["TO_FLASH"].append({"content": operation, "type": "success"})
                    DATA["TO_FLASH"].append({"content": "The Scheduler will be in charge of applying the changes.", "type": "success", "save": False})

            DATA["RELOADING"] = False

        DATA.update({"RELOADING": True, "LAST_RELOAD": time(), "CONFIG_CHANGED": True})
        Thread(target=update_global_config, args=(variables,)).start()

        arguments = {}
        if request.args.get("mode", "advanced") != "advanced":
            arguments["mode"] = request.args["mode"]
        if request.args.get("type", "all") != "all":
            arguments["type"] = request.args["type"]

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config.global_config_page") + f"?{'&'.join([f'{k}={v}' for k, v in arguments.items()])}",
                message="Saving global configuration",
            )
        )
    elif request.args.get("as_json", "false").lower() == "true":
        return global_config

    mode = request.args.get("mode", "advanced")
    search_type = request.args.get("type", "all")
    return render_template("global_config.html", mode=mode, type=search_type)
