from html import escape
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import JSONDecodeError, loads as json_loads
from os import listdir
from os.path import basename, dirname, isabs, join, sep
from pathlib import Path
from shutil import move, rmtree
from sys import path as sys_path
from tarfile import CompressionError, HeaderError, ReadError, TarError, open as tar_open
from threading import Thread
from time import time
from typing import List, Optional, Union
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.utils import secure_filename

from common_utils import bytes_hash  # type: ignore

from app.dependencies import CORE_PLUGINS_PATH, BW_CONFIG, BW_INSTANCES_UTILS, DATA, DB, EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH
from app.utils import ALWAYS_USED_PLUGINS, LOGGER, PLUGIN_NAME_RX, PLUGINS_SPECIFICS, TMP_DIR

from app.routes.utils import PLUGIN_KEYS, error_message, handle_error, verify_data_in_form, wait_applying

plugins = Blueprint("plugins", __name__)


@plugins.route("/plugins", methods=["GET"])
@login_required
def plugins_page():
    tmp_ui_path = TMP_DIR.joinpath("ui")
    # Remove everything in the tmp folder
    rmtree(tmp_ui_path, ignore_errors=True)
    tmp_ui_path.mkdir(parents=True, exist_ok=True)
    return render_template("plugins.html")


@plugins.route("/plugins/delete", methods=["POST"])
@login_required
def delete_plugin():
    if DB.readonly:
        return Response("Database is in read-only mode", 403)

    verify_data_in_form(
        data={"plugins": None},
        err_message="Missing plugins parameter on /plugins/delete.",
        redirect_url="plugins",
        next=True,
    )
    DATA.load_from_file()

    plugins = request.form["plugins"].split(",")

    def update_plugins(plugins: List[str]):
        wait_applying()

        for plugin in plugins:
            err = DB.delete_plugin(plugin, "ui", changes=plugin == plugins[-1])
            if err:
                if not err.startswith("Plugin with id"):
                    message = f"Couldn't delete plugin {plugin} in database: {err}"
                else:
                    message = err

                DATA["TO_FLASH"].append({"content": message, "type": "error"})
            else:
                DATA["TO_FLASH"].append({"content": f"Deleted plugin {plugin} successfully", "type": "success"})

        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time()})

    Thread(target=update_plugins, args=(plugins,)).start()

    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message=f"Deleting plugins: {', '.join(plugins)}"))


def get_plugin_path(plugin_id: str) -> Optional[Path]:
    """
    Find the filesystem path for a plugin given its ID.
    First checks in pro plugins path, then in external plugins path.

    Args:
        plugin_id: The plugin ID to search for

    Returns:
        Path object if found, None otherwise
    """
    # Look in pro plugins first (higher priority)
    pro_path = PRO_PLUGINS_PATH / plugin_id
    if (pro_path / "ui").exists():
        return pro_path

    # Then look in external plugins
    ext_path = EXTERNAL_PLUGINS_PATH / plugin_id
    if (ext_path / "ui").exists():
        return ext_path

    # And finally in core plugins
    core_path = CORE_PLUGINS_PATH / plugin_id
    if (core_path / "ui").exists():
        return core_path

    # Plugin not found in filesystem
    return None


