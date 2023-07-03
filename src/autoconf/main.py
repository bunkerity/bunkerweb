#!/usr/bin/python3

from os import _exit, getenv, sep
from os.path import join
from signal import SIGINT, SIGTERM, signal
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from pathlib import Path

for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",), ("db",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import setup_logger  # type: ignore
from SwarmController import SwarmController
from IngressController import IngressController
from DockerController import DockerController

# Get variables
logger = setup_logger("Autoconf", getenv("LOG_LEVEL", "INFO"))
swarm = getenv("SWARM_MODE", "no").lower() == "yes"
kubernetes = getenv("KUBERNETES_MODE", "no").lower() == "yes"
docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
wait_retry_interval = getenv("WAIT_RETRY_INTERVAL", "5")

if not wait_retry_interval.isdigit():
    logger.error("Invalid WAIT_RETRY_INTERVAL value, must be an integer")
    _exit(1)

wait_retry_interval = int(wait_retry_interval)


def exit_handler(signum, frame):
    logger.info("Stop signal received, exiting...")
    _exit(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)

try:
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
    Path(sep, "var", "tmp", "bunkerweb", "autoconf.healthy").write_text("ok")
    logger.info("Processing events ...")
    controller.process_events()
except:
    logger.error(f"Exception while running autoconf :\n{format_exc()}")
    sys_exit(1)
finally:
    Path(sep, "var", "tmp", "bunkerweb", "autoconf.healthy").unlink(missing_ok=True)
