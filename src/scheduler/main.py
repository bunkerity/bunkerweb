#!/usr/bin/env python3

from argparse import ArgumentParser
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from json import load as json_load
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

BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [BUNKERWEB_PATH.joinpath(*paths).as_posix() 
                  for paths in (("deps", "python"), ("utils",), 
                               ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from schedule import every as schedule_every, run_pending

from common_utils import (bytes_hash, dict_to_frozenset, 
                         handle_docker_secrets)  # type: ignore

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from Database import Database  # type: ignore
from JobScheduler import JobScheduler
from jobs import Job  # type: ignore
from API import API  # type: ignore

from ApiCaller import ApiCaller  # type: ignore

APPLYING_CHANGES = Event()
BACKING_UP_FAILOVER = Event()

RUN = True
SCHEDULER: Optional[JobScheduler] = None
SCHEDULER_LOCK = Lock()

CACHE_PATH = Path(sep, "var", "cache", "bunkerweb")
CACHE_PATH.mkdir(parents=True, exist_ok=True)

CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
CUSTOM_CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
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

for custom_config_dir in CUSTOM_CONFIGS_DIRS:
    CUSTOM_CONFIGS_PATH.joinpath(custom_config_dir).mkdir(parents=True, 
                                                          exist_ok=True)

CONFIG_PATH = Path(sep, "etc", "nginx")
NGINX_VARIABLES_PATH = CONFIG_PATH.joinpath("variables.env")

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")
TMP_PATH.mkdir(parents=True, exist_ok=True)
NGINX_TMP_VARIABLES_PATH = TMP_PATH.joinpath("variables.env")

FAILOVER_PATH = TMP_PATH.joinpath("failover")
FAILOVER_PATH.mkdir(parents=True, exist_ok=True)

HEALTHY_PATH = TMP_PATH.joinpath("scheduler.healthy")

DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")

# Initialize bw_logger module for main scheduler
LOGGER = bwlog(
    title="SCHEDULER: ",
    log_file_path="/var/log/bunkerweb/scheduler.log"
)

HEALTHCHECK_INTERVAL = getenv("HEALTHCHECK_INTERVAL", "30")

if not HEALTHCHECK_INTERVAL.isdigit():
    LOGGER.error("HEALTHCHECK_INTERVAL must be an integer, defaulting to 30")
    HEALTHCHECK_INTERVAL = 30

HEALTHCHECK_INTERVAL = int(HEALTHCHECK_INTERVAL)
HEALTHCHECK_EVENT = Event()

# Initialize bw_logger module for healthcheck
HEALTHCHECK_LOGGER = bwlog(
    title="SCHEDULER-HEALTHCHECK: ",
    log_file_path="/var/log/bunkerweb/scheduler.log"
)

RELOAD_MIN_TIMEOUT = getenv("RELOAD_MIN_TIMEOUT", "5")

if not RELOAD_MIN_TIMEOUT.isdigit():
    LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
    RELOAD_MIN_TIMEOUT = 5

RELOAD_MIN_TIMEOUT = int(RELOAD_MIN_TIMEOUT)

DISABLE_CONFIGURATION_TESTING = (getenv("DISABLE_CONFIGURATION_TESTING", 
                                        "no").lower() == "yes")

if DISABLE_CONFIGURATION_TESTING:
    LOGGER.warning("Configuration testing is disabled, changes will be "
                   "applied without testing (we hope you know what you're "
                   "doing) ...")

IGNORE_FAIL_SENDING_CONFIG = (getenv("IGNORE_FAIL_SENDING_CONFIG", 
                                     "no").lower() == "yes")

if IGNORE_FAIL_SENDING_CONFIG:
    LOGGER.warning("Ignoring fail sending config to some BunkerWeb "
                   "instances ...")

IGNORE_REGEX_CHECK = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"

if IGNORE_REGEX_CHECK:
    LOGGER.warning("Ignoring regex check for settings (we hope you know "
                   "what you're doing) ...")

# Check if debug logging is enabled
DEBUG_MODE = getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"

if DEBUG_MODE:
    LOGGER.debug("Debug mode enabled for Scheduler")
    LOGGER.debug(f"BUNKERWEB_PATH: {BUNKERWEB_PATH}")
    LOGGER.debug(f"HEALTHCHECK_INTERVAL: {HEALTHCHECK_INTERVAL}")
    LOGGER.debug(f"RELOAD_MIN_TIMEOUT: {RELOAD_MIN_TIMEOUT}")
    LOGGER.debug(f"DISABLE_CONFIGURATION_TESTING: "
                 f"{DISABLE_CONFIGURATION_TESTING}")


# Handle SIGINT/SIGTERM signals to gracefully stop the scheduler.
# Waits for ongoing configuration changes to complete (up to 30 seconds)
# before clearing scheduler jobs and exiting cleanly.
def handle_stop(signum, frame):
    if DEBUG_MODE:
        LOGGER.debug(f"handle_stop() called with signal: {signum}")
    
    LOGGER.debug(f"Received signal {signum}, preparing to stop...")
    current_time = datetime.now().astimezone()
    
    while (APPLYING_CHANGES.is_set() and 
           (datetime.now().astimezone() - current_time).seconds < 30):
        LOGGER.warning("Waiting for the changes to be applied before "
                       "stopping ...")
        sleep(1)

    if APPLYING_CHANGES.is_set():
        LOGGER.warning("Timeout reached, stopping without waiting for the "
                       "changes to be applied ...")

    if SCHEDULER is not None:
        if DEBUG_MODE:
            LOGGER.debug("Clearing scheduler jobs")
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Handle SIGHUP signal to reload configuration.
# Runs save_config.py to persist current configuration changes to disk
# when the scheduler receives a hangup signal.
def handle_reload(signum, frame):
    if DEBUG_MODE:
        LOGGER.debug(f"handle_reload() called with signal: {signum}")
    
    LOGGER.debug(f"Received SIGHUP signal, reloading configuration...")
    try:
        if SCHEDULER is not None and RUN:
            if SCHEDULER.db.readonly:
                LOGGER.warning("The database is read-only, no need to save "
                               "the changes in the configuration as they will "
                               "not be saved")
                return

            LOGGER.debug("Running save_config.py to persist configuration...")
            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", 
                                          "save_config.py").as_posix(),
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
                LOGGER.error("Config saver failed, configuration will not "
                             "work as expected...")
            else:
                LOGGER.debug("Configuration saved successfully")
        else:
            LOGGER.warning("Ignored reload operation because scheduler is "
                           "not running ...")
    except BaseException:
        LOGGER.exception("Exception while reloading scheduler")


signal(SIGHUP, handle_reload)


# Clean up and exit the scheduler.
# Removes PID file and health status file before terminating
# the scheduler process with the specified exit status.
def stop(status):
    if DEBUG_MODE:
        LOGGER.debug(f"stop() called with status: {status}")
    
    LOGGER.debug(f"Stopping scheduler with status {status}")
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(
        missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


# Send a file to BunkerWeb instances via API.
# Uploads files to all reachable instances and updates their status
# based on the response, maintaining a list of healthy instances.
def send_file_to_bunkerweb(file_path: Path, endpoint: str, 
                          logger=LOGGER, *, 
                          api_caller: Optional[ApiCaller] = None):
    if DEBUG_MODE:
        logger.debug(f"send_file_to_bunkerweb() called with file_path: "
                     f"{file_path}, endpoint: {endpoint}")
    
    assert SCHEDULER is not None, "SCHEDULER is not defined"
    logger.info(f"Sending {file_path} to "
                f"{'specific' if api_caller else 'all reachable'} "
                f"BunkerWeb instances ...")
    logger.debug(f"Using endpoint: {endpoint}")
    success, responses = (api_caller or SCHEDULER).send_files(
        file_path.as_posix(), endpoint, response=True)
    fails = []

    if not IGNORE_FAIL_SENDING_CONFIG:
        for db_instance in SCHEDULER.db.get_instances():
            if DEBUG_MODE:
                logger.debug(f"Processing instance: {db_instance['hostname']}")
            
            index = -1
            with SCHEDULER_LOCK:
                for i, api in enumerate(SCHEDULER.apis):
                    if api.endpoint == (f"http://{db_instance['hostname']}:"
                                       f"{db_instance['port']}/"):
                        index = i
                        break

            status = responses.get(db_instance["hostname"], 
                                  {"status": "down"}).get("status", "down")
            logger.debug(f"Instance {db_instance['hostname']} status: "
                        f"{status}")

            ret = SCHEDULER.db.update_instance(
                db_instance["hostname"], 
                "up" if status == "success" else "down")
            if ret:
                logger.error(f"Couldn't update instance "
                            f"{db_instance['hostname']} status to down in "
                            f"the database: {ret}")

            with SCHEDULER_LOCK:
                if status == "success":
                    success = True
                    if index == -1:
                        logger.debug(f"Adding {db_instance['hostname']}:"
                                    f"{db_instance['port']} to the list of "
                                    f"reachable instances")
                        SCHEDULER.apis.append(
                            API(f"http://{db_instance['hostname']}:"
                                f"{db_instance['port']}", 
                                db_instance["server_name"]))
                elif index != -1:
                    fails.append(f"{db_instance['hostname']}:"
                                f"{db_instance['port']}")
                    logger.debug(f"Removing {db_instance['hostname']}:"
                                f"{db_instance['port']} from the list of "
                                f"reachable instances")
                    del SCHEDULER.apis[index]

    if not success:
        logger.error(f"Error while sending {file_path} to BunkerWeb "
                     "instances")
    elif not fails:
        logger.info(f"Successfully sent {file_path} folder to reachable "
                    "BunkerWeb instances")
    elif not IGNORE_FAIL_SENDING_CONFIG:
        logger.warning(f"Error while sending {file_path} to some BunkerWeb "
                       f"instances, removing them from the list of "
                       f"reachable instances: {', '.join(fails)}")


# Generate custom configuration files from database.
# Cleans up old configs, creates new ones from database entries,
# and optionally sends them to BunkerWeb instances.
def generate_custom_configs(configs: Optional[List[Dict[str, Any]]] = None, 
                           *, original_path: Union[Path, str] = 
                           CUSTOM_CONFIGS_PATH, send: bool = True):
    if DEBUG_MODE:
        LOGGER.debug(f"generate_custom_configs() called with "
                     f"original_path: {original_path}, send: {send}")
    
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    LOGGER.info("Removing old custom configs files ...")
    if original_path.is_dir():
        LOGGER.debug(f"Cleaning up directory: {original_path}")
        for file in original_path.glob("*/*"):
            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
                    if DEBUG_MODE:
                        LOGGER.debug(f"Removed file: {file}")
            elif file.is_dir():
                rmtree(file, ignore_errors=True)
                if DEBUG_MODE:
                    LOGGER.debug(f"Removed directory: {file}")

    if configs is None:
        assert SCHEDULER is not None
        configs = SCHEDULER.db.get_custom_configs()

    if configs:
        LOGGER.info("Generating new custom configs ...")
        LOGGER.debug(f"Processing {len(configs)} custom configs")
        original_path.mkdir(parents=True, exist_ok=True)
        for custom_config in configs:
            try:
                if custom_config["data"]:
                    tmp_path = original_path.joinpath(
                        custom_config["type"].replace("_", "-"),
                        custom_config["service_id"] or "",
                        f"{Path(custom_config['name']).stem}.conf",
                    )
                    if DEBUG_MODE:
                        LOGGER.debug(f"Writing custom config to: {tmp_path}")
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path.write_bytes(custom_config["data"])
                    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
                    if tmp_path.stat().st_mode & 0o777 != desired_perms:
                        tmp_path.chmod(desired_perms)
                        if DEBUG_MODE:
                            LOGGER.debug(f"Set permissions for {tmp_path} "
                                        f"to 0o640")
            except OSError:
                LOGGER.exception(
                    f"OS error while generating custom configs "
                    f"\"{custom_config['name']}\""
                    f"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}"
                )
                if custom_config["method"] == "manual":
                    continue
            except BaseException:
                LOGGER.exception(
                    f"Error while generating custom configs "
                    f"\"{custom_config['name']}\""
                    f"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}"
                )

    if send and SCHEDULER and SCHEDULER.apis:
        send_file_to_bunkerweb(original_path, "/custom_configs")


# Generate external and pro plugins from database.
# Extracts plugin archives, compares checksums to avoid unnecessary updates,
# sets proper permissions, and sends plugins to BunkerWeb instances.
def generate_external_plugins(original_path: Union[Path, str] = 
                             EXTERNAL_PLUGINS_PATH, *, send: bool = True):
    if DEBUG_MODE:
        LOGGER.debug(f"generate_external_plugins() called with "
                     f"original_path: {original_path}, send: {send}")
    
    if not isinstance(original_path, Path):
        original_path = Path(original_path)
    pro = original_path.as_posix().endswith("/pro/plugins")

    if DEBUG_MODE:
        LOGGER.debug(f"Processing {'pro' if pro else 'external'} plugins")

    assert SCHEDULER is not None
    plugins = SCHEDULER.db.get_plugins(_type="pro" if pro else "external", 
                                      with_data=True)
    assert plugins is not None, "Couldn't get plugins from database"

    # Remove old external/pro plugins files
    LOGGER.info(f"Removing old/changed {'pro ' if pro else ''}external "
                f"plugins files ...")
    ignored_plugins = set()
    if original_path.is_dir():
        LOGGER.debug(f"Checking existing plugins in {original_path}")
        for file in original_path.glob("*"):
            with suppress(StopIteration, IndexError):
                index = next(i for i, plugin in enumerate(plugins) 
                           if plugin["id"] == file.name)

                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", 
                                 compresslevel=9) as tar:
                        tar.add(file, arcname=file.name, recursive=True)
                    plugin_content.seek(0, 0)
                    if (bytes_hash(plugin_content, algorithm="sha256") == 
                        plugins[index]["checksum"]):
                        ignored_plugins.add(file.name)
                        if DEBUG_MODE:
                            LOGGER.debug(f"Plugin {file.name} unchanged, "
                                        f"keeping it")
                        continue
                    if DEBUG_MODE:
                        LOGGER.debug(f"Checksum of {file} has changed, "
                                    f"removing it ...")

            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
                    if DEBUG_MODE:
                        LOGGER.debug(f"Removed file: {file}")
            elif file.is_dir():
                rmtree(file, ignore_errors=True)
                if DEBUG_MODE:
                    LOGGER.debug(f"Removed directory: {file}")

    if plugins:
        LOGGER.info(f"Generating new {'pro ' if pro else ''}external "
                    f"plugins ...")
        LOGGER.debug(f"Processing {len(plugins)} plugins")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            if plugin["id"] in ignored_plugins:
                if DEBUG_MODE:
                    LOGGER.debug(f"Skipping unchanged plugin: "
                                f"{plugin['id']}")
                continue

            try:
                if plugin["data"]:
                    if DEBUG_MODE:
                        LOGGER.debug(f"Extracting plugin {plugin['id']} to "
                                    f"{original_path}")
                    with tar_open(fileobj=BytesIO(plugin["data"]), 
                                 mode="r:gz") as tar:
                        try:
                            tar.extractall(original_path, 
                                          filter="fully_trusted")
                        except TypeError:
                            tar.extractall(original_path)

                    # Add u+x permissions to executable files
                    plugin_path = original_path.joinpath(plugin["id"])
                    desired_perms = (S_IRUSR | S_IWUSR | S_IXUSR | 
                                   S_IRGRP | S_IXGRP)  # 0o750
                    for subdir, pattern in (
                        ("jobs", "*"),
                        ("bwcli", "*"),
                        ("ui", "*.py"),
                    ):
                        for executable_file in (plugin_path.joinpath(subdir)
                                              .rglob(pattern)):
                            if (executable_file.stat().st_mode & 0o777 != 
                                desired_perms):
                                executable_file.chmod(desired_perms)
                                if DEBUG_MODE:
                                    LOGGER.debug(f"Set executable "
                                                f"permissions for "
                                                f"{executable_file}")
            except OSError:
                LOGGER.exception(f"OS error while generating "
                                f"{'pro ' if pro else ''}external plugins "
                                f"\"{plugin['name']}\"")
                if plugin["method"] == "manual":
                    continue
            except BaseException:
                LOGGER.exception(f"Error while generating "
                                f"{'pro ' if pro else ''}external plugins "
                                f"\"{plugin['name']}\"")

    if send and SCHEDULER and SCHEDULER.apis:
        LOGGER.info(f"Sending {'pro ' if pro else ''}external plugins to "
                    f"BunkerWeb")
        send_file_to_bunkerweb(
            original_path, 
            ("/pro_plugins" if original_path.as_posix().endswith(
                "/pro/plugins") else "/plugins"))


# Restore cache files from database.
# Rebuilds the cache directory structure by extracting cached data,
# cleaning up outdated files, and setting appropriate permissions.
def generate_caches():
    if DEBUG_MODE:
        LOGGER.debug("generate_caches() called")
    
    assert SCHEDULER is not None

    job_cache_files = SCHEDULER.db.get_jobs_cache_files()
    plugin_cache_files = set()
    ignored_dirs = set()

    LOGGER.debug(f"Restoring {len(job_cache_files)} cache files from "
                 f"database")

    for job_cache_file in job_cache_files:
        job_path = Path(sep, "var", "cache", "bunkerweb", 
                       job_cache_file["plugin_id"])
        cache_path = job_path.joinpath(job_cache_file["service_id"] or "", 
                                      job_cache_file["file_name"])
        plugin_cache_files.add(cache_path)

        try:
            if job_cache_file["file_name"].endswith(".tgz"):
                extract_path = cache_path.parent
                if job_cache_file["file_name"].startswith("folder:"):
                    extract_path = Path(
                        job_cache_file["file_name"].split("folder:", 1)[1]
                        .rsplit(".tgz", 1)[0])
                ignored_dirs.add(extract_path.as_posix())
                rmtree(extract_path, ignore_errors=True)
                extract_path.mkdir(parents=True, exist_ok=True)
                if DEBUG_MODE:
                    LOGGER.debug(f"Extracting tar file to {extract_path}")
                with tar_open(fileobj=BytesIO(job_cache_file["data"]), 
                             mode="r:gz") as tar:
                    assert isinstance(tar, TarFile)
                    try:
                        try:
                            tar.extractall(extract_path, 
                                          filter="fully_trusted")
                        except TypeError:
                            tar.extractall(extract_path)
                    except Exception:
                        LOGGER.exception("Error extracting tar file")
                if DEBUG_MODE:
                    LOGGER.debug(f"Restored cache directory {extract_path}")
                continue
                
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(job_cache_file["data"])
            desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
            if cache_path.stat().st_mode & 0o777 != desired_perms:
                cache_path.chmod(desired_perms)
            if DEBUG_MODE:
                LOGGER.debug(f"Restored cache file "
                            f"{job_cache_file['file_name']}")
        except BaseException:
            LOGGER.exception(f"Exception while restoring cache file "
                            f"{job_cache_file['file_name']}")

    if job_path.is_dir():
        for resource_path in list(job_path.rglob("*")):
            if resource_path.as_posix().startswith(tuple(ignored_dirs)):
                continue

            if DEBUG_MODE:
                LOGGER.debug(f"Checking if {resource_path} should be "
                            f"removed")
            if (resource_path not in plugin_cache_files and 
                resource_path.is_file()):
                if DEBUG_MODE:
                    LOGGER.debug(f"Removing non-cached file "
                                f"{resource_path}")
                resource_path.unlink(missing_ok=True)
                if (resource_path.parent.is_dir() and 
                    not list(resource_path.parent.iterdir())):
                    if DEBUG_MODE:
                        LOGGER.debug(f"Removing empty directory "
                                    f"{resource_path.parent}")
                    rmtree(resource_path.parent, ignore_errors=True)
                    if resource_path.parent == job_path:
                        break
                continue
            elif (resource_path.is_dir() and 
                  not list(resource_path.iterdir())):
                if DEBUG_MODE:
                    LOGGER.debug(f"Removing empty directory "
                                f"{resource_path}")
                rmtree(resource_path, ignore_errors=True)
                continue

            desired_perms = (S_IRUSR | S_IWUSR | S_IRGRP | 
                           S_IXUSR | S_IXGRP)  # 0o750
            if resource_path.stat().st_mode & 0o777 != desired_perms:
                resource_path.chmod(desired_perms)


# Generate nginx configuration files.
# Runs the main configuration generator and copies the variables file
# to the temporary location for nginx to use.
def generate_configs(logger=LOGGER) -> bool:
    if DEBUG_MODE:
        logger.debug("generate_configs() called")
    
    # run the generator
    logger.debug("Running configuration generator...")
    proc = subprocess_run(
        [
            BUNKERWEB_PATH.joinpath("gen", "main.py").as_posix(),
            "--settings",
            BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
            "--templates",
            BUNKERWEB_PATH.joinpath("confs").as_posix(),
            "--output",
            CONFIG_PATH.as_posix(),
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        check=False,
    )

    if proc.returncode != 0:
        logger.error("Config generator failed, configuration will not work "
                     "as expected...")
        return False

    if DEBUG_MODE:
        logger.debug(f"Copying {NGINX_VARIABLES_PATH} to "
                     f"{NGINX_TMP_VARIABLES_PATH}")
    copy(NGINX_VARIABLES_PATH.as_posix(), 
         NGINX_TMP_VARIABLES_PATH.as_posix())
    return True


# Periodic health check for BunkerWeb instances.
# Monitors instance health, handles loading states by sending configs,
# and maintains the list of reachable instances for load balancing.
def healthcheck_job():
    if DEBUG_MODE:
        HEALTHCHECK_LOGGER.debug("healthcheck_job() called")
    
    if HEALTHCHECK_EVENT.is_set():
        HEALTHCHECK_LOGGER.warning("Healthcheck job is already running, "
                                   "skipping execution ...")
        return

    try:
        assert SCHEDULER is not None
    except AssertionError:
        return

    HEALTHCHECK_EVENT.set()
    HEALTHCHECK_LOGGER.debug("Starting healthcheck job")

    if APPLYING_CHANGES.is_set():
        HEALTHCHECK_LOGGER.debug("Changes are being applied, skipping "
                                 "healthcheck")
        return

    env = None

    for db_instance in SCHEDULER.db.get_instances():
        bw_instance = API(f"http://{db_instance['hostname']}:"
                         f"{db_instance['port']}", 
                         db_instance["server_name"])
        HEALTHCHECK_LOGGER.debug(f"Checking health of "
                                f"{bw_instance.endpoint}")
        try:
            try:
                sent, err, status, resp = bw_instance.request("GET", 
                                                             "health")
            except BaseException as e:
                err = str(e)
                sent = False
                status = 500
                resp = {"status": "down", "msg": err}

            if DEBUG_MODE:
                HEALTHCHECK_LOGGER.debug(f"Health response: {resp}")

            success = True
            if not sent:
                HEALTHCHECK_LOGGER.warning(
                    f"Can't send API request to {bw_instance.endpoint}health"
                    f" : {err}, healthcheck will be retried in "
                    f"{HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False
            elif status != 200:
                HEALTHCHECK_LOGGER.warning(
                    f"Error while sending API request to "
                    f"{bw_instance.endpoint}health : status = "
                    f"{resp['status']}, msg = {resp['msg']}, healthcheck "
                    f"will be retried in {HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False

            if not success:
                ret = SCHEDULER.db.update_instance(
                    db_instance["hostname"], "down")
                if ret:
                    HEALTHCHECK_LOGGER.error(
                        f"Couldn't update instance {bw_instance.endpoint} "
                        f"status to down in the database: {ret}")

                for i, api in enumerate(SCHEDULER.apis):
                    if api.endpoint == bw_instance.endpoint:
                        if DEBUG_MODE:
                            HEALTHCHECK_LOGGER.debug(
                                f"Removing {bw_instance.endpoint} from the "
                                f"list of reachable instances")
                        del SCHEDULER.apis[i]
                        break
                continue

            if resp["msg"] == "loading":
                if db_instance["status"] == "failover":
                    HEALTHCHECK_LOGGER.warning(
                        f"Instance {db_instance['hostname']} is in failover "
                        f"mode, skipping sending config ...")
                    continue

                HEALTHCHECK_LOGGER.info(
                    f"Instance {bw_instance.endpoint} is loading, sending "
                    f"config ...")
                api_caller = ApiCaller([bw_instance])

                if env is None:
                    env = SCHEDULER.db.get_config()
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

                generate_configs(HEALTHCHECK_LOGGER)

                tmp_threads = [
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
                for thread in tmp_threads:
                    thread.start()

                for thread in tmp_threads:
                    thread.join()

                if not api_caller.send_to_apis(
                    "POST",
                    f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}",
                    timeout=max(RELOAD_MIN_TIMEOUT, 
                               3 * len(env.get("SERVER_NAME", 
                                              "www.example.com").split(" "))),
                )[0]:
                    HEALTHCHECK_LOGGER.error(
                        f"Error while reloading instance "
                        f"{bw_instance.endpoint}")
                    ret = SCHEDULER.db.update_instance(
                        db_instance["hostname"], "loading")
                    if ret:
                        HEALTHCHECK_LOGGER.error(
                            f"Couldn't update instance "
                            f"{bw_instance.endpoint} status to loading "
                            f"in the database: {ret}")
                    continue
                HEALTHCHECK_LOGGER.info(
                    f"Successfully reloaded instance "
                    f"{bw_instance.endpoint}")

            ret = SCHEDULER.db.update_instance(db_instance["hostname"], "up")
            if ret:
                HEALTHCHECK_LOGGER.error(
                    f"Couldn't update instance {bw_instance.endpoint} "
                    f"status to down in the database: {ret}")

            found = False
            for api in SCHEDULER.apis:
                if api.endpoint == bw_instance.endpoint:
                    found = True
                    break
            if not found:
                if DEBUG_MODE:
                    HEALTHCHECK_LOGGER.debug(
                        f"Adding {bw_instance.endpoint} to the list of "
                        f"reachable instances")
                SCHEDULER.apis.append(bw_instance)
        except BaseException:
            HEALTHCHECK_LOGGER.exception(
                f"Exception while checking instance "
                f"{bw_instance.endpoint}")
            for i, api in enumerate(SCHEDULER.apis):
                if api.endpoint == bw_instance.endpoint:
                    if DEBUG_MODE:
                        HEALTHCHECK_LOGGER.debug(
                            f"Removing {bw_instance.endpoint} from the list "
                            f"of reachable instances")
                    del SCHEDULER.apis[i]
                    break

    HEALTHCHECK_EVENT.clear()
    if DEBUG_MODE:
        HEALTHCHECK_LOGGER.debug("Healthcheck job completed")


# Backup current configuration for failover purposes.
# Creates a snapshot of working configs, custom configs, and cache
# to enable rollback if new configurations fail to load properly.
def backup_failover():
    if DEBUG_MODE:
        LOGGER.debug("backup_failover() called")
    
    BACKING_UP_FAILOVER.set()
    LOGGER.debug("Starting failover backup")
    try:
        rmtree(FAILOVER_PATH, ignore_errors=True)
        FAILOVER_PATH.mkdir(parents=True, exist_ok=True)

        for src, dst_name in (
            (CONFIG_PATH, "config"),
            (CUSTOM_CONFIGS_PATH, "custom_configs"),
            (CACHE_PATH, "cache"),
        ):
            try:
                if DEBUG_MODE:
                    LOGGER.debug(f"Copying {src} to {FAILOVER_PATH / dst_name}")
                copytree(src, FAILOVER_PATH / dst_name, dirs_exist_ok=True)
            except Exception:
                LOGGER.exception(f"Error copying {src} to failover path")

        success, err = JOB.cache_dir(FAILOVER_PATH, job_name="failover-backup")
        if not success:
            LOGGER.error(f"Error while caching failover backup: {err}")
        else:
            if DEBUG_MODE:
                LOGGER.debug("Failover backup completed successfully")
    except Exception:
        LOGGER.exception("Failed to initialize failover backup")
    finally:
        BACKING_UP_FAILOVER.clear()


if __name__ == "__main__":
    try:
        # Handle Docker secrets first
        docker_secrets = handle_docker_secrets()
        if docker_secrets:
            LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")
            if DEBUG_MODE:
                LOGGER.debug(f"Docker secrets keys: "
                            f"{list(docker_secrets.keys())}")
            # Update environment with secrets
            environ.update(docker_secrets)

        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            LOGGER.error("Scheduler is already running, skipping execution ...")
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")
        if DEBUG_MODE:
            LOGGER.debug(f"Written PID {getpid()} to {pid_path}")

        del pid_path

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument("--variables", type=str, 
                           help="path to the file containing environment "
                                "variables")
        args = parser.parse_args()

        tmp_variables_path = (Path(args.variables) if args.variables 
                             else NGINX_TMP_VARIABLES_PATH)
        if DEBUG_MODE:
            LOGGER.debug(f"Using variables file: {tmp_variables_path}")

        dotenv_env = {}
        if tmp_variables_path.is_file():
            with tmp_variables_path.open() as f:
                dotenv_env = dict(line.strip().split("=", 1) for line in f 
                                 if (line.strip() and not line.startswith("#") 
                                     and "=" in line))
            if DEBUG_MODE:
                LOGGER.debug(f"Loaded {len(dotenv_env)} variables from "
                            f"{tmp_variables_path}")

        SCHEDULER = JobScheduler(
            LOGGER, 
            db=Database(
                LOGGER, 
                sqlalchemy_string=dotenv_env.get(
                    "DATABASE_URI", 
                    getenv("DATABASE_URI", None))))  # type: ignore

        JOB = Job(LOGGER, __file__, SCHEDULER.db)

        APPLYING_CHANGES.set()

        if SCHEDULER.db.readonly:
            LOGGER.warning("The database is read-only, no need to save the "
                           "changes in the configuration as they will not be "
                           "saved")
        else:
            # run the config saver
            if DEBUG_MODE:
                LOGGER.debug("Running initial config saver...")
            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", 
                                          "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    "--first-run",
                ]
                + (["--variables", tmp_variables_path.as_posix()] 
                   if args.variables else []),
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not "
                             "work as expected...")

        ready = False
        while not ready:
            db_metadata = SCHEDULER.db.get_metadata()
            if (isinstance(db_metadata, str) or 
                not db_metadata["is_initialized"]):
                LOGGER.warning("Database is not initialized, retrying in "
                               "5s ...")
            else:
                ready = True
                if DEBUG_MODE:
                    LOGGER.debug("Database is initialized and ready")
                continue
            sleep(5)

        env = SCHEDULER.db.get_config()
        env["DATABASE_URI"] = SCHEDULER.db.database_uri
        tz = getenv("TZ")
        if tz:
            env["TZ"] = tz

        # Instantiate scheduler environment
        SCHEDULER.env = env | {"RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)}
        if DEBUG_MODE:
            LOGGER.debug(f"Scheduler environment initialized with "
                        f"{len(env)} variables")

        threads = []

        SCHEDULER.apis = []
        for db_instance in SCHEDULER.db.get_instances():
            SCHEDULER.apis.append(
                API(f"http://{db_instance['hostname']}:"
                    f"{db_instance['port']}", 
                    db_instance["server_name"]))
        if DEBUG_MODE:
            LOGGER.debug(f"Initialized {len(SCHEDULER.apis)} API instances")

        scheduler_first_start = db_metadata["scheduler_first_start"]

        LOGGER.info("Scheduler started ...")

        # Check for manually created custom configs
        # Scans the filesystem for new or modified configuration files
        # and saves them to the database when changes are detected.
        def check_configs_changes():
            if DEBUG_MODE:
                LOGGER.debug("check_configs_changes() called")
            
            # Checking if any custom config has been created by the user
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info("Checking if there are any changes in custom "
                        "configs ...")
            custom_configs = []
            db_configs = SCHEDULER.db.get_custom_configs()
            changes = False
            if DEBUG_MODE:
                LOGGER.debug(f"Found {len(db_configs)} custom configs in "
                            f"database")
            
            for file in list(CUSTOM_CONFIGS_PATH.rglob("*.conf")):
                if len(file.parts) > len(CUSTOM_CONFIGS_PATH.parts) + 3:
                    LOGGER.warning(f"Custom config file {file} is not in "
                                   f"the correct path, skipping ...")

                content = file.read_text(encoding="utf-8")
                service_id = (file.parent.name 
                             if file.parent.name not in CUSTOM_CONFIGS_DIRS 
                             else None)
                config_type = (file.parent.parent.name if service_id 
                              else file.parent.name)

                saving = True
                in_db = False
                from_template = False
                for db_conf in db_configs:
                    if (db_conf["service_id"] == service_id and 
                        db_conf["name"] == file.stem):
                        in_db = True
                        if db_conf["template"]:
                            from_template = True

                if (from_template or 
                    (not in_db and content.startswith("# CREATED BY ENV"))):
                    saving = False
                    changes = not from_template

                if saving:
                    custom_configs.append({
                        "value": content, 
                        "exploded": (service_id, config_type, file.stem)})
                    if DEBUG_MODE:
                        LOGGER.debug(f"Found custom config to save: "
                                    f"{file.stem}")

            changes = (changes or 
                      {hash(dict_to_frozenset(d)) for d in custom_configs} != 
                      {hash(dict_to_frozenset(d)) for d in db_configs})

            if changes:
                if DEBUG_MODE:
                    LOGGER.debug(f"Detected changes in custom configs, "
                                f"saving {len(custom_configs)} configs")
                try:
                    err = SCHEDULER.db.save_custom_configs(custom_configs, 
                                                          "manual")
                    if err:
                        LOGGER.error(f"Couldn't save some manually created "
                                    f"custom configs to database: {err}")
                except BaseException:
                    LOGGER.exception("Error while saving custom configs to "
                                     "database")

            generate_custom_configs(SCHEDULER.db.get_custom_configs())

        # Check for manually added plugins
        # Monitors plugin directories for new or updated external/pro plugins
        # and synchronizes them with the database when changes occur.
        def check_plugin_changes(_type: Literal["external", "pro"] = 
                                "external"):
            if DEBUG_MODE:
                LOGGER.debug(f"check_plugin_changes() called with type: "
                            f"{_type}")
            
            # Check if any external or pro plugin has been added by the user
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info(f"Checking if there are any changes in {_type} "
                        f"plugins ...")
            plugin_path = (PRO_PLUGINS_PATH if _type == "pro" 
                          else EXTERNAL_PLUGINS_PATH)
            db_plugins = SCHEDULER.db.get_plugins(_type=_type)
            if DEBUG_MODE:
                LOGGER.debug(f"Found {len(db_plugins)} {_type} plugins in "
                            f"database")
            external_plugins = []
            tmp_external_plugins = []
            
            for file in plugin_path.glob("*/plugin.json"):
                if DEBUG_MODE:
                    LOGGER.debug(f"Checking plugin: {file.parent.name}")
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", 
                                 compresslevel=9) as tar:
                        tar.add(file.parent, arcname=file.parent.name, 
                               recursive=True)
                    plugin_content.seek(0, 0)

                    with file.open("r", encoding="utf-8") as f:
                        plugin_data = json_load(f)

                    if plugin_data["id"] == "letsencrypt_dns":
                        continue

                    checksum = bytes_hash(plugin_content, algorithm="sha256")
                    common_data = plugin_data | {
                        "type": _type,
                        "page": file.parent.joinpath("ui").is_dir(),
                        "checksum": checksum,
                    }
                    jobs = common_data.pop("jobs", [])

                    with suppress(StopIteration, IndexError):
                        index = next(i for i, plugin in enumerate(db_plugins) 
                                   if plugin["id"] == common_data["id"])

                        if (checksum == db_plugins[index]["checksum"] or 
                            db_plugins[index]["method"] != "manual"):
                            continue

                    tmp_external_plugins.append(common_data.copy())

                    external_plugins.append(
                        common_data
                        | {
                            "method": "manual",
                            "data": plugin_content.getvalue(),
                        }
                        | ({"jobs": jobs} if jobs else {})
                    )

            changes = False
            if tmp_external_plugins:
                changes = ({hash(dict_to_frozenset(d)) 
                           for d in tmp_external_plugins} != 
                          {hash(dict_to_frozenset(d)) for d in db_plugins})

                if changes:
                    if DEBUG_MODE:
                        LOGGER.debug(f"Detected changes in {_type} plugins, "
                                    f"updating {len(external_plugins)} "
                                    f"plugins")
                    try:
                        err = SCHEDULER.db.update_external_plugins(
                            external_plugins, _type=_type, 
                            delete_missing=True)
                        if err:
                            LOGGER.error(f"Couldn't save some manually added "
                                        f"{_type} plugins to database: {err}")
                    except BaseException:
                        LOGGER.exception(f"Error while saving {_type} "
                                         f"plugins to database")
                else:
                    return send_file_to_bunkerweb(
                        plugin_path, 
                        "/pro_plugins" if _type == "pro" else "/plugins")

            generate_external_plugins(plugin_path)

        check_configs_changes()
        threads.extend([Thread(target=check_plugin_changes, 
                              args=("external",)), 
                       Thread(target=check_plugin_changes, 
                              args=("pro",))])

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        LOGGER.info("Running plugins download jobs ...")
        SCHEDULER.run_once(("misc", "pro"))

        db_metadata = SCHEDULER.db.get_metadata()
        if (db_metadata["pro_plugins_changed"] or 
            db_metadata["external_plugins_changed"]):
            threads.clear()

            if db_metadata["pro_plugins_changed"]:
                threads.append(Thread(target=generate_external_plugins, 
                                     args=(PRO_PLUGINS_PATH,)))
            if db_metadata["external_plugins_changed"]:
                threads.append(Thread(target=generate_external_plugins))

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            if SCHEDULER.db.readonly:
                LOGGER.warning("The database is read-only, no need to look "
                               "for changes in the plugins settings as they "
                               "will not be saved")
            else:
                # run the config saver to save potential ignored external 
                # plugins settings
                LOGGER.info("Running config saver to save potential "
                            "ignored external plugins settings ...")
                proc = subprocess_run(
                    [
                        BUNKERWEB_PATH.joinpath("gen", 
                                              "save_config.py").as_posix(),
                        "--settings",
                        BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    ]
                    + (["--variables", tmp_variables_path.as_posix()] 
                       if args.variables else []),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )
                if proc.returncode != 0:
                    LOGGER.error("Config saver failed, configuration will "
                                 "not work as expected...")

            SCHEDULER.update_jobs()
            env = SCHEDULER.db.get_config()
            env["DATABASE_URI"] = SCHEDULER.db.database_uri
            tz = getenv("TZ")
            if tz:
                env["TZ"] = tz

        LOGGER.info("Executing scheduler ...")

        del dotenv_env

        FIRST_START = True
        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []

        changed_plugins = []
        old_changes = {}
        healthcheck_job_run = False

        while True:
            threads.clear()

            while BACKING_UP_FAILOVER.is_set():
                LOGGER.warning("Waiting for the failover backup to "
                               "finish ...")
                sleep(1)

            if RUN_JOBS_ONCE:
                # Only run jobs once
                if DEBUG_MODE:
                    LOGGER.debug("Running jobs once...")
                if not SCHEDULER.reload(
                    env | {"TZ": getenv("TZ", "UTC"), 
                          "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)},
                    changed_plugins=changed_plugins,
                    ignore_plugins=("misc", "pro") if FIRST_START else (),
                ):
                    LOGGER.error("At least one job in run_once() failed")
                else:
                    LOGGER.info("All jobs in run_once() were successful")
                    if SCHEDULER.db.readonly:
                        generate_caches()
                healthcheck_job_run = False

            if CONFIG_NEED_GENERATION:
                if DEBUG_MODE:
                    LOGGER.debug("Generating configuration...")
                ret = generate_configs()
                if ret and SCHEDULER.apis:
                    # send nginx configs
                    threads.append(Thread(target=send_file_to_bunkerweb, 
                                         args=(CONFIG_PATH, "/confs")))
                    threads[-1].start()

            failover_message = ""
            try:
                success = True
                reachable = True
                if SCHEDULER.apis:
                    # send cache
                    threads.append(Thread(target=send_file_to_bunkerweb, 
                                         args=(CACHE_PATH, "/cache")))
                    threads[-1].start()

                    for thread in threads:
                        thread.join()

                    if DEBUG_MODE:
                        LOGGER.debug("Sending reload command to all "
                                    "instances...")
                    success, responses = SCHEDULER.send_to_apis(
                        "POST",
                        f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}",
                        timeout=max(RELOAD_MIN_TIMEOUT, 
                                   3 * len(env.get("SERVER_NAME", 
                                                  "www.example.com")
                                          .split(" "))),
                        response=True,
                    )
                    if not success:
                        reachable = False
                        if DEBUG_MODE:
                            LOGGER.debug("Error while reloading all "
                                        "bunkerweb instances")

                    if DEBUG_MODE:
                        LOGGER.debug(f"Reload responses: {responses}")

                    for db_instance in SCHEDULER.db.get_instances():
                        metadata = responses.get(db_instance["hostname"], {})
                        status = metadata.get("status", "down")

                        if status == "success":
                            success = True
                        else:
                            message = metadata.get("msg", 
                                                  "couldn't get message")
                            if "\n" in message:
                                message = message.split("\n", 1)[1]

                            failover_message += (f"{db_instance['hostname']}:"
                                               f"{db_instance['port']} - "
                                               f"{message}\n")

                        ret = SCHEDULER.db.update_instance(
                            db_instance["hostname"],
                            (
                                "up"
                                if status == "success"
                                else ("failover" 
                                     if responses.get(
                                         db_instance["hostname"], {})
                                       .get("msg") == "config check failed" 
                                     else "down")
                            ),
                        )
                        if ret:
                            LOGGER.error(
                                f"Couldn't update instance "
                                f"{db_instance['hostname']} status to "
                                f"{'up' if status == 'success' else 'down'} "
                                f"in the database: {ret}"
                            )

                        if status == "success":
                            found = False
                            for api in SCHEDULER.apis:
                                if api.endpoint == (
                                    f"http://{db_instance['hostname']}:"
                                    f"{db_instance['port']}/"):
                                    found = True
                                    break
                            if not found:
                                if DEBUG_MODE:
                                    LOGGER.debug(f"Adding "
                                                f"{db_instance['hostname']}:"
                                                f"{db_instance['port']} to "
                                                f"the list of reachable "
                                                f"instances")
                                SCHEDULER.apis.append(
                                    API(f"http://{db_instance['hostname']}:"
                                        f"{db_instance['port']}", 
                                        db_instance["server_name"]))
                            continue

                        for i, api in enumerate(SCHEDULER.apis):
                            if api.endpoint == (
                                f"http://{db_instance['hostname']}:"
                                f"{db_instance['port']}/"):
                                if DEBUG_MODE:
                                    LOGGER.debug(f"Removing "
                                                f"{db_instance['hostname']}:"
                                                f"{db_instance['port']} from "
                                                f"the list of reachable "
                                                f"instances")
                                del SCHEDULER.apis[i]
                                break
                else:
                    for thread in threads:
                        thread.join()

                    LOGGER.warning("No BunkerWeb instance found, skipping "
                                   "bunkerweb reload ...")
            except BaseException:
                LOGGER.exception("Exception while reloading after running "
                                 "jobs once scheduling")

            try:
                SCHEDULER.db.set_metadata({"failover": not success, 
                                          "failover_message": 
                                          failover_message})
            except BaseException:
                LOGGER.exception("Error while setting failover to true in "
                                 "the database")

            try:
                if not success and reachable:
                    LOGGER.error("Error while reloading bunkerweb, failing "
                                 "over to last working configuration ...")
                    if (
                        not FAILOVER_PATH.joinpath("config").is_dir()
                        or not FAILOVER_PATH.joinpath("custom_configs").is_dir()
                        or not FAILOVER_PATH.joinpath("cache").is_dir()
                    ):
                        LOGGER.error("No failover configuration found, "
                                     "ignoring failover ...")
                    else:
                        # Failover to last working configuration
                        if DEBUG_MODE:
                            LOGGER.debug("Restoring failover configuration...")
                        if SCHEDULER.apis:
                            tmp_threads = [
                                Thread(target=send_file_to_bunkerweb, 
                                      args=(FAILOVER_PATH.joinpath("config"), 
                                           "/confs")),
                                Thread(target=send_file_to_bunkerweb, 
                                      args=(FAILOVER_PATH.joinpath("cache"), 
                                           "/cache")),
                                Thread(target=send_file_to_bunkerweb, 
                                      args=(FAILOVER_PATH.joinpath(
                                          "custom_configs"), 
                                           "/custom_configs")),
                            ]
                            for thread in tmp_threads:
                                thread.start()

                            for thread in tmp_threads:
                                thread.join()

                        if not SCHEDULER.send_to_apis(
                            "POST",
                            f"/reload?test={'no' if DISABLE_CONFIGURATION_TESTING else 'yes'}",
                            timeout=max(RELOAD_MIN_TIMEOUT, 
                                       3 * len(env.get("SERVER_NAME", 
                                                      "www.example.com")
                                              .split(" "))),
                        )[0]:
                            LOGGER.error("Error while reloading bunkerweb "
                                         "with failover configuration, "
                                         "skipping ...")
                elif not reachable:
                    LOGGER.warning("No BunkerWeb instance is reachable, "
                                   "skipping failover ...")
                else:
                    LOGGER.info("Successfully reloaded bunkerweb")
                    Thread(target=backup_failover).start()
            except BaseException:
                LOGGER.exception("Exception while executing failover logic")

            try:
                ret = SCHEDULER.db.checked_changes(CHANGES, 
                                                  plugins_changes="all")
                if ret:
                    LOGGER.error(f"An error occurred when setting the "
                                f"changes to checked in the database : {ret}")
            except BaseException:
                LOGGER.exception("Error while setting changes to checked "
                                 "in the database")

            FIRST_START = False
            NEED_RELOAD = False
            RUN_JOBS_ONCE = False
            CONFIG_NEED_GENERATION = False
            CONFIGS_NEED_GENERATION = False
            PLUGINS_NEED_GENERATION = False
            PRO_PLUGINS_NEED_GENERATION = False
            INSTANCES_NEED_GENERATION = False
            changed_plugins.clear()

            if scheduler_first_start:
                try:
                    ret = SCHEDULER.db.set_metadata(
                        {"scheduler_first_start": False})

                    if ret == ("The database is read-only, the changes will "
                              "not be saved"):
                        LOGGER.warning("The database is read-only, the "
                                       "scheduler first start will not be "
                                       "saved")
                    elif ret:
                        LOGGER.error(f"An error occurred when setting the "
                                    f"scheduler first start : {ret}")
                except BaseException:
                    LOGGER.exception("Error while setting the scheduler "
                                     "first start")
                finally:
                    scheduler_first_start = False

            if not HEALTHY_PATH.is_file():
                HEALTHY_PATH.write_text(datetime.now().astimezone()
                                       .isoformat(), encoding="utf-8")

            APPLYING_CHANGES.clear()
            if not healthcheck_job_run:
                if DEBUG_MODE:
                    LOGGER.debug("Scheduling healthcheck job ...")
                schedule_every(HEALTHCHECK_INTERVAL).seconds.do(healthcheck_job)
                healthcheck_job_run = True

            # infinite schedule for the jobs
            LOGGER.info("Executing job scheduler ...")
            errors = 0
            while RUN and not NEED_RELOAD:
                try:
                    sleep(3 if SCHEDULER.db.readonly else 1)
                    run_pending()
                    SCHEDULER.run_pending()
                    current_time = datetime.now().astimezone()

                    while (DB_LOCK_FILE.is_file() and 
                           DB_LOCK_FILE.stat().st_ctime + 30 > 
                           current_time.timestamp()):
                        if DEBUG_MODE:
                            LOGGER.debug("Database is locked, waiting for it "
                                        "to be unlocked (timeout: 30s) ...")
                        sleep(1)

                    DB_LOCK_FILE.unlink(missing_ok=True)

                    db_metadata = SCHEDULER.db.get_metadata()

                    if isinstance(db_metadata, str):
                        raise Exception(f"An error occurred when checking "
                                       f"for changes in the database : "
                                       f"{db_metadata}")

                    changes = {
                        "pro_plugins_changed": 
                            db_metadata["pro_plugins_changed"],
                        "last_pro_plugins_change": 
                            db_metadata["last_pro_plugins_change"],
                        "external_plugins_changed": 
                            db_metadata["external_plugins_changed"],
                        "last_external_plugins_change": 
                            db_metadata["last_external_plugins_change"],
                        "custom_configs_changed": 
                            db_metadata["custom_configs_changed"],
                        "last_custom_configs_change": 
                            db_metadata["last_custom_configs_change"],
                        "plugins_config_changed": 
                            db_metadata["plugins_config_changed"],
                        "instances_changed": db_metadata["instances_changed"],
                        "last_instances_change": 
                            db_metadata["last_instances_change"],
                    }

                    if SCHEDULER.db.readonly and changes == old_changes:
                        continue

                    # check if the plugins have changed since last time
                    if changes["pro_plugins_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_pro_plugins_change"]
                        or not old_changes
                        or old_changes["last_pro_plugins_change"] != 
                           changes["last_pro_plugins_change"]
                    ):
                        LOGGER.info("Pro plugins changed, generating ...")
                        PRO_PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    if changes["external_plugins_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_external_plugins_change"]
                        or not old_changes
                        or old_changes["last_external_plugins_change"] != 
                           changes["last_external_plugins_change"]
                    ):
                        LOGGER.info("External plugins changed, generating ...")
                        PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    # check if the custom configs have changed since last time
                    if changes["custom_configs_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_custom_configs_change"]
                        or not old_changes
                        or old_changes["last_custom_configs_change"] != 
                           changes["last_custom_configs_change"]
                    ):
                        LOGGER.info("Custom configs changed, generating ...")
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # check if the config have changed since last time
                    if changes["plugins_config_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_plugins_config_change"]
                        or not old_changes
                        or old_changes["plugins_config_changed"] != 
                           changes["plugins_config_changed"]
                    ):
                        LOGGER.info("Plugins config changed, generating ...")
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True
                        changed_plugins = list(changes["plugins_config_changed"])
                        if DEBUG_MODE:
                            LOGGER.debug(f"Changed plugins: {changed_plugins}")

                    # check if the instances have changed since last time
                    if changes["instances_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_instances_change"]
                        or not old_changes
                        or old_changes["last_instances_change"] != 
                           changes["last_instances_change"]
                    ):
                        LOGGER.info("Instances changed, generating ...")
                        INSTANCES_NEED_GENERATION = True
                        PRO_PLUGINS_NEED_GENERATION = True
                        PLUGINS_NEED_GENERATION = True
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    old_changes = changes.copy()
                except BaseException:
                    LOGGER.exception("Exception in scheduler main loop")
                    if errors > 5:
                        LOGGER.error("Too many errors in scheduler main "
                                     "loop, exiting...")
                        stop(1)
                    errors += 1
                    sleep(5)

            if NEED_RELOAD:
                APPLYING_CHANGES.set()
                if DEBUG_MODE:
                    LOGGER.debug(f"Changes detected: {changes}")
                SCHEDULER.try_database_readonly(force=True)
                CHANGES.clear()

                if INSTANCES_NEED_GENERATION:
                    CHANGES.append("instances")
                    SCHEDULER.apis = []
                    for db_instance in SCHEDULER.db.get_instances():
                        SCHEDULER.apis.append(
                            API(f"http://{db_instance['hostname']}:"
                                f"{db_instance['port']}", 
                                db_instance["server_name"]))
                    if DEBUG_MODE:
                        LOGGER.debug(f"Updated API instances list, now "
                                    f"{len(SCHEDULER.apis)} instances")

                if CONFIGS_NEED_GENERATION:
                    CHANGES.append("custom_configs")
                    generate_custom_configs(
                        SCHEDULER.db.get_custom_configs())

                if PLUGINS_NEED_GENERATION:
                    CHANGES.append("external_plugins")
                    generate_external_plugins()
                    SCHEDULER.update_jobs()

                if PRO_PLUGINS_NEED_GENERATION:
                    CHANGES.append("pro_plugins")
                    generate_external_plugins(PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                if CONFIG_NEED_GENERATION:
                    CHANGES.append("config")
                    old_env = env.copy()
                    env = SCHEDULER.db.get_config()
                    if DEBUG_MODE:
                        LOGGER.debug("Reloaded configuration from database")
                    if (old_env.get("API_HTTP_PORT", "5000") != 
                        env.get("API_HTTP_PORT", "5000") or 
                        old_env.get("API_SERVER_NAME", "bwapi") != 
                        env.get("API_SERVER_NAME", "bwapi")):
                        if DEBUG_MODE:
                            LOGGER.debug("API configuration changed, "
                                        "updating instances...")
                        err = SCHEDULER.db.update_instances(
                            [
                                {
                                    "hostname": db_instance["hostname"],
                                    "name": db_instance["name"],
                                    "env": {
                                        "API_HTTP_PORT": 
                                            env.get("API_HTTP_PORT", "5000"),
                                        "API_SERVER_NAME": 
                                            env.get("API_SERVER_NAME", "bwapi"),
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
                            LOGGER.error(f"Couldn't update instances in the "
                                        f"database: {err}")
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

    except:
        LOGGER.exception("Exception while executing scheduler")
        stop(1)
