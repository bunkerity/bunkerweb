#!/usr/bin/python3
# -*- coding: utf-8 -*-

from copy import deepcopy
from functools import partial
from glob import glob
from json import loads
from logging import Logger
from os import cpu_count, getenv, sep
from os.path import basename, dirname, join
from pathlib import Path
from re import match
from time import sleep, time
from typing import Any, Dict, Optional
from subprocess import DEVNULL, STDOUT, run
from sys import path as sys_path
from threading import Lock, Semaphore, Thread


from croniter import croniter
from schedule import CancelJob, Job, clear as schedule_clear, every as schedule_every, jobs as schedule_jobs

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("api",), ("utils",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from API import API  # type: ignore
from jobs import CRON_RX  # type: ignore
from logger import setup_logger  # type: ignore

EXTERNAL_PLUGINS_PATH = Path(sep, "etc", "bunkerweb", "plugins")


class JobScheduler:
    def __init__(
        self,
        api: API,
        env: Optional[Dict[str, Any]] = None,
        logger: Optional[Logger] = None,
        *,
        lock: Optional[Lock] = None,
    ):
        self.__logger = logger or setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO"))
        self.__api = api
        self.__env = {k: v for k, v in env.items() if isinstance(v, str)} if env else {}
        self.__jobs = self.__get_jobs()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__semaphore = Semaphore(cpu_count() or 1)

    @property
    def env(self) -> Dict[str, Any]:
        return self.__env

    @env.setter
    def env(self, env: Dict[str, Any]):
        self.__env = {k: v for k, v in env.items() if isinstance(v, str)}

    def __get_jobs(self):
        jobs = {}
        for plugin_file in glob(join(sep, "usr", "share", "bunkerweb", "core_plugins", "*", "plugin.json")) + glob(join(sep, "etc", "bunkerweb", "plugins", "*", "plugin.json")):  # core plugins  # external plugins
            plugin_name = basename(dirname(plugin_file))
            jobs[plugin_name] = []
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                if "jobs" not in plugin_data:
                    continue

                plugin_jobs = plugin_data["jobs"]

                for x, job in enumerate(deepcopy(plugin_jobs)):
                    if not all(
                        key in job.keys()
                        for key in (
                            "name",
                            "file",
                            "every",
                            "reload",
                        )
                    ):
                        self.__logger.warning(f"missing keys for job {job['name']} in plugin {plugin_name}, must have name, file, every and reload, ignoring job")
                        plugin_jobs.pop(x)
                        continue

                    if not match(r"^[\w.-]{1,128}$", job["name"]):
                        self.__logger.warning(f"Invalid name for job {job['name']} in plugin {plugin_name} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 128)), ignoring job")
                        plugin_jobs.pop(x)
                        continue
                    elif not match(r"^[\w./-]{1,256}$", job["file"]):
                        self.__logger.warning(f"Invalid file for job {job['name']} in plugin {plugin_name} (Can only contain numbers, letters, underscores, hyphens and slashes (min 1 characters and max 256)), ignoring job")
                        plugin_jobs.pop(x)
                        continue
                    elif job["every"] not in ("once", "minute", "hour", "day", "week"):
                        self.__logger.warning(f"Invalid every for job {job['name']} in plugin {plugin_name} (Must be once, minute, hour, day or week), ignoring job")
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
                self.__logger.exception(
                    f"Exception while getting jobs for plugin {plugin_name}",
                )
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

        raise ValueError(f"Can't convert string {every} to schedule")

    def __job_wrapper(self, path: str, plugin: str, name: str, file: str) -> int:
        self.__logger.info(
            f"Executing job {name} from plugin {plugin} ...",
        )
        success = True
        ret = -1
        start_date = time()
        try:
            proc = run(
                join(path, "jobs", file),
                stdin=DEVNULL,
                stderr=STDOUT,
                env=self.__env,
                check=False,
            )
            ret = proc.returncode
        except BaseException:
            success = False
            self.__logger.exception(f"Exception while executing job {name} from plugin {plugin}")
            with self.__thread_lock:
                self.__job_success = False
        end_date = time()

        if self.__job_success and ret >= 2:
            success = False
            self.__logger.error(
                f"Error while executing job {name} from plugin {plugin}",
            )
            with self.__thread_lock:
                self.__job_success = False

        Thread(target=self.__add_job_run, args=(name, success, start_date, end_date)).start()

        return ret

    def __add_job_run(self, job_name: str, success: bool, start_date: float, end_date: float):
        sent, err, status, resp = self.__api.request(
            "POST",
            f"/jobs/{job_name}/status?method=core",
            data={"success": success, "start_date": start_date, "end_date": end_date},
            additonal_headers={"Authorization": f"Bearer {self.__env.get('CORE_TOKEN')}"} if "CORE_TOKEN" in self.__env else {},
        )

        if not sent:
            self.__logger.error(f"Can't send API request to {self.__api.endpoint}jobs/{job_name}/run : {err}, the database will not be updated")
        elif status == 503:
            retry_after = resp.headers.get("Retry-After", 1)
            retry_after = float(retry_after)
            self.__logger.warning(f"Can't send API request to {self.__api.endpoint}jobs/{job_name}/run : status = {status}, resp = {resp}, retrying in {retry_after} seconds")
            sleep(retry_after)
            Thread(
                target=self.__add_job_run,
                args=(job_name, success, start_date, end_date),
            ).start()
        elif status != 201:
            self.__logger.error(
                f"Error while sending API request to {self.__api.endpoint}jobs/{job_name}/run : status = {status}, resp = {resp}, the database will not be updated",
            )

    def setup(self):
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if CRON_RX.match(every):
                        cron = croniter(every, time())
                        next_run = cron.get_next()

                        def job_wrapper():
                            self.__job_wrapper(path, plugin, name, file)
                            nonlocal next_run
                            next_run = cron.get_next()
                            CancelJob()  # Cancel the previous job

                            # Reschedule the job
                            schedule_every(next_run - time.time()).seconds.do(job_wrapper)

                        schedule_every(next_run - time.time()).seconds.do(job_wrapper)
                    elif every != "once":
                        self.__str_to_schedule(every).do(self.__job_wrapper, path, plugin, name, file)
                except:
                    self.__logger.exception(
                        f"Exception while scheduling jobs for plugin {plugin}",
                    )

    def run_pending(self) -> bool:
        if self.__lock:
            self.__lock.acquire()

        success = True
        for job in schedule_jobs:
            if not job.should_run:
                continue

            try:
                assert job.job_func
            except (AssertionError, AttributeError):
                self.__logger.error(f"Job {job} has no job_func attribute, ignoring it")
                continue

            self.__logger.info(f"Job {job.job_func.args[2]} from plugin {job.job_func.args[1]} should run, executing it ...")
            ret = job.run()

            if not isinstance(ret, int):
                ret = -1

            if ret < 0 or ret >= 2:
                success = False

        if self.__lock:
            self.__lock.release()
        return success

    def run_once(self) -> bool:
        threads = []
        for plugin, jobs in self.__jobs.items():
            plugin_jobs = []

            for job in jobs:
                path = job["path"]
                name = job["name"]
                file = job["file"]

                # Add job to the list of jobs to run in the order they are defined
                plugin_jobs.append(partial(self.__job_wrapper, path, plugin, name, file))

            # Create a thread for each plugin
            threads.append(Thread(target=self.__run_in_thread, args=(plugin_jobs,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        ret = self.__job_success is True
        self.__job_success = True

        return ret

    def run_single(self, job_name: str) -> bool:
        if self.__lock:
            self.__lock.acquire()

        success = True
        for job in schedule_jobs:
            try:
                assert job.job_func
            except (AssertionError, AttributeError):
                self.__logger.error(f"Job {job} has no job_func attribute, ignoring it")
                continue

            if job.job_func.args[2] != job_name:
                continue

            self.__logger.info(f"Running job {job.job_func.args[2]} from plugin {job.job_func.args[1]} ...")
            ret = job.run()

            if not isinstance(ret, int):
                ret = -1

            if ret < 0 or ret >= 2:
                success = False

            break

        if self.__lock:
            self.__lock.release()
        return success

    def __run_in_thread(self, jobs: list):
        self.__semaphore.acquire(timeout=60)
        for job in jobs:
            job()
        self.__semaphore.release()

    def clear(self):
        schedule_clear()

    def reload(self, env: Dict[str, Any], api: Optional[API] = None, *, run: bool = True) -> bool:
        ret = True
        try:
            self.__env.update({k: v for k, v in env.items() if isinstance(v, str)})
            self.__api = api or self.__api
            self.clear()
            self.__jobs = self.__get_jobs()
            if run:
                ret = self.run_once()
            self.setup()
        except:
            self.__logger.exception("Exception while reloading scheduler")
            return False
        return ret
