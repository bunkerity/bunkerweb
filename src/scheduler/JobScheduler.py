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


def _setup_scheduler_logger(logger: Optional[Logger] = None) -> Logger:
    # Set up logger for the job scheduler with appropriate log level
    # Checks both CUSTOM_LOG_LEVEL and LOG_LEVEL environment variables
    # Returns configured logger instance for scheduler operations
    log_level = os.getenv("CUSTOM_LOG_LEVEL", 
                          os.getenv("LOG_LEVEL", "INFO"))
    return logger or setup_logger("Scheduler", log_level)


def _get_debug_enabled() -> bool:
    # Check if debug logging is enabled via environment variables
    # Returns True if LOG_LEVEL is set to DEBUG (case insensitive)
    return os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"


class JobScheduler(ApiCaller):
    def __init__(
        self,
        logger: Optional[Logger] = None,
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        # Initialize the job scheduler with database and API connections.
        # 
        # Creates a threaded job scheduler that can execute plugin jobs on
        # various schedules. Sets up thread pools, regex compilation, and
        # initializes all necessary state tracking variables.
        # 
        # Args:
        #     logger: Optional logger instance for output
        #     db: Optional database connection for job tracking
        #     lock: Optional lock for thread synchronization
        #     apis: Optional list of API endpoints for communication
        super().__init__(apis or [])
        self.__logger = _setup_scheduler_logger(logger)
        
        if _get_debug_enabled():
            self.__logger.debug("Starting JobScheduler initialization")
            self.__logger.debug(f"Log level set to: {os.getenv('LOG_LEVEL', 'INFO')}")
            self.__logger.debug(f"APIs provided: {len(apis or [])}")
        
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
        
        if _get_debug_enabled():
            self.__logger.debug(f"CPU count: {cpu_count}, "
                              f"calculated max_workers: {max_workers}")
            self.__logger.debug(f"Base environment has {len(self.__base_env)} "
                              "variables")
        
        self.__compiled_regexes = self.__compile_regexes()
        self.__module_paths = set()
        # Dedicated lock for module paths
        self.__module_paths_lock = Lock()
        
        if _get_debug_enabled():
            self.__logger.debug(f"JobScheduler initialized with "
                              f"max_workers={max_workers}")
            self.__logger.debug("Starting job discovery and validation")
        
        self.update_jobs()
        
        if _get_debug_enabled():
            self.__logger.debug("JobScheduler initialization complete")

    def __compile_regexes(self):
        # Precompile regular expressions for job validation.
        # 
        # Creates compiled regex patterns for validating job names and file
        # paths to ensure they meet security and naming requirements.
        # Job names must be 1-128 chars of word chars, dots, or dashes.
        # File paths must be 1-256 chars of word chars, dots, slashes, dashes.
        # 
        # Returns:
        #     dict: Dictionary containing compiled regex patterns for 
        #           'name' and 'file' validation
        if _get_debug_enabled():
            self.__logger.debug("Compiling regex patterns for job validation")
            self.__logger.debug("Name pattern: ^[\\w.-]{1,128}$ (word chars, "
                              "dots, dashes, 1-128 length)")
            self.__logger.debug("File pattern: ^[\\w./-]{1,256}$ (word chars, "
                              "dots, slashes, dashes, 1-256 length)")
        
        patterns = {
            "name": re_compile(r"^[\w.-]{1,128}$"),
            "file": re_compile(r"^[\w./-]{1,256}$"),
        }
        
        if _get_debug_enabled():
            self.__logger.debug(f"Successfully compiled {len(patterns)} "
                              "regex patterns")
        
        return patterns

    @property
    def env(self) -> Dict[str, Any]:
        # Get a copy of the current environment variables.
        # 
        # Returns a complete copy of the current process environment to
        # prevent external modification of the scheduler's environment state.
        # 
        # Returns:
        #     Dict[str, Any]: Copy of current environment variables
        if _get_debug_enabled():
            env_copy = os.environ.copy()
            self.__logger.debug(f"Returning environment copy with "
                              f"{len(env_copy)} variables")
            return env_copy
        return os.environ.copy()

    @env.setter
    def env(self, env: Dict[str, Any]):
        # Set environment variables, resetting to base first.
        # 
        # Resets the environment to the base state captured during
        # initialization, then applies the provided environment updates.
        # This ensures clean environment state for job execution.
        # 
        # Args:
        #     env: Dictionary of environment variables to set
        if _get_debug_enabled():
            self.__logger.debug(f"Setting environment with {len(env)} "
                              "variables")
            self.__logger.debug(f"Base environment has "
                              f"{len(self.__base_env)} variables")
            # Log any new variables being added
            new_vars = set(env.keys()) - set(self.__base_env.keys())
            if new_vars:
                self.__logger.debug(f"Adding {len(new_vars)} new variables: "
                                  f"{', '.join(sorted(new_vars))}")
        
        os.environ = self.__base_env.copy()  # Reset to base environment
        os.environ.update(env)  # Update with new environment
        
        if _get_debug_enabled():
            self.__logger.debug(f"Environment updated, now has "
                              f"{len(os.environ)} total variables")

    def update_jobs(self):
        # Refresh the job definitions from plugin files.
        # 
        # Scans all plugin directories, loads plugin.json files, and
        # validates job definitions. This method rebuilds the complete
        # job registry from scratch, ensuring all jobs are current and valid.
        # Called during initialization and when configuration changes.
        if _get_debug_enabled():
            self.__logger.debug("Starting job definition update from plugins")
            self.__logger.debug("Clearing existing job cache")
        
        start_time = datetime.now()
        self.__jobs = self.__get_jobs()
        end_time = datetime.now()
        
        if _get_debug_enabled():
            duration = (end_time - start_time).total_seconds()
            total_jobs = sum(len(jobs) for jobs in self.__jobs.values())
            self.__logger.debug(f"Job update completed in {duration:.3f}s")
            self.__logger.debug(f"Loaded {total_jobs} jobs from "
                              f"{len(self.__jobs)} plugins")
            for plugin_name, jobs in self.__jobs.items():
                if jobs:
                    self.__logger.debug(f"Plugin '{plugin_name}': "
                                      f"{len(jobs)} jobs")

    def __get_jobs(self):
        # Load and validate jobs from all plugin directories.
        # 
        # Searches predefined plugin directories for plugin.json files,
        # loads job definitions in parallel using thread pool, and
        # validates each job against the required schema. Handles
        # file loading errors gracefully and logs warnings for issues.
        # 
        # Returns:
        #     dict: Dictionary mapping plugin names to lists of valid jobs.
        #           Each job contains validated name, file, schedule, and path.
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

        if _get_debug_enabled():
            self.__logger.debug(f"Scanning {len(plugin_dirs)} plugin "
                              "directories:")
            for i, dir_pattern in enumerate(plugin_dirs, 1):
                self.__logger.debug(f"  {i}. {dir_pattern}")

        for pattern in plugin_dirs:
            found_files = glob(pattern)
            plugin_files.extend(found_files)
            if _get_debug_enabled():
                self.__logger.debug(f"Pattern '{pattern}' found "
                                  f"{len(found_files)} files")

        if _get_debug_enabled():
            self.__logger.debug(f"Found {len(plugin_files)} total plugin "
                              "files to process")
            if plugin_files:
                self.__logger.debug("Plugin files found:")
                for i, pf in enumerate(plugin_files, 1):
                    self.__logger.debug(f"  {i}. {pf}")

        def load_plugin(plugin_file):
            # Load and validate a single plugin file.
            # 
            # Reads the plugin.json file, extracts job definitions,
            # and validates them against the schema requirements.
            # 
            # Args:
            #     plugin_file: Path to the plugin.json file
            #     
            # Returns:
            #     tuple: (plugin_name, list_of_valid_jobs)
            plugin_name = os.path.basename(os.path.dirname(plugin_file))
            
            if _get_debug_enabled():
                self.__logger.debug(f"Processing plugin file: {plugin_file}")
                self.__logger.debug(f"Plugin name: {plugin_name}")
            
            try:
                file_content = Path(plugin_file).read_text(encoding="utf-8")
                
                if _get_debug_enabled():
                    self.__logger.debug(f"Read {len(file_content)} characters "
                                      f"from {plugin_file}")
                
                plugin_data = loads(file_content)
                plugin_jobs = plugin_data.get("jobs", [])
                
                if _get_debug_enabled():
                    self.__logger.debug(f"Loaded plugin data with "
                                      f"{len(plugin_jobs)} job definitions")
                    if "jobs" not in plugin_data:
                        self.__logger.debug(f"No 'jobs' key found in "
                                          f"{plugin_file}")
                    else:
                        self.__logger.debug(f"Jobs key found with "
                                          f"{len(plugin_jobs)} entries")
                
                validated_jobs = self.__validate_jobs(
                    plugin_jobs, plugin_name, plugin_file)
                
                if _get_debug_enabled():
                    self.__logger.debug(f"Plugin {plugin_name}: "
                                      f"{len(plugin_jobs)} raw jobs -> "
                                      f"{len(validated_jobs)} valid jobs")
                
                return plugin_name, validated_jobs
                
            except FileNotFoundError:
                self.__logger.warning(f"Plugin file not found: "
                                    f"{plugin_file}")
                if _get_debug_enabled():
                    self.__logger.debug(f"FileNotFoundError for {plugin_file}")
            except Exception as e:
                self.__logger.warning(f"Exception while getting jobs for "
                                    f"plugin {plugin_name}: {e}")
                if _get_debug_enabled():
                    self.__logger.debug(f"Exception type: {type(e).__name__}")
                    self.__logger.debug(f"Exception details: {str(e)}")
            
            return plugin_name, []

        # Load/validate plugins in parallel:
        if _get_debug_enabled():
            self.__logger.debug(f"Starting parallel plugin processing with "
                              f"ThreadPoolExecutor")
        
        results = list(self.__executor.map(load_plugin, plugin_files))

        if _get_debug_enabled():
            self.__logger.debug(f"Parallel processing completed, got "
                              f"{len(results)} results")

        for plugin_name, valid_jobs in results:
            jobs[plugin_name] = valid_jobs
            if _get_debug_enabled():
                if valid_jobs:
                    self.__logger.debug(f"Added {len(valid_jobs)} jobs for "
                                      f"plugin '{plugin_name}'")
                else:
                    self.__logger.debug(f"No valid jobs for plugin "
                                      f"'{plugin_name}'")
        
        if _get_debug_enabled():
            total_jobs = sum(len(job_list) for job_list in jobs.values())
            self.__logger.debug(f"Final result: {total_jobs} total valid "
                              f"jobs from {len(jobs)} plugins")
            plugins_with_jobs = sum(1 for job_list in jobs.values() 
                                  if job_list)
            self.__logger.debug(f"{plugins_with_jobs} plugins have jobs, "
                              f"{len(jobs) - plugins_with_jobs} plugins "
                              "have no jobs")
        
        return jobs

    def __validate_jobs(self, plugin_jobs, plugin_name, plugin_file):
        # Validate job definitions according to required schema.
        # 
        # Checks each job definition for required fields (name, file, every,
        # reload) and validates their format and values. Job names and files
        # must match regex patterns, schedule values must be valid, and
        # boolean flags must be proper booleans.
        # 
        # Args:
        #     plugin_jobs: List of job definitions from plugin.json
        #     plugin_name: Name of the plugin being validated
        #     plugin_file: Path to the plugin file for error reporting
        #     
        # Returns:
        #     list: List of validated job dictionaries with added 'path' field
        valid_jobs = []
        required_keys = ("name", "file", "every", "reload")
        valid_schedules = ("once", "minute", "hour", "day", "week")
        
        if _get_debug_enabled():
            self.__logger.debug(f"Validating {len(plugin_jobs)} jobs for "
                              f"plugin '{plugin_name}'")
            self.__logger.debug(f"Required keys: {', '.join(required_keys)}")
            self.__logger.debug(f"Valid schedules: "
                              f"{', '.join(valid_schedules)}")
        
        for i, job in enumerate(plugin_jobs):
            if _get_debug_enabled():
                self.__logger.debug(f"Validating job {i+1}/{len(plugin_jobs)}: "
                                  f"{job.get('name', '<no name>')}")
            
            # Check required keys
            missing_keys = [k for k in required_keys if k not in job]
            if missing_keys:
                self.__logger.warning(f"Missing keys in job definition in "
                                    f"plugin {plugin_name}. Required keys: "
                                    f"{', '.join(required_keys)}. "
                                    f"Missing: {', '.join(missing_keys)}. "
                                    f"Job: {job}")
                if _get_debug_enabled():
                    self.__logger.debug(f"Job {i+1} failed: missing keys")
                continue

            # Validate individual fields
            name_valid = self.__compiled_regexes["name"].match(job["name"])
            file_valid = self.__compiled_regexes["file"].match(job["file"])
            every_valid = job["every"] in valid_schedules
            reload_valid = isinstance(job.get("reload", False), bool)
            async_valid = isinstance(job.get("async", False), bool)

            if _get_debug_enabled():
                self.__logger.debug(f"Job '{job['name']}' validation:")
                self.__logger.debug(f"  name_valid: {bool(name_valid)} "
                                  f"('{job['name']}')")
                self.__logger.debug(f"  file_valid: {bool(file_valid)} "
                                  f"('{job['file']}')")
                self.__logger.debug(f"  every_valid: {every_valid} "
                                  f"('{job['every']}')")
                self.__logger.debug(f"  reload_valid: {reload_valid} "
                                  f"({job.get('reload', False)})")
                self.__logger.debug(f"  async_valid: {async_valid} "
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
                if _get_debug_enabled():
                    self.__logger.debug(f"Job {i+1} failed validation: "
                                      f"{', '.join(validation_details)}")
                continue

            # Add plugin path and accept the job
            job["path"] = os.path.dirname(plugin_file)
            valid_jobs.append(job)
            
            if _get_debug_enabled():
                self.__logger.debug(f"Job '{job['name']}' validated "
                                  f"successfully")
                self.__logger.debug(f"  path: {job['path']}")
                self.__logger.debug(f"  schedule: {job['every']}")
                self.__logger.debug(f"  reload: {job.get('reload', False)}")
                self.__logger.debug(f"  async: {job.get('async', False)}")
        
        if _get_debug_enabled():
            self.__logger.debug(f"Plugin '{plugin_name}' validation "
                              f"complete: {len(valid_jobs)}/{len(plugin_jobs)} "
                              "jobs valid")
        
        return valid_jobs

    def __str_to_schedule(self, every: str) -> schedule.Job:
        # Convert frequency string to schedule object.
        # 
        # Maps string representations of scheduling frequencies to the
        # corresponding schedule.Job objects used by the schedule library.
        # Supports minute, hour, day, and week intervals.
        # 
        # Args:
        #     every: String frequency ("minute", "hour", "day", "week")
        #     
        # Returns:
        #     schedule.Job: Configured job schedule object
        #     
        # Raises:
        #     ValueError: If the frequency string is not recognized
        schedule_map = {
            "minute": schedule.every().minute,
            "hour": schedule.every().hour,
            "day": schedule.every().day,
            "week": schedule.every().week,
        }
        
        if _get_debug_enabled():
            self.__logger.debug(f"Converting schedule string '{every}' to "
                              "schedule object")
            if every in schedule_map:
                self.__logger.debug(f"Found mapping for '{every}'")
            else:
                self.__logger.debug(f"No mapping found for '{every}', "
                                  f"available: {list(schedule_map.keys())}")
        
        try:
            schedule_obj = schedule_map[every]
            if _get_debug_enabled():
                self.__logger.debug(f"Successfully created schedule object "
                                  f"for '{every}'")
            return schedule_obj
        except KeyError:
            error_msg = f"Can't convert string '{every}' to schedule"
            if _get_debug_enabled():
                self.__logger.debug(f"KeyError: {error_msg}")
            raise ValueError(error_msg)

    def __reload(self) -> bool:
        # Reload nginx configuration via API.
        # 
        # Sends a reload request to connected APIs to refresh nginx
        # configuration. Calculates appropriate timeout based on server
        # names and minimum timeout settings. Handles configuration
        # testing based on environment settings.
        # 
        # Returns:
        #     bool: True if reload was successful, False otherwise
        self.__logger.info("Reloading nginx...")
        reload_min_timeout = self.env.get("RELOAD_MIN_TIMEOUT", "5")

        if _get_debug_enabled():
            self.__logger.debug(f"Raw RELOAD_MIN_TIMEOUT: '{reload_min_timeout}'")

        if not reload_min_timeout.isdigit():
            self.__logger.error("RELOAD_MIN_TIMEOUT must be an integer, "
                              "defaulting to 5")
            if _get_debug_enabled():
                self.__logger.debug(f"Invalid timeout value "
                                  f"'{reload_min_timeout}', using 5")
            reload_min_timeout = 5

        disable_config_test = (self.env.get('DISABLE_CONFIGURATION_TESTING', 
                                          'no').lower() == 'yes')
        test_param = 'no' if disable_config_test else 'yes'
        server_names = self.env.get("SERVER_NAME", "www.example.com")
        server_name_list = server_names.split(" ")
        timeout_calc = max(int(reload_min_timeout), 
                          3 * len(server_name_list))
        
        if _get_debug_enabled():
            self.__logger.debug(f"Configuration testing disabled: "
                              f"{disable_config_test}")
            self.__logger.debug(f"Test parameter: {test_param}")
            self.__logger.debug(f"Server names: '{server_names}' "
                              f"({len(server_name_list)} servers)")
            self.__logger.debug(f"Timeout calculation: max({reload_min_timeout}, "
                              f"3 * {len(server_name_list)}) = {timeout_calc}")
            self.__logger.debug(f"Sending reload request to {len(self.apis)} "
                              "APIs")

        reload_url = f"/reload?test={test_param}"
        if _get_debug_enabled():
            self.__logger.debug(f"Reload URL: {reload_url}")

        reload_success = self.send_to_apis(
            "POST",
            reload_url,
            timeout=timeout_calc,
        )[0]
        
        if _get_debug_enabled():
            self.__logger.debug(f"API response success: {reload_success}")
        
        if reload_success:
            self.__logger.info("Successfully reloaded nginx")
            return True
        
        self.__logger.error("Error while reloading nginx")
        if _get_debug_enabled():
            self.__logger.debug("Reload failed - API returned failure")
        return False

    def __exec_plugin_module(self, path: str, name: str) -> None:
        # Dynamically import and execute a plugin module.
        # 
        # Loads a Python module from the specified path, adds its directory
        # to sys.path for imports, and executes it. Handles path resolution,
        # module spec creation, and maintains thread-safe module path tracking.
        # 
        # Args:
        #     path: Full path to the Python module file to execute
        #     name: Name identifier for the module (used for spec creation)
        #     
        # Raises:
        #     FileNotFoundError: If the plugin path doesn't exist
        #     ImportError: If module spec creation fails
        # Convert to absolute path using Path
        abs_path = Path(path).resolve()
        module_dir = abs_path.parent

        if _get_debug_enabled():
            self.__logger.debug(f"Executing plugin module '{name}'")
            self.__logger.debug(f"Module path: {path}")
            self.__logger.debug(f"Absolute path: {abs_path}")
            self.__logger.debug(f"Module directory: {module_dir}")

        # Validate path exists
        if not abs_path.exists():
            error_msg = f"Plugin path not found: {abs_path}"
            if _get_debug_enabled():
                self.__logger.debug(f"Path validation failed: {error_msg}")
            raise FileNotFoundError(error_msg)

        if _get_debug_enabled():
            self.__logger.debug(f"Path validation successful")

        module_dir_str = module_dir.as_posix()
        
        # Thread-safe module path management
        with self.__module_paths_lock:
            path_already_added = (module_dir_str in sys_path or 
                                module_dir_str in self.__module_paths)
            
            if _get_debug_enabled():
                self.__logger.debug(f"Module dir string: {module_dir_str}")
                self.__logger.debug(f"Already in sys.path: "
                                  f"{module_dir_str in sys_path}")
                self.__logger.debug(f"Already tracked: "
                                  f"{module_dir_str in self.__module_paths}")
                self.__logger.debug(f"Current sys.path length: "
                                  f"{len(sys_path)}")
                self.__logger.debug(f"Tracked paths: "
                                  f"{len(self.__module_paths)}")
            
            if not path_already_added:
                self.__module_paths.add(module_dir.as_posix())
                sys_path.insert(0, module_dir.as_posix())
                if _get_debug_enabled():
                    self.__logger.debug(f"Added module directory to sys.path "
                                      f"at position 0")
                    self.__logger.debug(f"sys.path now has {len(sys_path)} "
                                      "entries")
            else:
                if _get_debug_enabled():
                    self.__logger.debug("Module directory already in path, "
                                      "skipping addition")

        # Create and execute module
        if _get_debug_enabled():
            self.__logger.debug(f"Creating module spec for '{name}' "
                              f"from {abs_path.as_posix()}")
        
        spec = spec_from_file_location(name, abs_path.as_posix())
        if spec is None:
            error_msg = f"Failed to create module spec for {abs_path}"
            if _get_debug_enabled():
                self.__logger.debug(f"Spec creation failed: {error_msg}")
            raise ImportError(error_msg)

        if _get_debug_enabled():
            self.__logger.debug(f"Module spec created successfully")
            self.__logger.debug(f"Spec name: {spec.name}")
            self.__logger.debug(f"Spec origin: {spec.origin}")
            self.__logger.debug(f"Creating module from spec")

        module = module_from_spec(spec)
        
        if _get_debug_enabled():
            self.__logger.debug(f"Module created, executing...")
        
        spec.loader.exec_module(module)
        
        if _get_debug_enabled():
            self.__logger.debug(f"Module '{name}' executed successfully")

    def __job_wrapper(self, path: str, plugin: str, name: str, 
                     file: str) -> int:
        # Execute a single job and handle its lifecycle.
        # 
        # Wraps job execution with timing, error handling, and state tracking.
        # Records start/end times, manages return codes, handles exceptions,
        # and updates global job state flags. Manages database logging of
        # job execution results.
        # 
        # Args:
        #     path: Base path to the plugin directory
        #     plugin: Name of the plugin containing the job
        #     name: Name of the job being executed
        #     file: Filename of the job script to execute
        #     
        # Returns:
        #     int: Job return code (1=success with reload, 0=success no reload,
        #          negative or >=2 indicates error)
        self.__logger.info(f"Executing job '{name}' from plugin "
                         f"'{plugin}'...")
        success = True
        ret = -1
        start_date = datetime.now().astimezone()
        
        if _get_debug_enabled():
            self.__logger.debug(f"Job execution started:")
            self.__logger.debug(f"  Job name: {name}")
            self.__logger.debug(f"  Plugin: {plugin}")
            self.__logger.debug(f"  File: {file}")
            self.__logger.debug(f"  Path: {path}")
            self.__logger.debug(f"  Start time: {start_date}")
            self.__logger.debug(f"  Thread ID: {threading.current_thread().ident}")
            self.__logger.debug(f"  Process ID: {os.getpid()}")
        
        job_file_path = os.path.join(path, "jobs", file)
        if _get_debug_enabled():
            self.__logger.debug(f"Full job file path: {job_file_path}")
            self.__logger.debug(f"Job file exists: {os.path.exists(job_file_path)}")
        
        try:
            if _get_debug_enabled():
                self.__logger.debug(f"Calling __exec_plugin_module")
            
            self.__exec_plugin_module(job_file_path, name)
            ret = 1
            
            if _get_debug_enabled():
                self.__logger.debug(f"Job completed normally, return code: {ret}")
                
        except SystemExit as e:
            ret = e.code if isinstance(e.code, int) else 1
            if _get_debug_enabled():
                self.__logger.debug(f"Job exited with SystemExit")
                self.__logger.debug(f"  Exit code type: {type(e.code)}")
                self.__logger.debug(f"  Exit code value: {e.code}")
                self.__logger.debug(f"  Processed return code: {ret}")
        except Exception as e:
            success = False
            self.__logger.error(f"Exception while executing job '{name}' "
                              f"from plugin '{plugin}': {e}")
            if _get_debug_enabled():
                self.__logger.debug(f"Job execution exception:")
                self.__logger.debug(f"  Exception type: {type(e).__name__}")
                self.__logger.debug(f"  Exception message: {str(e)}")
                import traceback
                self.__logger.debug(f"  Traceback: {traceback.format_exc()}")
            
            with self.__thread_lock:
                self.__job_success = False
                if _get_debug_enabled():
                    self.__logger.debug(f"Set global job_success to False")
        
        end_date = datetime.now().astimezone()
        execution_time = (end_date - start_date).total_seconds()

        if _get_debug_enabled():
            self.__logger.debug(f"Job execution completed:")
            self.__logger.debug(f"  End time: {end_date}")
            self.__logger.debug(f"  Execution time: {execution_time:.3f} seconds")
            self.__logger.debug(f"  Return code: {ret}")
            self.__logger.debug(f"  Success flag: {success}")

        # Handle reload flag
        if ret == 1:
            with self.__thread_lock:
                old_reload_state = self.__job_reload
                self.__job_reload = True
                if _get_debug_enabled():
                    self.__logger.debug(f"Job returned 1, setting reload flag")
                    self.__logger.debug(f"  Previous reload state: {old_reload_state}")
                    self.__logger.debug(f"  New reload state: True")

        # Handle error return codes
        if self.__job_success and (ret < 0 or ret >= 2):
            success = False
            self.__logger.error(f"Error while executing job '{name}' "
                              f"from plugin '{plugin}'")
            if _get_debug_enabled():
                self.__logger.debug(f"Job failed due to return code {ret}")
                self.__logger.debug(f"  Return code < 0: {ret < 0}")
                self.__logger.debug(f"  Return code >= 2: {ret >= 2}")
            
            with self.__thread_lock:
                self.__job_success = False
                if _get_debug_enabled():
                    self.__logger.debug(f"Set global job_success to False "
                                      "due to bad return code")

        if _get_debug_enabled():
            self.__logger.debug(f"Job {name} completed in {execution_time:.2f}s "
                              f"with success={success}")
            self.__logger.debug(f"Submitting job run record to database")

        # Use the executor to manage threads
        self.__executor.submit(self.__add_job_run, name, success, 
                             start_date, end_date)

        if _get_debug_enabled():
            self.__logger.debug(f"Job wrapper returning: {ret}")

        return ret

    def __add_job_run(self, name: str, success: bool, start_date: datetime, 
                     end_date: datetime):
        # Record job execution details in the database.
        # 
        # Stores job execution metadata including timing, success status,
        # and job identification in the database for tracking and auditing
        # purposes. Handles database errors gracefully and logs results.
        # 
        # Args:
        #     name: Name of the job that was executed
        #     success: Whether the job completed successfully
        #     start_date: When the job execution began
        #     end_date: When the job execution completed
        if _get_debug_enabled():
            duration = (end_date - start_date).total_seconds()
            self.__logger.debug(f"Adding job run record:")
            self.__logger.debug(f"  Job name: {name}")
            self.__logger.debug(f"  Success: {success}")
            self.__logger.debug(f"  Start: {start_date}")
            self.__logger.debug(f"  End: {end_date}")
            self.__logger.debug(f"  Duration: {duration:.3f} seconds")
            self.__logger.debug(f"  Thread ID: {threading.current_thread().ident}")
        
        with self.__thread_lock:
            if _get_debug_enabled():
                self.__logger.debug(f"Acquired thread lock, calling db.add_job_run")
            
            err = self.db.add_job_run(name, success, start_date, end_date)
            
            if _get_debug_enabled():
                self.__logger.debug(f"Database call completed")
                self.__logger.debug(f"  Error result: {err}")
                self.__logger.debug(f"  Error type: {type(err)}")

        if not err:
            self.__logger.info(f"Successfully added job run for the job "
                             f"'{name}'")
            if _get_debug_enabled():
                self.__logger.debug(f"Job run record saved successfully")
        else:
            self.__logger.warning(f"Failed to add job run for the job "
                                f"'{name}': {err}")
            if _get_debug_enabled():
                self.__logger.debug(f"Job run record save failed")
                self.__logger.debug(f"  Error details: {str(err)}")
                self.__logger.debug(f"  Database readonly: {getattr(self.db, 'readonly', 'unknown')}")

    def __update_cache_permissions(self):
        # Update permissions for cache files and directories.
        # 
        # Recursively traverses the BunkerWeb cache directory and sets
        # appropriate permissions on all files and directories. Directories
        # get 740 (rwxr-----) and files get 640 (rw-r-----) permissions
        # for security. Handles permission errors gracefully.
        self.__logger.info("Updating /var/cache/bunkerweb permissions...")
        cache_path = Path(os.sep, "var", "cache", "bunkerweb")

        DIR_MODE = 0o740
        FILE_MODE = 0o640

        if _get_debug_enabled():
            self.__logger.debug(f"Cache permissions update started:")
            self.__logger.debug(f"  Cache path: {cache_path}")
            self.__logger.debug(f"  Cache path exists: {cache_path.exists()}")
            if cache_path.exists():
                self.__logger.debug(f"  Cache path is dir: {cache_path.is_dir()}")
            self.__logger.debug(f"  Directory mode: {oct(DIR_MODE)} (rwxr-----)")
            self.__logger.debug(f"  File mode: {oct(FILE_MODE)} (rw-r-----)")

        if not cache_path.exists():
            if _get_debug_enabled():
                self.__logger.debug(f"Cache path does not exist, skipping permissions update")
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

                if _get_debug_enabled() and items_processed <= 10:
                    self.__logger.debug(f"Processing item {items_processed}: {item}")
                    self.__logger.debug(f"  Is directory: {item.is_dir()}")
                    self.__logger.debug(f"  Current mode: {oct(current_mode)}")
                    self.__logger.debug(f"  Target mode: {oct(target_mode)}")
                    self.__logger.debug(f"  Needs update: {current_mode != target_mode}")

                if current_mode != target_mode:
                    item.chmod(target_mode)
                    items_updated += 1
                    if _get_debug_enabled():
                        item_type = "directory" if item.is_dir() else "file"
                        self.__logger.debug(f"Updated {item_type} permissions: "
                                          f"{item}: {oct(current_mode)} -> "
                                          f"{oct(target_mode)}")

            if _get_debug_enabled():
                self.__logger.debug(f"Cache permissions update completed:")
                self.__logger.debug(f"  Total items processed: {items_processed}")
                self.__logger.debug(f"  Items updated: {items_updated}")
                self.__logger.debug(f"  Directories: {dirs_processed}")
                self.__logger.debug(f"  Files: {files_processed}")
                self.__logger.debug(f"  Update rate: {(items_updated/items_processed*100):.1f}%" if items_processed > 0 else "N/A")

        except Exception as e:
            self.__logger.error(f"Error while updating cache permissions: "
                              f"{e}")
            if _get_debug_enabled():
                self.__logger.debug(f"Cache permissions error details:")
                self.__logger.debug(f"  Exception type: {type(e).__name__}")
                self.__logger.debug(f"  Exception message: {str(e)}")
                import traceback
                self.__logger.debug(f"  Traceback: {traceback.format_exc()}")

    def setup(self):
        # Set up scheduled jobs from all loaded plugins.
        # 
        # Iterates through all validated job definitions and creates
        # scheduled tasks for jobs that are not set to run "once".
        # Uses the schedule library to register recurring jobs with
        # their specified frequencies (minute, hour, day, week).
        if _get_debug_enabled():
            self.__logger.debug("Setting up scheduled jobs")
            total_jobs = sum(len(jobs) for jobs in self.__jobs.values())
            self.__logger.debug(f"Total jobs to process: {total_jobs}")
        
        scheduled_count = 0
        once_count = 0
        error_count = 0
        
        for plugin, jobs in self.__jobs.items():
            if _get_debug_enabled():
                self.__logger.debug(f"Processing plugin '{plugin}' with "
                                  f"{len(jobs)} jobs")
            
            for job_idx, job in enumerate(jobs):
                if _get_debug_enabled():
                    self.__logger.debug(f"  Job {job_idx + 1}/{len(jobs)}: "
                                      f"'{job['name']}'")
                
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    
                    if _get_debug_enabled():
                        self.__logger.debug(f"    Path: {path}")
                        self.__logger.debug(f"    File: {file}")
                        self.__logger.debug(f"    Schedule: {every}")
                    
                    if every != "once":
                        schedule_obj = self.__str_to_schedule(every)
                        schedule_obj.do(self.__job_wrapper, path, plugin, 
                                      name, file)
                        scheduled_count += 1
                        
                        if _get_debug_enabled():
                            self.__logger.debug(f"    Scheduled job '{name}' "
                                              f"from plugin '{plugin}' "
                                              f"to run {every}")
                    else:
                        once_count += 1
                        if _get_debug_enabled():
                            self.__logger.debug(f"    Skipped 'once' job "
                                              f"'{name}'")
                            
                except Exception as e:
                    error_count += 1
                    self.__logger.error(f"Exception while scheduling job "
                                      f"'{name}' for plugin '{plugin}': {e}")
                    if _get_debug_enabled():
                        self.__logger.debug(f"    Scheduling error:")
                        self.__logger.debug(f"      Exception type: "
                                          f"{type(e).__name__}")
                        self.__logger.debug(f"      Exception message: "
                                          f"{str(e)}")
        
        if _get_debug_enabled():
            self.__logger.debug(f"Job scheduling summary:")
            self.__logger.debug(f"  Scheduled jobs: {scheduled_count}")
            self.__logger.debug(f"  'Once' jobs skipped: {once_count}")
            self.__logger.debug(f"  Scheduling errors: {error_count}")
            self.__logger.debug(f"  Total schedule library jobs: "
                              f"{len(schedule.jobs)}")
            
            if scheduled_count > 0:
                self.__logger.debug(f"Scheduled job details:")
                for idx, job in enumerate(schedule.jobs):
                    self.__logger.debug(f"  {idx + 1}. Next run: "
                                      f"{job.next_run}")


    def run_pending(self) -> bool:
        # Execute all pending scheduled jobs.
        # 
        # Checks for jobs that are scheduled to run, executes them in
        # parallel using the thread pool, handles any required reloads,
        # and cleans up module paths afterwards. Manages database
        # read-only state and file synchronization with APIs.
        # 
        # Returns:
        #     bool: True if all operations completed successfully, 
        #           False if any errors occurred
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        if _get_debug_enabled():
            self.__logger.debug(f"Checking for pending jobs:")
            self.__logger.debug(f"  Total scheduled jobs: {len(schedule.jobs)}")
            self.__logger.debug(f"  Pending jobs: {len(pending_jobs)}")
            
            if pending_jobs:
                self.__logger.debug(f"Pending job details:")
                for idx, job in enumerate(pending_jobs):
                    self.__logger.debug(f"  {idx + 1}. Job: {job}")
                    self.__logger.debug(f"      Next run: {job.next_run}")
                    self.__logger.debug(f"      Should run: {job.should_run}")

        if not pending_jobs:
            if _get_debug_enabled():
                self.__logger.debug("No pending jobs found, returning True")
            return True

        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, pending "
                              "jobs will not be executed")
            if _get_debug_enabled():
                self.__logger.debug("Database readonly check failed")
            return True

        if _get_debug_enabled():
            self.__logger.debug("Database is writable, proceeding with "
                              "job execution")

        # Reset job state flags
        self.__job_success = True
        self.__job_reload = False

        if _get_debug_enabled():
            self.__logger.debug("Reset job state flags:")
            self.__logger.debug(f"  job_success: {self.__job_success}")
            self.__logger.debug(f"  job_reload: {self.__job_reload}")

        try:
            # Use ThreadPoolExecutor to run jobs
            if _get_debug_enabled():
                self.__logger.debug(f"Submitting {len(pending_jobs)} jobs "
                                  "to thread pool")
            
            futures = [self.__executor.submit(job.run) 
                      for job in pending_jobs]

            if _get_debug_enabled():
                self.__logger.debug(f"Created {len(futures)} futures")

            # Wait for all jobs to complete
            for idx, future in enumerate(futures):
                if _get_debug_enabled():
                    self.__logger.debug(f"Waiting for future {idx + 1}/"
                                      f"{len(futures)}")
                
                result = future.result()
                
                if _get_debug_enabled():
                    self.__logger.debug(f"Future {idx + 1} completed with "
                                      f"result: {result}")

            success = self.__job_success
            if _get_debug_enabled():
                self.__logger.debug(f"All jobs completed, final success: "
                                  f"{success}")
            
            self.__job_success = True

            # Handle reload if needed
            if self.__job_reload:
                if _get_debug_enabled():
                    self.__logger.debug("Job reload flag is set, processing "
                                      "reload operations")
                
                try:
                    if self.apis:
                        cache_path = os.path.join(os.sep, "var", "cache", 
                                                "bunkerweb")
                        
                        if _get_debug_enabled():
                            self.__logger.debug(f"Sending cache folder: "
                                              f"{cache_path}")
                            self.__logger.debug(f"Cache path exists: "
                                              f"{os.path.exists(cache_path)}")
                            if os.path.exists(cache_path):
                                cache_size = sum(f.stat().st_size 
                                               for f in Path(cache_path).rglob('*') 
                                               if f.is_file())
                                self.__logger.debug(f"Cache size: {cache_size} bytes")
                        
                        self.__logger.info(f"Sending '{cache_path}' "
                                         "folder...")
                        if not self.send_files(cache_path, "/cache"):
                            success = False
                            self.__logger.error(f"Error while sending "
                                              f"'{cache_path}' folder")
                            if _get_debug_enabled():
                                self.__logger.debug("Cache folder send failed")
                        else:
                            self.__logger.info(f"Successfully sent "
                                             f"'{cache_path}' folder")
                            if _get_debug_enabled():
                                self.__logger.debug("Cache folder sent successfully")
                    else:
                        if _get_debug_enabled():
                            self.__logger.debug("No APIs configured, skipping "
                                              "cache folder send")

                    if _get_debug_enabled():
                        self.__logger.debug("Initiating nginx reload")
                    
                    if not self.__reload():
                        success = False
                        if _get_debug_enabled():
                            self.__logger.debug("Nginx reload failed")
                    else:
                        if _get_debug_enabled():
                            self.__logger.debug("Nginx reload successful")
                            
                except Exception as e:
                    success = False
                    self.__logger.error(f"Exception while reloading after "
                                      f"job scheduling: {e}")
                    if _get_debug_enabled():
                        self.__logger.debug(f"Reload exception details:")
                        self.__logger.debug(f"  Exception type: "
                                          f"{type(e).__name__}")
                        self.__logger.debug(f"  Exception message: {str(e)}")
                
                self.__job_reload = False
                if _get_debug_enabled():
                    self.__logger.debug("Reset job_reload flag to False")
            else:
                if _get_debug_enabled():
                    self.__logger.debug("No reload required")

            if pending_jobs:
                self.__logger.info("All scheduled jobs have been executed")

            if _get_debug_enabled():
                self.__logger.debug(f"run_pending returning: {success}")

            return success
        finally:
            # Clean up module paths thread-safely
            if _get_debug_enabled():
                self.__logger.debug("Cleaning up module paths")
            
            with self.__module_paths_lock:
                paths_to_remove = self.__module_paths.copy()
                if _get_debug_enabled():
                    self.__logger.debug(f"Removing {len(paths_to_remove)} "
                                      "module paths from sys.path")
                
                for module_path in paths_to_remove:
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                        if _get_debug_enabled():
                            self.__logger.debug(f"Removed from sys.path: "
                                              f"{module_path}")
                    self.__module_paths.remove(module_path)

                if _get_debug_enabled():
                    self.__logger.debug(f"Module path cleanup complete, "
                                      f"sys.path length: {len(sys_path)}")

            self.__update_cache_permissions()

    def run_once(self, plugins: Optional[List[str]] = None, 
                ignore_plugins: Optional[List[str]] = None) -> bool:
        # Execute all jobs once, optionally filtering by plugin names.
        # 
        # Runs all loaded jobs exactly once, regardless of their scheduling.
        # Supports filtering to include only specific plugins or exclude
        # certain plugins. Handles both synchronous and asynchronous jobs
        # appropriately using thread pools.
        # 
        # Args:
        #     plugins: Optional list of plugin names to include (whitelist)
        #     ignore_plugins: Optional list of plugin names to exclude (blacklist)
        #     
        # Returns:
        #     bool: True if all jobs completed successfully, False otherwise
        if self.try_database_readonly():
            self.__logger.error("Database is in read-only mode, jobs will "
                              "not be executed")
            return True

        if _get_debug_enabled():
            self.__logger.debug(f"Running once with plugins filter: "
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
                    if _get_debug_enabled():
                        self.__logger.debug(f"Skipping plugin '{plugin}' "
                                          "due to filters")
                    continue
                
                for job in jobs:
                    if job.get("async", False):
                        if _get_debug_enabled():
                            self.__logger.debug(f"Running async job "
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
                    if _get_debug_enabled():
                        self.__logger.debug(f"Running {len(jobs_to_run)} "
                                          f"sync jobs from plugin "
                                          f"'{plugin}'")
                    futures.append(self.__executor.submit(self.__run_jobs, 
                                                        jobs_to_run))

            # Wait for all jobs to complete
            if _get_debug_enabled():
                self.__logger.debug(f"Waiting for {len(futures)} futures to complete")
            
            for future in futures:
                future.result()

            if _get_debug_enabled():
                self.__logger.debug(f"All futures completed, final success: "
                                  f"{self.__job_success}")

            return self.__job_success
        finally:
            with self.__module_paths_lock:
                paths_to_remove = self.__module_paths.copy()
                if _get_debug_enabled():
                    self.__logger.debug(f"Cleaning up {len(paths_to_remove)} "
                                      "module paths")
                
                for module_path in paths_to_remove:
                    if module_path in sys_path:
                        sys_path.remove(module_path)
                    self.__module_paths.remove(module_path)

            self.__update_cache_permissions()

    def run_single(self, job_name: str) -> bool:
        # Execute a single job by name.
        # 
        # Searches for a job with the specified name across all loaded
        # plugins and executes it once. Handles locking for thread safety
        # and performs cleanup afterwards. Used for manual job execution
        # or testing individual jobs.
        # 
        # Args:
        #     job_name: Name of the job to execute
        #     
        # Returns:
        #     bool: True if job completed successfully, False otherwise
        if self.try_database_readonly():
            self.__logger.error(f"Database is in read-only mode, single "
                              f"job '{job_name}' will not be executed")
            return True

        if _get_debug_enabled():
            self.__logger.debug(f"Running single job: {job_name}")

        if self.__lock:
            if _get_debug_enabled():
                self.__logger.debug("Acquiring scheduler lock")
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
                        if _get_debug_enabled():
                            self.__logger.debug(f"Found job '{job_name}' "
                                              f"in plugin '{plugin}'")
                        break
                if job_to_run:
                    break

            if not job_plugin or not job_to_run:
                self.__logger.warning(f"Job '{job_name}' not found")
                if _get_debug_enabled():
                    self.__logger.debug(f"Job '{job_name}' not found in "
                                      f"{len(self.__jobs)} plugins")
                    available_jobs = []
                    for plugin, jobs in self.__jobs.items():
                        for job in jobs:
                            available_jobs.append(f"{plugin}.{job['name']}")
                    self.__logger.debug(f"Available jobs: {available_jobs}")
                return False

            if _get_debug_enabled():
                self.__logger.debug(f"Executing single job:")
                self.__logger.debug(f"  Name: {job_to_run['name']}")
                self.__logger.debug(f"  Plugin: {job_plugin}")
                self.__logger.debug(f"  Path: {job_to_run['path']}")
                self.__logger.debug(f"  File: {job_to_run['file']}")

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
                    if _get_debug_enabled():
                        self.__logger.debug(f"Cleaning up {len(paths_to_remove)} "
                                          "module paths after single job")
                    
                    for module_path in paths_to_remove:
                        if module_path in sys_path:
                            sys_path.remove(module_path)
                        self.__module_paths.remove(module_path)

                self.__update_cache_permissions()

            if _get_debug_enabled():
                self.__logger.debug(f"Single job '{job_name}' completed with "
                                  f"success: {self.__job_success}")

            return self.__job_success
        finally:
            if self.__lock:
                if _get_debug_enabled():
                    self.__logger.debug("Releasing scheduler lock")
                self.__lock.release()

    def __run_jobs(self, jobs):
        # Execute a list of jobs sequentially.
        # 
        # Takes a list of job functions and executes them one by one
        # in the current thread. Used for running synchronous jobs
        # that need to be executed in a specific order or thread.
        # 
        # Args:
        #     jobs: List of callable job functions to execute
        if _get_debug_enabled():
            self.__logger.debug(f"Executing {len(jobs)} jobs sequentially")
            self.__logger.debug(f"Thread ID: {threading.current_thread().ident}")
        
        for idx, job in enumerate(jobs):
            if _get_debug_enabled():
                self.__logger.debug(f"Executing job {idx + 1}/{len(jobs)}")
            job()

    def clear(self):
        # Clear all scheduled jobs.
        # 
        # Removes all jobs from the schedule library's job queue.
        # This is typically called during reload operations to
        # reset the scheduling state before setting up new jobs.
        if _get_debug_enabled():
            jobs_before = len(schedule.jobs)
            self.__logger.debug(f"Clearing {jobs_before} scheduled jobs")
        
        schedule.clear()
        
        if _get_debug_enabled():
            self.__logger.debug(f"Schedule cleared, now has "
                              f"{len(schedule.jobs)} jobs")

    def reload(
        self, env: Dict[str, Any], apis: Optional[list] = None, *, 
        changed_plugins: Optional[List[str]] = None, 
        ignore_plugins: Optional[List[str]] = None
    ) -> bool:
        # Reload the scheduler with new environment and plugin configuration.
        # 
        # Performs a complete reload of the job scheduler including environment
        # variables, API connections, and job definitions. Clears existing
        # schedules, updates job registry, runs jobs once, and sets up new
        # schedules. Used when configuration changes are detected.
        # 
        # Args:
        #     env: New environment variables to set
        #     apis: Optional new API endpoint list
        #     changed_plugins: Optional list of plugins that changed (whitelist)
        #     ignore_plugins: Optional list of plugins to ignore (blacklist)
        #     
        # Returns:
        #     bool: True if reload completed successfully, False otherwise
        if _get_debug_enabled():
            self.__logger.debug(f"Reloading scheduler with {len(env)} "
                              f"env vars, changed_plugins: "
                              f"{changed_plugins}, ignore: {ignore_plugins}")
            self.__logger.debug(f"Current APIs: {len(self.apis)}, "
                              f"new APIs: {len(apis or [])}")
        
        try:
            # Update environment
            if _get_debug_enabled():
                self.__logger.debug("Updating environment variables")
            os.environ = self.__base_env.copy()
            os.environ.update(env)  # Update with new environment
            
            # Reinitialize APIs
            if _get_debug_enabled():
                self.__logger.debug("Reinitializing API connections")
            super().__init__(apis or self.apis)
            
            # Clear existing schedules
            if _get_debug_enabled():
                self.__logger.debug("Clearing existing job schedules")
            self.clear()
            
            # Reload job definitions
            if _get_debug_enabled():
                self.__logger.debug("Reloading job definitions from plugins")
            self.update_jobs()
            
            # Run jobs once with filters
            if _get_debug_enabled():
                self.__logger.debug("Running jobs once after reload")
            success = self.run_once(changed_plugins, ignore_plugins)
            
            # Set up new schedules
            if _get_debug_enabled():
                self.__logger.debug("Setting up new job schedules")
            self.setup()
            
            if _get_debug_enabled():
                self.__logger.debug(f"Scheduler reload completed with "
                                  f"success: {success}")
                self.__logger.debug(f"Total scheduled jobs after reload: "
                                  f"{len(schedule.jobs)}")
            
            return success
        except Exception as e:
            self.__logger.error(f"Exception while reloading scheduler: {e}")
            if _get_debug_enabled():
                self.__logger.debug(f"Reload exception details:")
                self.__logger.debug(f"  Exception type: {type(e).__name__}")
                self.__logger.debug(f"  Exception message: {str(e)}")
                import traceback
                self.__logger.debug(f"  Traceback: {traceback.format_exc()}")
            return False

    def try_database_readonly(self, force: bool = False) -> bool:
        # Check if database is in read-only mode and attempt reconnection.
        # 
        # Tests database write capability and attempts to reconnect if in
        # read-only mode. Handles connection retry logic, fallback to
        # read-only databases, and connection timeout management. Uses
        # various connection strategies including fallback URLs.
        # 
        # Args:
        #     force: Whether to force a connection retry regardless of timing
        #     
        # Returns:
        #     bool: True if database is read-only, False if writable
        if _get_debug_enabled():
            self.__logger.debug(f"Checking database readonly status:")
            self.__logger.debug(f"  Current readonly: {self.db.readonly}")
            self.__logger.debug(f"  Force retry: {force}")
            self.__logger.debug(f"  Has database_uri: "
                              f"{bool(getattr(self.db, 'database_uri', None))}")
            last_retry = getattr(self.db, 'last_connection_retry', None)
            self.__logger.debug(f"  Last retry: {last_retry}")
        
        if not self.db.readonly:
            if _get_debug_enabled():
                self.__logger.debug("Database not in readonly mode, testing write")
            
            try:
                self.db.test_write()
                self.db.readonly = False
                if _get_debug_enabled():
                    self.__logger.debug("Write test successful, database is writable")
                return False
            except Exception as e:
                self.db.readonly = True
                if _get_debug_enabled():
                    self.__logger.debug(f"Write test failed: {e}")
                    self.__logger.debug("Setting database to readonly mode")
                return True
        elif (not force and self.db.last_connection_retry and 
              (datetime.now().astimezone() - 
               self.db.last_connection_retry).total_seconds() > 30):
            if _get_debug_enabled():
                last_retry_ago = (datetime.now().astimezone() - 
                                self.db.last_connection_retry).total_seconds()
                self.__logger.debug(f"Last retry was {last_retry_ago:.1f}s ago, "
                                  "within 30s limit, skipping retry")
            return True

        if self.db.database_uri and self.db.readonly:
            if _get_debug_enabled():
                self.__logger.debug("Database has URI and is readonly, "
                                  "attempting reconnection")
            
            try:
                if _get_debug_enabled():
                    self.__logger.debug("Trying read-write connection")
                
                self.db.retry_connection(pool_timeout=1)
                self.db.retry_connection(log=False)
                self.db.readonly = False
                self.__logger.info("The database is no longer read-only, "
                                 "defaulting to read-write mode")
                
                if _get_debug_enabled():
                    self.__logger.debug("Read-write connection successful")
                    
            except Exception as e:
                if _get_debug_enabled():
                    self.__logger.debug(f"Read-write connection failed: {e}")
                    self.__logger.debug("Trying readonly connection")
                
                try:
                    self.db.retry_connection(readonly=True, pool_timeout=1)
                    self.db.retry_connection(readonly=True, log=False)
                    if _get_debug_enabled():
                        self.__logger.debug("Readonly connection successful")
                except Exception as e2:
                    if _get_debug_enabled():
                        self.__logger.debug(f"Readonly connection failed: {e2}")
                    
                    if self.db.database_uri_readonly:
                        if _get_debug_enabled():
                            self.__logger.debug("Trying fallback connection")
                        with suppress(Exception):
                            self.db.retry_connection(fallback=True, 
                                                   pool_timeout=1)
                            self.db.retry_connection(fallback=True, 
                                                   log=False)
                            if _get_debug_enabled():
                                self.__logger.debug("Fallback connection successful")
                    else:
                        if _get_debug_enabled():
                            self.__logger.debug("No fallback URI available")
                
                self.db.readonly = True
                if _get_debug_enabled():
                    self.__logger.debug("Database remains in readonly mode")

        final_readonly = self.db.readonly
        if _get_debug_enabled():
            self.__logger.debug(f"Database readonly check complete: "
                              f"{final_readonly}")
            if hasattr(self.db, 'last_connection_retry'):
                self.__logger.debug(f"Updated last_connection_retry: "
                                  f"{self.db.last_connection_retry}")
        
        return final_readonly