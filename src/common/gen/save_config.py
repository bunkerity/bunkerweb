#!/usr/bin/python3

from argparse import ArgumentParser
from glob import glob
from itertools import chain
from json import loads
from os import R_OK, X_OK, access, environ, getenv, listdir, walk
from os.path import join
from pathlib import Path
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Any


sys_path.extend(
    (
        "/usr/share/bunkerweb/deps/python",
        "/usr/share/bunkerweb/utils",
        "/usr/share/bunkerweb/api",
        "/usr/share/bunkerweb/db",
    )
)

from docker import DockerClient

from logger import setup_logger
from Database import Database
from Configurator import Configurator
from API import API

custom_confs_rx = re_compile(
    r"^([0-9a-z\.-]*)_?CUSTOM_CONF_(HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$"
)


def get_instance_configs_and_apis(instance: Any, db, _type="Docker"):
    api_http_port = None
    api_server_name = None
    tmp_config = {}
    custom_confs = []
    apis = []

    for var in (
        instance.attrs["Config"]["Env"]
        if _type == "Docker"
        else instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]
    ):
        splitted = var.split("=", 1)
        if custom_confs_rx.match(splitted[0]):
            custom_confs.append(
                {
                    "value": splitted[1],
                    "exploded": custom_confs_rx.search(splitted[0]).groups(),
                }
            )
        else:
            tmp_config[splitted[0]] = splitted[1]

            if not db and splitted[0] == "DATABASE_URI":
                db = Database(
                    logger,
                    sqlalchemy_string=splitted[1],
                )
            elif splitted[0] == "API_HTTP_PORT":
                api_http_port = splitted[1]
            elif splitted[0] == "API_SERVER_NAME":
                api_server_name = splitted[1]

    apis.append(
        API(
            f"http://{instance.name}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
            host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
        )
    )

    return tmp_config, custom_confs, apis, db


