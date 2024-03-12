#!/usr/bin/env python3

from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime
from glob import glob
from hashlib import sha256
from io import BytesIO
from json import load as json_load
from os import _exit, chmod, environ, getenv, getpid, listdir, sep, walk
from os.path import basename, dirname, join, normpath
from pathlib import Path
from shutil import copy, rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT, PIPE
from sys import path as sys_path
from tarfile import open as tar_open
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Union

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from dotenv import dotenv_values

from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler

RUN = True
SCHEDULER: Optional[JobScheduler] = None
INTEGRATION = "Linux"
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy")
CACHE_PATH = join(sep, "var", "cache", "bunkerweb")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
SCHEDULER_TMP_ENV_PATH = Path(sep, "var", "tmp", "bunkerweb", "scheduler.env")
SCHEDULER_TMP_ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
SCHEDULER_TMP_ENV_PATH.touch()
logger = setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))


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
            # Get the env by reading the .env file
            tmp_env = dotenv_values(join(sep, "etc", "bunkerweb", "variables.env"))
            if SCHEDULER.reload(tmp_env):
                logger.info("Reload successful")
            else:
                logger.error("Reload failed")
        else:
            logger.warning("Ignored reload operation because scheduler is not running ...")
    except:
        logger.error(f"Exception while reloading scheduler : {format_exc()}")


signal(SIGHUP, handle_reload)


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