def run_action(plugin: str, function_name: str = "", *, tmp_dir: Optional[Path] = None) -> Union[dict, Response]:
    message = ""

    # Try to load from filesystem first if tmp_dir is not provided
    if not tmp_dir:
        plugin_path = get_plugin_path(plugin)

        if plugin_path and (plugin_path / "ui" / "actions.py").exists():
            # Plugin exists in filesystem
            tmp_dir = plugin_path / "ui"
        else:
            # Fall back to database if not found in filesystem
            page = DB.get_plugin_page(plugin)

            if not page:
                return {"status": "ko", "code": 404, "message": "The plugin does not have a page"}

            try:
                # Extract from database blob
                tmp_dir = TMP_DIR.joinpath("ui", "action", str(uuid4()))
                tmp_dir.mkdir(parents=True, exist_ok=True)

                with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                    for member in tar.getmembers():
                        # Prevent absolute paths and paths with '..'
                        if member.name.startswith("/") or ".." in Path(member.name).parts:
                            return {"status": "ko", "code": 400, "message": "Invalid file path"}

                        # Construct the target path and ensure it is within tmp_dir
                        target_path = tmp_dir.joinpath(member.name).resolve()
                        if not str(target_path).startswith(str(tmp_dir)):
                            return {"status": "ko", "code": 400, "message": "Invalid file path"}

                        # Extract the file safely
                        tar.extract(member, tmp_dir)

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
        if function_name != "pre_render" and not str(tmp_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
            rmtree(tmp_dir, ignore_errors=True)
            TMP_DIR.joinpath("ui").mkdir(parents=True, exist_ok=True)

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

        res = method(app=current_app, db=DB, bw_instances_utils=BW_INSTANCES_UTILS, args=queries, data=data)
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

        # Only clean up temporary directories that aren't permanent plugin paths
        if function_name != "pre_render" and not str(tmp_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
            rmtree(tmp_dir, ignore_errors=True)
            TMP_DIR.joinpath("ui").mkdir(parents=True, exist_ok=True)

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


@plugins.route("/plugins/refresh", methods=["POST"])
@login_required
def plugins_refresh():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "plugins")
    tmp_ui_path = TMP_DIR.joinpath("ui")

    verify_data_in_form(
        data={"csrf_token": None},
        err_message="Missing csrf_token parameter on /plugins.",
        redirect_url="plugins",
        next=True,
    )

    # Upload plugins
    if not tmp_ui_path.exists() or not listdir(str(tmp_ui_path)):
        return handle_error("Please upload new plugins to reload plugins", "plugins", True)
    DATA.load_from_file()

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
                    message = f"{file} is not a valid zip file. ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
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
                    message = f"Couldn't read file {file} ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
                except CompressionError:
                    errors += 1
                    message = f"{file} is not a valid tar file ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})
                except HeaderError:
                    errors += 1
                    message = f"The file plugin.json in {file} is not valid ({folder_name or temp_folder_name})"
                    LOGGER.exception(message)
                    DATA["TO_FLASH"].append({"content": f"{message}, check logs for more details", "type": "error", "save": False})

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
                DATA["TO_FLASH"].append(
                    {
                        "content": f"Invalid plugin name for {temp_folder_name}. (Can only contain numbers, letters, underscores and hyphens (min 4 characters and max 64))",
                        "type": "error",
                        "save": False,
                    }
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
                    "type": "ui",
                    "page": "ui" in listdir(str(temp_folder_path)),
                    "method": "ui",
                    "data": value,
                    "checksum": bytes_hash(value, algorithm="sha256"),
                }
            )
            new_plugins_ids.append(folder_name)
        except KeyError:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"{file} is not a valid plugin (plugin.json file is missing) ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except JSONDecodeError as e:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"The file plugin.json in {file} is not valid ({e.msg}: line {e.lineno} column {e.colno} (char {e.pos})) ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except ValueError:
            errors += 1
            DATA["TO_FLASH"].append(
                {
                    "content": f"The file plugin.json is missing one or more of the following keys: <i>{', '.join(PLUGIN_KEYS)}</i> ({folder_name or temp_folder_name})",
                    "type": "error",
                    "save": False,
                }
            )
        except FileExistsError:
            errors += 1
            DATA["TO_FLASH"].append({"content": f"A plugin named {folder_name} already exists", "type": "error", "save": False})
        except (TarError, OSError) as e:
            errors += 1
            DATA["TO_FLASH"].append({"content": str(e), "type": "error", "save": False})
        except Exception as e:
            errors += 1
            DATA["TO_FLASH"].append({"content": str(e), "type": "error", "save": False})

    if errors >= files_count:
        return redirect(url_for("loading", next=url_for("plugins.plugins_page")))

    def update_plugins():
        wait_applying()

        plugins = BW_CONFIG.get_plugins(_type="ui", with_data=True)
        for plugin in plugins:
            if plugin in new_plugins_ids:
                DATA["TO_FLASH"].append({"content": f"Plugin {plugin} already exists", "type": "error"})
                del new_plugins[new_plugins_ids.index(plugin)]

        if not new_plugins:
            DATA["RELOADING"] = False
            return

        err = DB.update_external_plugins(new_plugins, _type="ui", delete_missing=False)
        if err:
            DATA["TO_FLASH"].append({"content": f"Couldn't update ui plugins to database: {err}", "type": "error"})
        else:
            DATA["TO_FLASH"].append({"content": "Plugins uploaded successfully", "type": "success"})

        DATA["RELOADING"] = False

    DATA.update({"RELOADING": True, "LAST_RELOAD": time()})
    Thread(target=update_plugins).start()

    return redirect(url_for("loading", next=url_for("plugins.plugins_page"), message="Reloading plugins"))


