#!/usr/bin/python3

from argparse import ArgumentParser
from contextlib import contextmanager, suppress
from glob import glob
from hashlib import sha256
from io import BytesIO
from json import loads
from shutil import copytree, rmtree
from stat import S_IEXEC
from subprocess import DEVNULL, run as subprocess_run, STDOUT
from threading import Semaphore, Thread
from uuid import uuid4
from zipfile import ZipFile
from dotenv import dotenv_values
from functools import partial
from os import _exit, chmod, cpu_count, getenv, listdir, sep
from os.path import basename, dirname, join, normpath
from pathlib import Path
from re import compile as re_compile
from signal import SIGINT, SIGTERM, signal
from sys import path as sys_path
from tarfile import open as tar_open
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Optional
from magic import Magic


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("db",), ("gen",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

del deps_path, sys_path

from Configurator import Configurator  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import file_hash  # type: ignore

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pymysql import install_as_MySQLdb
from requests import get
from uvicorn.workers import UvicornWorker

install_as_MySQLdb()

del install_as_MySQLdb


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "api.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "api.healthy").unlink(missing_ok=True)
    _exit(status)


signal(SIGINT, partial(stop, 0))
signal(SIGTERM, partial(stop, 0))

INTEGRATION = "Linux"
SETTINGS_PATH = Path(sep, "usr", "share", "bunkerweb", "settings.json")
CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
BUNKERWEB_VERSION = (
    Path(sep, "usr", "share", "bunkerweb", "VERSION")
    .read_text(encoding="utf-8")
    .strip()
)

GLOBAL_ENV = dotenv_values(join(sep, "etc", "bunkerweb", "api.conf"))
LOGGER = setup_logger("API", getenv("LOG_LEVEL", GLOBAL_ENV.get("LOG_LEVEL", "INFO")))
USE_WHITELIST = (
    getenv("API_CHECK_WHITELIST", GLOBAL_ENV.get("API_CHECK_WHITELIST", "no")).lower()
    == "yes"
)
API_WHITELIST = getenv("API_WHITELIST", GLOBAL_ENV.get("API_WHITELIST", ""))
CHECK_TOKEN = (
    getenv("API_CHECK_TOKEN", GLOBAL_ENV.get("API_CHECK_TOKEN", "no")).lower() == "yes"
)
API_TOKEN = getenv("API_TOKEN", GLOBAL_ENV.get("API_TOKEN", None))

integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
os_release_path = Path(sep, "etc", "os-release")
if getenv("KUBERNETES_MODE", GLOBAL_ENV.get("KUBERNETES_MODE", "no")).lower() == "yes":
    INTEGRATION = "Kubernetes"
elif getenv("SWARM_MODE", GLOBAL_ENV.get("SWARM_MODE", "no")).lower() == "yes":
    INTEGRATION = "Swarm"
elif getenv("AUTOCONF_MODE", GLOBAL_ENV.get("AUTOCONF_MODE", "no")).lower() == "yes":
    INTEGRATION = "Autoconf"
elif integration_path.is_file():
    INTEGRATION = integration_path.read_text(encoding="utf-8").strip()
elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(
    encoding="utf-8"
):
    INTEGRATION = "Docker"

del integration_path, os_release_path

TMP_ENV_PATH = Path(
    sep,
    "etc",
    "bunkerweb",
    "variables.env" if INTEGRATION == "Linux" else sep,
    "var",
    "tmp",
    "bunkerweb",
    "variables.env",
)
TMP_ENV = dotenv_values(str(TMP_ENV_PATH))

DB = Database(
    LOGGER,
    getenv(
        "DATABASE_URI",
        GLOBAL_ENV.get("DATABASE_URI", "sqlite:////var/lib/bunkerweb/db.sqlite3"),
    ),
)
EXTERNAL_PLUGIN_URLS = getenv(
    "EXTERNAL_PLUGIN_URLS", GLOBAL_ENV.get("EXTERNAL_PLUGIN_URLS", "")
)
EXTERNAL_PLUGIN_URLS_RX = re_compile(
    r"^( *((https?://|file:///)[-\w@:%.+~#=]+[-\w()!@:%+.~?&/=$#]*)(?!.*\2(?!.)) *)*$"
)
SEMAPHORE = Semaphore(cpu_count() or 1)


app = FastAPI()


class BwUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        "loop": "auto",
        "http": "auto",
        "proxy_headers": False,
        "server_header": False,
        "date_header": False,
    }


