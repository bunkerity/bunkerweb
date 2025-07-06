#!/usr/bin/env python3

import os

from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime
from functools import partial
from glob import glob
from importlib.util import module_from_spec, spec_from_file_location
from json import loads
from pathlib import Path
from re import compile as re_compile
from typing import Any, Dict, List, Optional
import schedule
from sys import path as sys_path
from threading import Lock

# Add BunkerWeb dependency paths to Python path for module imports
for deps_path in [os.path.join(os.sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("deps", "python"), ("utils",), ("api",), 
                               ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore

# Import the setup_logger function from bw_logger module and give it the
# shorter alias 'bwlog' for convenience.
from bw_logger import setup_logger as bwlog

from ApiCaller import ApiCaller  # type: ignore

# Check if debug logging is enabled
DEBUG_MODE = os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"


class JobScheduler(ApiCaller):
    # Initialize the job scheduler with database and API connections.
    # Sets up thread pools, regex compilation, and loads initial job list
    # from all available plugins in the system.
    def __init__(
        self,
        logger=None,
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        super().__init__(apis or [])
        
        # Initialize bw_logger module for JobScheduler
        self.logger = (logger or 
                      bwlog(title="SCHEDULER-JOBSCHEDULER: ",
                           log_file_path="/var/log/bunkerweb/scheduler.log"))
        
        if DEBUG_MODE:
            self.logger.debug("Debug mode enabled for JobScheduler")
        
        self.logger.debug("Initializing JobScheduler")
        self.db = db or Database(self.logger)
        # Store only essential environment variables to reduce memory usage
        self.__base_env = os.environ.copy()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__job_reload = False
        
        max_workers = min(8, (os.cpu_count() or 1) * 4)
        self.__executor = ThreadPoolExecutor(max_workers=max_workers)
        
        if DEBUG_MODE:
            self.logger.debug(f"ThreadPoolExecutor initialized with "
                             f"{max_workers} workers")
        
        self.__compiled_regexes = self.__compile_regexes()
        self.__module_paths = set()
        self.__module_paths_lock = Lock()  # Dedicated lock for module paths
        self.update_jobs()

    # Precompile regular expressions for job validation.
    # Creates compiled regex patterns for job name and file path validation
    # to improve performance during job loading and validation.
    def __compile_regexes(self):
        if DEBUG_MODE:
            self.logger.debug("Compiling job validation regexes")
        return {
            "name": re_compile(r"^[\w.-]{1,128}$"),
            "file": re_compile(r"^[\w./-]{1,256}$"),
        }

    # Get current environment variables
    @property
    def env(self) -> Dict[str, Any]:
        return os.environ.copy()

    # Set environment variables.
    # Resets to base environment and applies new variables to ensure
    # clean state for job execution and configuration updates.
    @env.setter
    def env(self, env: Dict[str, Any]):
        if DEBUG_MODE:
            self.logger.debug(f"Updating environment with {len(env)} "
                             f"variables")
        os.environ = self.__base_env.copy()  # Reset to base environment
        os.environ.update(env)  # Update with new environment

    # Update the jobs list from plugins.
    # Rescans all plugin directories and reloads job definitions,
    # useful when plugins are added, removed, or modified.
    def update_jobs(self):
        if DEBUG_MODE:
            self.logger.debug("Updating jobs list")
        self.__jobs = self.__get_jobs()
        total_jobs = sum(len(jobs) for jobs in self.__jobs.values())
        if DEBUG_MODE:
            self.logger.debug(f"Updated jobs list with {total_jobs} "
                             f"total jobs")

    # Discover and load jobs from all plugins.
    # Scans core, external, and pro plugin directories for job definitions
    # and validates them before adding to the scheduler.
    def __get_jobs(self):
        jobs = {}
        plugin_files = []
        plugin_dirs = [
            os.path.join(os.sep, "usr", "share", "bunkerweb", "core", "*", 
                        "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "plugins", "*", 
                        "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "pro", "plugins", "*", 
                        "plugin.json"),
        ]

        for pattern in plugin_dirs:
            found_files = glob(pattern)
            plugin_files.extend(found_files)
            if DEBUG_MODE:
                self.logger.debug(f"Found {len(found_files)} plugin files "
                                 f"in {pattern}")

        if DEBUG_MODE:
            self.logger.debug(f"Total plugin files found: "
                             f"{len(plugin_files)}")

        # Load a single plugin and extract its jobs
        def load_plugin(plugin_file):
            plugin_name = os.path.basename(os.path.dirname(plugin_file))
            if DEBUG_MODE:
                self.logger.debug(f"Loading plugin: {plugin_name} from "
                                 f"{plugin_file}")
            try:
                plugin_data = loads(Path(plugin_file).read_text(
                    encoding="utf-8"))
                plugin_jobs = plugin_data.get("jobs", [])
                if DEBUG_MODE:
                    self.logger.debug(f"Plugin {plugin_name} has "
                                     f"{len(plugin_jobs)} jobs")
                return (plugin_name, 
                       self.__validate_jobs(plugin_jobs, plugin_name, 
                                           plugin_file))
            except FileNotFoundError:
                self.logger.warning(f"Plugin file not found: "
                                    f"{plugin_file}")
            except Exception:
                self.logger.exception(f"Exception while getting jobs for "
                                     f"plugin {plugin_name}")
            return plugin_name, []

        # Load/validate plugins in parallel:
        results = list(self.__executor.map(load_plugin, plugin_files))

        for plugin_name, valid_jobs in results:
            jobs[plugin_name] = valid_jobs
            if valid_jobs and DEBUG_MODE:
                self.logger.debug(f"Plugin {plugin_name} has "
                                 f"{len(valid_jobs)} valid jobs")
        return jobs

    # Validate job definitions from a plugin.
    # Checks required fields, validates formats using regex patterns,
    # and ensures job configuration is safe for execution.
    def __validate_jobs(self, plugin_jobs, plugin_name, plugin_file):
        valid_jobs = []
        for job in plugin_jobs:
            if DEBUG_MODE:
                self.logger.debug(f"Validating job "
                                 f"{job.get('name', 'unnamed')} from "
                                 f"plugin {plugin_name}")
            
            if not all(k in job for k in ("name", "file", "every", "reload")):
                self.logger.warning(f"Missing keys in job definition in "
                                   f"plugin {plugin_name}. Required keys: "
                                   f"name, file, every, reload. Job: {job}")
                continue

            name_valid = self.__compiled_regexes["name"].match(job["name"])
            file_valid = self.__compiled_regexes["file"].match(job["file"])
            every_valid = job["every"] in ("once", "minute", "hour", "day", 
                                          "week")
            reload_valid = isinstance(job.get("reload", False), bool)
            async_valid = isinstance(job.get("async", False), bool)

            if not all((name_valid, file_valid, every_valid, reload_valid, 
                       async_valid)):
                self.logger.warning(f"Invalid job definition in plugin "
                                   f"{plugin_name}. Job: {job}")
                if DEBUG_MODE:
                    self.logger.debug(f"Validation results - name: "
                                     f"{name_valid}, file: {file_valid}, "
                                     f"every: {every_valid}, reload: "
                                     f"{reload_valid}, async: {async_valid}")
                continue

            job["path"] = os.path.dirname(plugin_file)
            valid_jobs.append(job)
            if DEBUG_MODE:
                self.logger.debug(f"Job {job['name']} validated "
                                 f"successfully")
        return valid_jobs

    # Convert string schedule to schedule object.
    # Maps schedule strings like "minute", "hour" to actual schedule objects
    # for use with the schedule library.
    def __str_to_schedule(self, every: str) -> schedule.Job:
        if DEBUG_MODE:
            self.logger.debug(f"Converting schedule string '{every}' to "
                             f"schedule object")
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

    # Reload nginx configuration.
    # Sends reload command to all BunkerWeb instances with appropriate
    # timeout and configuration testing based on environment settings.
    def __reload(self) -> bool:
        self.logger.info("Reloading nginx...")
        reload_min_timeout = self.env.get("RELOAD_MIN_TIMEOUT", "5")

        if not reload_min_timeout.isdigit():
            self.logger.error("RELOAD_MIN_TIMEOUT must be an integer, "
                             "defaulting to 5")
            reload_min_timeout = 5

        if DEBUG_MODE:
            self.logger.debug(f"Using reload timeout: {reload_min_timeout} "
                             f"seconds")
        
        disable_testing = (self.env.get("DISABLE_CONFIGURATION_TESTING", 
                                       "no").lower() == "yes")
        test_param = "no" if disable_testing else "yes"
        
        timeout = max(int(reload_min_timeout), 
                     3 * len(self.env.get("SERVER_NAME", 
                                         "www.example.com").split(" ")))
        
        reload_success = self.send_to_apis(
            "POST",
            f"/reload?test={test_param}",
            timeout=timeout,
        )[0]
        
        if reload_success:
            self.logger.info("Successfully reloaded nginx")
            return True
        self.logger.error("Error while reloading nginx")
        return False

    # Dynamically import and execute a plugin module.
    # Safely loads plugin modules with proper path management and
    # thread-local environment handling for isolated execution.
    def __exec_plugin_module(self, path: str, name: str) -> None:
        if DEBUG_MODE:
            self.logger.debug(f"Loading plugin module: {name} from {path}")
        # Convert to absolute path using Path
        abs_path = Path(path).resolve()
        module_dir = abs_path.parent

        # Validate path exists
        if not abs_path.exists():
            raise FileNotFoundError(f"Plugin path not found: {abs_path}")

        module_dir_str = module_dir.as_posix()
        with self.__module_paths_lock:
            if (module_dir_str not in sys_path and 
                module_dir_str not in self.__module_paths):
                self.__module_paths.add(module_dir.as_posix())
                sys_path.insert(0, module_dir.as_posix())
                if DEBUG_MODE:
                    self.logger.debug(f"Added {module_dir_str} to sys.path")

        spec = spec_from_file_location(name, abs_path.as_posix())
        if spec is None:
            raise ImportError(f"Failed to create module spec for {abs_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        if DEBUG_MODE:
            self.logger.debug(f"Successfully loaded module {name}")

    # Execute a job with error handling and logging.
    # Wraps job execution with comprehensive error handling, timing,
    # and database logging for monitoring and troubleshooting.
    def __job_wrapper(self, path: str, plugin: str, name: str, 
                     file: str) -> int:
        self.logger.info(f"Executing job '{name}' from plugin "
                        f"'{plugin}'...")
        success = True
        ret = -1
        start_date = datetime.now().astimezone()
        try:
            self.__exec_plugin_module(os.path.join(path, "jobs", file), name)
            ret = 1
            if DEBUG_MODE:
                self.logger.debug(f"Job '{name}' from plugin '{plugin}' "
                                 f"executed successfully")
        except SystemExit as e:
            ret = e.code if isinstance(e.code, int) else 1
            if DEBUG_MODE:
                self.logger.debug(f"Job '{name}' from plugin '{plugin}' "
                                 f"exited with code {ret}")
        except Exception:
            success = False
            self.logger.exception(f"Exception while executing job '{name}' "
                                 f"from plugin '{plugin}'")
            with self.__thread_lock:
                self.__job_success = False
        end_date = datetime.now().astimezone()

        if ret == 1:
            if DEBUG_MODE:
                self.logger.debug(f"Job '{name}' requested reload")
            with self.__thread_lock:
                self.__job_reload = True

        if self.__job_success and (ret < 0 or ret >= 2):
            success = False
            self.logger.error(f"Error while executing job '{name}' from "
                             f"plugin '{plugin}'")
            with self.__thread_lock:
                self.__job_success = False

        # Use the executor to manage threads
        self.__executor.submit(self.__add_job_run, name, success, start_date, 
                              end_date)

        return ret

    # Record job execution in database.
    # Logs job execution results with timestamps for monitoring,
    # debugging, and performance analysis of scheduled tasks.
    def __add_job_run(self, name: str, success: bool, start_date: datetime, 
                     end_date: datetime = None):
        if DEBUG_MODE:
            self.logger.debug(f"Adding job run for '{name}' - success: "
                             f"{success}")
        with self.__thread_lock:
            err = self.db.add_job_run(name, success, start_date, end_date)

        if not err:
            self.logger.info(f"Successfully added job run for the job "
                            f"'{name}'")
        else:
            self.logger.warning(f"Failed to add job run for the job "
                               f"'{name}': {err}")

    # Update permissions for cache files and directories.
    # Ensures proper file system permissions on cache files for security
    # and proper access by BunkerWeb components.
    def __update_cache_permissions(self):
        self.logger.info("Updating /var/cache/bunkerweb permissions...")
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
            
            if DEBUG_MODE:
                self.logger.debug(f"Updated permissions: {updated_dirs} "
                                 f"directories, {updated_files} files")
        except Exception:
            self.logger.exception("Error while updating cache permissions")

    # Schedule all jobs according to their frequency.
    # Sets up recurring schedules for jobs that are not one-time only,
    # using the schedule library for timing management.
    def setup(self):
        if DEBUG_MODE:
            self.logger.debug("Setting up job schedules")
        scheduled_count = 0
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if every != "once":
                        if DEBUG_MODE:
                            self.logger.debug(f"Scheduling job '{name}' "
                                             f"from plugin '{plugin}' to "
                                             f"run every {every}")
                        self.__str_to_schedule(every).do(self.__job_wrapper, 
                                                        path, plugin, name, 
                                                        file)
                        scheduled_count += 1
                except Exception:
                    self.logger.exception(f"Exception while scheduling job "
                                         f"'{name}' for plugin '{plugin}'")
        
        if DEBUG_MODE:
            self.logger.debug(f"Scheduled {scheduled_count} jobs")

    # Run all pending scheduled jobs.
    # Executes jobs that are due according to their schedule, handles
    # reload requests, and manages cache synchronization.
    def run_pending(self) -> bool:
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        if not pending_jobs:
            return True

        if DEBUG_MODE:
            self.logger.debug(f"Found {len(pending_jobs)} pending jobs "
                             f"to run")

        if self.try_database_readonly():
            self.logger.error("Database is in read-only mode, pending "
                             "jobs will not be executed")
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
                if DEBUG_MODE:
                    self.logger.debug("Jobs requested reload, sending cache "
                                     "and reloading")
                try:
                    if self.apis:
                        cache_path = os.path.join(os.sep, "var", "cache", 
                                                 "bunkerweb")
                        self.logger.info(f"Sending '{cache_path}' folder...")
                        if not self.send_files(cache_path, "/cache"):
                            success = False
                            self.logger.error(f"Error while sending "
                                             f"'{cache_path}' folder")
                        else:
                            self.logger.info(f"Successfully sent "
                                            f"'{cache_path}' folder")

                    if not self.__reload():
                        success = False
                except Exception:
                    success = False
                    self.logger.exception("Exception while reloading after "
                                         "job scheduling")
                self.__job_reload = False

            if pending_jobs:
                self.logger.info("All scheduled jobs have been executed")

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
                if cleaned_paths and DEBUG_MODE:
                    self.logger.debug(f"Cleaned up {cleaned_paths} module "
                                     f"paths from sys.path")

            self.__update_cache_permissions()

    # Run all jobs once.
    # Executes all jobs immediately, optionally filtering by plugin names
    # or ignoring specific plugins for targeted execution.
    def run_once(self, plugins: Optional[List[str]] = None, 
                ignore_plugins: Optional[List[str]] = None) -> bool:
        if DEBUG_MODE:
            self.logger.debug(f"Running jobs once - plugins: {plugins}, "
                             f"ignore_plugins: {ignore_plugins}")
        
        if self.try_database_readonly():
            self.logger.error("Database is in read-only mode, jobs will "
                             "not be executed")
            return True

        self.__job_success = True
        self.__job_reload = False

        plugins = plugins or []

        try:
            futures = []
            total_jobs = 0
            for plugin, jobs in self.__jobs.items():
                jobs_to_run = []
                if ((plugins and plugin not in plugins) or 
                    (ignore_plugins and plugin in ignore_plugins)):
                    if DEBUG_MODE:
                        self.logger.debug(f"Skipping plugin {plugin}")
                    continue
                for job in jobs:
                    total_jobs += 1
                    if job.get("async", False):
                        if DEBUG_MODE:
                            self.logger.debug(f"Running job {job['name']} "
                                             f"asynchronously")
                        futures.append(
                            self.__executor.submit(self.__job_wrapper, 
                                                  job["path"], plugin, 
                                                  job["name"], job["file"]))
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
                    if DEBUG_MODE:
                        self.logger.debug(f"Running {len(jobs_to_run)} "
                                         f"synchronous jobs for plugin "
                                         f"{plugin}")
                    futures.append(self.__executor.submit(self.__run_jobs, 
                                                         jobs_to_run))

            if DEBUG_MODE:
                self.logger.debug(f"Waiting for {len(futures)} job futures "
                                 f"to complete (total jobs: {total_jobs})")
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
                if cleaned_paths and DEBUG_MODE:
                    self.logger.debug(f"Cleaned up {cleaned_paths} module "
                                     f"paths from sys.path")

            self.__update_cache_permissions()

    # Run a single job by name.
    # Finds and executes a specific job identified by name, useful for
    # manual job execution and testing individual job functionality.
    def run_single(self, job_name: str) -> bool:
        if DEBUG_MODE:
            self.logger.debug(f"Running single job: {job_name}")
        
        if self.try_database_readonly():
            self.logger.error(f"Database is in read-only mode, single job "
                             f"'{job_name}' will not be executed")
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
                        if DEBUG_MODE:
                            self.logger.debug(f"Found job '{job_name}' in "
                                             f"plugin '{plugin}'")
                        break

            if not job_plugin or not job_to_run:
                self.logger.warning(f"Job '{job_name}' not found")
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
                    if cleaned_paths and DEBUG_MODE:
                        self.logger.debug(f"Cleaned up {cleaned_paths} "
                                         f"module paths from sys.path")

                self.__update_cache_permissions()

            return self.__job_success
        finally:
            if self.__lock:
                self.__lock.release()

    # Run a list of jobs sequentially.
    # Executes multiple jobs in order, ensuring proper dependency handling
    # and avoiding race conditions between related jobs.
    def __run_jobs(self, jobs):
        if DEBUG_MODE:
            self.logger.debug(f"Running {len(jobs)} jobs sequentially")
        for job in jobs:
            job()

    # Clear all scheduled jobs.
    # Removes all scheduled jobs from the schedule library, useful for
    # cleanup and scheduler reinitialization.
    def clear(self):
        if DEBUG_MODE:
            self.logger.debug("Clearing all scheduled jobs")
        schedule.clear()

    # Reload scheduler with new environment and plugins.
    # Reinitializes the scheduler with updated configuration, API endpoints,
    # and plugin changes while maintaining proper cleanup and setup.
    def reload(
        self, env: Dict[str, Any], apis: Optional[list] = None, *, 
        changed_plugins: Optional[List[str]] = None, 
        ignore_plugins: Optional[List[str]] = None
    ) -> bool:
        if DEBUG_MODE:
            self.logger.debug(f"Reloading scheduler - changed_plugins: "
                             f"{changed_plugins}, ignore_plugins: "
                             f"{ignore_plugins}")
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
            self.logger.exception("Exception while reloading scheduler")
            return False

    # Check and retry database connection if readonly.
    # Attempts to restore write access to the database or falls back to
    # readonly mode, ensuring continued operation during database issues.
    def try_database_readonly(self, force: bool = False) -> bool:
        if DEBUG_MODE:
            self.logger.debug(f"Checking database readonly state - force: "
                             f"{force}")
        
        if not self.db.readonly:
            try:
                self.db.test_write()
                self.db.readonly = False
                if DEBUG_MODE:
                    self.logger.debug("Database is writable")
                return False
            except Exception:
                self.logger.exception("Database write test failed, setting "
                                     "to readonly")
                self.db.readonly = True
                return True
        elif (not force and self.db.last_connection_retry and 
              (datetime.now().astimezone() - 
               self.db.last_connection_retry).total_seconds() > 30):
            if DEBUG_MODE:
                self.logger.debug("Skipping database retry (last retry was "
                                 "less than 30s ago)")
            return True

        if self.db.database_uri and self.db.readonly:
            if DEBUG_MODE:
                self.logger.debug("Attempting to restore database write "
                                 "access")
            try:
                self.db.retry_connection(pool_timeout=1)
                self.db.retry_connection(log=False)
                self.db.readonly = False
                self.logger.info("The database is no longer read-only, "
                                "defaulting to read-write mode")
            except Exception:
                self.logger.exception("Failed to restore write access, "
                                     "trying readonly connection")
                try:
                    self.db.retry_connection(readonly=True, pool_timeout=1)
                    self.db.retry_connection(readonly=True, log=False)
                    if DEBUG_MODE:
                        self.logger.debug("Connected to database in "
                                         "readonly mode")
                except Exception:
                    self.logger.exception("Failed to connect in readonly "
                                         "mode")
                    if self.db.database_uri_readonly:
                        with suppress(Exception):
                            self.db.retry_connection(fallback=True, 
                                                    pool_timeout=1)
                            self.db.retry_connection(fallback=True, log=False)
                            if DEBUG_MODE:
                                self.logger.debug("Connected to fallback "
                                                 "database")
                self.db.readonly = True

        return self.db.readonly
