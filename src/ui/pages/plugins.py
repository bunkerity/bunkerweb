from base64 import b64encode
from copy import deepcopy
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, dumps, loads as json_loads
from os import listdir
from os.path import basename, dirname, isabs, join, sep
from pathlib import Path
from shutil import move, rmtree
from sys import path as sys_path
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from threading import Thread
from time import time
from typing import Optional, Union
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from flask import Blueprint, Response, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.utils import secure_filename

from common_utils import bytes_hash  # type: ignore

from builder.plugins import plugins_builder  # type: ignore

from dependencies import BW_CONFIG, BW_INSTANCES_UTILS, DATA, DB
from utils import LOGGER, PLUGIN_NAME_RX, TMP_DIR

from pages.utils import PLUGIN_ID_RX, PLUGIN_KEYS, error_message, handle_error, verify_data_in_form, wait_applying


plugins = Blueprint("plugins", __name__)


def run_action(plugin: str, function_name: str = "", *, tmp_dir: Optional[Path] = None) -> Union[dict, Response]:
    message = ""
    if not tmp_dir:
        page = DB.get_plugin_page(plugin)

        if not page:
            return {"status": "ko", "code": 404, "message": "The plugin does not have a page"}

        try:
            # Try to import the plugin's custom page
            tmp_dir = TMP_DIR.joinpath("ui", "action", str(uuid4()))
            tmp_dir.mkdir(parents=True, exist_ok=True)

            with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                tar.extractall(tmp_dir)

            tmp_dir = tmp_dir.joinpath("ui")
        except BaseException as e:
            LOGGER.error(f"An error occurred while extracting the plugin: {e}")
            return {"status": "ko", "code": 500, "message": "An error occurred while extracting the plugin, see logs for more details"}

    try:
        action_file = tmp_dir.joinpath("actions.py")
        if not action_file.is_file():
            return {"status": "ko", "code": 404, "message": "The plugin does not have an action file"}

        sys_path.append(tmp_dir.as_posix())
        loader = SourceFileLoader("actions", action_file.as_posix())
        actions = loader.load_module()
    except BaseException as e:
        sys_path.pop()
        if function_name != "pre_render":
            rmtree(tmp_dir, ignore_errors=True)

        LOGGER.error(f"An error occurred while importing the plugin: {e}")
        return {"status": "ko", "code": 500, "message": "An error occurred while importing the plugin, see logs for more details"}

    exception = None
    res = None
    message = None

    try:
        # Try to get the custom plugin custom function and call it
        method = getattr(actions, function_name or plugin)
        queries = request.args.to_dict()
        try:
            data = request.json or {}
        except BaseException:
            data = {}

        res = method(app=current_app, db=DB, instances_utils=BW_INSTANCES_UTILS, args=queries, data=data)
    except AttributeError as e:
        if function_name == "pre_render":
            sys_path.pop()
            return {"status": "ok", "code": 200, "message": "The plugin does not have a pre_render method"}

        message = "The plugin does not have a method"
        exception = e
    except BaseException as e:
        message = "An error occurred while executing the plugin"
        exception = e
    finally:
        sys_path.pop()

        if function_name != "pre_render":
            rmtree(tmp_dir, ignore_errors=True)

        if message:
            LOGGER.error(message + (f": {exception}" if exception else ""))
        if message or not isinstance(res, dict) and not res:
            return {
                "status": "ko",
                "code": 500,
                "message": message + ", see logs for more details" if message else "The plugin did not return a valid response",
            }

    if isinstance(res, Response):
        return res

    return {"status": "ok", "code": 200, "data": res}


