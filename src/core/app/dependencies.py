#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from datetime import datetime
from functools import wraps
from glob import glob
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import dumps, loads
from logging import Logger
from os import _exit, chmod, cpu_count, environ
from os.path import basename, dirname, join, normpath, sep
from pathlib import Path
from shutil import copytree, rmtree
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import ReadError, open as tar_open
from threading import enumerate as all_threads, Event, Semaphore, Thread
from time import sleep
from typing import Any, Callable, Dict, List, Literal, Optional, Union
from uuid import uuid4
from zipfile import ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("db",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi.routing import Mount
from magic import Magic
from regex import compile as re_compile
from requests import get

from API import API  # type: ignore
from api_caller import ApiCaller  # type: ignore
from database import Database  # type: ignore
from logger import setup_db_logger  # type: ignore
from .core import CoreConfig
from .job_scheduler import JobScheduler


TMP_FOLDER = Path(sep, "var", "tmp", "bunkerweb")
DB = None
HEALTHY_PATH = TMP_FOLDER.joinpath("core.healthy")
CORE_CONFIG = CoreConfig("core", **(environ if CoreConfig.get_instance() != "Linux" else {}))


def stop(status):
    global DB

    for thread in all_threads():
        if thread.name != "MainThread":
            CORE_CONFIG.logger.info(f"⏲ Waiting for thread {thread.name} to stop (timeout 3s) ...")
            if thread.is_alive():
                with suppress(RuntimeError):
                    thread.join(timeout=3)
            if thread.is_alive():
                CORE_CONFIG.logger.warning(f"Thread {thread.name} is still alive, skipping ...")

    HEALTHY_PATH.unlink(missing_ok=True)
    if DB:
        del DB
    _exit(status)


CORE_CONFIG.logger.info(f"🚀 {CORE_CONFIG.integration} integration detected")

# Create a semaphore to limit the number of threads to the number of CPUs - 1
MAX_THREADS = cpu_count() or 1
SEMAPHORE = Semaphore(MAX_THREADS - 1 if MAX_THREADS > 1 else 1)
PLUGIN_KEYS = ("id", "name", "description", "version", "stream", "settings")
PLUGIN_ID_REGEX = re_compile(r"^[\w.-]{1,64}$")
CUSTOM_CONFIGS_RX = re_compile(r"^((?P<service_id>[^ ]{,255})_)?CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(?P<name>.+)$")

# Create thread events
stop_event = Event()
api_started = Event()
jobs_not_running = Event()
jobs_not_running.set()
is_not_reloading = Event()
is_not_reloading.set()
listen_for_dynamic_instances = Event()

# Create static paths
CACHE_PATH = join(sep, "var", "cache", "bunkerweb")
CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core_plugins")
CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
SETTINGS_PATH = Path(sep, "usr", "share", "bunkerweb", "settings.json")
TMP_ENV_PATH = TMP_FOLDER.joinpath("core.env")

setup_db_logger(CORE_CONFIG.database_log_level)

# Instantiate database and api caller
DB = Database(CORE_CONFIG.logger, CORE_CONFIG.DATABASE_URI)

# Instantiate scheduler
SCHEDULER = JobScheduler(API(f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "bw-scheduler"), env=CORE_CONFIG.settings | {"API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "CORE_TOKEN": CORE_CONFIG.core_token}, logger=CORE_CONFIG.logger)


def update_app_mounts(app):
    """Update the app mounts with the api plugins"""
    CORE_CONFIG.logger.info("Updating app mounts ...")

    # remove the subapps from the routes
    for route in app.routes:
        if isinstance(route, Mount):
            app.routes.remove(route)

    # loop over every core + external plugins that have an api subfolder
    for subapi in glob(str(CORE_PLUGINS_PATH.joinpath("*", "api"))) + glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "api"))):
        main_file_path = Path(subapi, "main.py")

        if not main_file_path.is_file():
            continue

        subapi_plugin = basename(dirname(subapi))
        CORE_CONFIG.logger.info(f"Mounting subapi {subapi_plugin} ...")
        try:
            # load the subapi module
            loader = SourceFileLoader(f"{subapi_plugin}_api", str(main_file_path))
            subapi_module = loader.load_module()
            # get the subapi root path if it exists or set it to /{subapi_plugin}
            root_path = getattr(subapi_module, "root_path", f"/{subapi_plugin}")

            # If the subapi has an app attribute, mount it
            if hasattr(subapi_module, "app"):
                app.mount(root_path, getattr(subapi_module, "app"), basename(dirname(subapi)))

                CORE_CONFIG.logger.info(f"✅ The subapi for the plugin {subapi_plugin} has been mounted successfully, root path: {root_path}")
            else:
                CORE_CONFIG.logger.error(f"Couldn't mount subapi {subapi_plugin}, no app found")
        except Exception as e:
            CORE_CONFIG.logger.error(f"Exception while mounting subapi {subapi_plugin} : {e}")


