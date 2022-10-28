#!/usr/bin/python3

from os import _exit, getenv
from signal import SIGINT, SIGTERM, signal
from subprocess import DEVNULL, STDOUT, run
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/deps/python")
sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/api")
sys_path.append("/opt/bunkerweb/db")

from logger import setup_logger
from SwarmController import SwarmController
from IngressController import IngressController
from DockerController import DockerController

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
