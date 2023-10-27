#!/usr/bin/python3
# -*- coding: utf-8 -*-

from json import dumps
from re import match
from time import sleep
from typing import Any, Dict, List, Literal, Optional

from API import API  # type: ignore
from logger import setup_logger  # type: ignore


class Config:
    def __init__(
        self,
        core_api: API,
        log_level: str = "INFO",
        *,
        api_token: Optional[str] = None,
        wait_retry_interval: int = 5,
    ):
        self._api = core_api
        self.__logger = setup_logger("Config", log_level)
        self._api_token = api_token
        self._wait_retry_interval = wait_retry_interval
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
        self._settings = {}

        self._update_settings()

    def _update_settings(self) -> None:
        old_settings = self._settings
        try:
            self._settings = {}

            sent = None
            status = None
            plugins = []
            while not sent and status != 200:
                sent, err, status, plugins = self._api.request(
                    "GET",
                    "/plugins",
                    additonal_headers={"Authorization": f"Bearer {self._api_token}"} if self._api_token else {},
                )

                if not sent or status != 200:
                    self.__logger.warning(
                        f"Could not contact core API. Waiting {self._wait_retry_interval} seconds before retrying ...",
                    )
                    sleep(int(self._wait_retry_interval))
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {self._api.endpoint}plugins",
                    )

            for plugin in plugins.json():  # type: ignore
                self._settings.update(plugin["settings"])
        except:
            self.__logger.exception("Could not update settings")
            self._settings = old_settings

    def __get_full_env(self) -> dict:
        env_instances = {"SERVER_NAME": ""}
        for instance in self.__instances:
            for variable, value in instance["env"].items():
                env_instances[variable] = value
        env_services = {}
        for service in self.__services:
            server_name = service.get("SERVER_NAME", "").strip().split()[0]
            for variable, value in service.items():
                env_services[f"{server_name}_{variable}"] = value
            env_instances["SERVER_NAME"] += f" {server_name}"
        env_instances["SERVER_NAME"] = env_instances["SERVER_NAME"].strip()
        return self._full_env(env_instances, env_services)

    def update_needed(
        self,
        instances: List[Dict[Literal["name", "hostname", "health", "env"], Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> bool:
        if instances != self.__instances:
            return True
        elif services != self.__services:
            return True
        elif (configs or {}) != self.__configs:
            return True
        return False

    def _is_setting(self, setting) -> bool:
        return setting in self._settings

    def _is_setting_context(self, setting: str, context: Literal["global", "multisite"]) -> bool:
        if self._is_setting(setting):
            return self._settings[setting]["context"] == context
        elif match(r"^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[:-1])
            return self._is_setting(multiple_setting) and self._settings[multiple_setting]["context"] == context and "multiple" in self._settings[multiple_setting]
        return False

    def _full_env(self, env_instances: Dict[str, Any], env_services: Dict[str, Any]) -> Dict[str, Any]:
        full_env = {}
        self._update_settings()
        # Fill with default values
        for k, v in self._settings.items():
            full_env[k] = v["default"]
        # Replace with instances values
        for k, v in env_instances.items():
            full_env[k] = v
            if not self._is_setting_context(k, "global") and env_instances.get("MULTISITE", "no") == "yes" and env_instances.get("SERVER_NAME", "") != "":
                for server_name in env_instances["SERVER_NAME"].strip().split():
                    full_env[f"{server_name}_{k}"] = v
        # Replace with services values
        full_env = full_env | env_services
        full_env["MULTISITE"] = "yes"
        return full_env

    def apply(
        self,
        instances: List[Dict[Literal["name", "hostname", "health", "env"], Any]],
        services: List[Dict[str, str]],
        configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> bool:
        success = True

        # update values
        instances_changed = instances != self.__instances
        self.__instances = instances
        self.__services = services
        config = self.__get_full_env()
        configs_changed = (configs or {}) != self.__configs
        config_changed = self.__config != config

        sent = None
        status = None
        while not sent and status != 200:
            sent, err, status, resp = self._api.request(
                "GET",
                "/ping",
                additonal_headers={"Authorization": f"Bearer {self._api_token}"} if self._api_token else {},
            )

            if not sent or status != 200:
                self.__logger.warning(
                    f"Could not contact core API. Waiting {self._wait_retry_interval} seconds before retrying ...",
                )
                sleep(self._wait_retry_interval)
            else:
                self.__logger.info(
                    f"Successfully sent API request to {self._api.endpoint}ping",
                )

        if instances_changed:
            self.__logger.info("Instances changed, updating ...")
            status = 503
            while status == 503:
                # Send new instances to API
                sent, err, status, resp = self._api.request(
                    "PUT",
                    f"/instances?method=autoconf&reload={'false' if configs_changed or config_changed else 'true'}",
                    data=dumps(
                        [
                            {
                                "hostname": instance["hostname"],
                                "port": self.__config.get("API_HTTP_PORT", "5000"),
                                "server_name": self.__config.get("API_SERVER_NAME", "bwapi"),
                            }
                            for instance in instances
                        ]
                    ).encode(),
                    additonal_headers={"Authorization": f"Bearer {self._api_token}"} if self._api_token else {},
                )

                if not sent or status not in (200, 201, 503):
                    self.__logger.warning(resp)
                    self.__logger.warning(
                        f"Could not contact core API. Instances may not be updated: {err}",
                    )
                    success = False
                elif status == 503:
                    retry_after = resp.headers.get("Retry-After", 1)
                    retry_after = float(retry_after)
                    self.__logger.warning(
                        f"Core API is busy, waiting {retry_after} seconds before retrying ...",
                    )
                    sleep(retry_after)
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {self._api.endpoint}instances",
                    )

        if configs_changed:
            self.__logger.info("Custom configs changed, updating ...")
            self.__configs = configs or {}
            custom_configs = []
            for config_type, config_files in self.__configs.items():
                for file, data in config_files.items():
                    site = None
                    name = file
                    if "/" in file:
                        exploded = file.split("/")
                        site = exploded[0]
                        name = exploded[1]
                    custom_configs.append(
                        {
                            "service_id": site,
                            "type": config_type,
                            "name": name.replace(".conf", ""),
                            "data": data,
                        }
                    )

            status = 503
            while status == 503:
                # Send new custom configs to API
                sent, err, status, resp = self._api.request(
                    "PUT",
                    f"/custom_configs?method=autoconf&reload={'false' if config_changed else 'true'}",
                    data=dumps(custom_configs).encode(),
                    additonal_headers={"Authorization": f"Bearer {self._api_token}"} if self._api_token else {},
                )

                if not sent or status not in (200, 503):
                    self.__logger.warning(
                        f"Could not contact core API. Custom configs may not be updated: {err}",
                    )
                    success = False
                elif status == 503:
                    retry_after = resp.headers.get("Retry-After", 1)
                    retry_after = float(retry_after)
                    self.__logger.warning(
                        f"Core API is busy, waiting {retry_after} seconds before retrying ...",
                    )
                    sleep(retry_after)
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {self._api.endpoint}custom_configs",
                    )

        if config_changed:
            status = 503
            while status == 503:
                # Send new config to API
                sent, err, status, resp = self._api.request("PUT", "/config?method=autoconf", data=config, additonal_headers={"Authorization": f"Bearer {self._api_token}"} if self._api_token else {})

                if not sent or status not in (200, 503):
                    self.__logger.warning(
                        f"Could not contact core API. Config may not be updated:\n{err}",
                    )
                    success = False
                elif status == 503:
                    retry_after = resp.headers.get("Retry-After", 1)
                    retry_after = float(retry_after)
                    self.__logger.warning(
                        f"Core API is busy, waiting {retry_after} seconds before retrying ...",
                    )
                    sleep(retry_after)
                else:
                    self.__logger.info(
                        f"Successfully sent API request to {self._api.endpoint}config",
                    )

        return success
