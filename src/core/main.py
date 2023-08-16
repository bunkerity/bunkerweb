#!/usr/bin/python3

from contextlib import suppress
from copy import deepcopy
from datetime import datetime
from glob import glob
from importlib.machinery import SourceFileLoader
from io import BytesIO
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
)
from itertools import chain
from json import loads as json_loads
from shutil import rmtree
from socket import gaierror, herror
from threading import Semaphore, Thread
from dotenv import dotenv_values
from functools import partial
from os import _exit, cpu_count, environ, listdir, sep, walk
from os.path import basename, dirname, join
from pathlib import Path
from regex import compile as re_compile, match as regex_match
from signal import SIGINT, SIGTERM, signal
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from typing import Annotated, Dict, List, Literal, Optional, Union

from fastapi.routing import Mount


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("utils",), ("db",), ("gen",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

del deps_path, sys_path

from API import API  # type: ignore
from configurator import Configurator  # type: ignore
from database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import bytes_hash  # type: ignore

from fastapi import (
    BackgroundTasks,
    File,
    Form,
    Path as fastapi_Path,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, PlainTextResponse
from kombu import Connection, Queue

from core import (
    AddedPlugin,
    ApiConfig,
    app,
    BUNKERWEB_VERSION,
    CacheFileModel,
    CacheFileDataModel,
    ErrorMessage,
    Instance,
    Job,
    Job_cache,
    Plugin,
)
from utils import dict_to_frozenset, generate_external_plugins, install_plugin

DB = None
KOMBU_CONNECTION = None


def stop(status):
    global DB
    Path(sep, "var", "run", "bunkerweb", "core.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "core.healthy").unlink(missing_ok=True)
    if DB:
        del DB
    if KOMBU_CONNECTION:
        KOMBU_CONNECTION.release()
    _exit(status)


signal(SIGINT, partial(stop, 0))
signal(SIGTERM, partial(stop, 0))

API_CONFIG = ApiConfig("core", **environ)


SETTINGS_PATH = Path(sep, "usr", "share", "bunkerweb", "settings.json")
CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")

PLUGIN_KEYS = [
    "id",
    "name",
    "description",
    "version",
    "stream",
    "settings",
]

TOKEN_RX = r"^(?=.*?\p{Lowercase_Letter})(?=.*?\p{Uppercase_Letter})(?=.*?\d)(?=.*?[ !\"#$%&'()*+,\-./:;<=>?@[\\\]^_`{|}~]).{8,}$"
PLUGIN_ID_REGEX = re_compile(r"^[\w.-]{1,64}$")
EXTERNAL_PLUGIN_URLS_RX = re_compile(
    r"^( *((https?://|file:///)[-\w@:%.+~#=]+[-\w()!@:%+.~?&/=$#]*)(?!.*\2(?!.)) *)*$"
)
CUSTOM_CONFIGS_RX = re_compile(
    r"^([0-9a-z\.-]*)_?CUSTOM_CONF_(HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$"
)
BUNKERWEB_INSTANCES_RX = re_compile(r"([^: ]+)(:((\d+):)?(\w+))?")

LOGGER = setup_logger("CORE", API_CONFIG.log_level)

if (
    not API_CONFIG.WAIT_RETRY_INTERVAL.isdigit()
    or int(API_CONFIG.WAIT_RETRY_INTERVAL) < 1
):
    LOGGER.error(
        f"Invalid WAIT_RETRY_INTERVAL provided: {API_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer."
    )
    stop(1)

if API_CONFIG.check_token and not regex_match(TOKEN_RX, API_CONFIG.TOKEN):
    LOGGER.error(
        f"Invalid token provided: {API_CONFIG.TOKEN}, It must contain at least 8 characters, including at least 1 uppercase letter, 1 lowercase letter, 1 number and 1 special character (#@?!$%^&*-)."
    )
    stop(1)

TMP_ENV_PATH = Path(
    sep,
    "etc",
    "bunkerweb",
    "variables.env" if API_CONFIG.integration == "Linux" else sep,
    "var",
    "tmp",
    "bunkerweb",
    "variables.env",
)
TMP_ENV = dotenv_values(str(TMP_ENV_PATH))
MQ_PATH = None

LOGGER.info(f"🚀 {API_CONFIG.integration} integration detected")

if API_CONFIG.MQ_URI.startswith("filesystem:///"):
    MQ_PATH = Path(API_CONFIG.MQ_URI.replace("filesystem:///", ""))
    MQ_DATA_OUT_PATH = MQ_PATH.joinpath("data_out")
    MQ_DATA_IN_PATH = MQ_PATH.joinpath("data_in")
    MQ_DATA_OUT_PATH.mkdir(parents=True, exist_ok=True)
    MQ_DATA_IN_PATH.mkdir(parents=True, exist_ok=True)

    KOMBU_CONNECTION = Connection(
        "filesystem://",
        transport_options={
            "data_folder_in": str(MQ_PATH.joinpath("data_in")),
            "data_folder_out": str(MQ_PATH.joinpath("data_out")),
        },
    )
else:
    KOMBU_CONNECTION = Connection(API_CONFIG.MQ_URI)

with suppress(ConnectionRefusedError, gaierror, herror):
    KOMBU_CONNECTION.connect()

retries = 0
while not KOMBU_CONNECTION.connected and retries < 15:
    LOGGER.warning(
        f"Waiting for Kombu to be connected, retrying in {API_CONFIG.WAIT_RETRY_INTERVAL} seconds ..."
    )
    sleep(str(API_CONFIG.WAIT_RETRY_INTERVAL))
    with suppress(ConnectionRefusedError, gaierror, herror):
        KOMBU_CONNECTION.connect()
    retries += 1

if not KOMBU_CONNECTION.connected:
    LOGGER.error(
        f"Coudln't initiate a connection with Kombu with uri {API_CONFIG.MQ_URI}, exiting ..."
    )
    stop(1)

KOMBU_CONNECTION.release()

LOGGER.info("✅ Connection to Kombu succeeded")

scheduler_queue = Queue("scheduler", routing_key="scheduler")

DB = Database(LOGGER, API_CONFIG.DATABASE_URI)
SEMAPHORE = Semaphore(cpu_count() or 1)


db_is_initialized = DB.is_initialized()

db_config = {}
db_plugins = []
plugin_changes = False
if db_is_initialized:
    db_config = DB.get_config()
    db_plugins = DB.get_plugins(external=True)


def extract_plugin_data(filename: str) -> Optional[dict]:
    plugin_data = json_loads(Path(filename).read_text(encoding="utf-8"))

    if not all(key in plugin_data.keys() for key in PLUGIN_KEYS):
        LOGGER.warning(
            f"The plugin {dir_basename} doesn't have a valid plugin.json file, it's missing one or more of the following keys: {', '.join(PLUGIN_KEYS)}, ignoring it..."
        )
        return
    elif not PLUGIN_ID_REGEX.match(plugin_data["id"]):
        LOGGER.warning(
            f"The plugin {dir_basename} doesn't have a valid id, the id must match the following regex: {PLUGIN_ID_REGEX.pattern}, ignoring it..."
        )
        return

    plugin_content = BytesIO()
    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
        tar.add(_dir, arcname=dir_basename, recursive=True)
    plugin_content.seek(0, 0)
    checksum = bytes_hash(plugin_content)
    plugin_content.seek(0, 0)

    plugin_data.update(
        {
            "external": True,
            "page": Path(_dir, "ui").exists(),
            "data": plugin_content.getvalue(),
            "checksum": checksum,
        }
    )

    return plugin_data


LOGGER.info("Checking if any external plugin have been added or removed...")

manual_plugins = []
manual_plugins_ids = []
for filename in glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "plugin.json"))):
    _dir = dirname(filename)
    dir_basename = basename(_dir)
    in_db = False

    for db_plugin in db_plugins:
        if db_plugin["id"] == dir_basename and db_plugin["method"] != "manual":
            in_db = True

    if in_db:
        continue

    plugin_data = extract_plugin_data(filename)

    if not plugin_data:
        continue

    plugin_data["method"] = "manuel"

    manual_plugins_ids.append(plugin_data["id"])
    manual_plugins.append(plugin_data)