@plugins.route("/plugins/upload", methods=["POST"])
@login_required
def upload_plugin():
    if DB.readonly:
        return {"status": "ko", "message": "Database is in read-only mode"}, 403

    if not request.files:
        return {"status": "ko"}, 400

    tmp_ui_path = TMP_DIR.joinpath("ui")

    for uploaded_file in request.files.values():
        if not uploaded_file.filename:
            return {"status": "ko"}, 422

        if not uploaded_file.filename.endswith((".zip", ".tar.gz", ".tar.xz")):
            return {"status": "ko"}, 422

        file_name = Path(secure_filename(uploaded_file.filename)).name
        folder_name = file_name.rsplit(".", 2)[0]

        with BytesIO(uploaded_file.read()) as plugin_file:
            plugin_file.seek(0, 0)
            plugins = []
            if uploaded_file.filename.endswith(".zip"):
                with ZipFile(plugin_file) as zip_file:
                    for file in zip_file.namelist():
                        if file.endswith("plugin.json"):
                            plugins.append(basename(dirname(file)))
                    if len(plugins) > 1:
                        for file in zip_file.namelist():
                            if isabs(file) or ".." in file:
                                return {"status": "ko"}, 422

                        zip_file.extractall(str(tmp_ui_path) + "/")
            else:
                with tar_open(fileobj=plugin_file) as tar_file:
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
                plugin_file.seek(0, 0)
                # deepcode ignore PT: The folder name is being sanitized before
                tmp_ui_path.joinpath(file_name).write_bytes(plugin_file.read())
                return {"status": "ok"}, 201

        for plugin in plugins:
            if tmp_ui_path.joinpath(folder_name, plugin).exists():
                with BytesIO() as tgz:
                    with tar_open(mode="w:gz", fileobj=tgz, dereference=True, compresslevel=3) as tf:
                        tf.add(str(tmp_ui_path.joinpath(folder_name, plugin)), arcname=plugin)
                    tgz.seek(0, 0)
                    tmp_ui_path.joinpath(f"{plugin}.tar.gz").write_bytes(tgz.read())

    # deepcode ignore PT: The folder name is being sanitized before
    rmtree(tmp_ui_path.joinpath(folder_name), ignore_errors=True)

    return {"status": "ok"}, 201


