#!/usr/bin/env python3

# BunkerWeb Scheduler - Main execution module
# Handles job scheduling, configuration management, and instance monitoring
# for the BunkerWeb web application firewall

from argparse import ArgumentParser
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from json import load as json_load
from logging import Logger
from os import _exit, environ, getenv, getpid, sep
from os.path import join
from pathlib import Path
from shutil import copy, rmtree, copytree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import TarFile, open as tar_open
from threading import Event, Lock, Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Union

# Set up BunkerWeb path and add required dependencies to Python path
BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")

for deps_path in [BUNKERWEB_PATH.joinpath(*paths).as_posix() for paths in (
    ("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from schedule import every as schedule_every, run_pending

from common_utils import (
    bytes_hash, dict_to_frozenset, handle_docker_secrets
)  # type: ignore
from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler
from jobs import Job  # type: ignore
from API import API  # type: ignore

from ApiCaller import ApiCaller  # type: ignore


# Log debug messages only when LOG_LEVEL environment variable is set to
# "debug"
def debug_log(logger, message):
    if getenv("LOG_LEVEL") == "debug":
        logger.debug(f"[DEBUG] {message}")


# Initialize logging as early as possible
LOGGER = setup_logger(
    "Scheduler", 
    getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO"))
)

# Initialize healthcheck logger
HEALTHCHECK_LOGGER = setup_logger(
    "Scheduler.Healthcheck", 
    getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO"))
)

debug_log(LOGGER, "Logger initialized with debug level")

# Global synchronization events and threading primitives
APPLYING_CHANGES = Event()  # Prevents concurrent configuration changes
BACKING_UP_FAILOVER = Event()  # Prevents concurrent failover backups

# Main scheduler control variables
RUN = True  # Controls main scheduler loop
SCHEDULER: Optional[JobScheduler] = None  # Main scheduler instance
SCHEDULER_LOCK = Lock()  # Protects scheduler API list modifications

# Initialize core directory paths for BunkerWeb configuration
CACHE_PATH = Path(sep, "var", "cache", "bunkerweb")
CACHE_PATH.mkdir(parents=True, exist_ok=True)
debug_log(LOGGER, f"Cache directory initialized: {CACHE_PATH}")

CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
CUSTOM_CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
debug_log(LOGGER, f"Custom configs directory initialized: {CUSTOM_CONFIGS_PATH}")

# Define all supported custom configuration directory types
CUSTOM_CONFIGS_DIRS = (
    "http",
    "stream",
    "server-http",
    "server-stream",
    "default-server-http",
    "default-server-stream",
    "modsec",
    "modsec-crs",
    "crs-plugins-before",
    "crs-plugins-after",
)

# Create all custom config subdirectories
for custom_config_dir in CUSTOM_CONFIGS_DIRS:
    dir_path = CUSTOM_CONFIGS_PATH.joinpath(custom_config_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    debug_log(LOGGER, f"Created custom config directory: {dir_path}")

# Nginx configuration paths
CONFIG_PATH = Path(sep, "etc", "nginx")
NGINX_VARIABLES_PATH = CONFIG_PATH.joinpath("variables.env")

# External and Pro plugins directories
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)
debug_log(LOGGER, f"External plugins directory initialized: {EXTERNAL_PLUGINS_PATH}")

PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)
debug_log(LOGGER, f"Pro plugins directory initialized: {PRO_PLUGINS_PATH}")

# Temporary files and working directories
TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")
TMP_PATH.mkdir(parents=True, exist_ok=True)
NGINX_TMP_VARIABLES_PATH = TMP_PATH.joinpath("variables.env")

FAILOVER_PATH = TMP_PATH.joinpath("failover")
FAILOVER_PATH.mkdir(parents=True, exist_ok=True)
debug_log(LOGGER, f"Failover directory initialized: {FAILOVER_PATH}")

# Health check and status files
HEALTHY_PATH = TMP_PATH.joinpath("scheduler.healthy")
DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")

# Parse and validate healthcheck interval configuration
HEALTHCHECK_INTERVAL = getenv("HEALTHCHECK_INTERVAL", "30")

if not HEALTHCHECK_INTERVAL.isdigit():
    LOGGER.error("HEALTHCHECK_INTERVAL must be an integer, defaulting to 30")
    HEALTHCHECK_INTERVAL = 30

HEALTHCHECK_INTERVAL = int(HEALTHCHECK_INTERVAL)
HEALTHCHECK_EVENT = Event()  # Prevents concurrent healthcheck runs

debug_log(LOGGER, f"Healthcheck interval set to: {HEALTHCHECK_INTERVAL} seconds")

# Parse and validate reload minimum timeout configuration
RELOAD_MIN_TIMEOUT = getenv("RELOAD_MIN_TIMEOUT", "5")

if not RELOAD_MIN_TIMEOUT.isdigit():
    LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
    RELOAD_MIN_TIMEOUT = 5

RELOAD_MIN_TIMEOUT = int(RELOAD_MIN_TIMEOUT)
debug_log(LOGGER, f"Reload minimum timeout set to: {RELOAD_MIN_TIMEOUT} seconds")

# Parse configuration testing toggle
DISABLE_CONFIGURATION_TESTING = (
    getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes"
)

if DISABLE_CONFIGURATION_TESTING:
    LOGGER.warning(
        "Configuration testing is disabled, changes will be applied "
        "without testing (we hope you know what you're doing) ..."
    )
    debug_log(LOGGER, "Configuration testing disabled via environment variable")

# Parse fail sending config ignore toggle
IGNORE_FAIL_SENDING_CONFIG = (
    getenv("IGNORE_FAIL_SENDING_CONFIG", "no").lower() == "yes"
)

if IGNORE_FAIL_SENDING_CONFIG:
    LOGGER.warning("Ignoring fail sending config to some BunkerWeb instances ...")
    debug_log(LOGGER, "Fail sending config errors will be ignored")

# Parse regex check ignore toggle
IGNORE_REGEX_CHECK = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"

if IGNORE_REGEX_CHECK:
    LOGGER.warning(
        "Ignoring regex check for settings "
        "(we hope you know what you're doing) ..."
    )
    debug_log(LOGGER, "Regex validation for settings disabled")


# Signal handler for graceful shutdown (SIGINT, SIGTERM)
# Waits for ongoing changes to complete before stopping
def handle_stop(signum, frame):
    debug_log(LOGGER, f"Received signal {signum}, initiating shutdown")
    
    current_time = datetime.now().astimezone()
    # Wait up to 30 seconds for changes to complete
    while (APPLYING_CHANGES.is_set() and 
           (datetime.now().astimezone() - current_time).seconds < 30):
        LOGGER.warning("Waiting for the changes to be applied before stopping ...")
        sleep(1)

    if APPLYING_CHANGES.is_set():
        LOGGER.warning(
            "Timeout reached, stopping without waiting for the "
            "changes to be applied ..."
        )

    if SCHEDULER is not None:
        debug_log(LOGGER, "Clearing scheduler jobs before shutdown")
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Signal handler for configuration reload (SIGHUP)
# Saves current configuration to database without restarting scheduler
def handle_reload(signum, frame):
    debug_log(LOGGER, f"Received reload signal {signum}")
    
    try:
        if SCHEDULER is not None and RUN:
            debug_log(LOGGER, "Scheduler is running, processing reload request")
            
            if SCHEDULER.db.readonly:
                LOGGER.warning(
                    "The database is read-only, no need to save the changes "
                    "in the configuration as they will not be saved"
                )
                return

            debug_log(LOGGER, "Running config saver for reload")
            
            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    "--variables",
                    join(sep, "etc", "bunkerweb", "variables.env"),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.error(
                    "Config saver failed, configuration will not work "
                    "as expected..."
                )
            else:
                debug_log(LOGGER, "Config saver completed successfully")
        else:
            LOGGER.warning(
                "Ignored reload operation because scheduler is not running ..."
            )
    except BaseException as e:
        LOGGER.error(f"Exception while reloading scheduler : {e}")
        debug_log(LOGGER, f"Reload exception traceback: {format_exc()}")


signal(SIGHUP, handle_reload)


# Clean shutdown function - removes PID file and health check file
# Called with exit status code to terminate the scheduler process
def stop(status):
    debug_log(LOGGER, f"Stopping scheduler with status {status}")
    
    pid_file = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
    pid_file.unlink(missing_ok=True)
    debug_log(LOGGER, f"Removed PID file: {pid_file}")
    
    HEALTHY_PATH.unlink(missing_ok=True)
    debug_log(LOGGER, f"Removed health file: {HEALTHY_PATH}")
    
    _exit(status)


# Send files or directories to BunkerWeb instances via their API endpoints
# Handles both single API caller and broadcast to all reachable instances
# Updates instance status in database and manages reachable instances list
def send_file_to_bunkerweb(
    file_path: Path, 
    endpoint: str, 
    logger: Logger = LOGGER, 
    *, 
    api_caller: Optional[ApiCaller] = None
):
    assert SCHEDULER is not None, "SCHEDULER is not defined"
    
    debug_log(
        logger, 
        f"Preparing to send {file_path} to endpoint {endpoint}"
    )
    debug_log(
        logger,
        f"File exists: {file_path.exists()}, "
        f"File size: {file_path.stat().st_size if file_path.exists() else 'N/A'}"
    )
    
    logger.info(
        f"Sending {file_path} to "
        f"{'specific' if api_caller else 'all reachable'} BunkerWeb instances ..."
    )
    
    # Send files using either specific API caller or scheduler's API list
    success, responses = (api_caller or SCHEDULER).send_files(
        file_path.as_posix(), endpoint, response=True
    )
    fails = []

    debug_log(logger, f"Send files result: success={success}, responses={responses}")

    # Process responses and update instance status if not ignoring failures
    if not IGNORE_FAIL_SENDING_CONFIG:
        for db_instance in SCHEDULER.db.get_instances():
            debug_log(logger, f"Processing response for instance: {db_instance['hostname']}")
            
            index = -1
            # Find matching API in scheduler's list
            with SCHEDULER_LOCK:
                for i, api in enumerate(SCHEDULER.apis):
                    if api.endpoint == (
                        f"http://{db_instance['hostname']}:"
                        f"{db_instance['port']}/"
                    ):
                        index = i
                        break

            # Extract status from response
            status = responses.get(
                db_instance["hostname"], {"status": "down"}
            ).get("status", "down")

            debug_log(
                logger,
                f"Instance {db_instance['hostname']} status: {status}, "
                f"API index: {index}"
            )

            # Update instance status in database
            ret = SCHEDULER.db.update_instance(
                db_instance["hostname"], 
                "up" if status == "success" else "down"
            )
            if ret:
                logger.error(
                    f"Couldn't update instance {db_instance['hostname']} "
                    f"status to down in the database: {ret}"
                )

            # Manage reachable instances list based on success/failure
            with SCHEDULER_LOCK:
                if status == "success":
                    success = True
                    # Add instance to reachable list if not already present
                    if index == -1:
                        debug_log(
                            logger,
                            f"Adding {db_instance['hostname']}:"
                            f"{db_instance['port']} to the list of "
                            f"reachable instances"
                        )
                        SCHEDULER.apis.append(
                            API(
                                f"http://{db_instance['hostname']}:"
                                f"{db_instance['port']}", 
                                db_instance["server_name"]
                            )
                        )
                elif index != -1:
                    # Remove failed instance from reachable list
                    fails.append(
                        f"{db_instance['hostname']}:{db_instance['port']}"
                    )
                    debug_log(
                        logger,
                        f"Removing {db_instance['hostname']}:"
                        f"{db_instance['port']} from the list of "
                        f"reachable instances"
                    )
                    del SCHEDULER.apis[index]

    # Log final results
    if not success:
        logger.error(f"Error while sending {file_path} to BunkerWeb instances")
    elif not fails:
        logger.info(
            f"Successfully sent {file_path} folder to reachable "
            f"BunkerWeb instances"
        )
    elif not IGNORE_FAIL_SENDING_CONFIG:
        logger.warning(
            f"Error while sending {file_path} to some BunkerWeb instances, "
            f"removing them from the list of reachable instances: "
            f"{', '.join(fails)}"
        )

    debug_log(logger, f"File send operation completed for {file_path}")


# Generate custom configuration files from database entries
# Removes old config files and creates new ones with proper permissions
# Optionally sends updated configs to BunkerWeb instances
def generate_custom_configs(
    configs: Optional[List[Dict[str, Any]]] = None, 
    *, 
    original_path: Union[Path, str] = CUSTOM_CONFIGS_PATH, 
    send: bool = True
):
    # Convert to Path object immediately to ensure type safety
    config_path: Path = Path(original_path)

    debug_log(LOGGER, f"Generating custom configs at {config_path}")

    # Remove old custom configs files
    LOGGER.info("Removing old custom configs files ...")
    removed_count = 0
    if config_path.is_dir():
        for file in config_path.glob("*/*"):
            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
                    removed_count += 1
            elif file.is_dir():
                rmtree(file, ignore_errors=True)
                removed_count += 1
    
    debug_log(LOGGER, f"Removed {removed_count} old custom config files/directories")

    # Get configs from database if not provided
    if configs is None:
        assert SCHEDULER is not None
        configs = SCHEDULER.db.get_custom_configs()
        config_count = len(configs) if configs is not None else 0
        debug_log(LOGGER, f"Retrieved {config_count} custom configs from database")

    generated_count = 0
    if configs:
        LOGGER.info("Generating new custom configs ...")
        config_path.mkdir(parents=True, exist_ok=True)
        
        for custom_config in configs:
            debug_log(
                LOGGER,
                f"Processing custom config: {custom_config['name']} "
                f"for service: {custom_config.get('service_id', 'global')}"
            )
            
            try:
                if custom_config["data"]:
                    # Build file path based on config type and service
                    tmp_path = config_path.joinpath(
                        custom_config["type"].replace("_", "-"),
                        custom_config["service_id"] or "",
                        f"{Path(custom_config['name']).stem}.conf",
                    )
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write config data to file
                    tmp_path.write_bytes(custom_config["data"])
                    
                    # Set proper file permissions (0o640)
                    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
                    if tmp_path.stat().st_mode & 0o777 != desired_perms:
                        tmp_path.chmod(desired_perms)
                    
                    generated_count += 1
                    debug_log(LOGGER, f"Generated custom config: {tmp_path}")
            except OSError as e:
                debug_log(LOGGER, format_exc())
                if custom_config["method"] != "manual":
                    LOGGER.error(
                        f"Error while generating custom configs "
                        f"\"{custom_config['name']}\""
                        f"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: "
                        f"{e}"
                    )
            except BaseException as e:
                debug_log(LOGGER, format_exc())
                LOGGER.error(
                    f"Error while generating custom configs "
                    f"\"{custom_config['name']}\""
                    f"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: "
                    f"{e}"
                )

    debug_log(LOGGER, f"Generated {generated_count} custom config files")

    # Send configs to BunkerWeb instances if requested
    if send and SCHEDULER and SCHEDULER.apis:
        debug_log(LOGGER, "Sending custom configs to BunkerWeb instances")
        send_file_to_bunkerweb(config_path, "/custom_configs")


# Generate external or pro plugin files from database entries
# Extracts plugin tar.gz files and sets proper permissions on executables
# Checks plugin checksums to avoid unnecessary regeneration
def generate_external_plugins(
    original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH, 
    *, 
    send: bool = True
):
    # Convert to Path object immediately to ensure type safety
    plugins_path: Path = Path(original_path)
    pro = plugins_path.as_posix().endswith("/pro/plugins")

    debug_log(
        LOGGER,
        f"Generating {'pro ' if pro else ''}external plugins "
        f"at {plugins_path}"
    )

    assert SCHEDULER is not None
    plugins = SCHEDULER.db.get_plugins(
        _type="pro" if pro else "external", with_data=True
    )
    assert plugins is not None, "Couldn't get plugins from database"

    plugin_count = len(plugins) if plugins is not None else 0
    debug_log(
        LOGGER,
        f"Retrieved {plugin_count} {'pro ' if pro else ''}external "
        f"plugins from database"
    )

    # Remove old external/pro plugins files but preserve unchanged ones
    LOGGER.info(
        f"Removing old/changed {'pro ' if pro else ''}external plugins files ..."
    )
    ignored_plugins = set()
    removed_count = 0
    
    if plugins_path.is_dir():
        for file in plugins_path.glob("*"):
            # Check if plugin matches database checksum to avoid regeneration
            with suppress(StopIteration, IndexError):
                index = next(
                    i for i, plugin in enumerate(plugins) 
                    if plugin["id"] == file.name
                )

                # Calculate current plugin checksum
                with BytesIO() as plugin_content:
                    with tar_open(
                        fileobj=plugin_content, mode="w:gz", compresslevel=9
                    ) as tar:
                        tar.add(file, arcname=file.name, recursive=True)
                    plugin_content.seek(0, 0)
                    current_checksum = bytes_hash(plugin_content, algorithm="sha256")
                    
                if current_checksum == plugins[index]["checksum"]:
                    ignored_plugins.add(file.name)
                    debug_log(LOGGER, f"Plugin {file.name} unchanged, keeping existing version")
                    continue
                    
                debug_log(
                    LOGGER,
                    f"Checksum of {file} has changed, removing it ..."
                )

            # Remove outdated or changed plugin files
            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
                    removed_count += 1
            elif file.is_dir():
                rmtree(file, ignore_errors=True)
                removed_count += 1

    debug_log(LOGGER, f"Removed {removed_count} old/changed plugin files")

    generated_count = 0
    if plugins:
        LOGGER.info(
            f"Generating new {'pro ' if pro else ''}external plugins ..."
        )
        plugins_path.mkdir(parents=True, exist_ok=True)
        
        for plugin in plugins:
            if plugin["id"] in ignored_plugins:
                debug_log(LOGGER, f"Skipping unchanged plugin: {plugin['id']}")
                continue

            debug_log(
                LOGGER,
                f"Processing plugin: {plugin['id']} "
                f"(name: {plugin.get('name', 'unknown')})"
            )

            try:
                if plugin["data"]:
                    # Extract plugin tar.gz archive
                    with tar_open(
                        fileobj=BytesIO(plugin["data"]), mode="r:gz"
                    ) as tar:
                        try:
                            tar.extractall(plugins_path, filter="fully_trusted")
                        except TypeError:
                            # Fallback for older Python versions
                            tar.extractall(plugins_path)

                    # Set executable permissions on plugin script files
                    plugin_path = plugins_path.joinpath(plugin["id"])
                    desired_perms = (
                        S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP
                    )  # 0o750
                    
                    # Apply permissions to specific plugin subdirectories
                    for subdir, pattern in (
                        ("jobs", "*"),
                        ("bwcli", "*"),
                        ("ui", "*.py"),
                    ):
                        subdir_path = plugin_path.joinpath(subdir)
                        if subdir_path.exists():
                            for executable_file in subdir_path.rglob(pattern):
                                if (executable_file.stat().st_mode & 0o777 != 
                                    desired_perms):
                                    executable_file.chmod(desired_perms)
                                    debug_log(LOGGER, f"Set permissions on: {executable_file}")
                    
                    generated_count += 1
                    debug_log(LOGGER, f"Generated plugin: {plugin_path}")
            except OSError as e:
                debug_log(LOGGER, format_exc())
                if plugin["method"] != "manual":
                    LOGGER.error(
                        f"Error while generating {'pro ' if pro else ''}"
                        f"external plugins \"{plugin['name']}\": {e}"
                    )
            except BaseException as e:
                debug_log(LOGGER, format_exc())
                LOGGER.error(
                    f"Error while generating {'pro ' if pro else ''}"
                    f"external plugins \"{plugin['name']}\": {e}"
                )

    debug_log(LOGGER, f"Generated {generated_count} new plugin installations")

    # Send plugins to BunkerWeb instances if requested
    if send and SCHEDULER and SCHEDULER.apis:
        LOGGER.info(f"Sending {'pro ' if pro else ''}external plugins to BunkerWeb")
        endpoint = ("/pro_plugins" if plugins_path.as_posix().endswith("/pro/plugins") 
                   else "/plugins")
        debug_log(LOGGER, f"Using endpoint: {endpoint}")
        send_file_to_bunkerweb(plugins_path, endpoint)


# Generate cache files from database entries
# Restores job cache files including both individual files and tar.gz archives
# Removes obsolete cache files and sets proper permissions
def generate_caches():
    assert SCHEDULER is not None

    debug_log(LOGGER, "Generating cache files from database")

    job_cache_files = SCHEDULER.db.get_jobs_cache_files()
    plugin_cache_files = set()
    ignored_dirs = set()

    debug_log(LOGGER, f"Retrieved {len(job_cache_files)} cache files from database")

    restored_files = 0
    restored_dirs = 0
    
    for job_cache_file in job_cache_files:
        # Build cache file path
        job_path = Path(sep, "var", "cache", "bunkerweb", 
                       job_cache_file["plugin_id"])
        cache_path = job_path.joinpath(
            job_cache_file["service_id"] or "", 
            job_cache_file["file_name"]
        )
        plugin_cache_files.add(cache_path)

        debug_log(
            LOGGER,
            f"Processing cache file: {job_cache_file['file_name']} "
            f"for plugin: {job_cache_file['plugin_id']}"
        )

        try:
            # Handle tar.gz archive extraction
            if job_cache_file["file_name"].endswith(".tgz"):
                extract_path = cache_path.parent
                # Handle folder-prefixed archives
                if job_cache_file["file_name"].startswith("folder:"):
                    extract_path = Path(
                        job_cache_file["file_name"].split("folder:", 1)[1]
                        .rsplit(".tgz", 1)[0]
                    )
                
                ignored_dirs.add(extract_path.as_posix())
                rmtree(extract_path, ignore_errors=True)
                extract_path.mkdir(parents=True, exist_ok=True)
                
                # Extract tar.gz archive
                with tar_open(
                    fileobj=BytesIO(job_cache_file["data"]), mode="r:gz"
                ) as tar:
                    assert isinstance(tar, TarFile)
                    try:
                        try:
                            tar.extractall(extract_path, filter="fully_trusted")
                        except TypeError:
                            # Fallback for older Python versions
                            tar.extractall(extract_path)
                    except Exception as e:
                        LOGGER.error(f"Error extracting tar file: {e}")
                        debug_log(LOGGER, f"Extraction error details: {format_exc()}")
                
                restored_dirs += 1
                debug_log(LOGGER, f"Restored cache directory {extract_path}")
                continue
                
            # Handle regular cache files
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(job_cache_file["data"])
            
            # Set proper file permissions (0o640)
            desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
            if cache_path.stat().st_mode & 0o777 != desired_perms:
                cache_path.chmod(desired_perms)
                
            restored_files += 1
            debug_log(
                LOGGER,
                f"Restored cache file {job_cache_file['file_name']}"
            )
        except BaseException as e:
            LOGGER.error(
                f"Exception while restoring cache file "
                f"{job_cache_file['file_name']} :\n{e}"
            )
            debug_log(LOGGER, f"Cache restoration error: {format_exc()}")

    debug_log(
        LOGGER,
        f"Cache restoration complete: {restored_files} files, "
        f"{restored_dirs} directories"
    )

    # Clean up obsolete cache files that are no longer in database
    removed_files = 0
    if job_path.is_dir():
        for resource_path in list(job_path.rglob("*")):
            # Skip directories that were just extracted
            if resource_path.as_posix().startswith(tuple(ignored_dirs)):
                continue

            debug_log(LOGGER, f"Checking if {resource_path} should be removed")
                
            # Remove files not in current cache file list
            if (resource_path not in plugin_cache_files and 
                resource_path.is_file()):
                debug_log(LOGGER, f"Removing non-cached file {resource_path}")
                resource_path.unlink(missing_ok=True)
                removed_files += 1
                
                # Clean up empty parent directories
                if (resource_path.parent.is_dir() and 
                    not list(resource_path.parent.iterdir())):
                    debug_log(
                        LOGGER,
                        f"Removing empty directory {resource_path.parent}"
                    )
                    rmtree(resource_path.parent, ignore_errors=True)
                    if resource_path.parent == job_path:
                        break
                continue
            elif (resource_path.is_dir() and 
                  not list(resource_path.iterdir())):
                debug_log(LOGGER, f"Removing empty directory {resource_path}")
                rmtree(resource_path, ignore_errors=True)
                continue

            # Set proper permissions on remaining files/directories (0o750)
            desired_perms = (
                S_IRUSR | S_IWUSR | S_IRGRP | S_IXUSR | S_IXGRP
            )  # 0o750
            if resource_path.stat().st_mode & 0o777 != desired_perms:
                resource_path.chmod(desired_perms)

    debug_log(LOGGER, f"Cache cleanup complete: removed {removed_files} obsolete files")


# Generate nginx configuration files using the BunkerWeb config generator
# Runs the main.py generator script and copies variables file to temp location
# Returns True on success, False on failure
def generate_configs(logger: Logger = LOGGER) -> bool:
    debug_log(logger, "Starting config generation")
    
    # Run the BunkerWeb configuration generator
    generator_cmd = [
        BUNKERWEB_PATH.joinpath("gen", "main.py").as_posix(),
        "--settings",
        BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
        "--templates",
        BUNKERWEB_PATH.joinpath("confs").as_posix(),
        "--output",
        CONFIG_PATH.as_posix(),
    ]
    
    debug_log(logger, f"Running config generator: {' '.join(generator_cmd)}")
    
    proc = subprocess_run(
        generator_cmd,
        stdin=DEVNULL,
        stderr=STDOUT,
        check=False,
    )

    if proc.returncode != 0:
        logger.error(
            "Config generator failed, configuration will not work "
            "as expected..."
        )
        debug_log(logger, f"Config generator exit code: {proc.returncode}")
        return False

    # Copy nginx variables file to temporary location
    debug_log(
        logger,
        f"Copying {NGINX_VARIABLES_PATH} to {NGINX_TMP_VARIABLES_PATH}"
    )
    
    try:
        copy(NGINX_VARIABLES_PATH.as_posix(), NGINX_TMP_VARIABLES_PATH.as_posix())
    except Exception as e:
        logger.error(f"Failed to copy variables file: {e}")
        debug_log(logger, f"Variables copy error: {format_exc()}")
        return False
    
    debug_log(logger, "Config generation completed successfully")
    return True


# Perform health checks on BunkerWeb instances and send configs to loading
# instances. Checks instance health via API, updates database status, and
# manages reachable instances list. Automatically sends full configuration to
# instances in "loading" state
def healthcheck_job():
    if HEALTHCHECK_EVENT.is_set():
        HEALTHCHECK_LOGGER.warning(
            "Healthcheck job is already running, skipping execution ..."
        )
        return

    try:
        assert SCHEDULER is not None
    except AssertionError:
        debug_log(HEALTHCHECK_LOGGER, "Scheduler not initialized, skipping healthcheck")
        return

    debug_log(HEALTHCHECK_LOGGER, "Starting healthcheck job")

    HEALTHCHECK_EVENT.set()

    # Skip healthcheck if configuration changes are being applied
    if APPLYING_CHANGES.is_set():
        debug_log(HEALTHCHECK_LOGGER, "Changes being applied, skipping healthcheck")
        HEALTHCHECK_EVENT.clear()
        return

    env = None
    checked_instances = 0
    healthy_instances = 0
    loading_instances = 0

    # Check health of each registered instance
    for db_instance in SCHEDULER.db.get_instances():
        checked_instances += 1
        instance_endpoint = f"http://{db_instance['hostname']}:{db_instance['port']}"
        bw_instance = API(instance_endpoint, db_instance["server_name"])
        
        debug_log(HEALTHCHECK_LOGGER, f"Checking health of instance: {instance_endpoint}")
        
        try:
            # Send health check request to instance
            try:
                sent, err, status, resp = bw_instance.request("GET", "health")
            except BaseException as e:
                err = str(e)
                sent = False
                status = 500
                resp = {"status": "down", "msg": err}
                debug_log(
                    HEALTHCHECK_LOGGER,
                    f"Health check request failed for {instance_endpoint}: {e}"
                )

            debug_log(HEALTHCHECK_LOGGER, f"Health response from {instance_endpoint}: {resp}")

            success = True
            # Validate health check response
            if not sent:
                HEALTHCHECK_LOGGER.warning(
                    f"Can't send API request to {bw_instance.endpoint}health : "
                    f"{err}, healthcheck will be retried in "
                    f"{HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False
            elif status != 200:
                HEALTHCHECK_LOGGER.warning(
                    f"Error while sending API request to "
                    f"{bw_instance.endpoint}health : status = {resp['status']}, "
                    f"msg = {resp['msg']}, healthcheck will be retried in "
                    f"{HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False

            # Handle unhealthy instances
            if not success:
                ret = SCHEDULER.db.update_instance(
                    db_instance["hostname"], "down"
                )
                if ret:
                    HEALTHCHECK_LOGGER.error(
                        f"Couldn't update instance {bw_instance.endpoint} "
                        f"status to down in the database: {ret}"
                    )

                # Remove from reachable instances list
                for i, api in enumerate(SCHEDULER.apis):
                    if api.endpoint == bw_instance.endpoint:
                        debug_log(
                            HEALTHCHECK_LOGGER,
                            f"Removing {bw_instance.endpoint} from the "
                            f"list of reachable instances"
                        )
                        del SCHEDULER.apis[i]
                        break
                continue

            # Handle instances in loading state
            if resp["msg"] == "loading":
                loading_instances += 1
                
                # Skip failover instances during loading
                if db_instance["status"] == "failover":
                    HEALTHCHECK_LOGGER.warning(
                        f"Instance {db_instance['hostname']} is in failover "
                        f"mode, skipping sending config ..."
                    )
                    continue

                HEALTHCHECK_LOGGER.info(
                    f"Instance {bw_instance.endpoint} is loading, "
                    f"sending config ..."
                )
                
                # Create API caller for this specific instance
                api_caller = ApiCaller([bw_instance])

                # Get environment configuration if not already loaded
                if env is None:
                    debug_log(HEALTHCHECK_LOGGER, "Loading environment configuration")
                    env = SCHEDULER.db.get_config()
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

                # Generate fresh nginx configuration
                debug_log(HEALTHCHECK_LOGGER, "Generating configs for loading instance")
                generate_configs(HEALTHCHECK_LOGGER)

                # Send all configuration components to loading instance
                config_threads = [
                    Thread(
                        target=send_file_to_bunkerweb,
                        args=(
                            CUSTOM_CONFIGS_PATH,
                            "/custom_configs",
                            HEALTHCHECK_LOGGER,
                        ),
                        kwargs={"api_caller": api_caller},
                    ),
                    Thread(
                        target=send_file_to_bunkerweb,
                        args=(
                            EXTERNAL_PLUGINS_PATH,
                            "/plugins",
                            HEALTHCHECK_LOGGER,
                        ),
                        kwargs={"api_caller": api_caller},
                    ),
                    Thread(
                        target=send_file_to_bunkerweb,
                        args=(
                            PRO_PLUGINS_PATH,
                            "/pro_plugins",
                            HEALTHCHECK_LOGGER,
                        ),
                        kwargs={"api_caller": api_caller},
                    ),
                    Thread(
                        target=send_file_to_bunkerweb,
                        args=(
                            CONFIG_PATH,
                            "/confs",
                            HEALTHCHECK_LOGGER,
                        ),
                        kwargs={"api_caller": api_caller},
                    ),
                    Thread(
                        target=send_file_to_bunkerweb,
                        args=(
                            CACHE_PATH,
                            "/cache",
                            HEALTHCHECK_LOGGER,
                        ),
                        kwargs={"api_caller": api_caller},
                    ),
                ]
                
                debug_log(HEALTHCHECK_LOGGER, f"Starting {len(config_threads)} config send threads")
                
                # Start all config sending threads
                for thread in config_threads:
                    thread.start()

                # Wait for all config sending to complete
                for thread in config_threads:
                    thread.join()

                debug_log(HEALTHCHECK_LOGGER, "All config threads completed, triggering reload")

                # Trigger instance reload with appropriate timeout
                reload_timeout = max(
                    RELOAD_MIN_TIMEOUT, 
                    3 * len(env.get("SERVER_NAME", "www.example.com").split(" "))
                )
                
                reload_success = api_caller.send_to_apis(
                    "POST",
                    f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}",
                    timeout=reload_timeout,
                )[0]
                
                if not reload_success:
                    HEALTHCHECK_LOGGER.error(
                        f"Error while reloading instance {bw_instance.endpoint}"
                    )
                    # Mark instance as still loading if reload failed
                    ret = SCHEDULER.db.update_instance(
                        db_instance["hostname"], "loading"
                    )
                    if ret:
                        HEALTHCHECK_LOGGER.error(
                            f"Couldn't update instance {bw_instance.endpoint} "
                            f"status to loading in the database: {ret}"
                        )
                    continue
                
                HEALTHCHECK_LOGGER.info(
                    f"Successfully reloaded instance {bw_instance.endpoint}"
                )

            # Mark instance as healthy and add to reachable list
            healthy_instances += 1
            ret = SCHEDULER.db.update_instance(db_instance["hostname"], "up")
            if ret:
                HEALTHCHECK_LOGGER.error(
                    f"Couldn't update instance {bw_instance.endpoint} "
                    f"status to up in the database: {ret}"
                )

            # Ensure instance is in reachable APIs list
            found = False
            for api in SCHEDULER.apis:
                if api.endpoint == bw_instance.endpoint:
                    found = True
                    break
            if not found:
                debug_log(
                    HEALTHCHECK_LOGGER,
                    f"Adding {bw_instance.endpoint} to the list of "
                    f"reachable instances"
                )
                SCHEDULER.apis.append(bw_instance)
                
        except BaseException as e:
            HEALTHCHECK_LOGGER.error(
                f"Exception while checking instance {bw_instance.endpoint}: {e}"
            )
            debug_log(HEALTHCHECK_LOGGER, f"Healthcheck exception: {format_exc()}")
            
            # Remove failed instance from reachable list
            for i, api in enumerate(SCHEDULER.apis):
                if api.endpoint == bw_instance.endpoint:
                    debug_log(
                        HEALTHCHECK_LOGGER,
                        f"Removing {bw_instance.endpoint} from the list "
                        f"of reachable instances"
                    )
                    del SCHEDULER.apis[i]
                    break

    debug_log(
        HEALTHCHECK_LOGGER,
        f"Healthcheck completed: {checked_instances} checked, "
        f"{healthy_instances} healthy, {loading_instances} loading"
    )

    HEALTHCHECK_EVENT.clear()


# Create a backup of the current configuration for failover purposes
# Copies config, custom_configs, and cache directories to failover location
# Compresses the backup using job caching system for later restoration
def backup_failover():
    debug_log(LOGGER, "Starting failover backup")
    
    BACKING_UP_FAILOVER.set()
    backup_success = True
    
    try:
        # Clean up old failover backup
        rmtree(FAILOVER_PATH, ignore_errors=True)
        FAILOVER_PATH.mkdir(parents=True, exist_ok=True)
        
        debug_log(LOGGER, f"Cleaned and recreated failover directory: {FAILOVER_PATH}")

        # Define source and destination pairs for backup
        backup_items = [
            (CONFIG_PATH, "config"),
            (CUSTOM_CONFIGS_PATH, "custom_configs"),
            (CACHE_PATH, "cache"),
        ]
        
        copied_items = 0
        for src, dst_name in backup_items:
            try:
                dst_path = FAILOVER_PATH / dst_name
                debug_log(LOGGER, f"Copying {src} to {dst_path}")
                
                copytree(src, dst_path, dirs_exist_ok=True)
                copied_items += 1
                
                debug_log(LOGGER, f"Successfully backed up {src} to failover path")
            except Exception as e:
                LOGGER.error(f"Error copying {src} to failover path: {e}")
                backup_success = False
                debug_log(LOGGER, f"Backup copy error for {src}: {format_exc()}")

        debug_log(LOGGER, f"Copied {copied_items} out of {len(backup_items)} backup items")

        # Cache the failover backup for persistence
        if backup_success:
            debug_log(LOGGER, "Caching failover backup")
            
            success, err = JOB.cache_dir(FAILOVER_PATH, job_name="failover-backup")
            if not success:
                LOGGER.error(f"Error while caching failover backup: {err}")
                backup_success = False
            else:
                debug_log(LOGGER, "Failover backup cached successfully")
        
    except Exception as e:
        LOGGER.error(f"Failed to initialize failover backup: {e}")
        backup_success = False
        debug_log(LOGGER, f"Failover backup initialization error: {format_exc()}")
    finally:
        BACKING_UP_FAILOVER.clear()
        debug_log(LOGGER, f"Failover backup completed: {'success' if backup_success else 'failed'}")


# Main scheduler execution block
# Handles initialization, Docker secrets, database setup, and main scheduler
# loop
if __name__ == "__main__":
    try:
        debug_log(LOGGER, "Starting BunkerWeb Scheduler main execution")
        
        # Handle Docker secrets first
        docker_secrets = handle_docker_secrets()
        if docker_secrets:
            LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")
            debug_log(LOGGER, f"Docker secrets keys: {list(docker_secrets.keys())}")
            # Update environment with secrets
            environ.update(docker_secrets)

        # Check for existing scheduler process to prevent multiple instances
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            LOGGER.error(
                "Scheduler is already running, skipping execution ..."
            )
            existing_pid = pid_path.read_text(encoding="utf-8").strip()
            debug_log(LOGGER, f"Existing PID file contains: {existing_pid}")
            _exit(1)

        # Write current process PID to file
        current_pid = str(getpid())
        pid_path.write_text(current_pid, encoding="utf-8")
        debug_log(LOGGER, f"Created PID file with PID: {current_pid}")

        del pid_path

        # Parse command line arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument(
            "--variables", 
            type=str, 
            help="path to the file containing environment variables"
        )
        args = parser.parse_args()

        debug_log(LOGGER, f"Command line arguments: {args}")

        # Determine variables file path
        tmp_variables_path = (
            Path(args.variables) if args.variables 
            else NGINX_TMP_VARIABLES_PATH
        )

        debug_log(LOGGER, f"Using variables file: {tmp_variables_path}")

        # Load environment variables from dotenv file
        dotenv_env = {}
        if tmp_variables_path.is_file():
            debug_log(LOGGER, f"Loading environment from: {tmp_variables_path}")
            
            with tmp_variables_path.open() as f:
                dotenv_env = dict(
                    line.strip().split("=", 1) for line in f 
                    if (line.strip() and not line.startswith("#") and 
                        "=" in line)
                )
            
            debug_log(LOGGER, f"Loaded {len(dotenv_env)} environment variables from file")
        else:
            debug_log(LOGGER, "No variables file found, using system environment only")

        # Initialize scheduler with database connection
        database_uri = dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None))
        debug_log(LOGGER, f"Database URI source: {'dotenv' if database_uri in dotenv_env.values() else 'environment'}")
        
        SCHEDULER = JobScheduler(
            LOGGER, 
            db=Database(LOGGER, sqlalchemy_string=database_uri)
        )  # type: ignore

        debug_log(LOGGER, "JobScheduler initialized successfully")

        # Initialize job handler
        JOB = Job(LOGGER, __file__, SCHEDULER.db)
        
        debug_log(LOGGER, "Job handler initialized")

        # Set flag to indicate configuration changes are being applied
        APPLYING_CHANGES.set()

        # Handle database read-only mode and save initial configuration
        if SCHEDULER.db.readonly:
            LOGGER.warning(
                "The database is read-only, no need to save the changes "
                "in the configuration as they will not be saved"
            )
            debug_log(LOGGER, "Database is in read-only mode, skipping config save")
        else:
            debug_log(LOGGER, "Running initial config saver")
            
            # Run the initial configuration saver
            config_saver_cmd = [
                BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                "--settings",
                BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                "--first-run",
            ]
            
            # Add variables file if specified
            if args.variables:
                config_saver_cmd.extend(["--variables", tmp_variables_path.as_posix()])
            
            debug_log(LOGGER, f"Config saver command: {' '.join(config_saver_cmd)}")
            
            proc = subprocess_run(
                config_saver_cmd,
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.error(
                    "Config saver failed, configuration will not work "
                    "as expected..."
                )
                debug_log(LOGGER, f"Config saver exit code: {proc.returncode}")
            else:
                debug_log(LOGGER, "Initial config saver completed successfully")

        # Wait for database to be initialized
        ready = False
        db_check_attempts = 0
        while not ready:
            db_check_attempts += 1
            debug_log(LOGGER, f"Database initialization check attempt #{db_check_attempts}")
            
            db_metadata = SCHEDULER.db.get_metadata()
            if (isinstance(db_metadata, str) or 
                not isinstance(db_metadata, dict) or 
                not db_metadata.get("is_initialized", False)):
                LOGGER.warning("Database is not initialized, retrying in 5s ...")
                debug_log(LOGGER, f"Database metadata: {db_metadata}")
                sleep(5)
            else:
                ready = True
                debug_log(LOGGER, "Database is initialized and ready")
                continue

        # Load and setup environment configuration
        env = SCHEDULER.db.get_config()
        env["DATABASE_URI"] = SCHEDULER.db.database_uri
        tz = getenv("TZ")
        if tz:
            env["TZ"] = tz

        debug_log(LOGGER, f"Loaded {len(env)} configuration parameters")

        # Configure scheduler environment with reload timeout
        SCHEDULER.env = env | {"RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)}

        threads = []

        # Initialize API connections to all database instances
        SCHEDULER.apis = []
        for db_instance in SCHEDULER.db.get_instances():
            api_endpoint = f"http://{db_instance['hostname']}:{db_instance['port']}"
            SCHEDULER.apis.append(
                API(api_endpoint, db_instance["server_name"])
            )
            debug_log(LOGGER, f"Added API endpoint: {api_endpoint}")

        debug_log(LOGGER, f"Initialized {len(SCHEDULER.apis)} API connections")

        # Get scheduler first start flag from metadata
        scheduler_first_start = False
        if isinstance(db_metadata, dict):
            scheduler_first_start = db_metadata.get("scheduler_first_start", False)
        debug_log(LOGGER, f"Scheduler first start: {scheduler_first_start}")

        LOGGER.info("Scheduler started ...")

        # Define function to check for changes in custom configuration files
        # Scans filesystem for manually created configs and saves them to
        # database
        def check_configs_changes():
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info("Checking if there are any changes in custom configs ...")
            
            debug_log(LOGGER, f"Scanning custom configs directory: {CUSTOM_CONFIGS_PATH}")
            
            custom_configs = []
            db_configs = SCHEDULER.db.get_custom_configs()
            changes = False
            scanned_files = 0
            
            # Scan all .conf files in custom configs directory
            for file in list(CUSTOM_CONFIGS_PATH.rglob("*.conf")):
                scanned_files += 1
                
                # Validate file path depth
                if len(file.parts) > len(CUSTOM_CONFIGS_PATH.parts) + 3:
                    LOGGER.warning(
                        f"Custom config file {file} is not in the correct path, "
                        f"skipping ..."
                    )
                    continue

                debug_log(LOGGER, f"Processing custom config file: {file}")

                content = file.read_text(encoding="utf-8")
                
                # Determine service ID and config type from file path
                service_id = (
                    file.parent.name 
                    if file.parent.name not in CUSTOM_CONFIGS_DIRS 
                    else None
                )
                config_type = (
                    file.parent.parent.name 
                    if service_id 
                    else file.parent.name
                )

                saving = True
                in_db = False
                from_template = False
                
                # Check if config already exists in database
                for db_conf in db_configs:
                    if (db_conf["service_id"] == service_id and 
                        db_conf["name"] == file.stem):
                        in_db = True
                        if db_conf["template"]:
                            from_template = True
                        break

                # Skip saving if from template or auto-generated
                if (from_template or 
                    (not in_db and content.startswith("# CREATED BY ENV"))):
                    saving = False
                    changes = not from_template

                if saving:
                    custom_configs.append(
                        {
                            "value": content, 
                            "exploded": (service_id, config_type, file.stem)
                        }
                    )
                    debug_log(LOGGER, f"Marked for saving: {file.stem}")

            debug_log(
                LOGGER,
                f"Scanned {scanned_files} files, "
                f"{len(custom_configs)} marked for database save"
            )

            # Check if there are actual changes to save
            changes = (
                changes or 
                {hash(dict_to_frozenset(d)) for d in custom_configs} != 
                {hash(dict_to_frozenset(d)) for d in db_configs}
            )

            # Save changes to database if detected
            if changes:
                debug_log(LOGGER, "Changes detected, saving to database")
                
                try:
                    err = SCHEDULER.db.save_custom_configs(
                        custom_configs, "manual"
                    )
                    if err:
                        LOGGER.error(
                            f"Couldn't save some manually created custom "
                            f"configs to database: {err}"
                        )
                    else:
                        debug_log(LOGGER, "Custom configs saved successfully")
                except BaseException as e:
                    LOGGER.error(
                        f"Error while saving custom configs to database: {e}"
                    )
                    debug_log(LOGGER, f"Save error: {format_exc()}")
            else:
                debug_log(LOGGER, "No changes detected in custom configs")

            # Generate updated custom configs
            generate_custom_configs(SCHEDULER.db.get_custom_configs())

        # Define function to check for changes in external or pro plugin files
        # Scans filesystem for manually added plugins and saves them to
        # database
        def check_plugin_changes(_type: Literal["external", "pro"] = "external"):
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info(
                f"Checking if there are any changes in {_type} plugins ..."
            )
            
            plugin_path = PRO_PLUGINS_PATH if _type == "pro" else EXTERNAL_PLUGINS_PATH
            debug_log(LOGGER, f"Scanning {_type} plugins directory: {plugin_path}")
            
            db_plugins = SCHEDULER.db.get_plugins(_type=_type)
            external_plugins = []
            tmp_external_plugins = []
            scanned_plugins = 0
            
            # Scan for plugin.json files in plugin directories
            for file in plugin_path.glob("*/plugin.json"):
                scanned_plugins += 1
                debug_log(LOGGER, f"Processing plugin config: {file}")
                
                # Create tar.gz archive of entire plugin directory
                with BytesIO() as plugin_content:
                    with tar_open(
                        fileobj=plugin_content, mode="w:gz", compresslevel=9
                    ) as tar:
                        tar.add(
                            file.parent, arcname=file.parent.name, recursive=True
                        )
                    plugin_content.seek(0, 0)

                    # Load plugin metadata
                    try:
                        with file.open("r", encoding="utf-8") as f:
                            plugin_data = json_load(f)
                    except Exception as e:
                        LOGGER.error(f"Failed to parse plugin.json in {file.parent}: {e}")
                        continue

                    # Skip letsencrypt_dns plugin (special handling)
                    if plugin_data["id"] == "letsencrypt_dns":
                        debug_log(LOGGER, "Skipping letsencrypt_dns plugin")
                        continue

                    # Calculate plugin checksum for change detection
                    checksum = bytes_hash(plugin_content, algorithm="sha256")
                    common_data = plugin_data | {
                        "type": _type,
                        "page": file.parent.joinpath("ui").is_dir(),
                        "checksum": checksum,
                    }
                    jobs = common_data.pop("jobs", [])

                    debug_log(
                        LOGGER,
                        f"Plugin {plugin_data['id']} checksum: {checksum[:16]}..."
                    )

                    # Check if plugin already exists with same checksum
                    with suppress(StopIteration, IndexError):
                        index = next(
                            i for i, plugin in enumerate(db_plugins) 
                            if plugin["id"] == common_data["id"]
                        )

                        if (checksum == db_plugins[index]["checksum"] or 
                            db_plugins[index]["method"] != "manual"):
                            debug_log(LOGGER, f"Plugin {plugin_data['id']} unchanged, skipping")
                            continue

                    tmp_external_plugins.append(common_data.copy())

                    # Prepare plugin data for database storage
                    external_plugins.append(
                        common_data
                        | {
                            "method": "manual",
                            "data": plugin_content.getvalue(),
                        }
                        | ({"jobs": jobs} if jobs else {})
                    )
                    debug_log(LOGGER, f"Marked plugin {plugin_data['id']} for database save")

            debug_log(
                LOGGER,
                f"Scanned {scanned_plugins} plugins, "
                f"{len(external_plugins)} marked for database save"
            )

            changes = False
            if tmp_external_plugins:
                # Check if there are actual changes to save
                changes = (
                    {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != 
                    {hash(dict_to_frozenset(d)) for d in db_plugins}
                )

                if changes:
                    debug_log(LOGGER, f"Changes detected in {_type} plugins, saving to database")
                    
                    try:
                        err = SCHEDULER.db.update_external_plugins(
                            external_plugins, _type=_type, delete_missing=True
                        )
                        if err:
                            LOGGER.error(
                                f"Couldn't save some manually added {_type} "
                                f"plugins to database: {err}"
                            )
                        else:
                            debug_log(LOGGER, f"{_type} plugins saved successfully")
                    except BaseException as e:
                        LOGGER.error(
                            f"Error while saving {_type} plugins to database: {e}"
                        )
                        debug_log(LOGGER, f"Plugin save error: {format_exc()}")
                else:
                    debug_log(LOGGER, f"No changes detected in {_type} plugins")
                    # No changes, just send existing plugins to BunkerWeb
                    return send_file_to_bunkerweb(
                        plugin_path, 
                        "/pro_plugins" if _type == "pro" else "/plugins"
                    )

            # Generate updated plugins
            generate_external_plugins(plugin_path)

        # Run initial configuration and plugin checks
        debug_log(LOGGER, "Starting initial configuration and plugin checks")
        
        check_configs_changes()
        threads.extend([
            Thread(target=check_plugin_changes, args=("external",)), 
            Thread(target=check_plugin_changes, args=("pro",))
        ])

        debug_log(LOGGER, f"Starting {len(threads)} plugin check threads")

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        debug_log(LOGGER, "Initial plugin checks completed")

        # Run initial plugin download jobs
        LOGGER.info("Running plugins download jobs ...")
        debug_log(LOGGER, "Running scheduler jobs for misc and pro plugins")
        
        SCHEDULER.run_once(["misc", "pro"])

        # Check if plugins changed during download and regenerate if needed
        db_metadata = SCHEDULER.db.get_metadata()
        if (isinstance(db_metadata, dict) and 
            (db_metadata.get("pro_plugins_changed", False) or 
             db_metadata.get("external_plugins_changed", False))):
            
            debug_log(
                LOGGER,
                f"Plugins changed during download: "
                f"pro={db_metadata.get('pro_plugins_changed', False)}, "
                f"external={db_metadata.get('external_plugins_changed', False)}"
            )
            
            threads.clear()

            if isinstance(db_metadata, dict):
                if db_metadata.get("pro_plugins_changed", False):
                    threads.append(
                        Thread(target=generate_external_plugins, args=(PRO_PLUGINS_PATH,))
                    )
                if db_metadata.get("external_plugins_changed", False):
                    threads.append(Thread(target=generate_external_plugins))

            debug_log(LOGGER, f"Starting {len(threads)} plugin regeneration threads")

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # Save external plugin settings if database is writable
            if SCHEDULER.db.readonly:
                LOGGER.warning(
                    "The database is read-only, no need to look for changes "
                    "in the plugins settings as they will not be saved"
                )
            else:
                LOGGER.info(
                    "Running config saver to save potential ignored "
                    "external plugins settings ..."
                )
                
                config_saver_cmd = [
                    BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                ]
                
                if args.variables:
                    config_saver_cmd.extend(["--variables", tmp_variables_path.as_posix()])
                
                debug_log(LOGGER, f"Plugin settings saver command: {' '.join(config_saver_cmd)}")
                
                proc = subprocess_run(
                    config_saver_cmd,
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )
                if proc.returncode != 0:
                    LOGGER.error(
                        "Config saver failed, configuration will not work "
                        "as expected..."
                    )
                else:
                    debug_log(LOGGER, "Plugin settings saver completed successfully")

            # Update scheduler jobs with new plugin configurations
            debug_log(LOGGER, "Updating scheduler jobs after plugin changes")
            SCHEDULER.update_jobs()
            
            # Reload environment configuration
            env = SCHEDULER.db.get_config()
            env["DATABASE_URI"] = SCHEDULER.db.database_uri
            tz = getenv("TZ")
            if tz:
                env["TZ"] = tz

        LOGGER.info("Executing scheduler ...")

        # Clean up temporary variables
        del dotenv_env

        # Initialize main scheduler control variables
        FIRST_START = True
        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []

        changed_plugins = []
        old_changes = {}
        healthcheck_job_run = False

        debug_log(LOGGER, "Entering main scheduler loop")

        # Main scheduler execution loop
        # Handles configuration changes, job execution, and instance management
        while True:
            threads.clear()

            # Wait for any ongoing failover backup to complete
            while BACKING_UP_FAILOVER.is_set():
                LOGGER.warning("Waiting for the failover backup to finish ...")
                debug_log(LOGGER, "Failover backup in progress, waiting...")
                sleep(1)

            debug_log(LOGGER, f"Scheduler loop iteration: run_jobs_once={RUN_JOBS_ONCE}")

            # Execute jobs once if needed (startup or after changes)
            if RUN_JOBS_ONCE:
                debug_log(LOGGER, "Running scheduler jobs once")
                
                # Reload scheduler with current environment and changed plugins
                reload_env = env | {
                    "TZ": getenv("TZ", "UTC"), 
                    "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)
                }
                
                ignore_plugins = ["misc", "pro"] if FIRST_START else []
                debug_log(LOGGER, f"Reload parameters: ignore_plugins={ignore_plugins}")
                
                reload_success = SCHEDULER.reload(
                    reload_env,
                    changed_plugins=changed_plugins,
                    ignore_plugins=ignore_plugins,
                )
                
                if not reload_success:
                    LOGGER.error("At least one job in run_once() failed")
                else:
                    LOGGER.info("All jobs in run_once() were successful")
                    # Generate caches if database is read-only
                    if SCHEDULER.db.readonly:
                        debug_log(LOGGER, "Database is read-only, generating caches")
                        generate_caches()
                
                healthcheck_job_run = False

            # Generate nginx configuration if needed
            if CONFIG_NEED_GENERATION:
                debug_log(LOGGER, "Generating nginx configuration")
                
                config_gen_success = generate_configs()
                if config_gen_success and SCHEDULER.apis:
                    debug_log(LOGGER, "Starting nginx config send thread")
                    # Send nginx configs to BunkerWeb instances
                    threads.append(
                        Thread(
                            target=send_file_to_bunkerweb, 
                            args=(CONFIG_PATH, "/confs")
                        )
                    )
                    threads[-1].start()

            failover_message = ""
            try:
                success = True
                reachable = True
                
                if SCHEDULER.apis:
                    debug_log(LOGGER, "Starting cache send thread")
                    # Send cache files to BunkerWeb instances
                    threads.append(
                        Thread(
                            target=send_file_to_bunkerweb, 
                            args=(CACHE_PATH, "/cache")
                        )
                    )
                    threads[-1].start()

                    # Wait for all file sending threads to complete
                    debug_log(LOGGER, f"Waiting for {len(threads)} file send threads to complete")
                    
                    for thread in threads:
                        thread.join()

                    # Send reload command to all BunkerWeb instances
                    reload_endpoint = f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}"
                    reload_timeout = max(
                        RELOAD_MIN_TIMEOUT, 
                        3 * len(env.get("SERVER_NAME", "www.example.com").split(" "))
                    )
                    
                    debug_log(
                        LOGGER,
                        f"Sending reload command: {reload_endpoint}, "
                        f"timeout: {reload_timeout}"
                    )
                    
                    success, responses = SCHEDULER.send_to_apis(
                        "POST",
                        reload_endpoint,
                        timeout=reload_timeout,
                        response=True,
                    )
                    
                    if not success:
                        reachable = False
                        debug_log(
                            LOGGER,
                            "Error while reloading all bunkerweb instances"
                        )

                    debug_log(LOGGER, f"Reload responses: {responses}")

                    # Process responses from each instance
                    successful_instances = 0
                    failed_instances = 0
                    
                    for db_instance in SCHEDULER.db.get_instances():
                        metadata = responses.get(db_instance["hostname"], {})
                        status = metadata.get("status", "down")

                        debug_log(
                            LOGGER,
                            f"Instance {db_instance['hostname']} reload status: {status}"
                        )

                        if status == "success":
                            success = True
                            successful_instances += 1
                        else:
                            failed_instances += 1
                            message = metadata.get("msg", "couldn't get message")
                            if "\n" in message:
                                message = message.split("\n", 1)[1]

                            failover_message += (
                                f"{db_instance['hostname']}:"
                                f"{db_instance['port']} - {message}\n"
                            )

                        # Update instance status in database
                        new_status = (
                            "up" if status == "success"
                            else (
                                "failover" 
                                if responses.get(
                                    db_instance["hostname"], {}
                                ).get("msg") == "config check failed" 
                                else "down"
                            )
                        )
                        
                        ret = SCHEDULER.db.update_instance(
                            db_instance["hostname"], new_status
                        )
                        if ret:
                            LOGGER.error(
                                f"Couldn't update instance "
                                f"{db_instance['hostname']} status to "
                                f"{new_status} in the database: {ret}"
                            )

                        # Manage reachable instances list
                        if status == "success":
                            # Add successful instance to reachable list
                            found = False
                            for api in SCHEDULER.apis:
                                if api.endpoint == (
                                    f"http://{db_instance['hostname']}:"
                                    f"{db_instance['port']}/"
                                ):
                                    found = True
                                    break
                            if not found:
                                debug_log(
                                    LOGGER,
                                    f"Adding {db_instance['hostname']}:"
                                    f"{db_instance['port']} to the list of "
                                    f"reachable instances"
                                )
                                SCHEDULER.apis.append(
                                    API(
                                        f"http://{db_instance['hostname']}:"
                                        f"{db_instance['port']}", 
                                        db_instance["server_name"]
                                    )
                                )
                            continue

                        # Remove failed instance from reachable list
                        for i, api in enumerate(SCHEDULER.apis):
                            if api.endpoint == (
                                f"http://{db_instance['hostname']}:"
                                f"{db_instance['port']}/"
                            ):
                                debug_log(
                                    LOGGER,
                                    f"Removing {db_instance['hostname']}:"
                                    f"{db_instance['port']} from the list of "
                                    f"reachable instances"
                                )
                                del SCHEDULER.apis[i]
                                break

                    debug_log(
                        LOGGER,
                        f"Reload results: {successful_instances} successful, "
                        f"{failed_instances} failed"
                    )
                else:
                    # No BunkerWeb instances available
                    for thread in threads:
                        thread.join()

                    LOGGER.warning(
                        "No BunkerWeb instance found, skipping bunkerweb reload ..."
                    )
                    debug_log(LOGGER, "No API instances configured")
                        
            except BaseException as e:
                LOGGER.error(
                    f"Exception while reloading after running jobs once "
                    f"scheduling : {e}"
                )
                debug_log(LOGGER, f"Reload exception: {format_exc()}")

            # Update failover status in database
            try:
                debug_log(LOGGER, f"Setting failover status: {not success}")
                
                SCHEDULER.db.set_metadata(
                    {"failover": not success, "failover_message": failover_message}
                )
            except BaseException as e:
                LOGGER.error(
                    f"Error while setting failover to true in the database: {e}"
                )
                debug_log(LOGGER, f"Failover metadata update error: {format_exc()}")

            # Handle failover logic - attempt to restore last working
            # configuration
            try:
                if not success and reachable:
                    LOGGER.error(
                        "Error while reloading bunkerweb, failing over to "
                        "last working configuration ..."
                    )
                    
                    # Check if failover configuration exists
                    failover_config_paths = [
                        FAILOVER_PATH.joinpath("config"),
                        FAILOVER_PATH.joinpath("custom_configs"),
                        FAILOVER_PATH.joinpath("cache"),
                    ]
                    
                    missing_paths = [p for p in failover_config_paths if not p.is_dir()]
                    
                    if missing_paths:
                        LOGGER.error(
                            "No failover configuration found, ignoring failover ..."
                        )
                        debug_log(LOGGER, f"Missing failover paths: {missing_paths}")
                    else:
                        debug_log(LOGGER, "Initiating failover to last working configuration")
                        
                        # Send failover configuration to BunkerWeb instances
                        if SCHEDULER.apis:
                            failover_threads = [
                                Thread(
                                    target=send_file_to_bunkerweb, 
                                    args=(FAILOVER_PATH.joinpath("config"), "/confs")
                                ),
                                Thread(
                                    target=send_file_to_bunkerweb, 
                                    args=(FAILOVER_PATH.joinpath("cache"), "/cache")
                                ),
                                Thread(
                                    target=send_file_to_bunkerweb, 
                                    args=(
                                        FAILOVER_PATH.joinpath("custom_configs"), 
                                        "/custom_configs"
                                    )
                                ),
                            ]
                            
                            debug_log(LOGGER, f"Starting {len(failover_threads)} failover threads")
                            
                            for thread in failover_threads:
                                thread.start()

                            for thread in failover_threads:
                                thread.join()

                        # Reload with failover configuration
                        failover_reload_success = SCHEDULER.send_to_apis(
                            "POST",
                            f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}",
                            timeout=max(
                                RELOAD_MIN_TIMEOUT, 
                                3 * len(env.get("SERVER_NAME", "www.example.com").split(" "))
                            ),
                        )[0]
                        
                        if not failover_reload_success:
                            LOGGER.error(
                                "Error while reloading bunkerweb with failover "
                                "configuration, skipping ..."
                            )
                        else:
                            debug_log(LOGGER, "Failover configuration loaded successfully")
                            
                elif not reachable:
                    LOGGER.warning(
                        "No BunkerWeb instance is reachable, skipping failover ..."
                    )
                    debug_log(LOGGER, "All instances unreachable, cannot perform failover")
                else:
                    LOGGER.info("Successfully reloaded bunkerweb")
                    debug_log(LOGGER, "Starting failover backup thread")
                    # Create backup of successful configuration for future failover
                    Thread(target=backup_failover).start()
            except BaseException as e:
                LOGGER.error(f"Exception while executing failover logic : {e}")
                debug_log(LOGGER, f"Failover logic exception: {format_exc()}")

            # Mark configuration changes as processed in database
            try:
                debug_log(LOGGER, f"Marking changes as checked: {CHANGES}")
                
                ret = SCHEDULER.db.checked_changes(CHANGES, plugins_changes="all")
                if ret:
                    LOGGER.error(
                        f"An error occurred when setting the changes to "
                        f"checked in the database : {ret}"
                    )
            except BaseException as e:
                LOGGER.error(
                    f"Error while setting changes to checked in the database: {e}"
                )
                debug_log(LOGGER, f"Changes check error: {format_exc()}")

            # Reset control flags for next iteration
            FIRST_START = False
            NEED_RELOAD = False
            RUN_JOBS_ONCE = False
            CONFIG_NEED_GENERATION = False
            CONFIGS_NEED_GENERATION = False
            PLUGINS_NEED_GENERATION = False
            PRO_PLUGINS_NEED_GENERATION = False
            INSTANCES_NEED_GENERATION = False
            changed_plugins.clear()

            debug_log(LOGGER, "Reset scheduler flags for next iteration")

            # Handle scheduler first start flag
            if scheduler_first_start:
                debug_log(LOGGER, "Clearing scheduler first start flag")
                
                try:
                    ret = SCHEDULER.db.set_metadata({"scheduler_first_start": False})

                    if ret == (
                        "The database is read-only, the changes will not be saved"
                    ):
                        LOGGER.warning(
                            "The database is read-only, the scheduler first "
                            "start will not be saved"
                        )
                    elif ret:
                        LOGGER.error(
                            f"An error occurred when setting the scheduler "
                            f"first start : {ret}"
                        )
                    else:
                        debug_log(LOGGER, "Scheduler first start flag cleared successfully")
                except BaseException as e:
                    LOGGER.error(
                        f"Error while setting the scheduler first start : {e}"
                    )
                    debug_log(LOGGER, f"First start flag error: {format_exc()}")
                finally:
                    scheduler_first_start = False

            # Create health check file if it doesn't exist
            if not HEALTHY_PATH.is_file():
                timestamp = datetime.now().astimezone().isoformat()
                HEALTHY_PATH.write_text(timestamp, encoding="utf-8")
                debug_log(LOGGER, f"Created health file with timestamp: {timestamp}")

            # Clear configuration changes flag and schedule healthcheck
            APPLYING_CHANGES.clear()
            if not healthcheck_job_run:
                debug_log(LOGGER, "Scheduling healthcheck job ...")
                schedule_every(HEALTHCHECK_INTERVAL).seconds.do(healthcheck_job)
                healthcheck_job_run = True

            # Main scheduler monitoring loop
            # Continuously checks for database changes and triggers regeneration
            LOGGER.info("Executing job scheduler ...")
            errors = 0
            loop_iterations = 0
            
            while RUN and not NEED_RELOAD:
                loop_iterations += 1
                if getenv("LOG_LEVEL") == "debug" and loop_iterations % 100 == 0:
                    debug_log(LOGGER, f"Scheduler monitoring loop iteration: {loop_iterations}")
                
                try:
                    # Sleep based on database mode (read-only vs writable)
                    sleep(3 if SCHEDULER.db.readonly else 1)
                    
                    # Run pending scheduled jobs and healthchecks
                    run_pending()
                    SCHEDULER.run_pending()
                    current_time = datetime.now().astimezone()

                    # Wait for database lock to be released (30 second timeout)
                    while (DB_LOCK_FILE.is_file() and 
                           DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp()):
                        debug_log(
                            LOGGER,
                            "Database is locked, waiting for it to be "
                            "unlocked (timeout: 30s) ..."
                        )
                        sleep(1)

                    # Clean up stale lock file
                    DB_LOCK_FILE.unlink(missing_ok=True)

                    # Get current database metadata for change detection
                    db_metadata = SCHEDULER.db.get_metadata()

                    if isinstance(db_metadata, str):
                        raise Exception(
                            f"An error occurred when checking for changes "
                            f"in the database : {db_metadata}"
                        )
                    
                    if not isinstance(db_metadata, dict):
                        debug_log(LOGGER, f"Invalid db_metadata type: {type(db_metadata)}")
                        continue

                    # Extract change tracking information
                    changes = {
                        "pro_plugins_changed": db_metadata.get("pro_plugins_changed", False),
                        "last_pro_plugins_change": db_metadata.get("last_pro_plugins_change"),
                        "external_plugins_changed": db_metadata.get("external_plugins_changed", False),
                        "last_external_plugins_change": db_metadata.get("last_external_plugins_change"),
                        "custom_configs_changed": db_metadata.get("custom_configs_changed", False),
                        "last_custom_configs_change": db_metadata.get("last_custom_configs_change"),
                        "plugins_config_changed": db_metadata.get("plugins_config_changed", False),
                        "instances_changed": db_metadata.get("instances_changed", False),
                        "last_instances_change": db_metadata.get("last_instances_change"),
                    }

                    # Skip change detection if database is read-only and no changes
                    if SCHEDULER.db.readonly and changes == old_changes:
                        continue

                    if getenv("LOG_LEVEL") == "debug" and changes != old_changes:
                        debug_log(LOGGER, f"Changes detected: {changes}")

                    # Check for pro plugins changes
                    if changes["pro_plugins_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_pro_plugins_change"]
                        or not old_changes
                        or (old_changes.get("last_pro_plugins_change") != 
                            changes["last_pro_plugins_change"])
                    ):
                        LOGGER.info("Pro plugins changed, generating ...")
                        PRO_PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    # Check for external plugins changes
                    if changes["external_plugins_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_external_plugins_change"]
                        or not old_changes
                        or (old_changes.get("last_external_plugins_change") != 
                            changes["last_external_plugins_change"])
                    ):
                        LOGGER.info("External plugins changed, generating ...")
                        PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    # Check for custom configs changes
                    if changes["custom_configs_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_custom_configs_change"]
                        or not old_changes
                        or (old_changes.get("last_custom_configs_change") != 
                            changes["last_custom_configs_change"])
                    ):
                        LOGGER.info("Custom configs changed, generating ...")
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # Check for plugins configuration changes
                    if changes["plugins_config_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes.get("last_plugins_config_change")
                        or not old_changes
                        or (old_changes.get("plugins_config_changed") != 
                            changes["plugins_config_changed"])
                    ):
                        LOGGER.info("Plugins config changed, generating ...")
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True
                        changed_plugins = list(changes["plugins_config_changed"])
                        debug_log(LOGGER, f"Changed plugins: {changed_plugins}")

                    # Check for instances changes
                    if changes["instances_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_instances_change"]
                        or not old_changes
                        or (old_changes.get("last_instances_change") != 
                            changes["last_instances_change"])
                    ):
                        LOGGER.info("Instances changed, generating ...")
                        INSTANCES_NEED_GENERATION = True
                        PRO_PLUGINS_NEED_GENERATION = True
                        PLUGINS_NEED_GENERATION = True
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # Store current changes for next comparison
                    old_changes = changes.copy()
                    
                except BaseException:
                    debug_log(LOGGER, format_exc())
                    errors += 1
                    if errors > 5:
                        LOGGER.error(
                            f"An error occurred when executing the scheduler : "
                            f"{format_exc()}"
                        )
                        stop(1)
                    sleep(5)

            # Process detected changes and regenerate configurations
            # This section handles the actual regeneration of changed components
            if NEED_RELOAD:
                APPLYING_CHANGES.set()
                debug_log(LOGGER, f"Processing detected changes: {changes}")
                
                # Force database readonly check
                SCHEDULER.try_database_readonly(force=True)
                CHANGES.clear()

                # Regenerate instances API list if instances changed
                if INSTANCES_NEED_GENERATION:
                    CHANGES.append("instances")
                    debug_log(LOGGER, "Regenerating instances API list")
                    
                    SCHEDULER.apis = []
                    for db_instance in SCHEDULER.db.get_instances():
                        api_endpoint = (
                            f"http://{db_instance['hostname']}:"
                            f"{db_instance['port']}"
                        )
                        SCHEDULER.apis.append(
                            API(api_endpoint, db_instance["server_name"])
                        )
                        debug_log(LOGGER, f"Added API instance: {api_endpoint}")

                # Regenerate custom configurations if changed
                if CONFIGS_NEED_GENERATION:
                    CHANGES.append("custom_configs")
                    debug_log(LOGGER, "Regenerating custom configurations")
                    generate_custom_configs(SCHEDULER.db.get_custom_configs())

                # Regenerate external plugins if changed
                if PLUGINS_NEED_GENERATION:
                    CHANGES.append("external_plugins")
                    debug_log(LOGGER, "Regenerating external plugins")
                    generate_external_plugins()
                    SCHEDULER.update_jobs()

                # Regenerate pro plugins if changed
                if PRO_PLUGINS_NEED_GENERATION:
                    CHANGES.append("pro_plugins")
                    debug_log(LOGGER, "Regenerating pro plugins")
                    generate_external_plugins(PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                # Regenerate main configuration if changed
                if CONFIG_NEED_GENERATION:
                    CHANGES.append("config")
                    debug_log(LOGGER, "Regenerating main configuration")
                    
                    old_env = env.copy()
                    env = SCHEDULER.db.get_config()
                    
                    # Check if API settings changed and update instances accordingly
                    if (old_env.get("API_HTTP_PORT", "5000") != 
                        env.get("API_HTTP_PORT", "5000") or 
                        old_env.get("API_SERVER_NAME", "bwapi") != 
                        env.get("API_SERVER_NAME", "bwapi")):
                        
                        debug_log(LOGGER, "API settings changed, updating instances")
                        
                        # Update all instances with new API settings
                        err = SCHEDULER.db.update_instances(
                            [
                                {
                                    "hostname": db_instance["hostname"],
                                    "name": db_instance["name"],
                                    "env": {
                                        "API_HTTP_PORT": env.get("API_HTTP_PORT", "5000"),
                                        "API_SERVER_NAME": env.get("API_SERVER_NAME", "bwapi"),
                                    },
                                    "type": db_instance["type"],
                                    "status": db_instance["status"],
                                    "method": db_instance["method"],
                                    "last_seen": db_instance["last_seen"],
                                }
                                for db_instance in SCHEDULER.db.get_instances()
                            ],
                            method="scheduler",
                        )
                        if err:
                            LOGGER.error(
                                f"Couldn't update instances in the database: {err}"
                            )
                    
                    # Update environment with database URI and timezone
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

    # Global exception handler for the entire scheduler process
    # Logs any unhandled exceptions and exits with error status
    except:
        LOGGER.error(f"Exception while executing scheduler : {format_exc()}")
        debug_log(LOGGER, "Fatal scheduler exception occurred, stopping with status 1")
        stop(1)