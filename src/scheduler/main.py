#!/usr/bin/env python3

from argparse import ArgumentParser
from contextlib import suppress
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from gc import collect
from io import BytesIO
from json import load as json_load
from logging import Logger
from os import _exit, environ, getenv, getpid, sep
from os.path import join
from pathlib import Path
from shutil import rmtree
from signal import SIGINT, SIGTERM, signal, SIGHUP
from stat import S_IRGRP, S_IRUSR, S_IWUSR, S_IXGRP, S_IXUSR
from subprocess import run as subprocess_run, DEVNULL, STDOUT
from sys import path as sys_path
from tarfile import open as tar_open
from threading import Event, Lock
from time import sleep
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Union

BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")

for deps_path in [BUNKERWEB_PATH.joinpath(*paths).as_posix() for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from schedule import every as schedule_every, run_pending

from common_utils import bytes_hash, dict_to_frozenset, handle_docker_secrets, create_plugin_tar_gz, plugin_tar_exclude  # type: ignore
from logger import getLogger  # type: ignore
from jobs import _write_atomic  # type: ignore
from api_client import SchedulerApiClient

from JobScheduler import JobScheduler

# System vars that may leak into API /global_settings defaults but must not
# clobber container env when applied via SCHEDULER.env = ...
_BOOTSTRAP_ENV_KEYS = ("DATABASE_URI", "DATABASE_URI_READONLY", "PYTHONPATH", "PATH")


def _strip_bootstrap_env(env: dict) -> dict:
    """Drop system-only keys returned by /global_settings full=true so the real
    container env (DATABASE_URI etc.) wins on subprocess invocations."""
    for k in _BOOTSTRAP_ENV_KEYS:
        env.pop(k, None)
    return env


APPLYING_CHANGES = Event()

RUN = True
SCHEDULER: Optional[JobScheduler] = None
API_CLIENT: Optional[SchedulerApiClient] = None
SCHEDULER_LOCK = Lock()

CUSTOM_CONFIGS_PATH = Path(sep, "etc", "bunkerweb", "configs")
CUSTOM_CONFIGS_PATH.mkdir(parents=True, exist_ok=True)
CUSTOM_CONFIGS_DIRS = (
    "http",
    "stream",
    "server-http",
    "server-stream",
    "default-server-http",
    "default-server-stream",
    "modsec",
    "modsec-crs",
    "crs-plugins-before",
    "crs-plugins-after",
)

for custom_config_dir in CUSTOM_CONFIGS_DIRS:
    CUSTOM_CONFIGS_PATH.joinpath(custom_config_dir).mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path(sep, "etc", "nginx")
NGINX_VARIABLES_PATH = CONFIG_PATH.joinpath("variables.env")

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")
EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

PRO_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "pro", "plugins")
PRO_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)

TMP_PATH = Path(sep, "var", "tmp", "bunkerweb")
TMP_PATH.mkdir(parents=True, exist_ok=True)
NGINX_TMP_VARIABLES_PATH = TMP_PATH.joinpath("variables.env")

HEALTHY_PATH = TMP_PATH.joinpath("scheduler.healthy")

DB_LOCK_FILE = Path(sep, "var", "lib", "bunkerweb", "db.lock")
LOGGER = getLogger("SCHEDULER")

HEALTHCHECK_INTERVAL = getenv("HEALTHCHECK_INTERVAL", "30")

if not HEALTHCHECK_INTERVAL.isdigit():
    LOGGER.error("HEALTHCHECK_INTERVAL must be an integer, defaulting to 30")
    HEALTHCHECK_INTERVAL = 30

HEALTHCHECK_INTERVAL = int(HEALTHCHECK_INTERVAL)
HEALTHCHECK_EVENT = Event()
HEALTHCHECK_LOGGER = getLogger("SCHEDULER.HEALTHCHECK")

# Shared executor to reuse worker threads across scheduler tasks
SCHEDULER_TASKS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bw-scheduler-tasks")

RELOAD_MIN_TIMEOUT = getenv("RELOAD_MIN_TIMEOUT", "5")

if not RELOAD_MIN_TIMEOUT.isdigit():
    LOGGER.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
    RELOAD_MIN_TIMEOUT = 5

RELOAD_MIN_TIMEOUT = int(RELOAD_MIN_TIMEOUT)

DISABLE_CONFIGURATION_TESTING = getenv("DISABLE_CONFIGURATION_TESTING", "no").lower() == "yes"

if DISABLE_CONFIGURATION_TESTING:
    LOGGER.warning("Configuration testing is disabled, changes will be applied without testing (we hope you know what you're doing) ...")


