#!/usr/bin/env python3

from abc import abstractmethod
from os import getenv
from time import sleep

from Config import Config

from logger import getLogger  # type: ignore


class Controller(Config):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loaded = False
        self._instances = []
        self._services = []
        self._configs = {config_type: {} for config_type in self._supported_config_types}
        self._extra_config = {}
        self._logger = getLogger(f"{self._type.upper()}-CONTROLLER")
        self._namespaces = None
        self._first_start = True
        namespaces = getenv("NAMESPACES")
        if namespaces:
            self._namespaces = namespaces.strip().split()
            self._logger.info(
                "Only instances and services in the "
                + ", ".join(f"{namespace!r}" for namespace in self._namespaces)
                + f" namespace{'s' if len(self._namespaces) > 1 else ''} will be managed."
            )

    def wait(self, wait_time: int) -> list:
        all_ready = False
        while not all_ready:
            if self.have_to_wait():
                self._logger.info(f"Waiting for the database to be ready, retrying in {wait_time}s ...")
                sleep(wait_time)
                continue

            self._instances = self.get_instances()
            if not self._instances:
                self._logger.warning(f"No instance found, waiting {wait_time}s ...")
                sleep(wait_time)
                continue

            all_ready = True
            for instance in self._instances:
                if not instance["health"]:
                    self._logger.warning(f"Instance {instance['name']} is not ready, waiting {wait_time}s ...")
                    sleep(wait_time)
                    all_ready = False
                    break
        return self._instances

    @abstractmethod
    def _get_controller_instances(self):
        raise NotImplementedError

    @abstractmethod
    def _to_instances(self, controller_instance):
        raise NotImplementedError

    def get_instances(self):
        instances = []
        for controller_instance in self._get_controller_instances():
            instances.extend(self._to_instances(controller_instance))

        if not instances and self._first_start:
            for db_instance in self._db.get_instances(autoconf=True):
                if not any(db_instance["hostname"] == instance["hostname"] for instance in instances):
                    instances.append(db_instance)

        return instances

    @abstractmethod
    def _get_controller_services(self):
        raise NotImplementedError

    @abstractmethod
    def _to_services(self, controller_service):
        raise NotImplementedError

    def _set_autoconf_load_db(self):
        if not self._loaded:
            ret = self._db.set_metadata({"autoconf_loaded": True})
            if ret:
                self._logger.warning(f"Can't set autoconf loaded metadata to true in database: {ret}")
            else:
                self._loaded = True

    def get_services(self):
        services = []
        for controller_service in self._get_controller_services():
            services.extend(self._to_services(controller_service))
        return services

    @abstractmethod
    def get_configs(self):
        raise NotImplementedError

    @abstractmethod
    def apply_config(self):
        raise NotImplementedError

    @abstractmethod
    def process_events(self):
        raise NotImplementedError

    def _is_service_present(self, server_name):
        if not isinstance(server_name, str):
            return False

        normalized_server_name = server_name.strip().split(" ")[0]
        if not normalized_server_name:
            return False

        for service in self._services:
            service_name = service.get("SERVER_NAME", "")
            if not service_name:
                continue
            if normalized_server_name == service_name.strip().split(" ")[0]:
                return True

        db_services = self._db.get_services()
        for service in db_services:
            db_service_name = service.get("id", "")
            if normalized_server_name == db_service_name:
                return True

        return False
