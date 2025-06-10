#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from functools import partial
from glob import glob
from importlib.util import module_from_spec, spec_from_file_location
from json import loads
from logging import Logger
from os import cpu_count, environ, getenv, sep
from os.path import basename, dirname, join
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import schedule
from sys import path as sys_path
from threading import Lock

# Add dependencies to sys.path
for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from ApiCaller import ApiCaller  # type: ignore


class JobScheduler(ApiCaller):
    def __init__(
        self,
        env: Optional[Dict[str, Any]] = None,
        logger: Optional[Logger] = None,
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        super().__init__(apis or [])
        self.__logger = logger or setup_logger("Scheduler", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))
        self.db = db or Database(self.__logger)
        # Store only essential environment variables to reduce memory usage
        self.__base_env = environ.copy()
        self.__env = env or {}
        self.__cached_combined_env = None
        self.__env_dirty = True
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__env_lock = Lock()  # Dedicated lock for environment operations
        self.__job_success = True
        self.__job_reload = False
        self.__executor = ThreadPoolExecutor(max_workers=min(8, (cpu_count() or 1) * 4))
        self.__compiled_regexes = self.__compile_regexes()
        self.__module_paths = set()
        self.__module_paths_lock = Lock()  # Dedicated lock for module paths
        self.update_jobs()

    def __compile_regexes(self):
        """Precompile regular expressions for job validation."""
        return {
            "name": re.compile(r"^[\w.-]{1,128}$"),
            "file": re.compile(r"^[\w./-]{1,256}$"),
        }

    def _get_combined_env(self) -> Dict[str, Any]:
        """Get cached combined environment variables - thread-safe."""
        with self.__env_lock:
            if self.__cached_combined_env is None or self.__env_dirty:
                self.__cached_combined_env = self.__base_env | self.__env | {"LOG_LEVEL": getenv("CUSTOM_LOG_LEVEL", self.__env.get("LOG_LEVEL", "notice"))}
                self.__env_dirty = False
            return self.__cached_combined_env.copy()  # Return a copy to avoid external mutations

    def _update_env_context(self) -> Dict[str, str]:
        """Update environment context for job execution with minimal overhead - thread-safe.
        Returns the original environment state for restoration."""
        combined_env = self._get_combined_env()
        original_env = {}

        # Store original values for restoration
        for key, value in combined_env.items():
            original_env[key] = environ.get(key)
            if environ.get(key) != str(value):
                environ[key] = str(value)

        return original_env

    def _restore_env_context(self, original_env: Dict[str, str]):
        """Restore original environment context - thread-safe."""
        for key, original_value in original_env.items():
            if original_value is None:
                environ.pop(key, None)
            else:
                environ[key] = original_value

    @property
    def env(self) -> Dict[str, Any]:
        return self.__env

    @env.setter
    def env(self, env: Dict[str, Any]):
        with self.__env_lock:
            self.__env = env
            self.__env_dirty = True

    def update_jobs(self):
        self.__jobs = self.__get_jobs()

    def __get_jobs(self):
        jobs = {}
        plugin_files = []
        plugin_dirs = [
            join(sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json"),
            join(sep, "etc", "bunkerweb", "plugins", "*", "plugin.json"),
            join(sep, "etc", "bunkerweb", "pro", "plugins", "*", "plugin.json"),
        ]

        for pattern in plugin_dirs:
            plugin_files.extend(glob(pattern))

        def load_plugin(plugin_file):
            plugin_name = basename(dirname(plugin_file))
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                plugin_jobs = plugin_data.get("jobs", [])
                return plugin_name, self.__validate_jobs(plugin_jobs, plugin_name, plugin_file)
            except FileNotFoundError:
                self.__logger.warning(f"Plugin file not found: {plugin_file}")
            except Exception as e:
                self.__logger.warning(f"Exception while getting jobs for plugin {plugin_name}: {e}")
            return plugin_name, []

        # Load/validate plugins in parallel:
        results = list(self.__executor.map(load_plugin, plugin_files))

        for plugin_name, valid_jobs in results:
            jobs[plugin_name] = valid_jobs
        return jobs

    def __validate_jobs(self, plugin_jobs, plugin_name, plugin_file):
        valid_jobs = []
        for job in plugin_jobs:
            if not all(k in job for k in ("name", "file", "every", "reload")):
                self.__logger.warning(f"Missing keys in job definition in plugin {plugin_name}. Required keys: name, file, every, reload. Job: {job}")
                continue

            name_valid = self.__compiled_regexes["name"].match(job["name"])
            file_valid = self.__compiled_regexes["file"].match(job["file"])
            every_valid = job["every"] in ("once", "minute", "hour", "day", "week")
            reload_valid = isinstance(job.get("reload", False), bool)
            async_valid = isinstance(job.get("async", False), bool)

            if not all((name_valid, file_valid, every_valid, reload_valid, async_valid)):
                self.__logger.warning(f"Invalid job definition in plugin {plugin_name}. Job: {job}")
                continue

            job["path"] = dirname(plugin_file)
            valid_jobs.append(job)
        return valid_jobs

    def __str_to_schedule(self, every: str) -> schedule.Job:
        schedule_map = {
            "minute": schedule.every().minute,
            "hour": schedule.every().hour,
            "day": schedule.every().day,
            "week": schedule.every().week,
        }
        try:
            return schedule_map[every]
        except KeyError:
            raise ValueError(f"Can't convert string '{every}' to schedule")

    def __reload(self) -> bool:
        self.__logger.info("Reloading nginx...")
        reload_min_timeout = self.__env.get("RELOAD_MIN_TIMEOUT", "5")

        if not reload_min_timeout.isdigit():
            self.__logger.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
            reload_min_timeout = 5

        reload_success = self.send_to_apis(
            "POST",
            f"/reload?test={'no' if self.__env.get('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'}",
            timeout=max(int(reload_min_timeout), 3 * len(self.__env.get("SERVER_NAME", "www.example.com").split(" "))),
        )[0]
        if reload_success:
            self.__logger.info("Successfully reloaded nginx")
            return True
        self.__logger.error("Error while reloading nginx")
        return False

    def __exec_plugin_module(self, path: str, name: str) -> None:
        """Dynamically import a plugin module with thread-local environment."""
        # Convert to absolute path using Path
        abs_path = Path(path).resolve()
        module_dir = abs_path.parent

        # Validate path exists
        if not abs_path.exists():
            raise FileNotFoundError(f"Plugin path not found: {abs_path}")

        module_dir_str = module_dir.as_posix()
        with self.__module_paths_lock:
            if module_dir_str not in sys_path and module_dir_str not in self.__module_paths:
                self.__module_paths.add(module_dir.as_posix())
                sys_path.insert(0, module_dir.as_posix())

        spec = spec_from_file_location(name, abs_path.as_posix())
        if spec is None:
            raise ImportError(f"Failed to create module spec for {abs_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

    def __job_wrapper(self, path: str, plugin: str, name: str, file: str) -> int:
        self.__logger.info(f"Executing job '{name}' from plugin '{plugin}'...")
        success = True
        ret = -1
        start_date = datetime.now().astimezone()
        try:
            self.__exec_plugin_module(join(path, "jobs", file), name)
            ret = 1
        except SystemExit as e:
            ret = e.code if isinstance(e.code, int) else 1
        except Exception as e:
            success = False
            self.__logger.error(f"Exception while executing job '{name}' from plugin '{plugin}': {e}")
            with self.__thread_lock:
                self.__job_success = False
        end_date = datetime.now().astimezone()

        if ret == 1:
            with self.__thread_lock:
                self.__job_reload = True

        if self.__job_success and (ret < 0 or ret >= 2):
            success = False
            self.__logger.error(f"Error while executing job '{name}' from plugin '{plugin}'")
            with self.__thread_lock:
                self.__job_success = False

        # Use the executor to manage threads
        self.__executor.submit(self.__add_job_run, name, success, start_date, end_date)

        return ret

    def __add_job_run(self, name: str, success: bool, start_date: datetime, end_date: datetime = None):
        with self.__thread_lock:
            err = self.db.add_job_run(name, success, start_date, end_date)

        if not err:
            self.__logger.info(f"Successfully added job run for the job '{name}'")
        else:
            self.__logger.warning(f"Failed to add job run for the job '{name}': {err}")

    def __update_cache_permissions(self):
        """Update permissions for cache files and directories."""
        self.__logger.info("Updating /var/cache/bunkerweb permissions...")
        cache_path = Path(sep, "var", "cache", "bunkerweb")

        DIR_MODE = 0o740
        FILE_MODE = 0o640

        try:
            # Process directories and files in a single pass
            for item in cache_path.rglob("*"):
                current_mode = item.stat().st_mode & 0o777
                target_mode = DIR_MODE if item.is_dir() else FILE_MODE

                if current_mode != target_mode:
                    item.chmod(target_mode)
        except Exception as e:
            self.__logger.error(f"Error while updating cache permissions: {e}")

    def setup(self):
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if every != "once":
                        self.__str_to_schedule(every).do(self.__job_wrapper, path, plugin, name, file)
                except Exception as e:
                    self.__logger.error(f"Exception while scheduling job '{name}' for plugin '{plugin}': {e}")

    def run_pending(self) -> bool:
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        if not pending_jobs:
            return True

        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, pending jobs will not be executed")
            return True

        self.__job_success = True
        self.__job_reload = False

        # Update environment efficiently
        original_env = self._update_env_context()

        try:
            # Use ThreadPoolExecutor to run jobs
            futures = [self.__executor.submit(job.run) for job in pending_jobs]

            # Wait for all jobs to complete
            for future in futures:
                future.result()

            success = self.__job_success
            self.__job_success = True

            if self.__job_reload:
                try:
                    if self.apis:
                        cache_path = join(sep, "var", "cache", "bunkerweb")
                        self.__logger.info(f"Sending '{cache_path}' folder...")
                        if not self.send_files(cache_path, "/cache"):
                            success = False
                            self.__logger.error(f"Error while sending '{cache_path}' folder")
                        else:
                            self.__logger.info(f"Successfully sent '{cache_path}' folder")

                    if not self.__reload():
                        success = False
                except Exception as e:
                    success = False
                    self.__logger.error(f"Exception while reloading after job scheduling: {e}")
                self.__job_reload = False

            if pending_jobs:
                self.__logger.info("All scheduled jobs have been executed")

            return success
        finally:
            # Restore environment efficiently
            self._restore_env_context(original_env)

            # Clean up module paths thread-safely
            with self.__module_paths_lock:
                for module_path in self.__module_paths.copy():
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                    self.__module_paths.remove(module_path)

            self.__update_cache_permissions()

    def run_once(self, plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None) -> bool:
        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, jobs will not be executed")
            return True

        self.__job_success = True
        self.__job_reload = False

        plugins = plugins or []

        # Use optimized environment context
        original_env = self._update_env_context()

        try:
            futures = []
            for plugin, jobs in self.__jobs.items():
                jobs_to_run = []
                if (plugins and plugin not in plugins) or (ignore_plugins and plugin in ignore_plugins):
                    continue
                for job in jobs:
                    if job.get("async", False):
                        futures.append(self.__executor.submit(self.__job_wrapper, job["path"], plugin, job["name"], job["file"]))
                        continue

                    jobs_to_run.append(
                        partial(
                            self.__job_wrapper,
                            job["path"],
                            plugin,
                            job["name"],
                            job["file"],
                        )
                    )

                if jobs_to_run:
                    futures.append(self.__executor.submit(self.__run_jobs, jobs_to_run))

            # Wait for all jobs to complete
            for future in futures:
                future.result()

            return self.__job_success
        finally:
            self._restore_env_context(original_env)

            with self.__module_paths_lock:
                for module_path in self.__module_paths.copy():
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                    self.__module_paths.remove(module_path)

            self.__update_cache_permissions()

    def run_single(self, job_name: str) -> bool:
        if self.try_database_readonly():
            self.__logger.error(f"Database is in read-only mode, single job '{job_name}' will not be executed")
            return True

        if self.__lock:
            self.__lock.acquire()

        try:
            job_plugin = ""
            job_to_run = None
            for plugin, jobs in self.__jobs.items():
                for job in jobs:
                    if job["name"] == job_name:
                        job_plugin = plugin
                        job_to_run = job
                        break

            if not job_plugin or not job_to_run:
                self.__logger.warning(f"Job '{job_name}' not found")
                return False

            # Use optimized environment context
            original_env = self._update_env_context()

            try:
                self.__job_wrapper(
                    job_to_run["path"],
                    job_plugin,
                    job_to_run["name"],
                    job_to_run["file"],
                )
            finally:
                self._restore_env_context(original_env)

                with self.__module_paths_lock:
                    for module_path in self.__module_paths.copy():
                        if module_path in sys_path:
                            sys_path.remove(module_path)
                        self.__module_paths.remove(module_path)

                self.__update_cache_permissions()

            return self.__job_success
        finally:
            if self.__lock:
                self.__lock.release()

    def __run_jobs(self, jobs):
        for job in jobs:
            job()

    def clear(self):
        schedule.clear()

    def reload(
        self, env: Dict[str, Any], apis: Optional[list] = None, *, changed_plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None
    ) -> bool:
        try:
            with self.__env_lock:
                self.__env = env
                self.__env_dirty = True
            super().__init__(apis or self.apis)
            self.clear()
            self.update_jobs()
            success = self.run_once(changed_plugins, ignore_plugins)
            self.setup()
            return success
        except Exception as e:
            self.__logger.error(f"Exception while reloading scheduler: {e}")
            return False

    def try_database_readonly(self, force: bool = False) -> bool:
        if not self.db.readonly:
            try:
                self.db.test_write()
                self.db.readonly = False
                return False
            except Exception:
                self.db.readonly = True
                return True
        elif not force and self.db.last_connection_retry and (datetime.now().astimezone() - self.db.last_connection_retry).total_seconds() > 30:
            return True

        if self.db.database_uri and self.db.readonly:
            try:
                self.db.retry_connection(pool_timeout=1)
                self.db.retry_connection(log=False)
                self.db.readonly = False
                self.__logger.info("The database is no longer read-only, defaulting to read-write mode")
            except Exception:
                try:
                    self.db.retry_connection(readonly=True, pool_timeout=1)
                    self.db.retry_connection(readonly=True, log=False)
                except Exception:
                    if self.db.database_uri_readonly:
                        with suppress(Exception):
                            self.db.retry_connection(fallback=True, pool_timeout=1)
                            self.db.retry_connection(fallback=True, log=False)
                self.db.readonly = True

        return self.db.readonly
