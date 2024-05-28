#!/usr/bin/env python3

from argparse import ArgumentParser
from os import R_OK, X_OK, access, environ, getenv, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc
from typing import Any

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from docker import DockerClient
from kubernetes import client as kube_client
from kubernetes import config as kube_config

from common_utils import get_integration  # type: ignore
from logger import setup_logger  # type: ignore
from Database import Database  # type: ignore
from Configurator import Configurator
from API import API  # type: ignore

custom_confs_rx = re_compile(r"^([0-9a-z\.-]*)_?CUSTOM_CONF_(HTTP|SERVER_STREAM|STREAM|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$")


def get_instance_configs_and_apis(instance: Any, db, _type="Docker"):
    api_http_port = None
    api_server_name = None
    tmp_config = {}
    custom_confs = []
    apis = []

    for var in instance.attrs["Config"]["Env"] if _type == "Docker" else instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
        split = var.split("=", 1)
        if custom_confs_rx.match(split[0]):
            custom_conf = custom_confs_rx.search(split[0]).groups()
            custom_confs.append(
                {
                    "value": f"# CREATED BY ENV\n{split[1]}",
                    "exploded": (
                        custom_conf[0],
                        custom_conf[1],
                        custom_conf[2].replace(".conf", ""),
                    ),
                }
            )
            logger.info(
                f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}"
            )
        else:
            tmp_config[split[0]] = split[1]

            if not db and split[0] == "DATABASE_URI":
                db = Database(logger, sqlalchemy_string=split[1])
            elif split[0] == "API_HTTP_PORT":
                api_http_port = split[1]
            elif split[0] == "API_SERVER_NAME":
                api_server_name = split[1]

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
        parser.add_argument("--settings", default=join(sep, "usr", "share", "bunkerweb", "settings.json"), type=str, help="file containing the main settings")
        parser.add_argument("--core", default=join(sep, "usr", "share", "bunkerweb", "core"), type=str, help="directory containing the core plugins")
        parser.add_argument("--plugins", default=join(sep, "etc", "bunkerweb", "plugins"), type=str, help="directory containing the external plugins")
        parser.add_argument("--pro-plugins", default=join(sep, "etc", "bunkerweb", "pro", "plugins"), type=str, help="directory containing the pro plugins")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        parser.add_argument("--init", action="store_true", help="Only initialize the database")
        parser.add_argument("--method", default="scheduler", type=str, help="The method that is used to save the config")
        parser.add_argument("--no-check-changes", action="store_true", help="Set the changes to checked in the database")
        args = parser.parse_args()

        settings_path = Path(args.settings)
        core_path = Path(args.core)
        plugins_path = Path(args.plugins)
        pro_plugins_path = Path(args.pro_plugins)

        logger.info("Save config started ...")
        logger.info(f"Settings : {settings_path}")
        logger.info(f"Core : {core_path}")
        logger.info(f"Plugins : {plugins_path}")
        logger.info(f"Pro plugins : {pro_plugins_path}")
        logger.info(f"Init : {args.init}")

        integration = get_integration()

        if args.init:
            logger.info(f"Detected {integration} integration")

        if integration == "Linux" and not args.variables:
            args.variables = join(sep, "etc", "bunkerweb", "variables.env")

        config_files = None
        db = None
        apis = []

        external_plugins = args.plugins
        pro_plugins = args.pro_plugins
        if not Path(sep, "usr", "sbin", "nginx").exists() and args.method == "ui":
            db = Database(logger)
            external_plugins = db.get_plugins(_type="external")
            pro_plugins = db.get_plugins(_type="pro")

        # Check existences and permissions
        logger.info("Checking arguments ...")
        files = [settings_path] + ([Path(args.variables)] if args.variables else [])
        paths_rx = [core_path, plugins_path, pro_plugins_path]
        for file in files:
            if not file.is_file():
                logger.error(f"Missing file : {file}")
                sys_exit(1)
            if not access(file, R_OK):
                logger.error(f"Can't read file : {file}")
                sys_exit(1)
        for path in paths_rx:
            if not path.is_dir():
                logger.error(f"Missing directory : {path}")
                sys_exit(1)
            if not access(path, R_OK | X_OK):
                logger.error(f"Missing RX rights on directory : {path}")
                sys_exit(1)

        tmp_config = {}

        if args.variables:
            variables_path = Path(args.variables)
            logger.info(f"Variables : {variables_path}")

            # Compute the config
            logger.info("Computing config ...")
            config = Configurator(str(settings_path), str(core_path), external_plugins, pro_plugins, str(variables_path), logger)
            config_files = config.get_config()
            custom_confs = []
            for k, v in environ.items():
                if custom_confs_rx.match(k):
                    custom_conf = custom_confs_rx.search(k).groups()
                    custom_confs.append(
                        {
                            "value": f"# CREATED BY ENV\n{v}",
                            "exploded": (
                                custom_conf[0],
                                custom_conf[1],
                                custom_conf[2].replace(".conf", ""),
                            ),
                        }
                    )
                    logger.info(
                        f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}"
                    )

            db = Database(logger, config_files.get("DATABASE_URI", None))
        elif getenv("KUBERNETES_MODE", "no") != "yes":
            docker_client = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))

            while not docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"}):
                logger.info("Waiting for BunkerWeb instance ...")
                sleep(5)

            api_http_port = None
            api_server_name = None
            custom_confs = []
            apis = []

            for instance in docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"}):
                for var in instance.attrs["Config"]["Env"]:
                    split = var.split("=", 1)
                    if custom_confs_rx.match(split[0]):
                        custom_conf = custom_confs_rx.search(split[0]).groups()
                        custom_confs.append(
                            {
                                "value": f"# CREATED BY ENV\n{split[1]}",
                                "exploded": (
                                    custom_conf[0],
                                    custom_conf[1],
                                    custom_conf[2].replace(".conf", ""),
                                ),
                            }
                        )
                        logger.info(
                            f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}"
                        )
                    else:
                        tmp_config[split[0]] = split[1]

                        if not db and split[0] == "DATABASE_URI":
                            db = Database(logger, sqlalchemy_string=split[1])
                        elif split[0] == "API_HTTP_PORT":
                            api_http_port = split[1]
                        elif split[0] == "API_SERVER_NAME":
                            api_server_name = split[1]

                apis.append(
                    API(
                        f"http://{instance.name}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                        host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                    )
                )
        else:
            kube_config.load_incluster_config()
            kubernetes_client = kube_client.CoreV1Api()

            api_http_port = None
            api_server_name = None
            custom_confs = []
            apis = []

            for pod in kubernetes_client.list_pod_for_all_namespaces(watch=False).items:
                if pod.metadata.annotations is not None and "bunkerweb.io/INSTANCE" in pod.metadata.annotations:
                    for env in pod.env:
                        if custom_confs_rx.match(env.name):
                            custom_conf = custom_confs_rx.search(env.name).groups()
                            custom_confs.append(
                                {
                                    "value": f"# CREATED BY ENV\n{env.value}",
                                    "exploded": (
                                        custom_conf[0],
                                        custom_conf[1],
                                        custom_conf[2].replace(".conf", ""),
                                    ),
                                }
                            )
                            logger.info(
                                f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}"
                            )
                        else:
                            tmp_config[env.name] = env.value

                            if not db and env.name == "DATABASE_URI":
                                db = Database(logger, sqlalchemy_string=env.value)
                            elif env.name == "API_HTTP_PORT":
                                api_http_port = env.value
                            elif env.name == "API_SERVER_NAME":
                                api_server_name = env.value

                    apis.append(
                        API(
                            f"http://{pod.status.pod_ip or pod.metadata.name}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                            host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                        )
                    )

        if not db:
            db = Database(logger)

        # Compute the config
        if not config_files:
            logger.info("Computing config ...")
            config = Configurator(args.settings, args.core, external_plugins, pro_plugins, tmp_config, logger)
            config_files = config.get_config()

        bunkerweb_version = Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text().strip()
        db_initialized = db.is_initialized()

        if not db_initialized:
            logger.info(
                "Database not initialized, initializing ...",
            )
            ret, err = db.init_tables(
                [config.get_settings(), config.get_plugins("core"), config.get_plugins("external"), config.get_plugins("pro")],
                bunkerweb_version,
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
        else:
            logger.info("Database is already initialized, checking for changes ...")

            ret, err = db.init_tables(
                [config.get_settings(), config.get_plugins("core"), config.get_plugins("external"), config.get_plugins("pro")],
                bunkerweb_version,
            )

            if not ret and err:
                logger.error(f"Exception while checking database tables : {err}")
                sys_exit(1)
            elif not ret:
                logger.info("Database tables didn't change, skipping update ...")
            else:
                logger.info("Database tables successfully updated")

        err = db.initialize_db(version=bunkerweb_version, integration=integration)

        if err:
            logger.error(f"Can't {'initialize' if not db_initialized else 'update'} database metadata : {err}")
            sys_exit(1)
        else:
            logger.info("Database metadata successfully " + ("initialized" if not db_initialized else "updated"))

        if args.init:
            sys_exit(0)

        changes = []
        changed_plugins = set()
        err = db.save_config(config_files, args.method, changed=False)

        if isinstance(err, str):
            logger.warning(f"Couldn't save config to database : {err}, config may not work as expected")
        else:
            changed_plugins = err
            changes.append("config")
            logger.info("Config successfully saved to database")

        if args.method != "ui":
            err1 = db.save_custom_configs(custom_confs, args.method, changed=False)

            if err1:
                logger.warning(f"Couldn't save custom configs to database : {err1}, custom configs may not work as expected")
            else:
                changes.append("custom_configs")
                logger.info("Custom configs successfully saved to database")

            if apis:
                for api in apis:
                    endpoint_data = api.endpoint.replace("http://", "").split(":")
                    err = db.add_instance(
                        endpoint_data[0],
                        endpoint_data[1].replace("/", ""),
                        api.host,
                        changed=False,
                    )

                    if err:
                        logger.warning(err)
                    else:
                        if "instances" not in changes:
                            changes.append("instances")
                        logger.info(f"Instance {endpoint_data[0]} successfully saved to database")
            else:
                err = db.add_instance(
                    "127.0.0.1",
                    config_files.get("API_HTTP_PORT", 5000),
                    config_files.get("API_SERVER_NAME", "bwapi"),
                    changed=False,
                )

                if err:
                    logger.warning(err)
                else:
                    changes.append("instances")
                    logger.info("Instance 127.0.0.1 successfully saved to database")

        if not args.no_check_changes:
            # update changes in db
            ret = db.checked_changes(changes, plugins_changes=changed_plugins, value=True)
            if ret:
                logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")
    except SystemExit as e:
        sys_exit(e.code)
    except:
        logger.error(
            f"Exception while executing config saver : {format_exc()}",
        )
        sys_exit(1)

    # We're done
    logger.info("Config saver successfully executed !")