if __name__ == "__main__":
    logger = setup_logger("Generator", getenv("LOG_LEVEL", "INFO"))
    wait_retry_interval = getenv("WAIT_RETRY_INTERVAL", "5")

    if not wait_retry_interval.isdigit():
        logger.error("Invalid WAIT_RETRY_INTERVAL value, must be an integer")
        sys_exit(1)

    wait_retry_interval = int(wait_retry_interval)

    try:
        # Parse arguments
        parser = ArgumentParser(description="BunkerWeb config saver")
        parser.add_argument(
            "--settings",
            default="/usr/share/bunkerweb/settings.json",
            type=str,
            help="file containing the main settings",
        )
        parser.add_argument(
            "--core",
            default="/usr/share/bunkerweb/core",
            type=str,
            help="directory containing the core plugins",
        )
        parser.add_argument(
            "--plugins",
            default="/etc/bunkerweb/plugins",
            type=str,
            help="directory containing the external plugins",
        )
        parser.add_argument(
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        parser.add_argument(
            "--init",
            action="store_true",
            help="Only initialize the database",
        )
        parser.add_argument(
            "--method",
            default="scheduler",
            type=str,
            help="The method that is used to save the config",
        )
        args = parser.parse_args()

        logger.info("Save config started ...")
        logger.info(f"Settings : {args.settings}")
        logger.info(f"Core : {args.core}")
        logger.info(f"Plugins : {args.plugins}")
        logger.info(f"Init : {args.init}")

        integration = "Linux"
        if getenv("KUBERNETES_MODE", "no") == "yes":
            integration = "Kubernetes"
        elif getenv("SWARM_MODE", "no") == "yes":
            integration = "Swarm"
        elif getenv("AUTOCONF_MODE", "no") == "yes":
            integration = "Autoconf"
        elif Path("/usr/share/bunkerweb/INTEGRATION").is_file():
            integration = Path("/usr/share/bunkerweb/INTEGRATION").read_text().strip()

        if args.init:
            logger.info(f"Detected {integration} integration")

        config_files = None
        db = None
        apis = []

        plugins = args.plugins
        plugins_settings = None
        if not Path("/usr/sbin/nginx").exists() and args.method == "ui":
            db = Database(logger)
            plugins = {}
            plugins_settings = []
            for plugin in db.get_plugins():
                plugins_settings.append(plugin)
                plugins.update(plugin["settings"])

        # Check existences and permissions
        logger.info("Checking arguments ...")
        files = [args.settings] + ([args.variables] if args.variables else [])
        paths_rx = [args.core, args.plugins]
        for file in files:
            if not Path(file).is_file():
                logger.error(f"Missing file : {file}")
                sys_exit(1)
            if not access(file, R_OK):
                logger.error(f"Can't read file : {file}")
                sys_exit(1)
        for path in paths_rx:
            if not Path(path).is_dir():
                logger.error(f"Missing directory : {path}")
                sys_exit(1)
            if not access(path, R_OK | X_OK):
                logger.error(
                    f"Missing RX rights on directory : {path}",
                )
                sys_exit(1)

        # Check core plugins orders
        logger.info("Checking core plugins orders ...")
        core_plugins = {}
        files = glob(f"{args.core}/*/plugin.json")
        for file in files:
            try:
                core_plugin = loads(Path(file).read_text())

                if core_plugin["order"] not in core_plugins:
                    core_plugins[core_plugin["order"]] = []

                core_plugins[core_plugin["order"]].append(core_plugin)
            except:
                logger.error(
                    f"Exception while loading JSON from {file} : {format_exc()}",
                )

        core_settings = {}
        for order in core_plugins:
            if len(core_plugins[order]) > 1 and order != 999:
                logger.warning(
                    f"Multiple plugins have the same order ({order}) : {', '.join(plugin['id'] for plugin in core_plugins[order])}. Therefor, the execution order will be random.",
                )

            for plugin in core_plugins[order]:
                core_settings.update(plugin["settings"])

        if args.variables:
            logger.info(f"Variables : {args.variables}")

            # Compute the config
            logger.info("Computing config ...")
            config = Configurator(
                args.settings,
                core_settings,
                plugins,
                args.variables,
                logger,
                plugins_settings=plugins_settings,
            )
            config_files = config.get_config()
            custom_confs = [
                {"value": v, "exploded": custom_confs_rx.search(k).groups()}  # type: ignore
                for k, v in environ.items()
                if custom_confs_rx.match(k)
            ]
            root_dirs = listdir("/etc/bunkerweb/configs")
            for root, dirs, files in walk("/etc/bunkerweb/configs", topdown=True):
                if (
                    root != "configs"
                    and (dirs and not root.split("/")[-1] in root_dirs)
                    or files
                ):
                    path_exploded = root.split("/")
                    for file in files:
                        custom_confs.append(
                            {
                                "value": Path(join(root, file)).read_text(),
                                "exploded": (
                                    f"{path_exploded.pop()}"
                                    if path_exploded[-1] not in root_dirs
                                    else "",
                                    path_exploded[-1],
                                    file.replace(".conf", ""),
                                ),
                            }
                        )
        else:
            docker_client = DockerClient(
                base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            )

            while not docker_client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                logger.info("Waiting for BunkerWeb instance ...")
                sleep(5)

            api_http_port = None
            api_server_name = None
            tmp_config = {}
            custom_confs = []
            apis = []

            for instance in docker_client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                for var in instance.attrs["Config"]["Env"]:
                    splitted = var.split("=", 1)
                    if custom_confs_rx.match(splitted[0]):
                        custom_confs.append(
                            {
                                "value": splitted[1],
                                "exploded": custom_confs_rx.search(
                                    splitted[0]
                                ).groups(),
                            }
                        )
                    else:
                        tmp_config[splitted[0]] = splitted[1]

                        if not db and splitted[0] == "DATABASE_URI":
                            db = Database(
                                logger,
                                sqlalchemy_string=splitted[1],
                            )
                        elif splitted[0] == "API_HTTP_PORT":
                            api_http_port = splitted[1]
                        elif splitted[0] == "API_SERVER_NAME":
                            api_server_name = splitted[1]

            apis.append(
                API(
                    f"http://{instance.name}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                    host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                )
            )

        if not db:
            db = Database(logger)

        # Compute the config
        if not config_files:
            logger.info("Computing config ...")
            config = Configurator(
                args.settings,
                core_settings,
                plugins,
                tmp_config,
                logger,
                plugins_settings=plugins_settings,
            )
            config_files = config.get_config()

        if not db.is_initialized():
            logger.info(
                "Database not initialized, initializing ...",
            )
            ret, err = db.init_tables(
                [
                    config.get_settings(),
                    list(chain.from_iterable(core_plugins.values())),
                    config.get_plugins_settings(),
                ]
            )

            # Initialize database tables
            if err:
                logger.error(
                    f"Exception while initializing database : {err}",
                )
                sys_exit(1)
            elif not ret:
                logger.info(
                    "Database tables are already initialized, skipping creation ...",
                )
            else:
                logger.info("Database tables initialized")

            err = db.initialize_db(
                version=Path("/usr/share/bunkerweb/VERSION").read_text().strip(),
                integration=integration,
            )

            if err:
                logger.error(
                    f"Can't Initialize database : {err}",
                )
                sys_exit(1)
            else:
                logger.info("Database initialized")
        else:
            logger.info(
                "Database is already initialized, skipping ...",
            )

        if args.init:
            sys_exit(0)

        err = db.save_config(config_files, args.method)

        if not err:
            err1 = db.save_custom_configs(custom_confs, args.method)
        else:
            err = None
            err1 = None

        if err or err1:
            logger.error(
                f"Can't save config to database : {err or err1}",
            )
            sys_exit(1)
        else:
            logger.info("Config successfully saved to database")

        if apis:
            for api in apis:
                endpoint_data = api.get_endpoint().replace("http://", "").split(":")
                err = db.add_instance(
                    endpoint_data[0], endpoint_data[1], api.get_host()
                )

                if err:
                    logger.warning(err)
        else:
            err = db.add_instance(
                "localhost",
                config_files.get("API_HTTP_PORT", 5000),
                config_files.get("API_SERVER_NAME", "bwapi"),
            )

            if err:
                logger.warning(err)
    except SystemExit as e:
        raise e
    except:
        logger.error(
            f"Exception while executing config saver : {format_exc()}",
        )
        sys_exit(1)

    # We're done
    logger.info("Config saver successfully executed !")
