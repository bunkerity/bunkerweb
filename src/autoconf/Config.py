#!/usr/bin/python3

from os import getenv
from threading import Lock
from time import sleep
from typing import Literal, Optional, Union

from ConfigCaller import ConfigCaller  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore


class Config(ConfigCaller):
    def __init__(
        self,
        ctrl_type: Union[Literal["docker"], Literal["swarm"], Literal["kubernetes"]],
        lock: Optional[Lock] = None,
    ):
        super().__init__()
        self.__ctrl_type = ctrl_type
        self.__lock = lock
        self.__logger = setup_logger("Config", getenv("LOG_LEVEL", "INFO"))
        self.__instances = []
        self.__services = []
        self.__configs = []
        self.__config = {}

        self._db = Database(self.__logger)

    def __get_full_env(self) -> dict:
        env_instances = {"SERVER_NAME": ""}
        for instance in self.__instances:
            for variable, value in instance["env"].items():
                env_instances[variable] = value
        env_services = {}
        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            for variable, value in service.items():
                env_services[f"{server_name}_{variable}"] = value
            env_instances["SERVER_NAME"] += f" {server_name}"
        env_instances["SERVER_NAME"] = env_instances["SERVER_NAME"].strip()
        return self._full_env(env_instances, env_services)

    def update_needed(self, instances, services, configs=None) -> bool:
        if instances != self.__instances:
            return True
        elif services != self.__services:
            return True
        elif not configs is None and configs != self.__configs:
            return True
        return False

    def apply(self, instances, services, configs=None) -> bool:
        success = True

        # update values
        self.__instances = instances
        self.__services = services
        self.__configs = configs
        self.__config = self.__get_full_env()

        custom_configs = []
        for config_type in self.__configs:
            for file, data in self.__configs[config_type].items():
                site = None
                name = file
                if "/" in file:
                    exploded = file.split("/")
                    site = exploded[0]
                    name = exploded[1]
                custom_configs.append(
                    {
                        "value": data,
                        "exploded": [
                            site,
                            config_type,
                            name.replace(".conf", ""),
                        ],
                    }
                )

        while not self._db.is_initialized():
            self.__logger.warning(
                "Database is not initialized, retrying in 5 seconds ...",
            )
            sleep(5)

        if self.__lock:
            self.__lock.acquire()

        # update instances in database
        err = self._db.update_instances(self.__instances)
        if err:
            self.__logger.error(f"Failed to update instances: {err}")

        # save config to database
        err = self._db.save_config(self.__config, "autoconf")
        if err:
            success = False
            self.__logger.error(
                f"Can't save config in database: {err}, config may not work as expected",
            )

        # save custom configs to database
        err = self._db.save_custom_configs(custom_configs, "autoconf")
        if err:
            success = False
            self.__logger.error(
                f"Can't save autoconf custom configs in database: {err}, custom configs may not work as expected",
            )

        if self.__lock:
            self.__lock.release()

        return success
