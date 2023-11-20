#!/usr/bin/python3
# -*- coding: utf-8 -*-

from os import _exit, environ, getpid, sep
from os.path import join
from signal import SIGINT, SIGTERM, signal
from sys import path as sys_path
from pathlib import Path
from time import sleep

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from autoconf import AutoconfConfig  # type: ignore

from API import API  # type: ignore
from logger import setup_logger  # type: ignore
from SwarmController import SwarmController
from IngressController import IngressController
from DockerController import DockerController

# Get variables
PID_PATH = Path(sep, "var", "run", "bunkerweb", "autoconf.pid")
HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "autoconf.healthy")
AUTOCONF_CONFIG = AutoconfConfig("autoconf", **environ)
LOGGER = setup_logger("Autoconf", AUTOCONF_CONFIG.log_level)


def stop(status):
    PID_PATH.unlink(missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


if not isinstance(AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL, int) and (not AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL.isdigit() or int(AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL) < 1):
    LOGGER.error(f"Invalid WAIT_RETRY_INTERVAL provided: {AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer.")
    stop(1)


def exit_handler(signum, frame):
    LOGGER.info("Stop signal received, exiting...")
    stop(0)


signal(SIGINT, exit_handler)
signal(SIGTERM, exit_handler)

try:
    # Don't execute if pid file exists
    if PID_PATH.is_file():
        LOGGER.error(
            "Autoconf is already running, skipping execution ...",
        )
        _exit(1)

    # Write pid to file
    PID_PATH.write_text(str(getpid()), encoding="utf-8")

    CORE_API: API = API(AUTOCONF_CONFIG.CORE_ADDR, "bw-autoconf")

    LOGGER.info("Test API connection ...")

    sent = None
    status = None
    while not sent and status != 200:
        sent, err, status, resp = CORE_API.request(
            "GET",
            "/ping",
            additonal_headers={"Authorization": f"Bearer {AUTOCONF_CONFIG.CORE_TOKEN}"} if AUTOCONF_CONFIG.CORE_TOKEN else {},
            timeout=3,
        )

        if not sent or status != 200:
            LOGGER.warning(
                f"Could not contact core API. Waiting {AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL} seconds before retrying ...",
            )
            sleep(int(AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL))
        else:
            LOGGER.info(
                f"Successfully sent API request to {CORE_API.endpoint}ping",
            )

    LOGGER.info("✅ Autoconf is ready")

    # Instantiate the controller
    if AUTOCONF_CONFIG.swarm_mode:
        LOGGER.info("🐝 Swarm mode detected")
        controller = SwarmController(
            AUTOCONF_CONFIG.DOCKER_HOST,
            CORE_API,
            AUTOCONF_CONFIG.log_level,
            api_token=AUTOCONF_CONFIG.CORE_TOKEN,
            wait_retry_interval=AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL,
        )
    elif AUTOCONF_CONFIG.kubernetes_mode:
        LOGGER.info("☸️ Kubernetes mode detected")
        controller = IngressController(
            CORE_API,
            AUTOCONF_CONFIG.log_level,
            api_token=AUTOCONF_CONFIG.CORE_TOKEN,
            wait_retry_interval=AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL,
        )
    else:
        LOGGER.info("🐳 Docker mode detected")
        controller = DockerController(
            AUTOCONF_CONFIG.DOCKER_HOST,
            CORE_API,
            AUTOCONF_CONFIG.log_level,
            api_token=AUTOCONF_CONFIG.CORE_TOKEN,
            wait_retry_interval=AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL,
        )

    # Wait for instances
    LOGGER.info(f"Waiting for BunkerWeb instances, retrying every {AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL} seconds...")
    instances = controller.wait(int(AUTOCONF_CONFIG.WAIT_RETRY_INTERVAL))
    LOGGER.info("BunkerWeb instances are ready 🚀")
    i = 1
    for instance in instances:
        LOGGER.info(f"Instance #{i} : {instance['name']}")
        i += 1

    # Run first configuration
    ret = controller.apply_config()
    if not ret:
        LOGGER.error("Error while applying initial configuration")
        stop(1)

    # Process events
    HEALTHY_PATH.write_text("ok")
    LOGGER.info("🔄 Processing events ...")
    controller.process_events()
except:
    LOGGER.exception("Exception while running autoconf")
    stop(1)

stop(0)
