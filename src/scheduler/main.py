#!/usr/bin/python3

from argparse import ArgumentParser
from copy import deepcopy
from glob import glob
from os import (
    _exit,
    chmod,
    getenv,
    getpid,
    listdir,
    makedirs,
    path,
    remove,
    unlink,
    walk,
)
from os.path import dirname, exists, isdir, isfile, islink, join
from shutil import chown, copy, rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List

sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")
sys_path.append("/usr/share/bunkerweb/api")
sys_path.append("/usr/share/bunkerweb/db")

from dotenv import dotenv_values

from logger import setup_logger
from Database import Database
from JobScheduler import JobScheduler
from ApiCaller import ApiCaller

run = True
scheduler = None
reloading = False
logger = setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))


def handle_stop(signum, frame):
    global run, scheduler
    run = False
    if scheduler is not None:
        scheduler.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


def imerge(a, b):
    for i, j in zip(a, b):
        yield i
        yield j


def handle_reload(signum, frame, env):
    global run, scheduler, reloading
    try:
        if scheduler is not None and run:
            # Loading the environment variables from the .env file.
            if scheduler.reload(dotenv_values(env)):
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


def stop(status):
    remove("/var/tmp/bunkerweb/scheduler.pid")
    _exit(status)


def generate_custom_configs(
    custom_configs: List[Dict[str, Any]],
    integration: str,
    api_caller: ApiCaller,
    *,
    original_path: str = "/data/configs",
):
    makedirs(original_path, exist_ok=True)
    for custom_config in custom_configs:
        tmp_path = f"{original_path}/{custom_config['type'].replace('_', '-')}"
        if custom_config["service_id"]:
            tmp_path += f"/{custom_config['service_id']}"
        tmp_path += f"/{custom_config['name']}.conf"
        makedirs(dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "wb") as f:
            f.write(custom_config["data"])

    # Fix permissions for the custom configs folder
    for root, dirs, files in walk("/data/configs", topdown=False):
        for name in files + dirs:
            chown(join(root, name), "scheduler", "scheduler")

            if isdir(join(root, name)):
                chmod(join(root, name), 0o750)
            if isfile(join(root, name)):
                chmod(join(root, name), 0o740)

    if integration != "Linux":
        logger.info("Sending custom configs to BunkerWeb")
        ret = api_caller._send_files("/data/configs", "/custom_configs")

        if not ret:
            logger.error(
                "Sending custom configs failed, configuration will not work as expected...",
            )


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        if path.isfile("/var/tmp/bunkerweb/scheduler.pid"):
            logger.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        with open("/var/tmp/bunkerweb/scheduler.pid", "w") as f:
            f.write(str(getpid()))

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument(
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        args = parser.parse_args()
        generate = False
        integration = "Linux"
        api_caller = ApiCaller()

        # Define db here because otherwhise it will be undefined for Linux
        db = Database(
            logger,
            sqlalchemy_string=getenv("DATABASE_URI", None),
        )
        # END Define db because otherwhise it will be undefined for Linux

        logger.info("Scheduler started ...")

        # Checking if the argument variables is true.
        if args.variables:
            logger.info(f"Variables : {args.variables}")

            # Read env file
            env = dotenv_values(args.variables)

            db = Database(
                logger,
                sqlalchemy_string=env.get("DATABASE_URI", None),
            )

            while not db.is_initialized():
                logger.warning(
                    "Database is not initialized, retrying in 5s ...",
                )
                sleep(5)
        else:
            # Read from database
            integration = "Docker"
            if exists("/usr/share/bunkerweb/INTEGRATION"):
                with open("/usr/share/bunkerweb/INTEGRATION", "r") as f:
                    integration = f.read().strip()

            api_caller.auto_setup(bw_integration=integration)
            db = Database(
                logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
            )

            if integration in (
                "Swarm",
                "Kubernetes",
                "Autoconf",
            ):
                err = db.set_autoconf_load(False)
                if err:
                    success = False
                    logger.error(
                        f"Can't set autoconf loaded metadata to false in database: {err}",
                    )

                while not db.is_autoconf_loaded():
                    logger.warning(
                        "Autoconf is not loaded yet in the database, retrying in 5s ...",
                    )
                    sleep(5)
            elif integration == "Docker" and (
                not exists("/var/tmp/bunkerweb/variables.env")
                or db.get_config() != dotenv_values("/var/tmp/bunkerweb/variables.env")
            ):
                # run the config saver
                proc = subprocess_run(
                    [
                        "python",
                        "/usr/share/bunkerweb/gen/save_config.py",
                        "--settings",
                        "/usr/share/bunkerweb/settings.json",
                    ],
                    stdin=DEVNULL,
                    stderr=STDOUT,
                )
                if proc.returncode != 0:
                    logger.error(
                        "Config saver failed, configuration will not work as expected...",
                    )

            while not db.is_initialized():
                logger.warning(
                    "Database is not initialized, retrying in 5s ...",
                )
                sleep(5)

            env = db.get_config()
            while not db.is_first_config_saved() or not env:
                logger.warning(
                    "Database doesn't have any config saved yet, retrying in 5s ...",
                )
                sleep(5)
                env = db.get_config()

            env["DATABASE_URI"] = db.get_database_uri()

        # Checking if any custom config has been created by the user
        custom_confs = []
        root_dirs = listdir("/etc/bunkerweb/configs")
        for (root, dirs, files) in walk("/etc/bunkerweb/configs", topdown=True):
            if (
                root != "configs"
                and (dirs and not root.split("/")[-1] in root_dirs)
                or files
            ):
                path_exploded = root.split("/")
                for file in files:
                    with open(join(root, file), "r") as f:
                        custom_confs.append(
                            {
                                "value": f.read(),
                                "exploded": (
                                    f"{path_exploded.pop()}"
                                    if path_exploded[-1] not in root_dirs
                                    else "",
                                    path_exploded[-1],
                                    file.replace(".conf", ""),
                                ),
                            }
                        )

        old_configs = None
        if custom_confs:
            old_configs = db.get_custom_configs()

            err = db.save_custom_configs(custom_confs, "manual")
            if err:
                logger.error(
                    f"Couldn't save some manually created custom configs to database: {err}",
                )

        custom_configs = db.get_custom_configs()

        if old_configs != custom_configs:
            generate_custom_configs(custom_configs, integration, api_caller)

        logger.info("Executing scheduler ...")

        generate = not exists(
            "/var/tmp/bunkerweb/variables.env"
        ) or env != dotenv_values("/var/tmp/bunkerweb/variables.env")

        if generate is False:
            logger.warning(
                "Looks like BunkerWeb configuration is already generated, will not generate it again ..."
            )

        if exists("/var/lib/bunkerweb/db.sqlite3"):
            chmod("/var/lib/bunkerweb/db.sqlite3", 0o760)

        while True:
            # Instantiate scheduler
            scheduler = JobScheduler(
                env=deepcopy(env),
                apis=api_caller._get_apis(),
                logger=logger,
                integration=integration,
            )

            # Only run jobs once
            if not scheduler.run_once():
                logger.error("At least one job in run_once() failed")
            else:
                logger.info("All jobs in run_once() were successful")

            if generate is True:
                # run the generator
                proc = subprocess_run(
                    [
                        "python3",
                        "/usr/share/bunkerweb/gen/main.py",
                        "--settings",
                        "/usr/share/bunkerweb/settings.json",
                        "--templates",
                        "/usr/share/bunkerweb/confs",
                        "--output",
                        "/etc/nginx",
                    ]
                    + (["--variables", args.variables] if args.variables else []),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                )

                if proc.returncode != 0:
                    logger.error(
                        "Config generator failed, configuration will not work as expected...",
                    )
                else:
                    # Fix permissions for the nginx folder
                    for root, dirs, files in walk("/etc/nginx", topdown=False):
                        for name in files + dirs:
                            chown(join(root, name), "scheduler", "scheduler")
                            chmod(join(root, name), 0o770)

                    copy("/etc/nginx/variables.env", "/var/tmp/bunkerweb/variables.env")

                    if len(api_caller._get_apis()) > 0:
                        # send nginx configs
                        logger.info("Sending /etc/nginx folder ...")
                        ret = api_caller._send_files("/etc/nginx", "/confs")
                        if not ret:
                            logger.error(
                                "Sending nginx configs failed, configuration will not work as expected...",
                            )

            # Fix permissions for the cache and the custom configs folders
            for root, dirs, files in imerge(
                walk("/data/cache", topdown=False), walk("/data/configs", topdown=False)
            ):
                for name in files + dirs:
                    chown(join(root, name), "scheduler", "scheduler")

                    if isdir(join(root, name)):
                        chmod(join(root, name), 0o750)
                    if isfile(join(root, name)):
                        chmod(join(root, name), 0o740)

            try:
                if len(api_caller._get_apis()) > 0:
                    # send cache
                    logger.info("Sending /data/cache folder ...")
                    if not api_caller._send_files("/data/cache", "/cache"):
                        logger.error("Error while sending /data/cache folder")
                    else:
                        logger.info("Successfuly sent /data/cache folder")

                # reload nginx
                if integration == "Linux":
                    logger.info("Reloading nginx ...")
                    # Reloading the nginx server.
                    # Had to use this instead of the nginx reload command because it was not working
                    proc = subprocess_run(
                        # Reload nginx
                        ["/etc/init.d/nginx", "reload"],
                        # ["nginx", "-s", "reload"],
                        stdin=DEVNULL,
                        stderr=STDOUT,
                        env=deepcopy(env),
                    )
                    if proc.returncode == 0:
                        logger.info("Successfuly reloaded nginx")
                    else:
                        logger.error(
                            f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8')}",
                        )
                else:
                    logger.info("Reloading nginx ...")
                    if api_caller._send_to_apis("POST", "/reload"):
                        logger.info("Successfuly reloaded nginx")
                    else:
                        logger.error("Error while reloading nginx")
            except:
                logger.error(
                    f"Exception while reloading after running jobs once scheduling : {format_exc()}",
                )

            # infinite schedule for the jobs
            generate = True
            scheduler.setup()
            logger.info("Executing job scheduler ...")
            while run:
                scheduler.run_pending()
                sleep(1)

                if not args.variables:
                    # check if the custom configs have changed since last time
                    tmp_custom_configs = db.get_custom_configs()
                    if custom_configs != tmp_custom_configs:
                        logger.info("Custom configs changed, generating ...")
                        logger.debug(f"{tmp_custom_configs}")
                        logger.debug(f"{custom_configs}")
                        custom_configs = tmp_custom_configs
                        original_path = "/data/configs"

                        # Remove old custom configs files
                        logger.info("Removing old custom configs files ...")
                        files = glob(f"{original_path}/*")
                        for file in files:
                            if islink(file):
                                unlink(file)
                            elif isfile(file):
                                remove(file)
                            elif isdir(file):
                                rmtree(file, ignore_errors=False)

                        logger.info("Generating new custom configs ...")
                        generate_custom_configs(custom_configs, integration, api_caller)

                    # check if the config have changed since last time
                    tmp_env = db.get_config()
                    if env != tmp_env:
                        logger.info("Config changed, generating ...")
                        logger.debug(f"{tmp_env=}")
                        logger.debug(f"{env=}")
                        env = deepcopy(tmp_env)
                        break
    except:
        logger.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)
