#!/usr/bin/python3

from glob import glob
from json import JSONDecodeError, loads
from os import sep
from os.path import join
from pathlib import Path
from re import match
from traceback import format_exc
from typing import Any, Dict, Literal, Union

from logger import setup_logger


class ConfigCaller:
    def __init__(self):
        self.__logger = setup_logger("Config", "INFO")
        self._settings = loads(
            Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text()
        )
        for plugin in glob(
            join(sep, "usr", "share", "bunkerweb", "core", "*", "plugin.json")
        ) + glob(join(sep, "etc", "bunkerweb", "plugins", "*", "plugin.json")):
            try:
                self._settings.update(loads(Path(plugin).read_text())["settings"])
            except KeyError:
                self.__logger.error(
                    f'Error while loading plugin metadata file at {plugin} : missing "settings" key',
                )
            except JSONDecodeError:
                self.__logger.error(
                    f"Exception while loading plugin metadata file at {plugin} :\n{format_exc()}",
                )

    def _is_setting(self, setting) -> bool:
        return setting in self._settings

    def _is_setting_context(
        self, setting: str, context: Union[Literal["global"], Literal["multisite"]]
    ) -> bool:
        if self._is_setting(setting):
            return self._settings[setting]["context"] == context
        elif match(r"^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[:-1])
            return (
                self._is_setting(multiple_setting)
                and self._settings[multiple_setting]["context"] == context
                and "multiple" in self._settings[multiple_setting]
            )
        return False

    def _full_env(
        self, env_instances: Dict[str, Any], env_services: Dict[str, Any]
    ) -> Dict[str, Any]:
        full_env = {}
        # Fill with default values
        for k, v in self._settings.items():
            full_env[k] = v["default"]
        # Replace with instances values
        for k, v in env_instances.items():
            full_env[k] = v
            if (
                not self._is_setting_context(k, "global")
                and env_instances.get("MULTISITE", "no") == "yes"
                and env_instances.get("SERVER_NAME", "") != ""
            ):
                for server_name in env_instances["SERVER_NAME"].split(" "):
                    full_env[f"{server_name}_{k}"] = v
        # Replace with services values
        full_env = full_env | env_services
        return full_env