@plugins.route("/plugins/<string:plugin>", methods=["GET", "POST"])
@login_required
def custom_plugin_page(plugin: str):
    rmtree(TMP_DIR.joinpath("ui", "page"), ignore_errors=True)

    if not PLUGIN_NAME_RX.match(plugin):
        return handle_error("Invalid plugin id, (must be between 1 and 64 characters, only letters, numbers, underscores and hyphens)", "plugins")

    if request.method == "POST":
        action_result = run_action(plugin)

        if isinstance(action_result, Response):
            LOGGER.info("Plugin action executed successfully")
            return action_result

        # case error
        if action_result["status"] == "ko":
            return error_message(escape(action_result["message"])), action_result["code"]

        LOGGER.info(f"Plugin {plugin} action executed successfully")

        if request.content_type == "application/x-www-form-urlencoded":
            return redirect(f"{url_for('plugins.plugins_page')}/{plugin}", code=303)
        return jsonify({"message": "ok", "data": action_result["data"]}), 200

    plugin_data = {}
    for db_plugin, db_plugin_data in BW_CONFIG.get_plugins().items():
        if db_plugin == plugin:
            plugin_data = db_plugin_data | {"id": db_plugin}
            break

    if not plugin_data:
        return error_message("Plugin not found"), 404

    plugin_id = plugin.upper()
    plugin_name_formatted = plugin_data["name"].replace(" ", "_").upper()
    db_config = DB.get_config()

    def plugin_used(prefix: str = "") -> bool:
        if plugin_id in PLUGINS_SPECIFICS:
            for key, value in PLUGINS_SPECIFICS[plugin_id].items():
                if db_config.get(f"{prefix}{key}", value) != value:
                    return True
        elif db_config.get(f"{prefix}USE_{plugin_id}", db_config.get(f"{prefix}USE_{plugin_name_formatted}", "no")) != "no":
            return True
        return False

    is_metrics_on = db_config.get("USE_METRICS", "yes") != "no"
    is_used = plugin in ALWAYS_USED_PLUGINS or plugin_used() or plugin_data["type"] in ("pro", "ui")

    if is_metrics_on and not is_used:
        # Check if at least one service is using metrics and/or the plugin
        for service in db_config.get("SERVER_NAME", "").split(" "):
            if not is_metrics_on and db_config.get(f"{service}_USE_METRICS", "yes") != "no":
                is_metrics_on = True
            elif not is_used and plugin_used(f"{service}_"):
                is_used = True
            if is_metrics_on and is_used:
                break

    pre_render = {}
    plugin_page = ""

    if is_used and is_metrics_on:
        # Try loading from filesystem first
        plugin_fs_path = get_plugin_path(plugin)
        tmp_page_dir = None

        if plugin_fs_path and (plugin_fs_path / "ui").exists():
            # Use the filesystem path directly
            tmp_page_dir = plugin_fs_path / "ui"
            LOGGER.debug(f"Using filesystem path for plugin {plugin}: {tmp_page_dir}")
        else:
            # Fall back to database if not found in filesystem
            page = DB.get_plugin_page(plugin)
            if not page:
                return error_message("The plugin does not have a page"), 404

            # Extract from database blob to temporary location
            tmp_page_dir = TMP_DIR.joinpath("ui", "page", str(uuid4()))
            tmp_page_dir.mkdir(parents=True, exist_ok=True)

            with tar_open(fileobj=BytesIO(page), mode="r:gz") as tar:
                for member in tar.getmembers():
                    # Prevent absolute paths and paths with '..'
                    if member.name.startswith("/") or ".." in Path(member.name).parts:
                        return {"status": "ko", "code": 400, "message": "Invalid file path"}

                    # Construct the target path and ensure it is within tmp_dir
                    target_path = tmp_page_dir.joinpath(member.name).resolve()
                    if not str(target_path).startswith(str(tmp_page_dir)):
                        return {"status": "ko", "code": 400, "message": "the plugin page has an invalid file path"}

                    # Extract the file safely
                    tar.extract(member, tmp_page_dir)

            tmp_page_dir = tmp_page_dir.joinpath("ui")
            LOGGER.debug(f"Plugin {plugin} page extracted from database successfully")

        # Execute pre-render action if exists
        pre_render = run_action(plugin, "pre_render", tmp_dir=tmp_page_dir)
        template_path = tmp_page_dir / "template.html"

        if template_path.is_file():
            page_content = template_path.read_text(encoding="utf-8")

            if page_content.startswith('{% extends "base.html" %}'):
                page_content = """<div class="d-flex align-items-center justify-content-center">
    <div class="text-center text-primary">
        <p class="text-center relative w-full p-2 text-primary rounded-lg fw-bold">
            Plugin page uses old template, therefore it will not be displayed correctly. Please update it to the new format.
        </p>
    </div>
</div>"""

            try:
                # Merge globals and ENV with ENV taking precedence
                template_vars = {**current_app.jinja_env.globals, **current_app.config["ENV"]}

                # deepcode ignore Ssti: We trust the plugin template
                plugin_page = (
                    Environment(
                        loader=FileSystemLoader((tmp_page_dir.as_posix() + "/", join(sep, "usr", "share", "bunkerweb", "ui", "templates") + "/")),
                        autoescape=select_autoescape(["html"]),
                    )
                    .from_string(page_content)
                    .render(pre_render=pre_render, **template_vars)
                )
            except BaseException:
                LOGGER.exception("An error occurred while rendering the plugin page")
                plugin_page = '<div class="mt-2 mb-2 alert alert-danger text-center" role="alert">An error occurred while rendering the plugin page<br/>See logs for more details</div>'

            # Clean up temporary directories if extracted from database
            if not str(tmp_page_dir).startswith((str(EXTERNAL_PLUGINS_PATH), str(PRO_PLUGINS_PATH))):
                rmtree(tmp_page_dir.parent, ignore_errors=True)

    return render_template("plugin_page.html", plugin_page=plugin_page, plugin=plugin_data, is_used=is_used, is_metrics=is_metrics_on, pre_render=pre_render)
