from functools import partial, wraps
from glob import glob
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import loads
from logging import Logger
from os import _exit, chmod, cpu_count, environ
from os.path import basename, dirname, join, normpath, sep
from pathlib import Path
from shutil import copytree, rmtree
from signal import SIGINT, SIGTERM, signal
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from tarfile import open as tar_open
from threading import Thread, enumerate as all_threads, Event, Semaphore
from time import sleep
from typing import Any, Callable, Dict, List, Literal, Optional, Union
from uuid import uuid4
from zipfile import ZipFile

from fastapi.routing import Mount
from magic import Magic
from requests import get


from .core import CoreConfig
from .job_scheduler import JobScheduler

from API import API  # type: ignore
from api_caller import ApiCaller  # type: ignore
from database import Database  # type: ignore

DB = None
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "core.healthy")
SEMAPHORE = Semaphore(cpu_count() or 1)

# Create thread events
stop_event = Event()
scheduler_initialized = Event()
api_started = Event()


def stop(status):
    global DB

    stop_event.set()
    for thread in all_threads():
        if thread.name != "MainThread":
            thread.join()

    HEALTHY_PATH.unlink(missing_ok=True)
    if DB:
        del DB
    _exit(status)


signal(SIGINT, partial(stop, 0))  # type: ignore
signal(SIGTERM, partial(stop, 0))  # type: ignore

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core_plugins")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
SETTINGS_PATH = Path(sep, "usr", "share", "bunkerweb", "settings.json")
CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
CACHE_PATH = join(sep, "var", "cache", "bunkerweb")
TMP_ENV_PATH = Path(sep, "var", "tmp", "bunkerweb", "core.env")
TMP_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)

integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
os_release_path = Path(sep, "etc", "os-release")
if (
    integration_path.is_file()
    and integration_path.read_text(encoding="utf-8").strip().lower()
    in ("autoconf", "kubernetes", "swarm")
) or (
    os_release_path.is_file()
    and "Alpine" in os_release_path.read_text(encoding="utf-8")
):
    CORE_CONFIG = CoreConfig("core", **environ)
else:
    CORE_CONFIG = CoreConfig("core")

del integration_path, os_release_path

INSTANCES_API_CALLER = ApiCaller()

if not isinstance(CORE_CONFIG.WAIT_RETRY_INTERVAL, int) and (
    not CORE_CONFIG.WAIT_RETRY_INTERVAL.isdigit()
    or int(CORE_CONFIG.WAIT_RETRY_INTERVAL) < 1
):
    CORE_CONFIG.logger.error(
        f"Invalid WAIT_RETRY_INTERVAL provided: {CORE_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer."
    )
    stop(1)

if not isinstance(CORE_CONFIG.HEALTHCHECK_INTERVAL, int) and (
    not CORE_CONFIG.HEALTHCHECK_INTERVAL.isdigit()
    or int(CORE_CONFIG.HEALTHCHECK_INTERVAL) < 1
):
    CORE_CONFIG.logger.error(
        f"Invalid HEALTHCHECK_INTERVAL provided: {CORE_CONFIG.HEALTHCHECK_INTERVAL}, It must be a positive integer."
    )
    stop(1)

DB = Database(CORE_CONFIG.logger, CORE_CONFIG.DATABASE_URI, pool=False)

CORE_CONFIG.logger.info(f"🚀 {CORE_CONFIG.integration} integration detected")

# Instantiate scheduler
SCHEDULER = JobScheduler(
    API(f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "bw-scheduler"),
    env=CORE_CONFIG.settings
    | {
        "API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}",
        "API_TOKEN": CORE_CONFIG.TOKEN,
    },
    logger=CORE_CONFIG.logger,
)


