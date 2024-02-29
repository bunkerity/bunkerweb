#!/usr/bin/env python3

from hashlib import sha256
from io import BytesIO
from os import getenv, listdir, chmod, _exit, sep
from os.path import basename, dirname, join
from pathlib import Path
from stat import S_IEXEC
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from uuid import uuid4
from glob import glob
from json import dumps, loads
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

from requests import get

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from jobs import get_os_info, get_integration, get_version  # type: ignore

API_ENDPOINT = "https://api.bunkerweb.io/pro"
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_DIR = Path(sep, "etc", "bunkerweb", "pro", "plugins")
logger = setup_logger("Jobs.download-pro-plugins", getenv("LOG_LEVEL", "INFO"))
status = 0


def install_plugin(plugin_dir, db) -> bool:
    plugin_path = Path(plugin_dir)
    # Load plugin.json
    metadata = loads(plugin_path.joinpath("plugin.json").read_text(encoding="utf-8"))
    # Don't go further if plugin is already installed
    if PRO_PLUGINS_DIR.joinpath(metadata["id"], "plugin.json").is_file():
        old_version = None

        for plugin in db.get_plugins(_type="pro"):
            if plugin["id"] == metadata["id"]:
                old_version = plugin["version"]
                break

        if old_version == metadata["version"]:
            logger.warning(f"Skipping installation of pro plugin {metadata['id']} (version {metadata['version']} already installed)")
            return False

        logger.warning(f"Pro plugin {metadata['id']} is already installed but version {metadata['version']} is different from database ({old_version}), updating it...")
        rmtree(PRO_PLUGINS_DIR.joinpath(metadata["id"]), ignore_errors=True)

    # Copy the plugin
    copytree(plugin_dir, PRO_PLUGINS_DIR.joinpath(metadata["id"]))
    # Add u+x permissions to jobs files
    for job_file in glob(PRO_PLUGINS_DIR.joinpath(metadata["id"], "jobs", "*").as_posix()):
        st = Path(job_file).stat()
        chmod(job_file, st.st_mode | S_IEXEC)
    logger.info(f"Plugin {metadata['id']} installed")
    return True


try:
    logger.info(f"Trying to download pro plugins from {API_ENDPOINT}")

    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
        "service_number": str(len(getenv("SERVER_NAME", "").split(" "))),
    }

    headers = {"User-Agent": f"BunkerWeb/{data['version']}"}
    pro_license_key = getenv("PRO_LICENSE_KEY")
    if pro_license_key:
        headers["Authorization"] = f"Bearer {pro_license_key}"

    resp = get(API_ENDPOINT, headers=headers, json=data, timeout=5)
    resp.raise_for_status()

    if resp.headers.get("Content-Type", "") not in ("application/zip", "application/json"):
        logger.error(f"Got unexpected content type: {resp.headers.get('Content-Type', 'missing')} from {API_ENDPOINT}")
        status = 2
        sys_exit(status)

    db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"), pool=False)
    temp_dir = TMP_DIR.joinpath(str(uuid4()))
    temp_dir.mkdir(parents=True, exist_ok=True)

    if resp.headers.get("Content-Type") == "application/zip":
        logger.info("🚀 Your BunkerWeb Pro license is valid, checking if there are new or updated pro plugins...")

        db.set_is_pro(True)
        db.set_pro_expire("")
        db.set_pro_status("valid")
        db.set_pro_overlapped(False)
        db.set_pro_services("")

        with BytesIO(resp.content) as plugin_content:
            with ZipFile(plugin_content) as zf:
                zf.extractall(path=temp_dir)
    else:
        message = "No BunkerWeb Pro license key found"
        if pro_license_key:
            message = "Your BunkerWeb Pro license is not valid or has expired"
        logger.warning(f"{message}, only checking if there are new or updated info about pro plugins...")

        db.set_is_pro(False)
        db.set_pro_expire("")
        db.set_pro_status("invalid")
        db.set_pro_overlapped(False)
        db.set_pro_services("")

        plugins = resp.json()
        for plugin in plugins["data"]:
            plugin_path = temp_dir.joinpath(plugin["id"])
            plugin_path.mkdir(parents=True, exist_ok=True)
            plugin_path.joinpath("plugin.json").write_text(dumps(plugin, indent=4), encoding="utf-8")

    plugin_nbr = 0

    # Install plugins
    try:
        for plugin_dir in glob(temp_dir.joinpath("**", "plugin.json").as_posix(), recursive=True):
            try:
                if install_plugin(dirname(plugin_dir), db):
                    plugin_nbr += 1
            except FileExistsError:
                logger.warning(f"Skipping installation of plugin {basename(dirname(plugin_dir))} (already installed)")
    except:
        logger.exception("Exception while installing pro plugin(s)")
        status = 2
        sys_exit(status)

    if not plugin_nbr:
        logger.info("No pro plugins to update to database")
        _exit(0)

    pro_plugins = []
    pro_plugins_ids = []
    for plugin in listdir(PRO_PLUGINS_DIR):
        path = PRO_PLUGINS_DIR.joinpath(plugin)
        if not path.joinpath("plugin.json").is_file():
            logger.warning(f"Plugin {plugin} is not valid, deleting it...")
            rmtree(path, ignore_errors=True)
            continue

        plugin_file = loads(path.joinpath("plugin.json").read_text(encoding="utf-8"))

        with BytesIO() as plugin_content:
            with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                tar.add(path, arcname=path.name)
            plugin_content.seek(0)
            value = plugin_content.getvalue()

        plugin_file.update(
            {
                "type": "pro",
                "page": False,
                "method": "scheduler",
                "data": value,
                "checksum": sha256(value).hexdigest(),
            }
        )

        if "ui" in listdir(path):
            plugin_file["page"] = True

        pro_plugins.append(plugin_file)
        pro_plugins_ids.append(plugin_file["id"])

    lock = Lock()

    for plugin in db.get_plugins(_type="pro", with_data=True):
        if plugin["method"] != "scheduler" and plugin["id"] not in pro_plugins_ids:
            pro_plugins.append(plugin)

    with lock:
        err = db.update_external_plugins(pro_plugins, _type="pro")

    if err:
        logger.error(f"Couldn't update pro plugins to database: {err}")

    status = 1
    logger.info("Pro plugins downloaded and installed successfully!")
except:
    status = 2
    logger.error(f"Exception while running download-pro-plugins.py :\n{format_exc()}")

for plugin_tmp in glob(TMP_DIR.joinpath("*").as_posix()):
    rmtree(plugin_tmp, ignore_errors=True)

sys_exit(status)
