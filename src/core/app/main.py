#!/usr/bin/python3

from contextlib import suppress
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
from json import JSONDecodeError, loads as json_loads
from shutil import rmtree
from threading import Event, Thread
from os import listdir, sep, walk
from os.path import basename, dirname, join
from pathlib import Path
from signal import SIGINT, SIGTERM, signal
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from typing import Optional

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("db",), ("gen",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from dotenv import dotenv_values
from fastapi import FastAPI, Request, status
from fastapi.datastructures import Address
from fastapi.responses import JSONResponse
from redis.client import Redis
from regex import compile as re_compile

from API import API  # type: ignore
from api_caller import ApiCaller  # type: ignore
from configurator import Configurator  # type: ignore
from jobs import bytes_hash  # type: ignore
from .core import BUNKERWEB_VERSION, description, tags_metadata
from .dependencies import (
    CORE_CONFIG,
    CONFIGS_PATH,
    CORE_PLUGINS_PATH,
    DB,
    dict_to_frozenset,
    EXTERNAL_PLUGINS_PATH,
    generate_external_plugins,
    HEALTHY_PATH,
    install_plugin,
    SCHEDULER,
    run_jobs,
    SEMAPHORE,
    SETTINGS_PATH,
    seen_instance,
    stop,
    test_and_send_to_instances,
    update_app_mounts,
)

PLUGIN_KEYS = [
    "id",
    "name",
    "description",
    "version",
    "stream",
    "settings",
]

PLUGIN_ID_REGEX = re_compile(r"^[\w.-]{1,64}$")
CUSTOM_CONFIGS_RX = re_compile(r"^((?P<service_id>[^ ]{,255})_)?CUSTOM_CONF_(?P<type>HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(?P<name>.+)$")

stop_event = Event()


def stop_app(status):
    stop_event.set()
    stop(status)


def exit_handler(signum, frame):
    CORE_CONFIG.logger.info("Stop signal received, exiting...")
    stop_app(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)


# ? APP
app = FastAPI(
    title="BunkerWeb API",
    description=description,
    summary="The API used by BunkerWeb to communicate with the database and the instances",
    version=BUNKERWEB_VERSION,
    contact={
        "name": "BunkerWeb Team",
        "url": "https://bunkerweb.io",
        "email": "contact@bunkerity.com",
    },
    license_info={
        "name": "GNU Affero General Public License v3.0",
        "identifier": "AGPL-3.0",
        "url": "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE.md",
    },
    openapi_tags=tags_metadata,
)


TMP_ENV_PATH = Path(
    sep,
    "etc",
    "bunkerweb",
    "variables.env" if CORE_CONFIG.integration == "Linux" else sep,
    "var",
    "tmp",
    "bunkerweb",
    "variables.env",
)
TMP_ENV = dotenv_values(str(TMP_ENV_PATH))

INSTANCES_API_CALLER = ApiCaller()

db_is_initialized = DB.is_initialized()

db_config = {}
db_plugins = []
plugin_changes = False
if db_is_initialized:
    resp = DB.set_scheduler_initialized(False)

    if resp:
        CORE_CONFIG.logger.error(
            f"Can't set scheduler as not initialized : {resp}",
        )

    db_config = DB.get_config()

    if isinstance(db_config, str):
        CORE_CONFIG.logger.error(
            f"Can't get config from database : {db_config}",
        )
        stop_app(1)

    db_plugins = DB.get_plugins(external=True)

    if isinstance(db_plugins, str):
        CORE_CONFIG.logger.warning(
            f"Can't get plugins from database : {db_plugins}",
        )
        db_plugins = []


def extract_plugin_data(filename: str) -> Optional[dict]:
    plugin_data = json_loads(Path(filename).read_text(encoding="utf-8"))

    if not all(key in plugin_data.keys() for key in PLUGIN_KEYS):
        CORE_CONFIG.logger.warning(f"The plugin {dir_basename} doesn't have a valid plugin.json file, it's missing one or more of the following keys: {', '.join(PLUGIN_KEYS)}, ignoring it...")
        return
    elif not PLUGIN_ID_REGEX.match(plugin_data["id"]):
        CORE_CONFIG.logger.warning(f"The plugin {dir_basename} doesn't have a valid id, the id must match the following regex: {PLUGIN_ID_REGEX.pattern}, ignoring it...")
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


CORE_CONFIG.logger.info("Checking if any external plugin have been added or removed...")

manual_plugins = []
manual_plugins_ids = []
for filename in glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "plugin.json"))):
    _dir = dirname(filename)
    dir_basename = basename(_dir)
    in_db = False

    for db_plugin in db_plugins:
        if db_plugin["id"] == dir_basename and db_plugin["method"] != "static":
            in_db = True

    if in_db:
        continue

    plugin_data = extract_plugin_data(filename)

    if not plugin_data:
        continue

    plugin_data["method"] = "static"

    manual_plugins_ids.append(plugin_data["id"])
    manual_plugins.append(plugin_data)

