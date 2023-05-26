#!/usr/bin/python3

from os import getenv
from typing import Any, Dict, List
from docker import DockerClient
from re import compile as re_compile
from traceback import format_exc

from docker.models.containers import Container
from Controller import Controller
from ConfigCaller import ConfigCaller  # type: ignore
from logger import setup_logger  # type: ignore


class DockerController(Controller, ConfigCaller):
    def __init__(self, docker_host):
        Controller.__init__(self, "docker")
        ConfigCaller.__init__(self)
        self.__client = DockerClient(base_url=docker_host)
        self.__logger = setup_logger("docker-controller", getenv("LOG_LEVEL", "INFO"))
        self.__custom_confs_rx = re_compile(
            r"^bunkerweb.CUSTOM_CONF_(SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$"
        )

    def _get_controller_instances(self) -> List[Container]:
        return self.__client.containers.list(filters={"label": "bunkerweb.INSTANCE"})

    def _get_controller_services(self) -> List[Container]:
        return self.__client.containers.list(filters={"label": "bunkerweb.SERVER_NAME"})

    def _to_instances(self, controller_instance) -> List[dict]:
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

    def _to_services(self, controller_service) -> List[dict]:
        service = {}
        for variable, value in controller_service.labels.items():
            if not variable.startswith("bunkerweb."):
                continue
            real_variable = variable.replace("bunkerweb.", "", 1)
            if not self._is_setting_context(real_variable, "multisite"):
                continue
            service[real_variable] = value
        return [service]

    def _get_static_services(self) -> List[dict]:
        services = []
        variables = {}
        for instance in self.__client.containers.list(
            filters={"label": "bunkerweb.INSTANCE"}
        ):
            if not instance.attrs or not instance.attrs.get("Config", {}).get("Env"):
                continue

            for env in instance.attrs["Config"]["Env"]:
                variable = env.split("=")[0]
                value = env.replace(f"{variable}=", "", 1)
                variables[variable] = value

        if "SERVER_NAME" in variables and variables["SERVER_NAME"].strip():
            for server_name in variables["SERVER_NAME"].strip().split(" "):
                service = {"SERVER_NAME": server_name}
                for variable, value in variables.items():
                    prefix = variable.split("_")[0]
                    real_variable = variable.replace(f"{prefix}_", "", 1)
                    if prefix == server_name and self._is_setting_context(
                        real_variable, "multisite"
                    ):
                        service[real_variable] = value
                services.append(service)
        return services

    def get_configs(self) -> Dict[str, Dict[str, Any]]:
        configs = {config_type: {} for config_type in self._supported_config_types}
        # get site configs from labels
        for container in self.__client.containers.list(
            filters={"label": "bunkerweb.SERVER_NAME"}
        ):
            labels = container.labels  # type: ignore (labels is inside a container)
            if isinstance(labels, list):
                labels = {label: "" for label in labels}

            # extract server_name
            server_name = labels.get("bunkerweb.SERVER_NAME", "").split(" ")[0]

            # extract configs
            if not server_name:
                continue

            for variable, value in labels.items():
                if not variable.startswith("bunkerweb."):
                    continue
                result = self.__custom_confs_rx.search(variable)
                if result is None:
                    continue
                configs[result.group(1).lower().replace("_", "-")][
                    f"{server_name}/{result.group(2)}"
                ] = value
        return configs

    def apply_config(self) -> bool:
        return self._config.apply(
            self._instances, self._services, configs=self._configs
        )

    def process_events(self):
        self._set_autoconf_load_db()
        for _ in self.__client.events(decode=True, filters={"type": "container"}):
            try:
                self._instances = self.get_instances()
                self._services = self.get_services()
                self._configs = self.get_configs()
                if not self._config.update_needed(
                    self._instances, self._services, configs=self._configs
                ):
                    continue
                self.__logger.info(
                    "Caught Docker event, deploying new configuration ..."
                )
                if not self.apply_config():
                    self.__logger.error("Error while deploying new configuration")
                else:
                    self.__logger.info(
                        "Successfully deployed new configuration 🚀",
                    )

                    if not self._config._db.is_autoconf_loaded():
                        ret = self._config._db.set_autoconf_load(True)
                        if ret:
                            self.__logger.warning(
                                f"Can't set autoconf loaded metadata to true in database: {ret}",
                            )
            except:
                self.__logger.error(
                    f"Exception while processing events :\n{format_exc()}"
                )