if not EXTERNAL_PLUGIN_URLS_RX.match(API_CONFIG.EXTERNAL_PLUGIN_URLS):
    LOGGER.error(
        f"Invalid external plugin URLs provided: {API_CONFIG.EXTERNAL_PLUGIN_URLS}, plugin download will be skipped"
    )
elif API_CONFIG.EXTERNAL_PLUGIN_URLS != db_config.get("EXTERNAL_PLUGIN_URLS", ""):
    if db_is_initialized:
        LOGGER.info("External plugins urls changed, refreshing external plugins...")
        for db_plugin in db_plugins:
            rmtree(
                str(EXTERNAL_PLUGINS_PATH.joinpath(db_plugin["id"])),
                ignore_errors=True,
            )
    else:
        LOGGER.info("Found external plugins to download, starting download...")

    plugin_changes = True
    threads = []
    for plugin_url in API_CONFIG.EXTERNAL_PLUGIN_URLS.strip().split(" "):
        thread = Thread(
            target=install_plugin,
            args=(plugin_url, LOGGER),
            kwargs={"semaphore": SEMAPHORE},
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    LOGGER.info("External plugins download finished")

# Check if any external plugin has been added by the user
external_plugins = []
for filename in glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "plugin.json"))):
    _dir = dirname(filename)
    dir_basename = basename(_dir)

    if dir_basename in manual_plugins_ids:
        continue

    plugin_data = extract_plugin_data(filename)

    if not plugin_data:
        continue

    plugin_data["method"] = "core"

    external_plugins.append(plugin_data)