def handle_stop(signum, frame):
    current_time = datetime.now().astimezone()
    while APPLYING_CHANGES.is_set() and (datetime.now().astimezone() - current_time).seconds < 30:
        LOGGER.warning("Waiting for the changes to be applied before stopping ...")
        sleep(1)

    if APPLYING_CHANGES.is_set():
        LOGGER.warning("Timeout reached, stopping without waiting for the changes to be applied ...")

    if SCHEDULER is not None:
        SCHEDULER.clear()
    stop(0)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)


# Function to catch SIGHUP and reload the scheduler (save_config stays in scheduler per spec)
def handle_reload(signum, frame):
    try:
        if SCHEDULER is not None and RUN:
            if API_CLIENT and API_CLIENT.readonly:
                LOGGER.warning("The database is read-only, no need to save the changes in the configuration as they will not be saved")
                return

            cmd_env = {
                "PATH": getenv("PATH", ""),
                "PYTHONPATH": getenv("PYTHONPATH", ""),
                "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
                "LOG_LEVEL": getenv("LOG_LEVEL", ""),
                "DATABASE_URI": getenv("DATABASE_URI", ""),
            }

            if getenv("TZ"):
                cmd_env["TZ"] = getenv("TZ")

            for key, value in environ.items():
                if "CUSTOM_CONF" in key:
                    cmd_env[key] = value

            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    "--variables",
                    join(sep, "etc", "bunkerweb", "variables.env"),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
                env=cmd_env,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not work as expected...")
        else:
            LOGGER.warning("Ignored reload operation because scheduler is not running ...")
    except BaseException as e:
        LOGGER.error(f"Exception while reloading scheduler : {e}")


signal(SIGHUP, handle_reload)


def stop(status):
    Path(sep, "var", "run", "bunkerweb", "scheduler.pid").unlink(missing_ok=True)
    HEALTHY_PATH.unlink(missing_ok=True)
    SCHEDULER_TASKS_EXECUTOR.shutdown(wait=False)
    _exit(status)


