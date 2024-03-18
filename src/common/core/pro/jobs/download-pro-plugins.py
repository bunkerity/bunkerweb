#!/usr/bin/env python3

from datetime import datetime
from hashlib import sha256
from io import BytesIO
from os import getenv, listdir, chmod, sep
from os.path import join
from pathlib import Path
from stat import S_IEXEC
from sys import exit as sys_exit, path as sys_path
from threading import Lock
from uuid import uuid4
from glob import glob
from json import JSONDecodeError, loads
from shutil import copytree, rmtree
from tarfile import open as tar_open
from traceback import format_exc
from zipfile import ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from common_utils import get_os_info, get_integration, get_version  # type: ignore

API_ENDPOINT = "https://api.bunkerweb.io"
PREVIEW_ENDPOINT = "https://assets.bunkerity.com/bw-pro/preview"
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_DIR = Path(sep, "etc", "bunkerweb", "pro", "plugins")
STATUS_MESSAGES = {
    "invalid": "is not valid",
    "expired": "has expired",
    "suspended": "has been suspended",
}
LOGGER = setup_logger("Jobs.download-pro-plugins", getenv("LOG_LEVEL", "INFO"))
status = 0


def clean_pro_plugins(db) -> None:
    LOGGER.debug("Cleaning up Pro plugins...")
    # Clean Pro plugins
    rmtree(PRO_PLUGINS_DIR.joinpath("*"), ignore_errors=True)
    # Update database
    db.update_external_plugins([], _type="pro")