external_plugins = list(chain(manual_plugins, external_plugins))
if db_is_initialized:
    if not plugin_changes:
        plugins = []
        for plugin in deepcopy(external_plugins):
            plugin.pop("data", None)
            plugin.pop("checksum", None)
            plugin.pop("jobs", None)
            plugin.pop("method", None)
            plugins.append(plugin)

        tmp_db_plugins = []
        for db_plugin in db_plugins.copy():
            db_plugin.pop("method", None)
            tmp_db_plugins.append(db_plugin)

        changes = {hash(dict_to_frozenset(d)) for d in plugins} != {
            hash(dict_to_frozenset(d)) for d in tmp_db_plugins
        }

    if plugin_changes:
        LOGGER.info("External plugins changed, refreshing database...")

        err = DB.update_external_plugins(external_plugins, delete_missing=True)
        if err:
            LOGGER.error(
                f"Couldn't save some manually added plugins to database: {err}",
            )

        generate_external_plugins(
            LOGGER, external_plugins, original_path=EXTERNAL_PLUGINS_PATH
        )

instances_config = API_CONFIG.model_dump(
    exclude=(
        "LISTEN_ADDR",
        "LISTEN_PORT",
        "WAIT_RETRY_INTERVAL",
        "TOKEN",
        "MQ_URI",
        "BUNKERWEB_INSTANCES",
        "log_level",
        "check_whitelist",
        "CHECK_WHITELIST",
        "check_token",
        "CHECK_TOKEN",
        "kubernetes_mode",
        "swarm_mode",
        "autoconf_mode",
        "whitelist",
        "WHITELIST",
        "integration",
    )
)

if API_CONFIG.kubernetes_mode or API_CONFIG.swarm_mode or API_CONFIG.autoconf_mode:
    instances_config["MULTISITE"] = "yes"

LOGGER.info("Computing config ...")

config = Configurator(
    str(SETTINGS_PATH),
    str(CORE_PLUGINS_PATH),
    external_plugins,
    instances_config,
    LOGGER,
)
config_files = config.get_config()

if not db_is_initialized:
    LOGGER.info(
        "Database not initialized, initializing ...",
    )
    ret, err = DB.init_tables(
        [
            config.get_settings(),
            config.get_plugins("core"),
            config.get_plugins("external"),
        ]
    )

    # Initialize database tables
    if err:
        LOGGER.error(
            f"Exception while initializing database : {err}",
        )
        stop(1)
    elif not ret:
        LOGGER.info(
            "Database tables are already initialized, skipping creation ...",
        )
    else:
        LOGGER.info("Database tables initialized")

    err = DB.initialize_db(
        version=BUNKERWEB_VERSION, integration=API_CONFIG.integration
    )

    if err:
        LOGGER.error(
            f"Can't Initialize database : {err}",
        )
        stop(1)
    else:
        LOGGER.info("✅ Database initialized")
