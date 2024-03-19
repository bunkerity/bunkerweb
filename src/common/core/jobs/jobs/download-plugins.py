#!/usr/bin/env python3

from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from stat import S_IEXEC
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from uuid import uuid4
from json import JSONDecodeError, loads
from shutil import copytree, rmtree
from tarfile import open as tar_open
from traceback import format_exc
from zipfile import ZipFile

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (
        ("deps", "python"),
        ("utils",),
        ("api",),
        ("db",),
    )
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from magic import Magic
from requests import get

from common_utils import bytes_hash  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore


EXTERNAL_PLUGINS_DIR = Path(sep, "etc", "bunkerweb", "plugins")
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "plugins")
LOGGER = setup_logger("Jobs.download-plugins", getenv("LOG_LEVEL", "INFO"))
status = 0


def install_plugin(plugin_path: Path, db) -> bool:
    plugin_file = plugin_path.joinpath("plugin.json")

    if not plugin_file.is_file():
        LOGGER.error(f"Skipping installation of plugin {plugin_path.name} (plugin.json not found)")
        return False

    # Load plugin.json
    try:
        metadata = loads(plugin_file.read_text(encoding="utf-8"))
    except JSONDecodeError:
        LOGGER.error(f"Skipping installation of plugin {plugin_path.name} (plugin.json is not valid)")
        return False

    new_plugin_path = EXTERNAL_PLUGINS_DIR.joinpath(metadata["id"])

    # Don't go further if plugin is already installed
    if new_plugin_path.is_dir():
        old_version = None

        for plugin in db.get_plugins(_type="external"):
            if plugin["id"] == metadata["id"]:
                old_version = plugin["version"]
                break

        if old_version == metadata["version"]:
            LOGGER.warning(f"Skipping installation of plugin {metadata['id']} (version {metadata['version']} already installed)")
            return False

        LOGGER.warning(
            f"Plugin {metadata['id']} is already installed but version {metadata['version']} is different from database ({old_version}), updating it..."
        )
        rmtree(new_plugin_path, ignore_errors=True)

    # Copy the plugin
    copytree(plugin_path, new_plugin_path)
    # Add u+x permissions to jobs files
    for job_file in new_plugin_path.joinpath("jobs").glob("*"):
        job_file.chmod(job_file.stat().st_mode | S_IEXEC)
    LOGGER.info(f"Plugin {metadata['id']} installed")
    return True


try:
    # Check if we have plugins to download
    plugin_urls = getenv("EXTERNAL_PLUGIN_URLS")
    if not plugin_urls:
        LOGGER.info("No external plugins to download")
        sys_exit(0)

    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    plugin_nbr = 0

    # Loop on URLs
    LOGGER.info(f"Downloading external plugins from {plugin_urls}...")
    for plugin_url in plugin_urls.split(" "):
        # Download Plugin file
        try:
            if plugin_urls.startswith("file://"):
                content = Path(plugin_urls[7:]).read_bytes()
            else:
                content = b""
                resp = get(
                    plugin_url,
                    headers={"User-Agent": "BunkerWeb"},
                    stream=True,
                    timeout=30,
                )

                if resp.status_code != 200:
                    LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                    continue

                # Iterate over the response content in chunks
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        content += chunk
        except:
            LOGGER.error(f"Exception while downloading plugin(s) from {plugin_url} :\n{format_exc()}")
            status = 2
            continue

        # Extract it to tmp folder
        temp_dir = TMP_DIR.joinpath(str(uuid4()))
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            file_type = Magic(mime=True).from_buffer(content)

            if file_type == "application/zip":
                with ZipFile(BytesIO(content)) as zf:
                    zf.extractall(path=temp_dir)
            elif file_type == "application/gzip":
                with tar_open(fileobj=BytesIO(content), mode="r:gz") as tar:
                    try:
                        tar.extractall(path=temp_dir, filter="data")
                    except TypeError:
                        tar.extractall(path=temp_dir)
            elif file_type == "application/x-tar":
                with tar_open(fileobj=BytesIO(content), mode="r") as tar:
                    try:
                        tar.extractall(path=temp_dir, filter="data")
                    except TypeError:
                        tar.extractall(path=temp_dir)
            else:
                LOGGER.error(f"Unknown file type for {plugin_url}, either zip or tar are supported, skipping...")
                continue
        except:
            LOGGER.error(f"Exception while decompressing plugin(s) from {plugin_url} :\n{format_exc()}")
            status = 2
            continue

        # Install plugins
        try:
            for plugin_path in temp_dir.rglob("**/plugin.json"):
                try:
                    if install_plugin(plugin_path.parent, db):
                        plugin_nbr += 1
                except FileExistsError:
                    LOGGER.warning(f"Skipping installation of plugin {plugin_path.parent.name} (already installed)")
        except:
            LOGGER.error(f"Exception while installing plugin(s) from {plugin_url} :\n{format_exc()}")
            status = 2

    if not plugin_nbr:
        LOGGER.info("No external plugins to update to database")
        sys_exit(0)

    external_plugins = []
    external_plugins_ids = []
    for plugin_path in EXTERNAL_PLUGINS_DIR.glob("*"):
        if not plugin_path.joinpath("plugin.json").is_file():
            LOGGER.warning(f"Plugin {plugin_path.name} is not valid, deleting it...")
            rmtree(plugin_path, ignore_errors=True)
            continue

        plugin_file = loads(plugin_path.joinpath("plugin.json").read_text(encoding="utf-8"))

        with BytesIO() as plugin_content:
            with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                tar.add(plugin_path, arcname=plugin_path.name)
            plugin_content.seek(0)
            value = plugin_content.getvalue()

        plugin_file.update(
            {
                "type": "external",
                "page": False,
                "method": "scheduler",
                "data": value,
                "checksum": bytes_hash(value, algorithm="sha256"),
            }
        )

        if "ui" in list(plugin_path.iterdir()):
            plugin_file["page"] = True

        external_plugins.append(plugin_file)
        external_plugins_ids.append(plugin_file["id"])

    lock = Lock()

    for plugin in db.get_plugins(_type="external", with_data=True):
        if plugin["method"] != "scheduler" and plugin["id"] not in external_plugins_ids:
            external_plugins.append(plugin)

    with lock:
        err = db.update_external_plugins(external_plugins)

    if err:
        LOGGER.error(f"Couldn't update external plugins to database: {err}")

    status = 1
    LOGGER.info("External plugins downloaded and installed")

except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running download-plugins.py :\n{format_exc()}")

for plugin_tmp in TMP_DIR.glob("*"):
    rmtree(plugin_tmp, ignore_errors=True)

sys_exit(status)
