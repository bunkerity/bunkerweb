#!/usr/bin/env python3

from datetime import datetime
from os import getenv
from time import sleep
from typing import Any, Dict, List, Literal, Optional, Union

from api_client import ApiUnavailableError  # type: ignore
from common_utils import normalize_check_value  # type: ignore
from logger import getLogger  # type: ignore


class Config:
    def __init__(self, ctrl_type: Union[Literal["docker"], Literal["swarm"], Literal["kubernetes"]], *, api_client):
        self._type = ctrl_type
        self.__logger = getLogger("CONFIG")
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

        # When enabled, services / custom configs removed from the orchestrator are converted
        # to draft in the DB instead of being hard-deleted, so they can be republished later.
        self._disable_cleanup = getenv("AUTOCONF_DISABLE_CLEANUP", "no").strip().lower() == "yes"

        self._api = api_client
        self._api_available = True
        self._api_error_timeout = int(getenv("API_ERROR_TIMEOUT", "60"))

    def _update_settings(self):
        plugins = self._api.get_plugins()
        if not plugins:
            self.__logger.error("No plugins from API, can't update settings...")
            return
        self._settings = {}
        for plugin in plugins:
            self._settings.update(plugin.get("settings", {}))

    def __get_full_env(self) -> dict:
        config = {"SERVER_NAME": "", "MULTISITE": "yes"}
        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            config["SERVER_NAME"] += f" {server_name}"

        api_services = []
        for api_service in self._api.get_services():
            server_name = api_service.get("id", "")
            if not server_name:
                continue
            api_services.append(server_name)

        for service in self.__services:
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                continue
            for variable, value in service.items():
                if variable == "NAMESPACE" or variable.startswith("CUSTOM_CONF"):
                    continue

                is_global = False
                success, err = self._api.validate_setting(
                    variable,
                    value=value,
                    multisite=True,
                    extra_services=config["SERVER_NAME"].split() + api_services,
                )
                if not success:
                    if self._type == "kubernetes":
                        success, err = self._api.validate_setting(variable, value=value)
                        if success:
                            is_global = True
                            self.__logger.warning(f"Variable {variable} is a global value and will be applied globally")
                    if not success:
                        self.__logger.warning(f"Variable {variable}: {value} is not a valid autoconf setting ({err}), ignoring it")
                        continue

                # Canonicalize boolean ("check") aliases so the stored value matches the
                # DB's yes/no — otherwise apply()'s env diff vs self.__config would differ
                # every cycle (perpetual reconfigure loop).
                if self._settings.get(variable, {}).get("type") == "check":
                    value = normalize_check_value(value)

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
        metadata = self._api.get_metadata()
        return (
            isinstance(metadata, str)
            or not metadata.get("is_initialized")
            or any(
                v
                for k, v in metadata.items()
                if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
            )
        )

    def wait_applying(self):
        # Ready when DB is initialized and no scheduler apply is in flight.
        current_time = datetime.now().astimezone()
        ready = False
        waited = False
        error_since = None
        with self._api.expect_errors():
            while not ready and (datetime.now().astimezone() - current_time).seconds < 240:
                metadata = self._api.get_metadata()
                if isinstance(metadata, str):
                    if error_since is None:
                        error_since = datetime.now().astimezone()
                    elapsed = (datetime.now().astimezone() - error_since).seconds
                    if elapsed >= self._api_error_timeout:
                        self._api._expect_errors = False  # Escalate to real errors now
                        self.__logger.error(f"API has been failing for {elapsed}s ({metadata})")
                    else:
                        self.__logger.warning(f"Could not check metadata via API ({metadata}), will retry ...")
                elif (
                    metadata.get("is_initialized")
                    and metadata.get("first_config_saved")
                    and not any(
                        v
                        for k, v in metadata.items()
                        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
                    )
                ):
                    ready = True
                    continue
                else:
                    error_since = None  # API is responding, just not ready yet
                waited = True
                self.__logger.warning("Scheduler is already applying a configuration, retrying in 5 seconds ...")
                sleep(5)

        if not ready:
            raise Exception("Too many retries while waiting for scheduler to apply configuration...")

        if waited:
            self.__logger.info("Scheduler is ready, proceeding")

    def apply(
        self,
        instances: List[Dict[str, Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, bytes]]] = None,
        first: bool = False,
        extra_config: Optional[Dict[str, str]] = None,
    ) -> bool:
        success = True

        if not self._check_api_available():
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
                    # Ensure data is a string (Swarm's b64decode returns bytes which can't be JSON-serialized)
                    config_value = data.decode("utf-8") if isinstance(data, bytes) else data
                    custom_configs.append({"value": config_value, "exploded": [site, config_type, name.replace(".conf", "")]})

        # update instances via API
        if "instances" in changes:
            self.__logger.debug(f"Updating instances via API: {self.__instances}")
            err = self._api.update_instances(self.__instances, "autoconf", changed=False)
            if err:
                self.__logger.error(f"Failed to update instances: {err}")

        # save config via API
        changed_plugins = []
        if "config" in changes:
            self.__logger.debug(f"Saving config via API: {self.__config}")
            err = self._api.save_config(self.__config, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if isinstance(err, str):
                success = False
                self.__logger.error(f"Can't save config via API: {err}, config may not work as expected")
            else:
                changed_plugins = err

        # save custom configs via API
        if "custom_configs" in changes:
            self.__logger.debug(f"Saving custom configs via API: {custom_configs}")
            err = self._api.save_custom_configs(custom_configs, "autoconf", changed=False, disable_cleanup=self._disable_cleanup)
            if err:
                success = False
                self.__logger.error(f"Can't save autoconf custom configs via API: {err}, custom configs may not work as expected")

        # signal changes via API
        ret = self._api.checked_changes(changes, plugins_changes=changed_plugins, value=True)
        if ret:
            self.__logger.error(f"An error occurred when setting the changes to checked via API : {ret}")

        self.__logger.info("Successfully saved new configuration 🚀")

        return success

    def _check_api_available(self) -> bool:
        """Check if API is available and not readonly. Implements hybrid degraded mode.

        The readonly property on BaseApiClient catches ApiUnavailableError internally
        and returns True. So when readonly returns True, we ping() to distinguish
        'DB is genuinely read-only' from 'API is unreachable'.
        """
        if not self._api_available:
            try:
                self._api.ping()
                self._api_available = True
                self.__logger.info("API connection recovered, resuming normal operation")
            except ApiUnavailableError:
                self.__logger.warning("API is still unavailable, configuration will not be saved")
                return False

        if self._api.readonly:
            # readonly returns True either because DB is read-only OR because API is unreachable.
            # Use ping() to distinguish the two cases.
            try:
                self._api.ping()
                # API is up but DB is genuinely read-only
                self.__logger.error("API reports read-only mode, configuration will not be saved")
            except ApiUnavailableError:
                # API is actually down — enter degraded mode
                self._api_available = False
                self.__logger.error("API became unavailable, entering degraded mode")
            return False

        return True
