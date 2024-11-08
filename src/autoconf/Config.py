#!/usr/bin/env python3

from contextlib import suppress
from itertools import chain
from os import getenv
from time import sleep
from copy import deepcopy
from typing import Any, Dict, List, Optional

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore


class Config:
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
        config = {"SERVER_NAME": "", "MULTISITE": "yes"}

        for instance in self.__instances:
            for variable, value in instance["env"].items():
                if not self._db.is_setting(variable):
                    self.__logger.warning(f"Variable {variable}: {value} is not a valid setting, ignoring it")
                    continue
                config[variable] = value

        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            for variable, value in service.items():
                if variable.startswith("CUSTOM_CONF") or not variable.isupper():
                    continue
                if not self._db.is_setting(variable, multisite=True):
                    self.__logger.warning(f"Variable {variable}: {value} is not a valid multisite setting, ignoring it")
                    continue
                config[f"{server_name}_{variable}"] = value
            config["SERVER_NAME"] += f" {server_name}"
        config["SERVER_NAME"] = config["SERVER_NAME"].strip()
        return config

    def update_needed(self, instances: List[Dict[str, Any]], services: List[Dict[str, str]], configs: Optional[Dict[str, Dict[str, bytes]]] = None) -> bool:
        if instances != self.__instances:
            return True
        elif services != self.__services:
            return True
        elif (configs or {}) != self.__configs:
            return True
        return False

    def have_to_wait(self) -> bool:
        curr_changes = self._db.check_changes()
        return isinstance(curr_changes, str) or any(curr_changes.values())

    def wait_applying(self, startup: bool = False):
        i = 0
        while i < 60:
            curr_changes = self._db.check_changes()
            first_config_saved = self._db.is_first_config_saved()
            if isinstance(curr_changes, str):
                if not startup:
                    self.__logger.error(f"An error occurred when checking for changes in the database : {curr_changes}")
            elif isinstance(first_config_saved, str):
                if not startup:
                    self.__logger.error(f"An error occurred when checking if the first config is saved in the database : {first_config_saved}")
            elif not first_config_saved:
                self.__logger.warning("First configuration is not saved yet, retrying in 5 seconds ...")
            elif not any(curr_changes.values()):
                break
            else:
                self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
            i += 1
            sleep(5)
        if i >= 60:
            raise Exception("Too many retries while waiting for scheduler to apply configuration...")

    def apply(
        self, instances: List[Dict[str, Any]], services: List[Dict[str, str]], configs: Optional[Dict[str, Dict[str, bytes]]] = None, first: bool = False
    ) -> bool:
        success = True

        err = self._try_database_readonly()
        if err:
            return False

        while not self._db.is_initialized():
            self.__logger.warning("Database is not initialized, retrying in 5 seconds ...")
            sleep(5)

        self.wait_applying()

        configs = configs or {}

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
            old_env = deepcopy(self.__config)
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
                            "exploded": [site, config_type, name.replace(".conf", "")],
                        }
                    )

        # update instances in database
        if "instances" in changes:
            self.__logger.debug(f"Updating instances in database: {self.__instances}")
            err = self._db.update_instances(self.__instances, changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")

        # save config to database
        changed_plugins = []
        if "config" in changes:
            self.__logger.debug(f"Saving config in database: {self.__config}")
            err = self._db.save_config(self.__config, "autoconf", changed=False)
            if isinstance(err, str):
                success = False
                self.__logger.error(f"Can't save config in database: {err}, config may not work as expected")
            changed_plugins = err

        # save custom configs to database
        if "custom_configs" in changes:
            self.__logger.debug(f"Saving custom configs in database: {custom_configs}")
            err = self._db.save_custom_configs(custom_configs, "autoconf", changed=False)
            if err:
                success = False
                self.__logger.error(f"Can't save autoconf custom configs in database: {err}, custom configs may not work as expected")

        # update changes in db
        ret = self._db.checked_changes(changes, plugins_changes=changed_plugins, value=True)
        if ret:
            self.__logger.error(f"An error occurred when setting the changes to checked in the database : {ret}")

        return success

    def _try_database_readonly(self) -> bool:
        if not self._db.readonly:
            try:
                self._db.test_write()
            except BaseException:
                self._db.readonly = True
                return True

        if self._db.database_uri and self._db.readonly:
            try:
                self._db.retry_connection(pool_timeout=1)
                self._db.retry_connection(log=False)
                self._db.readonly = False
                self.__logger.info("The database is no longer read-only, defaulting to read-write mode")
            except BaseException:
                try:
                    self._db.retry_connection(readonly=True, pool_timeout=1)
                    self._db.retry_connection(readonly=True, log=False)
                except BaseException:
                    if self._db.database_uri_readonly:
                        with suppress(BaseException):
                            self._db.retry_connection(fallback=True, pool_timeout=1)
                            self._db.retry_connection(fallback=True, log=False)
                self._db.readonly = True

            if self._db.readonly:
                self.__logger.error("Database is in read-only mode, configuration will not be saved")

        return self._db.readonly