def install_plugin(plugin_path: Path, db, preview: bool = True) -> bool:
    plugin_file = plugin_path.joinpath("plugin.json")

    if not plugin_file.is_file():
        LOGGER.error(f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {plugin_path.name} (plugin.json not found)")
        return False

    # Load plugin.json
    try:
        metadata = loads(plugin_file.read_text(encoding="utf-8"))
    except JSONDecodeError:
        LOGGER.error(f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {plugin_path.name} (plugin.json is not valid)")
        return False

    # Don't go further if plugin is already installed
    if PRO_PLUGINS_DIR.joinpath(metadata["id"], "plugin.json").is_file():
        old_version = None

        for plugin in db.get_plugins(_type="pro"):
            if plugin["id"] == metadata["id"]:
                old_version = plugin["version"]
                break

        if old_version == metadata["version"]:
            LOGGER.warning(
                f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {metadata['id']} (version {metadata['version']} already installed)"
            )
            return False

        LOGGER.warning(
            f"{'Preview version of ' if preview else ''}Pro plugin {metadata['id']} is already installed but version {metadata['version']} is different from database ({old_version}), updating it..."
        )
        rmtree(PRO_PLUGINS_DIR.joinpath(metadata["id"]), ignore_errors=True)

    # Copy the plugin
    copytree(plugin_path, PRO_PLUGINS_DIR.joinpath(metadata["id"]))
    # Add u+x permissions to jobs files
    for job_file in glob(PRO_PLUGINS_DIR.joinpath(metadata["id"], "jobs", "*").as_posix()):
        st = Path(job_file).stat()
        chmod(job_file, st.st_mode | S_IEXEC)
    LOGGER.info(f"✅ {'Preview version of ' if preview else ''}Pro plugin {metadata['id']} (version {metadata['version']}) installed successfully!")
    return True


try:
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    db_metadata = db.get_metadata()
    current_date = datetime.now()
    pro_license_key = getenv("PRO_LICENSE_KEY")

    # If we already checked today, skip the check
    if pro_license_key == db_metadata["pro_license_key"] and db_metadata["last_pro_check"] and current_date.day == db_metadata["last_pro_check"].day:
        LOGGER.info("Skipping the check for BunkerWeb Pro license (already checked today)")
        sys_exit(0)

    LOGGER.info("Checking BunkerWeb Pro license key...")

    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
        "service_number": str(len(getenv("SERVER_NAME", "").split(" "))),
    }
    headers = {"User-Agent": f"BunkerWeb/{data['version']}"}
    default_metadata = {
        "is_pro": False,
        "pro_license_key": None,
        "pro_expire": None,
        "pro_status": "invalid",
        "pro_overlapped": False,
        "pro_services": 0,
    }
    metadata = {}
    error = False

    temp_dir = TMP_DIR.joinpath(str(uuid4()))
    temp_dir.mkdir(parents=True, exist_ok=True)

    if pro_license_key:
        default_metadata["pro_license_key"] = (pro_license_key := pro_license_key.strip())

        LOGGER.info("BunkerWeb Pro license provided, checking if it's valid...")
        headers["Authorization"] = f"Bearer {pro_license_key}"
        resp = get(f"{API_ENDPOINT}/pro/status", headers=headers, json=data, timeout=5, allow_redirects=True)

        if resp.status_code == 403:
            LOGGER.error(f"Access denied to {API_ENDPOINT}/pro-status - please check your BunkerWeb Pro access at https://panel.bunkerweb.io/")
            error = True
            if resp.headers.get("Content-Type", "") == "application/json":
                resp_data = resp.json()
                if db_metadata["is_pro"] and resp_data.get("action") == "clean":
                    clean_pro_plugins(db)
        elif resp.status_code == 429:
            LOGGER.warning("Too many requests to the remote server while checking BunkerWeb Pro license, please try again later")
            sys_exit(0)
        elif resp.status_code == 500:
            LOGGER.error("An error occurred with the remote server while checking BunkerWeb Pro license, please try again later")
            sys_exit(2)
        else:
            resp.raise_for_status()

            metadata = resp.json()["data"]
            LOGGER.debug(f"Got BunkerWeb Pro license metadata: {metadata}")
            metadata["pro_expire"] = datetime.strptime(metadata["pro_expire"], "%Y-%m-%d") if metadata["pro_expire"] else None
            if metadata["pro_expire"] and metadata["pro_expire"] < datetime.now():
                metadata["pro_status"] = "expired"
            if metadata["pro_services"] < int(data["service_number"]):
                metadata["pro_overlapped"] = True
            metadata["is_pro"] = metadata["pro_status"] == "active"

    metadata = default_metadata | metadata
    db.set_pro_metadata(metadata)

    if metadata["is_pro"] != db_metadata["is_pro"]:
        clean_pro_plugins(db)

    if metadata["is_pro"]:
        LOGGER.info("🚀 Your BunkerWeb Pro license is valid, checking if there are new or updated Pro plugins...")

        resp = get(f"{API_ENDPOINT}/pro/download", headers=headers, json=data, timeout=5, allow_redirects=True)

        if resp.status_code == 403:
            LOGGER.error(f"Access denied to {API_ENDPOINT}/pro - please check your BunkerWeb Pro access at https://panel.bunkerweb.io/")
            error = True
            if resp.headers.get("Content-Type", "") == "application/json":
                resp_data = resp.json()
                if resp_data.get("action") == "clean":
                    metadata = default_metadata.copy()
                    db.set_pro_metadata(metadata)
                    clean_pro_plugins(db)
        elif resp.status_code == 429:
            LOGGER.warning("Too many requests to the remote server while checking BunkerWeb Pro plugins, please try again later")
            sys_exit(0)
        elif resp.headers.get("Content-Type", "") != "application/octet-stream":
            LOGGER.error(f"Got unexpected content type: {resp.headers.get('Content-Type', 'missing')} from {API_ENDPOINT}/pro")
            status = 2
            sys_exit(status)

    if not metadata["is_pro"]:
        if metadata["pro_overlapped"]:
            message = (
                f"You have exceeded the number of services allowed by your BunkerWeb Pro license: {metadata['pro_services']} (current: {data['service_number']}"
            )
        elif pro_license_key:
            message = "Your BunkerWeb Pro license " + (
                STATUS_MESSAGES.get(metadata["pro_status"], "is not valid or has expired") if not error else "is not valid or has expired"
            )
        else:
            LOGGER.info("If you wish to purchase a BunkerWeb Pro license, please visit https://panel.bunkerweb.io/")
            message = "No BunkerWeb Pro license key provided"
        LOGGER.warning(f"{message}, only checking if there are new or updated preview versions of Pro plugins...")

        resp = get(f"{PREVIEW_ENDPOINT}/v{data['version']}.zip", timeout=5, allow_redirects=True)

        if resp.status_code == 404:
            LOGGER.error(f"Couldn't find Pro plugins for BunkerWeb version {data['version']} at {PREVIEW_ENDPOINT}/v{data['version']}.zip")
            status = 2
            sys_exit(status)
        elif resp.status_code == 429:
            LOGGER.warning("Too many requests to the remote server while checking Preview Pro plugins, please try again later")
            sys_exit(0)
        elif resp.headers.get("Content-Type", "") != "application/zip":
            LOGGER.error(f"Got unexpected content type: {resp.headers.get('Content-Type', 'missing')} from {PREVIEW_ENDPOINT}/v{data['version']}.zip")
            status = 2
            sys_exit(status)

    if resp.status_code == 500:
        LOGGER.error("An error occurred with the remote server, please try again later")
        status = 2
        sys_exit(status)
    resp.raise_for_status()

    with BytesIO(resp.content) as plugin_content:
        with ZipFile(plugin_content) as zf:
            zf.extractall(path=temp_dir)

    plugin_nbr = 0

    # Install plugins
    try:
        for plugin_path in temp_dir.glob("*"):
            try:
                if install_plugin(plugin_path, db, not metadata["is_pro"]):
                    plugin_nbr += 1
            except FileExistsError:
                LOGGER.warning(f"Skipping installation of pro plugin {plugin_path.name} (already installed)")
    except:
        LOGGER.exception("Exception while installing pro plugin(s)")
        status = 2
        sys_exit(status)

    if not plugin_nbr:
        LOGGER.info("All Pro plugins are up to date")
        sys_exit(0)

    pro_plugins = []
    pro_plugins_ids = []
    for plugin in listdir(PRO_PLUGINS_DIR):
        path = PRO_PLUGINS_DIR.joinpath(plugin)
        if not path.joinpath("plugin.json").is_file():
            LOGGER.warning(f"Plugin {plugin} is not valid, deleting it...")
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
        LOGGER.error(f"Couldn't update Pro plugins to database: {err}")
        sys_exit(2)

    db.set_pro_metadata(metadata | {"last_pro_check": current_date})
    status = 1
    LOGGER.info("🚀 Pro plugins downloaded and installed successfully!")
except SystemExit as e:
    status = e.code
except:
    status = 2
    LOGGER.error(f"Exception while running download-pro-plugins.py :\n{format_exc()}")

for plugin_tmp in glob(TMP_DIR.joinpath("*").as_posix()):
    rmtree(plugin_tmp, ignore_errors=True)

sys_exit(status)