else:
    err: str = DB.update_db_schema(BUNKERWEB_VERSION)

    if err and not err.startswith("The database"):
        LOGGER.error(f"Can't update database schema : {err}")
        stop(1)
    elif not err:
        LOGGER.info("✅ Database schema updated to latest version successfully")

del db_is_initialized

LOGGER.info("Checking if any custom config have been added or removed...")

db_configs = DB.get_custom_configs()
env_custom_configs = []
for k, v in instances_config.copy().items():
    match = CUSTOM_CONFIGS_RX.search(k)
    if match:
        custom_conf = match.groups()
        name = custom_conf[2].replace(".conf", "")
        env_custom_configs.append(
            {
                "value": v,
                "exploded": (
                    custom_conf[0],
                    custom_conf[1],
                    name,
                ),
            }
        )
        LOGGER.info(
            f"🛠️ Found custom conf env var \"{name}\"{' for service ' + custom_conf[0] if custom_conf[0] else ''} with type {custom_conf[1]}"
        )

if {hash(dict_to_frozenset(d)) for d in env_custom_configs} != {
    hash(dict_to_frozenset(d)) for d in db_configs if d["method"] == "core"
}:
    err = DB.save_custom_configs(env_custom_configs, "core")
    if err:
        LOGGER.error(
            f"Couldn't save some custom configs from env to database: {err}",
        )

    LOGGER.info("✅ Custom configs from env saved to database")

files_custom_configs = []
custom_configs_changes = False
max_num_sep = str(CONFIGS_PATH).count(sep) + (
    3 if config_files.get("MULTISITE", "no") == "yes" else 2
)
root_dirs = listdir(str(CONFIGS_PATH))
for root, dirs, files in walk(str(CONFIGS_PATH)):
    if root.count(sep) <= max_num_sep and (
        files or (dirs and basename(root) not in root_dirs)
    ):
        path_exploded = root.split("/")
        for file in files:
            content = Path(join(root, file)).read_text(encoding="utf-8")
            custom_conf = {
                "value": content,
                "exploded": (
                    f"{path_exploded.pop()}"
                    if path_exploded[-1] not in root_dirs
                    else None,
                    path_exploded[-1],
                    file.replace(".conf", ""),
                ),
            }
            saving = True

            for db_conf in db_configs:
                if (
                    db_conf["service_id"] == custom_conf["exploded"][0]
                    and db_conf["name"] == custom_conf["exploded"][2]
                ):
                    if db_conf["method"] != "manual":
                        saving = False
                    break

            if saving:
                files_custom_configs.append(custom_conf)

if {hash(dict_to_frozenset(d)) for d in files_custom_configs} != {
    hash(dict_to_frozenset(d)) for d in db_configs if d["method"] == "manual"
}:
    err = DB.save_custom_configs(files_custom_configs, "manual")
    if err:
        LOGGER.error(
            f"Couldn't save some manually created custom configs to database: {err}",
        )

    LOGGER.info("✅ Custom configs from files saved to database")

static_bunkerweb_instances = []
for bw_instance in BUNKERWEB_INSTANCES_RX.findall(API_CONFIG.BUNKERWEB_INSTANCES):
    static_bunkerweb_instances.append(
        {
            "hostname": bw_instance[0],
            "port": bw_instance[-2] or 5000,
            "server_name": bw_instance[-1] or "bwapi",
        }
    )

err = DB.update_instances(static_bunkerweb_instances)

if err:
    LOGGER.error(f"Can't update BunkerWeb instances to database : {err}")
    stop(1)

LOGGER.info("✅ BunkerWeb static instances updated to database")


