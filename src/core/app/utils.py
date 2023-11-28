#!/usr/bin/python3
# -*- coding: utf-8 -*-

from contextlib import suppress
from copy import deepcopy
from glob import glob
from io import BytesIO
from itertools import chain
from json import JSONDecodeError, loads as json_loads
from shutil import rmtree
from threading import Thread
from os import listdir, sep, walk
from os.path import basename, dirname, join
from pathlib import Path
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from typing import List


for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("gen",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from redis import Redis

from API import API  # type: ignore
from configurator import Configurator  # type: ignore
from jobs import bytes_hash  # type: ignore
from .core import BUNKERWEB_VERSION
from .dependencies import (
    CORE_CONFIG,
    CORE_PLUGINS_PATH,
    CUSTOM_CONFIGS_PATH,
    CUSTOM_CONFIGS_RX,
    DB,
    EXTERNAL_PLUGINS_PATH,
    SETTINGS_PATH,
    is_not_reloading,
    listen_for_dynamic_instances,
    PLUGIN_ID_REGEX,
    PLUGIN_KEYS,
    SEMAPHORE,
    run_jobs,
    stop,
    stop_event,
    generate_external_plugins,
    install_plugin,
    test_and_send_to_instances,
)


def dict_to_frozenset(d):
    """Converts a dict to a frozenset recursively."""
    if isinstance(d, list):
        return tuple(sorted(d))
    elif isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def extract_plugin_data(filename: str, dir_basename: str, _dir: str) -> dict:
    plugin_data = json_loads(Path(filename).read_text(encoding="utf-8"))

    if not all(key in plugin_data.keys() for key in PLUGIN_KEYS):
        CORE_CONFIG.logger.warning(f"The plugin {dir_basename} doesn't have a valid plugin.json file, it's missing one or more of the following keys: {', '.join(PLUGIN_KEYS)}, ignoring it...")
        return {}
    elif not PLUGIN_ID_REGEX.match(plugin_data["id"]):
        CORE_CONFIG.logger.warning(f"The plugin {dir_basename} doesn't have a valid id, the id must match the following regex: {PLUGIN_ID_REGEX.pattern}, ignoring it...")
        return {}

    plugin_content = BytesIO()
    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
        tar.add(_dir, arcname=dir_basename, recursive=True)
    plugin_content.seek(0, 0)
    checksum = bytes_hash(plugin_content)
    plugin_content.seek(0, 0)

    plugin_data.update({"external": True, "page": Path(_dir, "ui").exists(), "data": plugin_content.getvalue(), "checksum": checksum})

    return plugin_data


def update_external_plugins(db_plugins: List[dict], db_config: dict, db_initialized: bool = False) -> List[dict]:
    plugin_changes = False
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

        plugin_data = extract_plugin_data(filename, dir_basename, _dir)

        if not plugin_data:
            continue

        plugin_data["method"] = "static"

        manual_plugins_ids.append(plugin_data["id"])
        manual_plugins.append(plugin_data)

    if CORE_CONFIG.external_plugin_urls_str != db_config.get("EXTERNAL_PLUGIN_URLS", ""):
        if db_initialized:
            CORE_CONFIG.logger.info("External plugins urls changed, refreshing external plugins...")
            for db_plugin in glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*"))):
                rmtree(db_plugin, ignore_errors=True)
        else:
            CORE_CONFIG.logger.info("Found external plugins to download, starting download...")

        plugin_changes = True
        threads = []
        for plugin_url in CORE_CONFIG.external_plugin_urls:
            threads.append(Thread(target=install_plugin, args=(plugin_url, CORE_CONFIG.logger)))
            threads[-1].start()

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

        plugin_data = extract_plugin_data(filename, dir_basename, _dir)

        if not plugin_data:
            continue

        plugin_data["method"] = "core"

        external_plugins.append(plugin_data)

    external_plugins = list(chain(manual_plugins, external_plugins))
    if db_initialized:
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

            err = DB.update_external_plugins(deepcopy(external_plugins), delete_missing=True)
            if err:
                CORE_CONFIG.logger.error(f"Couldn't save some manually added plugins to database: {err}")

            generate_external_plugins(external_plugins, original_path=EXTERNAL_PLUGINS_PATH)

    return external_plugins


def update_custom_configs(db_config: dict):
    db_configs = DB.get_custom_configs()
    env_custom_configs = []
    for k, v in CORE_CONFIG.settings.copy().items():
        match = CUSTOM_CONFIGS_RX.search(k)
        if match:
            name = match.group("name").replace(".conf", "")
            service = match.group("service_id")
            CORE_CONFIG.logger.info(f"🛠️ Found custom conf env var \"{name}\"{' for service ' + service if service else ''} with type {match.group('type')}")
            if db_config.get("MULTISITE", "no") == "no" and service:
                CORE_CONFIG.logger.warning(f'🛠️ Because MULTISITE is set to "no", the service id will be ignored for custom conf env var "{name}" with type {match.group("type")}, the custom config will then be applied globally')
                service = None
            env_custom_configs.append({"value": v, "exploded": (service, match.group("type"), name)})

    if {hash(dict_to_frozenset(d)) for d in env_custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs if d["method"] == "env"}:
        err = DB.save_custom_configs(env_custom_configs, "env")
        if err:
            for e in err:
                if e.startswith("Couldn't"):
                    CORE_CONFIG.logger.warning(e)
                else:
                    CORE_CONFIG.logger.error(f"Couldn't save some custom configs from env to database: {err}")
        else:
            CORE_CONFIG.logger.info("✅ Custom configs from env saved to database")

    files_custom_configs = []
    max_num_sep = str(CUSTOM_CONFIGS_PATH).count(sep) + (3 if db_config.get("MULTISITE", "no") == "yes" else 2)
    root_dirs = listdir(CUSTOM_CONFIGS_PATH)
    for root, dirs, files in walk(CUSTOM_CONFIGS_PATH):
        if root.count(sep) <= max_num_sep and (files or (dirs and basename(root) not in root_dirs)):
            path_exploded = root.split("/")
            for file in files:
                content = Path(join(root, file)).read_text(encoding="utf-8")
                custom_conf = {"value": content, "exploded": (f"{path_exploded.pop()}" if path_exploded[-1] not in root_dirs else None, path_exploded[-1], file.replace(".conf", ""))}
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
            for e in err:
                if e.startswith("Couldn't"):
                    CORE_CONFIG.logger.warning(e)
                else:
                    CORE_CONFIG.logger.error(f"Couldn't save some manually created custom configs to database: {err}")
        else:
            CORE_CONFIG.logger.info("✅ Custom configs from files saved to database")


def startup():
    is_not_reloading.clear()

    CORE_CONFIG.logger.info("Checking if database is initialized ...")

    db_initialized = DB.is_initialized()

    db_config = {}
    db_plugins = []
    if db_initialized:
        resp = DB.set_scheduler_initialized(False)

        if resp:
            CORE_CONFIG.logger.warning(f"Can't set scheduler as not initialized : {resp}")

        db_config = "retry"
        retries = 0
        while db_config == "retry":
            db_config = DB.get_config()

            if db_config == "retry":
                if retries >= 5:
                    CORE_CONFIG.logger.error("Can't get config from database after 5 retries, aborting ...")
                    stop(1)
                CORE_CONFIG.logger.warning("Can't get config from database, retrying in 5 seconds ...")
                sleep(5)
                continue
            elif isinstance(db_config, str):
                CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}, retry later")
                stop(1)

        assert isinstance(db_config, dict)

        db_plugins = DB.get_plugins(external=True)

        if isinstance(db_plugins, str):
            CORE_CONFIG.logger.warning(f"Can't get plugins from database : {db_plugins}")
            db_plugins = []

    CORE_CONFIG.logger.info("Checking if any external plugin have been added or removed...")

    external_plugins = update_external_plugins(db_plugins, db_config, db_initialized)

    CORE_CONFIG.logger.info("Computing config ...")

    config = Configurator(str(SETTINGS_PATH), str(CORE_PLUGINS_PATH), external_plugins, CORE_CONFIG.settings, CORE_CONFIG.logger)
    config_files = config.get_config()

    if not db_initialized:
        CORE_CONFIG.logger.info("Database not initialized, initializing ...")
        ret, err = DB.init_tables([config.settings, config.get_plugins("core"), external_plugins])

        # Initialize database tables
        if err:
            CORE_CONFIG.logger.error(f"Exception while initializing database : {err}")
            stop(1)
        elif not ret:
            CORE_CONFIG.logger.info("Database tables are already initialized, skipping creation ...")
        else:
            CORE_CONFIG.logger.info("Database tables initialized")

        err = DB.initialize_db(version=BUNKERWEB_VERSION, integration=CORE_CONFIG.integration)

        if err:
            CORE_CONFIG.logger.error(f"Can't Initialize database : {err}")
            stop(1)
        CORE_CONFIG.logger.info("✅ Database initialized")
    else:
        ret, resp = DB.update_db_schema(BUNKERWEB_VERSION)

        if ret:
            CORE_CONFIG.logger.error(f"Can't update database schema : {resp}")
            stop(1)
        elif not resp:
            CORE_CONFIG.logger.info("✅ Database schema updated to latest version successfully")
        else:
            CORE_CONFIG.logger.info(resp)

    if config_files != db_config:
        err = DB.save_config(config_files, "core")

        if err:
            CORE_CONFIG.logger.error(f"Can't save config to database : {err}")
            stop(1)

        db_config = "retry"
        retries = 0
        while db_config == "retry":
            db_config = DB.get_config()

            if db_config == "retry":
                if retries >= 5:
                    CORE_CONFIG.logger.error("Can't get config from database after 5 retries, aborting ...")
                    stop(1)
                CORE_CONFIG.logger.warning("Can't get config from database, retrying in 5 seconds ...")
                sleep(5)
                continue
            elif isinstance(db_config, str):
                CORE_CONFIG.logger.error(f"Can't get config from database : {db_config}, retry later")
                stop(1)

        assert isinstance(db_config, dict)

        CORE_CONFIG.logger.info("✅ Config successfully saved to database")

    CORE_CONFIG.logger.info("Checking if any custom config have been added or removed...")

    update_custom_configs(db_config)

    if not db_initialized:
        err = DB.refresh_instances([], "dynamic")

        if err:
            CORE_CONFIG.logger.error(f"Can't clear dynamic BunkerWeb instances to database : {err}")
            stop(1)
        CORE_CONFIG.logger.info("✅ BunkerWeb dynamic instances cleared from database")

    err = DB.refresh_instances(CORE_CONFIG.bunkerweb_instances, "static")

    if err:
        CORE_CONFIG.logger.error(f"Can't refresh static BunkerWeb instances to database : {err}")
        stop(1)
    CORE_CONFIG.logger.info("✅ BunkerWeb static instances updated to database")

    if CORE_CONFIG.integration in ("Linux", "Docker"):
        CORE_CONFIG.logger.info("Executing scheduler ...")
        DB.set_scheduler_initialized()
        for thread in (Thread(target=test_and_send_to_instances, args=(None, {"plugins", "custom_configs"}), kwargs={"no_reload": True}), Thread(target=run_jobs)):
            thread.start()

    is_not_reloading.set()


