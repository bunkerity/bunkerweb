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
from shutil import copy, rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT, PIPE
from sys import path as sys_path
from tarfile import TarFile, open as tar_open
from threading import Event, Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from dotenv import dotenv_values
from schedule import every as schedule_every, run_pending

from common_utils import bytes_hash, dict_to_frozenset, get_integration  # type: ignore
from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler
from API import API  # type: ignore
from ApiCaller import ApiCaller  # type: ignore

RUN = True
SCHEDULER: Optional[JobScheduler] = None

CACHE_PATH = join(sep, "var", "cache", "bunkerweb")
Path(CACHE_PATH).mkdir(parents=True, exist_ok=True)

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
)

for custom_config_dir in CUSTOM_CONFIGS_DIRS:
    CUSTOM_CONFIGS_PATH.joinpath(custom_config_dir).mkdir(parents=True, exist_ok=True)

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")
TMP_PATH.mkdir(parents=True, exist_ok=True)

HEALTHY_PATH = TMP_PATH.joinpath("scheduler.healthy")

SCHEDULER_TMP_ENV_PATH = TMP_PATH.joinpath("scheduler.env")
SCHEDULER_TMP_ENV_PATH.touch()

DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")
LOGGER = setup_logger("Scheduler", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

HEALTHCHECK_INTERVAL = getenv("HEALTHCHECK_INTERVAL", "10")

if not HEALTHCHECK_INTERVAL.isdigit():
    LOGGER.error("HEALTHCHECK_INTERVAL must be an integer, defaulting to 10")
    HEALTHCHECK_INTERVAL = 10

HEALTHCHECK_INTERVAL = int(HEALTHCHECK_INTERVAL)
HEALTHCHECK_EVENT = Event()

SLAVE_MODE = getenv("SLAVE_MODE", "no") == "yes"
MASTER_MODE = getenv("MASTER_MODE", "no") == "yes"


def handle_stop(signum, frame):
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
    except:
        LOGGER.error(f"Exception while reloading scheduler : {format_exc()}")


signal(SIGHUP, handle_reload)


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


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
        LOGGER.info("Sending custom configs to BunkerWeb")
        ret = SCHEDULER.send_files(original_path, "/custom_configs")

        if not ret:
            LOGGER.error("Sending custom configs failed, configuration will not work as expected...")


def generate_external_plugins(plugins: Optional[List[Dict[str, Any]]] = None, *, original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)
    pro = "pro" in original_path.parts

    if not plugins:
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
                    tmp_path = TMP_PATH.joinpath(f"{plugin['id']}_{plugin['name']}.tar.gz")
                    tmp_path.write_bytes(plugin["data"])
                    with tar_open(str(tmp_path), "r:gz") as tar:
                        try:
                            tar.extractall(original_path, filter="fully_trusted")
                        except TypeError:
                            tar.extractall(original_path)
                    tmp_path.unlink(missing_ok=True)

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
        ret = SCHEDULER.send_files(original_path, "/pro_plugins" if original_path.as_posix().endswith("/pro/plugins") else "/plugins")

        if not ret:
            LOGGER.error(f"Sending {'pro ' if pro else ''}external plugins failed, configuration will not work as expected...")


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

    # Instantiate scheduler environment
    SCHEDULER.env = env

    threads = [
        Thread(target=generate_custom_configs),
        Thread(target=generate_external_plugins),
        Thread(target=generate_external_plugins, kwargs={"original_path": PRO_PLUGINS_PATH}),
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
            join(sep, "etc", "nginx"),
            "--variables",
            str(SCHEDULER_TMP_ENV_PATH),
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
    return  # TODO: remove this when the healthcheck endpoint is ready @fl0ppy-d1sk

    if HEALTHCHECK_EVENT.is_set():
        LOGGER.warning("Healthcheck job is already running, skipping execution ...")
        return

    try:
        assert SCHEDULER is not None
    except AssertionError:
        return

    HEALTHCHECK_EVENT.set()

    for db_instance in SCHEDULER.db.get_instances():
        try:
            bw_instance = API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"])
            sent, err, status, resp = bw_instance.request("GET", "health")

            if not sent:
                LOGGER.warning(
                    f"instances_healthcheck - Can't send API request to {bw_instance.endpoint}health : {err}, healthcheck will be retried in {HEALTHCHECK_INTERVAL} seconds ..."
                )
                if bw_instance in SCHEDULER.apis:
                    SCHEDULER.apis.remove(bw_instance)
                continue
            if status != 200:
                LOGGER.warning(
                    f"instances_healthcheck - Error while sending API request to {bw_instance.endpoint}health : status = {resp['status']}, msg = {resp['msg']}, healthcheck will be retried in {HEALTHCHECK_INTERVAL} seconds ..."
                )
                if bw_instance in SCHEDULER.apis:
                    SCHEDULER.apis.remove(bw_instance)
                continue

            if resp["state"] == "loading":
                LOGGER.info(f"instances_healthcheck - Instance {bw_instance.endpoint} is loading, sending config ...")
                api_caller = ApiCaller([bw_instance])
                api_caller.send_files(CUSTOM_CONFIGS_PATH, "/custom_configs")
                api_caller.send_files(EXTERNAL_PLUGINS_PATH, "/plugins")
                api_caller.send_files(PRO_PLUGINS_PATH, "/pro_plugins")
                api_caller.send_files(join(sep, "etc", "nginx"), "/confs")
                api_caller.send_files(CACHE_PATH, "/cache")
                if api_caller.send_to_apis("POST", "/reload"):
                    LOGGER.info(f"Successfully reloaded instance {bw_instance.endpoint}")
                else:
                    LOGGER.error(f"Error while reloading instance {bw_instance.endpoint}")
            elif resp["state"] == "down":
                LOGGER.warning(f"instances_healthcheck - Instance {bw_instance.endpoint} is down")
                if bw_instance in SCHEDULER.apis:
                    SCHEDULER.apis.remove(bw_instance)
                continue

            if bw_instance not in SCHEDULER.apis:
                SCHEDULER.apis.append(bw_instance)
        except BaseException:
            LOGGER.exception(f"instances_healthcheck - Exception while checking instance {bw_instance.endpoint}")
            if bw_instance in SCHEDULER.apis:
                SCHEDULER.apis.remove(bw_instance)

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

        INTEGRATION = get_integration()
        tmp_variables_path = Path(args.variables or join(sep, "var", "tmp", "bunkerweb", "variables.env"))
        nginx_variables_path = Path(sep, "etc", "nginx", "variables.env")
        dotenv_env = dotenv_values(str(tmp_variables_path))

        SCHEDULER = JobScheduler(environ, LOGGER, INTEGRATION, db=Database(LOGGER, sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None))))  # type: ignore

        if SLAVE_MODE:
            run_in_slave_mode()
            stop(1)

        schedule_every(HEALTHCHECK_INTERVAL).seconds.do(healthcheck_job)

        db_metadata = SCHEDULER.db.get_metadata()

        if (
            isinstance(db_metadata, str)
            or (db_metadata["is_initialized"] and SCHEDULER.db.get_config() != dotenv_env)
            or not tmp_variables_path.exists()
            or not nginx_variables_path.exists()
            or (tmp_variables_path.read_text(encoding="utf-8") != nginx_variables_path.read_text(encoding="utf-8"))
        ):
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
                    ]
                    + (["--variables", str(tmp_variables_path)] if args.variables else []),
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

        # Instantiate scheduler environment
        SCHEDULER.env = env

        threads = []

        SCHEDULER.apis = []
        for db_instance in SCHEDULER.db.get_instances():
            SCHEDULER.apis.append(API(f"http://{db_instance['hostname']}:{db_instance['port']}", db_instance["server_name"]))

        scheduler_first_start = db_metadata["scheduler_first_start"]

        LOGGER.info("Scheduler started ...")

        def check_configs_changes():
            # Checking if any custom config has been created by the user
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
                for db_conf in db_configs:
                    if db_conf["service_id"] == service_id and db_conf["name"] == file.stem:
                        in_db = True

                if not in_db and content.startswith("# CREATED BY ENV"):
                    saving = False
                    changes = True

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

        threads.append(Thread(target=check_configs_changes))

        def check_plugin_changes(_type: Literal["external", "pro"] = "external"):
            # Check if any external or pro plugin has been added by the user
            LOGGER.info(f"Checking if there are any changes in {_type} plugins ...")
            plugin_path = EXTERNAL_PLUGINS_PATH if _type == "external" else PRO_PLUGINS_PATH
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

            if tmp_external_plugins:
                changes = {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != {hash(dict_to_frozenset(d)) for d in db_plugins}

                if changes:
                    try:
                        err = SCHEDULER.db.update_external_plugins(external_plugins, _type=_type, delete_missing=True)
                        if err:
                            LOGGER.error(f"Couldn't save some manually added {_type} plugins to database: {err}")
                    except BaseException as e:
                        LOGGER.error(f"Error while saving {_type} plugins to database: {e}")

            generate_external_plugins(SCHEDULER.db.get_plugins(_type=_type, with_data=True), original_path=plugin_path)

        threads.extend([Thread(target=check_plugin_changes, args=("external",)), Thread(target=check_plugin_changes, args=("pro",))])

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        LOGGER.info("Running plugins download jobs ...")

        # Update the environment variables of the scheduler
        SCHEDULER.env = env
        if not SCHEDULER.run_single("download-plugins"):
            LOGGER.warning("download-plugins job failed at first start, plugins settings set by the user may not be up to date ...")
        if not SCHEDULER.run_single("download-pro-plugins"):
            LOGGER.warning("download-pro-plugins job failed at first start, pro plugins settings set by the user may not be up to date ...")

        db_metadata = SCHEDULER.db.get_metadata()
        if db_metadata["pro_plugins_changed"] or db_metadata["external_plugins_changed"]:
            threads.clear()

            if db_metadata["pro_plugins_changed"]:
                threads.append(Thread(target=generate_external_plugins, kwargs={"original_path": PRO_PLUGINS_PATH}))
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
                    ],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )
                if proc.returncode != 0:
                    LOGGER.error("Config saver failed, configuration will not work as expected...")

            SCHEDULER.update_jobs()
            env = SCHEDULER.db.get_config()
            env["DATABASE_URI"] = SCHEDULER.db.database_uri

        LOGGER.info("Executing scheduler ...")

        del dotenv_env

        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []

        def send_nginx_configs():
            LOGGER.info(f"Sending {join(sep, 'etc', 'nginx')} folder ...")
            ret = SCHEDULER.send_files(join(sep, "etc", "nginx"), "/confs")
            if not ret:
                LOGGER.error("Sending nginx configs failed, configuration will not work as expected...")

        def send_nginx_cache():
            LOGGER.info(f"Sending {CACHE_PATH} folder ...")
            if not SCHEDULER.send_files(CACHE_PATH, "/cache"):
                LOGGER.error(f"Error while sending {CACHE_PATH} folder")
            else:
                LOGGER.info(f"Successfully sent {CACHE_PATH} folder")

        changed_plugins = []
        old_changes = {}

        while True:
            threads.clear()

            if RUN_JOBS_ONCE:
                # Only run jobs once
                if not SCHEDULER.reload(env, changed_plugins=changed_plugins):
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
                        join(sep, "etc", "nginx"),
                        "--variables",
                        str(SCHEDULER_TMP_ENV_PATH),
                    ]
                    + (["--no-linux-reload"] if MASTER_MODE else []),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )

                if proc.returncode != 0:
                    LOGGER.error("Config generator failed, configuration will not work as expected...")
                else:
                    copy(str(nginx_variables_path), join(sep, "var", "tmp", "bunkerweb", "variables.env"))

                    if SCHEDULER.apis:
                        # send nginx configs
                        thread = Thread(target=send_nginx_configs)
                        thread.start()
                        threads.append(thread)
                    elif INTEGRATION != "Linux":
                        LOGGER.warning("No BunkerWeb instance found, skipping nginx configs sending ...")

            try:
                if SCHEDULER.apis:
                    # send cache
                    thread = Thread(target=send_nginx_cache)
                    thread.start()
                    threads.append(thread)

                    for thread in threads:
                        thread.join()

                    if SCHEDULER.send_to_apis("POST", "/reload"):
                        LOGGER.info("Successfully reloaded nginx")
                    else:
                        LOGGER.error("Error while reloading nginx")
                elif INTEGRATION == "Linux":
                    # Reload nginx
                    LOGGER.info("Reloading nginx ...")
                    proc = subprocess_run(
                        [join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                        stdin=DEVNULL,
                        stderr=STDOUT,
                        env=env.copy(),
                        check=False,
                        stdout=PIPE,
                    )
                    if proc.returncode == 0:
                        LOGGER.info("Successfully sent reload signal to nginx")
                    else:
                        LOGGER.error(
                            f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stdout.decode('utf-8') if proc.stdout else 'no output'}"
                        )
                else:
                    LOGGER.warning("No BunkerWeb instance found, skipping nginx reload ...")
            except:
                LOGGER.error(f"Exception while reloading after running jobs once scheduling : {format_exc()}")

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
                HEALTHY_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")

            # infinite schedule for the jobs
            LOGGER.info("Executing job scheduler ...")
            errors = 0
            while RUN and not NEED_RELOAD:
                try:
                    sleep(3 if SCHEDULER.db.readonly else 1)
                    run_pending()
                    SCHEDULER.run_pending()
                    current_time = datetime.now()

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
                    generate_external_plugins(SCHEDULER.db.get_plugins(_type="external", with_data=True))
                    SCHEDULER.update_jobs()

                if PRO_PLUGINS_NEED_GENERATION:
                    CHANGES.append("pro_plugins")
                    generate_external_plugins(SCHEDULER.db.get_plugins(_type="pro", with_data=True), original_path=PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                if CONFIG_NEED_GENERATION:
                    CHANGES.append("config")
                    env = SCHEDULER.db.get_config()
                    env["DATABASE_URI"] = SCHEDULER.db.database_uri

    except:
        LOGGER.error(f"Exception while executing scheduler : {format_exc()}")
        stop(1)
