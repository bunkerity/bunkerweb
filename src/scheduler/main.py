#!/usr/bin/env python3

from argparse import ArgumentParser
from base64 import b64encode
from contextlib import suppress
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from gc import collect
from io import BytesIO
from json import load as json_load
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
from typing import Any, Dict, List, Literal, Optional, Set, Union

BUNKERWEB_PATH = Path(sep, "usr", "share", "bunkerweb")

for deps_path in [BUNKERWEB_PATH.joinpath(*paths).as_posix() for paths in (("deps", "python"), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from schedule import every as schedule_every, run_pending

from common_utils import bytes_hash, dict_to_frozenset, handle_docker_secrets, create_plugin_tar_gz, plugin_tar_exclude  # type: ignore
from env_file import parse_env_file  # type: ignore
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
# Set by the SIGHUP handler, consumed by the main loop: rescan /etc/bunkerweb/configs
# before it gets regenerated from the database.
RELOAD_SCAN_CONFIGS = False
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

# A change flag is now cleared by the job that applies it, not by us on dispatch. So a flag
# still set this long after our last dispatch means that dispatch never landed, and nothing
# else will ever retry it.
APPLY_RETRY_INTERVAL = int(getenv("APPLY_RETRY_INTERVAL", "300") or 300)
HEALTHCHECK_EVENT = Event()
HEALTHCHECK_LOGGER = getLogger("SCHEDULER.HEALTHCHECK")
# Instances currently reporting the loading state, mapped to how many consecutive healthchecks
# have seen them that way. Drives both the retry cadence and the log level: see healthcheck_job.
LOADING_INSTANCES: Dict[str, int] = {}
# Re-push on each of the first few passes (the restart case clears within one), then back off to
# one attempt every N passes. Retrying is not free -- see the comment in healthcheck_job.
LOADING_FAST_RETRIES = 3
LOADING_SLOW_RETRY_EVERY = 20

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


def build_cmd_env() -> Dict[str, str]:
    """Environment handed to the gen/ and save_config subprocesses.

    The logging variables have to travel with it. Without them the child falls back to
    LOG_TYPES=stderr, so on Linux -- where the scheduler runs with LOG_TYPES=file -- every
    error the config saver reports lands in journald while the scheduler log file only keeps
    the one-line "failed" summary, which reads as "no logs at all".
    """
    cmd_env = {
        "PATH": getenv("PATH", ""),
        "PYTHONPATH": getenv("PYTHONPATH", ""),
        "CUSTOM_LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", ""),
        "LOG_LEVEL": getenv("LOG_LEVEL", ""),
        "DATABASE_URI": getenv("DATABASE_URI", ""),
    }

    for key in ("TZ", "LOG_TYPES", "LOG_FILE_PATH", "LOG_SYSLOG_ADDRESS", "LOG_SYSLOG_TAG", "DATABASE_LOG_LEVEL"):
        value = getenv(key)
        if value:
            cmd_env[key] = value

    for key, value in environ.items():
        if "CUSTOM_CONF" in key:
            cmd_env[key] = value

    return cmd_env


def changes_from_metadata(db_metadata: dict) -> dict:
    """The change flags the polling loop compares from one iteration to the next."""
    return {
        "pro_plugins_changed": db_metadata["pro_plugins_changed"],
        "last_pro_plugins_change": db_metadata["last_pro_plugins_change"],
        "external_plugins_changed": db_metadata["external_plugins_changed"],
        "last_external_plugins_change": db_metadata["last_external_plugins_change"],
        "custom_configs_changed": db_metadata["custom_configs_changed"],
        "last_custom_configs_change": db_metadata["last_custom_configs_change"],
        "plugins_config_changed": db_metadata["plugins_config_changed"],
        "instances_changed": db_metadata["instances_changed"],
        "last_instances_change": db_metadata["last_instances_change"],
        "certificates_changed": db_metadata.get("certificates_changed", False),
        "last_certificates_change": db_metadata.get("last_certificates_change"),
    }


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
    global RELOAD_SCAN_CONFIGS

    try:
        if SCHEDULER is not None and RUN:
            if API_CLIENT and API_CLIENT.readonly:
                LOGGER.warning("The database is read-only, no need to save the changes in the configuration as they will not be saved")
                return

            RELOAD_SCAN_CONFIGS = True
            cmd_env = build_cmd_env()

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
    # only_enabled=True: disabled plugins are skipped so they are never written to the
    # filesystem. The removal loop below then deletes any leftover dir of a newly-disabled
    # plugin (absent from `plugins`), removing it from every runtime glob (Configurator,
    # Templator, JobScheduler, Lua loader). Re-enabling re-materializes it from the DB.
    plugins = API_CLIENT.get_plugins(_type="pro" if pro else "external", with_data=True, only_enabled=True)
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
    plugin_dirs: Set[Path] = set()
    ignored_dirs = set()

    for job_cache_file in job_cache_files:
        job_path = Path(sep, "var", "cache", "bunkerweb", job_cache_file["plugin_id"])
        plugin_dirs.add(job_path)
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

    for plugin_path in plugin_dirs:
        if not plugin_path.is_dir():
            continue
        for resource_path in list(plugin_path.rglob("*")):
            if resource_path.as_posix().startswith(tuple(ignored_dirs)):
                continue

            LOGGER.debug(f"Checking if {resource_path} should be removed")
            if resource_path not in plugin_cache_files and resource_path.is_file():
                LOGGER.debug(f"Removing non-cached file {resource_path}")
                resource_path.unlink(missing_ok=True)
                if resource_path.parent.is_dir() and not list(resource_path.parent.iterdir()):
                    LOGGER.debug(f"Removing empty directory {resource_path.parent}")
                    rmtree(resource_path.parent, ignore_errors=True)
                    if resource_path.parent == plugin_path:
                        break
                continue
            elif resource_path.is_dir() and not list(resource_path.iterdir()):
                LOGGER.debug(f"Removing empty directory {resource_path}")
                rmtree(resource_path, ignore_errors=True)
                continue

            desired_perms = S_IRUSR | S_IWUSR | S_IRGRP | S_IXUSR | S_IXGRP  # 0o750
            if resource_path.stat().st_mode & 0o777 != desired_perms:
                resource_path.chmod(desired_perms)


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
    still_loading: Dict[str, int] = {}
    try:
        for db_instance in API_CLIENT.get_instances():
            hostname = db_instance["hostname"]
            previous_status = db_instance.get("status")
            health = None
            try:
                health = API_CLIENT.get_instance_health(hostname)
            except BaseException as e:
                HEALTHCHECK_LOGGER.error(f"Exception while checking instance {hostname}: {e}")

            if health is None:
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

            # An instance that restarted comes back reachable but keeps IS_LOADING=yes until
            # something pushes it a configuration -- and in that state both timer loops return
            # early, so bad-behavior counting, the metrics flush and the sessions cleanup are all
            # silently dead while the instance serves traffic normally. The down → up transition
            # above misses it whenever the restart fits between two healthchecks, which a ~15s
            # container restart regularly does.
            #
            # Worth more than one attempt, because the loading state is not only a telemetry
            # outage: nine core plugins gate their `is_needed()` on it (mtls, authbasic, blacklist,
            # greylist, whitelist, limit, dnsbl, bunkernet, robotstxt), so an instance holding it
            # answers healthchecks as up while enforcing no client certificates, no basic auth, no
            # blacklist and no rate limit. ModSecurity/CRS, antibot and country filtering are
            # unaffected -- they do not read this flag. A dispatch can also report success without
            # landing (a read-only database makes `run_single` return True without queueing
            # anything), so a single attempt is not a guarantee that anything was tried.
            #
            # Bounded, though, because retrying is not cheap: the instance was marked up above, so
            # each dispatch is a full push-configs -- config render, per-instance upload and a
            # reload of the whole fleet. `/health` also fails toward "loading"
            # (`bw/lua/bunkerweb/api.lua`), so a datastore hiccup alone can land here. A few quick
            # attempts cover the restart case; after that one attempt every LOADING_SLOW_RETRY_EVERY
            # passes keeps a genuinely stuck instance from reloading the fleet every 30s forever.
            # Two different states earn a re-push, and they are not equally urgent.
            #   loading      -- the instance has no configuration to enforce, so the nine plugins
            #                   that gate is_needed() on it are inactive. A real exposure.
            #   needs_config -- a restart kept its configuration and is enforcing all of it; it
            #                   just wants a fresh one. Nothing is bypassed, so this is routine.
            if health in ("loading", "needs_config"):
                attempts = LOADING_INSTANCES.get(hostname, 0) + 1
                still_loading[hostname] = attempts
                if attempts <= LOADING_FAST_RETRIES or attempts % LOADING_SLOW_RETRY_EVERY == 0:
                    recovered = True
                    unprotected = health == "loading"
                    if attempts == 1:
                        if unprotected:
                            HEALTHCHECK_LOGGER.warning(
                                f"Instance {hostname} is up but still reports the loading state; will trigger push-configs to re-sync it"
                            )
                        else:
                            HEALTHCHECK_LOGGER.info(
                                f"Instance {hostname} restarted with its configuration preserved and is asking for a fresh one; triggering push-configs"
                            )
                    elif attempts <= LOADING_FAST_RETRIES:
                        HEALTHCHECK_LOGGER.warning(f"Instance {hostname} still reports the {health} state after {attempts} healthchecks; re-pushing")
                    elif unprotected:
                        HEALTHCHECK_LOGGER.error(
                            f"Instance {hostname} has reported the loading state for {attempts} consecutive healthchecks. "
                            "It is serving traffic with mTLS, basic auth, blacklist, greylist and rate limiting inactive; "
                            "re-pushing, but this needs an operator."
                        )
                    else:
                        HEALTHCHECK_LOGGER.error(
                            f"Instance {hostname} has asked for a configuration for {attempts} consecutive healthchecks. "
                            "It is still enforcing the configuration it restarted with, so traffic is protected, but that "
                            "configuration is now stale -- re-pushing, and this needs an operator."
                        )

        if recovered and SCHEDULER is not None:
            try:
                if not SCHEDULER.run_single("push-configs"):
                    HEALTHCHECK_LOGGER.error("Failed to dispatch push-configs after instance recovery")
            except BaseException as e:
                HEALTHCHECK_LOGGER.error(f"Exception dispatching push-configs after recovery: {e}")
    finally:
        # Rebuilt from this pass rather than discarded per instance, so an unreachable or deleted
        # instance drops out on its own and gets a fresh push if it ever comes back loading.
        LOADING_INSTANCES.clear()
        LOADING_INSTANCES.update(still_loading)
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
            dotenv_env = parse_env_file(tmp_variables_path)

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

        SCHEDULER = JobScheduler(LOGGER, api_client=API_CLIENT, lock=SCHEDULER_LOCK)

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

            cmd_env = build_cmd_env()

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
        # Two different failures used to print the same line. `get_metadata()` returns the API
        # error as a STRING (scheduler/api_client.py), so an authentication or transport failure
        # was reported as "Database is not initialized" -- a claim about the database made by a
        # call that never reached it. On the Linux arm that is exactly what a missing API token
        # looks like: the readonly probe fails first, the configuration saver is skipped as if
        # the database were read-only, and this loop then spins for the whole stack-wait window
        # with 60 identical warnings and no mention of the API. Print what actually happened.
        while not ready:
            db_metadata = API_CLIENT.get_metadata()
            if isinstance(db_metadata, str):
                LOGGER.warning(f"Could not read the database metadata from the API, retrying in 5s ... : {db_metadata}")
            elif not db_metadata["is_initialized"]:
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

            cmd_env = build_cmd_env()

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

        def check_configs_changes(*, generate: bool = True) -> bool:
            # Checking if any custom config has been created by the user
            assert API_CLIENT is not None, "API_CLIENT is not defined"
            LOGGER.info("Checking if there are any changes in custom configs ...")
            custom_configs = []
            db_configs = API_CLIENT.get_custom_configs()
            changes = False
            for file in list(CUSTOM_CONFIGS_PATH.rglob("*.conf")):
                if len(file.parts) > len(CUSTOM_CONFIGS_PATH.parts) + 3:
                    LOGGER.warning(f"Custom config file {file} is not in the correct path, skipping ...")
                    continue

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

            if generate:
                generate_custom_configs(API_CLIENT.get_custom_configs())

            return changes

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
                        # base64 so the bytes survive JSON serialization to the API;
                        # the API decodes it back to bytes before storing (see plugins router).
                        "data": b64encode(plugin_content.getvalue()).decode("ascii"),
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
        CERTIFICATES_NEED_DEPLOYMENT = False

        changed_plugins = []
        old_changes = {}
        last_dispatch = None
        healthcheck_job_run = False

        while True:
            task_futures.clear()

            if RUN_JOBS_ONCE:
                # Dispatch all `once` jobs to workers (includes the
                # push-configs job, which renders + ships the NGINX config
                # tree to every BW instance and triggers a reload).
                skipped_plugins = ["misc", "pro"] if FIRST_START else []
                if scheduler_first_start:
                    # backup-data skips itself on the very first start of a fresh install: there
                    # is nothing worth archiving yet, and a backup of the pristine database would
                    # stamp its "already done for this period" cache and suppress the first real
                    # one for a whole day. That guard reads `scheduler_first_start` from the
                    # database -- the flag we clear a few lines below -- and dispatch is
                    # fire-and-forget, so the worker usually reads it already cleared and backs
                    # up anyway. Hold the job back here instead of racing its own guard.
                    skipped_plugins.append("backup")
                if not SCHEDULER.reload(
                    env | {"TZ": getenv("TZ", "UTC"), "RELOAD_MIN_TIMEOUT": str(RELOAD_MIN_TIMEOUT)},
                    changed_plugins=changed_plugins,
                    ignore_plugins=skipped_plugins or None,
                ):
                    LOGGER.error("At least one job in run_once() failed")
                else:
                    if not FIRST_START or SCHEDULER.confirm_worker_liveness():
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

            # The change flags are NOT cleared here any more. This ran in the same iteration that
            # dispatched push-configs, which is fire-and-forget (no result backend), so a push
            # that never completed left the flags clear and nothing ever re-dispatched it --
            # instances kept serving the previous configuration with only a failed job run as
            # evidence. The job that applies a change now acknowledges it, compare-and-set
            # against the watermark it read (Database.clear_applied_changes).
            #
            # What remains is the one thing `checked_changes` does that is not a clear: "config"
            # only latches `first_config_saved` (db_methods/metadata.py), which autoconf's
            # readiness gate blocks on. Never call it with an empty list -- `changes or [...]`
            # in that method turns `[]` into a blanket clear of every flag, including ones the
            # scheduler does not own.
            if CONFIG_NEED_GENERATION:
                try:
                    ret = API_CLIENT.checked_changes(["config"], value=False)
                    if ret:
                        LOGGER.error(f"An error occurred when latching first_config_saved in the database : {ret}")
                except BaseException as e:
                    LOGGER.error(f"Error while latching first_config_saved in the database: {e}")

            last_dispatch = datetime.now().astimezone()

            # Adopt what this pass just acted on as the polling baseline. Saving the
            # configuration raises every change flag, and since 1.7 those flags are cleared by
            # the job that applies them rather than by us on dispatch -- push-configs is
            # asynchronous, so a poll one second later still sees them set. With `old_changes`
            # empty, `not old_changes` reads that as brand new and runs the whole pass again:
            # every once-job dispatched twice on every cold boot, which is how `backup-data`
            # produced a backup the "first start of the scheduler" guard exists to prevent.
            # Nothing this pass applied is lost by adopting it -- it regenerated the
            # configuration and dispatched the jobs.
            # Only when the fleet answered. A pass that ran against an unreachable instance
            # applied nothing -- push-configs had nowhere to push -- so adopting its flags
            # parks the change until the APPLY_RETRY_INTERVAL re-arm, 300s later. Leaving the
            # baseline empty is what the loop did before this seed existed: the next poll reads
            # the still-set flags as new and dispatches again, which is the right thing while
            # an instance is coming back.
            # ponytail: a change landing between the generation and this read is still adopted
            # without having been applied, and only the re-arm below picks it up. Narrow the
            # window with a per-change watermark if that ever shows up in practice -- autoconf,
            # the one writer fast enough to hit it, gates its first write on first_config_saved,
            # which this pass has already latched.
            if not old_changes and success:
                try:
                    dispatched_metadata = API_CLIENT.get_metadata()
                    if not isinstance(dispatched_metadata, str):
                        old_changes = changes_from_metadata(dispatched_metadata)
                except BaseException as e:
                    LOGGER.error(f"Error while reading the change baseline after the first dispatch: {e}")

            FIRST_START = False
            NEED_RELOAD = False
            RUN_JOBS_ONCE = False
            CONFIG_NEED_GENERATION = False
            CONFIGS_NEED_GENERATION = False
            PLUGINS_NEED_GENERATION = False
            PRO_PLUGINS_NEED_GENERATION = False
            CERTIFICATES_NEED_DEPLOYMENT = False
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
                    # SIGHUP: re-read /etc/bunkerweb/configs before the folder gets regenerated
                    # from the database, otherwise a manual edit is reverted on every reload.
                    if RELOAD_SCAN_CONFIGS:
                        RELOAD_SCAN_CONFIGS = False
                        if not API_CLIENT.readonly and check_configs_changes(generate=False):
                            CONFIGS_NEED_GENERATION = True
                            CONFIG_NEED_GENERATION = True
                            NEED_RELOAD = True
                            # Same reason as the read-only branch below: `continue` leaves the
                            # try statement, so the `else` never runs. A rescan that found work
                            # is a clean pass, not a failure.
                            errors = 0
                            continue

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

                    changes = changes_from_metadata(db_metadata)

                    if API_CLIENT.readonly and changes == old_changes:
                        # Reset here too: `continue` leaves the try statement, so the `else`
                        # below never runs, and on a read-only instance this is the branch the
                        # loop takes almost every second.
                        errors = 0
                        continue

                    # check if the plugins have changed since last time
                    if changes["pro_plugins_changed"] and (
                        not changes["last_pro_plugins_change"]
                        or not old_changes
                        or old_changes["last_pro_plugins_change"] != changes["last_pro_plugins_change"]
                    ):
                        LOGGER.info("Pro plugins changed, generating ...")
                        PRO_PLUGINS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True

                    if changes["external_plugins_changed"] and (
                        not changes["last_external_plugins_change"]
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
                        not changes["last_custom_configs_change"]
                        or not old_changes
                        or old_changes["last_custom_configs_change"] != changes["last_custom_configs_change"]
                    ):
                        LOGGER.info("Custom configs changed, generating ...")
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # check if the config have changed since last time
                    # No `not API_CLIENT.readonly` short-circuit: the flags now survive until
                    # the job acknowledges them, so an un-guarded truthiness test would
                    # re-dispatch push-configs and re-run SCHEDULER.reload() every second while
                    # a push is in flight. The dict is {plugin_id: last_config_change}, so a
                    # genuinely new change moves a timestamp and compares unequal.
                    # (A `not changes.get("last_plugins_config_change")` clause used to sit
                    # here; that key is never in the dict built above, so it was always true.)
                    if changes["plugins_config_changed"] and (not old_changes or old_changes["plugins_config_changed"] != changes["plugins_config_changed"]):
                        LOGGER.info("Plugins config changed, generating ...")
                        CONFIG_NEED_GENERATION = True
                        RUN_JOBS_ONCE = True
                        NEED_RELOAD = True
                        changed_plugins = list(changes["plugins_config_changed"])

                    # check if the instances have changed since last time
                    if changes["instances_changed"] and (
                        not changes["last_instances_change"] or not old_changes or old_changes["last_instances_change"] != changes["last_instances_change"]
                    ):
                        LOGGER.info("Instances changed, generating ...")
                        PRO_PLUGINS_NEED_GENERATION = True
                        PLUGINS_NEED_GENERATION = True
                        CONFIGS_NEED_GENERATION = True
                        CONFIG_NEED_GENERATION = True
                        NEED_RELOAD = True

                    # check if the attached certificates have changed since last time. Nothing
                    # needs regenerating here — the material comes from the inventory, not from
                    # the templates — so only the deployment job runs; it pushes the cache and
                    # requests the reload itself when it actually wrote something.
                    if changes["certificates_changed"] and (
                        not changes["last_certificates_change"]
                        or not old_changes
                        or old_changes.get("last_certificates_change") != changes["last_certificates_change"]
                    ):
                        LOGGER.info("Attached certificates changed, deploying ...")
                        CERTIFICATES_NEED_DEPLOYMENT = True
                        NEED_RELOAD = True

                    old_changes = changes.copy()

                    # Re-arm. A flag still set this long after the last dispatch means that
                    # dispatch never landed -- the broker was down so the dispatch was refused,
                    # the worker was killed and the delivery abandoned past its retry limit, the
                    # job failed to render, or it skipped on a lease it could not take. None of
                    # those produce a new timestamp, so the dedup above would sit on them
                    # forever. Forgetting what we last saw makes the next poll treat the pending
                    # flags as new and dispatch again.
                    # ponytail: fixed interval, no backoff -- add one only if flapping shows up.
                    still_pending = bool(changes["plugins_config_changed"]) or any(
                        changes[key]
                        for key in ("pro_plugins_changed", "external_plugins_changed", "custom_configs_changed", "instances_changed", "certificates_changed")
                    )
                    if still_pending and last_dispatch is not None and (datetime.now().astimezone() - last_dispatch).total_seconds() >= APPLY_RETRY_INTERVAL:
                        LOGGER.warning(
                            f"Configuration changes are still pending {APPLY_RETRY_INTERVAL}s after the last dispatch; "
                            "the job that should have applied them never completed. Dispatching again ..."
                        )
                        old_changes = {}
                        last_dispatch = None
                except BaseException:
                    LOGGER.debug(format_exc())
                    if errors > 5:
                        LOGGER.error(f"An error occurred when executing the scheduler : {format_exc()}")
                        stop(1)
                    errors += 1
                    sleep(5)
                else:
                    # Consecutive failures, not failures ever. Without this the counter only
                    # goes up for the life of the process, so six unrelated hiccups spread over
                    # days -- a 429 from the API's own rate limit, a momentary DB lock -- add up
                    # to a scheduler that exits and, with no restart policy on the shipped
                    # stacks, never comes back.
                    errors = 0

            if NEED_RELOAD:
                APPLYING_CHANGES.set()
                LOGGER.debug(f"Changes: {changes}")

                if CERTIFICATES_NEED_DEPLOYMENT:
                    SCHEDULER.run_single("deploy-certificates")

                if CONFIGS_NEED_GENERATION:
                    generate_custom_configs(API_CLIENT.get_custom_configs())

                if PLUGINS_NEED_GENERATION:
                    generate_external_plugins()
                    SCHEDULER.update_jobs()

                if PRO_PLUGINS_NEED_GENERATION:
                    generate_external_plugins(PRO_PLUGINS_PATH)
                    SCHEDULER.update_jobs()

                if CONFIG_NEED_GENERATION:
                    old_env = env.copy()
                    env = API_CLIENT.get_config()
                    _strip_bootstrap_env(env)
                    if old_env.get("API_HTTP_PORT", "5000") != env.get("API_HTTP_PORT", "5000") or old_env.get("API_SERVER_NAME", "bwapi") != env.get(
                        "API_SERVER_NAME", "bwapi"
                    ):
                        err = API_CLIENT.update_instance_endpoints(
                            API_CLIENT.get_instances(),
                            int(env.get("API_HTTP_PORT", "5000")),
                            env.get("API_SERVER_NAME", "bwapi"),
                        )
                        if err:
                            LOGGER.error(f"Couldn't update instances: {err}")
                    tz = getenv("TZ")
                    if tz:
                        env["TZ"] = tz

    except:
        LOGGER.error(f"Exception while executing scheduler : {format_exc()}")
        stop(1)
