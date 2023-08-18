#!/usr/bin/python3

from copy import deepcopy
from glob import glob
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
from threading import Thread
from dotenv import dotenv_values
from os import listdir, sep, walk
from os.path import basename, dirname, join
from pathlib import Path
from fastapi.datastructures import Address
from regex import compile as re_compile, match as regex_match
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from typing import Optional


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("api",), ("db",), ("gen",), ("utils",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from fastapi import Request, status
from fastapi.responses import JSONResponse
from redis.client import Redis

from configurator import Configurator  # type: ignore
from jobs import bytes_hash  # type: ignore
from .core import app, BUNKERWEB_VERSION
from .dependencies import (
    API_CONFIG,
    CONFIGS_PATH,
    CORE_PLUGINS_PATH,
    DB,
    dict_to_frozenset,
    EXTERNAL_PLUGINS_PATH,
    generate_external_plugins,
    HEALTHY_PATH,
    inform_scheduler,
    install_plugin,
    KOMBU_CONNECTION,
    LOGGER,
    SETTINGS_PATH,
    stop,
    update_app_mounts,
    update_api_caller,
)

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

    plugin_data["method"] = "manual"

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
        "MAX_WORKERS",
        "MAX_THREADS",
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

update_api_caller()

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

REDIS_HOST: Optional[str] = config_files.get("REDIS_HOST", None)
REDIS_PORT: Optional[int] = None
REDIS_DATABASE: Optional[int] = None
REDIS_SSL: bool = False
REDIS_TIMEOUT: Optional[float] = None


def listen_dynamic_instances():
    if not any((REDIS_HOST, REDIS_PORT, REDIS_DATABASE, REDIS_TIMEOUT)):
        LOGGER.warning(
            "USE_REDIS is set to yes but one or more of the following variables are not defined: REDIS_HOST, REDIS_PORT, REDIS_DATABASE, REDIS_TIMEOUT, app will not listen for dynamic instances"
        )
        return

    assert REDIS_HOST
    assert REDIS_PORT
    assert REDIS_DATABASE
    assert REDIS_SSL
    assert REDIS_TIMEOUT

    redis_client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DATABASE,
        ssl=REDIS_SSL,
        socket_timeout=REDIS_TIMEOUT,
    )

    retries = 0
    connected = False
    while not connected:
        try:
            redis_client.ping()
            connected = True
        except Exception:
            retries += 1
            if retries > 10:
                LOGGER.error(
                    f"Couldn't connect to Redis after 10 retries, app will not listen for dynamic instances"
                )
                return
            LOGGER.warning(
                f"Can't connect to Redis, retrying in {API_CONFIG.WAIT_RETRY_INTERVAL} seconds ..."
            )
            sleep(int(API_CONFIG.WAIT_RETRY_INTERVAL))


if config_files.get("USE_REDIS", "no") == "yes":
    if REDIS_HOST:
        redis_port = config_files.get("REDIS_PORT", "6379")
        if not redis_port.isdigit() or not (1 <= int(redis_port) <= 65535):
            LOGGER.warning(
                f"Invalid REDIS_PORT provided: {redis_port}, It must be an integer between 1 and 65535, port will default to 6379"
            )
            redis_port = 6379
        REDIS_PORT = int(redis_port)
        del redis_port

        redis_database = config_files.get("REDIS_DATABASE", "0")
        if not redis_database.isdigit() or not (0 <= int(redis_database) <= 15):
            LOGGER.warning(
                f"Invalid REDIS_DATABASE provided: {redis_database}, It must be an integer between 0 and 15, database will default to 0"
            )
            redis_database = 0
        REDIS_DATABASE = int(redis_database)
        del redis_database

        if config_files.get("REDIS_SSL", "no") == "yes":
            REDIS_SSL = True

        redis_timeout = config_files.get("REDIS_TIMEOUT", "1000")  # ms
        if not redis_timeout.isdigit() or int(redis_timeout) < 1:
            LOGGER.warning(
                f"Invalid REDIS_TIMEOUT provided: {redis_timeout}, It must be a positive integer, timeout will default to 1000 ms"
            )
            redis_timeout = 1000
        REDIS_TIMEOUT = float(int(redis_timeout) / 1000)
        del redis_timeout

        Thread(target=listen_dynamic_instances, daemon=True).start()
    else:
        LOGGER.warning(
            "USE_REDIS is set to yes but REDIS_HOST is not defined, app will not listen for dynamic instances"
        )


@app.middleware("http")
async def validate_request(request: Request, call_next):
    try:
        assert isinstance(request.client, Address)
    except AssertionError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"}
        )

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


# Include the routers to the main app

from .routers import config, custom_configs, instances, jobs, plugins

app.include_router(config.router)
app.include_router(custom_configs.router)
app.include_router(instances.router)
app.include_router(jobs.router)
app.include_router(plugins.router)

update_app_mounts(app)

if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")


if __name__ == "__main__":
    from uvicorn import run

    if (
        not API_CONFIG.LISTEN_PORT.isdigit()
        or int(API_CONFIG.LISTEN_PORT) < 1
        or int(API_CONFIG.LISTEN_PORT) > 65535
    ):
        LOGGER.error(
            f"Invalid LISTEN_PORT provided: {API_CONFIG.LISTEN_PORT}, It must be an integer between 1 and 65535."
        )
        stop(1)

    run(
        app,
        host=API_CONFIG.LISTEN_ADDR,
        port=int(API_CONFIG.LISTEN_PORT),
        reload=True,
        proxy_headers=False,
        server_header=False,
        date_header=False,
    )
