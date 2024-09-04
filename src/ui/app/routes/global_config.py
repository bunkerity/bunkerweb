from contextlib import suppress
from threading import Thread
from time import time

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB

from app.routes.utils import handle_error, manage_bunkerweb, wait_applying


global_config = Blueprint("global_config", __name__)


@global_config.route("/global-config", methods=["GET", "POST"])
@login_required
def global_config_page():
    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "global_config")

        # Check variables
        variables = request.form.to_dict().copy()
        del variables["csrf_token"]

        # Edit check fields and remove already existing ones
        config = DB.get_config(methods=True, with_drafts=True)
        services = config["SERVER_NAME"]["value"].split(" ")
        for variable, value in variables.copy().items():
            setting = config.get(variable, {"value": None, "global": True})
            if setting["global"] and value == setting["value"]:
                del variables[variable]
                continue

        variables = BW_CONFIG.check_variables(variables, config)

        if not variables:
            return handle_error("The global configuration was not edited because no values were changed.", "global_config", True)

        for variable, value in variables.copy().items():
            for service in services:
                setting = config.get(f"{service}_{variable}", None)
                if setting and setting["global"] and (setting["value"] != value or setting["value"] == config.get(variable, {"value": None})["value"]):
                    variables[f"{service}_{variable}"] = value

        db_metadata = DB.get_metadata()

        def update_global_config(threaded: bool = False):
            wait_applying()

            manage_bunkerweb("global_config", variables, threaded=threaded)

        if "PRO_LICENSE_KEY" in variables:
            DATA["PRO_LOADING"] = True

        if any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()
            Thread(target=update_global_config, args=(True,)).start()
        else:
            update_global_config()

        DATA["CONFIG_CHANGED"] = True

        with suppress(BaseException):
            if config["PRO_LICENSE_KEY"]["value"] != variables["PRO_LICENSE_KEY"]:
                flash("Checking license key to upgrade.", "success")

        return redirect(
            url_for(
                "loading",
                next=url_for("global_config.global_config_page"),
                message="Saving global configuration",
            )
        )

    keywords = request.args.get("keywords", "")
    search_type = request.args.get("type", "all")
    global_config = DB.get_config(global_only=True, methods=True)
    plugins = BW_CONFIG.get_plugins()
    return render_template("global_config.html", config=global_config, plugins=plugins, keywords=keywords, type=search_type)
