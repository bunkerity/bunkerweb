#!/usr/bin/python3

from time import sleep
from typing import Any, Dict, List, Literal, Optional
from re import compile as re_compile

from API import API  # type: ignore
from Controller import Controller

from docker import DockerClient
from docker.models.containers import Container


class DockerController(Controller):
    def __init__(
        self,
        docker_host: str,
        core_api: API,
        log_level: str = "INFO",
        *,
        api_token: Optional[str] = None,
        wait_retry_interval: int = 5,
    ):
        super().__init__(
            "docker",
            core_api,
            log_level=log_level,
            api_token=api_token,
            wait_retry_interval=wait_retry_interval,
        )
        self.__client = DockerClient(base_url=docker_host)
        self.__custom_confs_rx = re_compile(
            r"^bunkerweb.CUSTOM_CONF_(SERVER_HTTP|MODSEC_CRS|MODSEC)_(.+)$"
        )
        self.__env_rx = re_compile(r"^(?![#\s])([^=]+)=([^\n]*)$")

    def _get_controller_instances(self) -> List[Container]:
        return self.__client.containers.list(filters={"label": "bunkerweb.INSTANCE"})  # type: ignore

    def _get_controller_services(self) -> List[Container]:
        return self.__client.containers.list(filters={"label": "bunkerweb.SERVER_NAME"})  # type: ignore

    def _to_instances(
        self, controller_instance: Container
    ) -> List[Dict[Literal["name", "hostname", "health", "env"], Any]]:
        instance: Dict[Literal["name", "hostname", "health", "env"], Any] = {
            "name": controller_instance.name,
            "hostname": controller_instance.name,
            "health": (
                controller_instance.status == "running"
                and controller_instance.attrs.get("State", {})  # type: ignore
                .get("Health", {})
                .get("Status")
                == "healthy"
            ),
            "env": {},
        }
        for env in controller_instance.attrs.get("Config", {}).get("Env", []):  # type: ignore
            match = self.__env_rx.search(env)
            if match is None:
                continue
            groups = match.groups()
            if self._is_setting(groups[0]):
                instance["env"][groups[0]] = groups[1]
        return [instance]

    def _to_services(self, controller_service) -> List[Dict[str, str]]:
        service = {}
        for variable, value in controller_service.labels.items():
            if not variable.startswith("bunkerweb."):
                continue
            real_variable = variable.replace("bunkerweb.", "", 1)
            if not self._is_setting_context(real_variable, "multisite"):
                continue
            service[real_variable] = value
        return [service]

    def _get_static_services(self) -> List[Dict[str, str]]:
        services = []
        variables = {}
        for instance in self.__client.containers.list(
            filters={"label": "bunkerweb.INSTANCE"}
        ):
            for env in instance.attrs.get("Config", {}).get("Env", []):  # type: ignore
                match = self.__env_rx.search(env)
                if match is None:
                    continue
                groups = match.groups()
                variables[groups[0]] = groups[1]

        if variables.get("SERVER_NAME", "").strip():
            for server_name in variables["SERVER_NAME"].strip().split():
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
            server_name = labels.get("bunkerweb.SERVER_NAME", "").strip().split()[0]

            if not server_name:
                continue

            # extract configs
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
        return self.apply(self._instances, self._services, configs=self._configs)

    def process_events(self):
        for _ in self.__client.events(decode=True, filters={"type": "container"}):
            try:
                self._instances = self.get_instances()
                self._services = self.get_services()
                self._configs = self.get_configs()
                if not self.update_needed(
                    self._instances, self._services, configs=self._configs
                ):
                    sleep(1)
                    continue
                self._logger.info(
                    "🐳 Caught Docker event, deploying new configuration ..."
                )
                if not self.apply_config():
                    self._logger.error("Error while deploying new configuration")
                    continue
                self._logger.info(
                    "Successfully deployed new configuration 🚀",
                )
            except:
                self._logger.exception("Exception while processing events")
