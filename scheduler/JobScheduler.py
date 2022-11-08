from glob import glob
from json import loads
from logging import Logger
from os import environ, getenv
from subprocess import DEVNULL, PIPE, STDOUT, run
from schedule import (
    clear as schedule_clear,
    every as schedule_every,
    jobs as schedule_jobs,
)
from sys import path as sys_path
from traceback import format_exc

sys_path.append("/opt/bunkerweb/utils")
sys_path.append("/opt/bunkerweb/db")

from Database import Database
from logger import setup_logger
from ApiCaller import ApiCaller


class JobScheduler(ApiCaller):
    def __init__(
        self,
        env={},
        lock=None,
        apis=[],
        logger: Logger = setup_logger("Scheduler", getenv("LOG_LEVEL", "INFO")),
        integration: str = "Linux",
    ):
        super().__init__(apis)
        self.__logger = logger
        self.__integration = integration
        self.__db = Database(self.__logger)
        self.__env = env
        self.__env.update(environ)
        self.__jobs = self.__get_jobs()
        self.__lock = lock

    def __get_jobs(self):
        jobs = {}
        plugins_core = [folder for folder in glob("/opt/bunkerweb/core/*/")]
        plugins_external = [folder for folder in glob("/opt/bunkerweb/plugins/*/")]
        for plugin in plugins_core + plugins_external:
            plugin_name = plugin.split("/")[-2]
            jobs[plugin_name] = []
            try:
                with open(f"{plugin}/plugin.json") as f:
                    plugin_data = loads(f.read())
                    if not "jobs" in plugin_data:
                        continue
                    for job in plugin_data["jobs"]:
                        job["path"] = plugin
                    jobs[plugin_name] = plugin_data["jobs"]
            except:
                self.__logger.warning(
                    f"Exception while getting jobs for plugin {plugin_name} : {format_exc()}",
                )
        return jobs

    def __str_to_schedule(self, every):
        if every == "minute":
            return schedule_every().minute
        if every == "hour":
            return schedule_every().hour
        if every == "day":
            return schedule_every().day
        if every == "week":
            return schedule_every().week
        raise Exception(f"can't convert every string {every} to schedule")

    def __reload(self):
        reload = True
        if self.__integration == "Linux":
            self.__logger.info("Reloading nginx ...")
            proc = run(
                ["/usr/sbin/nginx", "-s", "reload"],
                stdin=DEVNULL,
                stderr=PIPE,
                env=self.__env,
            )
            reload = proc.returncode == 0
            if reload:
                self.__logger.info("Successfuly reloaded nginx")
            else:
                self.__logger.error(
                    f"Error while reloading nginx - returncode: {proc.returncode} - error: {proc.stderr.decode('utf-8')}",
                )
        else:
            self.__logger.info("Reloading nginx ...")
            reload = self._send_to_apis("POST", "/reload")
            if reload:
                self.__logger.info("Successfuly reloaded nginx")
            else:
                self.__logger.error("Error while reloading nginx")
        return reload

    def __job_wrapper(self, path, plugin, name, file):
        self.__logger.info(
            f"Executing job {name} from plugin {plugin} ...",
        )
        success = True
        try:
            proc = run(
                f"{path}/jobs/{file}",
                stdin=DEVNULL,
                stderr=STDOUT,
                env=self.__env,
            )
        except:
            self.__logger.error(
                f"Exception while executing job {name} from plugin {plugin} :\n{format_exc()}",
            )
            success = False
        if success and proc.returncode >= 2:
            self.__logger.error(
                f"Error while executing job {name} from plugin {plugin}",
            )
            success = False
        elif success and proc.returncode < 2:
            err = self.__db.update_job(plugin, name)

            if not err:
                self.__logger.info(
                    f"Successfuly executed job {name} from plugin {plugin} and updated database",
                )
            else:
                self.__logger.warning(
                    f"Successfuly executed job {name} from plugin {plugin} but failed to update database: {err}",
                )

        return success

    def setup(self):
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if every != "once":
                        self.__str_to_schedule(every).do(
                            self.__job_wrapper, path, plugin, name, file
                        )
                except:
                    self.__logger.error(
                        f"Exception while scheduling jobs for plugin {plugin} : {format_exc()}",
                    )

    def run_pending(self):
        if self.__lock is not None:
            self.__lock.acquire()
        jobs = [job for job in schedule_jobs if job.should_run]
        success = True
        reload = False
        for job in jobs:
            ret = job.run()
            if ret == 1:
                reload = True
            elif ret >= 2:
                success = False
        if reload:
            try:
                if len(self._get_apis()) > 0:
                    self.__logger.info("Sending /data/cache folder ...")
                    if not self._send_files("/data/cache", "/cache"):
                        success = False
                        self.__logger.error("Error while sending /data/cache folder")
                    else:
                        self.__logger.info("Successfuly sent /data/cache folder")
                if not self.__reload():
                    success = False
            except:
                success = False
                self.__logger.error(
                    f"Exception while reloading after job scheduling : {format_exc()}",
                )
        if self.__lock is not None:
            self.__lock.release()
        return success

    def run_once(self):
        ret = True
        for plugin, jobs in self.__jobs.items():
            for job in jobs:
                try:
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    if self.__job_wrapper(path, plugin, name, file) >= 2:
                        ret = False
                except:
                    self.__logger.error(
                        f"Exception while running jobs once for plugin {plugin} : {format_exc()}",
                    )

        return ret

    def clear(self):
        schedule_clear()

    def reload(self, env, apis=[]):
        ret = True
        try:
            self.__env = env
            super().__init__(apis)
            self.clear()
            self.__jobs = self.__get_jobs()
            if not self.run_once():
                ret = False
            self.setup()
        except:
            self.__logger.error(
                f"Exception while reloading scheduler {format_exc()}",
            )
            return False
        return ret
