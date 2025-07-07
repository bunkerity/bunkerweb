from contextlib import suppress
from io import BytesIO
from os import getenv, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from sys import path as sys_path
from tarfile import open as tar_open

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

# Initialize bw_logger module
logger = bwlog(
    title="UI",
    log_file_path="/var/log/bunkerweb/ui.log"
)

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    logger.debug("Debug mode enabled for dependencies module")

from common_utils import bytes_hash  # type: ignore

from app.models.config import Config
from app.models.instance import InstancesUtils
from app.models.ui_data import UIData
from app.models.ui_database import UIDatabase

DB = UIDatabase(logger, log=False)
DATA = UIData(Path(sep, "var", "tmp", "bunkerweb").joinpath("ui_data.json"))

BW_CONFIG = Config(DB, data=DATA)
BW_INSTANCES_UTILS = InstancesUtils(DB)

CORE_PLUGINS_PATH = Path(sep, "usr", "share", "bunkerweb", "core")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")


# Reload and extract plugins from database to filesystem locations.
# Compares checksums to avoid unnecessary extractions and manages plugin
# file permissions and cleanup of orphaned plugin directories.
def reload_plugins():
    if DEBUG_MODE:
        logger.debug("reload_plugins() started")
    
    plugins = DB.get_plugins(_type="all", with_data=True)
    if DEBUG_MODE:
        logger.debug(f"Retrieved {len(plugins)} plugins from database")
    
    # Collect plugin ids from the database for cleanup later.
    known_plugin_ids = {plugin["id"] for plugin in plugins}
    if DEBUG_MODE:
        logger.debug(f"Known plugin IDs: {known_plugin_ids}")

    ignored_plugins = set()
    for plugin in plugins:
        if DEBUG_MODE:
            logger.debug(f"Processing plugin: {plugin['id']} (type: {plugin['type']})")
        
        # Determine the correct extraction path based on the plugin type.
        if plugin["type"] in ("external", "ui"):
            plugin_path = EXTERNAL_PLUGINS_PATH
        elif plugin["type"] == "pro":
            plugin_path = PRO_PLUGINS_PATH
        else:
            if DEBUG_MODE:
                logger.debug(f"Skipping plugin {plugin['id']} with unsupported type: {plugin['type']}")
            continue

        target = plugin_path / plugin["id"]
        if DEBUG_MODE:
            logger.debug(f"Target path for plugin {plugin['id']}: {target}")

        # If the target exists, compare its checksum.
        if target.exists():
            if DEBUG_MODE:
                logger.debug(f"Target {target} exists, checking checksum")
            
            with suppress(StopIteration, IndexError):
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(target, arcname=target.name, recursive=True)
                    plugin_content.seek(0)
                    if bytes_hash(plugin_content, algorithm="sha256") == plugin["checksum"]:
                        if DEBUG_MODE:
                            logger.debug(f"Checksum matches for {plugin['id']}, skipping")
                        ignored_plugins.add(target.name)
                        continue
            
            if DEBUG_MODE:
                logger.debug(f"Checksum of {target} has changed, removing it")
            logger.debug(f"Checksum of {target} has changed, removing it ...")

            if target.is_symlink() or target.is_file():
                with suppress(OSError):
                    target.unlink()
                    if DEBUG_MODE:
                        logger.debug(f"Removed file/symlink: {target}")
            elif target.is_dir():
                rmtree(target, ignore_errors=True)
                if DEBUG_MODE:
                    logger.debug(f"Removed directory: {target}")

        try:
            if plugin["data"]:
                if DEBUG_MODE:
                    logger.debug(f"Extracting plugin data for {plugin['id']}")
                
                with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(plugin_path, filter="fully_trusted")
                    except TypeError:
                        tar.extractall(plugin_path)
                
                if DEBUG_MODE:
                    logger.debug(f"Plugin {plugin['id']} extracted to {plugin_path}")

                plugin_folder = plugin_path / plugin["id"]
                # Add u+x permissions to executable files
                desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
                for subdir, pattern in (
                    ("jobs", "*"),
                    ("bwcli", "*"),
                    ("ui", "*.py"),
                ):
                    if DEBUG_MODE:
                        logger.debug(f"Setting permissions for {plugin_folder.joinpath(subdir)} with pattern {pattern}")
                    
                    for executable_file in plugin_folder.joinpath(subdir).rglob(pattern):
                        if executable_file.stat().st_mode & 0o777 != desired_perms:
                            executable_file.chmod(desired_perms)
                            if DEBUG_MODE:
                                logger.debug(f"Updated permissions for {executable_file}")
            else:
                if DEBUG_MODE:
                    logger.debug(f"No data to extract for plugin {plugin['id']}")
        except OSError as e:
            logger.exception(f"OSError while generating {plugin['type']} plugin \"{plugin['name']}\"")
            if plugin["method"] != "manual":
                logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")
        except BaseException as e:
            logger.exception(f"Exception while generating {plugin['type']} plugin \"{plugin['name']}\"")
            logger.error(f"Error while generating {plugin['type']} plugins \"{plugin['name']}\": {e}")

    if DEBUG_MODE:
        logger.debug(f"Ignored {len(ignored_plugins)} unchanged plugins")

    ret = DB.checked_changes(["ui_plugins"])
    if ret:
        logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

    # Cleanup: Remove plugin folders that exist on the filesystem but are not in the database.
    if DEBUG_MODE:
        logger.debug("Starting cleanup of orphaned plugin directories")
    
    for plugin_path in (EXTERNAL_PLUGINS_PATH, PRO_PLUGINS_PATH):
        if plugin_path.exists():
            if DEBUG_MODE:
                logger.debug(f"Cleaning up plugin path: {plugin_path}")
            
            for item in plugin_path.iterdir():
                if item.name not in known_plugin_ids:
                    if DEBUG_MODE:
                        logger.debug(f"Removing orphaned plugin: {item.name}")
                    
                    logger.debug(f"Plugin {item.name} not found in database, removing it...")
                    with suppress(OSError):
                        if item.is_symlink() or item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            rmtree(item, ignore_errors=True)
    
    if DEBUG_MODE:
        logger.debug("reload_plugins() completed successfully")


