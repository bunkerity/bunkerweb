#!/usr/bin/env python3

from time import sleep
from typing import Any, Dict, List
from docker import DockerClient
from re import compile as re_compile
from traceback import format_exc

from docker.models.containers import Container
from docker.errors import DockerException
from Controller import Controller


class DockerController(Controller):
    def __init__(self, docker_host):
        super().__init__("docker")
        self.__client = DockerClient(base_url=docker_host)
        self.__custom_confs_rx = re_compile(r"^bunkerweb.CUSTOM_CONF_(SERVER_STREAM|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(.+)$")

    def _get_controller_containers(self, label_key: str) -> List[Container]:
        """
        Fetch containers based on a specific label and filter them by namespace.

        Args:
            label_key (str): The key of the label to filter containers by (e.g., "bunkerweb.INSTANCE").

        Returns:
            List[Container]: A list of containers matching the label and namespace criteria.
        """
        try:
            # Retrieve containers with the specific label
            containers: List[Container] = self.__client.containers.list(filters={"label": label_key})
        except DockerException as e:
            self._logger.error(f"Failed to retrieve containers with label '{label_key}': {e}")
            return []

        if not self._namespaces:
            return containers

        namespace_set = set(self._namespaces)
        valid_containers = []

        for container in containers:
            try:
                # Safely retrieve and validate labels
                labels = getattr(container, "labels", {})
                if not isinstance(labels, dict):
                    if isinstance(labels, list):
                        labels = {label: "" for label in labels}
                    else:
                        self._logger.warning(f"Unexpected label format for container {container.id}: {labels}")
                        continue

                # Check if the namespace label matches any in the set
                namespace = labels.get("bunkerweb.NAMESPACE", "")
                if namespace in namespace_set:
                    self._logger.debug(f"Container {container.id} matches namespace '{namespace}'.")
                    valid_containers.append(container)
                else:
                    self._logger.debug(f"Container {container.id} does not match any namespace.")

            except AttributeError as e:
                self._logger.warning(f"Container {container.id} missing expected attributes: {e}")
            except Exception as e:
                self._logger.error(f"Unexpected error while processing container {container.id}: {e}")

        return valid_containers

    def _get_controller_instances(self) -> List[Container]:
        """
        Fetch containers labeled as 'bunkerweb.INSTANCE'.
        """
        return self._get_controller_containers(label_key="bunkerweb.INSTANCE")

    def _get_controller_services(self) -> List[Container]:
        """
        Fetch containers labeled as 'bunkerweb.SERVER_NAME'.
        """
        return self._get_controller_containers(label_key="bunkerweb.SERVER_NAME")

    def _to_instances(self, controller_instance) -> List[dict]:
        instance = {
            "name": controller_instance.name,
            "hostname": controller_instance.name,
            "type": "container",
            "health": controller_instance.status == "running" and controller_instance.attrs["State"]["Health"]["Status"] == "healthy",
            "env": {},
        }
        for env in controller_instance.attrs["Config"]["Env"]:
            variable, value = env.split("=", 1)
            instance["env"][variable] = value
        return [instance]

    def _to_services(self, controller_service) -> List[dict]:
        service = {}
        for variable, value in controller_service.labels.items():
            if not variable.startswith("bunkerweb."):
                continue
            service[variable.replace("bunkerweb.", "", 1)] = value
        return [service]

    def get_configs(self) -> Dict[str, Dict[str, Any]]:
        configs = {config_type: {} for config_type in self._supported_config_types}
        # get site configs from labels
        for container in self.__client.containers.list(filters={"label": "bunkerweb.SERVER_NAME"}):
            labels = container.labels  # type: ignore (labels is inside a container)
            if isinstance(labels, list):
                labels = {label: "" for label in labels}

            if self._namespaces and not any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces):
                continue

            # extract server_name
            server_name = labels.get("bunkerweb.SERVER_NAME", "").split(" ")[0]

            # extract configs
            if not server_name:
                continue

            # check if server_name exists
            if not self._is_service_present(server_name):
                self._logger.warning(f"Ignoring config because {server_name} doesn't exist")
                continue

            for variable, value in labels.items():
                if not variable.startswith("bunkerweb."):
                    continue
                result = self.__custom_confs_rx.search(variable)
                if result is None:
                    continue
                configs[result.group(1).lower().replace("_", "-")][f"{server_name}/{result.group(2)}"] = value
        return configs

    def apply_config(self) -> bool:
        return self.apply(self._instances, self._services, configs=self._configs, first=not self._loaded)

    def __process_event(self, event):
        return self._first_start or (
            "Actor" in event
            and "Attributes" in event["Actor"]
            and ("bunkerweb.INSTANCE" in event["Actor"]["Attributes"] or "bunkerweb.SERVER_NAME" in event["Actor"]["Attributes"])
            and (not self._namespaces or any(event["Actor"]["Attributes"].get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces))
        )

    def process_events(self):
        self._set_autoconf_load_db()
        for event in self.__client.events(decode=True, filters={"type": "container"}):
            applied = False
            try:
                if not self.__process_event(event):
                    continue
                self._first_start = False
                to_apply = False
                while not applied:
                    waiting = self.have_to_wait()
                    self._update_settings()
                    self._instances = self.get_instances()
                    self._services = self.get_services()
                    self._configs = self.get_configs()

                    if not to_apply and not self.update_needed(self._instances, self._services, configs=self._configs):
                        applied = True
                        continue

                    to_apply = True
                    if waiting:
                        sleep(1)
                        continue

                    self._logger.info("Caught Docker event, deploying new configuration ...")
                    if not self.apply_config():
                        self._logger.error("Error while deploying new configuration")
                    else:
                        self._logger.info("Successfully deployed new configuration 🚀")

                        self._set_autoconf_load_db()
                    applied = True
            except:
                self._logger.error(f"Exception while processing events :\n{format_exc()}")
