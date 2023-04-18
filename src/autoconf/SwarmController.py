from os import getenv
from time import sleep
from traceback import format_exc
from threading import Thread, Lock
from docker import DockerClient
from base64 import b64decode

from Controller import Controller
from ConfigCaller import ConfigCaller
from logger import setup_logger


class SwarmController(Controller, ConfigCaller):
    def __init__(self, docker_host):
        Controller.__init__(self, "swarm")
        ConfigCaller.__init__(self)
        self.__client = DockerClient(base_url=docker_host)
        self.__internal_lock = Lock()
        self.__logger = setup_logger("Swarm-controller", getenv("LOG_LEVEL", "INFO"))

    def _get_controller_instances(self):
        return self.__client.services.list(filters={"label": "bunkerweb.INSTANCE"})

    def _get_controller_services(self):
        return self.__client.services.list(filters={"label": "bunkerweb.SERVER_NAME"})

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
            if task["DesiredState"] != "running":
                continue
            instances.append(
                {
                    "name": task["ID"],
                    "hostname": f"{controller_instance.name}.{task['NodeID']}.{task['ID']}",
                    "health": task["Status"]["State"] == "running",
                    "env": instance_env,
                }
            )
        return instances

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
            if not instance.attrs or not instance.attrs.get("Spec", {}).get(
                "TaskTemplate", {}
            ).get("ContainerSpec", {}).get("Env"):
                continue

            for env in instance.attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Env"]:
                variable = env.split("=")[0]
                value = env.replace(f"{variable}=", "", 1)
                variables[variable] = value
        if "SERVER_NAME" in variables and variables["SERVER_NAME"].strip():
            for server_name in variables["SERVER_NAME"].strip().split(" "):
                service = {}
                service["SERVER_NAME"] = server_name
                for variable, value in variables.items():
                    prefix = variable.split("_")[0]
                    real_variable = variable.replace(f"{prefix}_", "", 1)
                    if prefix == server_name and self._is_multisite_setting(
                        real_variable
                    ):
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
            if (
                not config.name
                or not config.attrs
                or not config.attrs.get("Spec", {}).get("Labels", {})
                or not config.attrs.get("Spec", {}).get("Data", {})
            ):
                continue

            config_type = config.attrs["Spec"]["Labels"]["bunkerweb.CONFIG_TYPE"]
            config_name = config.name
            if config_type not in self._supported_config_types:
                self.__logger.warning(
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for Config {config_name}",
                )
                continue
            config_site = ""
            if "bunkerweb.CONFIG_SITE" in config.attrs["Spec"]["Labels"]:
                if not self._is_service_present(
                    config.attrs["Spec"]["Labels"]["bunkerweb.CONFIG_SITE"]
                ):
                    self.__logger.warning(
                        f"Ignoring config {config_name} because {config.attrs['Spec']['Labels']['bunkerweb.CONFIG_SITE']} doesn't exist",
                    )
                    continue
                config_site = (
                    f"{config.attrs['Spec']['Labels']['bunkerweb.CONFIG_SITE']}/"
                )
            configs[config_type][f"{config_site}{config_name}"] = b64decode(
                config.attrs["Spec"]["Data"]
            )
        return configs

    def apply_config(self):
        return self._config.apply(
            self._instances, self._services, configs=self._configs
        )

    def __event(self, event_type):
        while True:
            locked = False
            error = False
            try:
                for _ in self.__client.events(
                    decode=True, filters={"type": event_type}
                ):
                    self.__internal_lock.acquire()
                    locked = True
                    try:
                        self._instances = self.get_instances()
                        self._services = self.get_services()
                        self._configs = self.get_configs()
                        if not self._config.update_needed(
                            self._instances, self._services, configs=self._configs
                        ):
                            self.__internal_lock.release()
                            locked = False
                            continue
                        self.__logger.info(
                            f"Catched Swarm event ({event_type}), deploying new configuration ..."
                        )
                        if not self.apply_config():
                            self.__logger.error(
                                "Error while deploying new configuration"
                            )
                        else:
                            self.__logger.info(
                                "Successfully deployed new configuration 🚀",
                            )
                    except:
                        self.__logger.error(
                            f"Exception while processing Swarm event ({event_type}) :\n{format_exc()}"
                        )
                    self.__internal_lock.release()
                    locked = False
            except:
                self.__logger.error(
                    f"Exception while reading Swarm event ({event_type}) :\n{format_exc()}",
                )
                error = True
            finally:
                if locked:
                    self.__internal_lock.release()
                    locked = False
                if error is True:
                    self.__logger.warning("Got exception, retrying in 10 seconds ...")
                    sleep(10)

    def process_events(self):
        self._set_autoconf_load_db()
        event_types = ("service", "config")
        threads = [
            Thread(target=self.__event, args=(event_type,))
            for event_type in event_types
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
