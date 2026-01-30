#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime, timezone
from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from uuid import uuid4
from json import JSONDecodeError, load as json_load, loads
from shutil import copytree, rmtree
from tarfile import open as tar_open
from zipfile import ZipFile

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from requests import get
from requests.exceptions import ConnectionError

from common_utils import bytes_hash, get_os_info, get_integration, get_version, add_dir_to_tar_safely  # type: ignore
from Database import Database  # type: ignore
from logger import getLogger  # type: ignore

API_ENDPOINT = "https://api.bunkerweb.io"
PREVIEW_ENDPOINT = "https://assets.bunkerity.com/bw-pro/preview"
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_DIR = Path(sep, "etc", "bunkerweb", "pro", "plugins")
STATUS_MESSAGES = {
    "invalid": "is not valid",
    "expired": "has expired",
    "suspended": "has been suspended",
}
LOGGER = getLogger("PRO.DOWNLOAD-PLUGINS")
status = 0
existing_pro_plugin_ids = set()
cleaned_up_plugins = False


def clean_pro_plugins(db) -> None:
    global cleaned_up_plugins

    LOGGER.warning("Cleaning up Pro plugins...")
    # Clean Pro plugins
    for plugin_dir in PRO_PLUGINS_DIR.glob("*"):
        if plugin_dir.is_dir():
            plugin_json = plugin_dir / "plugin.json"
            if plugin_json.exists():
                # Delete all files and subdirectories except plugin.json
                for item in plugin_dir.iterdir():
                    if item != plugin_json:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            rmtree(item, ignore_errors=True)
            else:
                # If no plugin.json, remove the entire directory
                rmtree(plugin_dir, ignore_errors=True)
    # Update database
    db.update_external_plugins([], _type="pro", only_clear_metadata=True)
    cleaned_up_plugins = True


