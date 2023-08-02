#!/usr/bin/python3

from argparse import ArgumentParser
from contextlib import suppress
from glob import glob
from hashlib import sha256
from io import BytesIO
from json import dumps, load as json_load
from os import (
    _exit,
    chmod,
    environ,
    getenv,
    getpid,
    listdir,
    sep,
    walk,
)
from os.path import basename, dirname, join, normpath
from pathlib import Path
from shutil import copy, rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from socket import gaierror, herror
from stat import S_IEXEC
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import open as tar_open
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Optional, Union


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from kombu import Connection, Consumer, Queue

from logger import setup_logger  # type: ignore
from API import API  # type: ignore
from JobScheduler import JobScheduler
from scheduler import SchedulerConfig

RUN_ONCE = False
SCHEDULER_HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy")
SCHEDULER: Optional[JobScheduler] = None
SCHEDULER_CONFIG = SchedulerConfig("scheduler", **environ)
LOGGER = setup_logger("Scheduler", SCHEDULER_CONFIG.log_level)

if not SCHEDULER_CONFIG.API_ADDR:
    LOGGER.error("API_ADDR is not set")
    _exit(1)

if not SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL.isdigit():
    LOGGER.error("WAIT_RETRY_INTERVAL is not a digit")
    _exit(1)


def handle_stop(signum, frame):
    if SCHEDULER is not None:
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Function to catch SIGHUP and reload the scheduler
def handle_reload(signum, frame):
    try:
        pass

        # TODO: change this
        # if SCHEDULER is not None and RUN:
        #     # Get the env by reading the .env file
        #     tmp_env = dotenv_values(join(sep, "etc", "bunkerweb", "variables.env"))
        #     if SCHEDULER.reload(tmp_env):
        #         LOGGER.info("Reload successful")
        #     else:
        #         LOGGER.error("Reload failed")
        # else:
        #     LOGGER.warning(
        #         "Ignored reload operation because scheduler is not running ...",
        #     )
    except:
        LOGGER.error(
            f"Exception while reloading scheduler : {format_exc()}",
        )


signal(SIGHUP, handle_reload)


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy").unlink(missing_ok=True)
    _exit(status)


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            LOGGER.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")

        del pid_path

        MQ_PATH = None

        if SCHEDULER_CONFIG.MQ_URI.startswith("filesystem:///"):
            MQ_PATH = Path(SCHEDULER_CONFIG.MQ_URI.replace("filesystem:///", ""))

            while not MQ_PATH.exists():
                LOGGER.warning(
                    f"Waiting for {MQ_PATH} to be created, retrying in {SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL} second ..."
                )
                sleep(int(SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL))

            KOMBU_CONNECTION = Connection(
                "filesystem://",
                transport_options={
                    "data_folder_in": str(MQ_PATH.joinpath("data_out")),
                    "data_folder_out": str(MQ_PATH.joinpath("data_in")),
                },
            )
        else:
            KOMBU_CONNECTION = Connection(SCHEDULER_CONFIG.MQ_URI)

        with suppress(ConnectionRefusedError, gaierror, herror):
            KOMBU_CONNECTION.connect()

        retries = 0
        while not KOMBU_CONNECTION.connected and retries < 15:
            LOGGER.warning(
                f"Waiting for Kombu to be connected, retrying in {SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL} seconds ..."
            )
            sleep(int(SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL))
            with suppress(ConnectionRefusedError, gaierror, herror):
                KOMBU_CONNECTION.connect()
            retries += 1

        if not KOMBU_CONNECTION.connected:
            LOGGER.error(
                f"Coudln't initiate a connection with Kombu with uri {SCHEDULER_CONFIG.MQ_URI}, exiting ..."
            )
            stop(1)

        KOMBU_CONNECTION.release()

        LOGGER.info("✅ Connection to Kombu succeeded")

        scheduler_queue = Queue("scheduler", routing_key="scheduler")

        CORE_API = API(SCHEDULER_CONFIG.API_ADDR, "bw-scheduler")

        LOGGER.info("Test API connection ...")

        retries = 0
        sent = None
        status = None
        while not sent and status != 200 and retries < 5:
            sent, err, status, resp = CORE_API.request(
                "GET",
                "/ping",
                additonal_headers={
                    "Authorization": f"Bearer {SCHEDULER_CONFIG.API_TOKEN}"
                }
                if SCHEDULER_CONFIG.API_TOKEN
                else {},
            )

            if not sent or status != 200:
                LOGGER.warning(
                    f"Could not contact core API. Waiting {SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL} seconds before retrying ...",
                )
                sleep(int(SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL))
                retries += 1
            else:
                LOGGER.info(
                    f"Successfully sent API request to {CORE_API.endpoint}ping",
                )

        if not sent or status != 200:
            LOGGER.error(
                f"Could not send core API request to {CORE_API.endpoint}ping after {retries} retries, exiting ...",
            )
            stop(1)

        LOGGER.info("Scheduler started ...")

        # Instantiate scheduler
        SCHEDULER = JobScheduler(
            CORE_API, env=SCHEDULER_CONFIG.model_dump(), logger=LOGGER
        )

        # Function to process the incoming message
        def process_message(body, message):
            global RUN_ONCE
            LOGGER.info(f"📥 Received message : {body}")
            if isinstance(body, dict) and body.get("type") == "run_once":
                RUN_ONCE = True
            message.ack()

        with KOMBU_CONNECTION:
            with KOMBU_CONNECTION.Consumer(
                [scheduler_queue],
                callbacks=[process_message],
                accept=["json"],
            ) as consumer:
                while True:
                    SCHEDULER.setup()

                    if RUN_ONCE:
                        # Only run jobs once
                        if not SCHEDULER.run_once():
                            LOGGER.error("At least one job in run_once() failed")
                        else:
                            LOGGER.info("All jobs in run_once() were successful")

                        RUN_ONCE = False

                    # infinite schedule for the jobs
                    LOGGER.info("Executing scheduler ...")
                    if not SCHEDULER_HEALTHY_PATH.exists():
                        SCHEDULER_HEALTHY_PATH.write_text("ok", encoding="utf-8")

                    while not RUN_ONCE:
                        SCHEDULER.run_pending()
                        with suppress(TimeoutError):
                            KOMBU_CONNECTION.drain_events(timeout=1)

                    threads = [
                        Thread(target=SCHEDULER.update_env),
                        Thread(target=SCHEDULER.update_jobs),
                    ]

                    for thread in threads:
                        thread.start()

                    for thread in threads:
                        thread.join()

    except:
        LOGGER.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)
