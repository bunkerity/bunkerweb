#!/usr/bin/env python3

import os

from glob import glob
from json import loads
from logging import Logger
from pathlib import Path
from re import compile as re_compile
from typing import Any, Dict, List, Optional, Tuple

import schedule

from sys import path as sys_path
from threading import Lock

# Add dependencies to sys.path
for deps_path in [os.path.join(os.sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",),)]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from logger import getLogger  # type: ignore


class JobScheduler:
    """Thin scheduling orchestrator that dispatches jobs to workers via the API.

    Does NOT execute jobs locally — the API dispatches them to Celery workers.
    Retains only: job discovery from plugin.json files, schedule management,
    environment management, and dispatch calls.
    """

    def __init__(
        self,
        logger: Optional[Logger] = None,
        *,
        api_client=None,
        lock: Optional[Lock] = None,
    ):
        self.__logger = logger or getLogger("SCHEDULER.JOB_SCHEDULER")
        self.api_client = api_client
        self.__base_env = os.environ.copy()
        self.__lock = lock
        self.__compiled_regexes = self.__compile_regexes()
        self.update_jobs()

    def __compile_regexes(self):
        """Precompile regular expressions for job validation."""
        return {
            "name": re_compile(r"^[\w.-]{1,128}$"),
            "file": re_compile(r"^[\w./-]{1,256}$"),
        }

    @property
    def env(self) -> Dict[str, Any]:
        return os.environ.copy()

    @env.setter
    def env(self, env: Dict[str, Any]):
        os.environ = self.__base_env.copy()
        os.environ.update(env)

    def update_jobs(self):
        self.__jobs = self.__get_jobs()

    def __get_jobs(self):
        jobs = {}
        plugin_files = []
        plugin_dirs = [
            os.path.join(os.sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "plugins", "*", "plugin.json"),
            os.path.join(os.sep, "etc", "bunkerweb", "pro", "plugins", "*", "plugin.json"),
        ]

        for pattern in plugin_dirs:
            plugin_files.extend(glob(pattern))

        for plugin_file in plugin_files:
            plugin_name = os.path.basename(os.path.dirname(plugin_file))
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                plugin_jobs = plugin_data.get("jobs", [])
                jobs[plugin_name] = self.__validate_jobs(plugin_jobs, plugin_name, plugin_file)
            except FileNotFoundError:
                self.__logger.warning(f"Plugin file not found: {plugin_file}")
                jobs[plugin_name] = []
            except Exception as e:
                self.__logger.warning(f"Exception while getting jobs for plugin {plugin_name}: {e}")
                jobs[plugin_name] = []

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

            job["path"] = os.path.dirname(plugin_file)
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

    # ── Dispatch helpers ─────────────────────────────────────────────────

    def _build_dispatch_item(self, job: dict, plugin_id: str) -> dict:
        """Build a dispatch payload item from a validated job dict."""
        return {
            "name": job["name"],
            "plugin_id": plugin_id,
            "file": job["file"],
            "path": job["path"],
            "every": job["every"],
            "reload": job.get("reload", False),
            "async": job.get("async", False),
        }

    def dispatch_job(self, job: dict, plugin_id: str) -> Tuple[bool, list]:
        """Dispatch a single job to workers via the API."""
        return self.api_client.dispatch_jobs([self._build_dispatch_item(job, plugin_id)])

    def request_reload(self, test: bool = True) -> bool:
        """Request a reload of all BunkerWeb instances via the API."""
        self.__logger.info("Requesting nginx reload via API ...")
        success = self.api_client.reload_instances(test=test)
        if success:
            self.__logger.info("Successfully requested nginx reload")
        else:
            self.__logger.error("Error while requesting nginx reload")
        return success

    def try_api_readonly(self) -> bool:
        """Check if the API/database is in read-only mode."""
        return self.api_client.readonly

    # ── Schedule management ──────────────────────────────────────────────

    def setup(self):
        """Schedule periodic jobs (not 'once') for dispatch via the API."""
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    every = job["every"]
                    if every != "once":
                        self.__str_to_schedule(every).do(self._dispatch_scheduled_job, job, plugin)
                except Exception as e:
                    self.__logger.error(f"Exception while scheduling job '{job['name']}' for plugin '{plugin}': {e}")

    def _dispatch_scheduled_job(self, job: dict, plugin_id: str):
        """Callback for schedule library — dispatches a single periodic job."""
        self.__logger.info(f"Dispatching scheduled job '{job['name']}' from plugin '{plugin_id}' ...")
        ok, runs = self.dispatch_job(job, plugin_id)
        if not ok:
            self.__logger.error(f"Failed to dispatch scheduled job '{job['name']}' from plugin '{plugin_id}'")

    def run_pending(self) -> bool:
        """Run pending scheduled jobs (dispatches them to workers)."""
        pending_jobs = [job for job in schedule.jobs if job.should_run]

        if not pending_jobs:
            return True

        if self.try_api_readonly():
            self.__logger.error("Database is in read-only mode, pending jobs will not be dispatched")
            return True

        try:
            for job in pending_jobs:
                job.run()
            self.__logger.info("All pending scheduled jobs have been dispatched")
            return True
        except Exception as e:
            self.__logger.error(f"Exception while dispatching pending jobs: {e}")
            return False

    def run_once(self, plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None) -> bool:
        """Dispatch all 'once' jobs (optionally filtered by plugin). Returns True on success."""
        if self.try_api_readonly():
            self.__logger.error("Database is in read-only mode, jobs will not be dispatched")
            return True

        plugins = plugins or []
        dispatch_items = []

        for plugin, jobs in self.__jobs.items():
            if (plugins and plugin not in plugins) or (ignore_plugins and plugin in ignore_plugins):
                continue
            for job in jobs:
                dispatch_items.append(self._build_dispatch_item(job, plugin))

        if not dispatch_items:
            return True

        ok, runs = self.api_client.dispatch_jobs(dispatch_items)
        if not ok:
            self.__logger.error("Failed to dispatch once-jobs")
        return ok

    def run_single(self, job_name: str) -> bool:
        """Dispatch a single job by name. Returns True on success."""
        if self.try_api_readonly():
            self.__logger.error(f"Database is in read-only mode, single job '{job_name}' will not be dispatched")
            return True

        if self.__lock:
            self.__lock.acquire()

        try:
            for plugin, jobs in self.__jobs.items():
                for job in jobs:
                    if job["name"] == job_name:
                        ok, _ = self.dispatch_job(job, plugin)
                        return ok

            self.__logger.warning(f"Job '{job_name}' not found")
            return False
        finally:
            if self.__lock:
                self.__lock.release()

    def clear(self):
        schedule.clear()

    def reload(self, env: Dict[str, Any], *, changed_plugins: Optional[List[str]] = None, ignore_plugins: Optional[List[str]] = None) -> bool:
        """Reload the scheduler: update env, re-discover jobs, dispatch once-jobs, re-schedule periodic."""
        try:
            os.environ = self.__base_env.copy()
            os.environ.update(env)
            self.clear()
            self.update_jobs()
            success = self.run_once(changed_plugins, ignore_plugins)
            self.setup()
            return success
        except Exception as e:
            self.__logger.error(f"Exception while reloading scheduler: {e}")
            return False
