from contextlib import suppress
from functools import partial
from glob import glob
from importlib.machinery import SourceFileLoader
from io import BytesIO
from json import loads
from logging import Logger
from os import _exit, chmod, environ
from os.path import basename, dirname, join, normpath, sep
from pathlib import Path
from shutil import copytree, rmtree
from signal import SIGINT, SIGTERM, signal
from socket import gaierror, herror
from stat import S_IEXEC
from tarfile import open as tar_open
from threading import Semaphore
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4
from zipfile import ZipFile
from fastapi.routing import Mount

from kombu import Connection, Queue
from magic import Magic
from requests import get

from .core import ApiConfig
from logger import setup_logger  # type: ignore
from database import Database  # type: ignore


def dict_to_frozenset(d):
    if isinstance(d, list):
        return tuple(sorted(d))
    elif isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def install_plugin(
    plugin_url: str, logger: Logger, *, semaphore: Optional[Semaphore] = None
):
    if semaphore:
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
        logger.error(
            f"Exception while downloading plugin(s) from {plugin_url} :\n{format_exc()}",
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
        logger.error(
            f"Exception while decompressing plugin(s) from {plugin_url} :\n{format_exc()}",
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
        logger.error(
            f"Exception while installing plugin(s) from {plugin_url} :\n{format_exc()}",
        )

    if semaphore:
        semaphore.release()


def generate_external_plugins(
    logger: Logger,
    plugins: List[Dict[str, Any]] = None,
    db=None,
    *,
    original_path: Union[Path, str] = join(sep, "etc", "bunkerweb", "plugins"),
):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old external plugins files
    logger.info("Removing old external plugins files ...")
    for file in glob(str(original_path.joinpath("*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(str(file), ignore_errors=True)

    if not plugins and db:
        plugins = db.get_plugins(external=True, with_data=True)

    if plugins:
        logger.info("Generating new external plugins ...")
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


KOMBU_CONNECTION = None
DB = None
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "core.healthy")
CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")


def stop(status):
    global DB
    HEALTHY_PATH.unlink(missing_ok=True)
    if DB:
        del DB
    if KOMBU_CONNECTION:
        KOMBU_CONNECTION.release()
    _exit(status)


signal(SIGINT, partial(stop, 0))
signal(SIGTERM, partial(stop, 0))

API_CONFIG = ApiConfig("core", **environ)
LOGGER = setup_logger("CORE", API_CONFIG.log_level)
DB = Database(LOGGER, API_CONFIG.DATABASE_URI)

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


def update_app_mounts(app):
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
        # try:
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
        # except Exception as e:
        #     LOGGER.error(f"Exception while mounting subapi {subapi_plugin} : {e}")
