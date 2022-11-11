#!/usr/bin/python3

from argparse import ArgumentParser
from glob import glob
from itertools import chain
from json import loads
from os import R_OK, W_OK, X_OK, access, environ, getenv, path
from os.path import exists
from re import compile as re_compile
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from typing import Any


sys_path.append("/usr/share/bunkerweb/deps/python")
sys_path.append("/usr/share/bunkerweb/utils")
sys_path.append("/usr/share/bunkerweb/api")
sys_path.append("/usr/share/bunkerweb/db")

from docker import DockerClient
from kubernetes import client as kube_client

from logger import setup_logger
from Database import Database
from Configurator import Configurator
from API import API

custom_confs_rx = re_compile(
    r"^([0-9a-z\.\-]*)_?CUSTOM_CONF_(HTTP|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC|MODSEC_CRS)_(.+)$"
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

            if db is None and splitted[0] == "DATABASE_URI":
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
    wait_retry_interval = int(getenv("WAIT_RETRY_INTERVAL", "5"))

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
        elif exists("/usr/share/bunkerweb/INTEGRATION"):
            with open("/usr/share/bunkerweb/INTEGRATION", "r") as f:
                integration = f.read().strip()

        logger.info(f"Detected {integration} integration")
        config_files = None
        db = None

        # Check existences and permissions
        logger.info("Checking arguments ...")
        files = [args.settings] + ([args.variables] if args.variables else [])
        paths_rx = [args.core, args.plugins]
        for file in files:
            if not path.exists(file):
                logger.error(f"Missing file : {file}")
                sys_exit(1)
            if not access(file, R_OK):
                logger.error(f"Can't read file : {file}")
                sys_exit(1)
        for _path in paths_rx:
            if not path.isdir(_path):
                logger.error(f"Missing directory : {_path}")
                sys_exit(1)
            if not access(_path, R_OK | X_OK):
                logger.error(
                    f"Missing RX rights on directory : {_path}",
                )
                sys_exit(1)

        # Check core plugins orders
        logger.info("Checking core plugins orders ...")
        core_plugins = {}
        files = glob(f"{args.core}/*/plugin.json")
        for file in files:
            try:
                with open(file) as f:
                    core_plugin = loads(f.read())

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
                args.settings, core_settings, args.plugins, args.variables, logger
            )
            config_files = config.get_config()
            custom_confs = [
                {"value": v, "exploded": custom_confs_rx.search(k).groups()}
                for k, v in environ.items()
                if custom_confs_rx.match(k)
            ]
        elif integration == "Kubernetes":
            corev1 = kube_client.CoreV1Api()
            tmp_config = {}
            apis = []

            for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                if (
                    pod.metadata.annotations != None
                    and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                ):
                    api_http_port = None
                    api_server_name = None

                    for pod_env in pod.spec.containers[0].env:
                        tmp_config[pod_env.name] = pod_env.value

                        if db is None and pod_env.name == "DATABASE_URI":
                            db = Database(
                                logger,
                                sqlalchemy_string=pod_env.value,
                            )
                        elif pod_env.name == "API_HTTP_PORT":
                            api_http_port = pod_env.value
                        elif pod_env.name == "API_SERVER_NAME":
                            api_server_name = pod_env.value

                    apis.append(
                        API(
                            f"http://{pod.status.pod_ip}:{api_http_port or getenv('API_HTTP_PORT', '5000')}",
                            host=api_server_name or getenv("API_SERVER_NAME", "bwapi"),
                        )
                    )

            supported_config_types = [
                "http",
                "stream",
                "server-http",
                "server-stream",
                "default-server-http",
                "modsec",
                "modsec-crs",
            ]
            custom_confs = []

            for configmap in corev1.list_config_map_for_all_namespaces(
                watch=False
            ).items:
                if (
                    configmap.metadata.annotations is None
                    or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations
                ):
                    continue

                config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]

                if config_type not in supported_config_types:
                    logger.warning(
                        f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}",
                    )
                    continue
                elif not configmap.data:
                    logger.warning(
                        f"Ignoring blank ConfigMap {configmap.metadata.name}",
                    )
                    continue

                config_site = ""
                if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations:
                    config_site = (
                        f"{configmap.metadata.annotations['bunkerweb.io/CONFIG_SITE']}/"
                    )

                for config_name, config_data in configmap.data.items():
                    custom_confs.append(
                        {
                            "value": config_data,
                            "exploded": (config_site, config_type, config_name),
                        }
                    )
        else:
            docker_client = DockerClient(
                base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
            )

            tmp_config = {}
            custom_confs = []
            apis = []

            for instance in (
                docker_client.containers.list(filters={"label": "bunkerweb.INSTANCE"})
                if integration == "Docker"
                else docker_client.services.list(
                    filters={"label": "bunkerweb.INSTANCE"}
                )
            ):
                conf, cstm_confs, tmp_apis, tmp_db = get_instance_configs_and_apis(
                    instance, db, integration
                )
                tmp_config.update(conf)
                custom_confs.extend(cstm_confs)
                apis.extend(tmp_apis)
                if db is None:
                    db = tmp_db

        if db is None:
            db = Database(logger)

        # Compute the config
        if config_files is None:
            logger.info("Computing config ...")
            config = Configurator(
                args.settings, core_settings, args.plugins, tmp_config, logger
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
            elif ret is False:
                logger.info(
                    "Database tables are already initialized, skipping creation ...",
                )
            else:
                logger.info("Database tables initialized")

            with open("/usr/share/bunkerweb/VERSION", "r") as f:
                version = f.read().strip()

            err = db.initialize_db(version=version, integration=integration)

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

        err = db.save_config(config_files, "scheduler")

        if not err:
            err1 = db.save_custom_configs(custom_confs, "scheduler")
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
    except SystemExit as e:
        sys_exit(e)
    except:
        logger.error(
            f"Exception while executing config saver : {format_exc()}",
        )
        sys_exit(1)

    # We're done
    logger.info("Config saver successfully executed !")
