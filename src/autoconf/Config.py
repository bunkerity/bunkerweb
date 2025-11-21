#!/usr/bin/env python3

from contextlib import suppress
from datetime import datetime
from os import getenv
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Union

from Database import Database  # type: ignore
from logger import setup_logger  # type: ignore


class Config:
    def __init__(self, ctrl_type: Union[Literal["docker"], Literal["swarm"], Literal["kubernetes"]]):
        self._type = ctrl_type
        self.__logger = setup_logger("Config", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))
        self._settings = {}
        self.__instances = []
        self.__services = []
        self._supported_config_types = (
            "http",
            "stream",
            "server-http",
            "server-stream",
            "default-server-http",
            "modsec",
            "modsec-crs",
            "crs-plugins-before",
            "crs-plugins-after",
        )
        self.__configs = {config_type: {} for config_type in self._supported_config_types}
        self.__config = {}
        self.__extra_config = {}

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
        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            config["SERVER_NAME"] += f" {server_name}"

        db_services = []
        for db_service in self._db.get_services():
            server_name = db_service.get("id", "")
            if not server_name:
                continue
            db_services.append(server_name)

        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            for variable, value in service.items():
                if variable == "NAMESPACE" or variable.startswith("CUSTOM_CONF"):
                    continue

                is_global = False
                success, err = self._db.is_valid_setting(
                    variable,
                    value=value,
                    multisite=True,
                    extra_services=config["SERVER_NAME"].split(" ") + db_services,
                )
                if not success:
                    if self._type == "kubernetes":
                        success, err = self._db.is_valid_setting(variable, value=value)
                        if success:
                            is_global = True
                            self.__logger.warning(f"Variable {variable} is a global value and will be applied globally")
                    if not success:
                        self.__logger.warning(f"Variable {variable}: {value} is not a valid autoconf setting ({err}), ignoring it")
                        continue

                if is_global or variable.startswith(f"{server_name}_"):
                    if variable == "SERVER_NAME":
                        self.__logger.warning("Global variable SERVER_NAME can't be set via annotations, ignoring it")
                        continue
                    config[variable] = value
                    continue
                config[f"{server_name}_{variable}"] = value
        config["SERVER_NAME"] = config["SERVER_NAME"].strip()
        return config

    def update_needed(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        extra_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        configs = configs or {}
        extra_config = extra_config or {}

        # Use sets for comparing lists of dictionaries
        if set(map(str, self.__instances)) != set(map(str, instances)):
            self.__logger.debug(f"Instances changed: {self.__instances} -> {instances}")
            return True

        if set(map(str, self.__services)) != set(map(str, services)):
            self.__logger.debug(f"Services changed: {self.__services} -> {services}")
            return True

        if set(map(str, self.__configs.items())) != set(map(str, configs.items())):
            self.__logger.debug(f"Configs changed: {self.__configs} -> {configs}")
            return True

        if set(map(str, self.__extra_config.items())) != set(map(str, extra_config.items())):
            self.__logger.debug(f"Extra config changed: {self.__extra_config} -> {extra_config}")
            return True

        return False

    def have_to_wait(self) -> bool:
        db_metadata = self._db.get_metadata()
        return (
            isinstance(db_metadata, str)
            or not db_metadata["is_initialized"]
            or any(
                v
                for k, v in db_metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            )
        )

    def wait_applying(self, startup: bool = False):
        current_time = datetime.now().astimezone()
        ready = False
        while not ready and (datetime.now().astimezone() - current_time).seconds < 240:
            db_metadata = self._db.get_metadata()
            if isinstance(db_metadata, str):
                if not startup:
                    self.__logger.error(f"An error occurred when checking for changes in the database : {db_metadata}")
            elif (
                db_metadata["is_initialized"]
                and db_metadata["first_config_saved"]
                and not any(
                    v
                    for k, v in db_metadata.items()
                    if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
                )
            ):
                ready = True
                continue
            self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
            sleep(5)

        if not ready:
            raise Exception("Too many retries while waiting for scheduler to apply configuration...")

    def apply(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        first: bool = False,
        extra_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        success = True

        err = self._try_database_readonly()
        if err:
            return False

        self.wait_applying()

        configs = configs or {}
        extra_config = extra_config or {}

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
        if extra_config != self.__extra_config or first:
            changes.append("extra_config")
        if "instances" in changes or "services" in changes or "extra_config" in changes:
            old_env = self.__config.copy()
            new_env = self.__get_full_env() | extra_config
            if old_env != new_env or first:
                self.__config = new_env
                changes.append("config")
            if "extra_config" in changes:
                self.__extra_config = extra_config.copy()

        custom_configs = []
        if "custom_configs" in changes:
            for config_type in self.__configs:
                if config_type not in self._supported_config_types:
                    self.__logger.warning(f"Unsupported custom config type: {config_type}")
                    continue

                for file, data in self.__configs[config_type].items():
                    site = None
                    name = file
                    if "/" in file:
                        exploded = file.split("/")
                        site = exploded[0]
                        name = exploded[1]
                    custom_configs.append({"value": data, "exploded": [site, config_type, name.replace(".conf", "")]})

        # update instances in database
        if "instances" in changes:
            self.__logger.debug(f"Updating instances in database: {self.__instances}")
            err = self._db.update_instances(self.__instances, "autoconf", changed=False)
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

        self.__logger.info("Successfully saved new configuration 🚀")

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
