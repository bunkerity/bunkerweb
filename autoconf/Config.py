from traceback import format_exc
from threading import Thread, Lock
from time import sleep
from subprocess import run, DEVNULL, STDOUT
from glob import glob
from shutil import rmtree
from os import makedirs, remove, listdir
from os.path import dirname, isdir
from json import loads

from API import API
from JobScheduler import JobScheduler
from ApiCaller import ApiCaller
from ConfigCaller import ConfigCaller
from logger import log

class Config(ApiCaller, ConfigCaller) :

    def __init__(self, ctrl_type, lock=None) :
        ApiCaller.__init__(self)
        ConfigCaller.__init__(self)
        self.__ctrl_type = ctrl_type
        self.__lock = lock
        self.__instances = []
        self.__services = []
        self.__configs = []
        self.__config = {}
        self.__scheduler = None
        self.__scheduler_thread = None
        self.__schedule = False
        self.__schedule_lock = Lock()

    def __get_full_env(self) :
        env_instances = {}
        for instance in self.__instances :
            for variable, value in instance["env"].items() :
                env_instances[variable] = value
        env_services = {}
        if not "SERVER_NAME" in env_instances :
            env_instances["SERVER_NAME"] = ""
        for service in self.__services :
            for variable, value in service.items() :
                env_services[service["SERVER_NAME"].split(" ")[0] + "_" + variable] = value
            if env_instances["SERVER_NAME"] != "" :
                env_instances["SERVER_NAME"] += " "
            env_instances["SERVER_NAME"] += service["SERVER_NAME"].split(" ")[0]
        return self._full_env(env_instances, env_services)

    def __scheduler_run_pending(self) :
        schedule = True
        while schedule :
            self.__scheduler.run_pending()
            sleep(1)
            self.__schedule_lock.acquire()
            schedule = self.__schedule
            self.__schedule_lock.release()

    def update_needed(self, instances, services, configs=None) :
        if instances != self.__instances :
            return True
        if services != self.__services :
            return True
        if not configs is None and configs != self.__configs :
            return True
        return False

    def __get_config(self) :
        config = {}
        # extract instances variables
        for instance in self.__instances :
            for variable, value in instance["env"].items() :
                config[variable] = value
        # extract services variables
        server_names = []
        for service in self.__services :
            first_server = service["SERVER_NAME"].split(" ")[0]
            server_names.append(first_server)
            for variable, value in service.items() :
                config[first_server + "_" + variable] = value
        config["SERVER_NAME"] = " ".join(server_names)
        return config

    def __get_apis(self) :
        apis = []
        for instance in self.__instances :
            endpoint = "http://" + instance["hostname"] + ":5000"
            host = "bwapi"
            if "API_SERVER_NAME" in instance["env"] :
                host = instance["env"]["API_SERVER_NAME"]
            apis.append(API(endpoint, host=host))
        return apis

    def __write_configs(self) :
        ret = True
        for config_type in self.__configs :
            for file, data in self.__configs[config_type].items() :
                path = "/data/configs/" + config_type + "/" + file
                if not path.endswith(".conf") :
                    path += ".conf"
                makedirs(dirname(path), exist_ok=True)
                try :
                    mode = "w"
                    if type(data) is bytes :
                        mode = "wb"
                    with open(path, mode) as f :
                        f.write(data)
                except :
                    print(format_exc())
                    log("CONFIG", "❌", "Can't save file " + path)
                    ret = False
        return ret

    def __remove_configs(self) :
        ret = True
        for config_type in self.__configs :
            for file, data in self.__configs[config_type].items() :
                path = "/data/configs/" + config_type + "/" + file
                if not path.endswith(".conf") :
                    path += ".conf"
                try :
                    remove(path)
                except :
                    print(format_exc())
                    log("CONFIG", "❌", "Can't remove file " + path)
                    ret = False
        check_empty_dirs = []
        for type in ["server-http", "modsec", "modsec-crs"] :
            check_empty_dirs.extend(glob("/data/configs/" + type + "/*"))
        for check_empty_dir in check_empty_dirs :
            if isdir(check_empty_dir) and len(listdir(check_empty_dir)) == 0 :
                try :
                    rmtree(check_empty_dir)
                except :
                    print(format_exc())
                    log("CONFIG", "❌", "Can't remove directory " + check_empty_dir)
                    ret = False
        return ret

    def apply(self, instances, services, configs=None) :

        success = True

        # stop scheduler just in case caller didn't do it
        self.stop_scheduler()

        # update values
        self.__instances = instances
        self.__services = services
        self.__configs = configs
        self.__config = self.__get_full_env()
        self._set_apis(self.__get_apis())

        # write configs
        if configs != None :
            ret = self.__write_configs()
            if not ret :
                success = False
                log("CONFIG", "❌", "saving custom configs failed, configuration will not work as expected...")

        # get env
        env = self.__get_full_env()

        # run jobs once
        i = 1
        for instance in self.__instances :
            endpoint = "http://" + instance["hostname"] + ":5000"
            host = "bwapi"
            if "API_SERVER_NAME" in instance["env"] :
                host = instance["env"]["API_SERVER_NAME"]
            env["CLUSTER_INSTANCE_" + str(i)] = endpoint + " " + host
            i += 1
        if self.__scheduler is None :
            self.__scheduler = JobScheduler(env=env, lock=self.__lock, apis=self._get_apis())
        ret = self.__scheduler.reload(env, apis=self._get_apis())
        if not ret :
            success = False
            log("CONFIG", "❌", "scheduler.reload() failed, configuration will not work as expected...")
        
        # write config to /tmp/variables.env
        with open("/tmp/variables.env", "w") as f :
            for variable, value in self.__config.items() :
                f.write(variable + "=" + value + "\n")

        # run the generator
        cmd = "python /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env"
        proc = run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
        if proc.returncode != 0 :
            success = False
            log("CONFIG", "❌", "config generator failed, configuration will not work as expected...")
        # cmd = "chown -R root:101 /etc/nginx"
        # run(cmd.split(" "), stdin=DEVNULL, stdout=DEVNULL, stderr=STDOUT)
        # cmd = "chmod -R 770 /etc/nginx" 
        # run(cmd.split(" "), stdin=DEVNULL, stdout=DEVNULL, stderr=STDOUT)

        # send nginx configs
        # send data folder
        # reload nginx
        ret = self._send_files("/etc/nginx", "/confs")
        if not ret :
            success = False
            log("CONFIG", "❌", "sending nginx configs failed, configuration will not work as expected...")
        ret = self._send_files("/data", "/data")
        if not ret :
            success = False
            log("CONFIG", "❌", "sending custom configs failed, configuration will not work as expected...")   
        ret = self._send_to_apis("POST", "/reload")
        if not ret :
            success = False
            log("CONFIG", "❌", "reload failed, configuration will not work as expected...")

        # remove autoconf configs
        if configs != None :
            ret = self.__remove_configs()
            if not ret :
                success = False
                log("CONFIG", "❌", "removing custom configs failed, configuration will not work as expected...")

        return success

    def start_scheduler(self) :
        if self.__scheduler_thread is not None and self.__scheduler_thread.is_alive() :
            raise Exception("scheduler is already running, can't run it twice")
        self.__schedule = True
        self.__scheduler_thread = Thread(target=self.__scheduler_run_pending)
        self.__scheduler_thread.start()

    def stop_scheduler(self) :
        if self.__scheduler_thread is not None and self.__scheduler_thread.is_alive() :
            self.__schedule_lock.acquire()
            self.__schedule = False
            self.__schedule_lock.release()
            self.__scheduler_thread.join()
            self.__scheduler_thread = None

    def reload_scheduler(self, env) :
        if self.__scheduler_thread is None :
            return self.__scheduler.reload(env=env, apis=self._get_apis())

    def __get_scheduler(self, env) :
        self.__schedule_lock.acquire()
        if self.__schedule :
            self.__schedule_lock.release()
            raise Exception("can't create new scheduler, old one is still running...")
        self.__schedule_lock.release()
        return JobScheduler(env=env, lock=self.__lock, apis=self._get_apis())
