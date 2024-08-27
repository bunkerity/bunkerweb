from base64 import b64encode
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from threading import Thread
from time import sleep, time
from typing import Any, Dict, Optional, Tuple, Union

from flask import Response, flash, redirect, request, session, url_for
from qrcode.main import QRCode
from regex import compile as re_compile

from app.models.instance import Instance

from app.dependencies import BW_CONFIG, DATA, DB
from app.utils import LOGGER


LOG_RX = re_compile(r"^(?P<date>\d+/\d+/\d+\s\d+:\d+:\d+)\s\[(?P<level>[a-z]+)\]\s\d+#\d+:\s(?P<message>[^\n]+)$")
REVERSE_PROXY_PATH = re_compile(r"^(?P<host>https?://.{1,255}(:((6553[0-5])|(655[0-2]\d)|(65[0-4]\d{2})|(6[0-4]\d{3})|([1-5]\d{4})|([0-5]{0,5})|(\d{1,4})))?)$")
PLUGIN_KEYS = ["id", "name", "description", "version", "stream", "settings"]
PLUGIN_ID_RX = re_compile(r"^[\w_-]{1,64}$")


def wait_applying():
    current_time = datetime.now().astimezone()
    ready = False
    while not ready and (datetime.now().astimezone() - current_time).seconds < 120:
        db_metadata = DB.get_metadata()
        if isinstance(db_metadata, str):
            LOGGER.error(f"An error occurred when checking for changes in the database : {db_metadata}")
        elif not any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            ready = True
            continue
        else:
            LOGGER.warning("Scheduler is already applying a configuration, retrying in 1s ...")
        sleep(1)

    if not ready:
        LOGGER.error("Too many retries while waiting for scheduler to apply configuration...")


