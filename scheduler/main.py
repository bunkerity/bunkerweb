#!/usr/bin/python3

from argparse import ArgumentParser
from copy import deepcopy
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

from dotenv import dotenv_values

from logger import setup_logger
from Database import Database
from JobScheduler import JobScheduler
from API import API

run = True
scheduler = None
reloading = False
logger = setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))


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

        bw_integration = "Local"

        if args.variables:
            logger.info(f"Variables : {args.variables}")

            # Read env file
            env = dotenv_values(args.variables)
        else:
            # Read from database
            bw_integration = (
                "Kubernetes" if getenv("KUBERNETES_MODE", "no") == "yes" else "Cluster"
            )

            db = Database(
                logger,
                sqlalchemy_string=getenv("DATABASE_URI", None),
                bw_integration=bw_integration,
            )

            while not db.is_initialized():
                logger.warning(
                    "Database is not initialized, retrying in 5s ...",
                )
                sleep(3)

            env = db.get_config()
            while not db.is_first_config_saved() or not env:
                logger.warning(
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
            # Instantiate scheduler
            scheduler = JobScheduler(
                env=deepcopy(env),
                apis=[],
                logger=logger,
                auto=not args.variables,
                bw_integration=bw_integration,
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
                    logger.debug(f"{tmp_env=}")
                    logger.debug(f"{env=}")
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
