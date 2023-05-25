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
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from dotenv import dotenv_values

from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from JobScheduler import JobScheduler
from ApiCaller import ApiCaller  # type: ignore

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


# Function to catch SIGHUP and reload the scheduler
def handle_reload(signum, frame):
    global reloading, run, scheduler
    reloading = True
    try:
        if scheduler is not None and run:
            # Get the env by reading the .env file
            env = dotenv_values(join(sep, "etc", "bunkerweb", "variables.env"))
            if scheduler.reload(env):
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
    Path(sep, "var", "tmp", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy").unlink(missing_ok=True)
    _exit(status)


def generate_custom_configs(
    custom_configs: List[Dict[str, Any]],
    integration: str,
    api_caller: ApiCaller,
    *,
    original_path: str = join(sep, "etc", "bunkerweb", "configs"),
):
    logger.info("Generating new custom configs ...")
    Path(original_path).mkdir(parents=True, exist_ok=True)
    for custom_config in custom_configs:
        tmp_path = join(original_path, custom_config["type"].replace("_", "-"))
        if custom_config["service_id"]:
            tmp_path = join(tmp_path, custom_config["service_id"])
        tmp_path = Path(tmp_path, f"{custom_config['name']}.conf")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(custom_config["data"])

    if integration in ("Autoconf", "Swarm", "Kubernetes", "Docker"):
        logger.info("Sending custom configs to BunkerWeb")
        ret = api_caller._send_files(original_path, "/custom_configs")

        if not ret:
            logger.error(
                "Sending custom configs failed, configuration will not work as expected...",
            )


def generate_external_plugins(
    plugins: List[Dict[str, Any]],
    integration: str,
    api_caller: ApiCaller,
    *,
    original_path: str = join(sep, "etc", "bunkerweb", "plugins"),
):
    logger.info("Generating new external plugins ...")
    Path(original_path).mkdir(parents=True, exist_ok=True)
    for plugin in plugins:
        tmp_path = Path(original_path, plugin["id"], f"{plugin['name']}.tar.gz")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(plugin["data"])
        with tar_open(str(tmp_path), "r:gz") as tar:
            tar.extractall(original_path)
        tmp_path.unlink()

        for job_file in glob(join(str(tmp_path.parent), "jobs", "*")):
            st = Path(job_file).stat()
            chmod(job_file, st.st_mode | S_IEXEC)

    if integration in ("Autoconf", "Swarm", "Kubernetes", "Docker"):
        logger.info("Sending plugins to BunkerWeb")
        ret = api_caller._send_files(original_path, "/plugins")

        if not ret:
            logger.error(
                "Sending plugins failed, configuration will not work as expected...",
            )


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "tmp", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            logger.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()))

        del pid_path

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
        db_configs = None
        tmp_variables_path = Path(
            normpath(args.variables) if args.variables else sep,
            "var",
            "tmp",
            "bunkerweb",
            "variables.env",
        )

        logger.info("Scheduler started ...")

        # Checking if the argument variables is true.
        if args.variables:
            logger.info(f"Variables : {tmp_variables_path}")

            # Read env file
            env = dotenv_values(str(tmp_variables_path))

            db = Database(
                logger,
                sqlalchemy_string=env.get("DATABASE_URI", getenv("DATABASE_URI", None)),
            )

            while not db.is_initialized():
                logger.warning(
                    "Database is not initialized, retrying in 5s ...",
                )
                sleep(5)

            db_configs = db.get_custom_configs()
        else:
            # Read from database
            integration = "Docker"
            integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
            if integration_path.is_file():
                integration = integration_path.read_text().strip()

            del integration_path

            api_caller.auto_setup(bw_integration=integration)
            db = Database(
                logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
            )

            if db.is_initialized():
                db_configs = db.get_custom_configs()

            if integration in (
                "Swarm",
                "Kubernetes",
                "Autoconf",
            ):
                while not db.is_autoconf_loaded():
                    logger.warning(
                        "Autoconf is not loaded yet in the database, retrying in 5s ...",
                    )
                    sleep(5)
            elif not tmp_variables_path.is_file() or db.get_config() != dotenv_values(
                str(tmp_variables_path)
            ):
                # run the config saver
                proc = subprocess_run(
                    [
                        "python",
                        join(sep, "usr", "share", "bunkerweb", "gen", "save_config.py"),
                        "--settings",
                        join(sep, "usr", "share", "bunkerweb", "settings.json"),
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

            if not db_configs:
                db_configs = db.get_custom_configs()

            env = db.get_config()
            while not db.is_first_config_saved() or not env:
                logger.warning(
                    "Database doesn't have any config saved yet, retrying in 5s ...",
                )
                sleep(5)
                env = db.get_config()

            env["DATABASE_URI"] = db.get_database_uri()

        # Checking if any custom config has been created by the user
        custom_configs = []
        configs_path = join(sep, "etc", "bunkerweb", "configs")
        root_dirs = listdir(configs_path)
        for root, dirs, files in walk(configs_path):
            if files or (dirs and basename(root) not in root_dirs):
                path_exploded = root.split("/")
                for file in files:
                    with open(join(root, file), "r") as f:
                        custom_conf = {
                            "value": f.read(),
                            "exploded": (
                                f"{path_exploded.pop()}"
                                if path_exploded[-1] not in root_dirs
                                else None,
                                path_exploded[-1],
                                file.replace(".conf", ""),
                            ),
                        }

                    saving = True
                    for db_conf in db_configs:
                        if (
                            db_conf["method"] != "manual"
                            and db_conf["service_id"] == custom_conf["exploded"][0]
                            and db_conf["name"] == custom_conf["exploded"][2]
                        ):
                            saving = False
                            break

                    if saving:
                        custom_configs.append(custom_conf)

        err = db.save_custom_configs(custom_configs, "manual")
        if err:
            logger.error(
                f"Couldn't save some manually created custom configs to database: {err}",
            )

        # Remove old custom configs files
        logger.info("Removing old custom configs files ...")
        for file in glob(join(configs_path, "*", "*")):
            file = Path(file)
            if file.is_symlink() or file.is_file():
                file.unlink()
            elif file.is_dir():
                rmtree(str(file), ignore_errors=True)

        db_configs = db.get_custom_configs()

        if db_configs:
            logger.info("Generating new custom configs ...")
            generate_custom_configs(db_configs, integration, api_caller)

        # Check if any external plugin has been added by the user
        external_plugins = []
        plugins_dir = join(sep, "etc", "bunkerweb", "plugins")
        for filename in glob(join(plugins_dir, "*", "plugin.json")):
            with open(filename, "r") as f:
                _dir = dirname(filename)
                plugin_content = BytesIO()
                with tar_open(
                    fileobj=plugin_content, mode="w:gz", compresslevel=9
                ) as tar:
                    tar.add(_dir, arcname=basename(_dir), recursive=True)
                plugin_content.seek(0)
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

        if external_plugins:
            err = db.update_external_plugins(external_plugins, delete_missing=False)
            if err:
                logger.error(
                    f"Couldn't save some manually added plugins to database: {err}",
                )

        external_plugins = db.get_plugins(external=True)
        if external_plugins:
            # Remove old external plugins files
            logger.info("Removing old external plugins files ...")
            for file in glob(join(plugins_dir, "*")):
                file = Path(file)
                if file.is_symlink() or file.is_file():
                    file.unlink()
                elif file.is_dir():
                    rmtree(str(file), ignore_errors=True)

            generate_external_plugins(
                db.get_plugins(external=True, with_data=True),
                integration,
                api_caller,
                original_path=plugins_dir,
            )

        logger.info("Executing scheduler ...")

        generate = not tmp_variables_path.exists() or env != dotenv_values(
            str(tmp_variables_path)
        )

        if not generate:
            logger.warning(
                "Looks like BunkerWeb configuration is already generated, will not generate it again ..."
            )

        first_run = True
        while True:
            # Instantiate scheduler
            scheduler = JobScheduler(
                env=env.copy() | environ.copy(),
                apis=api_caller._get_apis(),
                logger=logger,
                integration=integration,
            )

            # Only run jobs once
            if not scheduler.run_once():
                logger.error("At least one job in run_once() failed")
            else:
                logger.info("All jobs in run_once() were successful")

            if generate:
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
                    ]
                    + (
                        ["--variables", str(tmp_variables_path)]
                        if args.variables and first_run
                        else []
                    ),
                    stdin=DEVNULL,
                    stderr=STDOUT,
                )

                if proc.returncode != 0:
                    logger.error(
                        "Config generator failed, configuration will not work as expected...",
                    )
                else:
                    copy(
                        join(sep, "etc", "nginx", "variables.env"),
                        str(tmp_variables_path),
                    )

                    if api_caller._get_apis():
                        # send nginx configs
                        logger.info(f"Sending {join(sep, 'etc', 'nginx')} folder ...")
                        ret = api_caller._send_files(
                            join(sep, "etc", "nginx"), "/confs"
                        )
                        if not ret:
                            logger.error(
                                "Sending nginx configs failed, configuration will not work as expected...",
                            )

            try:
                if api_caller._get_apis():
                    cache_path = join(sep, "var", "cache", "bunkerweb")
                    # send cache
                    logger.info(f"Sending {cache_path} folder ...")
                    if not api_caller._send_files(cache_path, "/cache"):
                        logger.error(f"Error while sending {cache_path} folder")
                    else:
                        logger.info(f"Successfully sent {cache_path} folder")

                # restart nginx
                if integration not in ("Autoconf", "Swarm", "Kubernetes", "Docker"):
                    # Stop temp nginx
                    logger.info("Stopping temp nginx ...")
                    proc = subprocess_run(
                        ["sudo", join(sep, "usr", "sbin", "nginx"), "-s", "stop"],
                        stdin=DEVNULL,
                        stderr=STDOUT,
                        env=env.copy(),
                    )
                    if proc.returncode == 0:
                        logger.info("Successfully sent stop signal to temp nginx")
                        i = 0
                        while i < 20:
                            if not Path(
                                sep, "var", "tmp", "bunkerweb", "nginx.pid"
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
                else:
                    if api_caller._send_to_apis("POST", "/reload"):
                        logger.info("Successfully reloaded nginx")
                    else:
                        logger.error("Error while reloading nginx")
            except:
                logger.error(
                    f"Exception while reloading after running jobs once scheduling : {format_exc()}",
                )

            generate = True
            scheduler.setup()
            need_reload = False
            first_run = False

            # infinite schedule for the jobs
            logger.info("Executing job scheduler ...")
            Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy").write_text("ok")
            while run and not need_reload:
                scheduler.run_pending()
                sleep(1)

                # check if the custom configs have changed since last time
                tmp_db_configs: Dict[str, Any] = db.get_custom_configs()
                if db_configs != tmp_db_configs:
                    logger.info("Custom configs changed, generating ...")
                    logger.debug(f"{tmp_db_configs=}")
                    logger.debug(f"{db_configs=}")
                    db_configs = tmp_db_configs.copy()

                    # Remove old custom configs files
                    logger.info("Removing old custom configs files ...")
                    for file in glob(join(configs_path, "*", "*")):
                        file = Path(file)
                        if file.is_symlink() or file.is_file():
                            file.unlink()
                        elif file.is_dir():
                            rmtree(str(file), ignore_errors=True)

                    generate_custom_configs(
                        db_configs,
                        integration,
                        api_caller,
                        original_path=configs_path,
                    )

                    # reload nginx
                    logger.info("Reloading nginx ...")
                    if integration not in (
                        "Autoconf",
                        "Swarm",
                        "Kubernetes",
                        "Docker",
                    ):
                        # Reloading the nginx server.
                        proc = subprocess_run(
                            # Reload nginx
                            ["sudo", join(sep, "usr", "sbin", "nginx"), "-s", "reload"],
                            stdin=DEVNULL,
                            stderr=STDOUT,
                            env=env.copy(),
                        )
                        if proc.returncode == 0:
                            logger.info("Successfully reloaded nginx")
                        else:
                            logger.error(
                                f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8') if proc.stderr else 'Missing stderr'}",
                            )
                    else:
                        need_reload = True

                # check if the plugins have changed since last time
                tmp_external_plugins: List[Dict[str, Any]] = db.get_plugins(
                    external=True
                )
                if external_plugins != tmp_external_plugins:
                    logger.info("External plugins changed, generating ...")
                    logger.debug(f"{tmp_external_plugins=}")
                    logger.debug(f"{external_plugins=}")
                    external_plugins = tmp_external_plugins.copy()

                    # Remove old external plugins files
                    logger.info("Removing old external plugins files ...")
                    for file in glob(join(plugins_dir, "*")):
                        file = Path(file)
                        if file.is_symlink() or file.is_file():
                            file.unlink()
                        elif file.is_dir():
                            rmtree(str(file), ignore_errors=True)

                    logger.info("Generating new external plugins ...")
                    generate_external_plugins(
                        db.get_plugins(external=True, with_data=True),
                        integration,
                        api_caller,
                        original_path=plugins_dir,
                    )
                    need_reload = True

                # check if the config have changed since last time
                tmp_env: Dict[str, Any] = db.get_config()
                tmp_env["DATABASE_URI"] = environ.get(
                    "DATABASE_URI", tmp_env["DATABASE_URI"]
                )
                if env != tmp_env:
                    logger.info("Config changed, generating ...")
                    logger.debug(f"{tmp_env=}")
                    logger.debug(f"{env=}")
                    env = tmp_env.copy()
                    need_reload = True
    except:
        logger.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)
