#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from os import getenv
from time import sleep

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
        self.__configs = {config_type: {} for config_type in self._supported_config_types}
        self.__config = {}

        self._db = Database(self.__logger)

    def _update_settings(self):
        plugins = self._db.get_plugins()
        if not plugins:
            self.__logger.error("No plugins in database, can't update settings...")
            return
        self._settings = {}
        for plugin in plugins:
            self._settings.update(plugin["settings"])

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

    def wait_applying(self):
        current_time = datetime.now()
        ready = False
        while not ready and (datetime.now() - current_time).seconds < 240:
            db_metadata = self._db.get_metadata()
            if isinstance(db_metadata, str):
                self.__logger.error(f"An error occurred when checking for changes in the database : {db_metadata}")
            elif not any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "config_changed", "instances_changed")
            ):
                ready = True
                continue
            else:
                self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
            sleep(5)

        if not ready:
            raise Exception("Too many retries while waiting for scheduler to apply configuration...")

    def apply(self, instances, services, configs={}, first=False) -> bool:
        success = True

        changes = []
        if instances != self.__instances or first:
            self.__instances = instances
            changes.append("instances")
        if services != self.__services or first:
            self.__services = services
            changes.append("services")
        if configs != self.__configs or first:
            self.__configs = configs
            changes.append("custom_configs")
        if "instances" in changes or "services" in changes:
            old_env = self.__config.copy()
            new_env = self.__get_full_env()
            if old_env != new_env or first:
                self.__config = new_env
                changes.append("config")

        custom_configs = []
        if "custom_configs" in changes:
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

        current_time = datetime.now()
        ready = False
        while not ready and (datetime.now() - current_time).seconds < 120:
            db_metadata = self._db.get_metadata()
            if isinstance(db_metadata, str) or not db_metadata["is_initialized"]:
                self.__logger.warning("Database is not initialized, retrying in 5s ...")
                sleep(5)
                continue
            ready = True

        if not ready:
            self.__logger.error(f"Timeout while waiting for database to be initialized, ignoring changes ...\ndb data: {db_metadata}")
            return False

        # wait until changes are applied
        ready = False
        with suppress(BaseException):
            self.wait_applying()
            ready = True

        if not ready:
            self.__logger.warning("Timeout while waiting for scheduler to apply configuration, continuing anyway...")

        # update instances in database
        if "instances" in changes:
            err = self._db.update_instances(self.__instances, "autoconf", changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")

        # save config to database
        if "config" in changes:
            err = self._db.save_config(self.__config, "autoconf", changed=False)
            if err:
                success = False
                self.__logger.error(f"Can't save config in database: {err}, config may not work as expected")

        # save custom configs to database
        if "custom_configs" in changes:
            err = self._db.save_custom_configs(custom_configs, "autoconf", changed=False)
            if err:
                success = False
                self.__logger.error(f"Can't save autoconf custom configs in database: {err}, custom configs may not work as expected")

        # update changes in db
        ret = self._db.checked_changes(changes, value=True)
        if ret:
            self.__logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

        self.__logger.info("Successfully saved new configuration 🚀")

        return success
