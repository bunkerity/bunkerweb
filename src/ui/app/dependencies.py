from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from json import load as json_load
from logging import getLogger
from os import sep
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from sys import path as sys_path
from tarfile import open as tar_open
from traceback import format_exc

BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")
GEN_PATH = BUNKERWEB_PATH.joinpath("gen").as_posix()
if GEN_PATH not in sys_path:
    sys_path.append(GEN_PATH)

from common_utils import bytes_hash, create_plugin_tar_gz, safe_tar_extractall  # type: ignore
from Configurator import Configurator  # type: ignore

from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData
from app.models.ui_database import UIDatabase

DB = UIDatabase(getLogger("UI"), log=False)
DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

BW_CONFIG = Config(DB, data=DATA)
BW_INSTANCES_UTILS = InstancesUtils(DB)

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
plugin_validator = None

# Shared thread pool executor for configuration tasks in routes
# This prevents spawning new threads for each config operation
CONFIG_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-route-tasks")

# Dedicated pool for read-heavy page fan-outs (e.g. /home runs its Redis
# aggregations and DB queries concurrently). Kept separate from
# CONFIG_TASKS_EXECUTOR so a long-running config mutation (import, plugin
# update) can never starve a user-facing page load via head-of-line blocking.
PAGE_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-ui-page-tasks")


def invalid_plugin_json(plugin_path: Path) -> bool:
    if plugin_path.is_symlink():
        return False
    plugin_file = plugin_path.joinpath("plugin.json")
    if not plugin_file.is_file():
        return False
    try:
        with plugin_file.open("r", encoding="utf-8") as file:
            plugin = json_load(file)
    except (OSError, ValueError) as e:
        DB.logger.error(f"Keeping invalid manual plugin {plugin_path.name}: {e}")
        return True

    global plugin_validator
    try:
        if plugin_validator is None:
            plugin_validator = Configurator(BUNKERWEB_PATH / "settings.json", BUNKERWEB_PATH / "core", [], [], {}, DB.logger)
        valid, message = plugin_validator._Configurator__validate_plugin(deepcopy(plugin))
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as e:
        DB.logger.error(f"Keeping invalid manual plugin {plugin_path.name}: {e}")
        return True
    if not valid:
        DB.logger.error(f"Keeping invalid manual plugin {plugin_path.name}: {message}")
        return True
    return False


def reload_plugins():
    plugins = DB.get_plugins(_type="all", with_data=True)
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
        if plugin["method"] == "manual" and target.is_dir() and invalid_plugin_json(target):
            continue

        # If the target exists, compare its checksum.
        if target.exists():
            with suppress(StopIteration, IndexError, FileNotFoundError):
                plugin_content = create_plugin_tar_gz(target, arc_root=target.name)
                if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                    ignored_plugins.add(target.name)
                    continue
                DB.logger.debug(f"Checksum of {target} has changed, removing it ...")

            if target.is_symlink() or target.is_file():
                with suppress(OSError):
                    target.unlink()
            elif target.is_dir():
                rmtree(target, ignore_errors=True)

        try:
            if plugin["data"]:
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    roots = {
                        Path(name).parts[0] for name in tar.getnames() if Path(name).parts and not Path(name).is_absolute() and ".." not in Path(name).parts
                    }
                    if plugin["method"] == "manual" and any((plugin_path / root).is_dir() and invalid_plugin_json(plugin_path / root) for root in roots):
                        continue
                    for root in roots:
                        if (plugin_path / root).is_symlink():
                            (plugin_path / root).unlink()
                    safe_tar_extractall(tar, plugin_path)
                    known_plugin_ids.update(roots)

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
            DB.logger.debug(format_exc())
            if plugin["method"] != "manual":
                DB.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
        except BaseException as e:
            DB.logger.debug(format_exc())
            DB.logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")

    ret = DB.checked_changes(["ui_plugins"])
    if ret:
        DB.logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

    # Cleanup: Remove plugin folders that exist on the filesystem but are not in the database.
    for plugin_path in (EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH):
        if plugin_path.exists():
            for item in plugin_path.iterdir():
                if item.name not in known_plugin_ids:
                    if item.is_dir() and invalid_plugin_json(item):
                        continue
                    DB.logger.debug(f"Plugin {item.name} not found in database, removing it...")
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
