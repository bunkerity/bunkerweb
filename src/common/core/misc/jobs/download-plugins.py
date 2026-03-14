#!/usr/bin/env python3

from contextlib import suppress
from io import BytesIO
from mimetypes import guess_type
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
from tarfile import TarError, open as tar_open
from zipfile import BadZipFile, ZipFile

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
from requests.exceptions import ConnectionError

from common_utils import bytes_hash, create_plugin_tar_gz  # type: ignore
from Database import Database  # type: ignore
from logger import getLogger  # type: ignore

EXTERNAL_PLUGINS_DIR = Path(sep, "etc", "bunkerweb", "plugins")
TMP_DIR = Path(sep, "var", "tmp", "bunkerweb", "plugins")
LOGGER = getLogger("DOWNLOAD-EXTERNAL-PLUGINS")
status = 0


def _set_plugin_permissions(plugin_path: Path) -> None:
    # Add u+x permissions to executable files
    desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
    for subdir, pattern in (
        ("jobs", "*"),
        ("bwcli", "*"),
        ("ui", "*.py"),
    ):
        for executable_file in plugin_path.joinpath(subdir).rglob(pattern):
            if executable_file.stat().st_mode & 0o777 != desired_perms:
                executable_file.chmod(desired_perms)


def _plugin_checksum_matches_database(plugin_path: Path, checksum: str) -> bool:
    try:
        plugin_content = create_plugin_tar_gz(plugin_path, arc_root=plugin_path.name)
        return bytes_hash(plugin_content, algorithm="sha256") == checksum
    except BaseException as e:
        LOGGER.debug(format_exc())
        LOGGER.warning(f"Could not verify plugin {plugin_path.name} integrity before skipping reinstall: {e}")
        return False


def _cleanup_stale_plugin_dirs() -> None:
    for pattern in (".*.tmp-*", ".*.bak-*"):
        for stale_dir in EXTERNAL_PLUGINS_DIR.glob(pattern):
            if stale_dir.is_dir():
                LOGGER.warning(f"Found stale plugin directory {stale_dir}, cleaning it up ...")
                rmtree(stale_dir, ignore_errors=True)


def _install_plugin_atomically(plugin_path: Path, new_plugin_path: Path) -> None:
    tmp_plugin_path = new_plugin_path.parent.joinpath(f".{new_plugin_path.name}.tmp-{uuid4()}")
    backup_plugin_path = new_plugin_path.parent.joinpath(f".{new_plugin_path.name}.bak-{uuid4()}")
    replaced_existing = False

    try:
        copytree(plugin_path, tmp_plugin_path)
        _set_plugin_permissions(tmp_plugin_path)

        if new_plugin_path.is_dir():
            new_plugin_path.rename(backup_plugin_path)
            replaced_existing = True

        tmp_plugin_path.rename(new_plugin_path)
    except BaseException:
        rmtree(tmp_plugin_path, ignore_errors=True)

        if replaced_existing and backup_plugin_path.is_dir() and not new_plugin_path.exists():
            with suppress(OSError):
                backup_plugin_path.rename(new_plugin_path)
        raise
    finally:
        if backup_plugin_path.is_dir() and new_plugin_path.exists():
            rmtree(backup_plugin_path, ignore_errors=True)


def install_plugin(plugin_path: Path, db) -> bool:
    plugin_file = plugin_path.joinpath("plugin.json")

    if not plugin_file.is_file():
        LOGGER.error(f"Skipping installation of plugin {plugin_path.name} (plugin.json not found)")
        return False

    # Load plugin.json
    try:
        metadata = loads(plugin_file.read_text(encoding="utf-8"))
    except JSONDecodeError as e:
        LOGGER.debug(format_exc())
        LOGGER.error(f"Skipping installation of plugin {plugin_path.name} (plugin.json is not valid) :\n{e}")
        return False

    new_plugin_path = EXTERNAL_PLUGINS_DIR.joinpath(metadata["id"])

    # Don't go further if plugin is already installed
    if new_plugin_path.is_dir():
        old_version = None
        old_checksum = ""
        old_method = ""

        for plugin in db.get_plugins(_type="external"):
            if plugin["id"] == metadata["id"]:
                old_version = plugin["version"]
                old_checksum = plugin.get("checksum", "")
                old_method = plugin.get("method", "")
                break

        if old_version == metadata["version"]:
            if old_method != "scheduler":
                LOGGER.warning(
                    f"Skipping installation of plugin {metadata['id']} (version {metadata['version']} already installed by method {old_method or 'unknown'})"
                )
                return False

            if old_checksum and _plugin_checksum_matches_database(new_plugin_path, old_checksum):
                LOGGER.warning(f"Skipping installation of plugin {metadata['id']} (version {metadata['version']} already installed)")
                return False

            LOGGER.warning(f"Detected an integrity mismatch for plugin {metadata['id']}, reinstalling it...")
        elif old_version != metadata["version"]:
            LOGGER.warning(
                f"Plugin {metadata['id']} is already installed but version {metadata['version']} is different from database ({old_version}), updating it..."
            )

    _install_plugin_atomically(plugin_path, new_plugin_path)
    LOGGER.info(f"✅ Plugin {metadata['id']} (version {metadata['version']}) installed successfully!")
    return True


