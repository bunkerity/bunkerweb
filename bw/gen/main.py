#!/usr/bin/python3

from argparse import ArgumentParser
from glob import glob
from itertools import chain
from json import loads
from os import R_OK, W_OK, X_OK, access, environ, getenv, makedirs, path, remove, unlink
from os.path import dirname, exists, isdir, isfile, islink
from re import compile as re_compile
from shutil import rmtree
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from time import sleep
from traceback import format_exc


sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/api")
sys_path.append("/opt/bunkerweb/db")

from docker import DockerClient
from docker.errors import DockerException
from kubernetes import client as kube_client

from logger import setup_logger
from Database import Database
from Configurator import Configurator
from Templator import Templator
from API import API
from ApiCaller import ApiCaller


if __name__ == "__main__":
    logger = setup_logger("Generator", environ.get("LOG_LEVEL", "INFO"))
    wait_retry_interval = int(getenv("WAIT_RETRY_INTERVAL", "5"))

    try:
        # Parse arguments
        parser = ArgumentParser(description="BunkerWeb config generator")
        parser.add_argument(
            "--settings",
            default="/opt/bunkerweb/settings.json",
            type=str,
            help="file containing the main settings",
        )
        parser.add_argument(
            "--templates",
            default="/opt/bunkerweb/confs",
            type=str,
            help="directory containing the main template files",
        )
        parser.add_argument(
            "--core",
            default="/opt/bunkerweb/core",
            type=str,
            help="directory containing the core plugins",
        )
        parser.add_argument(
            "--plugins",
            default="/opt/bunkerweb/plugins",
            type=str,
            help="directory containing the external plugins",
        )
        parser.add_argument(
            "--output",
            default="/etc/nginx",
            type=str,
            help="where to write the rendered files",
        )
        parser.add_argument(
            "--target",
            default="/etc/nginx",
            type=str,
            help="where nginx will search for configurations files",
        )
        parser.add_argument(
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        parser.add_argument(
            "--method",
            default="scheduler",
            type=str,
            help="The method that is used in the database",
        )
        parser.add_argument(
            "--init",
            action="store_true",
            help="Only initialize the database",
        )
        args = parser.parse_args()

        logger.info("Generator started ...")
        logger.info(f"Settings : {args.settings}")
        logger.info(f"Templates : {args.templates}")
        logger.info(f"Core : {args.core}")
        logger.info(f"Plugins : {args.plugins}")
        logger.info(f"Output : {args.output}")
        logger.info(f"Target : {args.target}")
        logger.info(f"Variables : {args.variables}")
        logger.info(f"Method : {args.method}")
        logger.info(f"Init : {args.init}")

        custom_confs_rx = re_compile(
            r"^([0-9a-z\.\-]*)_?CUSTOM_CONF_(HTTP|DEFAULT_SERVER_HTTP|SERVER_HTTP|MODSEC|MODSEC_CRS)_(.+)$"
        )

        # Check existences and permissions
        logger.info("Checking arguments ...")
        files = [args.settings] + ([args.variables] if args.variables else [])
        paths_rx = [args.core, args.plugins, args.templates]
        paths_rwx = [args.output]
        for file in files:
            if not path.exists(file):
                logger.error(f"Missing file : {file}")
                sys_exit(1)
            if not access(file, R_OK):
                logger.error(f"Can't read file : {file}")
                sys_exit(1)
        for _path in paths_rx + paths_rwx:
            if not path.isdir(_path):
                logger.error(f"Missing directory : {_path}")
                sys_exit(1)
            if not access(_path, R_OK | X_OK):
                logger.error(
                    f"Missing RX rights on directory : {_path}",
                )
                sys_exit(1)
        for _path in paths_rwx:
            if not access(_path, W_OK):
                logger.error(
                    f"Missing W rights on directory : {_path}",
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

        if args.variables or args.init:
            # Compute the config
            logger.info("Computing config ...")
            config = Configurator(
                args.settings, core_settings, args.plugins, args.variables, logger
            )
            config_files = config.get_config()

            if config_files.get("LOG_LEVEL", logger.level) != logger.level:
                logger = setup_logger("Generator", config_files["LOG_LEVEL"])

            bw_integration = None
            if config_files.get("SWARM_MODE", "no") == "yes":
                bw_integration = "Swarm"
            elif config_files.get("KUBERNETES_MODE", "no") == "yes":
                bw_integration = "Kubernetes"
            elif config_files.get("AUTOCONF_MODE", "no") == "yes":
                bw_integration = "Autoconf"
            elif args.method != "autoconf" and exists("/opt/bunkerweb/INTEGRATION"):
                with open("/opt/bunkerweb/INTEGRATION", "r") as f:
                    bw_integration = f.read().strip()

            db = None
            if bw_integration == "Linux":
                db = Database(logger, config_files["DATABASE_URI"])
            elif bw_integration in ("Docker", "Swarm", "Autoconf"):
                try:
                    docker_client = DockerClient(base_url="tcp://docker-proxy:2375")
                except DockerException:
                    docker_client = DockerClient(
                        base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
                    )

                apis = []
                for instance in docker_client.containers.list(
                    filters={"label": "bunkerweb.INSTANCE"}
                ):
                    api = None

                    for var in instance.attrs["Config"]["Env"]:
                        if db is None and var.startswith("DATABASE_URI="):
                            db = Database(logger, var.replace("DATABASE_URI=", "", 1))
                        elif var.startswith("API_HTTP_PORT="):
                            api = API(
                                f"http://{instance.name}:{var.replace('API_HTTP_PORT=', '', 1)}"
                            )

                    if api:
                        apis.append(api)
                    else:
                        apis.append(
                            API(
                                f"http://{instance.name}:{getenv('API_HTTP_PORT', '5000')}"
                            )
                        )

                api_caller = ApiCaller(apis=apis)
            elif bw_integration == "Kubernetes":
                corev1 = kube_client.CoreV1Api()
                for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                    if (
                        pod.metadata.annotations != None
                        and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                    ):
                        for pod_env in pod.spec.containers[0].env:
                            if pod_env.name == "DATABASE_URI":
                                db = Database(
                                    logger,
                                    pod_env.value or getenv("DATABASE_URI", "5000"),
                                )
                                break

            if db is None:
                db = Database(logger)

            if args.init:
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

                if not db.is_initialized():
                    logger.info(
                        "Database not initialized, initializing ...",
                    )

                    custom_confs = [
                        {"value": v, "exploded": custom_confs_rx.search(k).groups()}
                        for k, v in environ.items()
                        if custom_confs_rx.match(k)
                    ]

                    with open("/opt/bunkerweb/VERSION", "r") as f:
                        bw_version = f.read().strip()

                    bw_integration = None
                    if (
                        getenv("SWARM_MODE", config_files.get("SWARM_MODE", "no"))
                        == "yes"
                    ):
                        bw_integration = "Swarm"
                    elif (
                        getenv(
                            "KUBERNETES_MODE", config_files.get("KUBERNETES_MODE", "no")
                        )
                        == "yes"
                    ):
                        bw_integration = "Kubernetes"
                    elif (
                        getenv("AUTOCONF_MODE", config_files.get("AUTOCONF_MODE", "no"))
                        == "yes"
                    ):
                        bw_integration = "Autoconf"
                    elif exists("/opt/bunkerweb/INTEGRATION"):
                        with open("/opt/bunkerweb/INTEGRATION", "r") as f:
                            bw_integration = f.read().strip()

                    if bw_integration == "Linux":
                        err = db.save_config(config_files, args.method)

                        if not err:
                            err1 = db.save_custom_configs(custom_confs, args.method)
                    else:
                        err = None
                        err1 = None

                    err2 = db.initialize_db(
                        version=bw_version, integration=bw_integration
                    )

                    if err or err1 or err2:
                        logger.error(
                            f"Can't Initialize database : {err or err1 or err2}",
                        )
                        sys_exit(1)
                    else:
                        logger.info("Database initialized")
                else:
                    logger.info(
                        "Database is already initialized, skipping ...",
                    )

                sys_exit(0)

            config = config_files
        elif args.method != "autoconf":
            bw_integration = "Docker"

            try:
                docker_client = DockerClient(base_url="tcp://docker-proxy:2375")
            except DockerException:
                docker_client = DockerClient(
                    base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
                )

            tmp_config = {}
            custom_confs = []
            apis = []
            db = None
            for instance in docker_client.containers.list(
                filters={"label": "bunkerweb.INSTANCE"}
            ):
                api = None

                for var in instance.attrs["Config"]["Env"]:
                    if custom_confs_rx.match(var.split("=", 1)[0]):
                        splitted = var.split("=", 1)
                        custom_confs.append(
                            {
                                "value": var.pop(0),
                                "exploded": custom_confs_rx.search(
                                    "=".join(var)
                                ).groups(),
                            }
                        )
                    else:
                        tmp_config[var.split("=", 1)[0]] = var.split("=", 1)[1]

                    if var.startswith("DATABASE_URI="):
                        db = Database(logger, var.replace("DATABASE_URI=", "", 1))
                    elif var.startswith("API_HTTP_PORT="):
                        api = API(
                            f"http://{instance.name}:{var.replace('API_HTTP_PORT=', '', 1)}"
                        )

                if api:
                    apis.append(api)
                else:
                    apis.append(
                        API(f"http://{instance.name}:{getenv('API_HTTP_PORT', '5000')}")
                    )

            if db is None:
                db = Database(logger)

            api_caller = ApiCaller(apis=apis)

            # Compute the config
            logger.info("Computing config ...")
            config = Configurator(
                args.settings, core_settings, args.plugins, tmp_config, logger
            )
            config_files = config.get_config()

            if config_files.get("LOG_LEVEL", logger.level) != logger.level:
                logger = setup_logger("Generator", config_files["LOG_LEVEL"])

            err = db.save_config(config_files, args.method)

            if not err:
                err1 = db.save_custom_configs(custom_confs, args.method)
            else:
                err = None
                err1 = None

            with open("/opt/bunkerweb/VERSION", "r") as f:
                bw_version = f.read().strip()

            if err or err1:
                logger.error(
                    f"Can't save config to database : {err or err1}",
                )
                sys_exit(1)
            else:
                logger.info("Config successfully saved to database")

            config = config_files
        else:
            db = None
            if getenv("KUBERNETES_MODE", "no") == "yes":
                corev1 = kube_client.CoreV1Api()
                for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                    if (
                        pod.metadata.annotations != None
                        and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                        and "DATABASE_URI" in pod.spec.containers[0].env
                    ):
                        db = Database(
                            logger, pod.spec.containers[0].env["DATABASE_URI"]
                        )
                        break
            elif getenv("AUTOCONF_MODE", getenv("SWARM_MODE", "no")) == "yes":
                try:
                    docker_client = DockerClient(base_url="tcp://docker-proxy:2375")
                except DockerException:
                    docker_client = DockerClient(
                        base_url=getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
                    )

                for instance in docker_client.containers.list(
                    filters={"label": "bunkerweb.INSTANCE"}
                ):
                    for var in instance.attrs["Config"]["Env"]:
                        if var.startswith("DATABASE_URI="):
                            db = Database(logger, var.replace("DATABASE_URI=", "", 1))
                            break

                    if db:
                        break

            if db is None:
                db = Database(logger)

            config = db.get_config()

            bw_integration = None
            if config.get("SWARM_MODE", "no") == "yes":
                bw_integration = "Swarm"
            elif config.get("KUBERNETES_MODE", "no") == "yes":
                bw_integration = "Kubernetes"
            elif config.get("AUTOCONF_MODE", "no") == "yes":
                bw_integration = "Autoconf"
            elif args.method != "autoconf" and exists("/opt/bunkerweb/INTEGRATION"):
                with open("/opt/bunkerweb/INTEGRATION", "r") as f:
                    bw_integration = f.read().strip()

        logger = setup_logger("Generator", config.get("LOG_LEVEL", "INFO"))

        if bw_integration == "Docker":
            while not api_caller._send_to_apis("GET", "/ping"):
                logger.warning(
                    "Waiting for BunkerWeb's temporary nginx to start, retrying in 5 seconds ...",
                )
                sleep(5)
        elif bw_integration == "Linux":
            retries = 0
            while not exists("/opt/bunkerweb/tmp/nginx.pid"):
                if retries == 5:
                    logger.error(
                        "BunkerWeb's temporary nginx didn't start in time.",
                    )
                    sys_exit(1)

                logger.warning(
                    "Waiting for BunkerWeb's temporary nginx to start, retrying in 5 seconds ...",
                )
                retries += 1
                sleep(5)

        # Remove old files
        logger.info("Removing old files ...")
        files = glob(f"{args.output}/*")
        for file in files:
            if islink(file):
                unlink(file)
            elif isfile(file):
                remove(file)
            elif isdir(file):
                rmtree(file, ignore_errors=False)

        if bw_integration in ("Docker", "Linux"):
            logger.info(
                "Generating custom configs from Database ...",
            )
            custom_configs = db.get_custom_configs()
            original_path = "/data/configs"
            makedirs(original_path, exist_ok=True)
            for custom_config in custom_configs:
                tmp_path = f"{original_path}/{custom_config['type'].replace('_', '-')}"
                if custom_config["service_id"]:
                    tmp_path += f"/{custom_config['service_id']}"
                tmp_path += f"/{custom_config['name']}.conf"
                makedirs(dirname(tmp_path), exist_ok=True)
                with open(tmp_path, "w") as f:
                    f.write(custom_config["data"])

        # Render the templates
        logger.info("Rendering templates ...")
        templator = Templator(
            args.templates,
            args.core,
            args.plugins,
            args.output,
            args.target,
            config,
        )
        templator.render()

        if bw_integration == "Docker":
            ret = api_caller._send_to_apis("POST", "/reload")
            if not ret:
                logger.error(
                    "reload failed",
                )
                sys_exit(1)
        elif bw_integration == "Linux":
            cmd = "/usr/sbin/nginx -s reload"
            proc = run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
            if proc.returncode != 0:
                status = 1
                logger.error("Error while reloading nginx")
            else:
                logger.info("Successfully reloaded nginx")

    except SystemExit as e:
        sys_exit(e)
    except:
        logger.error(
            f"Exception while executing generator : {format_exc()}",
        )
        sys_exit(1)

    # We're done
    logger.info("Generator successfully executed !")
