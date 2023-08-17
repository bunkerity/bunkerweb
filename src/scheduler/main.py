#!/usr/bin/python3

from contextlib import suppress
from os import _exit, environ, getpid, sep
from os.path import join
from pathlib import Path
from signal import SIGINT, SIGTERM, signal, SIGHUP
from socket import gaierror, herror
from sys import path as sys_path
from threading import Thread
from time import sleep
from traceback import format_exc
from typing import Optional


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths)
    for paths in (("deps", "python"), ("utils",), ("api",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from kombu import Connection, Queue

from logger import setup_logger  # type: ignore
from API import API  # type: ignore
from JobScheduler import JobScheduler
from scheduler import SchedulerConfig  # type: ignore

RUN_ONCE = False
SCHEDULER_HEALTHY_PATH = Path(sep, "var", "tmp", "bunkerweb", "scheduler.healthy")
SCHEDULER_PID_PATH = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
SCHEDULER: Optional[JobScheduler] = None
CORE_API: Optional[API] = None
SCHEDULER_CONFIG = SchedulerConfig("scheduler", **environ)

LOGGER = setup_logger("Scheduler", SCHEDULER_CONFIG.log_level)


def stop(status):
    SCHEDULER_PID_PATH.unlink(missing_ok=True)
    SCHEDULER_HEALTHY_PATH.unlink(missing_ok=True)
    _exit(status)


if not SCHEDULER_CONFIG.API_ADDR:
    LOGGER.error("API_ADDR is not set")
    stop(1)

if (
    not SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL.isdigit()
    or int(SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL) < 1
):
    LOGGER.error(
        f"Invalid WAIT_RETRY_INTERVAL provided: {SCHEDULER_CONFIG.WAIT_RETRY_INTERVAL}, It must be a positive integer."
    )
    stop(1)


def handle_stop(signum, frame):
    if SCHEDULER is not None:
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Function to catch SIGHUP and reload the scheduler
def handle_reload(signum, frame):
    global CORE_API, SCHEDULER_CONFIG

    try:
        if SCHEDULER is not None:
            SCHEDULER_CONFIG = SchedulerConfig("scheduler", **environ)
            CORE_API = API(SCHEDULER_CONFIG.API_ADDR, "bw-scheduler")

            if SCHEDULER.reload(SCHEDULER_CONFIG.model_dump(), CORE_API):
                LOGGER.info("✅ Scheduler successfully reloaded")
            else:
                LOGGER.error("❌ Scheduler failed to reload")
        else:
            LOGGER.warning(
                "Ignored reload operation because scheduler is not running ...",
            )
    except:
        LOGGER.error(
            f"Exception while reloading scheduler : {format_exc()}",
        )


signal(SIGHUP, handle_reload)


if __name__ == "__main__":
    try:
        # Don't execute if pid file exists
        if SCHEDULER_PID_PATH.is_file():
            LOGGER.error(
                "Scheduler is already running, skipping execution ...",
            )
            _exit(1)

        # Write pid to file
        SCHEDULER_PID_PATH.write_text(str(getpid()), encoding="utf-8")

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

        CORE_API: API = API(SCHEDULER_CONFIG.API_ADDR, "bw-scheduler")

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

            if isinstance(body, dict):
                _type = body.get("type")
                if _type == "run_once":
                    RUN_ONCE = True
                elif _type == "run_single":
                    job_name = body.get("job_name")

                    if not job_name:
                        LOGGER.error("❌ No job name provided in message")
                        message.ack()
                        return

                    SCHEDULER.run_single(job_name)
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
