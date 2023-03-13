from json import JSONDecodeError, load
from glob import glob
from re import match
from traceback import format_exc

from logger import setup_logger


class ConfigCaller:
    def __init__(self):
        self.__logger = setup_logger("Config", "INFO")
        with open("/usr/share/bunkerweb/settings.json", "r") as f:
            self._settings = load(f)
        for plugin in glob("/usr/share/bunkerweb/core/*/plugin.json") + glob(
            "/etc/bunkerweb/plugins/*/plugin.json"
        ):
            with open(plugin, "r") as f:
                try:
                    self._settings.update(load(f)["settings"])
                except KeyError:
                    self.__logger.error(
                        f'Error while loading plugin metadata file at {plugin} : missing "settings" key',
                    )
                except JSONDecodeError:
                    self.__logger.error(
                        f"Exception while loading plugin metadata file at {plugin} :\n{format_exc()}",
                    )

    def _is_setting(self, setting):
        return setting in self._settings

    def _is_global_setting(self, setting):
        if self._is_setting(setting):
            return self._settings[setting]["context"] == "global"
        elif match(r"^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[:-1])
            return (
                self._is_setting(multiple_setting)
                and self._settings[multiple_setting]["context"] == "global"
                and "multiple" in self._settings[multiple_setting]
            )
        return False

    def _is_multisite_setting(self, setting):
        if self._is_setting(setting):
            return self._settings[setting]["context"] == "multisite"
        if match(r"^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[0:-1])
            return (
                self._is_setting(multiple_setting)
                and self._settings[multiple_setting]["context"] == "multisite"
                and "multiple" in self._settings[multiple_setting]
            )
        return False

    def _full_env(self, env_instances, env_services):
        full_env = {}
        # Fill with default values
        for k, v in self._settings.items():
            full_env[k] = v["default"]
        # Replace with instances values
        for k, v in env_instances.items():
            full_env[k] = v
            if (
                not self._is_global_setting(k)
                and env_instances.get("MULTISITE", "no") == "yes"
                and env_instances.get("SERVER_NAME", "") != ""
            ):
                for server_name in env_instances["SERVER_NAME"].split(" "):
                    full_env[f"{server_name}_{k}"] = v
        # Replace with services values
        for k, v in env_services.items():
            full_env[k] = v
        return full_env