@plugins.route("/plugins", methods=["GET", "POST"])
@login_required
def plugins_page():
    tmp_ui_path = TMP_DIR.joinpath("ui")

    if request.method == "POST":
        if DB.readonly:
            return handle_error("Database is in read-only mode", "plugins")

        verify_data_in_form(
            data={"csrf_token": None},
            err_message="Missing csrf_token parameter on /plugins.",
            redirect_url="plugins",
            next=True,
        )

        error = 0
        # Upload plugins
        if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
            return handle_error("Please upload new plugins to reload plugins", "plugins", True)

        errors = 0
        files_count = 0
        new_plugins = []
        new_plugins_ids = []

        for file in listdir(str(tmp_ui_path)):
            if not tmp_ui_path.joinpath(file).is_file():
                continue

            files_count += 1
            folder_name = ""
            temp_folder_name = file.split(".")[0]
            temp_folder_path = tmp_ui_path.joinpath(temp_folder_name)
            is_dir = False

            try:
                if file.endswith(".zip"):
                    try:
                        with ZipFile(str(tmp_ui_path.joinpath(file))) as zip_file:
                            try:
                                zip_file.getinfo("plugin.json")
                            except KeyError:
                                is_dir = True
                            zip_file.extractall(str(temp_folder_path))
                    except BadZipFile:
                        errors += 1
                        error = 1
                        message = f"{file} is not a valid zip file. ({folder_name or temp_folder_name})"
                        LOGGER.exception(message)
                        flash(message, "error")
                else:
                    try:
                        with tar_open(str(tmp_ui_path.joinpath(file)), errorlevel=2) as tar_file:
                            try:
                                tar_file.getmember("plugin.json")
                            except KeyError:
                                is_dir = True
                            try:
                                # deepcode ignore TarSlip: We don't need to check for tar slip as we are checking the files when they are uploaded
                                tar_file.extractall(str(temp_folder_path), filter="data")
                            except TypeError:
                                # deepcode ignore TarSlip: We don't need to check for tar slip as we are checking the files when they are uploaded
                                tar_file.extractall(str(temp_folder_path))
                    except ReadError:
                        errors += 1
                        error = 1
                        message = f"Couldn't read file {file} ({folder_name or temp_folder_name})"
                        LOGGER.exception(message)
                        flash(message, "error")
                    except CompressionError:
                        errors += 1
                        error = 1
                        message = f"{file} is not a valid tar file ({folder_name or temp_folder_name})"
                        LOGGER.exception(message)
                        flash(message, "error")
                    except HeaderError:
                        errors += 1
                        error = 1
                        message = f"The file plugin.json in {file} is not valid ({folder_name or temp_folder_name})"
                        LOGGER.exception(message)
                        flash(message, "error")

                if is_dir:
                    dirs = [d for d in listdir(str(temp_folder_path)) if temp_folder_path.joinpath(d).is_dir()]

                    if not dirs or len(dirs) > 1 or not temp_folder_path.joinpath(dirs[0], "plugin.json").is_file():
                        raise KeyError

                    for file_name in listdir(str(temp_folder_path.joinpath(dirs[0]))):
                        move(
                            str(temp_folder_path.joinpath(dirs[0], file_name)),
                            str(temp_folder_path.joinpath(file_name)),
                        )
                    rmtree(
                        str(temp_folder_path.joinpath(dirs[0])),
                        ignore_errors=True,
                    )

                plugin_file = json_loads(temp_folder_path.joinpath("plugin.json").read_text(encoding="utf-8"))

                if not all(key in plugin_file.keys() for key in PLUGIN_KEYS):
                    raise ValueError

                folder_name = plugin_file["id"]

                if not PLUGIN_NAME_RX.match(folder_name):
                    errors += 1
                    error = 1
                    flash(
                        f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 64))",
                        "error",
                    )
                    raise Exception

                plugin_content = BytesIO()
                with tar_open(
                    fileobj=plugin_content,
                    mode="w:gz",
                    compresslevel=9,
                ) as tar:
                    tar.add(
                        str(temp_folder_path),
                        arcname=temp_folder_name,
                        recursive=True,
                    )
                plugin_content.seek(0)
                value = plugin_content.getvalue()

                new_plugins.append(
                    plugin_file
                    | {
                        "type": "external",
                        "page": "ui" in listdir(str(temp_folder_path)),
                        "method": "ui",
                        "data": value,
                        "checksum": bytes_hash(value, algorithm="sha256"),
                    }
                )
                new_plugins_ids.append(folder_name)
            except KeyError:
                errors += 1
                error = 1
                flash(
                    f"{file} is not a valid plugin (plugin.json file is missing) ({folder_name or temp_folder_name})",
                    "error",
                )
            except JSONDecodeError as e:
                errors += 1
                error = 1
                flash(
                    f"The file plugin.json in {file} is not valid ({e.msg}: line {e.lineno} column {e.colno} (char {e.pos})) ({folder_name or temp_folder_name})",
                    "error",
                )
            except ValueError:
                errors += 1
                error = 1
                flash(
                    f"The file plugin.json is missing one or more of the following keys: <i>{', '.join(PLUGIN_KEYS)}</i> ({folder_name or temp_folder_name})",
                    "error",
                )
            except FileExistsError:
                errors += 1
                error = 1
                flash(
                    f"A plugin named {folder_name} already exists",
                    "error",
                )
            except (TarError, OSError) as e:
                errors += 1
                error = 1
                flash(str(e), "error")
            except Exception as e:
                errors += 1
                error = 1
                flash(str(e), "error")
            finally:
                if error != 1:
                    flash(f"Successfully created plugin: <b><i>{folder_name}</i></b>")

                error = 0

        if errors >= files_count:
            return redirect(url_for("loading", next=url_for("plugins.plugins_page")))

        db_metadata = DB.get_metadata()

        def update_plugins(threaded: bool = False):
            wait_applying()

            plugins = BW_CONFIG.get_plugins(_type="ui", with_data=True)
            for plugin in deepcopy(plugins):
                if plugin["id"] in new_plugins_ids:
                    flash(f"Plugin {plugin['id']} already exists", "error")
                    del new_plugins[new_plugins_ids.index(plugin["id"])]

            err = DB.update_external_plugins(new_plugins, _type="ui", delete_missing=False)
            if err:
                message = f"Couldn't update ui plugins to database: {err}"
                if threaded:
                    DATA["TO_FLASH"].append({"content": message, "type": "error"})
                else:
                    flash(message, "error")
            else:
                message = "Plugins uploaded successfully"
                if threaded:
                    DATA["TO_FLASH"].append({"content": message, "type": "success"})
                else:
                    flash("Plugins uploaded successfully")

            DATA["RELOADING"] = False

        if any(
            v
            for k, v in db_metadata.items()
            if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
        ):
            DATA["RELOADING"] = True
            DATA["LAST_RELOAD"] = time()

            Thread(target=update_plugins, args=(True,)).start()
        else:
            update_plugins()

        return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message="Reloading plugins"))

    # Remove tmp folder
    if tmp_ui_path.is_dir():
        rmtree(tmp_ui_path, ignore_errors=True)

    builder = plugins_builder(DB.get_plugins())
    return render_template("plugins.html", data_server_builder=b64encode(dumps(builder).encode("utf-8")).decode("ascii"))