def install_plugin(plugin_url: str):
    SEMAPHORE.acquire(timeout=30)

    # Download Plugin file
    try:
        if plugin_url.startswith("file://"):
            content = Path(normpath(plugin_url[7:])).read_bytes()
        else:
            content = b""
            resp = get(plugin_url, stream=True, timeout=10)

            if resp.status_code != 200:
                LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                return

            # Iterate over the response content in chunks
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
    except:
        LOGGER.error(
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
            LOGGER.error(
                f"Unknown file type for {plugin_url}, either zip or tar are supported, skipping..."
            )
            return
    except:
        LOGGER.error(
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
                    LOGGER.warning(
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
                LOGGER.info(f"Plugin {metadata['id']} installed")
            except FileExistsError:
                LOGGER.warning(
                    f"Skipping installation of plugin {basename(dirname(plugin_dir))} (already installed)",
                )
    except:
        LOGGER.error(
            f"Exception while installing plugin(s) from {plugin_url} :\n{format_exc()}",
        )

    SEMAPHORE.release()


@app.on_event("startup")
async def startup_event():
    if not EXTERNAL_PLUGIN_URLS_RX.match(EXTERNAL_PLUGIN_URLS):
        LOGGER.error(
            f"Invalid external plugin URLs provided: {EXTERNAL_PLUGIN_URLS}, plugin download will be skipped"
        )
    elif EXTERNAL_PLUGIN_URLS or listdir(str(EXTERNAL_PLUGINS_PATH)):
        if EXTERNAL_PLUGIN_URLS.strip():
            LOGGER.info("Found external plugins to download, starting download...")

            threads = []
            for plugin_url in EXTERNAL_PLUGIN_URLS.strip().split(" "):
                thread = Thread(target=install_plugin, args=(plugin_url,))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            LOGGER.info("External plugins download finished")

        if DB.is_initialized():
            external_plugins = []
            external_plugins_ids = []
            for plugin in listdir(str(EXTERNAL_PLUGINS_PATH)):
                path = EXTERNAL_PLUGINS_PATH.joinpath(plugin)
                if not path.joinpath("plugin.json").is_file():
                    LOGGER.warning(f"Plugin {plugin} is not valid, deleting it...")
                    rmtree(str(path), ignore_errors=True)
                    continue

                plugin_file = loads(
                    path.joinpath("plugin.json").read_text(encoding="utf-8")
                )

                plugin_content = BytesIO()
                with tar_open(
                    fileobj=plugin_content, mode="w:gz", compresslevel=9
                ) as tar:
                    tar.add(str(path), arcname=plugin_file["id"])
                plugin_content.seek(0, 0)
                value = plugin_content.getvalue()

                plugin_file.update(
                    {
                        "external": True,
                        "page": False,
                        "method": "api",
                        "data": value,
                        "checksum": sha256(value).hexdigest(),
                    }
                )

                if "ui" in listdir(str(path)):
                    plugin_file["page"] = True

                external_plugins.append(plugin_file)
                external_plugins_ids.append(plugin_file["id"])

            for plugin in DB.get_plugins(external=True, with_data=True):
                if (
                    plugin["method"] != "api"
                    and plugin["id"] not in external_plugins_ids
                ):
                    external_plugins.append(plugin)

            err = DB.update_external_plugins(external_plugins)

            if err:
                LOGGER.error(
                    f"Couldn't update external plugins to database: {err}, plugins will not be available"
                )
            else:
                LOGGER.info("External plugins successfully updated to database")

    if not DB.is_initialized():
        config = Configurator(
            str(SETTINGS_PATH),
            str(CORE_PLUGINS_PATH),
            str(EXTERNAL_PLUGINS_PATH),
            {},
            LOGGER,
        )
        default_config = config.get_config()
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
            version=BUNKERWEB_VERSION,
            integration=INTEGRATION,
        )

        if err:
            LOGGER.error(
                f"Can't Initialize database : {err}",
            )
            stop(1)
        else:
            LOGGER.info("Database initialized")
    else:
        err: str = DB.update_db_schema(BUNKERWEB_VERSION)

        if err and not err.startswith("The database"):
            LOGGER.error(f"Can't update database schema : {err}")
            stop(1)
        elif not err:
            LOGGER.info("Database schema updated to latest version successfully")


@app.on_event("shutdown")
async def shutdown_event():
    del DB


if __name__ == "__main__":
    from uvicorn import run

    uvicorn_port = getenv("UVICORN_PORT", GLOBAL_ENV.get("UVICORN_PORT", "1337"))

    if not uvicorn_port.isdigit():
        LOGGER.error(f"Invalid port provided: {uvicorn_port}, exiting...")
        stop(1)

    run(
        app,
        host=getenv("LISTEN_ADDR", GLOBAL_ENV.get("LISTEN_ADDR", "0.0.0.0")),
        port=int(uvicorn_port),
        reload=True,
        proxy_headers=False,
        server_header=False,
        date_header=False,
    )
