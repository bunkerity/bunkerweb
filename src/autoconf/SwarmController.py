from os import getenv
from traceback import format_exc
from threading import Thread, Lock
from docker import DockerClient
from base64 import b64decode

from Controller import Controller
from ConfigCaller import ConfigCaller
from logger import setup_logger


class SwarmController(Controller, ConfigCaller):
    def __init__(self, docker_host):
        super().__init__("swarm")
        ConfigCaller.__init__(self)
        self.__client = DockerClient(base_url=docker_host)
        self.__internal_lock = Lock()
        self.__logger = setup_logger("Swarm-controller", getenv("LOG_LEVEL", "INFO"))

    def _get_controller_instances(self):
        return self.__client.services.list(filters={"label": "bunkerweb.INSTANCE"})

    def _to_instances(self, controller_instance):
        instances = []
        instance_env = {}
        for env in controller_instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"][
            "Env"
        ]:
            variable = env.split("=")[0]
            value = env.replace(f"{variable}=", "", 1)
            if self._is_setting(variable):
                instance_env[variable] = value
        for task in controller_instance.tasks():
            instance = {}
            instance["name"] = task["ID"]
            instance[
                "hostname"
            ] = f"{controller_instance.name}.{task['NodeID']}.{task['ID']}"
            instance["health"] = task["Status"]["State"] == "running"
            instance["env"] = instance_env
            instances.append(instance)
        return instances

    def _get_controller_services(self):
        return self.__client.services.list(filters={"label": "bunkerweb.SERVER_NAME"})

    def _to_services(self, controller_service):
        service = {}
        for variable, value in controller_service.attrs["Spec"]["Labels"].items():
            if not variable.startswith("bunkerweb."):
                continue
            real_variable = variable.replace("bunkerweb.", "", 1)
            if not self._is_multisite_setting(real_variable):
                continue
            service[real_variable] = value
        return [service]

    def _get_static_services(self):
        services = []
        variables = {}
        for instance in self.__client.services.list(
            filters={"label": "bunkerweb.INSTANCE"}
        ):
            for env in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
                variable = env.split("=")[0]
                value = env.replace(f"{variable}=", "", 1)
                variables[variable] = value
        server_names = []
        if "SERVER_NAME" in variables and variables["SERVER_NAME"] != "":
            server_names = variables["SERVER_NAME"].split(" ")
        for server_name in server_names:
            service = {}
            service["SERVER_NAME"] = server_name
            for variable, value in variables.items():
                prefix = variable.split("_")[0]
                real_variable = variable.replace(f"{prefix}_", "", 1)
                if prefix == server_name and self._is_multisite_setting(real_variable):
                    service[real_variable] = value
            services.append(service)
        return services

    def get_configs(self):
        configs = {}
        for config_type in self._supported_config_types:
            configs[config_type] = {}
        for config in self.__client.configs.list(
            filters={"label": "bunkerweb.CONFIG_TYPE"}
        ):
            config_type = config.attrs["Spec"]["Labels"]["bunkerweb.CONFIG_TYPE"]
            config_name = config.name
            if config_type not in self._supported_config_types:
                self.__logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for Config {config_name}",
                )
                continue
            config_site = ""
            if "bunkerweb.CONFIG_SITE" in config.attrs["Spec"]["Labels"]:
                config_site = (
                    f"{config.attrs['Spec']['Labels']['bunkerweb.CONFIG_SITE']}/"
                )
            configs[config_type][f"{config_site}{config_name}"] = b64decode(
                config.attrs["Spec"]["Data"]
            )
        return configs

    def apply_config(self):
        ret = self._config.apply(self._instances, self._services, configs=self._configs)
        return ret

    def __event(self, event_type):
        for event in self.__client.events(decode=True, filters={"type": event_type}):
            self.__internal_lock.acquire()
            self._instances = self.get_instances()
            self._services = self.get_services()
            self._configs = self.get_configs()
            if not self._config.update_needed(
                self._instances, self._services, configs=self._configs
            ):
                self.__internal_lock.release()
                continue
            self.__logger.info(
                "Catched Swarm event, deploying new configuration ...",
            )
            try:
                ret = self.apply_config()
                if not ret:
                    self.__logger.error(
                        "Error while deploying new configuration ...",
                    )
                else:
                    self.__logger.info(
                        "Successfully deployed new configuration 🚀",
                    )

                    if not self._config._db.is_autoconf_loaded():
                        ret = self._config._db.set_autoconf_load(True)
                        if ret:
                            self.__logger.error(
                                f"Can't set autoconf loaded metadata to true in database: {ret}",
                            )
            except:
                self.__logger.error(
                    f"Exception while deploying new configuration :\n{format_exc()}",
                )
            self.__internal_lock.release()

    def process_events(self):
        event_types = ["service", "config"]
        threads = []
        for event_type in event_types:
            threads.append(Thread(target=self.__event, args=(event_type,)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