def install_plugin(plugin_url: str, logger: Logger, *, semaphore: Semaphore = SEMAPHORE):
    """Install a plugin from a url"""
    semaphore.acquire(timeout=30)

    # Download Plugin file
    try:
        if plugin_url.startswith("file://"):
            content = Path(normpath(plugin_url[7:])).read_bytes()
        else:
            content = b""
            resp = get(plugin_url, stream=True, timeout=10)

            if resp.status_code != 200:
                logger.warning(f"Got status code {resp.status_code}, skipping...")
                return

            # Iterate over the response content in chunks
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
    except:
        logger.exception(f"Exception while downloading plugin(s) from {plugin_url}")
        return

    # Extract it to tmp folder
    temp_dir = TMP_FOLDER.joinpath("plugins", str(uuid4()))
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_type = Magic(mime=True).from_buffer(content)

        if file_type == "application/zip":
            with ZipFile(BytesIO(content)) as zf:
                zf.extractall(path=temp_dir)
        elif file_type == "application/gzip":
            with tar_open(fileobj=BytesIO(content), mode="r:gz") as tar:
                tar.extractall(path=temp_dir)
        elif file_type == "application/x-tar":
            with tar_open(fileobj=BytesIO(content), mode="r") as tar:
                tar.extractall(path=temp_dir)
        else:
            logger.error(f"Unknown file type for {plugin_url}, either zip or tar are supported, skipping...")
            return
    except:
        logger.exception(f"Exception while decompressing plugin(s) from {plugin_url}")
        return

    # Install plugins
    try:
        for plugin_dir in glob(str(temp_dir.joinpath("**", "plugin.json")), recursive=True):
            plugin_dir = Path(plugin_dir).parent
            try:
                # Load plugin.json
                metadata = loads(plugin_dir.joinpath("plugin.json").read_text(encoding="utf-8"))
                # Don't go further if plugin is already installed
                if EXTERNAL_PLUGINS_PATH.joinpath(metadata["id"], "plugin.json").is_file():
                    logger.warning(f"Skipping installation of plugin {metadata['id']} (already installed)")
                    return
                # Copy the plugin
                copytree(plugin_dir, EXTERNAL_PLUGINS_PATH.joinpath(metadata["id"]))
                # Add u+x permissions to jobs files
                for job_file in glob(str(plugin_dir.joinpath("jobs", "*"))):
                    st = Path(job_file).stat()
                    chmod(job_file, st.st_mode | S_IEXEC)
                logger.info(f"Plugin {metadata['id']} installed")
            except FileExistsError:
                logger.warning(f"Skipping installation of plugin {plugin_dir.parent.name} (already installed)")
    except:
        logger.exception(f"Exception while installing plugin(s) from {plugin_url}")

    semaphore.release()


