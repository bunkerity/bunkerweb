#!/usr/bin/env python3

import os

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from functools import partial
from glob import glob
from importlib.util import module_from_spec, spec_from_file_location
from json import loads
from logging import Logger
from pathlib import Path
from re import compile as re_compile
from typing import Any, Dict, List, Optional
import schedule
from sys import path as sys_path
from threading import Lock

# Add dependencies to sys.path
for deps_path in [os.path.join(os.sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from ApiCaller import ApiCaller  # type: ignore


class JobScheduler(ApiCaller):
    # Initialize the job scheduler with database and API connections
    def __init__(
        self,
        logger: Optional[Logger] = None,
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        super().__init__(apis or [])
        self.__logger = logger or setup_logger("Scheduler", os.getenv("CUSTOM_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")))
        self.__logger.debug("Initializing JobScheduler")
        self.db = db or Database(self.__logger)
        # Store only essential environment variables to reduce memory usage
        self.__base_env = os.environ.copy()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__job_reload = False
        self.__executor = ThreadPoolExecutor(max_workers=min(8, (os.cpu_count() or 1) * 4))
        self.__logger.debug(f"ThreadPoolExecutor initialized with {min(8, (os.cpu_count() or 1) * 4)} workers")
        self.__compiled_regexes = self.__compile_regexes()
        self.__module_paths = set()
        self.__module_paths_lock = Lock()  # Dedicated lock for module paths
        self.update_jobs()

    # Precompile regular expressions for job validation
    def __compile_regexes(self):
        """Precompile regular expressions for job validation."""
        self.__logger.debug("Compiling job validation regexes")
        return {
            "name": re_compile(r"^[\w.-]{1,128}$"),
            "file": re_compile(r"^[\w./-]{1,256}$"),
        }

    # Get current environment variables
    @property
    def env(self) -> Dict[str, Any]:
        return os.environ.copy()

    # Set environment variables
    @env.setter
    def env(self, env: Dict[str, Any]):
        self.__logger.debug(f"Updating environment with {len(env)} variables")
        os.environ = self.__base_env.copy()  # Reset to base environment
        os.environ.update(env)  # Update with new environment

    # Update the jobs list from plugins
    def update_jobs(self):
        self.__logger.debug("Updating jobs list")
        self.__jobs = self.__get_jobs()
        self.__logger.debug(f"Updated jobs list with {sum(len(jobs) for jobs in self.__jobs.values())} total jobs")

    # Discover and load jobs from all plugins
    def __get_jobs(self):
        jobs = {}
        plugin_files = []
        plugin_dirs = [
            os.path.join(os.sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "plugins", "*", "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "pro", "plugins", "*", "plugin.json"),
        ]

        for pattern in plugin_dirs:
            found_files = glob(pattern)
            plugin_files.extend(found_files)
            self.__logger.debug(f"Found {len(found_files)} plugin files in {pattern}")

        self.__logger.debug(f"Total plugin files found: {len(plugin_files)}")

        # Load a single plugin and extract its jobs
        def load_plugin(plugin_file):
            plugin_name = os.path.basename(os.path.dirname(plugin_file))
            self.__logger.debug(f"Loading plugin: {plugin_name} from {plugin_file}")
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                plugin_jobs = plugin_data.get("jobs", [])
                self.__logger.debug(f"Plugin {plugin_name} has {len(plugin_jobs)} jobs")
                return plugin_name, self.__validate_jobs(plugin_jobs, plugin_name, plugin_file)
            except FileNotFoundError:
                self.__logger.warning(f"Plugin file not found: {plugin_file}")
            except Exception:
                self.__logger.exception(f"Exception while getting jobs for plugin {plugin_name}")
            return plugin_name, []

        # Load/validate plugins in parallel:
        results = list(self.__executor.map(load_plugin, plugin_files))

        for plugin_name, valid_jobs in results:
            jobs[plugin_name] = valid_jobs
            if valid_jobs:
                self.__logger.debug(f"Plugin {plugin_name} has {len(valid_jobs)} valid jobs")
        return jobs

    # Validate job definitions from a plugin
    def __validate_jobs(self, plugin_jobs, plugin_name, plugin_file):
        valid_jobs = []
        for job in plugin_jobs:
            self.__logger.debug(f"Validating job {job.get('name', 'unnamed')} from plugin {plugin_name}")
            
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
                self.__logger.debug(f"Validation results - name: {name_valid}, file: {file_valid}, every: {every_valid}, reload: {reload_valid}, async: {async_valid}")
                continue

            job["path"] = os.path.dirname(plugin_file)
            valid_jobs.append(job)
            self.__logger.debug(f"Job {job['name']} validated successfully")
        return valid_jobs

    # Convert string schedule to schedule object
    def __str_to_schedule(self, every: str) -> schedule.Job:
        self.__logger.debug(f"Converting schedule string '{every}' to schedule object")
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

    # Reload nginx configuration
    def __reload(self) -> bool:
        self.__logger.info("Reloading nginx...")
        reload_min_timeout = self.env.get("RELOAD_MIN_TIMEOUT", "5")

        if not reload_min_timeout.isdigit():
            self.__logger.error("RELOAD_MIN_TIMEOUT must be an integer, defaulting to 5")
            reload_min_timeout = 5

        self.__logger.debug(f"Using reload timeout: {reload_min_timeout} seconds")
        reload_success = self.send_to_apis(
            "POST",
            f"/reload?test={'no' if self.env.get('DISABLE_CONFIGURATION_TESTING', 'no').lower() == 'yes' else 'yes'}",
            timeout=max(int(reload_min_timeout), 3 * len(self.env.get("SERVER_NAME", "www.example.com").split(" "))),
        )[0]
        if reload_success:
            self.__logger.info("Successfully reloaded nginx")
            return True
        self.__logger.error("Error while reloading nginx")
        return False

    # Dynamically import and execute a plugin module
    def __exec_plugin_module(self, path: str, name: str) -> None:
        """Dynamically import a plugin module with thread-local environment."""
        self.__logger.debug(f"Loading plugin module: {name} from {path}")
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
                self.__logger.debug(f"Added {module_dir_str} to sys.path")

        spec = spec_from_file_location(name, abs_path.as_posix())
        if spec is None:
            raise ImportError(f"Failed to create module spec for {abs_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        self.__logger.debug(f"Successfully loaded module {name}")

    # Execute a job with error handling and logging
    def __job_wrapper(self, path: str, plugin: str, name: str, file: str) -> int:
        self.__logger.info(f"Executing job '{name}' from plugin '{plugin}'...")
        success = True
        ret = -1
        start_date = datetime.now().astimezone()
        try:
            self.__exec_plugin_module(os.path.join(path, "jobs", file), name)
            ret = 1
            self.__logger.debug(f"Job '{name}' from plugin '{plugin}' executed successfully")
        except SystemExit as e:
            ret = e.code if isinstance(e.code, int) else 1
            self.__logger.debug(f"Job '{name}' from plugin '{plugin}' exited with code {ret}")
        except Exception:
            success = False
            self.__logger.exception(f"Exception while executing job '{name}' from plugin '{plugin}'")
            with self.__thread_lock:
                self.__job_success = False
        end_date = datetime.now().astimezone()

        if ret == 1:
            self.__logger.debug(f"Job '{name}' requested reload")
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

    # Record job execution in database
    def __add_job_run(self, name: str, success: bool, start_date: datetime, end_date: datetime = None):
        self.__logger.debug(f"Adding job run for '{name}' - success: {success}")
        with self.__thread_lock:
            err = self.db.add_job_run(name, success, start_date, end_date)

        if not err:
            self.__logger.info(f"Successfully added job run for the job '{name}'")
        else:
            self.__logger.warning(f"Failed to add job run for the job '{name}': {err}")

    # Update permissions for cache files and directories
    def __update_cache_permissions(self):
        """Update permissions for cache files and directories."""
        self.__logger.info("Updating /var/cache/bunkerweb permissions...")
        cache_path = Path(os.sep, "var", "cache", "bunkerweb")

        DIR_MODE = 0o740
        FILE_MODE = 0o640

        try:
            updated_dirs = 0
            updated_files = 0
            # Process directories and files in a single pass
            for item in cache_path.rglob("*"):
                current_mode = item.stat().st_mode & 0o777
                target_mode = DIR_MODE if item.is_dir() else FILE_MODE

                if current_mode != target_mode:
                    item.chmod(target_mode)
                    if item.is_dir():
                        updated_dirs += 1
                    else:
                        updated_files += 1
            
            self.__logger.debug(f"Updated permissions: {updated_dirs} directories, {updated_files} files")
        except Exception:
            self.__logger.exception("Error while updating cache permissions")

    # Schedule all jobs according to their frequency
    def setup(self):
        self.__logger.debug("Setting up job schedules")
        scheduled_count = 0
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if every != "once":
                        self.__logger.debug(f"Scheduling job '{name}' from plugin '{plugin}' to run every {every}")
                        self.__str_to_schedule(every).do(self.__job_wrapper, path, plugin, name, file)
                        scheduled_count += 1
                except Exception:
                    self.__logger.exception(f"Exception while scheduling job '{name}' for plugin '{plugin}'")
        
        self.__logger.debug(f"Scheduled {scheduled_count} jobs")

    # Run all pending scheduled jobs
    def run_pending(self) -> bool:
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        if not pending_jobs:
            return True

        self.__logger.debug(f"Found {len(pending_jobs)} pending jobs to run")

        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, pending jobs will not be executed")
            return True

        self.__job_success = True
        self.__job_reload = False

        try:
            # Use ThreadPoolExecutor to run jobs
            futures = [self.__executor.submit(job.run) for job in pending_jobs]

            # Wait for all jobs to complete
            for future in futures:
                future.result()

            success = self.__job_success
            self.__job_success = True

            if self.__job_reload:
                self.__logger.debug("Jobs requested reload, sending cache and reloading")
                try:
                    if self.apis:
                        cache_path = os.path.join(os.sep, "var", "cache", "bunkerweb")
                        self.__logger.info(f"Sending '{cache_path}' folder...")
                        if not self.send_files(cache_path, "/cache"):
                            success = False
                            self.__logger.error(f"Error while sending '{cache_path}' folder")
                        else:
                            self.__logger.info(f"Successfully sent '{cache_path}' folder")

                    if not self.__reload():
                        success = False
                except Exception:
                    success = False
                    self.__logger.exception("Exception while reloading after job scheduling")
                self.__job_reload = False

            if pending_jobs:
                self.__logger.info("All scheduled jobs have been executed")

            return success
        finally:
            # Clean up module paths thread-safely
            with self.__module_paths_lock:
                cleaned_paths = 0
                for module_path in self.__module_paths.copy():
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                        cleaned_paths += 1
                    self.__module_paths.remove(module_path)
                if cleaned_paths:
                    self.__logger.debug(f"Cleaned up {cleaned_paths} module paths from sys.path")

            self.__update_cache_permissions()

    # Run all jobs once
    def run_once(self, plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None) -> bool:
        self.__logger.debug(f"Running jobs once - plugins: {plugins}, ignore_plugins: {ignore_plugins}")
        
        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, jobs will not be executed")
            return True

        self.__job_success = True
        self.__job_reload = False

        plugins = plugins or []

        try:
            futures = []
            total_jobs = 0
            for plugin, jobs in self.__jobs.items():
                jobs_to_run = []
                if (plugins and plugin not in plugins) or (ignore_plugins and plugin in ignore_plugins):
                    self.__logger.debug(f"Skipping plugin {plugin}")
                    continue
                for job in jobs:
                    total_jobs += 1
                    if job.get("async", False):
                        self.__logger.debug(f"Running job {job['name']} asynchronously")
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
                    self.__logger.debug(f"Running {len(jobs_to_run)} synchronous jobs for plugin {plugin}")
                    futures.append(self.__executor.submit(self.__run_jobs, jobs_to_run))

            self.__logger.debug(f"Waiting for {len(futures)} job futures to complete (total jobs: {total_jobs})")
            # Wait for all jobs to complete
            for future in futures:
                future.result()

            return self.__job_success
        finally:
            with self.__module_paths_lock:
                cleaned_paths = 0
                for module_path in self.__module_paths.copy():
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                        cleaned_paths += 1
                    self.__module_paths.remove(module_path)
                if cleaned_paths:
                    self.__logger.debug(f"Cleaned up {cleaned_paths} module paths from sys.path")

            self.__update_cache_permissions()

    # Run a single job by name
    def run_single(self, job_name: str) -> bool:
        self.__logger.debug(f"Running single job: {job_name}")
        
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
                        self.__logger.debug(f"Found job '{job_name}' in plugin '{plugin}'")
                        break

            if not job_plugin or not job_to_run:
                self.__logger.warning(f"Job '{job_name}' not found")
                return False

            try:
                self.__job_wrapper(
                    job_to_run["path"],
                    job_plugin,
                    job_to_run["name"],
                    job_to_run["file"],
                )
            finally:
                with self.__module_paths_lock:
                    cleaned_paths = 0
                    for module_path in self.__module_paths.copy():
                        if module_path in sys_path:
                            sys_path.remove(module_path)
                            cleaned_paths += 1
                        self.__module_paths.remove(module_path)
                    if cleaned_paths:
                        self.__logger.debug(f"Cleaned up {cleaned_paths} module paths from sys.path")

                self.__update_cache_permissions()

            return self.__job_success
        finally:
            if self.__lock:
                self.__lock.release()

    # Run a list of jobs sequentially
    def __run_jobs(self, jobs):
        self.__logger.debug(f"Running {len(jobs)} jobs sequentially")
        for job in jobs:
            job()

    # Clear all scheduled jobs
    def clear(self):
        self.__logger.debug("Clearing all scheduled jobs")
        schedule.clear()

    # Reload scheduler with new environment and plugins
    def reload(
        self, env: Dict[str, Any], apis: Optional[list] = None, *, changed_plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None
    ) -> bool:
        self.__logger.debug(f"Reloading scheduler - changed_plugins: {changed_plugins}, ignore_plugins: {ignore_plugins}")
        try:
            os.environ = self.__base_env.copy()
            os.environ.update(env)  # Update with new environment
            super().__init__(apis or self.apis)
            self.clear()
            self.update_jobs()
            success = self.run_once(changed_plugins, ignore_plugins)
            self.setup()
            return success
        except Exception:
            self.__logger.exception("Exception while reloading scheduler")
            return False

    # Check and retry database connection if readonly
    def try_database_readonly(self, force: bool = False) -> bool:
        self.__logger.debug(f"Checking database readonly state - force: {force}")
        
        if not self.db.readonly:
            try:
                self.db.test_write()
                self.db.readonly = False
                self.__logger.debug("Database is writable")
                return False
            except Exception:
                self.__logger.exception("Database write test failed, setting to readonly")
                self.db.readonly = True
                return True
        elif not force and self.db.last_connection_retry and (datetime.now().astimezone() - self.db.last_connection_retry).total_seconds() > 30:
            self.__logger.debug("Skipping database retry (last retry was less than 30s ago)")
            return True

        if self.db.database_uri and self.db.readonly:
            self.__logger.debug("Attempting to restore database write access")
            try:
                self.db.retry_connection(pool_timeout=1)
                self.db.retry_connection(log=False)
                self.db.readonly = False
                self.__logger.info("The database is no longer read-only, defaulting to read-write mode")
            except Exception:
                self.__logger.exception("Failed to restore write access, trying readonly connection")
                try:
                    self.db.retry_connection(readonly=True, pool_timeout=1)
                    self.db.retry_connection(readonly=True, log=False)
                    self.__logger.debug("Connected to database in readonly mode")
                except Exception:
                    self.__logger.exception("Failed to connect in readonly mode")
                    if self.db.database_uri_readonly:
                        with suppress(Exception):
                            self.db.retry_connection(fallback=True, pool_timeout=1)
                            self.db.retry_connection(fallback=True, log=False)
                            self.__logger.debug("Connected to fallback database")
                self.db.readonly = True

        return self.db.readonly
