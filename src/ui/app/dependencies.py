from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from logging import getLogger
from os import getenv, sep
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from tarfile import open as tar_open
from traceback import format_exc

from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall  # type: ignore

from app.api_client import ApiClient
from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData

# DB is no longer used by the UI (all access goes through API_CLIENT).
# Exported as None for backward compatibility with core plugin blueprints that import it.
DB = None

DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

API_CLIENT = ApiClient(
    base_url=getenv("API_URL", "http://bw-api:5000"),
    api_token=getenv("API_TOKEN", ""),
)

BW_CONFIG = Config(data=DATA, api_client=API_CLIENT)
BW_INSTANCES_UTILS = InstancesUtils(api_client=API_CLIENT)

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")

# Shared thread pool executor for configuration tasks in routes
# This prevents spawning new threads for each config operation
CONFIG_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-route-tasks")

# Dedicated pool for read-heavy page fan-outs (e.g. /home runs its Redis
# aggregations and DB queries concurrently). Kept separate from
# CONFIG_TASKS_EXECUTOR so a long-running config mutation (import, plugin
# update) can never starve a user-facing page load via head-of-line blocking.
PAGE_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-page-tasks")


LOGGER = getLogger("UI")


def reload_plugins():
    plugins = API_CLIENT.get_plugins(type="all", with_data=True)
    # Collect plugin ids from the database for cleanup later.
    known_plugin_ids = {plugin["id"] for plugin in plugins}

    ignored_plugins = set()
    for plugin in plugins:
        # Determine the correct extraction path based on the plugin type.
        if plugin["type"] in ("external", "ui"):
            plugin_path = EXTERNAL_PLUGINS_PATH
        elif plugin["type"] == "pro":
            plugin_path = PRO_PLUGINS_PATH
        else:
            continue

        target = plugin_path / plugin["id"]

        # If the target exists, compare its checksum.
        if target.exists():
            with suppress(StopIteration, IndexError, FileNotFoundError):
                plugin_content = create_plugin_tar_gz(target, arc_root=target.name)
                if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                    ignored_plugins.add(target.name)
                    continue
                LOGGER.debug(f"Checksum of {target} has changed, removing it ...")

            if target.is_symlink() or target.is_file():
                with suppress(OSError):
                    target.unlink()
            elif target.is_dir():
                rmtree(target, ignore_errors=True)

        try:
            if plugin["data"]:
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    safe_tar_extractall(tar, plugin_path)

                plugin_folder = plugin_path / plugin["id"]
                # Add u+x permissions to executable files
                desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
                for subdir, pattern in (
                    ("jobs", "*"),
                    ("bwcli", "*"),
                    ("ui", "*.py"),
                ):
                    for executable_file in plugin_folder.joinpath(subdir).rglob(pattern):
                        if executable_file.stat().st_mode & 0o777 != desired_perms:
                            executable_file.chmod(desired_perms)
        except OSError as e:
            LOGGER.debug(format_exc())
            if plugin["method"] != "manual":
                LOGGER.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
        except BaseException as e:
            LOGGER.debug(format_exc())
            LOGGER.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")

    try:
        API_CLIENT.checked_changes(["ui_plugins"])
    except Exception as e:
        LOGGER.error(f"An error occurred when setting the changes to checked: {e}")

    # Cleanup: Remove plugin folders that exist on the filesystem but are not in the database.
    for plugin_path in (EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH):
        if plugin_path.exists():
            for item in plugin_path.iterdir():
                if item.name not in known_plugin_ids:
                    LOGGER.debug(f"Plugin {item.name} not found in database, removing it...")
                    with suppress(OSError):
                        if item.is_symlink() or item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            rmtree(item, ignore_errors=True)


def safe_reload_plugins(force: bool = False):
    DATA.load_from_file()
    if force or DATA.get("FORCE_RELOAD_PLUGIN", False) or not DATA.get("IS_RELOADING_PLUGINS", False):
        DATA["IS_RELOADING_PLUGINS"] = True
        reload_plugins()