def generate_external_plugins(
    plugins: Optional[List[Dict[str, Any]]] = None,
    *,
    original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH,
):
    """Generate external plugins from the database or from a list of plugins if provided"""
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old external plugins files
    CORE_CONFIG.logger.info("Removing old external plugins files ...")
    for file in glob(str(original_path.joinpath("*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(file, ignore_errors=True)

    if not plugins:
        assert DB
        plugins = DB.get_plugins(external=True, with_data=True)

    if plugins:
        CORE_CONFIG.logger.info("Generating new external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            try:
                tar_path = original_path.joinpath(plugin["id"], f"{plugin['name']['en']}.tar.gz")
                tar_path.parent.mkdir(parents=True, exist_ok=True)

                try:
                    # Extract plugin data
                    tar_path.write_bytes(plugin["data"])
                    with tar_open(str(tar_path), "r:gz") as tar:
                        tar.extractall(original_path)

                    # Add u+x permissions to jobs files
                    for job_file in glob(join(str(tar_path.parent), "jobs", "*")):
                        st = Path(job_file).stat()
                        chmod(job_file, st.st_mode | S_IEXEC)
                except ReadError as re:
                    CORE_CONFIG.logger.warning(f"Can't generate external plugin {plugin['id']}, {re}, will generate only the plugin.json and ui files")
                    tar_path.parent.joinpath("plugin.json").write_text(
                        dumps(
                            {"id": plugin["id"], "stream": plugin["stream"], "name": plugin["name"], "description": plugin["description"], "version": plugin["version"], "settings": plugin["settings"]}
                            | ({"jobs": plugin["jobs"]} if plugin.get("jobs") else {}),
                            indent=4,
                        ),
                        encoding="utf-8",
                    )
                    if plugin["page"] and (plugin["template_file"] or plugin["actions_file"]):
                        tar_path.parent.joinpath("ui").mkdir(parents=True, exist_ok=True)
                        if plugin["template_file"]:
                            tar_path.parent.joinpath("ui", "index.html").write_bytes(plugin["template_file"])
                        if plugin["actions_file"]:
                            tar_path.parent.joinpath("ui", "actions.py").write_bytes(plugin["actions_file"])

                # Add u+x permissions to actions file
                ui_actions_file = tar_path.parent.joinpath("ui", "actions.py")
                if ui_actions_file.is_file():
                    st = ui_actions_file.stat()
                    tar_path.parent.joinpath("ui", "actions.py").chmod(st.st_mode | S_IEXEC)

                tar_path.unlink(missing_ok=True)
            except PermissionError:
                CORE_CONFIG.logger.warning(f"Can't generate external plugin {plugin['id']}, permission denied")


def generate_custom_configs(
    configs: Optional[List[Dict[str, Any]]] = None,
    *,
    original_path: Union[Path, str] = CUSTOM_CONFIGS_PATH,
):
    """Generate custom configs from the database or from a list of configs if provided"""
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    CORE_CONFIG.logger.info("Removing old custom configs files ...")
    for file in glob(str(original_path.joinpath("*", "*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(file, ignore_errors=True)

    if not configs:
        assert DB
        configs = DB.get_custom_configs()

    if configs:
        CORE_CONFIG.logger.info("Generating new custom configs ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for custom_config in configs:
            # Extract custom config data
            tmp_path = original_path.joinpath(custom_config["type"].replace("_", "-"), custom_config["service_id"] or "", f"{custom_config['name']}.conf")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(custom_config["data"])


def generate_config(function: Optional[Callable] = None):
    """A decorator that also can be used as a context manager to generate the config before running the function"""

    @wraps(function)  # type: ignore
    def wrap(*args, **kwargs):
        assert DB

        if not jobs_not_running.is_set():
            CORE_CONFIG.logger.info("⏲ Waiting for jobs to finish ...")
            jobs_not_running.wait(60)

        db_config = "retry"
        retries = 0
        while db_config == "retry":
            db_config = DB.get_config()

            if db_config == "retry":
                if retries >= 5:
                    CORE_CONFIG.logger.error("Can't get config from database after 5 retries, exiting ...")
                    stop(1)
                CORE_CONFIG.logger.warning("Can't get config from database, retrying in 5 seconds ...")
                sleep(5)
                continue
            elif isinstance(db_config, str):
                CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}")
                stop(1)

        assert isinstance(db_config, dict)

        content = ""
        for k, v in db_config.items():
            content += f"{k}={v}\n"
        TMP_ENV_PATH.write_text(content)

        # run the generator
        proc = subprocess_run(
            [
                "python3",
                join(sep, "usr", "share", "bunkerweb", "gen", "main.py"),
                "--settings",
                str(SETTINGS_PATH),
                "--templates",
                join(sep, "usr", "share", "bunkerweb", "confs"),
                "--output",
                join(sep, "etc", "nginx"),
                "--variables",
                str(TMP_ENV_PATH),
            ],
            stdin=DEVNULL,
            stderr=STDOUT,
            check=False,
        )

        if proc.returncode != 0:
            CORE_CONFIG.logger.error("Config generator failed, configuration will not work as expected...")

        if function:
            return function(*args, **kwargs)

    return wrap


def assert_api_caller(function: Callable):
    """A decorator to assert that the api_caller is set right before running the function. The function must have api_caller as the first argument"""

    @wraps(function)
    def wrap(api_caller: Optional[ApiCaller] = None, *args, **kwargs):
        assert DB
        if not api_caller:
            db_instances = DB.get_instances()
            if isinstance(db_instances, str):
                message = f"Can't get instances in database : {db_instances}"
                Thread(target=DB.add_action, args=({"date": datetime.now(), "api_method": "GET", "method": "unknown", "tags": ["instance"], "title": "Get instances failed while asserting api_caller", "message": message, "status": "error"},)).start()
                CORE_CONFIG.logger.error(f"{message} while asserting api_caller, api_caller will be None")
            else:
                api_caller = ApiCaller([API(f"http://{instance['hostname']}:{instance['port']}", instance["server_name"]) for instance in db_instances])

        return function(api_caller, *args, **kwargs)

    return wrap


@assert_api_caller
def send_plugins_to_instances(api_caller: ApiCaller):
    """Send the plugins to the instances"""
    generate_external_plugins(original_path=EXTERNAL_PLUGINS_PATH)
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(f"Sending {EXTERNAL_PLUGINS_PATH} folder to instances {instances_endpoints} ...")
    ret = api_caller.send_files(EXTERNAL_PLUGINS_PATH, "/plugins")
    if not ret:
        CORE_CONFIG.logger.error("Not all instances have received the plugins, configuration will not work as expected...")


@generate_config
@assert_api_caller
def send_config_to_instances(api_caller: ApiCaller):  # , *, old_config: bool = False):
    """Send the config to the instances"""
    nginx_prefix = Path(sep, "etc", "nginx")
    # backup_path = Path(sep, "var", "tmp", "bunkerweb", "config_backup.zip") # TODO
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    if not nginx_prefix.is_dir():
        CORE_CONFIG.logger.error(f"{nginx_prefix} is not a directory, configuration will not be sent to instances {instances_endpoints}")
        return 1

    CORE_CONFIG.logger.info(f"Sending {nginx_prefix} folder to instances {instances_endpoints} ...")
    failed_apis, responses = api_caller.send_files(nginx_prefix, "/confs")
    if len(failed_apis) == len(api_caller.apis):
        message = "An error occurred while sending the config to all instances, check your actions,"
        # if old_config:
        CORE_CONFIG.logger.debug(responses)
        CORE_CONFIG.logger.error(f"{message} configuration will not work as expected...")
        DB.add_action(
            {
                "date": datetime.now(),
                "api_method": "POST",
                "method": "unknown",
                "tags": ["instance"],
                "title": "Send config failed to all instances",
                "message": f"{message.replace(' check your actions,', '')} response: {responses}",
                "status": "error",
            },
        )
        return 1

        # CORE_CONFIG.logger.warning(f"{message} trying to send old config to instances ...") # TODO

        # if not backup_path.is_file():
        #     CORE_CONFIG.logger.error(f"No backup found at {backup_path}, configuration will not work as expected...")
        #     return 1

        # CORE_CONFIG.logger.warning(f"Cleaning {nginx_prefix} folder ...")

        # for file in glob(str(nginx_prefix.joinpath("*"))):
        #     file = Path(file)
        #     if file.is_dir():
        #         rmtree(str(file), ignore_errors=True)
        #         continue
        #     file.unlink()

        # CORE_CONFIG.logger.warning(f"Unpacking backup {backup_path} to {nginx_prefix} ...")

        # with ZipFile(backup_path, "r") as backup:
        #     backup.extractall(path=nginx_prefix)

        # CORE_CONFIG.logger.info(f"Successfully unpacked backup {backup_path} to {nginx_prefix}")
        # return send_config_to_instances(api_caller, old_config=True)
    for failed_api in failed_apis:
        CORE_CONFIG.logger.error(f"Can't send config to instance {failed_api.endpoint}, configuration will not work as expected...")
        response = responses[failed_api.endpoint.split("://", 1).pop().split(":")[0]]
        CORE_CONFIG.logger.debug(response)
        DB.add_action(
            {
                "date": datetime.now(),
                "api_method": "POST",
                "method": "unknown",
                "tags": ["instance"],
                "title": "Send config failed",
                "message": f"Can't send config to instance {failed_api.endpoint}, response: {response}",
                "status": "error",
            },
        )
        sleep(0.5)

    # backup_path.unlink(missing_ok=True) # TODO


@assert_api_caller
def send_custom_configs_to_instances(api_caller: ApiCaller):
    """Send the custom configs to the instances"""
    generate_custom_configs(original_path=CUSTOM_CONFIGS_PATH)
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(f"Sending {CUSTOM_CONFIGS_PATH} folder to instances {instances_endpoints} ...")
    ret = api_caller.send_files(CUSTOM_CONFIGS_PATH, "/custom_configs")
    if not ret:
        CORE_CONFIG.logger.error("Not all instances have received the custom configs, configuration will not work as expected...")


@assert_api_caller
def send_cache_to_instances(api_caller: ApiCaller):
    """Send the cache to the instances"""
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(f"Sending {CACHE_PATH} folder to instances {instances_endpoints} ...")
    ret = api_caller.send_files(CACHE_PATH, "/cache")
    if not ret:
        CORE_CONFIG.logger.error("Not all instances have received the cache, configuration will not work as expected...")


@assert_api_caller
def reload_instances(api_caller: ApiCaller):
    """Reload the instances"""
    CORE_CONFIG.logger.info(f"Reloading instances {', '.join(api.endpoint for api in api_caller.apis)} ...")
    ret = api_caller.send_to_apis("POST", "/reload")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have been reloaded, configuration will not work as expected...",
        )


def send_to_instances(types: Union[Literal["all"], set[Literal["plugins", "custom_configs", "config", "cache", "reload"]]], *, instance_api: Optional[API] = None, caller: Optional[ApiCaller] = None, no_reload: bool = False) -> int:
    """Send the data to the instances"""
    api_caller = caller or (ApiCaller([instance_api]) if instance_api else None)

    if api_caller is None:
        assert DB
        api_caller = ApiCaller([API(f"http://{instance['hostname']}:{instance['port']}", instance["server_name"]) for instance in DB.get_instances()])

    if types != "all" and not types:
        CORE_CONFIG.logger.error("No type provided, nothing to do...")
        return 1

    if types == "all" or "plugins" in types:
        send_plugins_to_instances(api_caller)
    if types == "all" or "custom_configs" in types:
        send_custom_configs_to_instances(api_caller)
    if types == "all" or "config" in types:
        send_config_to_instances(api_caller)
    if types == "all" or "cache" in types:
        send_cache_to_instances(api_caller)
    if not no_reload and (types == "all" or types):
        reload_instances(api_caller)
    return 0


def seen_instance(instance_hostname: str):
    """Update the last_seen of an instance in the database"""
    SEMAPHORE.acquire(timeout=30)

    error = DB.seen_instance(instance_hostname)
    if error:
        CORE_CONFIG.logger.error(f"Couldn't update instance {instance_hostname} last_seen to database: {error}")
        return False

    SEMAPHORE.release()

    return True


@assert_api_caller
def test_and_send_to_instances(instance_apis: Union[set[API], ApiCaller], types: Union[Literal["all"], set[Literal["plugins", "custom_configs", "config", "cache", "reload"]]], *, no_reload: bool = False) -> int:
    """Test and send the data to the instances"""
    for instance_api in instance_apis.copy() if isinstance(instance_apis, set) else instance_apis.apis:
        sent, err, status, resp = instance_api.request("GET", "ping")
        if not sent:
            CORE_CONFIG.logger.warning(f"Can't send API request to {instance_api.endpoint}ping : {err}, data will not be sent to it ...")
            instance_apis.remove(instance_api)
            continue
        else:
            if status != 200:
                CORE_CONFIG.logger.warning(f"Error while sending API request to {instance_api.endpoint}ping : status = {resp['status']}, msg = {resp['msg']}, data will not be sent to it ...")
                instance_apis.remove(instance_api)
                continue
            else:
                CORE_CONFIG.logger.info(f"Successfully sent API request to {instance_api.endpoint}ping, sending data to it ...")

        Thread(target=seen_instance, args=(instance_api.endpoint.split("://", 1).pop().split(":")[0],)).start()

    if instance_apis if isinstance(instance_apis, set) else instance_apis.apis:
        api_caller = instance_apis if isinstance(instance_apis, ApiCaller) else ApiCaller(instance_apis)

        return send_to_instances(types, caller=api_caller, no_reload=no_reload)
    return 0


def run_jobs():
    """Run plugins jobs"""
    if not api_started.is_set():
        local_api = API(f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "bw-scheduler")
        sent = False
        status = 0

        while not sent or status != 200:
            sent, err, status, resp = local_api.request("GET", "ping", additonal_headers={"Authorization": f"Bearer {CORE_CONFIG.core_token}"} if CORE_CONFIG.core_token else {})
            sleep(1)

    assert DB

    jobs_not_running.wait(60)

    jobs_not_running.clear()

    try:
        db_config = DB.get_config()

        if isinstance(db_config, str):
            CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}")
            stop(1)

        assert isinstance(db_config, dict)

        # Only run jobs once
        if not SCHEDULER.reload(db_config | {"API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "core_token": CORE_CONFIG.core_token}):
            CORE_CONFIG.logger.error("At least one job in run_once() failed")
        else:
            CORE_CONFIG.logger.info("All jobs in run_once() were successful")

        jobs_not_running.set()

        if test_and_send_to_instances(None, {"cache", "config"}) != 0:
            CORE_CONFIG.logger.warning("Can't send data to BunkerWeb instances, configuration will not work as expected")

        if not DB.is_scheduler_initialized():
            DB.set_scheduler_initialized()
        api_started.set()
    except:
        CORE_CONFIG.logger.exception("Exception while running jobs")
    finally:
        jobs_not_running.set()


def run_job(job_name: str):
    """Run a job"""
    assert DB

    jobs_not_running.wait(60)

    jobs_not_running.clear()

    try:
        db_config = DB.get_config()

        if isinstance(db_config, str):
            CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}")
            stop(1)

        assert isinstance(db_config, dict)

        SCHEDULER.reload(db_config | {"API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "core_token": CORE_CONFIG.core_token}, run=False)
        SCHEDULER.run_single(job_name)

        jobs_not_running.set()

        # TODO: remove this when the soft reload will be available
        if test_and_send_to_instances(None, {"cache", "config"}) != 0:
            CORE_CONFIG.logger.warning("Can't send data to BunkerWeb instances, configuration will not work as expected")
    except:
        CORE_CONFIG.logger.exception(f"Exception while running job {job_name}")
    finally:
        jobs_not_running.set()