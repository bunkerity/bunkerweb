import schedule, glob, traceback, os, sys, json, subprocess

sys.path.append("/opt/bunkerweb/utils")
from logger import log
from ApiCaller import ApiCaller

class JobScheduler(ApiCaller) :

    def __init__(self, env={}, lock=None, apis=[]) :
        super().__init__(apis)
        self.__env = env
        with open("/tmp/autoconf.env", "w") as f :
            for k, v in self.__env.items() :
                f.write(k + "=" + v + "\n")
        self.__env.update(os.environ)
        self.__jobs = self.__get_jobs()
        self.__lock = lock

    def __get_jobs(self) :
        jobs = {}
        plugins_core = [folder for folder in glob.glob("/opt/bunkerweb/core/*/")]
        plugins_external = [folder for folder in glob.glob("/opt/bunkerweb/plugins/*/")]
        for plugin in plugins_core + plugins_external :
            plugin_name = plugin.split("/")[-2]
            jobs[plugin_name] = []
            try :
                with open(plugin + "/plugin.json") as f :
                    plugin_data = json.loads(f.read())
                    if not "jobs" in plugin_data :
                        continue
                    for job in plugin_data["jobs"] :
                        job["path"] = plugin
                    jobs[plugin_name] = plugin_data["jobs"]
            except :
                log("SCHEDULER", "⚠️", "Exception while getting jobs for plugin " + plugin_name + " : " + traceback.format_exc())
        return jobs

    def __str_to_schedule(self, every) :
        if every == "minute" :
            return schedule.every().minute
        if every == "hour" :
            return schedule.every().hour
        if every == "day" :
            return schedule.every().day
        if every == "week" :
            return schedule.every().week
        raise Exception("can't convert every string \"" + every + "\" to schedule")

    def __reload(self) :
        reload = True
        if os.path.isfile("/usr/sbin/nginx") and os.path.isfile("/opt/bunkerweb/tmp/nginx.pid") :
            log("SCHEDULER", "ℹ️", "Reloading nginx ...")
            proc = subprocess.run(["/usr/sbin/nginx", "-s", "reload"], stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=self.__env)
            reload = proc.returncode != 0
            if reload :
                log("SCHEDULER", "ℹ️", "Successfuly reloaded nginx")
            else :
                log("SCHEDULER", "❌", "Error while reloading nginx")
        else :
            log("SCHEDULER", "ℹ️", "Reloading nginx ...")
            reload = self._send_to_apis("POST", "/reload")
            if reload :
                log("SCHEDULER", "ℹ️", "Successfuly reloaded nginx")
            else :
                log("SCHEDULER", "❌", "Error while reloading nginx")
        return reload
    
    def __gen_conf(self) :
        success = True
        cmd = "/opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/autoconf.env"
        proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if proc.returncode != 0 :
            success = False
        return success

    def __job_wrapper(self, path, plugin, name, file) :
        log("SCHEDULER", "ℹ️", "Executing job " + name + " from plugin " + plugin + " ...")
        success = True
        try :
            proc = subprocess.run(path + "/jobs/" + file, stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=self.__env)
        except :
            log("SCHEDULER", "❌", "Exception while executing job " + name + " from plugin " + plugin + " : " + traceback.format_exc())
            success = False
        if success and proc.returncode >= 2 :
            log("SCHEDULER", "❌", "Error while executing job " + name + " from plugin " + plugin)
            success = False
        elif success and proc.returncode < 2 :
            log("SCHEDULER", "ℹ️", "Successfuly executed job " + name + " from plugin " + plugin)
        return success

    def setup(self) :
        for plugin, jobs in self.__jobs.items() :
            for job in jobs :
                try :
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    every = job["every"]
                    if every != "once" :
                        self.__str_to_schedule(every).do(self.__job_wrapper, path, plugin, name, file)
                except :
                    log("SCHEDULER", "❌", "Exception while scheduling jobs for plugin " + plugin + " : " + traceback.format_exc())

    def run_pending(self) :
        if self.__lock is not None :
            self.__lock.acquire()
        jobs = [job for job in schedule.jobs if job.should_run]
        success = True
        reload = False
        for job in jobs :
            ret = job.run()
            if ret == 1 :
                reload = True
            elif ret >= 2 :
                success = False
        if reload :
            try :
                if len(self._get_apis()) > 0 :
                    log("SCHEDULER", "ℹ️", "Sending /data folder ...")
                    if not self._send_files("/data", "/data") :
                        success = False
                        log("SCHEDULER", "❌", "Error while sending /data folder")
                    else :
                        log("SCHEDULER", "ℹ️", "Successfuly sent /data folder")
                if not self.__reload() :
                    success = False
            except :
                success = False
                log("SCHEDULER", "❌", "Exception while reloading after job scheduling : " + traceback.format_exc())
        if self.__lock is not None :
            self.__lock.release()
        return success

    def run_once(self) :
        ret = True
        for plugin, jobs in self.__jobs.items() :
            for job in jobs :
                try :
                    path = job["path"]
                    name = job["name"]
                    file = job["file"]
                    if self.__job_wrapper(path, plugin, name, file) >= 2 :
                        ret = False
                except :
                    log("SCHEDULER", "❌", "Exception while running once jobs for plugin " + plugin + " : " + traceback.format_exc())
        return ret

    def clear(self) :
        schedule.clear()

    def reload(self, env, apis=[]) :
        ret = True
        try :
            self.__env = env
            super().__init__(apis)
            with open("/tmp/autoconf.env", "w") as f :
                for k, v in self.__env.items() :
                    f.write(k + "=" + v + "\n")
            self.clear()
            self.__jobs = self.__get_jobs()
            if not self.run_once() :
                ret = False
            self.setup()
        except :
            log("SCHEDULER", "❌", "Exception while reloading scheduler " + traceback.format_exc())
            return False
        return ret
