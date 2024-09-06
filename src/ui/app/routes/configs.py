from copy import deepcopy
from os.path import join, sep

from bs4 import BeautifulSoup
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB  # TODO: remember about DATA.load_from_file()
from app.utils import LOGGER, PLUGIN_NAME_RX, path_to_dict

from app.routes.utils import handle_error, verify_data_in_form


configs = Blueprint("configs", __name__)


@configs.route("/configs", methods=["GET", "POST"])
@login_required
def configs_page():  # TODO: refactor this function
    db_configs = DB.get_custom_configs()

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "configs")

        operation = ""

        verify_data_in_form(
            data={"operation": ("new", "edit", "delete"), "type": "file", "path": None},
            err_message="Invalid operation parameter on /configs.",
            redirect_url="configs",
            next=True,
        )

        # Check variables
        variables = deepcopy(request.form.to_dict())
        del variables["csrf_token"]

        if variables["type"] != "file":
            return handle_error("Invalid type parameter on /configs.", "configs", True)

        # TODO: revamp this to use a path but a form to edit the content

        # operation = BW_CUSTOM_CONFIGS.check_path(variables["path"])

        # if operation:
        #     return handle_error(operation, "configs", True)

        old_name = variables.get("old_name", "").replace(".conf", "")
        name = variables.get("name", old_name).replace(".conf", "")
        path_exploded = variables["path"].split(sep)
        service_id = (path_exploded[5] if len(path_exploded) > 6 else None) or None
        root_dir = path_exploded[4].replace("-", "_").lower()

        if not old_name and not name:
            return handle_error("Missing name parameter on /configs.", "configs", True)

        index = -1
        for i, db_config in enumerate(db_configs):
            if db_config["type"] == root_dir and db_config["name"] == name and db_config["service_id"] == service_id:
                if request.form["operation"] == "new":
                    return handle_error(f"Config {name} already exists{f' for service {service_id}' if service_id else ''}", "configs", True)
                elif db_config["method"] not in ("ui", "manual"):
                    return handle_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it was not created by the UI or manually",
                        "configs",
                        True,
                    )
                index = i
                break

        # New or edit a config
        if request.form["operation"] in ("new", "edit"):
            if not PLUGIN_NAME_RX.match(name):
                return handle_error(
                    f"Invalid {variables['type']} name. (Can only contain numbers, letters, underscores, dots and hyphens (min 4 characters and max 64))",
                    "configs",
                    True,
                )

            content = BeautifulSoup(variables["content"], "html.parser").get_text()

            if request.form["operation"] == "new":
                db_configs.append({"type": root_dir, "name": name, "service_id": service_id, "data": content, "method": "ui"})
                operation = f"Created config {name}{f' for service {service_id}' if service_id else ''}"
            elif request.form["operation"] == "edit":
                if index == -1:
                    return handle_error(
                        f"Can't edit config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True
                    )

                if old_name != name:
                    db_configs[index]["name"] = name
                elif db_configs[index]["data"] == content:
                    return handle_error(
                        f"Config {name} was not edited because no values were changed{f' for service {service_id}' if service_id else ''}",
                        "configs",
                        True,
                    )

                db_configs[index]["data"] = content
                operation = f"Edited config {name}{f' for service {service_id}' if service_id else ''}"

        # Delete a config
        elif request.form["operation"] == "delete":
            if index == -1:
                return handle_error(f"Can't delete config {name}{f' for service {service_id}' if service_id else ''} because it doesn't exist", "configs", True)

            del db_configs[index]
            operation = f"Deleted config {name}{f' for service {service_id}' if service_id else ''}"

        error = DB.save_custom_configs([config for config in db_configs if config["method"] == "ui"], "ui")
        if error:
            LOGGER.error(f"Could not save custom configs: {error}")
            return handle_error("Couldn't save custom configs", "configs", True)

        DATA["CONFIG_CHANGED"] = True

        flash(operation)

        return redirect(url_for("loading", next=url_for("configs.configs_page"), message="Update configs"))

    return render_template(
        "configs.html",
        folders=[
            path_to_dict(
                join(sep, "etc", "bunkerweb", "configs"),
                db_data=db_configs,
                services=BW_CONFIG.get_config(global_only=True, methods=False, filtered_settings=("SERVER_NAME",)).get("SERVER_NAME", "").split(" "),
            )
        ],
    )