def inform_scheduler(data: dict):
    LOGGER.info(f"📤 Informing the scheduler with data : {data}")

    with KOMBU_CONNECTION:
        with KOMBU_CONNECTION.default_channel as channel:
            with KOMBU_CONNECTION.Producer(channel) as producer:
                producer.publish(
                    data,
                    routing_key=scheduler_queue.routing_key,
                    serializer="json",
                    exchange=scheduler_queue.exchange,
                    retry=True,
                    declare=[scheduler_queue],
                )


# TODO handle when it's on autoconf/swarm/kubernetes mode the global config
if API_CONFIG.integration in ("Linux", "Docker"):
    if config_files != db_config:
        err = DB.save_config(config_files, "core")

        if err:
            LOGGER.error(
                f"Can't save config to database : {err}",
            )
            stop(1)

        LOGGER.info("✅ Config successfully saved to database")

        Thread(target=inform_scheduler, args=({"type": "run_once"},)).start()
else:
    while not DB.is_autoconf_loaded():
        LOGGER.warning(
            f"Autoconf is not loaded yet in the database, retrying in {API_CONFIG.WAIT_RETRY_INTERVAL} seconds ..."
        )
        sleep(int(API_CONFIG.WAIT_RETRY_INTERVAL))


def update_app_mounts():
    LOGGER.info("Updating app mounts ...")

    for route in app.routes:
        if isinstance(route, Mount):
            # remove the subapp from the routes
            app.routes.remove(route)

    for subapi in glob(str(CORE_PLUGINS_PATH.joinpath("*", "api"))) + glob(
        str(EXTERNAL_PLUGINS_PATH.joinpath("*", "api"))
    ):
        subapi_plugin = basename(dirname(subapi))
        LOGGER.info(f"Mounting subapi {subapi_plugin} ...")
        try:
            loader = SourceFileLoader(f"{subapi_plugin}_api", join(subapi, "main.py"))
            subapi_module = loader.load_module()
            root_path = getattr(subapi_module, "root_path", f"/{subapi_plugin}")

            if hasattr(subapi_module, "app"):
                app.mount(
                    root_path,
                    getattr(subapi_module, "app"),
                    basename(dirname(subapi)),
                )

                LOGGER.info(
                    f"✅ The subapi for the plugin {subapi_plugin} has been mounted successfully, root path: {root_path}"
                )
            else:
                LOGGER.error(f"Couldn't mount subapi {subapi_plugin}, no app found")
        except Exception as e:
            LOGGER.error(f"Exception while mounting subapi {subapi_plugin} : {e}")


@app.on_event("startup")
async def startup_event():
    update_app_mounts()


@app.on_event("shutdown")
async def shutdown_event():
    del DB
    KOMBU_CONNECTION.release()


@app.middleware("http")
async def validate_request(request: Request, call_next):
    if API_CONFIG.check_whitelist:
        if not API_CONFIG.whitelist:
            LOGGER.warning(
                f'Unauthorized access attempt from {request.client.host} (whitelist check is set to "yes" but the whitelist is empty), aborting...'
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"}
            )

        remote_ip = ip_address(request.client.host)
        for whitelist in API_CONFIG.whitelist:
            if isinstance(whitelist, IPv4Network) or isinstance(whitelist, IPv6Network):
                if remote_ip in whitelist:
                    break
            elif isinstance(whitelist, IPv4Address) or isinstance(
                whitelist, IPv6Address
            ):
                if remote_ip == whitelist:
                    break
        else:
            LOGGER.warning(
                f"Unauthorized access attempt from {remote_ip} (not in whitelist), aborting..."
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"}
            )

    if API_CONFIG.check_token:
        if request.headers.get("Authorization") != f"Bearer {API_CONFIG.TOKEN}":
            LOGGER.warning(
                f"Unauthorized access attempt from {request.client.host} (invalid token), aborting..."
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"}
            )

    return await call_next(request)


@app.get("/ping", tags=["misc"])
async def get_ping() -> JSONResponse:
    """Get BunkerWeb API ping"""
    return JSONResponse(content={"message": "pong"})


@app.get("/version", tags=["misc"])
async def get_version() -> JSONResponse:
    """Get BunkerWeb API version"""
    return JSONResponse(content={"message": BUNKERWEB_VERSION})