def generate_custom_configs(configs: Optional[List[Dict[str, Any]]] = None, *, original_path: Union[Path, str] = CUSTOM_CONFIGS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)

    # Remove old custom configs files
    LOGGER.info("Removing old custom configs files ...")
    if original_path.is_dir():
        for file in original_path.glob("*/*"):
            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
            elif file.is_dir():
                rmtree(file, ignore_errors=True)

    if configs is None:
        assert API_CLIENT is not None
        configs = API_CLIENT.get_custom_configs()

    if configs:
        LOGGER.info("Generating new custom configs ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for custom_config in configs:
            try:
                if custom_config.get("is_draft"):
                    continue
                if custom_config["data"]:
                    tmp_path = original_path.joinpath(
                        custom_config["type"].replace("_", "-"),
                        custom_config["service_id"] or "",
                        f"{Path(custom_config['name']).stem}.conf",
                    )
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    _write_atomic(tmp_path, custom_config["data"])
                    desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
                    if tmp_path.stat().st_mode & 0o777 != desired_perms:
                        tmp_path.chmod(desired_perms)
            except OSError as e:
                LOGGER.debug(format_exc())
                if custom_config["method"] != "manual":
                    LOGGER.error(
                        f"Error while generating custom configs \"{custom_config['name']}\"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: {e}"
                    )
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(
                    f"Error while generating custom configs \"{custom_config['name']}\"{' for service ' + custom_config['service_id'] if custom_config['service_id'] else ''}: {e}"
                )


def generate_external_plugins(original_path: Union[Path, str] = EXTERNAL_PLUGINS_PATH):
    if not isinstance(original_path, Path):
        original_path = Path(original_path)
    pro = original_path.as_posix().endswith("/pro/plugins")

    assert API_CLIENT is not None
    plugins = API_CLIENT.get_plugins(_type="pro" if pro else "external", with_data=True)
    assert plugins is not None, "Couldn't get plugins from API"

    # Remove old external/pro plugins files
    LOGGER.info(f"Removing old/changed {'pro ' if pro else ''}external plugins files ...")
    ignored_plugins = set()
    if original_path.is_dir():
        for file in original_path.glob("*"):
            with suppress(StopIteration, IndexError, FileNotFoundError):
                index = next(i for i, plugin in enumerate(plugins) if plugin["id"] == file.name)

                if file.is_dir():
                    plugin_content = create_plugin_tar_gz(file, arc_root=file.name)
                elif file.is_file():
                    if plugin_tar_exclude(file.as_posix()):
                        LOGGER.debug(f"Excluding file from tar: {file}")
                        continue
                    plugin_content = create_plugin_tar_gz(file, arc_root=file.name)
                else:
                    continue
                if bytes_hash(plugin_content, algorithm="sha256") == plugins[index]["checksum"]:
                    ignored_plugins.add(file.name)
                    continue
                LOGGER.debug(f"Checksum of {file} has changed, removing it ...")

            if file.is_symlink() or file.is_file():
                with suppress(OSError):
                    file.unlink()
            elif file.is_dir():
                rmtree(file, ignore_errors=True)

    if plugins:
        LOGGER.info(f"Generating new {'pro ' if pro else ''}external plugins ...")
        original_path.mkdir(parents=True, exist_ok=True)
        for plugin in plugins:
            if plugin["id"] in ignored_plugins:
                continue

            try:
                if plugin["data"]:
                    with tar_open(fileobj=BytesIO(plugin["data"]), mode="r:gz") as tar:
                        try:
                            tar.extractall(original_path, filter="fully_trusted")
                        except TypeError:
                            tar.extractall(original_path)

                    # Add u+x permissions to executable files
                    plugin_path = original_path.joinpath(plugin["id"])
                    desired_perms = S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IXGRP  # 0o750
                    for subdir, pattern in (
                        ("jobs", "*"),
                        ("bwcli", "*"),
                        ("ui", "*.py"),
                    ):
                        for executable_file in plugin_path.joinpath(subdir).rglob(pattern):
                            if executable_file.stat().st_mode & 0o777 != desired_perms:
                                executable_file.chmod(desired_perms)
            except OSError as e:
                LOGGER.debug(format_exc())
                if plugin["method"] != "manual":
                    LOGGER.error(f"Error while generating {'pro ' if pro else ''}external plugins \"{plugin['name']}\": {e}")
            except BaseException as e:
                LOGGER.debug(format_exc())
                LOGGER.error(f"Error while generating {'pro ' if pro else ''}external plugins \"{plugin['name']}\": {e}")


def generate_caches():
    assert API_CLIENT is not None

    job_cache_files = API_CLIENT.get_jobs_cache_files()
    plugin_cache_files = set()
    ignored_dirs = set()

    for job_cache_file in job_cache_files:
        job_path = Path(sep, "var", "cache", "bunkerweb", job_cache_file["plugin_id"])
        cache_path = job_path.joinpath(job_cache_file["service_id"] or "", job_cache_file["file_name"])
        plugin_cache_files.add(cache_path)

        try:
            if job_cache_file["file_name"].endswith(".tgz"):
                extract_path = cache_path.parent
                if job_cache_file["file_name"].startswith("folder:"):
                    extract_path = Path(job_cache_file["file_name"].split("folder:", 1)[1].rsplit(".tgz", 1)[0])
                ignored_dirs.add(extract_path.as_posix())
                rmtree(extract_path, ignore_errors=True)
                extract_path.mkdir(parents=True, exist_ok=True)
                with tar_open(fileobj=BytesIO(job_cache_file["data"]), mode="r:gz") as tar:
                    try:
                        tar.extractall(extract_path, filter="fully_trusted")
                    except TypeError:
                        tar.extractall(extract_path)
                LOGGER.debug(f"Restored cache directory {extract_path}")
                continue
            _write_atomic(cache_path, job_cache_file["data"])
            desired_perms = S_IRUSR | S_IWUSR | S_IRGRP  # 0o640
            if cache_path.stat().st_mode & 0o777 != desired_perms:
                cache_path.chmod(desired_perms)
            LOGGER.debug(f"Restored cache file {job_cache_file['file_name']}")
        except BaseException as e:
            LOGGER.error(f"Exception while restoring cache file {job_cache_file['file_name']} :\n{e}")

    if job_path.is_dir():
        for resource_path in list(job_path.rglob("*")):
            if resource_path.as_posix().startswith(tuple(ignored_dirs)):
                continue

            LOGGER.debug(f"Checking if {resource_path} should be removed")
            if resource_path not in plugin_cache_files and resource_path.is_file():
                LOGGER.debug(f"Removing non-cached file {resource_path}")
                resource_path.unlink(missing_ok=True)
                if resource_path.parent.is_dir() and not list(resource_path.parent.iterdir()):
                    LOGGER.debug(f"Removing empty directory {resource_path.parent}")
                    rmtree(resource_path.parent, ignore_errors=True)
                    if resource_path.parent == job_path:
                        break
                continue
            elif resource_path.is_dir() and not list(resource_path.iterdir()):
                LOGGER.debug(f"Removing empty directory {resource_path}")
                rmtree(resource_path, ignore_errors=True)
                continue

            desired_perms = S_IRUSR | S_IWUSR | S_IRGRP | S_IXUSR | S_IXGRP  # 0o750
            if resource_path.stat().st_mode & 0o777 != desired_perms:
                resource_path.chmod(desired_perms)


def generate_configs(logger: Logger = LOGGER) -> bool:
    cmd_env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
        "LOG_LEVEL": getenv("LOG_LEVEL", ""),
        "DATABASE_URI": getenv("DATABASE_URI", ""),
    }

    if getenv("TZ"):
        cmd_env["TZ"] = getenv("TZ")

    # run the generator
    proc = subprocess_run(
        [
            BUNKERWEB_PATH.joinpath("gen", "main.py").as_posix(),
            "--settings",
            BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
            "--templates",
            BUNKERWEB_PATH.joinpath("confs").as_posix(),
            "--output",
            CONFIG_PATH.as_posix(),
        ],
        stdin=DEVNULL,
        stderr=STDOUT,
        check=False,
        env=cmd_env,
    )

    if proc.returncode != 0:
        logger.error("Config generator failed, configuration will not work as expected...")
        return False

    return True