def listen_dynamic_instances():
    SEMAPHORE.acquire()

    if not CORE_CONFIG.REDIS_HOST:
        CORE_CONFIG.logger.warning("listen_dynamic_instances - USE_REDIS is set to yes but REDIS_HOST is not defined, app will not listen for dynamic instances")
        SEMAPHORE.release()
        return

    redis_client = Redis(host=CORE_CONFIG.REDIS_HOST, port=int(CORE_CONFIG.REDIS_PORT), db=int(CORE_CONFIG.REDIS_DATABASE), ssl=CORE_CONFIG.redis_ssl, socket_timeout=float(CORE_CONFIG.REDIS_TIMEOUT) / 1000)

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
            sleep(float(CORE_CONFIG.WAIT_RETRY_INTERVAL))

    CORE_CONFIG.logger.info("listen_dynamic_instances - ✅ Connected to Redis")

    pubsub = redis_client.pubsub()

    CORE_CONFIG.logger.info('listen_dynamic_instances - Subscribing to Redis channel "bw-instances" ...')

    while not stop_event.is_set():
        try:
            pubsub.subscribe("bw-instances")
            break
        except ConnectionError:
            CORE_CONFIG.logger.warning(f"listen_dynamic_instances - Can't subscribe to Redis channel, retrying in {CORE_CONFIG.WAIT_RETRY_INTERVAL} seconds ...")
            sleep(float(CORE_CONFIG.WAIT_RETRY_INTERVAL))

    CORE_CONFIG.logger.info('listen_dynamic_instances - ✅ Subscribed to Redis channel "bw-instances", starting to listen for dynamic instances ...')

    try:
        while not stop_event.is_set() and listen_for_dynamic_instances.is_set():
            pubsub_message = None
            try:
                pubsub_message = pubsub.get_message(timeout=15)
            except (ConnectionError, TimeoutError):
                while not stop_event.is_set():
                    with suppress(ConnectionError):
                        pubsub.close()
                        pubsub.subscribe("bw-instances")
                        break
                    sleep(float(CORE_CONFIG.WAIT_RETRY_INTERVAL))

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
                        instance_api = API(f"http://{data['hostname']}:{data['listening_port']}", data["server_name"])

                        if not test_and_send_to_instances({instance_api}, "all"):
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


def run_repeatedly(delay: int, func, *, wait_first: bool = False, **kwargs):
    SEMAPHORE.acquire()

    while not stop_event.is_set():
        if not wait_first:
            func(**kwargs)
        sleep(delay)
        wait_first = False

    SEMAPHORE.release()