@app.get("/config", tags=["misc"])
async def get_config() -> JSONResponse:
    """Get config from Database"""
    return JSONResponse(content=DB.get_config())


@app.post("/config", tags=["misc"])
async def update_config(
    config: dict, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Update config in Database"""
    err = DB.save_config(config, "core")

    if err:
        LOGGER.error(f"Can't save config to database : {err}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})

    LOGGER.info("✅ Config successfully saved to database")

    return JSONResponse(content={"message": "Config successfully saved"})


@app.get(
    "/instances",
    response_model=List[Instance],
    tags=["instances"],
    summary="Get BunkerWeb instances",
    response_description="BunkerWeb instances",
)
async def get_instances():
    """
    Get BunkerWeb instances with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    return DB.get_instances()


@app.get(
    "/instances/{instance_hostname}",
    response_model=Instance,
    tags=["instances"],
    summary="Get a BunkerWeb instance",
    response_description="A BunkerWeb instance",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        }
    },
)
async def get_instance(
    instance_hostname: Annotated[
        str,
        fastapi_Path(
            title="The hostname of the instance", min_length=1, max_length=256
        ),
    ]
):
    """
    Get a BunkerWeb instance with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": f"Instance {instance_hostname} not found"},
        )

    return db_instance


@app.post(
    "/instances",
    status_code=status.HTTP_201_CREATED,
    tags=["instances"],
    summary="Add a BunkerWeb instance",
    response_description="A BunkerWeb instance",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Instance already exists",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def add_instance(instance: Instance) -> JSONResponse:
    """
    Add a BunkerWeb instance with the following information:

    - **hostname**: The hostname of the instance
    - **port**: The port of the instance
    - **server_name**: The server name of the instance
    """
    db_instance = DB.get_instance(instance.hostname)

    if db_instance:
        message = f"Instance {instance.hostname} already exists"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"message": message}
        )

    error = DB.add_instance(**instance.to_dict())

    if error:
        LOGGER.error(f"Can't add instance to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    LOGGER.info(f"✅ Instance {instance.hostname} successfully added to database")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Instance successfully added"},
    )


@app.delete(
    "/instances/{instance_hostname}",
    tags=["instances"],
    summary="Delete a BunkerWeb instance",
    response_description="A BunkerWeb instance",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_instance(instance_hostname: str) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )

    error = DB.remove_instance(instance_hostname)

    if error:
        LOGGER.error(f"Can't remove instance to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    LOGGER.info(f"✅ Instance {instance_hostname} successfully removed from database")

    return JSONResponse(
        content={"message": "Instance successfully removed"},
    )


@app.post(
    "/instances/{instance_hostname}/{action}",
    tags=["instances"],
    summary="Send an action to a BunkerWeb instance",
    response_description="A BunkerWeb instance",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Instance not found",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid action",
            "model": ErrorMessage,
        },
    },
)
async def send_instance_action(
    instance_hostname: str, action: Literal["start", "stop", "restart", "reload"]
) -> JSONResponse:
    """
    Delete a BunkerWeb instance
    """
    db_instance = DB.get_instance(instance_hostname)

    if not db_instance:
        message = f"Instance {instance_hostname} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )

    instance_api = API(
        f"http://{db_instance['hostname']}:{db_instance['port']}",
        db_instance["server_name"],
    )

    sent, err, status_code, resp = instance_api.request("POST", f"/{action}")

    if not sent:
        error = f"Can't send API request to {instance_api.endpoint}{action} : {err}"
        LOGGER.error(error)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )
    else:
        if status_code != 200:
            error = f"Error while sending API request to {instance_api.endpoint}{action} : status = {resp['status']}, msg = {resp['msg']}"
            LOGGER.error(error)
            return JSONResponse(status_code=status_code, content={"message": error})

    LOGGER.info(f"Successfully sent API request to {instance_api.endpoint}{action}")

    return JSONResponse(content={"message": "Action successfully sent"})


@app.get(
    "/plugins",
    response_model=List[Plugin],
    tags=["plugins"],
    summary="Get all plugins",
    response_description="Plugins",
)
async def get_plugins():
    """
    Get core and external plugins from the database.
    """
    return DB.get_plugins()


@app.post(
    "/plugins",
    status_code=status.HTTP_201_CREATED,
    tags=["plugins"],
    summary="Add a plugin",
    response_description="Plugins",
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Plugin already exists",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def add_plugin(
    plugin: AddedPlugin, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Add a plugin to the database.
    """
    error = DB.add_external_plugin(plugin.to_dict())

    if error == "exists":
        message = f"Plugin {plugin.id} already exists"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't add plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts)

    LOGGER.info(f"✅ Plugin {plugin.id} successfully added to database")

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Plugin successfully added"},
    )