def healthcheck_job():
    if HEALTHCHECK_EVENT.is_set():
        HEALTHCHECK_LOGGER.warning("Healthcheck job is already running, skipping execution ...")
        return

    try:
        assert API_CLIENT is not None
    except AssertionError:
        return

    HEALTHCHECK_EVENT.set()

    if APPLYING_CHANGES.is_set():
        HEALTHCHECK_EVENT.clear()
        return

    recovered = False
    try:
        for db_instance in API_CLIENT.get_instances():
            hostname = db_instance["hostname"]
            previous_status = db_instance.get("status")
            reachable = False
            try:
                reachable = API_CLIENT.ping_instance(hostname)
            except BaseException as e:
                HEALTHCHECK_LOGGER.error(f"Exception while pinging instance {hostname}: {e}")

            if not reachable:
                HEALTHCHECK_LOGGER.warning(f"Instance {hostname} is not reachable, healthcheck will be retried in {HEALTHCHECK_INTERVAL} seconds ...")
                ret = API_CLIENT.update_instance(hostname, "down")
                if ret:
                    HEALTHCHECK_LOGGER.error(f"Couldn't update instance {hostname} status to down: {ret}")
                continue

            ret = API_CLIENT.update_instance(hostname, "up")
            if ret:
                HEALTHCHECK_LOGGER.error(f"Couldn't update instance {hostname} status to up: {ret}")
                continue

            if previous_status in ("down", "failover"):
                HEALTHCHECK_LOGGER.info(f"Instance {hostname} recovered from {previous_status} → up; will trigger push-configs to re-sync it")
                recovered = True

        if recovered and SCHEDULER is not None:
            try:
                if not SCHEDULER.run_single("push-configs"):
                    HEALTHCHECK_LOGGER.error("Failed to dispatch push-configs after instance recovery")
            except BaseException as e:
                HEALTHCHECK_LOGGER.error(f"Exception dispatching push-configs after recovery: {e}")
    finally:
        HEALTHCHECK_EVENT.clear()