# Safely reload plugins with condition checking and worker coordination.
# Loads UI data state and only reloads plugins when necessary, updating
# worker refresh flags and managing reload state persistence.
def safe_reload_plugins(force: bool = False):
    if DEBUG_MODE:
        logger.debug(f"safe_reload_plugins() called with force={force}")
    
    DATA.load_from_file()
    if DEBUG_MODE:
        logger.debug("UI data loaded from file")
    
    force_reload = DATA.get("FORCE_RELOAD_PLUGIN", False)
    is_reloading = DATA.get("IS_RELOADING_PLUGINS", False)
    
    if DEBUG_MODE:
        logger.debug(f"Current state - force_reload: {force_reload}, is_reloading: {is_reloading}")
    
    if force or force_reload or not is_reloading:
        if DEBUG_MODE:
            logger.debug("Starting plugin reload process")
        
        DATA["IS_RELOADING_PLUGINS"] = True
        reload_plugins()
        
        workers = DATA.get("WORKERS", {})
        if DEBUG_MODE:
            logger.debug(f"Updating refresh context for {len(workers)} workers")
        
        for worker_pid in workers:
            DATA["WORKERS"][worker_pid]["refresh_context"] = True
            if DEBUG_MODE:
                logger.debug(f"Set refresh_context=True for worker {worker_pid}")
        
        DATA.update({"FORCE_RELOAD_PLUGIN": False, "IS_RELOADING_PLUGINS": False})
        
        if DEBUG_MODE:
            logger.debug("Plugin reload completed and state updated")
    else:
        if DEBUG_MODE:
            logger.debug("Plugin reload skipped - already in progress")
