#!/usr/bin/env python3

from copy import deepcopy
from functools import partial
from glob import glob
from json import loads
from logging import Logger
from os import cpu_count, environ, getenv, sep
from os.path import basename, dirname, join
from pathlib import Path
from re import match
from typing import Any, Dict, Optional
from schedule import (
    Job,
    clear as schedule_clear,
    every as schedule_every,
    jobs as schedule_jobs,
)
from subprocess import DEVNULL, PIPE, STDOUT, run
from sys import path as sys_path
from threading import Lock, Semaphore, Thread
from traceback import format_exc

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore
from ApiCaller import ApiCaller  # type: ignore
from API import API  # type: ignore


class JobScheduler(ApiCaller):
    def __init__(
        self,
        env: Optional[Dict[str, Any]] = None,
        logger: Optional[Logger] = None,
        integration: str = "Linux",
        *,
        db: Optional[Database] = None,
        lock: Optional[Lock] = None,
        apis: Optional[list] = None,
    ):
        super().__init__(apis or [])
        self.__logger = logger or setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))
        self.__integration = integration
        self.__db = db or Database(self.__logger)
        self.__env = env or {}
        self.__env.update(environ)
        self.__jobs = self.__get_jobs()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__job_reload = False
        self.__semaphore = Semaphore(cpu_count() or 1)

    @property
    def env(self) -> Dict[str, Any]:
        return self.__env

    @env.setter
    def env(self, env: Dict[str, Any]):
        self.__env = env

    def set_integration(self, integration: str):
        self.__integration = integration

    def auto_setup(self):
        super().auto_setup(bw_integration=self.__integration)

    def update_instances(self):
        super(JobScheduler, type(self)).apis.fset(self, self.__get_apis())

    def __get_apis(self):
        apis = []
        try:
            with self.__thread_lock:
                instances = self.__db.get_instances()
            for instance in instances:
                api = API(f"http://{instance['hostname']}:{instance['port']}", host=instance["server_name"])
                apis.append(api)
        except:
            self.__logger.warning(f"Exception while getting jobs instances : {format_exc()}")
        return apis

    def update_jobs(self):
        self.__jobs = self.__get_jobs()

    def __get_jobs(self):
        jobs = {}
        for plugin_file in (
            glob(join(sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json"))
            + glob(join(sep, "etc", "bunkerweb", "plugins", "*", "plugin.json"))
            + glob(join(sep, "etc", "bunkerweb", "pro", "plugins", "*", "plugin.json"))
        ):  # core plugins  # external plugins # pro plugins
            plugin_name = basename(dirname(plugin_file))
            jobs[plugin_name] = []
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                if "jobs" not in plugin_data:
                    continue

                plugin_jobs = plugin_data["jobs"]

                for x, job in enumerate(deepcopy(plugin_jobs)):
                    if not all(key in job.keys() for key in ("name", "file", "every", "reload")):
                        self.__logger.warning(
                            f"missing keys for job {job['name']} in plugin {plugin_name}, must have name, file, every and reload, ignoring job"
                        )
                        plugin_jobs.pop(x)
                        continue

                    if not match(r"^[\w.-]{1,128}$", job["name"]):
                        self.__logger.warning(
                            f"Invalid name for job {job['name']} in plugin {plugin_name} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 128)), ignoring job"
                        )
                        plugin_jobs.pop(x)
                        continue
                    elif not match(r"^[\w./-]{1,256}$", job["file"]):
                        self.__logger.warning(
                            f"Invalid file for job {job['name']} in plugin {plugin_name} (Can only contain numbers, letters, underscores, hyphens and slashes (min 1 characters and max 256)), ignoring job"
                        )
                        plugin_jobs.pop(x)
                        continue
                    elif job["every"] not in ("once", "minute", "hour", "day", "week"):
                        self.__logger.warning(
                            f"Invalid every for job {job['name']} in plugin {plugin_name} (Must be once, minute, hour, day or week), ignoring job"
                        )
                        plugin_jobs.pop(x)
                        continue
                    elif job["reload"] is not True and job["reload"] is not False:
                        self.__logger.warning(f"Invalid reload for job {job['name']} in plugin {plugin_name} (Must be true or false), ignoring job")
                        plugin_jobs.pop(x)
                        continue

                    plugin_jobs[x]["path"] = dirname(plugin_file)

                jobs[plugin_name] = plugin_jobs
            except FileNotFoundError:
                pass
            except:
                self.__logger.warning(f"Exception while getting jobs for plugin {plugin_name} : {format_exc()}")
        return jobs

    def __str_to_schedule(self, every: str) -> Job:
        if every == "minute":
            return schedule_every().minute
        elif every == "hour":
            return schedule_every().hour
        elif every == "day":
            return schedule_every().day
        elif every == "week":
            return schedule_every().week
        raise ValueError(f"can't convert string {every} to schedule")

    def __reload(self) -> bool:
        reload = True
        if self.__integration not in ("Autoconf", "Swarm", "Kubernetes", "Docker"):
            self.__logger.info("Reloading nginx ...")
            proc = run([join(sep, "usr", "sbin", "nginx"), "-s", "reload"], stdin=DEVNULL, stderr=PIPE, env=self.__env, check=False)
            reload = proc.returncode == 0
            if reload:
                self.__logger.info("Successfully reloaded nginx")
            else:
                self.__logger.error(
                    f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stderr.decode() if proc.stderr else 'Missing stderr'}"
                )
        else:
            self.__logger.info("Reloading nginx ...")
            reload = self.send_to_apis("POST", "/reload")
            if reload:
                self.__logger.info("Successfully reloaded nginx")
            else:
                self.__logger.error("Error while reloading nginx")
        return reload

    def __job_wrapper(self, path: str, plugin: str, name: str, file: str) -> int:
        self.__logger.info(f"Executing job {name} from plugin {plugin} ...")
        success = True
        ret = -1
        try:
            proc = run(join(path, "jobs", file), stdin=DEVNULL, stderr=STDOUT, env=self.__env, check=False)
            ret = proc.returncode
        except BaseException:
            success = False
            self.__logger.error(f"Exception while executing job {name} from plugin {plugin} :\n{format_exc()}")
            with self.__thread_lock:
                self.__job_success = False

        if ret == 1:
            with self.__thread_lock:
                self.__job_reload = True

        if self.__job_success and (ret < 0 or ret >= 2):
            success = False
            self.__logger.error(f"Error while executing job {name} from plugin {plugin}")
            with self.__thread_lock:
                self.__job_success = False

        Thread(target=self.__update_job, args=(plugin, name, success)).start()

        return ret

    def __update_job(self, plugin: str, name: str, success: bool):
        with self.__thread_lock:
            err = self.__db.update_job(plugin, name, success)

        if not err:
            self.__logger.info(f"Successfully updated database for the job {name} from plugin {plugin}")
        else:
            self.__logger.warning(f"Failed to update database for the job {name} from plugin {plugin}: {err}")

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
                except:
                    self.__logger.error(f"Exception while scheduling jobs for plugin {plugin} : {format_exc()}")

    def run_pending(self) -> bool:
        threads = []
        self.__job_success = True
        self.__job_reload = False

        for job in schedule_jobs:
            if not job.should_run:
                continue
            threads.append(Thread(target=self.__run_in_thread, args=((job.run,),)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        success = self.__job_success
        self.__job_success = True

        if self.__job_reload:
            try:
                if self.apis:
                    cache_path = join(sep, "var", "cache", "bunkerweb")
                    self.__logger.info(f"Sending {cache_path} folder ...")
                    if not self.send_files(cache_path, "/cache"):
                        success = False
                        self.__logger.error(f"Error while sending {cache_path} folder")
                    else:
                        self.__logger.info(f"Successfully sent {cache_path} folder")

                if not self.__reload():
                    success = False
            except BaseException:
                success = False
                self.__logger.error(f"Exception while reloading after job scheduling : {format_exc()}")
            self.__job_reload = False

        if threads:
            self.__logger.info("All scheduled jobs have been executed")

        return success

    def run_once(self) -> bool:
        threads = []
        self.__job_success = True
        self.__job_reload = False

        for plugin, jobs in self.__jobs.items():
            # Add job to the list of jobs to run in the order they are defined
            jobs_jobs = [partial(self.__job_wrapper, job["path"], plugin, job["name"], job["file"]) for job in jobs]

            # Create a thread for each plugin
            threads.append(Thread(target=self.__run_in_thread, args=(jobs_jobs,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        ret = self.__job_success
        self.__job_success = True

        return ret

    def run_single(self, job_name: str) -> bool:
        if self.__lock:
            self.__lock.acquire()

        job_plugin = ""
        job_to_run = None
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                if job["name"] == job_name:
                    job_plugin = plugin
                    job_to_run = job
                    break

        if not job_plugin or not job_to_run:
            self.__logger.warning(f"Job {job_name} not found")
            return False

        self.__job_wrapper(job_to_run["path"], job_plugin, job_to_run["name"], job_to_run["file"])

        if self.__lock:
            self.__lock.release()
        return self.__job_success

    def __run_in_thread(self, jobs: list):
        self.__semaphore.acquire(timeout=60)
        for job in jobs:
            job()
        self.__semaphore.release()

    def clear(self):
        schedule_clear()

    def reload(self, env: Dict[str, Any], apis: Optional[list] = None) -> bool:
        ret = True
        try:
            self.__env = env
            super().__init__(apis or self.apis)
            self.clear()
            self.__jobs = self.__get_jobs()
            ret = self.run_once()
            self.setup()
        except:
            self.__logger.error(f"Exception while reloading scheduler {format_exc()}")
            return False
        return ret