def generate_custom_configs(configs: List[Dict[str, Any]], *, original_path: Union[Path, str] = join(sep, "etc", "bunkerweb", "configs")):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    logger.info("Removing old custom configs files ...")
    for file in glob(str(original_path.joinpath("*", "*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(file, ignore_errors=True)

    if configs:
        logger.info("Generating new custom configs ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for custom_config in configs:
            tmp_path = original_path.joinpath(
                custom_config["type"].replace("_", "-"),
                custom_config["service_id"] or "",
                f"{custom_config['name']}.conf",
            )
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(custom_config["data"])

    if SCHEDULER and SCHEDULER.apis:
        logger.info("Sending custom configs to BunkerWeb")
        ret = SCHEDULER.send_files(original_path, "/custom_configs")

        if not ret:
            logger.error("Sending custom configs failed, configuration will not work as expected...")


def generate_external_plugins(plugins: List[Dict[str, Any]], *, original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)
    pro = original_path.as_posix().endswith("/pro/plugins")

    # Remove old external/pro plugins files
    logger.info(f"Removing old {'pro ' if pro else ''}external plugins files ...")
    for file in glob(str(original_path.joinpath("*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(file, ignore_errors=True)

    if plugins:
        logger.info(f"Generating new {'pro ' if pro else ''}external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            tmp_path = original_path.joinpath(plugin["id"], f"{plugin['name']}.tar.gz")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(plugin["data"])
            with tar_open(str(tmp_path), "r:gz") as tar:
                tar.extractall(original_path)
            tmp_path.unlink()

            for job_file in glob(join(str(tmp_path.parent), "jobs", "*")):
                st = Path(job_file).stat()
                chmod(job_file, st.st_mode | S_IEXEC)

    if SCHEDULER and SCHEDULER.apis:
        logger.info(f"Sending {'pro ' if pro else ''}external plugins to BunkerWeb")
        ret = SCHEDULER.send_files(original_path, "/pro_plugins" if original_path.as_posix().endswith("/pro/plugins") else "/plugins")

        if not ret:
            logger.error(f"Sending {'pro ' if pro else ''}external plugins failed, configuration will not work as expected...")


def dict_to_frozenset(d):
    if isinstance(d, list):
        return tuple(sorted(d))
    elif isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


def api_to_instance(api):
    hostname_port = api.endpoint.replace("http://", "").replace("https://", "").replace("/", "").split(":")
    return {
        "hostname": hostname_port[0],
        "env": {"API_HTTP_PORT": int(hostname_port[1]), "API_SERVER_NAME": api.host},
    }


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            logger.error("Scheduler is already running, skipping execution ...")
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")

        del pid_path

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            INTEGRATION = "Kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            INTEGRATION = "Swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            INTEGRATION = "Autoconf"
        elif integration_path.is_file():
            INTEGRATION = integration_path.read_text(encoding="utf-8").strip()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(encoding="utf-8"):
            INTEGRATION = "Docker"

        del integration_path, os_release_path

        tmp_variables_path = normpath(args.variables) if args.variables else join(sep, "var", "tmp", "bunkerweb", "variables.env")
        tmp_variables_path = Path(tmp_variables_path)
        nginx_variables_path = Path(sep, "etc", "nginx", "variables.env")
        dotenv_env = dotenv_values(str(tmp_variables_path))

        db = Database(
            logger,
            sqlalchemy_string=dotenv_env.get("DATABASE_URI", getenv("DATABASE_URI", None)),
        )
        env = {}

        if INTEGRATION in ("Swarm", "Kubernetes", "Autoconf"):
            while not db.is_initialized():
                logger.warning("Database is not initialized, retrying in 5s ...")
                sleep(5)

            while not db.is_autoconf_loaded():
                logger.warning("Autoconf is not loaded yet in the database, retrying in 5s ...")
                sleep(5)

            env = db.get_config()
        elif (
            not tmp_variables_path.exists()
            or not nginx_variables_path.exists()
            or (tmp_variables_path.read_text(encoding="utf-8") != nginx_variables_path.read_text(encoding="utf-8"))
            or db.is_initialized()
            and db.get_config() != dotenv_env
        ):
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
                logger.error("Config saver failed, configuration will not work as expected...")

            while not db.is_initialized():
                logger.warning("Database is not initialized, retrying in 5s ...")
                sleep(5)

            env = db.get_config()
            while not db.is_first_config_saved() or not env:
                logger.warning("Database doesn't have any config saved yet, retrying in 5s ...")
                sleep(5)
                env = db.get_config()
        else:
            env = db.get_config()

        env["DATABASE_URI"] = db.database_uri

        # Instantiate scheduler
        SCHEDULER = JobScheduler(env | environ.copy(), logger, INTEGRATION, db=db)

        if INTEGRATION in ("Docker", "Swarm", "Kubernetes", "Autoconf"):
            # Automatically setup the scheduler apis
            while not SCHEDULER.apis:
                SCHEDULER.auto_setup()

                if not SCHEDULER.apis:
                    logger.warning("No BunkerWeb API found, retrying in 5s ...")
                    sleep(5)
            db.update_instances([api_to_instance(api) for api in SCHEDULER.apis])

        scheduler_first_start = db.is_scheduler_first_start()

        logger.info("Scheduler started ...")

        # Checking if any custom config has been created by the user
        logger.info("Checking if there are any changes in custom configs ...")
        custom_configs = []
        db_configs = db.get_custom_configs()
        configs_path = Path(sep, "etc", "bunkerweb", "configs")
        root_dirs = listdir(str(configs_path))
        changes = False
        for root, dirs, files in walk(str(configs_path)):
            if files or (dirs and basename(root) not in root_dirs):
                path_exploded = root.split("/")
                for file in files:
                    content = Path(join(root, file)).read_text(encoding="utf-8")
                    custom_conf = {
                        "value": content,
                        "exploded": (path_exploded.pop() if path_exploded[-1] not in root_dirs else None, path_exploded[-1], file.replace(".conf", "")),
                    }

                    saving = True
                    in_db = False
                    for db_conf in db_configs:
                        if db_conf["service_id"] == custom_conf["exploded"][0] and db_conf["name"] == custom_conf["exploded"][2]:
                            in_db = True
                            if db_conf["method"] != "manual":
                                saving = False
                                break

                    if not in_db and content.startswith("# CREATED BY ENV"):
                        saving = False
                        changes = True

                    if saving:
                        custom_configs.append(custom_conf)

        changes = changes or {hash(dict_to_frozenset(d)) for d in custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs}

        if changes:
            err = db.save_custom_configs(custom_configs, "manual")
            if err:
                logger.error(f"Couldn't save some manually created custom configs to database: {err}")

        if (scheduler_first_start and db_configs) or changes:
            Thread(target=generate_custom_configs, args=(db.get_custom_configs(),), kwargs={"original_path": configs_path}).start()

        del custom_configs, db_configs

        def check_plugin_changes(_type: Literal["external", "pro"] = "external"):
            # Check if any external or pro plugin has been added by the user
            logger.info(f"Checking if there are any changes in {_type} plugins ...")
            external_plugins = []
            db_plugins = db.get_plugins(_type=_type)
            for filename in glob(str((EXTERNAL_PLUGINS_PATH if _type == "external" else PRO_PLUGINS_PATH).joinpath("*", "plugin.json"))):
                with open(filename, "r", encoding="utf-8") as f:
                    _dir = dirname(filename)
                    plugin_content = BytesIO()
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(_dir, arcname=basename(_dir), recursive=True)
                    plugin_content.seek(0, 0)
                    value = plugin_content.getvalue()

                    external_plugins.append(
                        json_load(f)
                        | {
                            "type": _type,
                            "page": Path(_dir, "ui").exists(),
                            "method": "manual",
                            "data": value,
                            "checksum": sha256(value).hexdigest(),
                        }
                    )

            tmp_external_plugins = []
            for external_plugin in deepcopy(external_plugins):
                external_plugin.pop("data", None)
                external_plugin.pop("checksum", None)
                external_plugin.pop("jobs", None)
                external_plugin.pop("method", None)
                tmp_external_plugins.append(external_plugin)

            tmp_db_plugins = []
            for db_plugin in db_plugins.copy():
                db_plugin.pop("method", None)
                tmp_db_plugins.append(db_plugin)

            changes = {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != {hash(dict_to_frozenset(d)) for d in tmp_db_plugins}

            if changes:
                err = db.update_external_plugins(external_plugins, _type=_type, delete_missing=True)
                if err:
                    logger.error(f"Couldn't save some manually added {_type} plugins to database: {err}")

            if (scheduler_first_start and db_plugins) or changes:
                generate_external_plugins(
                    db.get_plugins(_type=_type, with_data=True),
                    original_path=EXTERNAL_PLUGINS_PATH if _type == "external" else PRO_PLUGINS_PATH,
                )
                SCHEDULER.update_jobs()

        check_plugin_changes("external")
        check_plugin_changes("pro")

        logger.info("Running plugins download jobs ...")

        # Update the environment variables of the scheduler
        SCHEDULER.env = env | environ.copy()
        if not SCHEDULER.run_single("download-plugins"):
            logger.warning("download-plugins job failed at first start, plugins settings set by the user may not be up to date ...")
        if not SCHEDULER.run_single("download-pro-plugins"):
            logger.warning("download-pro-plugins job failed at first start, pro plugins settings set by the user may not be up to date ...")

        changes = db.check_changes()
        if INTEGRATION not in ("Swarm", "Kubernetes", "Autoconf") and (changes["pro_plugins_changed"] or changes["external_plugins_changed"]):
            # run the config saver to save potential ignored external plugins settings
            logger.info("Running config saver to save potential ignored external plugins settings ...")
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
                logger.error(
                    "Config saver failed, configuration will not work as expected...",
                )

        logger.info("Executing scheduler ...")

        del dotenv_env

        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []
        threads = []

        def send_nginx_configs():
            logger.info(f"Sending {join(sep, 'etc', 'nginx')} folder ...")
            ret = SCHEDULER.send_files(join(sep, "etc", "nginx"), "/confs")
            if not ret:
                logger.error("Sending nginx configs failed, configuration will not work as expected...")

        def send_nginx_cache():
            logger.info(f"Sending {CACHE_PATH} folder ...")
            if not SCHEDULER.send_files(CACHE_PATH, "/cache"):
                logger.error(f"Error while sending {CACHE_PATH} folder")
            else:
                logger.info(f"Successfully sent {CACHE_PATH} folder")

        def listen_for_instances_reload(db: Database):
            from docker import DockerClient

            global SCHEDULER

            docker_client = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))
            for event in docker_client.events(decode=True, filters={"type": "container", "label": "bunkerweb.INSTANCE"}):
                if event["Action"] in ("start", "die"):
                    logger.info(f"🐋 Detected {event['Action']} event on container {event['Actor']['Attributes']['name']}")
                    SCHEDULER.auto_setup()
                    db.update_instances([api_to_instance(api) for api in SCHEDULER.apis], changed=event["Action"] == "die")
                    if event["Action"] == "start":
                        db.checked_changes(value=True)

        if INTEGRATION == "Docker":
            Thread(target=listen_for_instances_reload, args=(db,), name="listen_for_instances_reload").start()

        while True:
            threads.clear()
            ret = db.checked_changes(CHANGES)

            if ret:
                logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")
                stop(1)

            if RUN_JOBS_ONCE:
                # Update the environment variables of the scheduler
                SCHEDULER.env = env | environ.copy()
                SCHEDULER.setup()

                # Only run jobs once
                if not SCHEDULER.run_once():
                    logger.error("At least one job in run_once() failed")
                else:
                    logger.info("All jobs in run_once() were successful")

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
                    ],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )

                if proc.returncode != 0:
                    logger.error("Config generator failed, configuration will not work as expected...")
                else:
                    copy(str(nginx_variables_path), join(sep, "var", "tmp", "bunkerweb", "variables.env"))

                    if SCHEDULER.apis:
                        # send nginx configs
                        thread = Thread(target=send_nginx_configs)
                        thread.start()
                        threads.append(thread)
                    elif INTEGRATION != "Linux":
                        logger.warning("No BunkerWeb instance found, skipping nginx configs sending ...")

            try:
                if SCHEDULER.apis:
                    # send cache
                    thread = Thread(target=send_nginx_cache)
                    thread.start()
                    threads.append(thread)

                    for thread in threads:
                        thread.join()

                    if SCHEDULER.send_to_apis("POST", "/reload"):
                        logger.info("Successfully reloaded nginx")
                    else:
                        logger.error("Error while reloading nginx")
                elif INTEGRATION == "Linux":
                    # Reload nginx
                    logger.info("Reloading nginx ...")
                    proc = subprocess_run(
                        [join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                        stdin=DEVNULL,
                        stderr=STDOUT,
                        env=env.copy(),
                        check=False,
                        stdout=PIPE,
                    )
                    if proc.returncode == 0:
                        logger.info("Successfully sent reload signal to nginx")
                    else:
                        logger.error(
                            f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stdout.decode('utf-8') if proc.stdout else 'no output'}"
                        )
                else:
                    logger.warning("No BunkerWeb instance found, skipping nginx reload ...")
            except:
                logger.error(f"Exception while reloading after running jobs once scheduling : {format_exc()}")

            NEED_RELOAD = False
            RUN_JOBS_ONCE = False
            CONFIG_NEED_GENERATION = False
            CONFIGS_NEED_GENERATION = False
            PLUGINS_NEED_GENERATION = False
            PRO_PLUGINS_NEED_GENERATION = False
            INSTANCES_NEED_GENERATION = False

            if scheduler_first_start:
                ret = db.set_scheduler_first_start()

                if ret:
                    logger.error(f"An error occurred when setting the scheduler first start : {ret}")
                    stop(1)
                scheduler_first_start = False

            if not HEALTHY_PATH.is_file():
                HEALTHY_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")

            # infinite schedule for the jobs
            logger.info("Executing job scheduler ...")
            while RUN and not NEED_RELOAD:
                SCHEDULER.run_pending()
                sleep(1)

                changes = db.check_changes()

                if isinstance(changes, str):
                    logger.error(f"An error occurred when checking for changes in the database : {changes}")
                    stop(1)

                # check if the plugins have changed since last time
                if changes["pro_plugins_changed"]:
                    logger.info("Pro plugins changed, generating ...")
                    PRO_PLUGINS_NEED_GENERATION = True
                    CONFIG_NEED_GENERATION = True
                    RUN_JOBS_ONCE = True
                    NEED_RELOAD = True

                if changes["external_plugins_changed"]:
                    logger.info("External plugins changed, generating ...")
                    PLUGINS_NEED_GENERATION = True
                    CONFIG_NEED_GENERATION = True
                    RUN_JOBS_ONCE = True
                    NEED_RELOAD = True

                # check if the custom configs have changed since last time
                if changes["custom_configs_changed"]:
                    logger.info("Custom configs changed, generating ...")
                    CONFIGS_NEED_GENERATION = True
                    CONFIG_NEED_GENERATION = True
                    NEED_RELOAD = True

                # check if the config have changed since last time
                if changes["config_changed"]:
                    logger.info("Config changed, generating ...")
                    CONFIG_NEED_GENERATION = True
                    RUN_JOBS_ONCE = True
                    NEED_RELOAD = True

                # check if the instances have changed since last time
                if changes["instances_changed"]:
                    logger.info("Instances changed, generating ...")
                    INSTANCES_NEED_GENERATION = True
                    CONFIGS_NEED_GENERATION = True
                    CONFIG_NEED_GENERATION = True
                    NEED_RELOAD = True

            if NEED_RELOAD:
                CHANGES.clear()

                if INSTANCES_NEED_GENERATION:
                    CHANGES.append("instances")
                    SCHEDULER.update_instances()

                if CONFIGS_NEED_GENERATION:
                    CHANGES.append("custom_configs")
                    generate_custom_configs(db.get_custom_configs(), original_path=configs_path)

                if PLUGINS_NEED_GENERATION:
                    CHANGES.append("external_plugins")
                    generate_external_plugins(db.get_plugins(_type="external", with_data=True))
                    SCHEDULER.update_jobs()

                if PRO_PLUGINS_NEED_GENERATION:
                    CHANGES.append("pro_plugins")
                    generate_external_plugins(db.get_plugins(_type="pro", with_data=True), original_path=PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                if CONFIG_NEED_GENERATION:
                    CHANGES.append("config")
                    env = db.get_config()
                    env["DATABASE_URI"] = db.database_uri

    except:
        logger.error(f"Exception while executing scheduler : {format_exc()}")
        stop(1)
