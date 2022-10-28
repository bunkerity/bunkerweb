#!/usr/bin/python3

from argparse import ArgumentParser
from copy import deepcopy
from glob import glob
from os import _exit, getenv, getpid, makedirs, path, remove, unlink
from os.path import dirname, isdir, isfile, islink
from shutil import rmtree
from signal import SIGINT, SIGTERM, SIGUSR1, SIGUSR2, signal
from subprocess import PIPE, run as subprocess_run, DEVNULL, STDOUT
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
from ApiCaller import ApiCaller

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
            "--variables",
            type=str,
            help="path to the file containing environment variables",
        )
        parser.add_argument(
            "--generate",
            default="no",
            type=str,
            help="Precise if the configuration needs to be generated directly or not",
        )
        args = parser.parse_args()

        logger.info("Scheduler started ...")

        bw_integration = (
            "Local"
            if not isfile("/usr/sbin/nginx")
            and not isfile("/opt/bunkerweb/tmp/nginx.pid")
            else "Cluster"
        )

        if args.variables:
            logger.info(f"Variables : {args.variables}")

            # Read env file
            env = dotenv_values(args.variables)
        else:
            # Read from database
            bw_integration = (
                "Kubernetes" if getenv("KUBERNETES_MODE", "no") == "yes" else "Cluster"
            )

            api_caller = ApiCaller()
            api_caller.auto_setup(bw_integration=bw_integration)

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

            custom_configs = db.get_custom_configs()

            original_path = "/data/configs"
            makedirs(original_path, exist_ok=True)
            for custom_config in custom_configs:
                tmp_path = f"{original_path}/{custom_config['type'].replace('_', '-')}"
                if custom_config["service_id"]:
                    tmp_path += f"/{custom_config['service_id']}"
                tmp_path += f"/{custom_config['name']}.conf"
                makedirs(dirname(tmp_path), exist_ok=True)
                with open(tmp_path, "wb") as f:
                    f.write(custom_config["data"])

            if bw_integration != "Local":
                logger.info("Sending custom configs to BunkerWeb")
                ret = api_caller._send_files("/data/configs", "/custom_configs")

                if not ret:
                    logger.error(
                        "Sending custom configs failed, configuration will not work as expected...",
                    )

        logger.info("Executing scheduler ...")
        while True:
            # Instantiate scheduler
            scheduler = JobScheduler(
                env=deepcopy(env),
                apis=api_caller._get_apis(),
                logger=logger,
                bw_integration=bw_integration,
            )

            # Only run jobs once
            if not scheduler.run_once():
                logger.error("At least one job in run_once() failed")
            else:
                logger.info("All jobs in run_once() were successful")

            # run the generator
            cmd = f"python /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx{f' --variables {args.variables}' if args.variables else ''} --method scheduler"
            proc = subprocess_run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
            if proc.returncode != 0:
                logger.error(
                    "Config generator failed, configuration will not work as expected...",
                )

            if len(api_caller._get_apis()) > 0:
                # send nginx configs
                logger.info("Sending /etc/nginx folder ...")
                ret = api_caller._send_files("/etc/nginx", "/confs")
                if not ret:
                    logger.error(
                        "Sending nginx configs failed, configuration will not work as expected...",
                    )

            try:
                if len(api_caller._get_apis()) > 0:
                    # send cache
                    logger.info("Sending /data/cache folder ...")
                    if not api_caller._send_files("/data/cache", "/cache"):
                        logger.error("Error while sending /data/cache folder")
                    else:
                        logger.info("Successfuly sent /data/cache folder")

                # reload nginx
                if bw_integration == "Local":
                    logger.info("Reloading nginx ...")
                    proc = run(
                        ["/usr/sbin/nginx", "-s", "reload"],
                        stdin=DEVNULL,
                        stderr=PIPE,
                        env=deepcopy(env),
                    )
                    if proc.returncode == 0:
                        logger.info("Successfuly reloaded nginx")
                    else:
                        logger.error(
                            f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8')}",
                        )
                else:
                    logger.info("Reloading nginx ...")
                    if api_caller._send_to_apis("POST", "/reload"):
                        logger.info("Successfuly reloaded nginx")
                    else:
                        logger.error("Error while reloading nginx")
            except:
                logger.error(
                    f"Exception while reloading after running jobs once scheduling : {format_exc()}",
                )

            # infinite schedule for the jobs
            scheduler.setup()
            logger.info("Executing job scheduler ...")
            while run:
                scheduler.run_pending()
                sleep(1)

                # check if the custom configs have changed since last time
                tmp_custom_configs = db.get_custom_configs()
                if custom_configs != tmp_custom_configs:
                    logger.info("Custom configs changed, generating ...")
                    logger.debug(f"{tmp_custom_configs}")
                    logger.debug(f"{custom_configs}")
                    custom_configs = tmp_custom_configs
                    original_path = "/data/configs"

                    # Remove old custom configs files
                    logger.info("Removing old custom configs files ...")
                    files = glob(f"{original_path}/*")
                    for file in files:
                        if islink(file):
                            unlink(file)
                        elif isfile(file):
                            remove(file)
                        elif isdir(file):
                            rmtree(file, ignore_errors=False)

                    logger.info("Generating new custom configs ...")
                    makedirs(original_path, exist_ok=True)
                    for custom_config in custom_configs:
                        tmp_path = (
                            f"{original_path}/{custom_config['type'].replace('_', '-')}"
                        )
                        if custom_config["service_id"]:
                            tmp_path += f"/{custom_config['service_id']}"
                        tmp_path += f"/{custom_config['name']}.conf"
                        makedirs(dirname(tmp_path), exist_ok=True)
                        with open(tmp_path, "wb") as f:
                            f.write(custom_config["data"])

                    if bw_integration != "Local":
                        logger.info("Sending custom configs to BunkerWeb")
                        ret = api_caller._send_files("/data/configs", "/custom_configs")

                        if not ret:
                            logger.error(
                                "Sending custom configs failed, configuration will not work as expected...",
                            )

                # check if the config have changed since last time
                tmp_env = (
                    dotenv_values(args.variables) if args.variables else db.get_config()
                )
                if env != tmp_env:
                    logger.info("Config changed, generating ...")
                    logger.debug(f"{tmp_env=}")
                    logger.debug(f"{env=}")
                    env = deepcopy(tmp_env)
                    break
    except:
        logger.error(
            f"Exception while executing scheduler : {format_exc()}",
        )
        stop(1)
