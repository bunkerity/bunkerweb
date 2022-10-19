from abc import ABC, abstractmethod
from os import getenv
from time import sleep

from Config import Config

from logger import setup_logger


class Controller(ABC):
    def __init__(self, ctrl_type, lock=None):
        self._type = ctrl_type
        self._instances = []
        self._services = []
        self._supported_config_types = [
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
        ]
        self._configs = {}
        for config_type in self._supported_config_types:
            self._configs[config_type] = {}
        self._config = Config(ctrl_type, lock)
        self.__logger = setup_logger("Controller", getenv("LOG_LEVEL", "INFO"))

    def wait(self, wait_time):
        while True:
            self._instances = self.get_instances()
            if len(self._instances) == 0:
                self.__logger.warning(
                    f"No instance found, waiting {wait_time}s ...",
                )
                sleep(wait_time)
                continue
            all_ready = True
            for instance in self._instances:
                if not instance["health"]:
                    self.__logger.warning(
                        f"Instance {instance['name']} is not ready, waiting {wait_time}s ...",
                    )
                    sleep(wait_time)
                    all_ready = False
                    break
            if all_ready:
                break
        return self._instances

    @abstractmethod
    def _get_controller_instances(self):
        pass

    @abstractmethod
    def _to_instances(self, controller_instance):
        pass

    def get_instances(self):
        instances = []
        for controller_instance in self._get_controller_instances():
            for instance in self._to_instances(controller_instance):
                instances.append(instance)
        return instances

    @abstractmethod
    def _get_controller_services(self):
        pass

    @abstractmethod
    def _to_services(self, controller_service):
        pass

    @abstractmethod
    def _get_static_services(self):
        pass

    def get_services(self):
        services = []
        for controller_service in self._get_controller_services():
            for service in self._to_services(controller_service):
                services.append(service)
        for static_service in self._get_static_services():
            services.append(static_service)
        return services

    @abstractmethod
    def get_configs(self):
        pass

    @abstractmethod
    def apply_config(self):
        pass

    @abstractmethod
    def process_events(self):
        pass
