#!/usr/bin/python3

from os import _exit, environ, getenv
from signal import SIGINT, SIGTERM, signal
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
from SwarmController import SwarmController
from IngressController import IngressController
from DockerController import DockerController
from Database import Database

# Get variables
logger = setup_logger("Autoconf", getenv("LOG_LEVEL", "INFO"))
swarm = getenv("SWARM_MODE", "no") == "yes"
kubernetes = getenv("KUBERNETES_MODE", "no") == "yes"
docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
wait_retry_interval = int(getenv("WAIT_RETRY_INTERVAL", "5"))


def exit_handler(signum, frame):
    logger.info("Stop signal received, exiting...")
    _exit(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)

try:

    # Setup /data folder if needed
    proc = run(
        ["/opt/bunkerweb/helpers/data.sh", "AUTOCONF"],
        stdin=DEVNULL,
        stderr=STDOUT,
    )
    if proc.returncode != 0:
        _exit(1)

    db = None
    if "DATABASE_URI" in environ:
        db = Database(logger)
    elif kubernetes:
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
    else:
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
            for var in instance.attrs["Config"]["Env"]:
                if var.startswith("DATABASE_URI="):
                    db = Database(logger, var.replace("DATABASE_URI=", "", 1))
                    break

    if db is None:
        logger.error("No database found, exiting ...")
        _exit(1)

    while not db.is_initialized():
        logger.warning(
            "Database is not initialized, retrying in 5 seconds ...",
        )
        sleep(5)

    # Instantiate the controller
    if swarm:
        logger.info("Swarm mode detected")
        controller = SwarmController(docker_host)
    elif kubernetes:
        logger.info("Kubernetes mode detected")
        controller = IngressController()
    else:
        logger.info("Docker mode detected")
        controller = DockerController(docker_host)

    # Wait for instances
    logger.info("Waiting for BunkerWeb instances ...")
    instances = controller.wait(wait_retry_interval)
    logger.info("BunkerWeb instances are ready 🚀")
    i = 1
    for instance in instances:
        logger.info(f"Instance #{i} : {instance['name']}")
        i += 1

    # Run first configuration
    ret = controller.apply_config()
    if not ret:
        logger.error("Error while applying initial configuration")
        _exit(1)

    # Process events
    logger.info("Processing events ...")
    controller.process_events()

except:
    logger.error(f"Exception while running autoconf :\n{format_exc()}")
    sys_exit(1)
