#!/usr/bin/python3

from argparse import ArgumentParser
from glob import glob
from hashlib import sha256
from io import BytesIO
from json import load as json_load
from os import (
    _exit,
    chmod,
    environ,
    getenv,
    getpid,
    listdir,
    sep,
    walk,
)
from os.path import basename, dirname, join, normpath
from pathlib import Path
from shutil import copy, rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import open as tar_open
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Optional, Union

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler

RUN = True
SCHEDULER: Optional[JobScheduler] = None
SCHEDULER_HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy")
GENERATE = False
INTEGRATION = "Linux"
CONFIGS_DIRS = [
    "http",
    "stream",
    "server-http",
    "server-stream",
    "default-server-http",
    "default-server-stream",
    "modsec",
    "modsec-crs",
]
NGINX_PATH = Path(sep, "etc", "nginx")
CACHE_PATH = join(sep, "var", "cache", "bunkerweb")
CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
logger = setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy").unlink(missing_ok=True)
    _exit(status)


def handle_stop(signum, frame):
    if SCHEDULER is not None:
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


def handle_reload(signum, frame):
    try:
        if SCHEDULER is not None and RUN:
            if SCHEDULER.reload():
                logger.info("Reload successful")
            else:
                logger.error("Reload failed")
        else:
            logger.warning(
                "Ignored reload operation because scheduler is not running ...",
            )
    except:
        logger.error(
            f"Exception while reloading scheduler : {format_exc()}",
        )


signal(SIGHUP, handle_reload)