@app.patch(
    "/plugins/{plugin_id}",
    tags=["plugins"],
    summary="Update a plugin",
    response_description="Plugins",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Plugin not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Can't update a core plugin",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def update_plugin(
    plugin_id: str, plugin: AddedPlugin, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Update a plugin from the database.
    """
    error = DB.update_external_plugin(plugin_id, plugin.to_dict())

    if error == "not_found":
        message = f"Plugin {plugin.id} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif error == "not_external":
        message = f"Can't update a core plugin ({plugin.id})"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't update plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts)

    LOGGER.info(f"✅ Plugin {plugin.id} successfully updated to database")

    return JSONResponse(content={"message": "Plugin successfully updated"})


@app.delete(
    "/plugins/{plugin_id}",
    tags=["plugins"],
    summary="Delete a plugin",
    response_description="Plugins",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Plugin not found",
            "model": ErrorMessage,
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "Can't delete a core plugin",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_plugin(
    plugin_id: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Delete a plugin from the database.
    """
    error = DB.remove_external_plugin(plugin_id)

    if error == "not_found":
        message = f"Plugin {plugin_id} not found"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"message": message}
        )
    elif error == "not_external":
        message = f"Can't delete a core plugin ({plugin_id})"
        LOGGER.warning(message)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN, content={"message": message}
        )
    elif error:
        LOGGER.error(f"Can't delete plugin to database : {error}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": error},
        )

    background_tasks.add_task(inform_scheduler, {"type": "run_once"})
    background_tasks.add_task(
        generate_external_plugins, LOGGER, None, DB, original_path=EXTERNAL_PLUGINS_PATH
    )
    background_tasks.add_task(update_app_mounts)

    LOGGER.info(f"✅ Plugin {plugin.id} successfully deleted from database")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Plugin successfully deleted"},
    )


@app.get(
    "/plugins/external/files",
    tags=["plugins"],
    summary="Get all external plugins files in a tar archive",
    response_description="Tar archive containing all external plugins files",
)
async def get_plugins_files():
    """
    Get all external plugins files in a tar archive.
    """
    plugins_files = BytesIO()
    with tar_open(
        fileobj=plugins_files, mode="w:gz", compresslevel=9, dereference=True
    ) as tar:
        tar.add(
            str(EXTERNAL_PLUGINS_PATH),
            arcname=".",
            recursive=True,
        )
    plugins_files.seek(0, 0)

    return Response(
        content=plugins_files.getvalue(),
        media_type="application/x-tar",
        headers={"Content-Disposition": "attachment; filename=plugins.tar.gz"},
    )


@app.get(
    "/jobs",
    response_model=Dict[str, Job],
    tags=["jobs"],
    summary="Get all jobs",
    response_description="Jobs",
)
async def get_jobs():
    """
    Get all jobs from the database.
    """
    return DB.get_jobs()


@app.post(
    "/jobs/{job_name}/status",
    tags=["jobs"],
    summary="Adds a new job run status to the database",
    response_description="Job",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Missing start_date",
            "model": ErrorMessage,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def add_job_run(
    job_name: str,
    data: Dict[Literal["success", "start_date", "end_date"], Union[bool, float]],
) -> JSONResponse:
    """
    Update a job run status in the database.
    """
    start_date = data.get("start_date")

    if not start_date:
        LOGGER.error("Missing start_date")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Missing start_date"},
        )

    start_date = datetime.fromtimestamp(start_date)
    end_date = data.get("end_date")

    if end_date:
        end_date = datetime.fromtimestamp(end_date)

    err = DB.add_job_run(job_name, data.get("success", False), start_date, end_date)

    if err:
        LOGGER.error(f"Can't add job {job_name} run in database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": err},
        )

    LOGGER.info(
        f"✅ Job {job_name} run successfully added to database with run status: {'✅' if data.get('success', False) else '❌'}"
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={"message": "Job run successfully added to database"},
    )


