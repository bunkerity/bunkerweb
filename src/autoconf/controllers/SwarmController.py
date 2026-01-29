#!/usr/bin/env python3

from os import getenv
from contextlib import suppress
from time import sleep, time
from traceback import format_exc
from threading import Thread, Lock
from typing import Any, Dict, List
from docker import DockerClient
from re import split as re_split
from base64 import b64decode

from docker.models.services import Service
from docker.errors import DockerException
from controllers.Controller import Controller


class SwarmController(Controller):
    def __init__(self, docker_host):
        super().__init__("swarm")
        self.__client = DockerClient(base_url=docker_host)
        self.__internal_lock = Lock()
        self.__swarm_instances = []
        self.__swarm_services = []
        self.__swarm_configs = []
        self.__pending_apply = False
        self.__last_event_time = 0.0
        self.__debounce_delay = 2  # seconds
        self._logger.warning("Swarm integration is deprecated and will be removed in a future release")
        self.__ignored_labels_exact = set()
        self.__ignored_label_suffixes = set()
        ignore_labels = getenv("SWARM_IGNORE_LABELS", "")
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

            self._logger.info("Ignoring Swarm labels while collecting instances: " + ", ".join(sorted(self.__ignored_labels_exact)))

    def __should_ignore_label(self, label: str) -> bool:
        if label in self.__ignored_labels_exact:
            return True
        if label.removeprefix("bunkerweb.") in self.__ignored_label_suffixes:
            return True
        return False

    def _get_controller_swarm_services(self, label_key: str) -> List[Service]:
        """
        Fetch Swarm services based on a specific label and filter them by namespace.

        Args:
            label_key (str): The key of the label to filter services by (e.g., "bunkerweb.INSTANCE").

        Returns:
            List[Service]: A list of services matching the label and namespace criteria.
        """
        try:
            # Retrieve services with the specific label
            services: List[Service] = self.__client.services.list(filters={"label": label_key})
        except DockerException as e:
            self._logger.error(f"Failed to retrieve services with label '{label_key}': {e}")
            return []

        namespace_set = set(self._namespaces or [])
        valid_services = []

        for service in services:
            try:
                # Safely retrieve and validate labels
                labels = service.attrs.get("Spec", {}).get("Labels", {})
                if not isinstance(labels, dict):
                    self._logger.warning(f"Unexpected label format for service {service.id}: {labels}")
                    continue

                if namespace_set:
                    namespace = labels.get("bunkerweb.NAMESPACE", "")
                    if namespace not in namespace_set:
                        self._logger.debug(f"Service {service.id} does not match any namespace.")
                        continue

                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping service {getattr(service, 'name', service.id)} because of ignored labels")
                    continue

                valid_services.append(service)

            except AttributeError as e:
                self._logger.warning(f"Service {service.id} missing expected attributes: {e}")
            except Exception as e:
                self._logger.error(f"Unexpected error while processing service {service.id}: {e}")

        return valid_services

    def _get_controller_instances(self) -> List[Service]:
        """
        Fetch Swarm services labeled as 'bunkerweb.INSTANCE'.
        """
        return self._get_controller_swarm_services(label_key="bunkerweb.INSTANCE")

    def _get_controller_services(self) -> List[Service]:
        """
        Fetch Swarm services labeled as 'bunkerweb.SERVER_NAME'.
        """
        return self._get_controller_swarm_services(label_key="bunkerweb.SERVER_NAME")

    def _to_instances(self, controller_instance) -> List[dict]:
        self.__swarm_instances.append(controller_instance.id)
        instances = []
        instance_env = {}
        for env in controller_instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
            variable, value = env.split("=", 1)
            instance_env[variable] = value

        for task in controller_instance.tasks():
            if task["DesiredState"] != "running":
                continue
            instances.append(
                {
                    "name": task["ID"],
                    "hostname": f"{controller_instance.name}.{task['NodeID']}.{task['ID']}",
                    "type": "container",
                    "health": task["Status"]["State"] == "running",
                    "env": instance_env,
                }
            )
        return instances

    def _to_services(self, controller_service) -> List[dict]:
        self.__swarm_services.append(controller_service.id)
        service = {}
        for variable, value in controller_service.attrs["Spec"]["Labels"].items():
            if self.__should_ignore_label(variable):
                continue
            if not variable.startswith("bunkerweb."):
                continue
            service[variable.replace("bunkerweb.", "", 1)] = value
        return [service]

    def get_configs(self) -> Dict[str, Dict[str, Any]]:
        self.__swarm_configs = []
        configs = {}
        for config_type in self._supported_config_types:
            configs[config_type] = {}
        for config in self.__client.configs.list(filters={"label": "bunkerweb.CONFIG_TYPE"}):
            if not config.name or not config.attrs or not config.attrs.get("Spec", {}).get("Labels", {}) or not config.attrs.get("Spec", {}).get("Data", {}):
                continue

            labels = config.attrs["Spec"].get("Labels", {}) or {}
            if any(self.__should_ignore_label(label) for label in labels):
                self._logger.info(f"Skipping Swarm config {getattr(config, 'name', config.id)} because of ignored labels")
                continue

            config_type = labels["bunkerweb.CONFIG_TYPE"]
            config_name = config.name
            if config_type not in self._supported_config_types:
                self._logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for Config {config_name}",
                )
                continue
            config_site = ""
            if "bunkerweb.CONFIG_SITE" in labels:
                if not self._is_service_present(labels["bunkerweb.CONFIG_SITE"]):
                    self._logger.warning(
                        f"Ignoring config {config_name} because {labels['bunkerweb.CONFIG_SITE']} doesn't exist",
                    )
                    continue
                config_site = f"{labels['bunkerweb.CONFIG_SITE']}/"
            configs[config_type][f"{config_site}{config_name}"] = b64decode(config.attrs["Spec"]["Data"])
            self.__swarm_configs.append(config.id)
        return configs

    def apply_config(self) -> bool:
        return self.apply(
            self._instances,
            self._services,
            configs=self._configs,
            first=not self._loaded,
        )

    def __process_event(self, event):
        if self._first_start:
            return True

        if "Actor" not in event or "ID" not in event["Actor"] or "Type" not in event:
            return False
        if event["Type"] not in ("service", "config"):
            return False
        if event["Type"] == "service":
            if event["Actor"]["ID"] in self.__swarm_instances or event["Actor"]["ID"] in self.__swarm_services:
                return True
            try:
                labels = self.__client.services.get(event["Actor"]["ID"]).attrs["Spec"].get("Labels", {}) or {}
                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping Swarm service {event['Actor']['ID']} because of ignored labels")
                    return False
                return ("bunkerweb.INSTANCE" in labels or "bunkerweb.SERVER_NAME" in labels) and (
                    not self._namespaces or any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces)
                )
            except:
                return False
        if event["Type"] == "config":
            if event["Actor"]["ID"] in self.__swarm_configs:
                return True
            try:
                labels = self.__client.configs.get(event["Actor"]["ID"]).attrs["Spec"].get("Labels", {}) or {}
                if any(self.__should_ignore_label(label) for label in labels):
                    self._logger.info(f"Skipping Swarm config {event['Actor']['ID']} because of ignored labels")
                    return False
                return "bunkerweb.CONFIG_TYPE" in labels and (
                    not self._namespaces or any(labels.get("bunkerweb.NAMESPACE", "") == namespace for namespace in self._namespaces)
                )
            except:
                return False
        return False

    def __event(self, event_type):
        while True:
            locked = False
            error = False
            applied = False
            try:
                for event in self.__client.events(decode=True, filters={"type": event_type}):
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
                    self._logger.debug(f"Swarm event ({event_type}) received, will batch if more arrive...")
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

                            self._logger.info("Batched Swarm event(s), deploying configuration...")
                            if not self.apply_config():
                                self._logger.error("Error while deploying new configuration")
                            else:
                                self._logger.info(
                                    "Successfully deployed new configuration 🚀",
                                )
                                self._set_autoconf_load_db()
                            applied = True
                    except BaseException:
                        self._logger.error(f"Exception while processing Swarm event ({event_type}) :\n{format_exc()}")

                    if locked:
                        self.__internal_lock.release()
                        locked = False
            except:
                self._logger.error(f"Exception while reading Swarm event ({event_type}) :\n{format_exc()}")
                error = True
            finally:
                if locked:
                    with suppress(BaseException):
                        self.__internal_lock.release()
                    locked = False
                if error is True:
                    self._logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def process_events(self):
        self._set_autoconf_load_db()
        event_types = ("service", "config")
        threads = [Thread(target=self.__event, args=(event_type,)) for event_type in event_types]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
