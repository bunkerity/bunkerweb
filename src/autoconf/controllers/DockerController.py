#!/usr/bin/env python3

from os import getenv
from contextlib import suppress
from time import sleep, time
from typing import Any, Dict, List
from threading import Lock
from docker import DockerClient
from re import compile as re_compile, split as re_split
from traceback import format_exc

from docker.models.containers import Container
from docker.errors import DockerException
from controllers.Controller import Controller


class DockerController(Controller):
    def __init__(self, docker_host):
        super().__init__("docker")
        self.__client = DockerClient(base_url=docker_host)
        self.__internal_lock = Lock()
        self.__pending_apply = False
        self.__last_event_time = 0.0
        self.__debounce_delay = 2  # seconds
        self.__custom_confs_rx = re_compile(r"^bunkerweb.CUSTOM_CONF_(SERVER_STREAM|SERVER_HTTP|MODSEC_CRS|MODSEC|CRS_PLUGINS_BEFORE|CRS_PLUGINS_AFTER)_(.+)$")
        self.__ignored_labels_exact = set()
        self.__ignored_label_suffixes = set()
        ignore_labels = getenv("DOCKER_IGNORE_LABELS", "")
        if ignore_labels:
            tokens = [token.strip() for token in re_split(r"[,\s]+", ignore_labels) if token.strip()]
            for token in tokens:
                if "." in token:
                    self.__ignored_labels_exact.add(token)
                    if token.startswith("bunkerweb."):
                        suffix = token.split(".", 1)[1]
                        if suffix:
                            self.__ignored_label_suffixes.add(suffix)
                else:
                    self.__ignored_label_suffixes.add(token)
                    self.__ignored_labels_exact.add(f"bunkerweb.{token}")

            self._logger.info("Ignoring Docker labels while collecting instances: " + ", ".join(sorted(self.__ignored_labels_exact)))

    def __should_ignore_label(self, label: str) -> bool:
        if label in self.__ignored_labels_exact:
            return True
        if label.removeprefix("bunkerweb.") in self.__ignored_label_suffixes:
            return True
        return False

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

        namespace_set = set(self._namespaces or [])
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

                if namespace_set:
                    namespace = labels.get("bunkerweb.NAMESPACE", "")
                    if namespace not in namespace_set:
                        self._logger.debug(f"Container {container.id} does not match any namespace.")
                        continue

                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping container {getattr(container, 'name', container.id)} because of ignored labels")
                    continue

                valid_containers.append(container)

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
            if self.__should_ignore_label(variable):
                continue
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
            if not isinstance(labels, dict):
                self._logger.warning(f"Unexpected label format for container {container.id}: {labels}")
                continue

            if any(self.__should_ignore_label(label) for label in labels):
                self._logger.info(f"Skipping container {getattr(container, 'name', container.id)} while collecting configs because of ignored labels")
                continue

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
                if self.__should_ignore_label(variable):
                    continue
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
        if self._first_start:
            return True

        attributes = event.get("Actor", {}).get("Attributes")
        if not isinstance(attributes, dict):
            return False

        has_instance_label = "bunkerweb.INSTANCE" in attributes or "bunkerweb.SERVER_NAME" in attributes
        if not has_instance_label:
            return False

        if self._namespaces and not any(attributes.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces):
            self._logger.info(
                f"Skipping Docker event for {attributes.get('name') or attributes.get('container')} because its namespace is not in the allowed namespaces"
            )
            return False

        if any(self.__should_ignore_label(label) for label in attributes):
            self._logger.info(f"Skipping Docker event for {attributes.get('name') or attributes.get('container')} because of ignored labels")
            return False

        return True

    def process_events(self):
        self._set_autoconf_load_db()
        locked = False
        error = False
        applied = False
        while True:
            try:
                for event in self.__client.events(decode=True, filters={"type": "container"}):
                    applied = False
                    self.__internal_lock.acquire()
                    locked = True
                    if not self.__process_event(event):
                        self.__internal_lock.release()
                        locked = False
                        continue
                    self._first_start = False

                    # Mark event received and update time
                    self.__pending_apply = True
                    self.__last_event_time = time()
                    self._logger.debug("Docker event received, will batch if more arrive...")
                    self.__internal_lock.release()
                    locked = False

                    # Wait for debounce period
                    while (time() - self.__last_event_time) < self.__debounce_delay:
                        sleep(0.1)

                    # Debounce period passed, try to apply
                    self.__internal_lock.acquire()
                    locked = True

                    # Check if another event updated the time while we were waiting
                    if (time() - self.__last_event_time) < self.__debounce_delay:
                        self.__internal_lock.release()
                        locked = False
                        continue

                    if not self.__pending_apply:
                        self.__internal_lock.release()
                        locked = False
                        continue

                    self.__pending_apply = False

                    try:
                        to_apply = False
                        while not applied:
                            waiting = self.have_to_wait()
                            self._update_settings()
                            self._instances = self.get_instances()
                            self._services = self.get_services()
                            self._configs = self.get_configs()

                            if not to_apply and not self.update_needed(self._instances, self._services, configs=self._configs):
                                if locked:
                                    self.__internal_lock.release()
                                    locked = False
                                applied = True
                                continue

                            to_apply = True
                            if waiting:
                                sleep(1)
                                continue

                            self._logger.info("Batched Docker event(s), deploying configuration...")
                            if not self.apply_config():
                                self._logger.error("Error while deploying new configuration")
                            else:
                                self._logger.info("Successfully deployed new configuration 🚀")
                                self._set_autoconf_load_db()
                            applied = True
                    except BaseException:
                        self._logger.error(f"Exception while processing Docker event :\n{format_exc()}")

                    if locked:
                        self.__internal_lock.release()
                        locked = False
            except:
                self._logger.error(f"Exception while reading Docker event :\n{format_exc()}")
                error = True
            finally:
                if locked:
                    with suppress(BaseException):
                        self.__internal_lock.release()
                    locked = False
                if error is True:
                    self._logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)
                    error = False
