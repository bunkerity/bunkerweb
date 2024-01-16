#!/usr/bin/python3

from argparse import ArgumentParser
from os import R_OK, X_OK, access, environ, getenv, sep
from os.path import join, normpath
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
            logger.info(f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}")
        else:
            tmp_config[split[0]] = split[1]

            if not db and split[0] == "DATABASE_URI":
                db = Database(logger, sqlalchemy_string=split[1], pool=False)
            elif split[0] == "API_HTTP_PORT":
                api_http_port = split[1]
            elif split[0] == "API_SERVER_NAME":
                api_server_name = split[1]

    apis.append(
        API(
            f"http://{getenv("API_HTTP_HOST", instance.name)}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
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
            default=join(sep, "usr", "share", "bunkerweb", "settings.json"),
            type=str,
            help="file containing the main settings",
        )
        parser.add_argument(
            "--core",
            default=join(sep, "usr", "share", "bunkerweb", "core"),
            type=str,
            help="directory containing the core plugins",
        )
        parser.add_argument(
            "--plugins",
            default=join(sep, "etc", "bunkerweb", "plugins"),
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
        parser.add_argument(
            "--no-check-changes",
            action="store_true",
            help="Set the changes to checked in the database",
        )
        args = parser.parse_args()

        settings_path = Path(normpath(args.settings))
        core_path = Path(normpath(args.core))
        plugins_path = Path(normpath(args.plugins))

        logger.info("Save config started ...")
        logger.info(f"Settings : {settings_path}")
        logger.info(f"Core : {core_path}")
        logger.info(f"Plugins : {plugins_path}")
        logger.info(f"Init : {args.init}")

        integration = "Linux"
        integration_path = Path(sep, "usr", "share", "bunkerweb", "INTEGRATION")
        os_release_path = Path(sep, "etc", "os-release")
        if getenv("KUBERNETES_MODE", "no").lower() == "yes":
            integration = "Kubernetes"
        elif getenv("SWARM_MODE", "no").lower() == "yes":
            integration = "Swarm"
        elif getenv("AUTOCONF_MODE", "no").lower() == "yes":
            integration = "Autoconf"
        elif integration_path.is_file():
            integration = integration_path.read_text().strip()
        elif os_release_path.is_file() and "Alpine" in os_release_path.read_text():
            integration = "Docker"

        del integration_path, os_release_path

        if args.init:
            logger.info(f"Detected {integration} integration")

        config_files = None
        db = None
        apis = []

        external_plugins = args.plugins
        if not Path(sep, "usr", "sbin", "nginx").exists() and args.method == "ui":
            db = Database(logger, pool=False)
            external_plugins = db.get_plugins()

        # Check existences and permissions
        logger.info("Checking arguments ...")
        files = [settings_path] + ([Path(normpath(args.variables))] if args.variables else [])
        paths_rx = [core_path, plugins_path]
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
                logger.error(
                    f"Missing RX rights on directory : {path}",
                )
                sys_exit(1)

        if args.variables:
            variables_path = Path(normpath(args.variables))
            logger.info(f"Variables : {variables_path}")

            # Compute the config
            logger.info("Computing config ...")
            config = Configurator(
                str(settings_path),
                str(core_path),
                external_plugins,
                str(variables_path),
                logger,
            )
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
                    logger.info(f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}")

            db = Database(logger, config_files.get("DATABASE_URI", None), pool=False)
        else:
            docker_client = DockerClient(base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock"))

            while not docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"}):
                logger.info("Waiting for BunkerWeb instance ...")
                sleep(5)

            api_http_port = None
            api_server_name = None
            tmp_config = {}
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
                        logger.info(f"Found custom conf env var {'for service ' + custom_conf[0] if custom_conf[0] else 'without service'} with type {custom_conf[1]} and name {custom_conf[2]}")
                    else:
                        tmp_config[split[0]] = split[1]

                        if not db and split[0] == "DATABASE_URI":
                            db = Database(logger, sqlalchemy_string=split[1], pool=False)
                        elif split[0] == "API_HTTP_PORT":
                            api_http_port = split[1]
                        elif split[0] == "API_SERVER_NAME":
                            api_server_name = split[1]

                apis.append(
                    API(
                        f"http://{getenv("API_HTTP_HOST", instance.name)}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                        host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                    )
                )

        if not db:
            db = Database(logger, pool=False)

        # Compute the config
        if not config_files:
            logger.info("Computing config ...")
            config = Configurator(
                args.settings,
                args.core,
                external_plugins,
                tmp_config,
                logger,
            )
            config_files = config.get_config()

        if not db.is_initialized():
            logger.info(
                "Database not initialized, initializing ...",
            )
            ret, err = db.init_tables(
                [
                    config.get_settings(),
                    config.get_plugins("core"),
                    config.get_plugins("external"),
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
                version=Path(sep, "usr", "share", "bunkerweb", "VERSION").read_text().strip(),
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

        changes = []
        err = db.save_config(config_files, args.method, changed=False)

        if err:
            logger.warning(f"Couldn't save config to database : {err}, config may not work as expected")
        else:
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
                apihost = getenv("API_HTTP_HOST", config_files.get("API_HTTP_HOST", "127.0.0.1"))
                err = db.add_instance(
                    apihost,
                    config_files.get("API_HTTP_PORT", 5000),
                    config_files.get("API_SERVER_NAME", "bwapi"),
                    changed=False,
                )

                if err:
                    logger.warning(err)
                else:
                    changes.append("instances")
                    logger.info(f"Instance {apihost} successfully saved to database")

        if not args.no_check_changes:
            # update changes in db
            ret = db.checked_changes(changes, value=True)
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