def dict_to_frozenset(d):
    if isinstance(d, list):
        return tuple(sorted(d))
    elif isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def update_app_mounts(app):
    CORE_CONFIG.logger.info("Updating app mounts ...")

    for route in app.routes:
        if isinstance(route, Mount):
            # remove the subapp from the routes
            app.routes.remove(route)

    for subinstance_api in glob(
        str(CORE_PLUGINS_PATH.joinpath("*", "instance_api"))
    ) + glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "instance_api"))):
        main_file_path = Path(subinstance_api, "main.py")

        if not main_file_path.is_file():
            continue

        subinstance_api_plugin = basename(dirname(subinstance_api))
        CORE_CONFIG.logger.info(
            f"Mounting subinstance_api {subinstance_api_plugin} ..."
        )
        try:
            loader = SourceFileLoader(
                f"{subinstance_api_plugin}_instance_api", str(main_file_path)
            )
            subinstance_api_module = loader.load_module()
            root_path = getattr(
                subinstance_api_module, "root_path", f"/{subinstance_api_plugin}"
            )

            if hasattr(subinstance_api_module, "app"):
                app.mount(
                    root_path,
                    getattr(subinstance_api_module, "app"),
                    basename(dirname(subinstance_api)),
                )

                CORE_CONFIG.logger.info(
                    f"✅ The subinstance_api for the plugin {subinstance_api_plugin} has been mounted successfully, root path: {root_path}"
                )
            else:
                CORE_CONFIG.logger.error(
                    f"Couldn't mount subinstance_api {subinstance_api_plugin}, no app found"
                )
        except Exception as e:
            CORE_CONFIG.logger.error(
                f"Exception while mounting subinstance_api {subinstance_api_plugin} : {e}"
            )


def install_plugin(
    plugin_url: str, logger: Logger, *, semaphore: Semaphore = SEMAPHORE
):
    semaphore.acquire(timeout=30)

    # Download Plugin file
    try:
        if plugin_url.startswith("file://"):
            content = Path(normpath(plugin_url[7:])).read_bytes()
        else:
            content = b""
            resp = get(plugin_url, stream=True, timeout=10)  # type: ignore

            if resp.status_code != 200:
                logger.warning(f"Got status code {resp.status_code}, skipping...")
                return

            # Iterate over the response content in chunks
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
    except:
        logger.exception(
            f"Exception while downloading plugin(s) from {plugin_url}",
        )
        return

    # Extract it to tmp folder
    temp_dir = join(sep, "var", "tmp", "bunkerweb", "plugins", str(uuid4()))
    try:
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
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
            logger.error(
                f"Unknown file type for {plugin_url}, either zip or tar are supported, skipping..."
            )
            return
    except:
        logger.exception(
            f"Exception while decompressing plugin(s) from {plugin_url}",
        )
        return

    # Install plugins
    try:
        for plugin_dir in glob(join(temp_dir, "**", "plugin.json"), recursive=True):
            try:
                plugin_dir = dirname(plugin_dir)
                # Load plugin.json
                metadata = loads(
                    Path(plugin_dir, "plugin.json").read_text(encoding="utf-8")
                )
                # Don't go further if plugin is already installed
                if Path(
                    "etc", "bunkerweb", "plugins", metadata["id"], "plugin.json"
                ).is_file():
                    logger.warning(
                        f"Skipping installation of plugin {metadata['id']} (already installed)",
                    )
                    return
                # Copy the plugin
                copytree(
                    plugin_dir, join(sep, "etc", "bunkerweb", "plugins", metadata["id"])
                )
                # Add u+x permissions to jobs files
                for job_file in glob(join(plugin_dir, "jobs", "*")):
                    st = Path(job_file).stat()
                    chmod(job_file, st.st_mode | S_IEXEC)
                logger.info(f"Plugin {metadata['id']} installed")
            except FileExistsError:
                logger.warning(
                    f"Skipping installation of plugin {basename(dirname(plugin_dir))} (already installed)",
                )
    except:
        logger.exception(
            f"Exception while installing plugin(s) from {plugin_url}",
        )

    semaphore.release()


def generate_external_plugins(
    plugins: Optional[List[Dict[str, Any]]] = None,
    *,
    original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH,
):
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
            tmp_path = original_path.joinpath(plugin["id"], f"{plugin['name']}.tar.gz")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(plugin["data"])
            with tar_open(str(tmp_path), "r:gz") as tar:
                tar.extractall(original_path)
            tmp_path.unlink()

            for job_file in glob(join(str(tmp_path.parent), "jobs", "*")):
                st = Path(job_file).stat()
                chmod(job_file, st.st_mode | S_IEXEC)