@plugins.route("/plugins/delete", methods=["POST"])
@login_required
def delete_plugin():
    if DB.readonly:
        return {"status": "ko", "message": "Database is in read-only mode"}, 403

    verify_data_in_form(
        data={"plugin_name": None},
        err_message="Missing plugin name parameter on /plugins/delete.",
        redirect_url="plugins",
        next=True,
    )

    plugin = request.form["plugin_name"]
    db_metadata = DB.get_metadata()

    def update_plugins(threaded: bool = False):  # type: ignore
        wait_applying()

        err = DB.delete_plugin(plugins, "ui")
        if err:
            if not err.startswith("Plugin with id"):
                message = f"Couldn't delete plugin {plugin} in database: {err}"
            else:
                message = err

            if threaded:
                DATA["TO_FLASH"].append({"content": message, "type": "error"})
            else:
                error_message(message)
        else:
            message = f"Deleted plugin {plugin} successfully"
            if threaded:
                DATA["TO_FLASH"].append({"content": message, "type": "success"})
            else:
                flash(message)

        DATA["RELOADING"] = False

    if any(
        v
        for k, v in db_metadata.items()
        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
    ):
        DATA["RELOADING"] = True
        DATA["LAST_RELOAD"] = time()

        Thread(target=update_plugins, args=(True,)).start()
    else:
        update_plugins()

    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message=f"Deleting plugin {plugin}"))