try:
    _cleanup_stale_plugin_dirs()

    # Check if we have plugins to download
    plugin_urls = getenv("EXTERNAL_PLUGIN_URLS", "").strip()
    if not plugin_urls:
        LOGGER.info("No external plugins to download")
        sys_exit(0)

    db = Database(LOGGER, sqlalchemy_string=getenv("DATABASE_URI"))
    plugin_nbr = 0

    # Loop on URLs
    LOGGER.info(f"Downloading external plugins from {plugin_urls}...")
    for plugin_url in plugin_urls.split():
        with BytesIO() as content:
            # Download Plugin file
            try:
                if plugin_url.startswith("file://"):
                    content.write(Path(plugin_url[7:]).read_bytes())
                else:
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        try:
                            resp = get(plugin_url, headers={"User-Agent": "BunkerWeb"}, stream=True, timeout=10)
                            break
                        except ConnectionError as e:
                            retry_count += 1
                            if retry_count == max_retries:
                                raise e
                            LOGGER.warning(f"Connection refused, retrying in 3 seconds... ({retry_count}/{max_retries})")
                            sleep(3)

                    if resp.status_code != 200:
                        LOGGER.warning(f"Got status code {resp.status_code}, skipping...")
                        continue

                    # Iterate over the response content in chunks
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            content.write(chunk)

                content.seek(0)
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while downloading plugin(s) from {plugin_url} :\n{e}")
                status = 2
                continue

            # Extract it to tmp folder
            temp_dir = TMP_DIR.joinpath(str(uuid4()))
            try:
                temp_dir.mkdir(parents=True, exist_ok=True)

                # Detect file type
                file_type = Magic(mime=True).from_buffer(content.getvalue())
                LOGGER.debug(f"Detected file type: {file_type}")

                # Fallback to file extension detection
                if file_type == "application/octet-stream":
                    file_type = guess_type(plugin_url)[0] or "application/octet-stream"
                    LOGGER.debug(f"Guessed file type from URL: {file_type}")

                content.seek(0)

                # Handle ZIP files
                if file_type == "application/zip" or plugin_url.endswith(".zip"):
                    try:
                        with ZipFile(content) as zf:
                            zf.extractall(path=temp_dir)
                        LOGGER.info(f"Successfully extracted ZIP file to {temp_dir}")
                    except BadZipFile as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(f"Invalid ZIP file: {e}")
                        continue

                # Handle TAR files (all compression types)
                elif file_type.startswith("application/x-tar") or plugin_url.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
                    try:
                        # Detect the appropriate tar mode
                        tar_mode = "r"
                        if plugin_url.endswith(".gz") or file_type == "application/gzip":
                            tar_mode = "r:gz"
                        elif plugin_url.endswith(".bz2"):
                            tar_mode = "r:bz2"
                        elif plugin_url.endswith(".xz"):
                            tar_mode = "r:xz"

                        with tar_open(fileobj=content, mode=tar_mode) as tar:
                            try:
                                tar.extractall(path=temp_dir, filter="fully_trusted")
                            except TypeError:
                                tar.extractall(path=temp_dir)
                        LOGGER.info(f"Successfully extracted TAR file to {temp_dir}")
                    except TarError as e:
                        LOGGER.debug(format_exc())
                        LOGGER.error(f"Invalid TAR file: {e}")
                        continue

                else:
                    LOGGER.error(f"Unknown file type for {plugin_url}, either ZIP or TAR is supported, skipping...")
                    continue

            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Exception while decompressing plugin(s) from {plugin_url}:\n{e}")
                continue

        # Install plugins
        try:
            for plugin_path in list(temp_dir.rglob("**/plugin.json")):
                try:
                    if install_plugin(plugin_path.parent, db):
                        plugin_nbr += 1
                except FileExistsError:
                    LOGGER.warning(f"Skipping installation of plugin {plugin_path.parent.name} (already installed)")
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Exception while installing plugin(s) from {plugin_url} :\n{e}")
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

        plugin_content = create_plugin_tar_gz(plugin_path, arc_root=plugin_path.name)

        with plugin_path.joinpath("plugin.json").open("r", encoding="utf-8") as f:
            plugin_data = json_load(f)

        checksum = bytes_hash(plugin_content, algorithm="sha256")
        plugin_data.update(
            {
                "type": "external",
                "page": plugin_path.joinpath("ui").is_dir(),
                "method": "scheduler",
                "data": plugin_content.getvalue(),
                "checksum": checksum,
            }
        )

        external_plugins.append(plugin_data)
        external_plugins_ids.append(plugin_data["id"])

    for plugin in db.get_plugins(_type="external", with_data=True):
        if plugin["method"] != "scheduler" and plugin["id"] not in external_plugins_ids:
            external_plugins.append(plugin)

    err = db.update_external_plugins(external_plugins, per_plugin_commit=False)

    if err:
        LOGGER.error(f"Couldn't update external plugins to database: {err}")

    status = 1
    LOGGER.info("External plugins downloaded and installed")

except SystemExit as e:
    status = e.code
except BaseException as e:
    status = 2
    LOGGER.debug(format_exc())
    LOGGER.error(f"Exception while running download-plugins.py :\n{e}")

rmtree(TMP_DIR, ignore_errors=True)

sys_exit(status)