def generate_custom_configs(
    configs: Optional[List[Dict[str, Any]]] = None,
    *,
    original_path: Union[Path, str] = CUSTOM_CONFIGS_PATH,
):
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
            tmp_path = original_path.joinpath(
                custom_config["type"].replace("_", "-"),
                custom_config["service_id"] or "",
                f"{custom_config['name']}.conf",
            )
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(custom_config["data"])


def generate_config(function: Optional[Callable] = None):
    @wraps(function)  # type: ignore (if function is None, no error is raised)
    def wrap(*args, **kwargs):
        assert DB

        nginx_prefix = join(sep, "etc", "nginx")
        content = ""
        for k, v in DB.get_config().items():
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
                nginx_prefix,
                "--variables",
                str(TMP_ENV_PATH),
            ],
            stdin=DEVNULL,
            stderr=STDOUT,
            check=False,
        )

        if proc.returncode != 0:
            CORE_CONFIG.logger.error(
                "Config generator failed, configuration will not work as expected..."
            )

        if function:
            return function(*args, **kwargs)

    if function:
        return wrap
    wrap()


def send_plugins_to_instances(api_caller: ApiCaller = None):
    if not api_caller:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    generate_external_plugins(original_path=EXTERNAL_PLUGINS_PATH)
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(
        f"Sending {EXTERNAL_PLUGINS_PATH} folder to instances {instances_endpoints} ..."
    )
    ret = api_caller.send_files(EXTERNAL_PLUGINS_PATH, "/plugins")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have received the plugins, configuration will not work as expected...",
        )


@generate_config
def send_config_to_instances(api_caller: ApiCaller = None):
    if not api_caller:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    nginx_prefix = Path(sep, "etc", "nginx")
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    if not nginx_prefix.is_dir():
        CORE_CONFIG.logger.error(
            f"{nginx_prefix} is not a directory, configuration will not be sent to instances {instances_endpoints}"
        )
        return 1

    CORE_CONFIG.logger.info(
        f"Sending {nginx_prefix} folder to instances {instances_endpoints} ..."
    )
    ret = api_caller.send_files(nginx_prefix, "/confs")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have received the configuration, configuration will not work as expected...",
        )


def send_custom_configs_to_instances(api_caller: ApiCaller = None):
    if not api_caller:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    generate_custom_configs(original_path=CUSTOM_CONFIGS_PATH)
    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(
        f"Sending {CUSTOM_CONFIGS_PATH} folder to instances {instances_endpoints} ..."
    )
    ret = api_caller.send_files(CUSTOM_CONFIGS_PATH, "/custom_configs")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have received the custom configs, configuration will not work as expected...",
        )


def send_cache_to_instances(api_caller: ApiCaller = None):
    if not api_caller:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    instances_endpoints = ", ".join(api.endpoint for api in api_caller.apis)

    CORE_CONFIG.logger.info(
        f"Sending {CACHE_PATH} folder to instances {instances_endpoints} ..."
    )
    ret = api_caller.send_files(CACHE_PATH, "/cache")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have received the cache, configuration will not work as expected...",
        )


def reload_instances(api_caller: ApiCaller = None):
    if not api_caller:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    CORE_CONFIG.logger.info(
        f"Reloading instances {', '.join(api.endpoint for api in api_caller.apis)} ..."
    )
    ret = api_caller.send_to_apis("POST", "/reload")
    if not ret:
        CORE_CONFIG.logger.error(
            "Not all instances have been reloaded, configuration will not work as expected...",
        )


def send_to_instances(
    types: Union[
        Literal["all"],
        set[Literal["plugins", "custom_configs", "config", "cache", "reload"]],
    ],
    *,
    instance_api: Optional[API] = None,
    caller: Optional[ApiCaller] = None,
    no_reload: bool = False,
) -> int:
    api_caller = caller or (ApiCaller([instance_api]) if instance_api else None)

    if api_caller is None:
        assert DB
        api_caller = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    if types != "all" and not types:
        CORE_CONFIG.logger.error("No type provided, nothing to do...")
        return 1

    if types == "all" or "plugins" in types:
        send_plugins_to_instances(api_caller) or None  # type: ignore
    if types == "all" or "custom_configs" in types:
        send_custom_configs_to_instances(api_caller) or None  # type: ignore
    if types == "all" or "config" in types:
        send_config_to_instances(api_caller) or None  # type: ignore
    if types == "all" or "cache" in types:
        send_cache_to_instances(api_caller) or None  # type: ignore
    if not no_reload and (types == "all" or types):
        reload_instances(api_caller) or None  # type: ignore
    return 0


