#!/usr/bin/env python3

from os import _exit, environ, getenv, sep
from os.path import join
from signal import SIGINT, SIGTERM, signal
from sys import exit as sys_exit, path as sys_path
from traceback import format_exc
from pathlib import Path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from common_utils import handle_docker_secrets  # type: ignore
from logger import getLogger  # type: ignore
from controllers.SwarmController import SwarmController
from controllers.IngressController import IngressController
from controllers.DockerController import DockerController
from controllers.GatewayController import GatewayController

# Get variables
# Handle Docker secrets first
docker_secrets = handle_docker_secrets()
if docker_secrets:
    # Update environment with secrets
    environ.update(docker_secrets)

LOGGER = getLogger("AUTOCONF")

if docker_secrets:
    LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")

swarm = getenv("SWARM_MODE", "no").lower() == "yes"
gateway_api = getenv("KUBERNETES_GATEWAY_MODE", "no").lower() == "yes"
kubernetes = gateway_api or getenv("KUBERNETES_MODE", "no").lower() == "yes"
docker_host = getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
wait_retry_interval = getenv("WAIT_RETRY_INTERVAL", "5")

if not wait_retry_interval.isdigit():
    LOGGER.error("Invalid WAIT_RETRY_INTERVAL value, must be an integer")
    _exit(1)

wait_retry_interval = int(wait_retry_interval)


def exit_handler(signum, frame):
    LOGGER.info("Stop signal received, exiting...")
    _exit(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)

try:
    # Instantiate the controller
    if swarm:
        LOGGER.info("Swarm mode detected")
        controller = SwarmController(docker_host)
    elif kubernetes:
        if gateway_api:
            LOGGER.info("Kubernetes Gateway API mode detected")
            controller = GatewayController()
        else:
            LOGGER.info("Kubernetes mode detected")
            controller = IngressController()
    else:
        LOGGER.info("Docker mode detected")
        controller = DockerController(docker_host)

    # Wait for instances
    LOGGER.info("Waiting for BunkerWeb instances ...")
    instances = controller.wait(wait_retry_interval)
    LOGGER.info("BunkerWeb instances are ready 🚀")
    i = 1
    for instance in instances:
        LOGGER.info(f"Instance #{i} : {instance['name']}")
        i += 1

    controller.wait_applying(True)

    # Process events
    Path(sep, "var", "tmp", "bunkerweb", "autoconf.healthy").write_text("ok")
    LOGGER.info("Processing events ...")
    controller.process_events()
except:
    LOGGER.error(f"Exception while running autoconf :\n{format_exc()}")
    sys_exit(1)
finally:
    Path(sep, "var", "tmp", "bunkerweb", "autoconf.healthy").unlink(missing_ok=True)