if CORE_CONFIG.external_plugin_urls_str != db_config.get("EXTERNAL_PLUGIN_URLS", ""):
    if db_is_initialized:
        CORE_CONFIG.logger.info("External plugins urls changed, refreshing external plugins...")
        for db_plugin in db_plugins:
            rmtree(
                str(EXTERNAL_PLUGINS_PATH.joinpath(db_plugin["id"])),
                ignore_errors=True,
            )
    else:
        CORE_CONFIG.logger.info("Found external plugins to download, starting download...")

    plugin_changes = True
    threads = []
    for plugin_url in CORE_CONFIG.external_plugin_urls:
        thread = Thread(
            target=install_plugin,
            args=(plugin_url, CORE_CONFIG.logger),
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    CORE_CONFIG.logger.info("External plugins download finished")

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

        plugin_changes = {hash(dict_to_frozenset(d)) for d in plugins} != {hash(dict_to_frozenset(d)) for d in tmp_db_plugins}

    if plugin_changes:
        CORE_CONFIG.logger.info("External plugins changed, refreshing database...")

        err = DB.update_external_plugins(external_plugins, delete_missing=True)
        if err:
            CORE_CONFIG.logger.error(
                f"Couldn't save some manually added plugins to database: {err}",
            )

        generate_external_plugins(external_plugins, original_path=EXTERNAL_PLUGINS_PATH)

CORE_CONFIG.logger.info("Computing config ...")

config = Configurator(
    str(SETTINGS_PATH),
    str(CORE_PLUGINS_PATH),
    external_plugins,
    CORE_CONFIG.settings,
    CORE_CONFIG.logger,
)
config_files = config.get_config()

if not db_is_initialized:
    CORE_CONFIG.logger.info(
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
        CORE_CONFIG.logger.error(
            f"Exception while initializing database : {err}",
        )
        stop_app(1)
    elif not ret:
        CORE_CONFIG.logger.info(
            "Database tables are already initialized, skipping creation ...",
        )
    else:
        CORE_CONFIG.logger.info("Database tables initialized")

    err = DB.initialize_db(version=BUNKERWEB_VERSION, integration=CORE_CONFIG.integration)

    if err:
        CORE_CONFIG.logger.error(
            f"Can't Initialize database : {err}",
        )
        stop_app(1)
    else:
        CORE_CONFIG.logger.info("✅ Database initialized")
else:
    err: str = DB.update_db_schema(BUNKERWEB_VERSION)

    if err and not err.startswith("The database"):
        CORE_CONFIG.logger.error(f"Can't update database schema : {err}")
        stop_app(1)
    elif not err:
        CORE_CONFIG.logger.info("✅ Database schema updated to latest version successfully")

CORE_CONFIG.logger.info("Checking if any custom config have been added or removed...")

db_configs = DB.get_custom_configs()
env_custom_configs = []
for k, v in CORE_CONFIG.settings.copy().items():
    match = CUSTOM_CONFIGS_RX.search(k)
    if match:
        name = match.group("name").replace(".conf", "")
        env_custom_configs.append(
            {
                "value": v,
                "exploded": (
                    match.group("service_id"),
                    match.group("type"),
                    name,
                ),
            }
        )
        CORE_CONFIG.logger.info(f"🛠️ Found custom conf env var \"{name}\"{' for service ' + match.group('service_id') if match.group('service_id') else ''} with type {match.group('type')}")

if {hash(dict_to_frozenset(d)) for d in env_custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs if d["method"] == "core"}:
    err = DB.save_custom_configs(env_custom_configs, "core")
    if err:
        CORE_CONFIG.logger.error(
            f"Couldn't save some custom configs from env to database: {err}",
        )

    CORE_CONFIG.logger.info("✅ Custom configs from env saved to database")

files_custom_configs = []
custom_configs_changes = False
max_num_sep = str(CONFIGS_PATH).count(sep) + (3 if config_files.get("MULTISITE", "no") == "yes" else 2)
root_dirs = listdir(str(CONFIGS_PATH))
for root, dirs, files in walk(str(CONFIGS_PATH)):
    if root.count(sep) <= max_num_sep and (files or (dirs and basename(root) not in root_dirs)):
        path_exploded = root.split("/")
        for file in files:
            content = Path(join(root, file)).read_text(encoding="utf-8")
            custom_conf = {
                "value": content,
                "exploded": (
                    f"{path_exploded.pop()}" if path_exploded[-1] not in root_dirs else None,
                    path_exploded[-1],
                    file.replace(".conf", ""),
                ),
            }
            saving = True

            for db_conf in db_configs:
                if db_conf["service_id"] == custom_conf["exploded"][0] and db_conf["name"] == custom_conf["exploded"][2]:
                    if db_conf["method"] != "static":
                        saving = False
                    break

            if saving:
                files_custom_configs.append(custom_conf)

if {hash(dict_to_frozenset(d)) for d in files_custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs if d["method"] == "static"}:
    err = DB.save_custom_configs(files_custom_configs, "static")
    if err:
        CORE_CONFIG.logger.error(
            f"Couldn't save some manually created custom configs to database: {err}",
        )

    CORE_CONFIG.logger.info("✅ Custom configs from files saved to database")

err = DB.refresh_instances([], "dynamic")

if err:
    CORE_CONFIG.logger.error(f"Can't clear dynamic BunkerWeb instances to database : {err}")
    stop_app(1)

err = DB.refresh_instances(CORE_CONFIG.bunkerweb_instances, "static")

if err:
    CORE_CONFIG.logger.error(f"Can't refresh static BunkerWeb instances to database : {err}")
    stop_app(1)

CORE_CONFIG.logger.info("✅ BunkerWeb static instances updated to database")

if config_files != db_config:
    err = DB.save_config(config_files, "core")

    if err:
        CORE_CONFIG.logger.error(
            f"Can't save config to database : {err}",
        )
        stop_app(1)

    CORE_CONFIG.logger.info("✅ Config successfully saved to database")

if CORE_CONFIG.integration in ("Linux", "Docker"):
    CORE_CONFIG.logger.info("Executing scheduler ...")
    DB.set_scheduler_initialized()
    threads = [
        Thread(
            target=test_and_send_to_instances,
            args=({"plugins", "custom_configs", "config"},),
            kwargs={"no_reload": True},
        ),
        Thread(target=run_jobs),
    ]

    for thread in threads:
        thread.start()

REDIS_HOST: Optional[str] = config_files.get("REDIS_HOST", None)
REDIS_PORT: Optional[int] = None
REDIS_DATABASE: Optional[int] = None
REDIS_SSL: bool = False
REDIS_TIMEOUT: Optional[float] = None


def listen_dynamic_instances():
    SEMAPHORE.acquire()

    if not any((REDIS_HOST, REDIS_PORT, REDIS_DATABASE, REDIS_TIMEOUT)):
        CORE_CONFIG.logger.warning("listen_dynamic_instances - USE_REDIS is set to yes but one or more of the following variables are not defined: REDIS_HOST, REDIS_PORT, REDIS_DATABASE, REDIS_TIMEOUT, app will not listen for dynamic instances")
        SEMAPHORE.release()
        return

    assert REDIS_HOST is not None
    assert REDIS_PORT is not None
    assert REDIS_DATABASE is not None
    assert REDIS_TIMEOUT is not None

    redis_client = Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DATABASE,
        ssl=REDIS_SSL,
        socket_timeout=REDIS_TIMEOUT,
    )

    CORE_CONFIG.logger.info("listen_dynamic_instances - USE_REDIS is set to yes, trying to connect to Redis ...")

    retries = 0
    connected = False
    while not connected:
        try:
            redis_client.ping()
            connected = True
        except Exception:
            retries += 1
            if retries > 10:
                CORE_CONFIG.logger.error("listen_dynamic_instances - Couldn't connect to Redis after 10 retries, app will not listen for dynamic instances")
                SEMAPHORE.release()
                return
            CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Can't connect to Redis, retrying in {CORE_CONFIG.WAIT_RETRY_INTERVAL} seconds ...")
            sleep(int(CORE_CONFIG.WAIT_RETRY_INTERVAL))

    CORE_CONFIG.logger.info("listen_dynamic_instances - ✅ Connected to Redis")

    pubsub = redis_client.pubsub()

    CORE_CONFIG.logger.info('listen_dynamic_instances - Subscribing to Redis channel "bw-instances" ...')

    while not stop_event.is_set():
        try:
            pubsub.subscribe("bw-instances")
            break
        except ConnectionError:
            CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Can't subscribe to Redis channel, retrying in {CORE_CONFIG.WAIT_RETRY_INTERVAL} seconds ...")
            sleep(int(CORE_CONFIG.WAIT_RETRY_INTERVAL))

    CORE_CONFIG.logger.info('listen_dynamic_instances - ✅ Subscribed to Redis channel "bw-instances", starting to listen for dynamic instances ...')

    try:
        while not stop_event.is_set():
            pubsub_message = None
            try:
                pubsub_message = pubsub.get_message(timeout=15)
            except (ConnectionError, TimeoutError):
                while not stop_event.is_set():
                    with suppress(ConnectionError):
                        pubsub.close()
                        pubsub.subscribe("bw-instances")
                        break
                    sleep(int(CORE_CONFIG.WAIT_RETRY_INTERVAL))

            try:
                if isinstance(pubsub_message, dict) and pubsub_message.get("type") == "message":
                    CORE_CONFIG.logger.info(f"listen_dynamic_instances - Redis - New message received: {pubsub_message}")
                    try:
                        message = json_loads(pubsub_message["data"])
                    except JSONDecodeError:
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Can't decode message data: {pubsub_message['data']}, ignoring it ...")
                        continue

                    if message.get("type") != "startup":
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Invalid message type: {message.get('type', 'missing key')}, ignoring it ...")
                        continue
                    elif "data" not in message:
                        CORE_CONFIG.logger.warning("listen_dynamic_instances - Missing message data, ignoring it ...")
                        continue

                    data = message["data"]

                    if not all(key in data for key in ("hostname", "listening_port", "server_name")):
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Invalid message data: {data}, ignoring it ...")
                        continue
                    elif len(data["hostname"]) > 256:
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Invalid hostname provided: {data['hostname']}, it must be less than 256 characters, ignoring it ...")
                        continue
                    elif not data["listening_port"].isdigit() or not (1 <= int(data["listening_port"]) <= 65535):
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Invalid listening_port provided: {data['listening_port']}, it must be an integer between 1 and 65535, ignoring it ...")
                        continue
                    elif len(data["server_name"]) > 256:
                        CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Invalid server_name provided: {data['server_name']}, it must be less than 256 characters, ignoring it ...")
                        continue

                    error = DB.upsert_instance(
                        data["hostname"],
                        data["listening_port"],
                        data["server_name"],
                        "dynamic",
                    )

                    if error and error not in ("created", "updated"):
                        CORE_CONFIG.logger.error(f"listen_dynamic_instances - Couldn't save instance to database: {error}, ignoring it ...")
                        continue

                    CORE_CONFIG.logger.info(f"listen_dynamic_instances - ✅ Instance {data['hostname']}:{data['listening_port']}:{data['server_name']} successfully {error} to database")
                    if error != "updated":
                        instance_api = API(
                            f"http://{data['hostname']}:{data['listening_port']}",
                            data["server_name"],
                        )

                        if not test_and_send_to_instances("all", {instance_api}):
                            continue

                        CORE_CONFIG.logger.info(f"listen_dynamic_instances - Successfully sent data to instance {instance_api.endpoint}")
                    else:
                        CORE_CONFIG.logger.info(f"listen_dynamic_instances - Skipping sending data to instance {data['hostname']}:{data['listening_port']}:{data['server_name']} because it's already in database")
            except Exception:
                CORE_CONFIG.logger.exception(f"listen_dynamic_instances - Exception while parsing message: {pubsub_message}")
    finally:
        with suppress(ConnectionError):
            pubsub.unsubscribe("bw-instances")

    SEMAPHORE.release()


def run_pending_jobs() -> None:
    while not DB.is_scheduler_initialized():
        CORE_CONFIG.logger.warning(f"run_pending_jobs - Scheduler is not initialized yet, retrying in {CORE_CONFIG.WAIT_RETRY_INTERVAL} seconds ...")
        sleep(int(CORE_CONFIG.WAIT_RETRY_INTERVAL) - 1 if int(CORE_CONFIG.WAIT_RETRY_INTERVAL) > 0 else 0)

    SCHEDULER.run_pending()


def instances_healthcheck() -> None:
    if not DB:
        return

    instance_apis = {
        instance["hostname"]: API(
            f"http://{instance['hostname']}:{instance['port']}",
            instance["server_name"],
        )
        for instance in DB.get_instances()
    }

    if not instance_apis:
        CORE_CONFIG.logger.warning("instances_healthcheck - No instances found in database, skipping healthcheck ...")
        return

    for instance, instance_api in instance_apis.items():
        sent, err, status, resp = instance_api.request("GET", "ping")
        if not sent:
            CORE_CONFIG.logger.warning(f"instances_healthcheck - Can't send API request to {instance_api.endpoint}ping : {err}, healthcheck will be retried in 30 seconds ...")
            continue
        else:
            if status != 200:
                CORE_CONFIG.logger.warning(f"instances_healthcheck - Error while sending API request to {instance_api.endpoint}ping : status = {resp['status']}, msg = {resp['msg']}, healthcheck will be retried in 30 seconds ...")
                continue
            else:
                CORE_CONFIG.logger.info(f"instances_healthcheck - Successfully sent API request to {instance_api.endpoint}ping, marking instance as seen ...")

                Thread(target=seen_instance, args=(instance,)).start()


def run_repeatedly(delay: int, func, *, wait_first: bool = False, **kwargs):
    SEMAPHORE.acquire()

    while not stop_event.is_set():
        if not wait_first:
            func(**kwargs)
        sleep(delay)
        wait_first = False

    SEMAPHORE.release()


@app.middleware("http")
async def validate_request(request: Request, call_next):
    try:
        assert isinstance(request.client, Address)
    except AssertionError:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})

    if CORE_CONFIG.check_whitelist and request.client.host != "127.0.0.1":
        if not CORE_CONFIG.whitelist:
            CORE_CONFIG.logger.warning(f'Unauthorized access attempt from {request.client.host} (whitelist check is set to "yes" but the whitelist is empty), aborting...')
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})

        remote_ip = ip_address(request.client.host)
        for whitelist in CORE_CONFIG.whitelist:
            if isinstance(whitelist, (IPv4Network, IPv6Network)):
                if remote_ip in whitelist:
                    break
            elif isinstance(whitelist, (IPv4Address, IPv6Address)):
                if remote_ip == whitelist:
                    break
        else:
            CORE_CONFIG.logger.warning(f"Unauthorized access attempt from {remote_ip} (not in whitelist), aborting...")
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})

    if CORE_CONFIG.check_token:
        if request.headers.get("Authorization") != f"Bearer {CORE_CONFIG.CORE_TOKEN}":
            CORE_CONFIG.logger.warning(f"Unauthorized access attempt from {request.client.host} (invalid token), aborting...")
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"result": "ko"})

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

