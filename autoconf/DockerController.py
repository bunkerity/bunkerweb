from os import getenv
from docker import DockerClient
from re import search
from traceback import format_exc

from Controller import Controller
from ConfigCaller import ConfigCaller
from logger import setup_logger


class DockerController(Controller, ConfigCaller):
    def __init__(self, docker_host):
        super().__init__("docker")
        ConfigCaller.__init__(self)
        self.__client = DockerClient(base_url=docker_host)
        self.__logger = setup_logger("docker-controller", getenv("LOG_LEVEL", "INFO"))

    def _get_controller_instances(self):
        return self.__client.containers.list(filters={"label": "bunkerweb.INSTANCE"})

    def _to_instances(self, controller_instance):
        instance = {}
        instance["name"] = controller_instance.name
        instance["hostname"] = controller_instance.name
        instance["health"] = (
            controller_instance.status == "running"
            and controller_instance.attrs["State"]["Health"]["Status"] == "healthy"
        )
        instance["env"] = {}
        for env in controller_instance.attrs["Config"]["Env"]:
            variable = env.split("=")[0]
            value = env.replace(f"{variable}=", "", 1)
            if self._is_setting(variable):
                instance["env"][variable] = value
        return [instance]

    def _get_controller_services(self):
        return self.__client.containers.list(filters={"label": "bunkerweb.SERVER_NAME"})

    def _to_services(self, controller_service):
        service = {}
        for variable, value in controller_service.labels.items():
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
        for instance in self.__client.containers.list(
            filters={"label": "bunkerweb.INSTANCE"}
        ):
            for env in instance.attrs["Config"]["Env"]:
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
        # get site configs from labels
        for container in self.__client.containers.list(
            filters={"label": "bunkerweb.SERVER_NAME"}
        ):
            # extract server_name
            server_name = ""
            for variable, value in container.labels.items():
                if not variable.startswith("bunkerweb."):
                    continue
                real_variable = variable.replace("bunkerweb.", "", 1)
                if real_variable == "SERVER_NAME":
                    server_name = value.split(" ")[0]
                    break
            # extract configs
            if server_name == "":
                continue
            for variable, value in container.labels.items():
                if not variable.startswith("bunkerweb."):
                    continue
                real_variable = variable.replace("bunkerweb.", "", 1)
                result = search(
                    r"^CUSTOM_CONF_(SERVER_HTTP|MODSEC|MODSEC_CRS)_(.+)$", real_variable
                )
                if result is None:
                    continue
                cfg_type = result.group(1).lower().replace("_", "-")
                cfg_name = result.group(2)
                configs[cfg_type][f"{server_name}/{cfg_name}"] = value
        return configs

    def apply_config(self):
        ret = self._config.apply(self._instances, self._services, configs=self._configs)
        return ret

    def process_events(self):
        for event in self.__client.events(decode=True, filters={"type": "container"}):
            self._instances = self.get_instances()
            self._services = self.get_services()
            self._configs = self.get_configs()
            if not self._config.update_needed(
                self._instances, self._services, configs=self._configs
            ):
                continue
            self.__logger.info(
                "Catched docker event, deploying new configuration ...",
            )
            try:
                ret = self.apply_config()
                if not ret:
                    self.__logger.error(
                        "Error while deploying new configuration",
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