def generate_custom_configs(
    instances_configs: List[Dict[str, Any]],
    *,
    original_path: Union[Path, str] = CONFIGS_PATH,
    updated_instances: Optional[List[str]] = None,
):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    logger.info("Removing old custom configs files ...")
    for file in glob(str(original_path.joinpath("*", "*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(str(file), ignore_errors=True)

    updated_instances = updated_instances or []

    for instance, configs in instances_configs.items():
        if not FIRST_RUN and instance not in updated_instances:
            continue

        instance_path = original_path.joinpath(
            instance if instance != "127.0.0.1" else ""
        )
        instance_path.mkdir(parents=True, exist_ok=True)

        if configs:
            logger.info(f"Generating custom configs for instance {instance} ...")
            for custom_config in configs:
                tmp_path = instance_path.joinpath(
                    custom_config["type"].replace("_", "-"),
                    custom_config["service_id"] or "",
                    f"{custom_config['name']}.conf",
                )
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(custom_config["data"])

        if instance != "localhost":
            instance_api = None
            for api in SCHEDULER.apis:
                if f"{instance}:" in api.endpoint:
                    instance_api = api
                    break

            if not instance_api:
                logger.error(
                    f"Could not find an API for instance {instance}, configuration will not work as expected...",
                )
                continue

            logger.info(f"Sending custom configs to instance {instance} ...")

            ret = SCHEDULER.send_files(
                instance_path, "/custom_configs", apis=[instance_api]
            )

            if not ret:
                logger.error(
                    "Sending custom configs failed, configuration will not work as expected...",
                )

    logger.info("✅ Custom configs generation done")


def generate_external_plugins(
    plugins: List[Dict[str, Any]],
    *,
    original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH,
):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old external plugins files
    logger.info("Removing old external plugins files ...")
    for file in glob(str(original_path.joinpath("*"))):
        file = Path(file)
        if file.is_symlink() or file.is_file():
            file.unlink()
        elif file.is_dir():
            rmtree(str(file), ignore_errors=True)

    if plugins:
        logger.info("Generating new external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            tmp_path = original_path.joinpath(plugin["id"], f"{plugin['name']}.tar.gz")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_bytes(plugin["data"])
            with tar_open(str(tmp_path), "r:gz") as tar:
                tar.extractall(original_path)
            tmp_path.unlink()

            for job_file in glob(str(tmp_path.parent.joinpath("jobs", "*"))):
                st = Path(job_file).stat()
                chmod(job_file, st.st_mode | S_IEXEC)

    if SCHEDULER and SCHEDULER.apis:
        logger.info("Sending plugins to BunkerWeb")
        ret = SCHEDULER.send_files(original_path, "/plugins")

        if not ret:
            logger.error(
                "Sending plugins failed, configuration will not work as expected...",
            )


def dict_to_frozenset(d):
    if isinstance(d, dict):
        return frozenset((k, dict_to_frozenset(v)) for k, v in d.items())
    return d


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            logger.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")

        del pid_path

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument(
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        args = parser.parse_args()

        wait_retry_interval = getenv("WAIT_RETRY_INTERVAL", "5")

        if not wait_retry_interval.isdigit():
            logger.error("Invalid WAIT_RETRY_INTERVAL value, must be an integer")
            stop(1)
        wait_retry_interval = int(wait_retry_interval)

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
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text(
            encoding="utf-8"
        ):
            INTEGRATION = "Docker"

        del integration_path, os_release_path

        tmp_variables_path = (
            normpath(args.variables)
            if args.variables
            else join(sep, "var", "tmp", "bunkerweb", "variables.env")
        )
        tmp_variables_path = Path(tmp_variables_path)
        nginx_variables_path = NGINX_PATH.joinpath("variables.env")

        db = Database(logger, sqlalchemy_string=getenv("DATABASE_URI"))

        if INTEGRATION in (
            "Swarm",
            "Kubernetes",
            "Autoconf",
        ):
            while not db.is_autoconf_loaded():
                logger.warning(
                    f"Autoconf is not loaded yet in the database, retrying in {wait_retry_interval}s ...",
                )
                sleep(wait_retry_interval)
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
                logger.error(
                    "Config saver failed, try again later or check the logs for more details ...",
                )
                stop(1)

        while not db.is_initialized():
            logger.warning(
                f"Database is not initialized, retrying in {wait_retry_interval}s ...",
            )
            sleep(wait_retry_interval)

        # Instantiate scheduler
        SCHEDULER = JobScheduler(db, logger, INTEGRATION)
        bunkerweb_instances: List[Dict[str, Any]] = db.get_instances()

        if INTEGRATION in ("Swarm", "Kubernetes", "Autoconf", "Docker"):
            # Automatically setup the scheduler apis
            SCHEDULER.auto_setup(bunkerweb_instances=bunkerweb_instances)

        scheduler_first_start = db.is_scheduler_first_start()
        FIRST_RUN = True

        # Checking if any custom config has been created by the user
        custom_configs = {}
        db_configs = db.get_custom_configs()
        updated_instances_custom_configs = []
        changes = False
        for instance in bunkerweb_instances:
            tmp_path = CONFIGS_PATH.joinpath(
                instance["hostname"] if instance["hostname"] != "127.0.0.1" else ""
            )
            custom_configs[instance["hostname"]] = []

            if tmp_path.is_dir():
                root_dirs = listdir(tmp_path)
                for root, dirs, files in walk(tmp_path):
                    if files or (dirs and basename(root) not in root_dirs):
                        path_exploded = root.split("/")
                        for file in files:
                            content = Path(join(root, file)).read_text(encoding="utf-8")
                            custom_conf = {
                                "value": content,
                                "exploded": (
                                    f"{path_exploded.pop()}"
                                    if path_exploded[-1] not in root_dirs
                                    else None,
                                    path_exploded[-1],
                                    file.replace(".conf", ""),
                                ),
                            }

                            saving = True
                            in_db = False

                    for db_conf in db_configs:
                        if (
                            db_conf["service_id"] == custom_conf["exploded"][0]
                            and db_conf["name"] == custom_conf["exploded"][2]
                        ):
                            in_db = True
                            if db_conf["method"] != "manual":
                                saving = False
                                break

                            if not in_db and content.startswith("# CREATED BY ENV"):
                                saving = False
                                changes = True

                    if saving:
                        custom_configs[instance["hostname"]].append(custom_conf)

            if (
                changes
                or instance["hostname"] not in db_configs
                or {
                    hash(dict_to_frozenset(d))
                    for d in custom_configs[instance["hostname"]]
                }
                != {
                    hash(dict_to_frozenset(d)) for d in db_configs[instance["hostname"]]
                }
            ):
                updated_instances_custom_configs.append(instance["hostname"])

        if updated_instances_custom_configs:
            err = db.save_custom_configs(custom_configs, "manual")
            if err:
                logger.error(
                    f"Couldn't save some manually created custom configs to database: {err}",
                )

        if (scheduler_first_start and db_configs) or changes:
            Thread(
                target=generate_custom_configs,
                args=(db.get_custom_configs(),),
                kwargs={"updated_instances": updated_instances_custom_configs},
            ).start()

        del custom_configs, db_configs

        # Check if any external plugin has been added by the user
        external_plugins = []
        db_plugins = db.get_plugins(external=True)
        for filename in glob(str(EXTERNAL_PLUGINS_PATH.joinpath("*", "plugin.json"))):
            with open(filename, "r", encoding="utf-8") as f:
                _dir = dirname(filename)
                plugin_content = BytesIO()
                with tar_open(
                    fileobj=plugin_content, mode="w:gz", compresslevel=9
                ) as tar:
                    tar.add(_dir, arcname=basename(_dir), recursive=True)
                plugin_content.seek(0, 0)
                value = plugin_content.getvalue()

                external_plugins.append(
                    json_load(f)
                    | {
                        "external": True,
                        "page": Path(_dir, "ui").exists(),
                        "method": "manual",
                        "data": value,
                        "checksum": sha256(value).hexdigest(),
                    }
                )

        tmp_external_plugins = []
        for external_plugin in external_plugins.copy():
            external_plugin.pop("data", None)
            external_plugin.pop("checksum", None)
            external_plugin.pop("jobs", None)
            tmp_external_plugins.append(external_plugin)

        changes = {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != {
            hash(dict_to_frozenset(d)) for d in db_plugins
        }

        if changes:
            err = db.update_external_plugins(external_plugins, delete_missing=True)
            if err:
                logger.error(
                    f"Couldn't save some manually added plugins to database: {err}",
                )

        if (scheduler_first_start and db_plugins) or changes:
            generate_external_plugins(db.get_plugins(external=True, with_data=True))
            SCHEDULER.update_jobs()

        del tmp_external_plugins, external_plugins, db_plugins

        logger.info("Scheduler started ...")

        changes = db.check_changes()

        if isinstance(changes, str):
            logger.error(
                f"An error occurred when checking for changes in the database : {changes}"
            )
            stop(1)

        all_instances_hostname = [
            instance["hostname"] for instance in bunkerweb_instances
        ]
        CHANGES = {
            "config": all_instances_hostname,
            "custom_configs": all_instances_hostname,
            "external_plugins": True,
        }
        threads = []

        GENERATE = (
            not nginx_variables_path.exists()
            or (
                tmp_variables_path.read_text(encoding="utf-8")
                != nginx_variables_path.read_text(encoding="utf-8")
            )
            or changes["custom_configs_changed"]
            or changes["config_changed"]
        )
        updated_instances_custom_configs = all_instances_hostname.copy()
        updated_instances_config = all_instances_hostname.copy()

        if not GENERATE:
            updated_instances_config.clear()
            logger.warning(
                "Looks like BunkerWeb configuration is already generated, will not generate it again ..."
            )

        if scheduler_first_start:
            ret = db.set_scheduler_first_start()

            if ret:
                logger.error(
                    f"An error occurred when setting the scheduler first start : {ret}"
                )
                stop(1)

        def send_nginx_config(instance_hostname):
            nginx_path = NGINX_PATH.joinpath(
                instance_hostname if instance_hostname != "127.0.0.1" else ""
            )
            tmp_variables_path = Path(
                sep,
                "var",
                "tmp",
                "bunkerweb",
                instance_hostname if instance_hostname != "127.0.0.1" else "",
                "variables.env",
            )
            tmp_variables_path.parent.mkdir(parents=True, exist_ok=True)

            copy(str(nginx_path.joinpath("variables.env")), str(tmp_variables_path))

            if SCHEDULER.apis and nginx_path.exists():
                instance_api = None
                for api in SCHEDULER.apis:
                    if f"{instance_hostname}:" in api.endpoint:
                        instance_api = api
                        break

                if not instance_api:
                    logger.error(
                        f"Could not find an API for instance {instance_hostname}, NGINX configuration will not be sent to it...",
                    )
                    return

                logger.info(f"Sending nginx configs to {instance_hostname}...")

                ret = SCHEDULER.send_files(nginx_path, "/confs", apis=[instance_api])
                if not ret:
                    logger.error(
                        f"Sending nginx configs to {instance_hostname} failed, configuration will not work as expected...",
                    )

        while True:
            threads.clear()
            ret = db.checked_changes(CHANGES)

            if ret:
                logger.error(
                    f"An error occurred when setting the changes to checked in the database : {ret}"
                )
                stop(1)

            # Update the environment variables of the scheduler
            SCHEDULER.env = environ.copy()
            SCHEDULER.setup()

            # Only run jobs once
            if not SCHEDULER.run_once():
                logger.error("At least one job in run_once() failed")
            else:
                logger.info("All jobs in run_once() were successful")

            if GENERATE:
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
                        str(NGINX_PATH),
                    ]
                    + (
                        ["--variables", str(tmp_variables_path)]
                        if args.variables and FIRST_RUN
                        else []
                    ),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                    check=False,
                )

                if proc.returncode != 0:
                    logger.error(
                        "Config generator failed, configuration will not work as expected...",
                    )
                else:
                    # send nginx configs
                    for instance in updated_instances_config:
                        thread = Thread(target=send_nginx_config, args=(instance,))
                        thread.start()
                        threads.append(thread)

            try:
                if SCHEDULER.apis:
                    for thread in threads:
                        thread.join()

                    if SCHEDULER.send_to_apis("POST", "/reload"):
                        logger.info("Successfully reloaded nginx")
                    else:
                        logger.error("Error while reloading nginx")
                else:
                    # Stop temp nginx
                    logger.info("Stopping temp nginx ...")
                    proc = subprocess_run(
                        ["sudo", join(sep, "usr", "sbin", "nginx"), "-s", "stop"],
                        stdin=DEVNULL,
                        stderr=STDOUT,
                        env=env.copy(),
                        check=False,
                    )
                    if proc.returncode == 0:
                        logger.info("Successfully sent stop signal to temp nginx")
                        i = 0
                        while i < 20:
                            if not Path(
                                sep, "var", "run", "bunkerweb", "nginx.pid"
                            ).is_file():
                                break
                            logger.warning("Waiting for temp nginx to stop ...")
                            sleep(1)
                            i += 1
                        if i >= 20:
                            logger.error(
                                "Timeout error while waiting for temp nginx to stop"
                            )
                        else:
                            # Start nginx
                            logger.info("Starting nginx ...")
                            proc = subprocess_run(
                                ["sudo", join(sep, "usr", "sbin", "nginx")],
                                stdin=DEVNULL,
                                stderr=STDOUT,
                                env=env.copy(),
                                check=False,
                            )
                            if proc.returncode == 0:
                                logger.info("Successfully started nginx")
                            else:
                                logger.error(
                                    f"Error while starting nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8') if proc.stderr else 'Missing stderr'}",
                                )
                    else:
                        logger.error(
                            f"Error while sending stop signal to temp nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8') if proc.stderr else 'Missing stderr'}",
                        )
            except:
                logger.error(
                    f"Exception while reloading after running jobs once scheduling : {format_exc()}",
                )

            GENERATE = True
            NEED_RELOAD = False
            PLUGINS_NEED_GENERATION = False
            updated_instances_config.clear()
            updated_instances_custom_configs.clear()

            # infinite schedule for the jobs
            logger.info("Executing job scheduler ...")
            if not SCHEDULER_HEALTHY_PATH.exists():
                SCHEDULER_HEALTHY_PATH.write_text("ok", encoding="utf-8")
            while RUN and not NEED_RELOAD:
                SCHEDULER.run_pending()
                sleep(1)

                changes = db.check_changes()

                if isinstance(changes, str):
                    logger.error(
                        f"An error occurred when checking for changes in the database : {changes}"
                    )
                    stop(1)

                # check if the plugins have changed since last time
                if changes["external_plugins_changed"]:
                    logger.info("External plugins changed, generating ...")

                    if FIRST_RUN:
                        # run the config saver to save potential ignored external plugins settings
                        logger.info(
                            "Running config saver to save potential ignored external plugins settings ..."
                        )
                        proc = subprocess_run(
                            [
                                "python",
                                join(
                                    sep,
                                    "usr",
                                    "share",
                                    "bunkerweb",
                                    "gen",
                                    "save_config.py",
                                ),
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

                        changes.update(
                            {
                                "custom_configs_changed": all_instances_hostname,
                                "config_changed": all_instances_hostname,
                            }
                        )

                    PLUGINS_NEED_GENERATION = True
                    NEED_RELOAD = True

                # check if the custom configs have changed since last time
                if changes["custom_configs_changed"]:
                    logger.info("Custom configs changed, generating ...")
                    updated_instances_custom_configs = changes["custom_configs_changed"]
                    NEED_RELOAD = True

                # check if the config have changed since last time
                if changes["config_changed"]:
                    logger.info("Config changed, generating ...")
                    updated_instances_config = changes["config_changed"]
                    NEED_RELOAD = True

            FIRST_RUN = False

            if NEED_RELOAD:
                CHANGES.update(
                    {
                        "config": [],
                        "custom_configs": [],
                        "external_plugins": False,
                    }
                )

                if updated_instances_custom_configs:
                    CHANGES["custom_configs"] = updated_instances_custom_configs.copy()
                    Thread(
                        target=generate_custom_configs,
                        args=(db.get_custom_configs(),),
                        kwargs={"updated_instances": CHANGES["custom_configs"]},
                    ).start()

                if PLUGINS_NEED_GENERATION:
                    CHANGES["external_plugins"] = True
                    generate_external_plugins(
                        db.get_plugins(external=True, with_data=True)
                    )
                    SCHEDULER.update_jobs()

                if updated_instances_config:
                    CHANGES["config"] = updated_instances_config.copy()
                    env = db.get_config()
    except SystemExit as e:
        _exit(e.code)
    except:
        logger.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)
