#!/usr/bin/env python3

from argparse import ArgumentParser
from contextlib import suppress
from datetime import datetime
from io import BytesIO
from itertools import chain
from json import load as json_load
from os import _exit, environ, getenv, getpid, sep
from os.path import join
from pathlib import Path
from shutil import copy, rmtree, copytree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import TarFile, open as tar_open
from threading import Event, Lock, Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from dotenv import dotenv_values
from schedule import every as schedule_every, run_pending

from common_utils import bytes_hash, dict_to_frozenset, get_version  # type: ignore
from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler
from jobs import Job  # type: ignore
from API import API  # type: ignore

# from ApiCaller import ApiCaller  # type: ignore  # TODO: uncomment when the healthcheck endpoint is ready @fl0ppy-d1sk

APPLYING_CHANGES = Event()
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
    CUSTOM_CONFIGS_PATH.joinpath(custom_config_dir).mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path(sep, "etc", "nginx")

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")
TMP_PATH.mkdir(parents=True, exist_ok=True)

FAILOVER_PATH = TMP_PATH.joinpath("failover")
FAILOVER_PATH.mkdir(parents=True, exist_ok=True)

HEALTHY_PATH = TMP_PATH.joinpath("scheduler.healthy")

SCHEDULER_TMP_ENV_PATH = TMP_PATH.joinpath("scheduler.env")
SCHEDULER_TMP_ENV_PATH.touch()

DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")
LOGGER = setup_logger("Scheduler", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

HEALTHCHECK_INTERVAL = getenv("HEALTHCHECK_INTERVAL", "30")

if not HEALTHCHECK_INTERVAL.isdigit():
    LOGGER.error("HEALTHCHECK_INTERVAL must be an integer, defaulting to 30")
    HEALTHCHECK_INTERVAL = 30

HEALTHCHECK_INTERVAL = int(HEALTHCHECK_INTERVAL)
HEALTHCHECK_EVENT = Event()
HEALTHCHECK_LOGGER = setup_logger("Scheduler.Healthcheck", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

RELOAD_MIN_TIMEOUT = getenv("RELOAD_MIN_TIMEOUT", "5")

if not RELOAD_MIN_TIMEOUT.isdigit():
    LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
    RELOAD_MIN_TIMEOUT = 5

RELOAD_MIN_TIMEOUT = int(RELOAD_MIN_TIMEOUT)

SLAVE_MODE = getenv("SLAVE_MODE", "no") == "yes"
MASTER_MODE = getenv("MASTER_MODE", "no") == "yes"


def handle_stop(signum, frame):
    current_time = datetime.now().astimezone()
    while APPLYING_CHANGES.is_set() and (datetime.now().astimezone() - current_time).seconds < 30:
        LOGGER.warning("Waiting for the changes to be applied before stopping ...")
        sleep(1)

    if APPLYING_CHANGES.is_set():
        LOGGER.warning("Timeout reached, stopping without waiting for the changes to be applied ...")

    if SCHEDULER is not None:
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Function to catch SIGHUP and reload the scheduler
def handle_reload(signum, frame):
    try:
        if SCHEDULER is not None and RUN:
            if SCHEDULER.db.readonly:
                LOGGER.warning("The database is read-only, no need to save the changes in the configuration as they will not be saved")
                return

            # run the config saver
            proc = subprocess_run(
                [
                    "python3",
                    join(sep, "usr", "share", "bunkerweb", "gen", "save_config.py"),
                    "--settings",
                    join(sep, "usr", "share", "bunkerweb", "settings.json"),
                    "--variables",
                    join(sep, "etc", "bunkerweb", "variables.env"),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not work as expected...")
        else:
            LOGGER.warning("Ignored reload operation because scheduler is not running ...")
    except BaseException as e:
        LOGGER.error(f"Exception while reloading scheduler : {e}")


signal(SIGHUP, handle_reload)


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


def send_file_to_bunkerweb(file_path: Path, endpoint: str):
    assert SCHEDULER is not None, "SCHEDULER is not defined"
    LOGGER.info(f"Sending {file_path} to BunkerWeb instances ...")
    success, responses = SCHEDULER.send_files(file_path.as_posix(), endpoint, response=True)
    fails = []

    for db_instance in SCHEDULER.db.get_instances():
        index = -1
        with SCHEDULER_LOCK:
            for i, api in enumerate(SCHEDULER.apis):
                if api.endpoint == f"http://{db_instance['hostname']}:{db_instance['port']}/":
                    index = i
                    break

        status = responses.get(db_instance["hostname"], {"status": "down"}).get("status", "down")

        ret = SCHEDULER.db.update_instance(db_instance["hostname"], "up" if status == "success" else "down")
        if ret:
            LOGGER.error(f"Couldn't update instance {db_instance['hostname']} status to down in the database: {ret}")

        with SCHEDULER_LOCK:
            if status == "success":
                success = True
                if index == -1:
                    LOGGER.debug(f"Adding {db_instance['hostname']}:{db_instance['port']} to the list of reachable instances")
                    SCHEDULER.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))
            elif index != -1:
                fails.append(f"{db_instance['hostname']}:{db_instance['port']}")
                LOGGER.debug(f"Removing {db_instance['hostname']}:{db_instance['port']} from the list of reachable instances")
                del SCHEDULER.apis[index]

    if not success:
        LOGGER.error(f"Error while sending {file_path} to BunkerWeb instances")
        return
    elif not fails:
        LOGGER.info(f"Successfully sent {file_path} folder to reachable BunkerWeb instances")
        return
    LOGGER.warning(f"Error while sending {file_path} to some BunkerWeb instances, removing them from the list of reachable instances: {', '.join(fails)}")


def generate_custom_configs(configs: Optional[List[Dict[str, Any]]] = None, *, original_path: Union[Path, str] = CUSTOM_CONFIGS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    LOGGER.info("Removing old custom configs files ...")
    if original_path.is_dir():
        for file in original_path.glob("*/*"):
            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
            elif file.is_dir():
                rmtree(file, ignore_errors=True)

    if configs is None:
        assert SCHEDULER is not None
        configs = SCHEDULER.db.get_custom_configs()

    if configs:
        LOGGER.info("Generating new custom configs ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for custom_config in configs:
            try:
                if custom_config["data"]:
                    tmp_path = original_path.joinpath(
                        custom_config["type"].replace("_", "-"),
                        custom_config["service_id"] or "",
                        f"{Path(custom_config['name']).stem}.conf",
                    )
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path.write_bytes(custom_config["data"])
            except OSError as e:
                LOGGER.debug(format_exc())
                if custom_config["method"] != "manual":
                    LOGGER.error(
                        f"Error while generating custom configs \"{custom_config['name']}\"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: {e}"
                    )
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(
                    f"Error while generating custom configs \"{custom_config['name']}\"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: {e}"
                )

    if SCHEDULER and SCHEDULER.apis:
        send_file_to_bunkerweb(original_path, "/custom_configs")


def generate_external_plugins(original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)
    pro = original_path.as_posix().endswith("/pro/plugins")

    assert SCHEDULER is not None
    plugins = SCHEDULER.db.get_plugins(_type="pro" if pro else "external", with_data=True)
    assert plugins is not None, "Couldn't get plugins from database"

    # Remove old external/pro plugins files
    LOGGER.info(f"Removing old/changed {'pro ' if pro else ''}external plugins files ...")
    ignored_plugins = set()
    if original_path.is_dir():
        for file in original_path.glob("*"):
            with suppress(StopIteration, IndexError):
                index = next(i for i, plugin in enumerate(plugins) if plugin["id"] == file.name)

                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(file, arcname=file.name, recursive=True)
                    plugin_content.seek(0, 0)
                    if bytes_hash(plugin_content, algorithm="sha256") == plugins[index]["checksum"]:
                        ignored_plugins.add(file.name)
                        continue
                    LOGGER.debug(f"Checksum of {file} has changed, removing it ...")

            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
            elif file.is_dir():
                rmtree(file, ignore_errors=True)

    if plugins:
        LOGGER.info(f"Generating new {'pro ' if pro else ''}external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            if plugin["id"] in ignored_plugins:
                continue

            try:
                if plugin["data"]:
                    with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                        try:
                            tar.extractall(original_path, filter="fully_trusted")
                        except TypeError:
                            tar.extractall(original_path)

                    for job_file in chain(original_path.joinpath(plugin["id"], "jobs").glob("*"), original_path.joinpath(plugin["id"], "bwcli").glob("*")):
                        job_file.chmod(job_file.stat().st_mode | S_IEXEC)
            except OSError as e:
                LOGGER.debug(format_exc())
                if plugin["method"] != "manual":
                    LOGGER.error(f"Error while generating {'pro ' if pro else ''}external plugins \"{plugin['name']}\": {e}")
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while generating {'pro ' if pro else ''}external plugins \"{plugin['name']}\": {e}")

    if SCHEDULER and SCHEDULER.apis:
        LOGGER.info(f"Sending {'pro ' if pro else ''}external plugins to BunkerWeb")
        send_file_to_bunkerweb(original_path, "/pro_plugins" if original_path.as_posix().endswith("/pro/plugins") else "/plugins")


def generate_caches():
    assert SCHEDULER is not None

    job_cache_files = SCHEDULER.db.get_jobs_cache_files()
    plugin_cache_files = set()
    ignored_dirs = set()

    for job_cache_file in job_cache_files:
        job_path = Path(sep, "var", "cache", "bunkerweb", job_cache_file["plugin_id"])
        cache_path = job_path.joinpath(job_cache_file["service_id"] or "", job_cache_file["file_name"])
        plugin_cache_files.add(cache_path)

        try:
            if job_cache_file["file_name"].endswith(".tgz"):
                extract_path = cache_path.parent
                if job_cache_file["file_name"].startswith("folder:"):
                    extract_path = Path(job_cache_file["file_name"].split("folder:", 1)[1].rsplit(".tgz", 1)[0])
                ignored_dirs.add(extract_path.as_posix())
                rmtree(extract_path, ignore_errors=True)
                extract_path.mkdir(parents=True, exist_ok=True)
                with tar_open(fileobj=BytesIO(job_cache_file["data"]), mode="r:gz") as tar:
                    assert isinstance(tar, TarFile)
                    try:
                        for member in tar.getmembers():
                            try:
                                tar.extract(member, path=extract_path)
                            except Exception as e:
                                LOGGER.error(f"Error extracting {member.name}: {e}")
                    except Exception as e:
                        LOGGER.error(f"Error extracting tar file: {e}")
                LOGGER.debug(f"Restored cache directory {extract_path}")
                continue
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(job_cache_file["data"])
            LOGGER.debug(f"Restored cache file {job_cache_file['file_name']}")
        except BaseException as e:
            LOGGER.error(f"Exception while restoring cache file {job_cache_file['file_name']} :\n{e}")

    if job_path.is_dir():
        for file in job_path.rglob("*"):
            if file.as_posix().startswith(tuple(ignored_dirs)):
                continue

            LOGGER.debug(f"Checking if {file} should be removed")
            if file not in plugin_cache_files and file.is_file():
                LOGGER.debug(f"Removing non-cached file {file}")
                file.unlink(missing_ok=True)
                if file.parent.is_dir() and not list(file.parent.iterdir()):
                    LOGGER.debug(f"Removing empty directory {file.parent}")
                    rmtree(file.parent, ignore_errors=True)
                    if file.parent == job_path:
                        break
            elif file.is_dir() and not list(file.iterdir()):
                LOGGER.debug(f"Removing empty directory {file}")
                rmtree(file, ignore_errors=True)


def run_in_slave_mode():  # TODO: Refactor this feature
    assert SCHEDULER is not None

    ready = False
    while not ready:
        db_metadata = SCHEDULER.db.get_metadata()
        env = SCHEDULER.db.get_config()
        if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
            LOGGER.warning("Database is not initialized, retrying in 5s ...")
        elif not db_metadata["first_config_saved"] or not env:
            LOGGER.warning("Database doesn't have any config saved yet, retrying in 5s ...")
        else:
            ready = True
            continue
        sleep(5)

    tz = getenv("TZ")
    if tz:
        env["TZ"] = tz

    # Instantiate scheduler environment
    SCHEDULER.env = env | {"LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", env.get("LOG_LEVEL", "notice")), "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)}

    generate_custom_configs()
    threads = [
        Thread(target=generate_external_plugins),
        Thread(target=generate_external_plugins, args=(PRO_PLUGINS_PATH,)),
        Thread(target=generate_caches),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Gen config
    content = ""
    for k, v in env.items():
        content += f"{k}={v}\n"
    SCHEDULER_TMP_ENV_PATH.write_text(content)
    proc = subprocess_run(
        [
            "python3",
            join(sep, "usr", "share", "bunkerweb", "gen", "main.py"),
            "--settings",
            join(sep, "usr", "share", "bunkerweb", "settings.json"),
            "--templates",
            join(sep, "usr", "share", "bunkerweb", "confs"),
            "--output",
            CONFIG_PATH.as_posix(),
            "--variables",
            SCHEDULER_TMP_ENV_PATH.as_posix(),
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        check=False,
    )
    if proc.returncode != 0:
        LOGGER.error("Config generator failed, configuration will not work as expected...")

    # TODO : check nginx status + check DB status
    while True:
        sleep(5)


def healthcheck_job():
    if HEALTHCHECK_EVENT.is_set():
        HEALTHCHECK_LOGGER.warning("Healthcheck job is already running, skipping execution ...")
        return

    try:
        assert SCHEDULER is not None
    except AssertionError:
        return

    HEALTHCHECK_EVENT.set()

    for db_instance in SCHEDULER.db.get_instances():
        bw_instance = API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"])
        try:
            sent, err, status, resp = bw_instance.request("GET", "ping")
            # sent, err, status, resp = bw_instance.request("GET", "health") # TODO: use health instead when the healthcheck endpoint is ready @fl0ppy-d1sk

            success = True
            if not sent:
                HEALTHCHECK_LOGGER.warning(
                    f"Can't send API request to {bw_instance.endpoint}health : {err}, healthcheck will be retried in {HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False
            elif status != 200:
                HEALTHCHECK_LOGGER.warning(
                    f"Error while sending API request to {bw_instance.endpoint}health : status = {resp['status']}, msg = {resp['msg']}, healthcheck will be retried in {HEALTHCHECK_INTERVAL} seconds ..."
                )
                success = False

            if not success:
                ret = SCHEDULER.db.update_instance(db_instance["hostname"], "down")
                if ret:
                    HEALTHCHECK_LOGGER.error(f"Couldn't update instance {bw_instance.endpoint} status to down in the database: {ret}")

                for i, api in enumerate(SCHEDULER.apis):
                    if api.endpoint == bw_instance.endpoint:
                        HEALTHCHECK_LOGGER.debug(f"Removing {bw_instance.endpoint} from the list of reachable instances")
                        del SCHEDULER.apis[i]
                        break
                continue

            # if resp["state"] == "loading": # TODO: uncomment when the healthcheck endpoint is ready @fl0ppy-d1sk
            #     HEALTHCHECK_LOGGER.info(f"Instance {bw_instance.endpoint} is loading, sending config ...")
            #     api_caller = ApiCaller([bw_instance])
            #     api_caller.send_files(CUSTOM_CONFIGS_PATH, "/custom_configs")
            #     api_caller.send_files(EXTERNAL_PLUGINS_PATH, "/plugins")
            #     api_caller.send_files(PRO_PLUGINS_PATH, "/pro_plugins")
            #     api_caller.send_files(join(sep, "etc", "nginx"), "/confs")
            #     api_caller.send_files(CACHE_PATH, "/cache")
            #     if not api_caller.send_to_apis("POST", "/reload")[0]:
            #         HEALTHCHECK_LOGGER.error(f"Error while reloading instance {bw_instance.endpoint}")
            #         ret = SCHEDULER.db.update_instance(db_instance["hostname"], "loading")
            #         if ret:
            #             HEALTHCHECK_LOGGER.error(f"Couldn't update instance {bw_instance.endpoint} status to loading in the database: {ret}")
            #         continue
            #     HEALTHCHECK_LOGGER.info(f"Successfully reloaded instance {bw_instance.endpoint}")
            # elif resp["state"] == "down":
            #     HEALTHCHECK_LOGGER.warning(f"Instance {bw_instance.endpoint} is down")
            #     ret = SCHEDULER.db.update_instance(db_instance["hostname"], "down")
            #     if ret:
            #         HEALTHCHECK_LOGGER.error(f"Couldn't update instance {bw_instance.endpoint} status to down in the database: {ret}")
            #     for i, api in enumerate(SCHEDULER.apis):
            #         if api.endpoint == bw_instance.endpoint:
            #             HEALTHCHECK_LOGGER.debug(f"Removing {bw_instance.endpoint} from the list of reachable instances")
            #             del SCHEDULER.apis[i]
            #             break
            #     continue

            ret = SCHEDULER.db.update_instance(db_instance["hostname"], "up")
            if ret:
                HEALTHCHECK_LOGGER.error(f"Couldn't update instance {bw_instance.endpoint} status to down in the database: {ret}")

            found = False
            for api in SCHEDULER.apis:
                if api.endpoint == bw_instance.endpoint:
                    found = True
                    break
            if not found:
                HEALTHCHECK_LOGGER.debug(f"Adding {bw_instance.endpoint} to the list of reachable instances")
                SCHEDULER.apis.append(bw_instance)
        except BaseException as e:
            HEALTHCHECK_LOGGER.error(f"Exception while checking instance {bw_instance.endpoint}: {e}")
            for i, api in enumerate(SCHEDULER.apis):
                if api.endpoint == bw_instance.endpoint:
                    HEALTHCHECK_LOGGER.debug(f"Removing {bw_instance.endpoint} from the list of reachable instances")
                    del SCHEDULER.apis[i]
                    break

    HEALTHCHECK_EVENT.clear()


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            LOGGER.error("Scheduler is already running, skipping execution ...")
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")

        del pid_path

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        tmp_variables_path = Path(args.variables or join(sep, "var", "tmp", "bunkerweb", "variables.env"))
        nginx_variables_path = CONFIG_PATH.joinpath("variables.env")
        dotenv_env = dotenv_values(tmp_variables_path.as_posix())

        SCHEDULER = JobScheduler(environ, LOGGER, db=Database(LOGGER, sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None))))  # type: ignore

        JOB = Job(LOGGER, SCHEDULER.db)

        if SLAVE_MODE:
            run_in_slave_mode()
            stop(1)

        APPLYING_CHANGES.set()

        db_version = SCHEDULER.db.get_version()
        if not db_version.startswith("Error") and db_version != get_version():
            LOGGER.warning("BunkerWeb version changed, creating a backup of the database and proceeding with the upgrade ...")
            SCHEDULER.env = {
                "DATABASE_URI": SCHEDULER.db.database_uri,
                "USE_BACKUP": "yes",
                "FORCE_BACKUP": "yes",
                "BACKUP_SCHEDULE": "daily",
                "BACKUP_ROTATION": "7",
                "BACKUP_DIRECTORY": "/var/lib/bunkerweb/upgrade_backups",
                "LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "notice")),
                "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT),
            }

            if not SCHEDULER.run_single("backup-data"):
                LOGGER.error("backup-data job failed, stopping ...")
                stop(1)
            LOGGER.info("Backup completed successfully, if you want to restore the backup, you can find it in /var/lib/bunkerweb/upgrade_backups")

        if SCHEDULER.db.readonly:
            LOGGER.warning("The database is read-only, no need to save the changes in the configuration as they will not be saved")
        else:
            # run the config saver
            proc = subprocess_run(
                [
                    "python3",
                    join(sep, "usr", "share", "bunkerweb", "gen", "save_config.py"),
                    "--settings",
                    join(sep, "usr", "share", "bunkerweb", "settings.json"),
                    "--first-run",
                ]
                + (["--variables", tmp_variables_path.as_posix()] if args.variables else []),
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not work as expected...")

        ready = False
        while not ready:
            db_metadata = SCHEDULER.db.get_metadata()
            if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
                LOGGER.warning("Database is not initialized, retrying in 5s ...")
            else:
                ready = True
                continue
            sleep(5)

        env = SCHEDULER.db.get_config()
        env["DATABASE_URI"] = SCHEDULER.db.database_uri
        tz = getenv("TZ")
        if tz:
            env["TZ"] = tz

        # Instantiate scheduler environment
        SCHEDULER.env = env | {"LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", env.get("LOG_LEVEL", "notice")), "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)}

        threads = []

        SCHEDULER.apis = []
        for db_instance in SCHEDULER.db.get_instances():
            SCHEDULER.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))

        scheduler_first_start = db_metadata["scheduler_first_start"]

        LOGGER.info("Scheduler started ...")

        def check_configs_changes():
            # Checking if any custom config has been created by the user
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info("Checking if there are any changes in custom configs ...")
            custom_configs = []
            db_configs = SCHEDULER.db.get_custom_configs()
            changes = False
            for file in CUSTOM_CONFIGS_PATH.rglob("*.conf"):
                if len(file.parts) > len(CUSTOM_CONFIGS_PATH.parts) + 3:
                    LOGGER.warning(f"Custom config file {file} is not in the correct path, skipping ...")

                content = file.read_text(encoding="utf-8")
                service_id = file.parent.name if file.parent.name not in CUSTOM_CONFIGS_DIRS else None
                config_type = file.parent.parent.name if service_id else file.parent.name

                saving = True
                in_db = False
                from_template = False
                for db_conf in db_configs:
                    if db_conf["service_id"] == service_id and db_conf["name"] == file.stem:
                        in_db = True
                        if db_conf["template"]:
                            from_template = True

                if from_template or (not in_db and content.startswith("# CREATED BY ENV")):
                    saving = False
                    changes = not from_template

                if saving:
                    custom_configs.append({"value": content, "exploded": (service_id, config_type, file.stem)})

            changes = changes or {hash(dict_to_frozenset(d)) for d in custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs}

            if changes:
                try:
                    err = SCHEDULER.db.save_custom_configs(custom_configs, "manual")
                    if err:
                        LOGGER.error(f"Couldn't save some manually created custom configs to database: {err}")
                except BaseException as e:
                    LOGGER.error(f"Error while saving custom configs to database: {e}")

            generate_custom_configs(SCHEDULER.db.get_custom_configs())

        def check_plugin_changes(_type: Literal["external", "pro"] = "external"):
            # Check if any external or pro plugin has been added by the user
            assert SCHEDULER is not None, "SCHEDULER is not defined"
            LOGGER.info(f"Checking if there are any changes in {_type} plugins ...")
            plugin_path = PRO_PLUGINS_PATH if _type == "pro" else EXTERNAL_PLUGINS_PATH
            db_plugins = SCHEDULER.db.get_plugins(_type=_type)
            external_plugins = []
            tmp_external_plugins = []
            for file in plugin_path.glob("*/plugin.json"):
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(file.parent, arcname=file.parent.name, recursive=True)
                    plugin_content.seek(0, 0)

                    with file.open("r", encoding="utf-8") as f:
                        plugin_data = json_load(f)

                    checksum = bytes_hash(plugin_content, algorithm="sha256")
                    common_data = plugin_data | {
                        "type": _type,
                        "page": file.parent.joinpath("ui").is_dir(),
                        "checksum": checksum,
                    }
                    jobs = common_data.pop("jobs", [])

                    with suppress(StopIteration, IndexError):
                        index = next(i for i, plugin in enumerate(db_plugins) if plugin["id"] == common_data["id"])

                        if checksum == db_plugins[index]["checksum"] or db_plugins[index]["method"] != "manual":
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
                changes = {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != {hash(dict_to_frozenset(d)) for d in db_plugins}

                if changes:
                    try:
                        err = SCHEDULER.db.update_external_plugins(external_plugins, _type=_type, delete_missing=True)
                        if err:
                            LOGGER.error(f"Couldn't save some manually added {_type} plugins to database: {err}")
                    except BaseException as e:
                        LOGGER.error(f"Error while saving {_type} plugins to database: {e}")
                else:
                    return send_file_to_bunkerweb(plugin_path, "/pro_plugins" if _type == "pro" else "/plugins")

            generate_external_plugins(plugin_path)

        check_configs_changes()
        threads.extend([Thread(target=check_plugin_changes, args=("external",)), Thread(target=check_plugin_changes, args=("pro",))])

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        LOGGER.info("Running plugins download jobs ...")

        if not SCHEDULER.run_single("download-plugins"):
            LOGGER.warning("download-plugins job failed at first start, plugins settings set by the user may not be up to date ...")
        if not SCHEDULER.run_single("download-pro-plugins"):
            LOGGER.warning("download-pro-plugins job failed at first start, pro plugins settings set by the user may not be up to date ...")

        db_metadata = SCHEDULER.db.get_metadata()
        if db_metadata["pro_plugins_changed"] or db_metadata["external_plugins_changed"]:
            threads.clear()

            if db_metadata["pro_plugins_changed"]:
                threads.append(Thread(target=generate_external_plugins, args=(PRO_PLUGINS_PATH,)))
            if db_metadata["external_plugins_changed"]:
                threads.append(Thread(target=generate_external_plugins))

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            if SCHEDULER.db.readonly:
                LOGGER.warning("The database is read-only, no need to look for changes in the plugins settings as they will not be saved")
            else:
                # run the config saver to save potential ignored external plugins settings
                LOGGER.info("Running config saver to save potential ignored external plugins settings ...")
                proc = subprocess_run(
                    [
                        "python3",
                        join(sep, "usr", "share", "bunkerweb", "gen", "save_config.py"),
                        "--settings",
                        join(sep, "usr", "share", "bunkerweb", "settings.json"),
                    ]
                    + (["--variables", tmp_variables_path.as_posix()] if args.variables else []),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )
                if proc.returncode != 0:
                    LOGGER.error("Config saver failed, configuration will not work as expected...")

            SCHEDULER.update_jobs()
            env = SCHEDULER.db.get_config()
            env["DATABASE_URI"] = SCHEDULER.db.database_uri
            tz = getenv("TZ")
            if tz:
                env["TZ"] = tz

        LOGGER.info("Executing scheduler ...")

        del dotenv_env

        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []

        changed_plugins = []
        old_changes = {}

        while True:
            threads.clear()

            if RUN_JOBS_ONCE:
                # Only run jobs once
                if not SCHEDULER.reload(
                    env
                    | {
                        "TZ": getenv("TZ", "UTC"),
                        "LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", env.get("LOG_LEVEL", "notice")),
                        "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT),
                    },
                    changed_plugins=changed_plugins,
                ):
                    LOGGER.error("At least one job in run_once() failed")
                else:
                    LOGGER.info("All jobs in run_once() were successful")
                    if SCHEDULER.db.readonly:
                        generate_caches()

            if CONFIG_NEED_GENERATION:
                content = ""
                for k, v in env.items():
                    content += f"{k}={v}\n"
                SCHEDULER_TMP_ENV_PATH.write_text(content)
                # run the generator
                proc = subprocess_run(
                    [
                        "python3",
                        join(sep, "usr", "share", "bunkerweb", "gen", "main.py"),
                        "--settings",
                        join(sep, "usr", "share", "bunkerweb", "settings.json"),
                        "--templates",
                        join(sep, "usr", "share", "bunkerweb", "confs"),
                        "--output",
                        CONFIG_PATH.as_posix(),
                        "--variables",
                        SCHEDULER_TMP_ENV_PATH.as_posix(),
                    ]
                    + (["--no-linux-reload"] if MASTER_MODE else []),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )

                if proc.returncode != 0:
                    LOGGER.error("Config generator failed, configuration will not work as expected...")
                else:
                    copy(nginx_variables_path.as_posix(), join(sep, "var", "tmp", "bunkerweb", "variables.env"))

                    if SCHEDULER.apis:
                        # send nginx configs
                        threads.append(Thread(target=send_file_to_bunkerweb, args=(CONFIG_PATH, "/confs")))
                        threads[-1].start()

            try:
                success = True
                reachable = True
                if SCHEDULER.apis:
                    # send cache
                    threads.append(Thread(target=send_file_to_bunkerweb, args=(CACHE_PATH, "/cache")))
                    threads[-1].start()

                    for thread in threads:
                        thread.join()

                    success, responses = SCHEDULER.send_to_apis(
                        "POST", "/reload", timeout=max(RELOAD_MIN_TIMEOUT, 2 * len(env["SERVER_NAME"].split(" "))), response=True
                    )
                    if not success:
                        reachable = False
                        LOGGER.debug(f"Error while reloading all bunkerweb instances: {responses}")

                    for db_instance in SCHEDULER.db.get_instances():
                        status = responses.get(db_instance["hostname"], {"status": "down"}).get("status", "down")
                        if status == "success":
                            success = True
                        ret = SCHEDULER.db.update_instance(db_instance["hostname"], "up" if status == "success" else "down")
                        if ret:
                            LOGGER.error(f"Couldn't update instance {db_instance['hostname']} status to down in the database: {ret}")

                        if status == "success":
                            found = False
                            for api in SCHEDULER.apis:
                                if api.endpoint == f"http://{db_instance['hostname']}:{db_instance['port']}/":
                                    found = True
                                    break
                            if not found:
                                LOGGER.debug(f"Adding {db_instance['hostname']}:{db_instance['port']} to the list of reachable instances")
                                SCHEDULER.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))
                            continue

                        for i, api in enumerate(SCHEDULER.apis):
                            if api.endpoint == f"http://{db_instance['hostname']}:{db_instance['port']}/":
                                LOGGER.debug(f"Removing {db_instance['hostname']}:{db_instance['port']} from the list of reachable instances")
                                del SCHEDULER.apis[i]
                                break
                else:
                    for thread in threads:
                        thread.join()

                    LOGGER.warning("No BunkerWeb instance found, skipping bunkerweb reload ...")
            except BaseException as e:
                LOGGER.error(f"Exception while reloading after running jobs once scheduling : {e}")

            try:
                SCHEDULER.db.set_metadata({"failover": not success})
            except BaseException as e:
                LOGGER.error(f"Error while setting failover to true in the database: {e}")

            try:
                if not success and reachable:
                    LOGGER.error("Error while reloading bunkerweb, failing over to last working configuration ...")
                    if (
                        not FAILOVER_PATH.joinpath("config").is_dir()
                        or not FAILOVER_PATH.joinpath("custom_configs").is_dir()
                        or not FAILOVER_PATH.joinpath("cache").is_dir()
                    ):
                        LOGGER.error("No failover configuration found, ignoring failover ...")
                    else:
                        # Failover to last working configuration
                        if SCHEDULER.apis:
                            tmp_threads = [
                                Thread(target=send_file_to_bunkerweb, args=(FAILOVER_PATH.joinpath("config"), "/confs")),
                                Thread(target=send_file_to_bunkerweb, args=(FAILOVER_PATH.joinpath("cache"), "/cache")),
                                Thread(target=send_file_to_bunkerweb, args=(FAILOVER_PATH.joinpath("custom_configs"), "/custom_configs")),
                            ]
                            for thread in tmp_threads:
                                thread.start()

                            for thread in tmp_threads:
                                thread.join()

                        if not SCHEDULER.send_to_apis("POST", "/reload", timeout=max(RELOAD_MIN_TIMEOUT, 2 * len(env["SERVER_NAME"].split(" "))))[0]:
                            LOGGER.error("Error while reloading bunkerweb with failover configuration, skipping ...")
                elif not reachable:
                    LOGGER.warning("No BunkerWeb instance is reachable, skipping failover ...")
                else:
                    LOGGER.info("Successfully reloaded bunkerweb")
                    # Update the failover path with the working configuration
                    rmtree(FAILOVER_PATH, ignore_errors=True)
                    FAILOVER_PATH.mkdir(parents=True, exist_ok=True)
                    copytree(CONFIG_PATH, FAILOVER_PATH.joinpath("config"))
                    copytree(CUSTOM_CONFIGS_PATH, FAILOVER_PATH.joinpath("custom_configs"))
                    copytree(CACHE_PATH, FAILOVER_PATH.joinpath("cache"))
                    Thread(target=JOB.cache_dir, args=(FAILOVER_PATH,), kwargs={"job_name": "failover-backup"}).start()
            except BaseException as e:
                LOGGER.error(f"Exception while executing failover logic : {e}")

            try:
                ret = SCHEDULER.db.checked_changes(CHANGES, plugins_changes="all")
                if ret:
                    LOGGER.error(f"An error occurred when setting the changes to checked in the database : {ret}")
            except BaseException as e:
                LOGGER.error(f"Error while setting changes to checked in the database: {e}")

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
                    ret = SCHEDULER.db.set_metadata({"scheduler_first_start": False})

                    if ret == "The database is read-only, the changes will not be saved":
                        LOGGER.warning("The database is read-only, the scheduler first start will not be saved")
                    elif ret:
                        LOGGER.error(f"An error occurred when setting the scheduler first start : {ret}")
                except BaseException as e:
                    LOGGER.error(f"Error while setting the scheduler first start : {e}")
                finally:
                    scheduler_first_start = False

            if not HEALTHY_PATH.is_file():
                HEALTHY_PATH.write_text(datetime.now().astimezone().isoformat(), encoding="utf-8")

            APPLYING_CHANGES.clear()
            schedule_every(HEALTHCHECK_INTERVAL).seconds.do(healthcheck_job)

            # infinite schedule for the jobs
            LOGGER.info("Executing job scheduler ...")
            errors = 0
            while RUN and not NEED_RELOAD:
                try:
                    sleep(3 if SCHEDULER.db.readonly else 1)
                    run_pending()
                    SCHEDULER.run_pending()
                    current_time = datetime.now().astimezone()

                    while DB_LOCK_FILE.is_file() and DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp():
                        LOGGER.debug("Database is locked, waiting for it to be unlocked (timeout: 30s) ...")
                        sleep(1)

                    DB_LOCK_FILE.unlink(missing_ok=True)

                    db_metadata = SCHEDULER.db.get_metadata()

                    if isinstance(db_metadata, str):
                        raise Exception(f"An error occurred when checking for changes in the database : {db_metadata}")

                    changes = {
                        "pro_plugins_changed": db_metadata["pro_plugins_changed"],
                        "last_pro_plugins_change": db_metadata["last_pro_plugins_change"],
                        "external_plugins_changed": db_metadata["external_plugins_changed"],
                        "last_external_plugins_change": db_metadata["last_external_plugins_change"],
                        "custom_configs_changed": db_metadata["custom_configs_changed"],
                        "last_custom_configs_change": db_metadata["last_custom_configs_change"],
                        "plugins_config_changed": db_metadata["plugins_config_changed"],
                        "instances_changed": db_metadata["instances_changed"],
                        "last_instances_change": db_metadata["last_instances_change"],
                    }

                    if SCHEDULER.db.readonly and changes == old_changes:
                        continue

                    # check if the plugins have changed since last time
                    if changes["pro_plugins_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_pro_plugins_change"]
                        or not old_changes
                        or old_changes["last_pro_plugins_change"] != changes["last_pro_plugins_change"]
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
                        or old_changes["last_external_plugins_change"] != changes["last_external_plugins_change"]
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
                        or old_changes["last_custom_configs_change"] != changes["last_custom_configs_change"]
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
                        or old_changes["plugins_config_changed"] != changes["plugins_config_changed"]
                    ):
                        LOGGER.info("Plugins config changed, generating ...")
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True
                        changed_plugins = list(changes["plugins_config_changed"])

                    # check if the instances have changed since last time
                    if changes["instances_changed"] and (
                        not SCHEDULER.db.readonly
                        or not changes["last_instances_change"]
                        or not old_changes
                        or old_changes["last_instances_change"] != changes["last_instances_change"]
                    ):
                        LOGGER.info("Instances changed, generating ...")
                        INSTANCES_NEED_GENERATION = True
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    old_changes = changes.copy()
                except BaseException:
                    LOGGER.debug(format_exc())
                    if errors > 5:
                        LOGGER.error(f"An error occurred when executing the scheduler : {format_exc()}")
                        stop(1)
                    errors += 1
                    sleep(5)

            if NEED_RELOAD:
                APPLYING_CHANGES.set()
                LOGGER.debug(f"Changes: {changes}")
                SCHEDULER.try_database_readonly(force=True)
                CHANGES.clear()

                if INSTANCES_NEED_GENERATION:
                    CHANGES.append("instances")
                    SCHEDULER.apis = []
                    for db_instance in SCHEDULER.db.get_instances():
                        SCHEDULER.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))

                if CONFIGS_NEED_GENERATION:
                    CHANGES.append("custom_configs")
                    generate_custom_configs(SCHEDULER.db.get_custom_configs())

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
                    if old_env["API_HTTP_PORT"] != env["API_HTTP_PORT"] or old_env["API_SERVER_NAME"] != env["API_SERVER_NAME"]:
                        err = SCHEDULER.db.update_instances(
                            [
                                {
                                    "hostname": db_instance["hostname"],
                                    "name": db_instance["name"],
                                    "env": {
                                        "API_HTTP_PORT": env["API_HTTP_PORT"],
                                        "API_SERVER_NAME": env["API_SERVER_NAME"],
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
                            LOGGER.error(f"Couldn't update instances in the database: {err}")
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

    except:
        LOGGER.error(f"Exception while executing scheduler : {format_exc()}")
        stop(1)