if __name__ == "__main__":
    try:
        # Handle Docker secrets first
        docker_secrets = handle_docker_secrets()
        if docker_secrets:
            LOGGER.info(f"Loaded {len(docker_secrets)} Docker secrets")
            environ.update(docker_secrets)

        # Don't execute if pid file exists
        pid_path = Path(sep, "var", "run", "bunkerweb", "scheduler.pid")
        if pid_path.is_file():
            LOGGER.error("Scheduler is already running, skipping execution ...")
            _exit(1)

        # Write pid to file
        pid_path.write_text(str(getpid()), encoding="utf-8")

        del pid_path

        # Parse arguments
        parser = ArgumentParser(description="Job scheduler for BunkerWeb")
        parser.add_argument("--variables", type=str, help="path to the file containing environment variables")
        args = parser.parse_args()

        tmp_variables_path = Path(args.variables) if args.variables else NGINX_TMP_VARIABLES_PATH

        dotenv_env = {}
        if tmp_variables_path.is_file():
            with tmp_variables_path.open() as f:
                dotenv_env = dict(line.strip().split("=", 1) for line in f if line.strip() and not line.startswith("#") and "=" in line)

        # Initialize API client
        api_url = getenv("API_URL", dotenv_env.get("API_URL", "http://bw-api:5000"))
        api_token = getenv("API_TOKEN", dotenv_env.get("API_TOKEN", ""))
        API_CLIENT = SchedulerApiClient(api_url, api_token)

        # Wait for API to be ready
        LOGGER.info(f"Waiting for API at {api_url} to be ready ...")
        with API_CLIENT.expect_errors():
            while True:
                try:
                    API_CLIENT.ping()
                    break
                except Exception:
                    LOGGER.warning("API not ready yet, retrying in 5s ...")
                    sleep(5)
        LOGGER.info("API is ready")

        SCHEDULER = JobScheduler(LOGGER, api_client=API_CLIENT)

        APPLYING_CHANGES.set()

        if API_CLIENT.readonly:
            LOGGER.warning("The database is read-only, no need to save the changes in the configuration as they will not be saved")
        else:
            env_file_path = deepcopy(NGINX_TMP_VARIABLES_PATH)
            if args.variables:
                env_file_path = deepcopy(tmp_variables_path)
            else:
                env_content = "\n".join(f"{key}={value}" for key, value in environ.items() if "CUSTOM_CONF" not in key)
                env_file_path.write_text(env_content + "\n", encoding="utf-8")

            cmd_env = {
                "PATH": getenv("PATH", ""),
                "PYTHONPATH": getenv("PYTHONPATH", ""),
                "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
                "LOG_LEVEL": getenv("LOG_LEVEL", ""),
                "DATABASE_URI": getenv("DATABASE_URI", ""),
            }

            if getenv("TZ"):
                cmd_env["TZ"] = getenv("TZ")

            for key, value in environ.items():
                if "CUSTOM_CONF" in key:
                    cmd_env[key] = value

            # run the config saver (first-run stays in scheduler per spec)
            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    "--first-run",
                    "--variables",
                    env_file_path.as_posix(),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
                env=cmd_env,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not work as expected...")

        ready = False
        while not ready:
            db_metadata = API_CLIENT.get_metadata()
            if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
                LOGGER.warning("Database is not initialized, retrying in 5s ...")
            else:
                ready = True
                continue
            sleep(5)

        env = API_CLIENT.get_config()
        _strip_bootstrap_env(env)
        tz = getenv("TZ")
        if tz:
            env["TZ"] = tz

        # Instantiate scheduler environment
        SCHEDULER.env = env | {"RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)}

        task_futures: List[Future] = []

        scheduler_first_start = db_metadata["scheduler_first_start"]

        LOGGER.info("Scheduler started ...")

        def run_config_saver(log_message: str) -> bool:
            if API_CLIENT.readonly:
                LOGGER.warning("The database is read-only, no need to save plugins settings changes as they will not be saved")
                return False

            LOGGER.info(log_message)
            env_file_path = deepcopy(NGINX_TMP_VARIABLES_PATH)
            if args.variables:
                env_file_path = deepcopy(tmp_variables_path)
            else:
                env_content = "\n".join(
                    f"{key}={value}" for key, value in (env | {k: v for k, v in environ.items() if k in env}).items() if "CUSTOM_CONF" not in key
                )
                env_file_path.write_text(env_content + "\n", encoding="utf-8")

            cmd_env = {
                "PATH": getenv("PATH", ""),
                "PYTHONPATH": getenv("PYTHONPATH", ""),
                "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
                "LOG_LEVEL": getenv("LOG_LEVEL", ""),
                "DATABASE_URI": getenv("DATABASE_URI", ""),
            }

            if getenv("TZ"):
                cmd_env["TZ"] = getenv("TZ")

            for key, value in environ.items():
                if "CUSTOM_CONF" in key:
                    cmd_env[key] = value

            proc = subprocess_run(
                [
                    BUNKERWEB_PATH.joinpath("gen", "save_config.py").as_posix(),
                    "--settings",
                    BUNKERWEB_PATH.joinpath("settings.json").as_posix(),
                    "--variables",
                    env_file_path.as_posix(),
                ],
                stdin=DEVNULL,
                stderr=STDOUT,
                check=False,
                env=cmd_env,
            )
            if proc.returncode != 0:
                LOGGER.error("Config saver failed, configuration will not work as expected...")
                return False
            return True

        def check_configs_changes():
            # Checking if any custom config has been created by the user
            assert API_CLIENT is not None, "API_CLIENT is not defined"
            LOGGER.info("Checking if there are any changes in custom configs ...")
            custom_configs = []
            db_configs = API_CLIENT.get_custom_configs()
            changes = False
            for file in list(CUSTOM_CONFIGS_PATH.rglob("*.conf")):
                if len(file.parts) > len(CUSTOM_CONFIGS_PATH.parts) + 3:
                    LOGGER.warning(f"Custom config file {file} is not in the correct path, skipping ...")

                content = file.read_text(encoding="utf-8")
                service_id = file.parent.name if file.parent.name not in CUSTOM_CONFIGS_DIRS else None
                config_type = file.parent.parent.name if service_id else file.parent.name

                saving = True
                in_db = False
                from_template = False
                for db_conf in db_configs:
                    if db_conf["service_id"] == service_id and db_conf["name"] == file.stem:
                        in_db = True
                        if db_conf["template"]:
                            from_template = True

                if from_template or (not in_db and content.startswith("# CREATED BY ENV")):
                    saving = False
                    changes = not from_template

                if saving:
                    custom_configs.append({"value": content, "exploded": (service_id, config_type, file.stem), "is_draft": False})

            changes = changes or {hash(dict_to_frozenset(d)) for d in custom_configs} != {hash(dict_to_frozenset(d)) for d in db_configs}

            if changes:
                try:
                    err = API_CLIENT.save_custom_configs(custom_configs, "manual")
                    if err:
                        LOGGER.error(f"Couldn't save some manually created custom configs to database: {err}")
                except BaseException as e:
                    LOGGER.error(f"Error while saving custom configs to database: {e}")

            generate_custom_configs(API_CLIENT.get_custom_configs())

        def check_plugin_changes(_type: Literal["external", "pro"] = "external"):
            # Check if any external or pro plugin has been added by the user
            assert API_CLIENT is not None, "API_CLIENT is not defined"
            LOGGER.info(f"Checking if there are any changes in {_type} plugins ...")
            plugin_path = PRO_PLUGINS_PATH if _type == "pro" else EXTERNAL_PLUGINS_PATH
            plugins_before = {file.parent.name for file in plugin_path.glob("*/plugin.json")}
            db_plugins = API_CLIENT.get_plugins(_type=_type)
            external_plugins = []
            tmp_external_plugins = []
            for file in plugin_path.glob("*/plugin.json"):
                plugin_content = create_plugin_tar_gz(file.parent, arc_root=file.parent.name)

                with file.open("r", encoding="utf-8") as f:
                    plugin_data = json_load(f)

                if plugin_data["id"] == "letsencrypt_dns":
                    continue

                checksum = bytes_hash(plugin_content, algorithm="sha256")
                common_data = plugin_data | {
                    "type": _type,
                    "page": file.parent.joinpath("ui").is_dir(),
                    "checksum": checksum,
                }
                jobs = common_data.pop("jobs", [])

                with suppress(StopIteration, IndexError):
                    index = next(i for i, plugin in enumerate(db_plugins) if plugin["id"] == common_data["id"])

                    if checksum == db_plugins[index]["checksum"] or db_plugins[index]["method"] != "manual":
                        continue

                tmp_external_plugins.append(common_data.copy())

                external_plugins.append(
                    common_data
                    | {
                        "method": "manual",
                        "data": plugin_content.getvalue(),
                    }
                    | ({"jobs": jobs} if jobs else {})
                )

            changes = False
            if tmp_external_plugins:
                changes = {hash(dict_to_frozenset(d)) for d in tmp_external_plugins} != {hash(dict_to_frozenset(d)) for d in db_plugins}

                if changes:
                    try:
                        err = API_CLIENT.update_external_plugins(external_plugins, _type=_type, delete_missing=True)
                        if err:
                            LOGGER.error(f"Couldn't save some manually added {_type} plugins to database: {err}")
                    except BaseException as e:
                        LOGGER.error(f"Error while saving {_type} plugins to database: {e}")
                else:
                    return False

            generate_external_plugins(plugin_path)
            plugins_after = {file.parent.name for file in plugin_path.glob("*/plugin.json")}
            return plugins_before != plugins_after

        check_configs_changes()
        plugins_refreshed = []
        task_futures.extend(
            [
                SCHEDULER_TASKS_EXECUTOR.submit(check_plugin_changes, "external"),
                SCHEDULER_TASKS_EXECUTOR.submit(check_plugin_changes, "pro"),
            ]
        )

        for future in task_futures:
            plugins_refreshed.append(bool(future.result()))

        task_futures.clear()

        if any(plugins_refreshed):
            if run_config_saver("Running config saver after restoring plugin files from database ..."):
                SCHEDULER.update_jobs()
                env = API_CLIENT.get_config()
                _strip_bootstrap_env(env)
                tz = getenv("TZ")
                if tz:
                    env["TZ"] = tz

        LOGGER.info("Running plugins download jobs ...")
        SCHEDULER.run_once(["misc", "pro"])

        db_metadata = API_CLIENT.get_metadata()
        if isinstance(db_metadata, str):
            LOGGER.error(f"Error getting metadata: {db_metadata}")
        elif db_metadata["pro_plugins_changed"] or db_metadata["external_plugins_changed"]:
            task_futures.clear()

            if db_metadata["pro_plugins_changed"]:
                task_futures.append(SCHEDULER_TASKS_EXECUTOR.submit(generate_external_plugins, PRO_PLUGINS_PATH))
            if db_metadata["external_plugins_changed"]:
                task_futures.append(SCHEDULER_TASKS_EXECUTOR.submit(generate_external_plugins))

            for future in task_futures:
                future.result()

            task_futures.clear()

            if API_CLIENT.readonly:
                LOGGER.warning("The database is read-only, no need to look for changes in the plugins settings as they will not be saved")
            else:
                run_config_saver("Running config saver to save potential ignored external plugins settings ...")

            SCHEDULER.update_jobs()
            env = API_CLIENT.get_config()
            _strip_bootstrap_env(env)
            tz = getenv("TZ")
            if tz:
                env["TZ"] = tz

        LOGGER.info("Executing scheduler ...")

        del dotenv_env

        FIRST_START = True
        CONFIG_NEED_GENERATION = True
        RUN_JOBS_ONCE = True
        CHANGES = []

        changed_plugins = []
        old_changes = {}
        healthcheck_job_run = False

        while True:
            task_futures.clear()

            if RUN_JOBS_ONCE:
                # Dispatch all `once` jobs to workers (includes the
                # push-configs job, which renders + ships the NGINX config
                # tree to every BW instance and triggers a reload).
                if not SCHEDULER.reload(
                    env | {"TZ": getenv("TZ", "UTC"), "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)},
                    changed_plugins=changed_plugins,
                    ignore_plugins=["misc", "pro"] if FIRST_START else None,
                ):
                    LOGGER.error("At least one job in run_once() failed")
                else:
                    LOGGER.info("All jobs in run_once() were successful")
                    if API_CLIENT.readonly:
                        generate_caches()
                healthcheck_job_run = False

            if CONFIG_NEED_GENERATION and not FIRST_START:
                # Change detected — ask the worker to re-push. push-configs is
                # idempotent and Redis-locked against concurrent runs, so
                # bursty changes coalesce naturally. We must dispatch via
                # run_single (not rely on RUN_JOBS_ONCE) because SCHEDULER.reload
                # filters run_once to the `changed_plugins` set, which never
                # includes the "jobs" core plugin where push-configs lives.
                LOGGER.info("Configuration change detected — dispatching push-configs ...")
                if not SCHEDULER.run_single("push-configs"):
                    LOGGER.error("Failed to dispatch push-configs job")

            try:
                success = True
                # Update instance statuses (push + reload happen in the worker now)
                for db_instance in API_CLIENT.get_instances():
                    hostname = db_instance["hostname"]
                    is_up = API_CLIENT.ping_instance(hostname)
                    ret = API_CLIENT.update_instance(hostname, "up" if is_up else "down")
                    if ret:
                        LOGGER.error(f"Couldn't update instance {hostname} status: {ret}")
                    elif not is_up:
                        success = False
            except BaseException as e:
                LOGGER.error(f"Exception while updating instance statuses : {e}")
                success = False

            try:
                API_CLIENT.set_metadata({"failover": not success, "failover_message": ""})
            except BaseException as e:
                LOGGER.error(f"Error while setting failover metadata: {e}")

            if success:
                LOGGER.info("All BunkerWeb instances are up")
            else:
                LOGGER.error("One or more BunkerWeb instances are unreachable")

            try:
                ret = API_CLIENT.checked_changes(CHANGES, plugins_changes="all", value=False)
                if ret:
                    LOGGER.error(f"An error occurred when setting the changes to checked in the database : {ret}")
            except BaseException as e:
                LOGGER.error(f"Error while setting changes to checked in the database: {e}")

            FIRST_START = False
            NEED_RELOAD = False
            RUN_JOBS_ONCE = False
            CONFIG_NEED_GENERATION = False
            CONFIGS_NEED_GENERATION = False
            PLUGINS_NEED_GENERATION = False
            PRO_PLUGINS_NEED_GENERATION = False
            INSTANCES_NEED_GENERATION = False
            changed_plugins.clear()

            if scheduler_first_start:
                try:
                    ret = API_CLIENT.set_metadata({"scheduler_first_start": False})

                    if ret == "The database is read-only, the changes will not be saved":
                        LOGGER.warning("The database is read-only, the scheduler first start will not be saved")
                    elif ret:
                        LOGGER.error(f"An error occurred when setting the scheduler first start : {ret}")
                except BaseException as e:
                    LOGGER.error(f"Error while setting the scheduler first start : {e}")
                finally:
                    scheduler_first_start = False

            if not HEALTHY_PATH.is_file():
                HEALTHY_PATH.write_text(datetime.now().astimezone().isoformat(), encoding="utf-8")

            APPLYING_CHANGES.clear()
            if not healthcheck_job_run:
                LOGGER.debug("Scheduling healthcheck job ...")
                schedule_every(HEALTHCHECK_INTERVAL).seconds.do(healthcheck_job)
                healthcheck_job_run = True

            # infinite schedule for the jobs
            LOGGER.info("Executing job scheduler ...")
            errors = 0
            _gc_counter = 0
            while RUN and not NEED_RELOAD:
                try:
                    sleep(3 if API_CLIENT.readonly else 1)
                    run_pending()
                    SCHEDULER.run_pending()
                    _gc_counter += 1
                    if _gc_counter >= 60:
                        collect()
                        _gc_counter = 0
                    current_time = datetime.now().astimezone()

                    while DB_LOCK_FILE.is_file() and DB_LOCK_FILE.stat().st_ctime + 30 > current_time.timestamp():
                        LOGGER.debug("Database is locked, waiting for it to be unlocked (timeout: 30s) ...")
                        sleep(1)

                    DB_LOCK_FILE.unlink(missing_ok=True)

                    db_metadata = API_CLIENT.get_metadata()

                    if isinstance(db_metadata, str):
                        raise Exception(f"An error occurred when checking for changes in the database : {db_metadata}")

                    changes = {
                        "pro_plugins_changed": db_metadata["pro_plugins_changed"],
                        "last_pro_plugins_change": db_metadata["last_pro_plugins_change"],
                        "external_plugins_changed": db_metadata["external_plugins_changed"],
                        "last_external_plugins_change": db_metadata["last_external_plugins_change"],
                        "custom_configs_changed": db_metadata["custom_configs_changed"],
                        "last_custom_configs_change": db_metadata["last_custom_configs_change"],
                        "plugins_config_changed": db_metadata["plugins_config_changed"],
                        "instances_changed": db_metadata["instances_changed"],
                        "last_instances_change": db_metadata["last_instances_change"],
                    }

                    if API_CLIENT.readonly and changes == old_changes:
                        continue

                    # check if the plugins have changed since last time
                    if changes["pro_plugins_changed"] and (
                        not API_CLIENT.readonly
                        or not changes["last_pro_plugins_change"]
                        or not old_changes
                        or old_changes["last_pro_plugins_change"] != changes["last_pro_plugins_change"]
                    ):
                        LOGGER.info("Pro plugins changed, generating ...")
                        PRO_PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    if changes["external_plugins_changed"] and (
                        not API_CLIENT.readonly
                        or not changes["last_external_plugins_change"]
                        or not old_changes
                        or old_changes["last_external_plugins_change"] != changes["last_external_plugins_change"]
                    ):
                        LOGGER.info("External plugins changed, generating ...")
                        PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    # check if the custom configs have changed since last time
                    if changes["custom_configs_changed"] and (
                        not API_CLIENT.readonly
                        or not changes["last_custom_configs_change"]
                        or not old_changes
                        or old_changes["last_custom_configs_change"] != changes["last_custom_configs_change"]
                    ):
                        LOGGER.info("Custom configs changed, generating ...")
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # check if the config have changed since last time
                    if changes["plugins_config_changed"] and (
                        not API_CLIENT.readonly
                        or not changes.get("last_plugins_config_change")
                        or not old_changes
                        or old_changes["plugins_config_changed"] != changes["plugins_config_changed"]
                    ):
                        LOGGER.info("Plugins config changed, generating ...")
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True
                        changed_plugins = list(changes["plugins_config_changed"])

                    # check if the instances have changed since last time
                    if changes["instances_changed"] and (
                        not API_CLIENT.readonly
                        or not changes["last_instances_change"]
                        or not old_changes
                        or old_changes["last_instances_change"] != changes["last_instances_change"]
                    ):
                        LOGGER.info("Instances changed, generating ...")
                        INSTANCES_NEED_GENERATION = True
                        PRO_PLUGINS_NEED_GENERATION = True
                        PLUGINS_NEED_GENERATION = True
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    old_changes = changes.copy()
                except BaseException:
                    LOGGER.debug(format_exc())
                    if errors > 5:
                        LOGGER.error(f"An error occurred when executing the scheduler : {format_exc()}")
                        stop(1)
                    errors += 1
                    sleep(5)

            if NEED_RELOAD:
                APPLYING_CHANGES.set()
                LOGGER.debug(f"Changes: {changes}")
                CHANGES.clear()

                if CONFIGS_NEED_GENERATION:
                    CHANGES.append("custom_configs")
                    generate_custom_configs(API_CLIENT.get_custom_configs())

                if PLUGINS_NEED_GENERATION:
                    CHANGES.append("external_plugins")
                    generate_external_plugins()
                    SCHEDULER.update_jobs()

                if PRO_PLUGINS_NEED_GENERATION:
                    CHANGES.append("pro_plugins")
                    generate_external_plugins(PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                if CONFIG_NEED_GENERATION:
                    CHANGES.append("config")
                    old_env = env.copy()
                    env = API_CLIENT.get_config()
                    _strip_bootstrap_env(env)
                    if old_env.get("API_HTTP_PORT", "5000") != env.get("API_HTTP_PORT", "5000") or old_env.get("API_SERVER_NAME", "bwapi") != env.get(
                        "API_SERVER_NAME", "bwapi"
                    ):
                        err = API_CLIENT.update_instances(
                            [
                                {
                                    "hostname": db_instance["hostname"],
                                    "name": db_instance["name"],
                                    "env": {
                                        "API_HTTP_PORT": env.get("API_HTTP_PORT", "5000"),
                                        "API_SERVER_NAME": env.get("API_SERVER_NAME", "bwapi"),
                                    },
                                    "type": db_instance["type"],
                                    "status": db_instance["status"],
                                    "method": db_instance["method"],
                                    "last_seen": db_instance["last_seen"],
                                }
                                for db_instance in API_CLIENT.get_instances()
                            ],
                            method="scheduler",
                        )
                        if err:
                            LOGGER.error(f"Couldn't update instances: {err}")
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

    except:
        LOGGER.error(f"Exception while executing scheduler : {format_exc()}")
        stop(1)