@app.post(
    "/jobs/{job_name}/run",
    tags=["jobs"],
    summary="Run a job",
    response_description="Job",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found",
            "model": ErrorMessage,
        }
    },
)
async def run_job(job_name: str, background_tasks: BackgroundTasks):
    """
    Run a job.
    """
    job = DB.get_job(job_name)

    if not job:
        LOGGER.warning(f"Job {job_name} not found")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": f"Job {job_name} not found"},
        )

    background_tasks.add_task(
        inform_scheduler, {"type": "run_single", "job_name": job_name}
    )

    return JSONResponse(content={"result": "ok"})


@app.get(
    "/jobs/{job_name}/cache/{file_name}",
    response_model=Job_cache,
    tags=["jobs"],
    summary="Get a file from the cache",
    response_description="Job cache",
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "File not found",
            "model": ErrorMessage,
        }
    },
)
async def get_cache(
    job_name: str,
    file_name: str,
    data: CacheFileDataModel,
):
    """
    Get a file from the cache.
    """
    cached_file = DB.get_job_cache(
        job_name,
        file_name,
        service_id=data.service_id,
        with_info=data.with_info,
        with_data=data.with_data,
    )

    if not cached_file:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "File not found"},
        )

    return (
        {}
        | (
            {
                "last_update": cached_file.last_update.timestamp(),
                "checksum": cached_file.checksum,
            }
            if data.with_info
            else {}
        )
        | ({"data": cached_file.data} if data.with_data else {})
    )


@app.put(
    "/jobs/{job_name}/cache/{file_name}",
    tags=["jobs"],
    summary="Upload a file to the cache",
    response_description="Job cache",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
        status.HTTP_201_CREATED: {
            "description": "File successfully uploaded to cache",
            "model": ErrorMessage,
        },
        status.HTTP_200_OK: {
            "description": "File successfully updated in cache",
            "model": ErrorMessage,
        },
    },
)
async def update_cache(
    job_name: str,
    file_name: str,
    cache_file: Annotated[bytes, File()] = None,
    service_id: Annotated[str, Form()] = None,
    checksum: Annotated[str, Form()] = None,
):
    """
    Upload a file to the cache.
    """
    # TODO add a background task that sends a request to the instances to update the cache
    resp = DB.update_job_cache(
        job_name,
        file_name,
        cache_file,
        service_id=service_id,
        checksum=checksum,
    )

    if resp not in ("created", "updated"):
        LOGGER.error(f"Can't update job {job_name} cache in database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": err},
        )

    LOGGER.info(f"✅ Job {job_name} cache successfully updated in database")

    return JSONResponse(
        status_code=status.HTTP_200_OK
        if resp == "updated"
        else status.HTTP_201_CREATED,
        content={"message": "File successfully uploaded to cache"},
    )


@app.delete(
    "/jobs/{job_name}/cache/{file_name}",
    tags=["jobs"],
    summary="Delete a file from the cache",
    response_description="Job cache",
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error",
            "model": ErrorMessage,
        },
    },
)
async def delete_cache(job_name: str, file_name: str, data: CacheFileModel):
    """
    Delete a file from the cache.
    """
    # TODO add a background task that sends a request to the instances to delete the cache
    err = DB.delete_job_cache(job_name, file_name, service_id=data.service_id)

    if err:
        LOGGER.error(f"Can't delete job {job_name} cache in database : {err}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": err},
        )

    LOGGER.info(f"✅ Job {job_name} cache successfully deleted from database")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "File successfully deleted from cache"},
    )


if __name__ == "__main__":
    from uvicorn import run

    run(
        app,
        host=API_CONFIG.LISTEN_ADDR,
        port=API_CONFIG.LISTEN_PORT,
        reload=True,
        proxy_headers=False,
        server_header=False,
        date_header=False,
    )