@plugins.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if DB.readonly:
        return {"status": "ko", "message": "Database is in read-only mode"}, 403

    if not request.files:
        return {"status": "ko"}, 400

    tmp_ui_path = TMP_DIR.joinpath("ui")
    tmp_ui_path.mkdir(parents=True, exist_ok=True)

    for uploaded_file in request.files.values():
        if not uploaded_file.filename:
            continue

        if not uploaded_file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        file_name = Path(secure_filename(uploaded_file.filename)).name
        folder_name = file_name.replace(".tar.gz", "").replace(".tar.xz", "").replace(".zip", "")

        with BytesIO(uploaded_file.read()) as io:
            io.seek(0, 0)
            plugins = []
            if uploaded_file.filename.endswith(".zip"):
                with ZipFile(io) as zip_file:
                    for file in zip_file.namelist():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for file in zip_file.namelist():
                            if isabs(file) or ".." in file:
                                return {"status": "ko"}, 422

                        zip_file.extractall(str(tmp_ui_path) + "/")
            else:
                with tar_open(fileobj=io) as tar_file:
                    for file in tar_file.getnames():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for member in tar_file.getmembers():
                            if isabs(member.name) or ".." in member.name:
                                return {"status": "ko"}, 422

                        try:
                            # deepcode ignore TarSlip: The files in the tar are being inspected before extraction
                            tar_file.extractall(str(tmp_ui_path) + "/", filter="data")
                        except TypeError:
                            # deepcode ignore TarSlip: The files in the tar are being inspected before extraction
                            tar_file.extractall(str(tmp_ui_path) + "/")

            if len(plugins) <= 1:
                io.seek(0, 0)
                # deepcode ignore PT: The folder name is being sanitized before
                tmp_ui_path.joinpath(file_name).write_bytes(io.read())
                return {"status": "ok"}, 201

        for plugin in plugins:
            with BytesIO() as tgz:
                with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                    tf.add(str(tmp_ui_path.joinpath(folder_name, plugin)), arcname=plugin)
                tgz.seek(0, 0)
                tmp_ui_path.joinpath(f"{plugin}.tar.gz").write_bytes(tgz.read())

        # deepcode ignore PT: The folder name is being sanitized before
        rmtree(tmp_ui_path.joinpath(folder_name), ignore_errors=True)

    return {"status": "ok"}, 201