# TODO: Find a more elegant way to handle this
def manage_bunkerweb(method: str, *args, operation: str = "reloads", is_draft: bool = False, was_draft: bool = False, threaded: bool = False) -> int:
    # Do the operation
    error = 0

    if "TO_FLASH" not in DATA:
        DATA["TO_FLASH"] = []

    if method == "services":
        if operation == "new":
            operation, error = BW_CONFIG.new_service(args[0], is_draft=is_draft)
        elif operation == "edit":
            operation, error = BW_CONFIG.edit_service(args[1], args[0], check_changes=(was_draft != is_draft or not is_draft), is_draft=is_draft)
        elif operation == "delete":
            operation, error = BW_CONFIG.delete_service(args[2], check_changes=(was_draft != is_draft or not is_draft))
    elif method == "global_config":
        operation, error = BW_CONFIG.edit_global_conf(args[0], check_changes=True)

    if operation == "reload":
        instance = Instance.from_hostname(args[0], DB)
        if instance:
            operation = instance.reload()
        else:
            operation = "The instance does not exist."
    elif operation == "start":
        instance = Instance.from_hostname(args[0], DB)
        if instance:
            operation = instance.start()
        else:
            operation = "The instance does not exist."
    elif operation == "stop":
        instance = Instance.from_hostname(args[0], DB)
        if instance:
            operation = instance.stop()
        else:
            operation = "The instance does not exist."
    elif operation == "restart":
        instance = Instance.from_hostname(args[0], DB)
        if instance:
            operation = instance.restart()
        else:
            operation = "The instance does not exist."
    elif operation == "ping":
        instance = Instance.from_hostname(args[0], DB)
        if instance:
            operation = instance.ping()[0]
        else:
            operation = "The instance does not exist."
    elif not error:
        operation = "The scheduler will be in charge of applying the changes."

    if operation:
        if isinstance(operation, list):
            for op in operation:
                DATA["TO_FLASH"].append({"content": f"Reload failed for the instance {op}", "type": "error"})
        elif operation.startswith(("Can't", "The database is read-only")):
            DATA["TO_FLASH"].append({"content": operation, "type": "error"})
        else:
            DATA["TO_FLASH"].append({"content": operation, "type": "success"})

    if not threaded:
        for f in DATA.get("TO_FLASH", []):
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

            if "flash_messages" in session:
                session["flash_messages"].append((f["content"], f["type"], datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")))

        DATA["TO_FLASH"] = []

    DATA["RELOADING"] = False

    return error


def verify_data_in_form(
    data: Optional[Dict[str, Union[Tuple, Any]]] = None, err_message: str = "", redirect_url: str = "", next: bool = False
) -> Union[bool, Response]:
    if not request.form:
        return handle_error("Invalid request", redirect_url, next, "error")

    LOGGER.debug(f"Verifying data in form: {data}")
    LOGGER.debug(f"Request form: {request.form}")

    # Loop on each key in data
    for key, values in (data or {}).items():
        if key not in request.form:
            return handle_error(f"Missing {key} in form", redirect_url, next, "error")

        # Case we want to only check if key is in form, we can skip the values check by setting values to falsy value
        if not values:
            continue

        if request.form[key] not in values:
            return handle_error(err_message, redirect_url, next, "error")

    return True


def handle_error(err_message: str = "", redirect_url: str = "", next: bool = False, log: Union[bool, str] = False) -> Union[bool, Response]:
    """Handle error message, flash it, log it if needed and redirect to redirect_url if provided or return False."""
    flash(err_message, "error")

    if log == "error":
        LOGGER.error(err_message)

    if log == "exception":
        LOGGER.exception(err_message)

    if not redirect_url:
        return False

    if next:
        return redirect(url_for("loading", next=url_for(f"{redirect_url}.{redirect_url}_page")))

    return redirect(url_for(f"{redirect_url}.{redirect_url}_page"))


def error_message(msg: str):
    LOGGER.error(msg)
    return {"status": "ko", "message": msg}


def get_b64encoded_qr_image(data: str):
    qr = QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b5577", back_color="white")
    buffered = BytesIO()
    img.save(buffered)
    return b64encode(buffered.getvalue()).decode("utf-8")


def get_remain(seconds):
    term = "minute(s)"
    years, seconds = divmod(seconds, 60 * 60 * 24 * 365)
    months, seconds = divmod(seconds, 60 * 60 * 24 * 30)
    while months >= 12:
        years += 1
        months -= 12
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    time_parts = []
    if years > 0:
        term = "year(s)"
        time_parts.append(f"{int(years)} year{'' if years == 1 else 's'}")
    if months > 0:
        if term == "minute(s)":
            term = "month(s)"
        time_parts.append(f"{int(months)} month{'' if months == 1 else 's'}")
    if days > 0:
        if term == "minute(s)":
            term = "day(s)"
        time_parts.append(f"{int(days)} day{'' if days == 1 else 's'}")
    if hours > 0:
        if term == "minute(s)":
            term = "hour(s)"
        time_parts.append(f"{int(hours)} hour{'' if hours == 1 else 's'}")
    if minutes > 0:
        time_parts.append(f"{int(minutes)} minute{'' if minutes == 1 else 's'}")

    if len(time_parts) > 1:
        time_parts[-1] = f"and {time_parts[-1]}"

    return " ".join(time_parts), term


def get_service_data(page_name: str):

    verify_data_in_form(
        data={"csrf_token": None},
        err_message=f"Missing csrf_token parameter on /{page_name}.",
        redirect_url="services",
    )

    verify_data_in_form(
        data={"operation": None},
        err_message=f"Missing operation parameter on /{page_name}.",
        redirect_url="services",
    )

    verify_data_in_form(
        data={"operation": ("edit", "new", "delete")},
        err_message="Invalid operation parameter on /{page_name}.",
        redirect_url="services",
    )

    config = DB.get_config(methods=True, with_drafts=True)
    # Check variables
    variables = deepcopy(request.form.to_dict())
    mode = variables.pop("mode", None)

    del variables["csrf_token"]
    operation = variables.pop("operation")

    # Delete custom client variables
    variables.pop("SECURITY_LEVEL", None)

    # Get server name and old one
    old_server_name = ""
    if variables.get("OLD_SERVER_NAME"):
        old_server_name = variables.get("OLD_SERVER_NAME", "")
        del variables["OLD_SERVER_NAME"]

    server_name = variables["SERVER_NAME"].split(" ")[0] if "SERVER_NAME" in variables else old_server_name

    # Get draft if exists
    was_draft = config.get(f"{server_name}_IS_DRAFT", {"value": "no"})["value"] == "yes"
    is_draft = was_draft if not variables.get("is_draft") else variables.get("is_draft") == "yes"
    if variables.get("is_draft"):
        del variables["is_draft"]

    is_draft_unchanged = is_draft == was_draft

    # Get all variables starting with custom_config and delete them from variables
    custom_configs = []
    config_types = (
        "http",
        "stream",
        "server-http",
        "server-stream",
        "default-server-http",
        "default-server-stream",
        "modsec",
        "modsec-crs",
        "crs-plugins-before",
        "crs-plugins-after",
    )

    for variable in variables:
        if variable.startswith("custom_config_"):
            custom_configs.append(variable)
            del variables[variable]

    # custom_config variable format is custom_config_<type>_<filename>
    # we want a list of dict with each dict containing type, filename, action and server name
    # after getting all configs, we want to save them after the end of current service action
    # to avoid create config for none existing service or in case editing server name
    format_configs = []
    for custom_config in custom_configs:
        # first remove custom_config_ prefix
        custom_config = custom_config.split("custom_config_")[1]
        # then split the config into type, filename, action
        custom_config = custom_config.split("_")
        # check if the config is valid
        if len(custom_config) == 2 and custom_config[0] in config_types:
            format_configs.append({"type": custom_config[0], "filename": custom_config[1], "action": operation, "server_name": server_name})
        else:
            return handle_error(err_message=f"Invalid custom config {custom_config}", redirect_url="services", next=True)

    # Edit check fields and remove already existing ones
    for variable, value in variables.copy().items():
        if (
            variable in variables
            and variable != "SERVER_NAME"
            and value == config.get(f"{server_name}_{variable}" if request.form["operation"] == "edit" else variable, {"value": None})["value"]
        ):
            del variables[variable]

    variables = BW_CONFIG.check_variables(variables, config)
    return config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged, mode


def update_service(config, variables, format_configs, server_name, old_server_name, operation, is_draft, was_draft, is_draft_unchanged):
    if request.form["operation"] == "edit":
        if is_draft_unchanged and len(variables) == 1 and "SERVER_NAME" in variables and server_name == old_server_name:
            return handle_error("The service was not edited because no values were changed.", "services", True)

    if request.form["operation"] == "new" and not variables:
        return handle_error("The service was not created because all values had the default value.", "services", True)

    # Delete
    if request.form["operation"] == "delete":

        is_service = BW_CONFIG.check_variables({"SERVER_NAME": request.form["SERVER_NAME"]}, config)

        if not is_service:
            error_message(f"Error while deleting the service {request.form['SERVER_NAME']}")

        if config.get(f"{request.form['SERVER_NAME'].split(' ')[0]}_SERVER_NAME", {"method": "scheduler"})["method"] != "ui":
            return handle_error("The service cannot be deleted because it has not been created with the UI.", "services", True)

    db_metadata = DB.get_metadata()

    def update_services(threaded: bool = False):
        wait_applying()

        manage_bunkerweb(
            "services",
            variables,
            old_server_name,
            variables.get("SERVER_NAME", ""),
            operation=operation,
            is_draft=is_draft,
            was_draft=was_draft,
            threaded=threaded,
        )

        if any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()
            Thread(target=update_services, args=(True,)).start()
        else:
            update_services()

        DATA["CONFIG_CHANGED"] = True

    message = ""

    if request.form["operation"] == "new":
        message = f"Creating {'draft ' if is_draft else ''}service {variables.get('SERVER_NAME', '').split(' ')[0]}"
    elif request.form["operation"] == "edit":
        message = f"Saving configuration for {'draft ' if is_draft else ''}service {old_server_name.split(' ')[0]}"
    elif request.form["operation"] == "delete":
        message = f"Deleting {'draft ' if was_draft and is_draft else ''}service {request.form.get('SERVER_NAME', '').split(' ')[0]}"

    return message
