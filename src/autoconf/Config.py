#!/usr/bin/python3

from os import getenv
from time import sleep
from typing import Optional
from copy import deepcopy

from ConfigCaller import ConfigCaller  # type: ignore
from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore


class Config(ConfigCaller):
    def __init__(self):
        super().__init__()
        self.__logger = setup_logger("Config", getenv("LOG_LEVEL", "INFO"))
        self.__instances = []
        self.__services = []
        self._supported_config_types = [
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
        ]
        self.__configs = {
            config_type: {} for config_type in self._supported_config_types
        }
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

    def update_needed(self, instances, services, configs={}) -> bool:
        if instances != self.__instances:
            return True
        elif services != self.__services:
            return True
        elif configs != self.__configs:
            return True
        return False

    def apply(self, instances, services, configs={}, first=False) -> bool:
        success = True

        # update types
        updates = {
            "instances": False,
            "services": False,
            "configs": False,
            "config": False

        }
        changes = []
        if instances != self.__instances or first:
            self.__instances = instances
            updates["instances"] = True
            changes.append("instances")
        if services != self.__services or first:
            self.__services = services
            updates["services"] = True
        if configs != self.__configs or first:
            self.__configs = configs
            updates["configs"] = True
            changes.append("custom_configs")
        if updates["instances"] or updates["services"]:
            old_env = deepcopy(self.__config)
            new_env = self.__get_full_env()
            if old_env != new_env or first:
                self.__config = new_env
                updates["config"] = True
                changes.append("config")

        custom_configs = []
        if updates["configs"]:
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

        # update instances in database
        if updates["instances"]:
            err = self._db.update_instances(self.__instances, changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")
        # save config to database
        if updates["config"]:
            err = self._db.save_config(self.__config, "autoconf", changed=False)
            if err:
                success = False
                self.__logger.error(
                    f"Can't save config in database: {err}, config may not work as expected",
                )
        # save custom configs to database
        if updates["configs"]:
            err = self._db.save_custom_configs(custom_configs, "autoconf", changed=False)
            if err:
                success = False
                self.__logger.error(
                    f"Can't save autoconf custom configs in database: {err}, custom configs may not work as expected",
                )
        # update changes in db
        ret = self._db.checked_changes(changes, value=True)
        if ret:
            self.__logger.error(
                f"An error occurred when setting the changes to checked in the database : {ret}"
            )

        return success