@plugins.route("/plugins/<plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin(plugin: str):
    if not PLUGIN_ID_RX.match(plugin):
        return error_message("Invalid plugin id, (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)"), 400

    # Case we ware looking for a plugin template
    # We need to check if a page exists, and if it does, we need to check if the plugin is activated and metrics are on
    if request.method == "GET":

        # Check plugin's page
        page = DB.get_plugin_page(plugin)

        if not page:
            return error_message("The plugin does not have a page"), 404

        tmp_page_dir = TMP_DIR.joinpath("ui", "page", str(uuid4()))
        tmp_page_dir.mkdir(parents=True, exist_ok=True)

        with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar_file:
            tar_file.extractall(tmp_page_dir)

        tmp_page_dir = tmp_page_dir.joinpath("ui")

        LOGGER.debug(f"Plugin {plugin} page extracted successfully")

        # Case template, prepare data
        plugins = BW_CONFIG.get_plugins()
        plugin_id = None
        curr_plugin = {}
        is_used = False
        use_key = False
        is_metrics_on = False
        context = "multisite"

        for plug in plugins:
            if plug["id"] == plugin:
                plugin_id = plug["id"]
                curr_plugin = plug
                break

        # Case no plugin found
        if plugin_id is None:
            return error_message("Plugin not found"), 404

        config = DB.get_config()

        # Check if we are using metrics
        for service in config.get("SERVER_NAME", "").split(" "):
            # specific case
            if config.get(f"{service}_USE_METRICS", "yes") != "no":
                is_metrics_on = True
                break

        # Check if the plugin is used

        # Here we have specific cases for some plugins
        # {plugin_id: [[setting_name, setting_false], ...]}
        specific_cases = {
            "limit": [["USE_LIMIT_REQ", "no"], ["USE_LIMIT_CONN", "no"]],
            "misc": [["DISABLE_DEFAULT_SERVER", "no"], ["ALLOWED_METHODS", ""]],
            "modsecurity": [["USE_MODSECURITY", "no"]],
            "realip": [["USE_REALIP", "no"]],
            "reverseproxy": [["USE_REVERSE_PROXY", "no"]],
            "selfsigned": [["GENERATE_SELF_SIGNED_SSL", "no"]],
            "letsencrypt": [["AUTO_LETS_ENCRYPT", "no"]],
            "country": [["BLACKLIST_COUNTRY", ""], ["WHITELIST_COUNTRY", ""]],
        }

        # specific cases
        for key, data in curr_plugin["settings"].items():
            # specific cases
            if plugin_id in specific_cases:
                use_key = "SPECIFIC"
                context = data["context"]
                break

            # default case (one USE_)
            if key.upper().startswith("USE_"):
                use_key = key
                context = data["context"]
                break

        # Case USE_<NAME>, it means show only if used by one service
        if context == "global":
            if plugin_id in specific_cases:
                for key in specific_cases[plugin_id]:
                    setting_name = key[0]
                    setting_false = key[1]
                    if config.get(setting_name, setting_false) != setting_false:
                        is_used = True
                        break

            if config.get(use_key, "no") != "no":
                is_used = True

        if context == "multisite":
            for service in config.get("SERVER_NAME", "").split(" "):
                # specific case
                if plugin_id in specific_cases:
                    for key in specific_cases[plugin_id]:
                        setting_name = key[0]
                        setting_false = key[1]
                        if config.get(f"{service}_{setting_name}", setting_false) != setting_false:
                            is_used = True
                            break

                # general case
                if config.get(f"{service}_{use_key}", "no") != "no":
                    is_used = True
                    break

        # Get prerender from action.py
        pre_render = run_action(plugin, "pre_render", tmp_dir=tmp_page_dir)
        return render_template(
            # deepcode ignore Ssti: We trust the plugin template
            Environment(
                loader=FileSystemLoader((tmp_page_dir.as_posix() + "/", join(sep, "usr", "share", "bunkerweb", "ui", "templates") + "/")),
                autoescape=select_autoescape(["html"]),
            ).from_string(tmp_page_dir.joinpath("template.html").read_text(encoding="utf-8")),
            current_endpoint=plugin,
            plugin=curr_plugin,
            pre_render=pre_render,
            is_used=is_used,
            is_metrics=is_metrics_on,
            **current_app.jinja_env.globals,
        )

    rmtree(TMP_DIR.joinpath("ui", "page"), ignore_errors=True)

    action_result = run_action(plugin)

    if isinstance(action_result, Response):
        LOGGER.info(f"Plugin {plugin} action executed successfully")
        return action_result

    # case error
    if action_result["status"] == "ko":
        return error_message(action_result["message"]), action_result["code"]

    LOGGER.info(f"Plugin {plugin} action executed successfully")

    if request.content_type == "application/x-www-form-urlencoded":
        return redirect(f"{url_for('plugins.plugins_page')}/{plugin}", code=303)
    return jsonify({"message": "ok", "data": action_result["data"]}), 200