def install_plugin(plugin_path: Path, db, preview: bool = True) -> bool:
    plugin_file = plugin_path.joinpath("plugin.json")

    if not plugin_file.is_file():
        LOGGER.error(f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {plugin_path.name} (plugin.json not found)")
        return False

    # Load plugin.json
    try:
        metadata = loads(plugin_file.read_text(encoding="utf-8"))
    except JSONDecodeError as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {plugin_path.name} (plugin.json is not valid) :\n{e}")
        return False

    new_plugin_path = PRO_PLUGINS_DIR.joinpath(metadata["id"])

    # Don't go further if plugin is already installed
    if new_plugin_path.is_dir():
        old_version = None

        for plugin in db.get_plugins(_type="pro"):
            if plugin["id"] == metadata["id"]:
                old_version = plugin["version"]
                break

        if not cleaned_up_plugins and old_version == metadata["version"]:
            LOGGER.warning(
                f"Skipping installation of {'preview version of ' if preview else ''}Pro plugin {metadata['id']} (version {metadata['version']} already installed)"
            )
            return False

        if old_version != metadata["version"]:
            LOGGER.warning(
                f"{'Preview version of ' if preview else ''}Pro plugin {metadata['id']} is already installed but version {metadata['version']} is different from database ({old_version}), updating it..."
            )
        rmtree(new_plugin_path, ignore_errors=True)

    # Copy the plugin
    copytree(plugin_path, new_plugin_path)
    # Add u+x permissions to executable files
    desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
    for subdir, pattern in (
        ("jobs", "*"),
        ("bwcli", "*"),
        ("ui", "*.py"),
    ):
        for executable_file in new_plugin_path.joinpath(subdir).rglob(pattern):
            if executable_file.stat().st_mode & 0o777 != desired_perms:
                executable_file.chmod(desired_perms)
    LOGGER.info(f"✅ {'Preview version of ' if preview else ''}Pro plugin {metadata['id']} (version {metadata['version']}) installed successfully!")
    return True


try:
    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    db_metadata = db.get_metadata()
    current_date = datetime.now().astimezone()
    pro_license_key = getenv("PRO_LICENSE_KEY", "").strip()
    force_update = bool(db_metadata.get("force_pro_update", False))
    if force_update:
        with suppress(BaseException):
            db.set_metadata({"force_pro_update": False})

    LOGGER.info("Checking BunkerWeb Pro status..." if not force_update else "Force update requested: skipping status check and metadata update")

    data = {
        "integration": get_integration(),
        "version": get_version(),
        "os": get_os_info(),
        "service_number": str(len(getenv("SERVER_NAME", "www.example.com").split())),
    }
    headers = {"User-Agent": f"BunkerWeb/{data['version']}"}
    default_metadata = {
        "is_pro": False,
        "pro_license": pro_license_key,
        "pro_expire": None,
        "pro_status": "invalid",
        "pro_overlapped": False,
        "pro_services": 0,
        "non_draft_services": 0,
    }
    metadata = {
        "non_draft_services": int(data["service_number"]),
    }
    error = False

    temp_dir = TMP_DIR.joinpath(str(uuid4()))
    temp_dir.mkdir(parents=True, exist_ok=True)

    if pro_license_key and not force_update:
        LOGGER.info("BunkerWeb Pro license provided, checking if it's valid...")
        headers["Authorization"] = f"Bearer {pro_license_key}"
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                resp = get(f"{API_ENDPOINT}/pro/status", headers=headers, json=data, timeout=8, allow_redirects=True)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)

        if resp.status_code == 403:
            LOGGER.error(f"Access denied to {API_ENDPOINT}/pro-status - please check your BunkerWeb Pro access at https://panel.bunkerweb.io/")
            error = True
            clean = False
            if resp.headers.get("Content-Type", "") == "application/json":
                resp_data = resp.json()
                clean = db_metadata["is_pro"] and resp_data.get("action") == "clean"

            if clean:
                clean_pro_plugins(db)
            else:
                LOGGER.warning("Skipping the check for BunkerWeb Pro license...")
                sys_exit(0)
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
            metadata["is_pro"] = metadata["pro_status"] == "active"
            if metadata["is_pro"] and metadata["pro_services"] < int(data["service_number"]):
                metadata["pro_overlapped"] = True

    db_metadata = db.get_metadata()

    # Skip daily/license checks if forced
    if not force_update:
        # Convert current date to UTC and normalize to midnight for daily comparison
        current_day_utc = current_date.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Normalize database last check date to midnight UTC
        # Note: MariaDB returns naive datetime (stored as UTC), so we need to make it timezone-aware
        db_last_check = db_metadata["last_pro_check"]
        if db_last_check:
            if db_last_check.tzinfo is None:
                db_last_check = db_last_check.replace(tzinfo=timezone.utc)
            else:
                db_last_check = db_last_check.astimezone(timezone.utc)
        db_last_check_day_utc = db_last_check.replace(hour=0, minute=0, second=0, microsecond=0) if db_last_check else None

        # Check if we can skip: same license, same pro status, not overlapped (or same service count), and already checked today
        license_unchanged = pro_license_key == db_metadata.get("pro_license", "")
        pro_status_unchanged = metadata.get("is_pro", False) == db_metadata["is_pro"]
        overlap_ok = not metadata.get("pro_overlapped", False) or metadata.get("non_draft_services", 0) == db_metadata.get("non_draft_services", 0)
        already_checked_today = db_last_check_day_utc is not None and current_day_utc == db_last_check_day_utc

        if license_unchanged and pro_status_unchanged and overlap_ok and already_checked_today:
            LOGGER.info("Skipping the check for BunkerWeb Pro license (already checked today)")
            sys_exit(0)

        default_metadata["last_pro_check"] = current_date
        metadata = default_metadata | metadata
        db.set_metadata(metadata)

        if metadata["is_pro"] != db_metadata["is_pro"]:
            clean_pro_plugins(db)
    else:
        # In force mode, keep current metadata and status
        metadata = {"is_pro": db_metadata["is_pro"], "pro_overlapped": db_metadata.get("pro_overlapped", False)}
        # Ensure Authorization header is present if we have a key
        if pro_license_key:
            headers["Authorization"] = f"Bearer {pro_license_key}"

    if metadata["is_pro"]:
        LOGGER.info("🚀 Your BunkerWeb Pro license is valid, checking if there are new or updated Pro plugins...")

        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                resp = get(f"{API_ENDPOINT}/pro/download", headers=headers, json=data, timeout=8, stream=True, allow_redirects=True)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)

        if resp.status_code == 403:
            LOGGER.error(f"Access denied to {API_ENDPOINT}/pro - please check your BunkerWeb Pro access at https://panel.bunkerweb.io/")
            error = True
            clean = False
            if resp.headers.get("Content-Type", "") == "application/json":
                resp_data = {}
                with BytesIO() as resp_content:
                    for chunk in resp.iter_content(chunk_size=8192):
                        resp_content.write(chunk)
                    resp_content.seek(0)
                    resp_data = json_load(resp_content)

                clean = resp_data.get("action") == "clean"
            # In force mode, keep current state, do not clean or change metadata
            if force_update:
                LOGGER.warning("Skipping forced update due to access denied; keeping current PRO plugins state.")
                sys_exit(0)
            else:
                if clean:
                    metadata = default_metadata.copy()
                    db.set_metadata(metadata)
                    clean_pro_plugins(db)
                else:
                    LOGGER.warning("Skipping the check for new or updated Pro plugins...")
                    sys_exit(0)
        elif resp.status_code == 429:
            LOGGER.warning("Too many requests to the remote server while checking BunkerWeb Pro plugins, please try again later")
            sys_exit(0)
        elif resp.headers.get("Content-Type", "") != "application/octet-stream":
            LOGGER.error(f"Got unexpected content type: {resp.headers.get('Content-Type', 'missing')} from {API_ENDPOINT}/pro")
            status = 2
            sys_exit(status)
        elif resp.status_code != 500:
            resp.raise_for_status()

    if not metadata["is_pro"]:
        if metadata["pro_overlapped"]:
            LOGGER.warning(
                f"You have exceeded the number of services allowed by your BunkerWeb Pro license: {metadata['pro_services']} (current: {data['service_number']})"
            )

        if pro_license_key:
            message = "Your BunkerWeb Pro license " + (
                STATUS_MESSAGES.get(metadata["pro_status"], "is not valid or has expired") if not error else "is not valid or has expired"
            )
        else:
            LOGGER.info("If you wish to purchase a BunkerWeb Pro license, please visit https://panel.bunkerweb.io/")
            message = "No BunkerWeb Pro license key provided"
        # In force mode, still try preview download (keeps current if it fails)
        LOGGER.warning(f"{message}, only checking if there are new or updated preview versions of Pro plugins...")

        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                resp = get(f"{PREVIEW_ENDPOINT}/v{data['version']}.zip", timeout=8, stream=True, allow_redirects=True)
                break
            except ConnectionError as e:
                retry_count += 1
                if retry_count == max_retries:
                    raise e
                LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                sleep(3)

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
        elif resp.status_code != 500:
            resp.raise_for_status()
            # Add retry logic for connection refused errors

    if resp.status_code == 500:
        LOGGER.error("An error occurred with the remote server, please try again later")
        status = 2
        sys_exit(status)

    with BytesIO() as plugin_content:
        for chunk in resp.iter_content(chunk_size=8192):
            plugin_content.write(chunk)
        plugin_content.seek(0)

        with ZipFile(plugin_content) as zf:
            zf.extractall(path=temp_dir)

    existing_pro_plugin_ids = {plugin["id"] for plugin in db.get_plugins(_type="pro")}

    plugin_nbr = 0

    # Install plugins
    try:
        for plugin_path in temp_dir.glob("*"):
            try:
                if install_plugin(plugin_path, db, not metadata["is_pro"]):
                    plugin_nbr += 1
            except FileExistsError:
                LOGGER.warning(f"Skipping installation of pro plugin {plugin_path.name} (already installed)")
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Exception while installing pro plugin(s) :\n{e}")
        status = 2
        sys_exit(status)

    if not plugin_nbr:
        LOGGER.info("All Pro plugins are up to date")
        sys_exit(0)

    pro_plugins = []
    pro_plugins_ids = []
    for plugin_path in PRO_PLUGINS_DIR.glob("*"):
        if not plugin_path.joinpath("plugin.json").is_file():
            LOGGER.warning(f"Plugin {plugin_path.name} is not valid, deleting it...")
            rmtree(plugin_path, ignore_errors=True)
            continue

        with BytesIO() as plugin_content:
            with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=3) as tar:
                add_dir_to_tar_safely(tar, plugin_path, arc_root=plugin_path.name)
            plugin_content.seek(0, 0)

            with plugin_path.joinpath("plugin.json").open("r", encoding="utf-8") as f:
                plugin_data = json_load(f)

            checksum = bytes_hash(plugin_content, algorithm="sha256")
            plugin_data.update(
                {
                    "type": "pro",
                    "page": plugin_path.joinpath("ui").is_dir(),
                    "method": "scheduler",
                    "data": plugin_content.getvalue(),
                    "checksum": checksum,
                }
            )

        pro_plugins.append(plugin_data)
        pro_plugins_ids.append(plugin_data["id"])

    for plugin in db.get_plugins(_type="pro", with_data=True):
        if plugin["method"] != "scheduler" and plugin["id"] not in pro_plugins_ids:
            pro_plugins.append(plugin)

    err = db.update_external_plugins(pro_plugins, _type="pro")

    if err:
        LOGGER.error(f"Couldn't update Pro plugins to database: {err}")
        # Only cleanup newly added plugins if the error suggests a database issue
        if "max_allowed_packet" in err.lower() or "packet" in err.lower():
            LOGGER.warning("Database packet size issue detected. Consider increasing max_allowed_packet in MariaDB/MySQL configuration.")

        plugins_to_cleanup = [plugin_id for plugin_id in pro_plugins_ids if plugin_id not in existing_pro_plugin_ids]
        if plugins_to_cleanup:
            LOGGER.warning("Cleaning up Pro plugins that were not previously in the database due to the failed update.")
            for plugin_id in plugins_to_cleanup:
                plugin_dir = PRO_PLUGINS_DIR.joinpath(plugin_id)
                if plugin_dir.exists():
                    LOGGER.debug(f"Removing Pro plugin directory {plugin_dir} after database update failure.")
                    rmtree(plugin_dir, ignore_errors=True)
        sys_exit(2)

    status = 1
    LOGGER.info("🚀 Pro plugins downloaded and installed successfully!")
except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running download-pro-plugins.py :\n{e}")

for plugin_tmp in TMP_DIR.glob("*"):
    rmtree(plugin_tmp, ignore_errors=True)

sys_exit(status)
