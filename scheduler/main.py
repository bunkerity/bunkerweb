#!/usr/bin/python3

from argparse import ArgumentParser
from os import _exit, environ, getenv, getpid, path, remove
from os.path import exists
from signal import SIGINT, SIGTERM, SIGUSR1, SIGUSR2, signal
from sys import path as sys_path
from time import sleep
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/api")
sys_path.append("/opt/bunkerweb/db")

from docker import DockerClient
from docker.errors import DockerException
from dotenv import dotenv_values
from kubernetes import client as kube_client

from logger import setup_logger
from Database import Database
from JobScheduler import JobScheduler
from API import API

run = True
scheduler = None
reloading = False
logger = setup_logger("Scheduler", environ.get("LOG_LEVEL", "INFO"))


def handle_stop(signum, frame):
    global run, scheduler
    run = False
    if scheduler is not None:
        scheduler.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


def handle_reload(env):
    global run, scheduler, reloading
    try:
        if scheduler is not None and run:
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


def handle_reload_bw(signum, frame):
    handle_reload("/etc/nginx/variables.env")


signal(SIGUSR1, handle_reload_bw)


def handle_reload_api(signum, frame):
    handle_reload("/opt/bunkerweb/tmp/jobs.env")


signal(SIGUSR2, handle_reload_api)


def stop(status):
    remove("/opt/bunkerweb/tmp/scheduler.pid")
    _exit(status)


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        if path.isfile("/opt/bunkerweb/tmp/scheduler.pid"):
            logger.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        with open("/opt/bunkerweb/tmp/scheduler.pid", "w") as f:
            f.write(str(getpid()))

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument(
            "--run", action="store_true", help="only run jobs one time in foreground"
        )
        parser.add_argument(
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        args = parser.parse_args()

        logger.info("Scheduler started ...")

        bw_integration = "Linux"

        if args.variables:
            logger.info(f"Variables : {args.variables}")

            # Read env file
            env = dotenv_values(args.variables)
        else:
            # Read from database
            db = None
            if "DATABASE_URI" in environ:
                db = Database(logger)
            elif getenv("KUBERNETES_MODE", "no") == "yes":
                bw_integration = "Kubernetes"
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
            else:
                bw_integration = "Docker"
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

            if db is None:
                logger.error("No database found, exiting ...")
                stop(1)

            while not db.is_initialized():
                logger.warning(
                    "Database is not initialized, retrying in 5s ...",
                )
                sleep(3)

            env = db.get_config()
            while not db.is_first_config_saved() or not env:
                logger.info(
                    "Database doesn't have any config saved yet, retrying in 5s ...",
                )
                sleep(3)
                env = db.get_config()

        if args.run:
            # write config to /tmp/variables.env
            with open("/tmp/variables.env", "w") as f:
                for variable, value in env.items():
                    f.write(f"{variable}={value}\n")
            run_once = True
        else:
            # Check if config as changed since last run
            run_once = dotenv_values("/tmp/variables.env") != env

            if run_once:
                logger.info("Config changed since last run, reloading ...")

        logger.info("Executing job scheduler ...")
        while True:
            apis = []
            if not args.variables:
                if bw_integration == "Docker":
                    try:
                        docker_client = DockerClient(base_url="tcp://docker-proxy:2375")
                    except DockerException:
                        docker_client = DockerClient(
                            base_url=getenv(
                                "DOCKER_HOST", "unix:///var/run/docker.sock"
                            )
                        )

                    for instance in docker_client.containers.list(
                        filters={"label": "bunkerweb.INSTANCE"}
                    ):
                        api = None

                        for var in instance.attrs["Config"]["Env"]:
                            if var.startswith("API_HTTP_PORT="):
                                api = API(
                                    f"http://{instance.name}:{var.replace('API_HTTP_PORT=', '', 1)}"
                                )
                                break

                        if api:
                            apis.append(api)
                        else:
                            apis.append(
                                API(
                                    f"http://{instance.name}:{getenv('API_HTTP_PORT', '5000')}"
                                )
                            )
                elif bw_integration == "Kubernetes":
                    corev1 = kube_client.CoreV1Api()
                    for pod in corev1.list_pod_for_all_namespaces(watch=False).items:
                        api = None
                        if (
                            pod.metadata.annotations != None
                            and "bunkerweb.io/INSTANCE" in pod.metadata.annotations
                        ):
                            for pod_env in instance.spec.containers[0].env:
                                if pod_env.name == "API_HTTP_PORT":
                                    api = API(
                                        f"http://{pod.status.pod_ip}:{pod_env.value or getenv('API_HTTP_PORT', '5000')}"
                                    )
                                    break

                            if api:
                                apis.append(api)
                            else:
                                apis.append(
                                    API(
                                        f"http://{pod.status.pod_ip}:{env.get('API_HTTP_PORT', getenv('API_HTTP_PORT', '5000'))}"
                                    )
                                )

            # Instantiate scheduler
            scheduler = JobScheduler(
                env=env,
                apis=apis,
                logger=logger,
            )

            # Only run jobs once
            if run_once:
                if not scheduler.run_once():
                    logger.error("At least one job in run_once() failed")
                    if args.run:
                        stop(1)
                else:
                    logger.info("All jobs in run_once() were successful")
                    if args.run:
                        break

                run_once = False

            # Or infinite schedule
            scheduler.setup()
            while run:
                scheduler.run_pending()
                sleep(1)

                tmp_env = (
                    dotenv_values(args.variables) if args.variables else db.get_config()
                )
                if env != tmp_env:
                    logger.info("Config changed, reloading ...")
                    env = tmp_env
                    run_once = True
                    break

    except:
        logger.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)

    logger.info("Job scheduler stopped")
    stop(0)
