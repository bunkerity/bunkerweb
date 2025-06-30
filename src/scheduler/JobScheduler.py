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
import threading

# Add dependencies to sys.path
for deps_path in [os.path.join(os.sep, "usr", "share", "bunkerweb", *paths) 
                  for paths in (("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from ApiCaller import ApiCaller  # type: ignore


# Log debug messages only when LOG_LEVEL environment variable is set to
# "debug"
def debug_log(logger, message):
    if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG":
        logger.debug(f"[DEBUG] {message}")


# Set up logger for the job scheduler with appropriate log level
# Checks both CUSTOM_LOG_LEVEL and LOG_LEVEL environment variables
# Returns configured logger instance for scheduler operations
def _setup_scheduler_logger(logger: Optional[Logger] = None) -> Logger:
    log_level = os.getenv("CUSTOM_LOG_LEVEL", 
                          os.getenv("LOG_LEVEL", "INFO"))
    return logger or setup_logger("Scheduler", log_level)


class JobScheduler(ApiCaller):
    # Initialize the job scheduler with database and API connections.
    # 
    # Creates a threaded job scheduler that can execute plugin jobs on
    # various schedules. Sets up thread pools, regex compilation, and
    # initializes all necessary state tracking variables.
    def __init__(
        self,
        logger: Optional[Logger] = None,
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        super().__init__(apis or [])
        self.__logger = _setup_scheduler_logger(logger)
        
        debug_log(self.__logger, "Starting JobScheduler initialization")
        debug_log(self.__logger, f"Log level set to: {os.getenv('LOG_LEVEL', 'INFO')}")
        debug_log(self.__logger, f"APIs provided: {len(apis or [])}")
        
        self.db = db or Database(self.__logger)
        # Store only essential environment variables to reduce memory usage
        self.__base_env = os.environ.copy()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__job_reload = False
        cpu_count = os.cpu_count() or 1
        max_workers = min(8, cpu_count * 4)
        self.__executor = ThreadPoolExecutor(max_workers=max_workers)
        
        debug_log(self.__logger, f"CPU count: {cpu_count}, "
                                f"calculated max_workers: {max_workers}")
        debug_log(self.__logger, f"Base environment has {len(self.__base_env)} "
                                "variables")
        
        self.__compiled_regexes = self.__compile_regexes()
        self.__module_paths = set()
        # Dedicated lock for module paths
        self.__module_paths_lock = Lock()
        
        debug_log(self.__logger, f"JobScheduler initialized with "
                                f"max_workers={max_workers}")
        debug_log(self.__logger, "Starting job discovery and validation")
        
        self.update_jobs()
        
        debug_log(self.__logger, "JobScheduler initialization complete")

    # Precompile regular expressions for job validation.
    # 
    # Creates compiled regex patterns for validating job names and file
    # paths to ensure they meet security and naming requirements.
    # Job names must be 1-128 chars of word chars, dots, or dashes.
    # File paths must be 1-256 chars of word chars, dots, slashes, dashes.
    def __compile_regexes(self):
        debug_log(self.__logger, "Compiling regex patterns for job validation")
        debug_log(self.__logger, "Name pattern: ^[\\w.-]{1,128}$ (word chars, "
                                "dots, dashes, 1-128 length)")
        debug_log(self.__logger, "File pattern: ^[\\w./-]{1,256}$ (word chars, "
                                "dots, slashes, dashes, 1-256 length)")
        
        patterns = {
            "name": re_compile(r"^[\w.-]{1,128}$"),
            "file": re_compile(r"^[\w./-]{1,256}$"),
        }
        
        debug_log(self.__logger, f"Successfully compiled {len(patterns)} "
                                "regex patterns")
        
        return patterns

    @property
    # Get a copy of the current environment variables.
    # 
    # Returns a complete copy of the current process environment to
    # prevent external modification of the scheduler's environment state.
    def env(self) -> Dict[str, Any]:
        env_copy = os.environ.copy()
        debug_log(self.__logger, f"Returning environment copy with "
                                f"{len(env_copy)} variables")
        return env_copy

    @env.setter
    # Set environment variables, resetting to base first.
    # 
    # Resets the environment to the base state captured during
    # initialization, then applies the provided environment updates.
    # This ensures clean environment state for job execution.
    def env(self, env: Dict[str, Any]):
        debug_log(self.__logger, f"Setting environment with {len(env)} "
                                "variables")
        debug_log(self.__logger, f"Base environment has "
                                f"{len(self.__base_env)} variables")
        # Log any new variables being added
        new_vars = set(env.keys()) - set(self.__base_env.keys())
        if new_vars:
            debug_log(self.__logger, f"Adding {len(new_vars)} new variables: "
                                    f"{', '.join(sorted(new_vars))}")
        
        os.environ = self.__base_env.copy()  # Reset to base environment
        os.environ.update(env)  # Update with new environment
        
        debug_log(self.__logger, f"Environment updated, now has "
                                f"{len(os.environ)} total variables")

    # Refresh the job definitions from plugin files.
    # 
    # Scans all plugin directories, loads plugin.json files, and
    # validates job definitions. This method rebuilds the complete
    # job registry from scratch, ensuring all jobs are current and valid.
    # Called during initialization and when configuration changes.
    def update_jobs(self):
        debug_log(self.__logger, "Starting job definition update from plugins")
        debug_log(self.__logger, "Clearing existing job cache")
        
        start_time = datetime.now()
        self.__jobs = self.__get_jobs()
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        total_jobs = sum(len(jobs) for jobs in self.__jobs.values())
        debug_log(self.__logger, f"Job update completed in {duration:.3f}s")
        debug_log(self.__logger, f"Loaded {total_jobs} jobs from "
                                f"{len(self.__jobs)} plugins")
        for plugin_name, jobs in self.__jobs.items():
            if jobs:
                debug_log(self.__logger, f"Plugin '{plugin_name}': "
                                        f"{len(jobs)} jobs")

    # Load and validate jobs from all plugin directories.
    # 
    # Searches predefined plugin directories for plugin.json files,
    # loads job definitions in parallel using thread pool, and
    # validates each job against the required schema. Handles
    # file loading errors gracefully and logs warnings for issues.
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

        debug_log(self.__logger, f"Scanning {len(plugin_dirs)} plugin "
                                "directories:")
        for i, dir_pattern in enumerate(plugin_dirs, 1):
            debug_log(self.__logger, f"  {i}. {dir_pattern}")

        for pattern in plugin_dirs:
            found_files = glob(pattern)
            plugin_files.extend(found_files)
            debug_log(self.__logger, f"Pattern '{pattern}' found "
                                    f"{len(found_files)} files")

        debug_log(self.__logger, f"Found {len(plugin_files)} total plugin "
                                "files to process")
        if plugin_files:
            debug_log(self.__logger, "Plugin files found:")
            for i, pf in enumerate(plugin_files, 1):
                debug_log(self.__logger, f"  {i}. {pf}")

        # Load and validate a single plugin file.
        # 
        # Reads the plugin.json file, extracts job definitions,
        # and validates them against the schema requirements.
        def load_plugin(plugin_file):
            plugin_name = os.path.basename(os.path.dirname(plugin_file))
            
            debug_log(self.__logger, f"Processing plugin file: {plugin_file}")
            debug_log(self.__logger, f"Plugin name: {plugin_name}")
            
            try:
                file_content = Path(plugin_file).read_text(encoding="utf-8")
                
                debug_log(self.__logger, f"Read {len(file_content)} characters "
                                        f"from {plugin_file}")
                
                plugin_data = loads(file_content)
                plugin_jobs = plugin_data.get("jobs", [])
                
                debug_log(self.__logger, f"Loaded plugin data with "
                                        f"{len(plugin_jobs)} job definitions")
                if "jobs" not in plugin_data:
                    debug_log(self.__logger, f"No 'jobs' key found in "
                                            f"{plugin_file}")
                else:
                    debug_log(self.__logger, f"Jobs key found with "
                                            f"{len(plugin_jobs)} entries")
                
                validated_jobs = self.__validate_jobs(
                    plugin_jobs, plugin_name, plugin_file)
                
                debug_log(self.__logger, f"Plugin {plugin_name}: "
                                        f"{len(plugin_jobs)} raw jobs -> "
                                        f"{len(validated_jobs)} valid jobs")
                
                return plugin_name, validated_jobs
                
            except FileNotFoundError:
                self.__logger.warning(f"Plugin file not found: "
                                    f"{plugin_file}")
                debug_log(self.__logger, f"FileNotFoundError for {plugin_file}")
            except Exception as e:
                self.__logger.warning(f"Exception while getting jobs for "
                                    f"plugin {plugin_name}: {e}")
                debug_log(self.__logger, f"Exception type: {type(e).__name__}")
                debug_log(self.__logger, f"Exception details: {str(e)}")
            
            return plugin_name, []

        # Load/validate plugins in parallel:
        debug_log(self.__logger, f"Starting parallel plugin processing with "
                                f"ThreadPoolExecutor")
        
        results = list(self.__executor.map(load_plugin, plugin_files))

        debug_log(self.__logger, f"Parallel processing completed, got "
                                f"{len(results)} results")

        for plugin_name, valid_jobs in results:
            jobs[plugin_name] = valid_jobs
            if valid_jobs:
                debug_log(self.__logger, f"Added {len(valid_jobs)} jobs for "
                                        f"plugin '{plugin_name}'")
            else:
                debug_log(self.__logger, f"No valid jobs for plugin "
                                        f"'{plugin_name}'")
        
        total_jobs = sum(len(job_list) for job_list in jobs.values())
        debug_log(self.__logger, f"Final result: {total_jobs} total valid "
                                f"jobs from {len(jobs)} plugins")
        plugins_with_jobs = sum(1 for job_list in jobs.values() 
                                if job_list)
        debug_log(self.__logger, f"{plugins_with_jobs} plugins have jobs, "
                                f"{len(jobs) - plugins_with_jobs} plugins "
                                "have no jobs")
        
        return jobs

    # Validate job definitions according to required schema.
    # 
    # Checks each job definition for required fields (name, file, every,
    # reload) and validates their format and values. Job names and files
    # must match regex patterns, schedule values must be valid, and
    # boolean flags must be proper booleans.
    def __validate_jobs(self, plugin_jobs, plugin_name, plugin_file):
        valid_jobs = []
        required_keys = ("name", "file", "every", "reload")
        valid_schedules = ("once", "minute", "hour", "day", "week")
        
        debug_log(self.__logger, f"Validating {len(plugin_jobs)} jobs for "
                                f"plugin '{plugin_name}'")
        debug_log(self.__logger, f"Required keys: {', '.join(required_keys)}")
        debug_log(self.__logger, f"Valid schedules: "
                                f"{', '.join(valid_schedules)}")
        
        for i, job in enumerate(plugin_jobs):
            debug_log(self.__logger, f"Validating job {i+1}/{len(plugin_jobs)}: "
                                    f"{job.get('name', '<no name>')}")
            
            # Check required keys
            missing_keys = [k for k in required_keys if k not in job]
            if missing_keys:
                self.__logger.warning(f"Missing keys in job definition in "
                                    f"plugin {plugin_name}. Required keys: "
                                    f"{', '.join(required_keys)}. "
                                    f"Missing: {', '.join(missing_keys)}. "
                                    f"Job: {job}")
                debug_log(self.__logger, f"Job {i+1} failed: missing keys")
                continue

            # Validate individual fields
            name_valid = self.__compiled_regexes["name"].match(job["name"])
            file_valid = self.__compiled_regexes["file"].match(job["file"])
            every_valid = job["every"] in valid_schedules
            reload_valid = isinstance(job.get("reload", False), bool)
            async_valid = isinstance(job.get("async", False), bool)

            debug_log(self.__logger, f"Job '{job['name']}' validation:")
            debug_log(self.__logger, f"  name_valid: {bool(name_valid)} "
                                    f"('{job['name']}')")
            debug_log(self.__logger, f"  file_valid: {bool(file_valid)} "
                                    f"('{job['file']}')")
            debug_log(self.__logger, f"  every_valid: {every_valid} "
                                    f"('{job['every']}')")
            debug_log(self.__logger, f"  reload_valid: {reload_valid} "
                                    f"({job.get('reload', False)})")
            debug_log(self.__logger, f"  async_valid: {async_valid} "
                                    f"({job.get('async', False)})")

            if not all((name_valid, file_valid, every_valid, reload_valid, 
                       async_valid)):
                validation_details = []
                if not name_valid:
                    validation_details.append(f"invalid name '{job['name']}'")
                if not file_valid:
                    validation_details.append(f"invalid file '{job['file']}'")
                if not every_valid:
                    validation_details.append(
                        f"invalid schedule '{job['every']}'")
                if not reload_valid:
                    validation_details.append(
                        f"invalid reload flag {job.get('reload')}")
                if not async_valid:
                    validation_details.append(
                        f"invalid async flag {job.get('async')}")
                
                self.__logger.warning(f"Invalid job definition in plugin "
                                    f"{plugin_name}. Issues: "
                                    f"{', '.join(validation_details)}. "
                                    f"Job: {job}")
                debug_log(self.__logger, f"Job {i+1} failed validation: "
                                        f"{', '.join(validation_details)}")
                continue

            # Add plugin path and accept the job
            job["path"] = os.path.dirname(plugin_file)
            valid_jobs.append(job)
            
            debug_log(self.__logger, f"Job '{job['name']}' validated "
                                    f"successfully")
            debug_log(self.__logger, f"  path: {job['path']}")
            debug_log(self.__logger, f"  schedule: {job['every']}")
            debug_log(self.__logger, f"  reload: {job.get('reload', False)}")
            debug_log(self.__logger, f"  async: {job.get('async', False)}")
        
        debug_log(self.__logger, f"Plugin '{plugin_name}' validation "
                                f"complete: {len(valid_jobs)}/{len(plugin_jobs)} "
                                "jobs valid")
        
        return valid_jobs

    # Convert frequency string to schedule object.
    # 
    # Maps string representations of scheduling frequencies to the
    # corresponding schedule.Job objects used by the schedule library.
    # Supports minute, hour, day, and week intervals.
    def __str_to_schedule(self, every: str) -> schedule.Job:
        schedule_map = {
            "minute": schedule.every().minute,
            "hour": schedule.every().hour,
            "day": schedule.every().day,
            "week": schedule.every().week,
        }
        
        debug_log(self.__logger, f"Converting schedule string '{every}' to "
                                "schedule object")
        if every in schedule_map:
            debug_log(self.__logger, f"Found mapping for '{every}'")
        else:
            debug_log(self.__logger, f"No mapping found for '{every}', "
                                    f"available: {list(schedule_map.keys())}")
        
        try:
            schedule_obj = schedule_map[every]
            debug_log(self.__logger, f"Successfully created schedule object "
                                    f"for '{every}'")
            return schedule_obj
        except KeyError:
            error_msg = f"Can't convert string '{every}' to schedule"
            debug_log(self.__logger, f"KeyError: {error_msg}")
            raise ValueError(error_msg)

    # Reload nginx configuration via API.
    # 
    # Sends a reload request to connected APIs to refresh nginx
    # configuration. Calculates appropriate timeout based on server
    # names and minimum timeout settings. Handles configuration
    # testing based on environment settings.
    def __reload(self) -> bool:
        self.__logger.info("Reloading nginx...")
        reload_min_timeout = self.env.get("RELOAD_MIN_TIMEOUT", "5")

        debug_log(self.__logger, f"Raw RELOAD_MIN_TIMEOUT: '{reload_min_timeout}'")

        if not reload_min_timeout.isdigit():
            self.__logger.error("RELOAD_MIN_TIMEOUT must be an integer, "
                              "defaulting to 5")
            debug_log(self.__logger, f"Invalid timeout value "
                                    f"'{reload_min_timeout}', using 5")
            reload_min_timeout = 5

        disable_config_test = (self.env.get('DISABLE_CONFIGURATION_TESTING', 
                                          'no').lower() == 'yes')
        test_param = 'no' if disable_config_test else 'yes'
        server_names = self.env.get("SERVER_NAME", "www.example.com")
        server_name_list = server_names.split(" ")
        timeout_calc = max(int(reload_min_timeout), 
                          3 * len(server_name_list))
        
        debug_log(self.__logger, f"Configuration testing disabled: "
                                f"{disable_config_test}")
        debug_log(self.__logger, f"Test parameter: {test_param}")
        debug_log(self.__logger, f"Server names: '{server_names}' "
                                f"({len(server_name_list)} servers)")
        debug_log(self.__logger, f"Timeout calculation: max({reload_min_timeout}, "
                                f"3 * {len(server_name_list)}) = {timeout_calc}")
        debug_log(self.__logger, f"Sending reload request to {len(self.apis)} "
                                "APIs")

        reload_url = f"/reload?test={test_param}"
        debug_log(self.__logger, f"Reload URL: {reload_url}")

        reload_success = self.send_to_apis(
            "POST",
            reload_url,
            timeout=timeout_calc,
        )[0]
        
        debug_log(self.__logger, f"API response success: {reload_success}")
        
        if reload_success:
            self.__logger.info("Successfully reloaded nginx")
            return True
        
        self.__logger.error("Error while reloading nginx")
        debug_log(self.__logger, "Reload failed - API returned failure")
        return False

    # Dynamically import and execute a plugin module.
    # 
    # Loads a Python module from the specified path, adds its directory
    # to sys.path for imports, and executes it. Handles path resolution,
    # module spec creation, and maintains thread-safe module path tracking.
    def __exec_plugin_module(self, path: str, name: str) -> None:
        # Convert to absolute path using Path
        abs_path = Path(path).resolve()
        module_dir = abs_path.parent

        debug_log(self.__logger, f"Executing plugin module '{name}'")
        debug_log(self.__logger, f"Module path: {path}")
        debug_log(self.__logger, f"Absolute path: {abs_path}")
        debug_log(self.__logger, f"Module directory: {module_dir}")

        # Validate path exists
        if not abs_path.exists():
            error_msg = f"Plugin path not found: {abs_path}"
            debug_log(self.__logger, f"Path validation failed: {error_msg}")
            raise FileNotFoundError(error_msg)

        debug_log(self.__logger, f"Path validation successful")

        module_dir_str = module_dir.as_posix()
        
        # Thread-safe module path management
        with self.__module_paths_lock:
            path_already_added = (module_dir_str in sys_path or 
                                module_dir_str in self.__module_paths)
            
            debug_log(self.__logger, f"Module dir string: {module_dir_str}")
            debug_log(self.__logger, f"Already in sys.path: "
                                    f"{module_dir_str in sys_path}")
            debug_log(self.__logger, f"Already tracked: "
                                    f"{module_dir_str in self.__module_paths}")
            debug_log(self.__logger, f"Current sys.path length: "
                                    f"{len(sys_path)}")
            debug_log(self.__logger, f"Tracked paths: "
                                    f"{len(self.__module_paths)}")
            
            if not path_already_added:
                self.__module_paths.add(module_dir.as_posix())
                sys_path.insert(0, module_dir.as_posix())
                debug_log(self.__logger, f"Added module directory to sys.path "
                                        f"at position 0")
                debug_log(self.__logger, f"sys.path now has {len(sys_path)} "
                                        "entries")
            else:
                debug_log(self.__logger, "Module directory already in path, "
                                        "skipping addition")

        # Create and execute module
        debug_log(self.__logger, f"Creating module spec for '{name}' "
                                f"from {abs_path.as_posix()}")
        
        spec = spec_from_file_location(name, abs_path.as_posix())
        if spec is None:
            error_msg = f"Failed to create module spec for {abs_path}"
            debug_log(self.__logger, f"Spec creation failed: {error_msg}")
            raise ImportError(error_msg)

        debug_log(self.__logger, f"Module spec created successfully")
        debug_log(self.__logger, f"Spec name: {spec.name}")
        debug_log(self.__logger, f"Spec origin: {spec.origin}")
        debug_log(self.__logger, f"Creating module from spec")

        module = module_from_spec(spec)
        
        debug_log(self.__logger, f"Module created, executing...")
        
        spec.loader.exec_module(module)
        
        debug_log(self.__logger, f"Module '{name}' executed successfully")

    # Execute a single job and handle its lifecycle.
    # 
    # Wraps job execution with timing, error handling, and state tracking.
    # Records start/end times, manages return codes, handles exceptions,
    # and updates global job state flags. Manages database logging of
    # job execution results.
    def __job_wrapper(self, path: str, plugin: str, name: str, 
                     file: str) -> int:
        self.__logger.info(f"Executing job '{name}' from plugin "
                         f"'{plugin}'...")
        success = True
        ret = -1
        start_date = datetime.now().astimezone()
        
        debug_log(self.__logger, f"Job execution started:")
        debug_log(self.__logger, f"  Job name: {name}")
        debug_log(self.__logger, f"  Plugin: {plugin}")
        debug_log(self.__logger, f"  File: {file}")
        debug_log(self.__logger, f"  Path: {path}")
        debug_log(self.__logger, f"  Start time: {start_date}")
        debug_log(self.__logger, f"  Thread ID: {threading.current_thread().ident}")
        debug_log(self.__logger, f"  Process ID: {os.getpid()}")
        
        job_file_path = os.path.join(path, "jobs", file)
        debug_log(self.__logger, f"Full job file path: {job_file_path}")
        debug_log(self.__logger, f"Job file exists: {os.path.exists(job_file_path)}")
        
        try:
            debug_log(self.__logger, f"Calling __exec_plugin_module")
            
            self.__exec_plugin_module(job_file_path, name)
            ret = 1
            
            debug_log(self.__logger, f"Job completed normally, return code: {ret}")
                
        except SystemExit as e:
            ret = e.code if isinstance(e.code, int) else 1
            debug_log(self.__logger, f"Job exited with SystemExit")
            debug_log(self.__logger, f"  Exit code type: {type(e.code)}")
            debug_log(self.__logger, f"  Exit code value: {e.code}")
            debug_log(self.__logger, f"  Processed return code: {ret}")
        except Exception as e:
            success = False
            self.__logger.error(f"Exception while executing job '{name}' "
                              f"from plugin '{plugin}': {e}")
            debug_log(self.__logger, f"Job execution exception:")
            debug_log(self.__logger, f"  Exception type: {type(e).__name__}")
            debug_log(self.__logger, f"  Exception message: {str(e)}")
            import traceback
            debug_log(self.__logger, f"  Traceback: {traceback.format_exc()}")
            
            with self.__thread_lock:
                self.__job_success = False
                debug_log(self.__logger, f"Set global job_success to False")
        
        end_date = datetime.now().astimezone()
        execution_time = (end_date - start_date).total_seconds()

        debug_log(self.__logger, f"Job execution completed:")
        debug_log(self.__logger, f"  End time: {end_date}")
        debug_log(self.__logger, f"  Execution time: {execution_time:.3f} seconds")
        debug_log(self.__logger, f"  Return code: {ret}")
        debug_log(self.__logger, f"  Success flag: {success}")

        # Handle reload flag
        if ret == 1:
            with self.__thread_lock:
                old_reload_state = self.__job_reload
                self.__job_reload = True
                debug_log(self.__logger, f"Job returned 1, setting reload flag")
                debug_log(self.__logger, f"  Previous reload state: {old_reload_state}")
                debug_log(self.__logger, f"  New reload state: True")

        # Handle error return codes
        if self.__job_success and (ret < 0 or ret >= 2):
            success = False
            self.__logger.error(f"Error while executing job '{name}' "
                              f"from plugin '{plugin}'")
            debug_log(self.__logger, f"Job failed due to return code {ret}")
            debug_log(self.__logger, f"  Return code < 0: {ret < 0}")
            debug_log(self.__logger, f"  Return code >= 2: {ret >= 2}")
            
            with self.__thread_lock:
                self.__job_success = False
                debug_log(self.__logger, f"Set global job_success to False "
                                        "due to bad return code")

        debug_log(self.__logger, f"Job {name} completed in {execution_time:.2f}s "
                                f"with success={success}")
        debug_log(self.__logger, f"Submitting job run record to database")

        # Use the executor to manage threads
        self.__executor.submit(self.__add_job_run, name, success, 
                             start_date, end_date)

        debug_log(self.__logger, f"Job wrapper returning: {ret}")

        return ret

    # Record job execution details in the database.
    # 
    # Stores job execution metadata including timing, success status,
    # and job identification in the database for tracking and auditing
    # purposes. Handles database errors gracefully and logs results.
    def __add_job_run(self, name: str, success: bool, start_date: datetime, 
                     end_date: datetime):
        duration = (end_date - start_date).total_seconds()
        debug_log(self.__logger, f"Adding job run record:")
        debug_log(self.__logger, f"  Job name: {name}")
        debug_log(self.__logger, f"  Success: {success}")
        debug_log(self.__logger, f"  Start: {start_date}")
        debug_log(self.__logger, f"  End: {end_date}")
        debug_log(self.__logger, f"  Duration: {duration:.3f} seconds")
        debug_log(self.__logger, f"  Thread ID: {threading.current_thread().ident}")
        
        with self.__thread_lock:
            debug_log(self.__logger, f"Acquired thread lock, calling db.add_job_run")
            
            err = self.db.add_job_run(name, success, start_date, end_date)
            
            debug_log(self.__logger, f"Database call completed")
            debug_log(self.__logger, f"  Error result: {err}")
            debug_log(self.__logger, f"  Error type: {type(err)}")

        if not err:
            self.__logger.info(f"Successfully added job run for the job "
                             f"'{name}'")
            debug_log(self.__logger, f"Job run record saved successfully")
        else:
            self.__logger.warning(f"Failed to add job run for the job "
                                f"'{name}': {err}")
            debug_log(self.__logger, f"Job run record save failed")
            debug_log(self.__logger, f"  Error details: {str(err)}")
            debug_log(self.__logger, f"  Database readonly: {getattr(self.db, 'readonly', 'unknown')}")

    # Update permissions for cache files and directories.
    # 
    # Recursively traverses the BunkerWeb cache directory and sets
    # appropriate permissions on all files and directories. Directories
    # get 740 (rwxr-----) and files get 640 (rw-r-----) permissions
    # for security. Handles permission errors gracefully.
    def __update_cache_permissions(self):
        self.__logger.info("Updating /var/cache/bunkerweb permissions...")
        cache_path = Path(os.sep, "var", "cache", "bunkerweb")

        DIR_MODE = 0o740
        FILE_MODE = 0o640

        debug_log(self.__logger, f"Cache permissions update started:")
        debug_log(self.__logger, f"  Cache path: {cache_path}")
        debug_log(self.__logger, f"  Cache path exists: {cache_path.exists()}")
        if cache_path.exists():
            debug_log(self.__logger, f"  Cache path is dir: {cache_path.is_dir()}")
        debug_log(self.__logger, f"  Directory mode: {oct(DIR_MODE)} (rwxr-----)")
        debug_log(self.__logger, f"  File mode: {oct(FILE_MODE)} (rw-r-----)")

        if not cache_path.exists():
            debug_log(self.__logger, f"Cache path does not exist, skipping permissions update")
            return

        try:
            items_processed = 0
            items_updated = 0
            dirs_processed = 0
            files_processed = 0
            
            # Process directories and files in a single pass
            for item in cache_path.rglob("*"):
                items_processed += 1
                current_mode = item.stat().st_mode & 0o777
                target_mode = DIR_MODE if item.is_dir() else FILE_MODE
                
                if item.is_dir():
                    dirs_processed += 1
                else:
                    files_processed += 1

                if items_processed <= 10:
                    debug_log(self.__logger, f"Processing item {items_processed}: {item}")
                    debug_log(self.__logger, f"  Is directory: {item.is_dir()}")
                    debug_log(self.__logger, f"  Current mode: {oct(current_mode)}")
                    debug_log(self.__logger, f"  Target mode: {oct(target_mode)}")
                    debug_log(self.__logger, f"  Needs update: {current_mode != target_mode}")

                if current_mode != target_mode:
                    item.chmod(target_mode)
                    items_updated += 1
                    item_type = "directory" if item.is_dir() else "file"
                    debug_log(self.__logger, f"Updated {item_type} permissions: "
                                            f"{item}: {oct(current_mode)} -> "
                                            f"{oct(target_mode)}")

            debug_log(self.__logger, f"Cache permissions update completed:")
            debug_log(self.__logger, f"  Total items processed: {items_processed}")
            debug_log(self.__logger, f"  Items updated: {items_updated}")
            debug_log(self.__logger, f"  Directories: {dirs_processed}")
            debug_log(self.__logger, f"  Files: {files_processed}")
            debug_log(self.__logger, f"  Update rate: {(items_updated/items_processed*100):.1f}%" if items_processed > 0 else "N/A")

        except Exception as e:
            self.__logger.error(f"Error while updating cache permissions: "
                              f"{e}")
            debug_log(self.__logger, f"Cache permissions error details:")
            debug_log(self.__logger, f"  Exception type: {type(e).__name__}")
            debug_log(self.__logger, f"  Exception message: {str(e)}")
            import traceback
            debug_log(self.__logger, f"  Traceback: {traceback.format_exc()}")

    # Set up scheduled jobs from all loaded plugins.
    # 
    # Iterates through all validated job definitions and creates
    # scheduled tasks for jobs that are not set to run "once".
    # Uses the schedule library to register recurring jobs with
    # their specified frequencies (minute, hour, day, week).
    def setup(self):
        debug_log(self.__logger, "Setting up scheduled jobs")
        total_jobs = sum(len(jobs) for jobs in self.__jobs.values())
        debug_log(self.__logger, f"Total jobs to process: {total_jobs}")
        
        scheduled_count = 0
        once_count = 0
        error_count = 0
        
        for plugin, jobs in self.__jobs.items():
            debug_log(self.__logger, f"Processing plugin '{plugin}' with "
                                    f"{len(jobs)} jobs")
            
            for job_idx, job in enumerate(jobs):
                debug_log(self.__logger, f"  Job {job_idx + 1}/{len(jobs)}: "
                                        f"'{job['name']}'")
                
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    
                    debug_log(self.__logger, f"    Path: {path}")
                    debug_log(self.__logger, f"    File: {file}")
                    debug_log(self.__logger, f"    Schedule: {every}")
                    
                    if every != "once":
                        schedule_obj = self.__str_to_schedule(every)
                        schedule_obj.do(self.__job_wrapper, path, plugin, 
                                      name, file)
                        scheduled_count += 1
                        
                        debug_log(self.__logger, f"    Scheduled job '{name}' "
                                                f"from plugin '{plugin}' "
                                                f"to run {every}")
                    else:
                        once_count += 1
                        debug_log(self.__logger, f"    Skipped 'once' job "
                                                f"'{name}'")
                            
                except Exception as e:
                    error_count += 1
                    self.__logger.error(f"Exception while scheduling job "
                                      f"'{name}' for plugin '{plugin}': {e}")
                    debug_log(self.__logger, f"    Scheduling error:")
                    debug_log(self.__logger, f"      Exception type: "
                                            f"{type(e).__name__}")
                    debug_log(self.__logger, f"      Exception message: "
                                            f"{str(e)}")
        
        debug_log(self.__logger, f"Job scheduling summary:")
        debug_log(self.__logger, f"  Scheduled jobs: {scheduled_count}")
        debug_log(self.__logger, f"  'Once' jobs skipped: {once_count}")
        debug_log(self.__logger, f"  Scheduling errors: {error_count}")
        debug_log(self.__logger, f"  Total schedule library jobs: "
                                f"{len(schedule.jobs)}")
        
        if scheduled_count > 0:
            debug_log(self.__logger, f"Scheduled job details:")
            for idx, job in enumerate(schedule.jobs):
                debug_log(self.__logger, f"  {idx + 1}. Next run: "
                                        f"{job.next_run}")

    # Execute all pending scheduled jobs.
    # 
    # Checks for jobs that are scheduled to run, executes them in
    # parallel using the thread pool, handles any required reloads,
    # and cleans up module paths afterwards. Manages database
    # read-only state and file synchronization with APIs.
    def run_pending(self) -> bool:
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        debug_log(self.__logger, f"Checking for pending jobs:")
        debug_log(self.__logger, f"  Total scheduled jobs: {len(schedule.jobs)}")
        debug_log(self.__logger, f"  Pending jobs: {len(pending_jobs)}")
        
        if pending_jobs:
            debug_log(self.__logger, f"Pending job details:")
            for idx, job in enumerate(pending_jobs):
                debug_log(self.__logger, f"  {idx + 1}. Job: {job}")
                debug_log(self.__logger, f"      Next run: {job.next_run}")
                debug_log(self.__logger, f"      Should run: {job.should_run}")

        if not pending_jobs:
            debug_log(self.__logger, "No pending jobs found, returning True")
            return True

        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, pending "
                              "jobs will not be executed")
            debug_log(self.__logger, "Database readonly check failed")
            return True

        debug_log(self.__logger, "Database is writable, proceeding with "
                                "job execution")

        # Reset job state flags
        self.__job_success = True
        self.__job_reload = False

        debug_log(self.__logger, "Reset job state flags:")
        debug_log(self.__logger, f"  job_success: {self.__job_success}")
        debug_log(self.__logger, f"  job_reload: {self.__job_reload}")

        try:
            # Use ThreadPoolExecutor to run jobs
            debug_log(self.__logger, f"Submitting {len(pending_jobs)} jobs "
                                    "to thread pool")
            
            futures = [self.__executor.submit(job.run) 
                      for job in pending_jobs]

            debug_log(self.__logger, f"Created {len(futures)} futures")

            # Wait for all jobs to complete
            for idx, future in enumerate(futures):
                debug_log(self.__logger, f"Waiting for future {idx + 1}/"
                                        f"{len(futures)}")
                
                result = future.result()
                
                debug_log(self.__logger, f"Future {idx + 1} completed with "
                                        f"result: {result}")

            success = self.__job_success
            debug_log(self.__logger, f"All jobs completed, final success: "
                                    f"{success}")
            
            self.__job_success = True

            # Handle reload if needed
            if self.__job_reload:
                debug_log(self.__logger, "Job reload flag is set, processing "
                                        "reload operations")
                
                try:
                    if self.apis:
                        cache_path = os.path.join(os.sep, "var", "cache", 
                                                "bunkerweb")
                        
                        debug_log(self.__logger, f"Sending cache folder: "
                                                f"{cache_path}")
                        debug_log(self.__logger, f"Cache path exists: "
                                                f"{os.path.exists(cache_path)}")
                        if os.path.exists(cache_path):
                            cache_size = sum(f.stat().st_size 
                                           for f in Path(cache_path).rglob('*') 
                                           if f.is_file())
                            debug_log(self.__logger, f"Cache size: {cache_size} bytes")
                        
                        self.__logger.info(f"Sending '{cache_path}' "
                                         "folder...")
                        if not self.send_files(cache_path, "/cache"):
                            success = False
                            self.__logger.error(f"Error while sending "
                                              f"'{cache_path}' folder")
                            debug_log(self.__logger, "Cache folder send failed")
                        else:
                            self.__logger.info(f"Successfully sent "
                                             f"'{cache_path}' folder")
                            debug_log(self.__logger, "Cache folder sent successfully")
                    else:
                        debug_log(self.__logger, "No APIs configured, skipping "
                                                "cache folder send")

                    debug_log(self.__logger, "Initiating nginx reload")
                    
                    if not self.__reload():
                        success = False
                        debug_log(self.__logger, "Nginx reload failed")
                    else:
                        debug_log(self.__logger, "Nginx reload successful")
                            
                except Exception as e:
                    success = False
                    self.__logger.error(f"Exception while reloading after "
                                      f"job scheduling: {e}")
                    debug_log(self.__logger, f"Reload exception details:")
                    debug_log(self.__logger, f"  Exception type: "
                                            f"{type(e).__name__}")
                    debug_log(self.__logger, f"  Exception message: {str(e)}")
                
                self.__job_reload = False
                debug_log(self.__logger, "Reset job_reload flag to False")
            else:
                debug_log(self.__logger, "No reload required")

            if pending_jobs:
                self.__logger.info("All scheduled jobs have been executed")

            debug_log(self.__logger, f"run_pending returning: {success}")

            return success
        finally:
            # Clean up module paths thread-safely
            debug_log(self.__logger, "Cleaning up module paths")
            
            with self.__module_paths_lock:
                paths_to_remove = self.__module_paths.copy()
                debug_log(self.__logger, f"Removing {len(paths_to_remove)} "
                                        "module paths from sys.path")
                
                for module_path in paths_to_remove:
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                        debug_log(self.__logger, f"Removed from sys.path: "
                                                f"{module_path}")
                    self.__module_paths.remove(module_path)

                debug_log(self.__logger, f"Module path cleanup complete, "
                                        f"sys.path length: {len(sys_path)}")

            self.__update_cache_permissions()

    # Execute all jobs once, optionally filtering by plugin names.
    # 
    # Runs all loaded jobs exactly once, regardless of their scheduling.
    # Supports filtering to include only specific plugins or exclude
    # certain plugins. Handles both synchronous and asynchronous jobs
    # appropriately using thread pools.
    def run_once(self, plugins: Optional[List[str]] = None, 
                ignore_plugins: Optional[List[str]] = None) -> bool:
        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, jobs will "
                              "not be executed")
            return True

        debug_log(self.__logger, f"Running once with plugins filter: "
                                f"{plugins}, ignore: {ignore_plugins}")

        self.__job_success = True
        self.__job_reload = False

        plugins = plugins or []

        try:
            futures = []
            for plugin, jobs in self.__jobs.items():
                jobs_to_run = []
                if ((plugins and plugin not in plugins) or 
                    (ignore_plugins and plugin in ignore_plugins)):
                    debug_log(self.__logger, f"Skipping plugin '{plugin}' "
                                            "due to filters")
                    continue
                
                for job in jobs:
                    if job.get("async", False):
                        debug_log(self.__logger, f"Running async job "
                                                f"'{job['name']}' from "
                                                f"plugin '{plugin}'")
                        futures.append(
                            self.__executor.submit(
                                self.__job_wrapper, job["path"], plugin, 
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
                    debug_log(self.__logger, f"Running {len(jobs_to_run)} "
                                            f"sync jobs from plugin "
                                            f"'{plugin}'")
                    futures.append(self.__executor.submit(self.__run_jobs, 
                                                        jobs_to_run))

            # Wait for all jobs to complete
            debug_log(self.__logger, f"Waiting for {len(futures)} futures to complete")
            
            for future in futures:
                future.result()

            debug_log(self.__logger, f"All futures completed, final success: "
                                    f"{self.__job_success}")

            return self.__job_success
        finally:
            with self.__module_paths_lock:
                paths_to_remove = self.__module_paths.copy()
                debug_log(self.__logger, f"Cleaning up {len(paths_to_remove)} "
                                        "module paths")
                
                for module_path in paths_to_remove:
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                    self.__module_paths.remove(module_path)

            self.__update_cache_permissions()

    # Execute a single job by name.
    # 
    # Searches for a job with the specified name across all loaded
    # plugins and executes it once. Handles locking for thread safety
    # and performs cleanup afterwards. Used for manual job execution
    # or testing individual jobs.
    def run_single(self, job_name: str) -> bool:
        if self.try_database_readonly():
            self.__logger.error(f"Database is in read-only mode, single "
                              f"job '{job_name}' will not be executed")
            return True

        debug_log(self.__logger, f"Running single job: {job_name}")

        if self.__lock:
            debug_log(self.__logger, "Acquiring scheduler lock")
            self.__lock.acquire()

        try:
            job_plugin = ""
            job_to_run = None
            
            # Search for the job across all plugins
            for plugin, jobs in self.__jobs.items():
                for job in jobs:
                    if job["name"] == job_name:
                        job_plugin = plugin
                        job_to_run = job
                        debug_log(self.__logger, f"Found job '{job_name}' "
                                                f"in plugin '{plugin}'")
                        break
                if job_to_run:
                    break

            if not job_plugin or not job_to_run:
                self.__logger.warning(f"Job '{job_name}' not found")
                debug_log(self.__logger, f"Job '{job_name}' not found in "
                                        f"{len(self.__jobs)} plugins")
                available_jobs = []
                for plugin, jobs in self.__jobs.items():
                    for job in jobs:
                        available_jobs.append(f"{plugin}.{job['name']}")
                debug_log(self.__logger, f"Available jobs: {available_jobs}")
                return False

            debug_log(self.__logger, f"Executing single job:")
            debug_log(self.__logger, f"  Name: {job_to_run['name']}")
            debug_log(self.__logger, f"  Plugin: {job_plugin}")
            debug_log(self.__logger, f"  Path: {job_to_run['path']}")
            debug_log(self.__logger, f"  File: {job_to_run['file']}")

            try:
                self.__job_wrapper(
                    job_to_run["path"],
                    job_plugin,
                    job_to_run["name"],
                    job_to_run["file"],
                )
            finally:
                with self.__module_paths_lock:
                    paths_to_remove = self.__module_paths.copy()
                    debug_log(self.__logger, f"Cleaning up {len(paths_to_remove)} "
                                            "module paths after single job")
                    
                    for module_path in paths_to_remove:
                        if module_path in sys_path:
                            sys_path.remove(module_path)
                        self.__module_paths.remove(module_path)

                self.__update_cache_permissions()

            debug_log(self.__logger, f"Single job '{job_name}' completed with "
                                    f"success: {self.__job_success}")

            return self.__job_success
        finally:
            if self.__lock:
                debug_log(self.__logger, "Releasing scheduler lock")
                self.__lock.release()

    # Execute a list of jobs sequentially.
    # 
    # Takes a list of job functions and executes them one by one
    # in the current thread. Used for running synchronous jobs
    # that need to be executed in a specific order or thread.
    def __run_jobs(self, jobs):
        debug_log(self.__logger, f"Executing {len(jobs)} jobs sequentially")
        debug_log(self.__logger, f"Thread ID: {threading.current_thread().ident}")
        
        for idx, job in enumerate(jobs):
            debug_log(self.__logger, f"Executing job {idx + 1}/{len(jobs)}")
            job()

    # Clear all scheduled jobs.
    # 
    # Removes all jobs from the schedule library's job queue.
    # This is typically called during reload operations to
    # reset the scheduling state before setting up new jobs.
    def clear(self):
        jobs_before = len(schedule.jobs)
        debug_log(self.__logger, f"Clearing {jobs_before} scheduled jobs")
        
        schedule.clear()
        
        debug_log(self.__logger, f"Schedule cleared, now has "
                                f"{len(schedule.jobs)} jobs")

    # Reload the scheduler with new environment and plugin configuration.
    # 
    # Performs a complete reload of the job scheduler including environment
    # variables, API connections, and job definitions. Clears existing
    # schedules, updates job registry, runs jobs once, and sets up new
    # schedules. Used when configuration changes are detected.
    def reload(
        self, env: Dict[str, Any], apis: Optional[list] = None, *, 
        changed_plugins: Optional[List[str]] = None, 
        ignore_plugins: Optional[List[str]] = None
    ) -> bool:
        debug_log(self.__logger, f"Reloading scheduler with {len(env)} "
                                f"env vars, changed_plugins: "
                                f"{changed_plugins}, ignore: {ignore_plugins}")
        debug_log(self.__logger, f"Current APIs: {len(self.apis)}, "
                                f"new APIs: {len(apis or [])}")
        
        try:
            # Update environment
            debug_log(self.__logger, "Updating environment variables")
            os.environ = self.__base_env.copy()
            os.environ.update(env)  # Update with new environment
            
            # Reinitialize APIs
            debug_log(self.__logger, "Reinitializing API connections")
            super().__init__(apis or self.apis)
            
            # Clear existing schedules
            debug_log(self.__logger, "Clearing existing job schedules")
            self.clear()
            
            # Reload job definitions
            debug_log(self.__logger, "Reloading job definitions from plugins")
            self.update_jobs()
            
            # Run jobs once with filters
            debug_log(self.__logger, "Running jobs once after reload")
            success = self.run_once(changed_plugins, ignore_plugins)
            
            # Set up new schedules
            debug_log(self.__logger, "Setting up new job schedules")
            self.setup()
            
            debug_log(self.__logger, f"Scheduler reload completed with "
                                    f"success: {success}")
            debug_log(self.__logger, f"Total scheduled jobs after reload: "
                                    f"{len(schedule.jobs)}")
            
            return success
        except Exception as e:
            self.__logger.error(f"Exception while reloading scheduler: {e}")
            debug_log(self.__logger, f"Reload exception details:")
            debug_log(self.__logger, f"  Exception type: {type(e).__name__}")
            debug_log(self.__logger, f"  Exception message: {str(e)}")
            import traceback
            debug_log(self.__logger, f"  Traceback: {traceback.format_exc()}")
            return False

    # Check if database is in read-only mode and attempt reconnection.
    # 
    # Tests database write capability and attempts to reconnect if in
    # read-only mode. Handles connection retry logic, fallback to
    # read-only databases, and connection timeout management. Uses
    # various connection strategies including fallback URLs.
    def try_database_readonly(self, force: bool = False) -> bool:
        debug_log(self.__logger, f"Checking database readonly status:")
        debug_log(self.__logger, f"  Current readonly: {self.db.readonly}")
        debug_log(self.__logger, f"  Force retry: {force}")
        debug_log(self.__logger, f"  Has database_uri: "
                                f"{bool(getattr(self.db, 'database_uri', None))}")
        last_retry = getattr(self.db, 'last_connection_retry', None)
        debug_log(self.__logger, f"  Last retry: {last_retry}")
        
        if not self.db.readonly:
            debug_log(self.__logger, "Database not in readonly mode, testing write")
            
            try:
                self.db.test_write()
                self.db.readonly = False
                debug_log(self.__logger, "Write test successful, database is writable")
                return False
            except Exception as e:
                self.db.readonly = True
                debug_log(self.__logger, f"Write test failed: {e}")
                debug_log(self.__logger, "Setting database to readonly mode")
                return True
        elif (not force and self.db.last_connection_retry and 
              (datetime.now().astimezone() - 
               self.db.last_connection_retry).total_seconds() > 30):
            last_retry_ago = (datetime.now().astimezone() - 
                            self.db.last_connection_retry).total_seconds()
            debug_log(self.__logger, f"Last retry was {last_retry_ago:.1f}s ago, "
                                    "within 30s limit, skipping retry")
            return True

        if self.db.database_uri and self.db.readonly:
            debug_log(self.__logger, "Database has URI and is readonly, "
                                    "attempting reconnection")
            
            try:
                debug_log(self.__logger, "Trying read-write connection")
                
                self.db.retry_connection(pool_timeout=1)
                self.db.retry_connection(log=False)
                self.db.readonly = False
                self.__logger.info("The database is no longer read-only, "
                                 "defaulting to read-write mode")
                
                debug_log(self.__logger, "Read-write connection successful")
                    
            except Exception as e:
                debug_log(self.__logger, f"Read-write connection failed: {e}")
                debug_log(self.__logger, "Trying readonly connection")
                
                try:
                    self.db.retry_connection(readonly=True, pool_timeout=1)
                    self.db.retry_connection(readonly=True, log=False)
                    debug_log(self.__logger, "Readonly connection successful")
                except Exception as e2:
                    debug_log(self.__logger, f"Readonly connection failed: {e2}")
                    
                    if self.db.database_uri_readonly:
                        debug_log(self.__logger, "Trying fallback connection")
                        with suppress(Exception):
                            self.db.retry_connection(fallback=True, 
                                                   pool_timeout=1)
                            self.db.retry_connection(fallback=True, 
                                                   log=False)
                            debug_log(self.__logger, "Fallback connection successful")
                    else:
                        debug_log(self.__logger, "No fallback URI available")
                
                self.db.readonly = True
                debug_log(self.__logger, "Database remains in readonly mode")

        final_readonly = self.db.readonly
        debug_log(self.__logger, f"Database readonly check complete: "
                                f"{final_readonly}")
        if hasattr(self.db, 'last_connection_retry'):
            debug_log(self.__logger, f"Updated last_connection_retry: "
                                    f"{self.db.last_connection_retry}")
        
        return final_readonly