if config_files.get("USE_REDIS", "no") == "yes":
    if REDIS_HOST:
        redis_port = config_files.get("REDIS_PORT", "6379")
        if not redis_port.isdigit() or not (1 <= int(redis_port) <= 65535):
            CORE_CONFIG.logger.warning(f"Invalid REDIS_PORT provided: {redis_port}, It must be an integer between 1 and 65535, port will default to 6379")
            redis_port = 6379
        REDIS_PORT = int(redis_port)
        del redis_port

        redis_database = config_files.get("REDIS_DATABASE", "0")
        if not redis_database.isdigit() or not (0 <= int(redis_database) <= 15):
            CORE_CONFIG.logger.warning(f"Invalid REDIS_DATABASE provided: {redis_database}, It must be an integer between 0 and 15, database will default to 0")
            redis_database = 0
        REDIS_DATABASE = int(redis_database)
        del redis_database

        if config_files.get("REDIS_SSL", "no") == "yes":
            REDIS_SSL = True

        redis_timeout = config_files.get("REDIS_TIMEOUT", "1000")  # ms
        if not redis_timeout.isdigit() or int(redis_timeout) < 1:
            CORE_CONFIG.logger.warning(f"Invalid REDIS_TIMEOUT provided: {redis_timeout}, It must be a positive integer, timeout will default to 1000 ms")
            redis_timeout = 1000
        REDIS_TIMEOUT = float(int(redis_timeout) / 1000)
        del redis_timeout

        Thread(target=listen_dynamic_instances, name="redis_listener").start()
    else:
        CORE_CONFIG.logger.warning("USE_REDIS is set to yes but REDIS_HOST is not defined, app will not listen for dynamic instances")

Thread(
    target=run_repeatedly,
    args=(int(CORE_CONFIG.HEALTHCHECK_INTERVAL), instances_healthcheck),
    kwargs={"wait_first": True},
    name="instances_healthcheck",
).start()
Thread(target=run_repeatedly, args=(1, run_pending_jobs), name="run_pending_jobs").start()

if not HEALTHY_PATH.exists():
    HEALTHY_PATH.write_text("ok", encoding="utf-8")


if __name__ == "__main__":
    from uvicorn import run

    if not isinstance(CORE_CONFIG.LISTEN_PORT, int) and (not CORE_CONFIG.LISTEN_PORT.isdigit() or not (1 <= int(CORE_CONFIG.LISTEN_PORT) <= 65535)):
        CORE_CONFIG.logger.error(f"Invalid LISTEN_PORT provided: {CORE_CONFIG.LISTEN_PORT}, It must be an integer between 1 and 65535.")
        stop_app(1)

    run(
        app,
        host=CORE_CONFIG.LISTEN_ADDR,
        port=int(CORE_CONFIG.LISTEN_PORT),
        reload=True,
        proxy_headers=False,
        server_header=False,
        date_header=False,
    )
