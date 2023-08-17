#!/usr/bin/python3

from copy import deepcopy
from functools import partial
from glob import glob
from io import BytesIO
from json import loads
from logging import Logger
from os import cpu_count, getenv, sep, walk
from os.path import basename, dirname, join
from pathlib import Path
from re import IGNORECASE, compile as re_compile, match
from stat import S_IEXEC
from tarfile import open as tar_open
from time import sleep, time
from typing import Any, Dict, Optional
from subprocess import DEVNULL, STDOUT, run
from sys import path as sys_path
from threading import Lock, Semaphore, Thread
from traceback import format_exc


for deps_path in [
    join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("utils",), ("api",))
]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from croniter import croniter
from requests import Response
from schedule import (
    CancelJob,
    Job,
    clear as schedule_clear,
    every as schedule_every,
    jobs as schedule_jobs,
)

from API import API  # type: ignore
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
        self.__env = env or {}
        self.__jobs = self.__get_jobs()
        self.__lock = lock
        self.__thread_lock = Lock()
        self.__job_success = True
        self.__semaphore = Semaphore(cpu_count() or 1)

        minute_rx = r"[1-5]?\d"
        day_rx = r"(3[01]|[12][0-9]|[1-9])"
        month_rx = r"(1[0-2]|[1-9]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        week_day_rx = r"([0-6]|sun|mon|tue|wed|thu|fri|sat)"
        cron_rx = r"^(?P<minute>(?!,)((^|,)(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?))+)\s(?P<hour>(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?)(,(\*(/\d+)?|{minute_rx}(-{minute_rx}|/\d+)?))*)\s(?P<day>(\*(/\d+)?|{day_rx}(-{day_rx}|/\d+)?)(,(\*(/\d+)?|{day_rx}(-{day_rx}|/\d+)?))*)\s(?P<month>(\*(/\d+)?|{month_rx}(-{month_rx}|/\d+)?)(,(\*(/\d+)?|{month_rx}(-{month_rx}|/\d+)?))*)\s(?P<week_day>(\*(/\d+)?|{week_day_rx}(-{week_day_rx}|/\d+)?)(,(\*(/\d+)?|{week_day_rx}(-{week_day_rx}|/\d+)?))*)$".format(
            minute_rx=minute_rx,
            day_rx=day_rx,
            month_rx=month_rx,
            week_day_rx=week_day_rx,
        )
        self.__cron_rx = re_compile(cron_rx, IGNORECASE)

    @property
    def env(self) -> Dict[str, Any]:
        return self.__env

    def update_env(self):
        retries = 0
        sent = None
        err = None
        status = None
        resp = {}
        while not sent and status != 200 and retries < 3:
            sent, err, status, resp = self.__api.request(
                "GET",
                "/config",
                additonal_headers={
                    "Authorization": f"Bearer {self.__env.get('API_TOKEN')}"
                }
                if "API_TOKEN" in self.__env
                else {},
            )

            if not sent or status != 200:
                self.__logger.warning(
                    f"Could not contact core API. Waiting {self.__env.get('WAIT_RETRY_INTERVAL', 5)} seconds before retrying ...",
                )
                sleep(int(self.__env.get("WAIT_RETRY_INTERVAL", 5)))
                retries += 1
            else:
                self.__logger.info(
                    f"Successfully sent API request to {self.__api.endpoint}config",
                )

        if (not sent or status != 200) and err:
            self.__logger.error(
                f"Could not send core API request to {self.__api.endpoint}config after {retries} retries : {err}, configuration will not work as expected.",
            )
            return

        self.__env.update(resp)

    def update_jobs(self):
        retries = 0
        sent = None
        err = None
        status = None
        resp = {}
        while not sent and status != 200 and retries < 3:
            sent, err, status, resp = self.__api.request(
                "GET",
                "/plugins/external/files",
                additonal_headers={
                    "Authorization": f"Bearer {self.__env.get('API_TOKEN')}"
                }
                if "API_TOKEN" in self.__env
                else {},
            )

            if not sent or status != 200:
                self.__logger.warning(
                    f"Could not contact core API. Waiting {self.__env.get('WAIT_RETRY_INTERVAL', 5)} seconds before retrying ...",
                )
                sleep(int(self.__env.get("WAIT_RETRY_INTERVAL", 5)))
                retries += 1
            else:
                self.__logger.info(
                    f"Successfully sent API request to {self.__api.endpoint}plugins/external/files",
                )

        if (not sent or status != 200) and err:
            self.__logger.error(
                f"Could not send core API request to {self.__api.endpoint}plugins/external/files after {retries} retries : {err}, not all jobs will be available.",
            )
        else:
            try:
                assert isinstance(resp, Response)
            except (AssertionError, AttributeError):
                self.__logger.error(
                    f"Could not get external plugins from core API, not all jobs will be available.",
                )
                return

            EXTERNAL_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)
            with tar_open(mode="r:gz", fileobj=BytesIO(resp.content)) as tar:
                tar.extractall(EXTERNAL_PLUGINS_PATH)

            # Fix potential permission issues
            for root, _, files in walk(str(EXTERNAL_PLUGINS_PATH)):
                for f in files:
                    _path = Path(root, f)
                    st = _path.stat()
                    _path.chmod(st.st_mode | S_IEXEC)

        self.__jobs = self.__get_jobs()

    def __get_jobs(self):
        jobs = {}
        for plugin_file in glob(
            join(sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json")
        ) + glob(  # core plugins
            join(sep, "etc", "bunkerweb", "plugins", "*", "plugin.json")
        ):  # external plugins
            plugin_name = basename(dirname(plugin_file))
            jobs[plugin_name] = []
            try:
                plugin_data = loads(Path(plugin_file).read_text(encoding="utf-8"))
                if not "jobs" in plugin_data:
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
                        self.__logger.warning(
                            f"Invalid reload for job {job['name']} in plugin {plugin_name} (Must be true or false), ignoring job"
                        )
                        plugin_jobs.pop(x)
                        continue

                    plugin_jobs[x]["path"] = dirname(plugin_file)

                jobs[plugin_name] = plugin_jobs
            except FileNotFoundError:
                pass
            except:
                self.__logger.warning(
                    f"Exception while getting jobs for plugin {plugin_name} : {format_exc()}",
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
        start_date = time()
        end_date = None
        ret = -1
        try:
            proc = run(
                join(path, "jobs", file),
                stdin=DEVNULL,
                stderr=STDOUT,
                env=self.__env,
                check=False,
            )
            end_date = time()
            ret = proc.returncode
        except BaseException:
            success = False
            self.__logger.error(
                f"Exception while executing job {name} from plugin {plugin} :\n{format_exc()}",
            )
            with self.__thread_lock:
                self.__job_success = False

        if self.__job_success and ret >= 2:
            success = False
            self.__logger.error(
                f"Error while executing job {name} from plugin {plugin}",
            )
            with self.__thread_lock:
                self.__job_success = False

        Thread(
            target=self.__add_job_run,
            args=(name, success, start_date, end_date or time()),
        ).start()

        return ret

    def __add_job_run(
        self, job_name: str, success: bool, start_date: float, end_date: float
    ):
        sent, err, status, resp = self.__api.request(
            "POST",
            f"/jobs/{job_name}/status",
            data={"success": success, "start_date": start_date, "end_date": end_date},
            additonal_headers={"Authorization": f"Bearer {self.__env.get('API_TOKEN')}"}
            if "API_TOKEN" in self.__env
            else {},
        )

        if not sent:
            self.__logger.error(
                f"Can't send API request to {self.__api.endpoint}jobs/{job_name}/run : {err}, the database will not be updated"
            )
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
                    if self.__cron_rx.match(every):
                        cron = croniter(every, time())
                        next_run = cron.get_next()

                        def job_wrapper():
                            self.__job_wrapper(path, plugin, name, file)
                            nonlocal next_run
                            next_run = cron.get_next()
                            CancelJob()  # Cancel the previous job

                            # Reschedule the job
                            schedule_every(next_run - time.time()).seconds.do(
                                job_wrapper
                            )

                        schedule_every(next_run - time.time()).seconds.do(job_wrapper)
                    elif every != "once":
                        self.__str_to_schedule(every).do(
                            self.__job_wrapper, path, plugin, name, file
                        )
                except:
                    self.__logger.error(
                        f"Exception while scheduling jobs for plugin {plugin} : {format_exc()}",
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

            self.__logger.info(
                f"Job {job.job_func.args[2]} from plugin {job.job_func.args[1]} should run, executing it ..."
            )
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
                plugin_jobs.append(
                    partial(self.__job_wrapper, path, plugin, name, file)
                )

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

            self.__logger.info(
                f"Running job {job.job_func.args[2]} from plugin {job.job_func.args[1]} ..."
            )
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

    def reload(self, env: Dict[str, Any], api: Optional[API] = None) -> bool:
        ret = True
        try:
            self.__env.update(env)
            self.__api = api or self.__api
            self.clear()
            self.update_env()
            self.update_jobs()
            ret = self.run_once()
            self.setup()
        except:
            self.__logger.error(
                f"Exception while reloading scheduler {format_exc()}",
            )
            return False
        return ret
