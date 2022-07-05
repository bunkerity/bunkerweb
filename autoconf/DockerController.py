import traceback

from docker import DockerClient
from glob import glob
from os.path import basename
from re import search

from Controller import Controller
from ConfigCaller import ConfigCaller
from logger import log

class DockerController(Controller, ConfigCaller) :

    def __init__(self, docker_host) :
        super().__init__("docker")
        ConfigCaller.__init__(self)
        self.__client = DockerClient(base_url=docker_host)

    def _get_controller_instances(self) :
        return self.__client.containers.list(filters={"label" : "bunkerweb.AUTOCONF"})
        
    def _to_instances(self, controller_instance) :
        instance = {}
        instance["name"] = controller_instance.name
        instance["hostname"] = controller_instance.name
        instance["health"] = controller_instance.status == "running" and controller_instance.attrs["State"]["Health"]["Status"] == "healthy"
        instance["env"] = {}
        for env in controller_instance.attrs["Config"]["Env"] :
            variable = env.split("=")[0]
            value = env.replace(variable + "=", "", 1)
            if self._is_setting(variable) :
                instance["env"][variable] = value
        return [instance]

    def _get_controller_services(self) :
        return self.__client.containers.list(filters={"label" : "bunkerweb.SERVER_NAME"})
        
    def _to_services(self, controller_service) :
        service = {}
        for variable, value in controller_service.labels.items() :
            if not variable.startswith("bunkerweb.") :
                continue
            real_variable = variable.replace("bunkerweb.", "", 1)
            if not self._is_multisite_setting(real_variable) :
                continue
            service[real_variable] = value
        return [service]

    def _get_static_services(self) :
        services = []
        variables = {}
        for instance in self.__client.containers.list(filters={"label" : "bunkerweb.AUTOCONF"}) :
            for env in instance.attrs["Config"]["Env"] :
                variable = env.split("=")[0]
                value = env.replace(variable + "=", "", 1)
                variables[variable] = value
        server_names = []
        if "SERVER_NAME" in variables and variables["SERVER_NAME"] != "" :
            server_names = variables["SERVER_NAME"].split(" ")
        for server_name in server_names :
            service = {}
            service["SERVER_NAME"] = server_name
            for variable, value in variables.items() :
                prefix = variable.split("_")[0]
                real_variable = variable.replace(prefix + "_", "", 1)
                if prefix == server_name and self._is_multisite_setting(real_variable) :
                    service[real_variable] = value
            services.append(service)
        return services

    def get_configs(self) :
        configs = {}
        for config_type in self._supported_config_types :
            configs[config_type] = {}
        # get site configs from labels
        for container in self.__client.containers.list(filters={"label" : "bunkerweb.SERVER_NAME"}) :
            # extract server_name
            server_name = ""
            for variable, value in container.labels.items() :
                if not variable.startswith("bunkerweb.") :
                    continue
                real_variable = variable.replace("bunkerweb.", "", 1)
                if real_variable == "SERVER_NAME" :
                    server_name = value.split(" ")[0]
                    break
            # extract configs
            if server_name == "" :
                continue
            for variable, value in container.labels.items() :
                if not variable.startswith("bunkerweb.") :
                    continue
                real_variable = variable.replace("bunkerweb.", "", 1)
                result = search(r"^CUSTOM_CONF_(SERVER_HTTP|MODSEC|MODSEC_CRS)_(.+)$ ", real_variable)
                if result is None :
                    continue
                type = result.group(1).lower().replace("_", "-")
                name = result.group(2)
                configs[type][server_name + "/" + name] = value
        return configs

    def apply_config(self) :
        self._config.stop_scheduler()
        ret = self._config.apply(self._instances, self._services)
        self._config.start_scheduler()
        return ret

    def process_events(self) :
        for event in self.__client.events(decode=True, filters={"type": "container"}) :
            self._instances = self.get_instances()
            self._services = self.get_services()
            self._configs = self.get_configs()
            if not self._config.update_needed(self._instances, self._services, configs=self._configs) :
                continue
            log("DOCKER-CONTROLLER", "ℹ️", "Catched docker event, deploying new configuration ...")
            try :
                ret = self.apply_config()
                if not ret :
                    log("DOCKER-CONTROLLER", "❌", "Error while deploying new configuration")
                else :
                    log("DOCKER-CONTROLLER", "ℹ️", "Successfully deployed new configuration 🚀")
            except :
                log("DOCKER-CONTROLLER", "❌", "Exception while deploying new configuration :")
                print(traceback.format_exc())