def seen_instance(instance_hostname: str):
    SEMAPHORE.acquire(timeout=30)

    error = DB.seen_instance(instance_hostname)
    if error:
        CORE_CONFIG.logger.error(
            f"Couldn't update instance {instance_hostname} last_seen to database: {error}"
        )
        return False

    SEMAPHORE.release()

    return True


def test_and_send_to_instances(
    types: Union[
        Literal["all"],
        set[Literal["plugins", "custom_configs", "config", "cache", "reload"]],
    ],
    instance_apis: Union[set[API], ApiCaller] = None,
    *,
    no_reload: bool = False,
) -> int:
    if instance_apis is None:
        assert DB
        instance_apis = ApiCaller(
            [
                API(
                    f"http://{instance['hostname']}:{instance['port']}",
                    instance["server_name"],
                )
                for instance in DB.get_instances()
            ]
        )

    for instance_api in (
        instance_apis.copy() if isinstance(instance_apis, set) else instance_apis.apis
    ):
        sent, err, status, resp = instance_api.request("GET", "ping")
        if not sent:
            CORE_CONFIG.logger.warning(
                f"Can't send API request to {instance_api.endpoint}ping : {err}, data will not be sent to it ...",
            )
            instance_apis.remove(instance_api)
            continue
        else:
            if status != 200:
                CORE_CONFIG.logger.warning(
                    f"Error while sending API request to {instance_api.endpoint}ping : status = {resp['status']}, msg = {resp['msg']}, data will not be sent to it ...",
                )
                instance_apis.remove(instance_api)
                continue
            else:
                CORE_CONFIG.logger.info(
                    f"Successfully sent API request to {instance_api.endpoint}ping, sending data to it ..."
                )

        Thread(
            target=seen_instance,
            args=(instance_api.endpoint.replace("http://", "").split(":")[0],),
        ).start()

    if instance_apis if isinstance(instance_apis, set) else instance_apis.apis:
        api_caller = (
            instance_apis
            if isinstance(instance_apis, ApiCaller)
            else ApiCaller(instance_apis)
        )

        return send_to_instances(types, caller=api_caller, no_reload=no_reload)
    return 0


def run_jobs():
    if not api_started.is_set():
        local_api = API(f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}", "bw-scheduler")
        sent = False
        status = 0

        while not sent or status != 200:
            sent, err, status, resp = local_api.request(
                "GET",
                "/ping",
                additonal_headers={"Authorization": f"Bearer {CORE_CONFIG.TOKEN}"}
                if CORE_CONFIG.TOKEN
                else {},
            )
            sleep(1)

    assert DB
    SCHEDULER.reload(
        DB.get_config()
        | {
            "API_ADDR": f"http://127.0.0.1:{CORE_CONFIG.LISTEN_PORT}",
            "API_TOKEN": CORE_CONFIG.TOKEN,
        }
    )

    # Only run jobs once
    if not SCHEDULER.run_once():
        CORE_CONFIG.logger.error("At least one job in run_once() failed")
    else:
        CORE_CONFIG.logger.info("All jobs in run_once() were successful")

    if test_and_send_to_instances({"cache"}) != 0:
        CORE_CONFIG.logger.warning(
            "Can't send data to BunkerWeb instances, configuration will not work as expected"
        )

    api_started.set()


def run_job(job_name: str):
    SCHEDULER.run_single(job_name)

    # TODO: remove this when the soft reload will be available
    if test_and_send_to_instances({"cache"}) != 0:
        CORE_CONFIG.logger.warning(
            "Can't send data to BunkerWeb instances, configuration will not work as expected"
        )
