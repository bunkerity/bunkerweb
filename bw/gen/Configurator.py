from glob import glob
from json import loads
from logging import Logger
from re import search as re_search
from sys import path as sys_path
from traceback import format_exc
from typing import Union

sys_path.append("/opt/bunkerweb/utils")


class Configurator:
    def __init__(
        self,
        settings: str,
        core: str,
        plugins: str,
        variables: Union[str, dict],
        logger: Logger,
    ):
        self.__logger = logger
        self.__settings = self.__load_settings(settings)
        self.__core = core
        self.__plugins_settings = []
        self.__plugins = self.__load_plugins(plugins, "plugins")

        if isinstance(variables, str):
            self.__variables = self.__load_variables(variables)
        else:
            self.__variables = variables

        self.__multisite = (
            "MULTISITE" in self.__variables and self.__variables["MULTISITE"] == "yes"
        )
        self.__servers = self.__map_servers()

    def get_settings(self):
        return self.__settings

    def get_plugins_settings(self):
        return self.__plugins_settings

    def __map_servers(self):
        if not self.__multisite or not "SERVER_NAME" in self.__variables:
            return {}
        servers = {}
        for server_name in self.__variables["SERVER_NAME"].split(" "):
            if not re_search(self.__settings["SERVER_NAME"]["regex"], server_name):
                self.__logger.warning(
                    f"Ignoring server name {server_name} because regex is not valid",
                )
                continue
            names = [server_name]
            if f"{server_name}_SERVER_NAME" in self.__variables:
                if not re_search(
                    self.__settings["SERVER_NAME"]["regex"],
                    self.__variables[f"{server_name}_SERVER_NAME"],
                ):
                    self.__logger.warning(
                        f"Ignoring {server_name}_SERVER_NAME because regex is not valid",
                    )
                else:
                    names = self.__variables[f"{server_name}_SERVER_NAME"].split(" ")
            servers[server_name] = names
        return servers

    def __load_settings(self, path):
        with open(path) as f:
            return loads(f.read())

    def __load_plugins(self, path, type: str = "other"):
        plugins = {}
        files = glob(f"{path}/*/plugin.json")
        for file in files:
            try:
                with open(file) as f:
                    data = loads(f.read())

                    if type == "plugins":
                        self.__plugins_settings.append(data)

                    plugins.update(data["settings"])
            except:
                self.__logger.error(
                    f"Exception while loading JSON from {file} : {format_exc()}",
                )

        return plugins

    def __load_variables(self, path):
        variables = {}
        with open(path) as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("#") or line == "" or not "=" in line:
                    continue
                var = line.split("=")[0]
                value = line[len(var) + 1 :]
                variables[var] = value
        return variables

    def get_config(self):
        config = {}
        # Extract default settings
        default_settings = [self.__settings, self.__core, self.__plugins]
        for settings in default_settings:
            for setting, data in settings.items():
                config[setting] = data["default"]

        # Override with variables
        for variable, value in self.__variables.items():
            ret, err = self.__check_var(variable)
            if ret:
                config[variable] = value
            elif not variable.startswith("PYTHON") and variable not in (
                "GPG_KEY",
                "LANG",
                "PATH",
                "NGINX_VERSION",
                "NJS_VERSION",
                "PKG_RELEASE",
                "DOCKER_HOST",
            ):
                self.__logger.warning(f"Ignoring variable {variable} : {err}")
        # Expand variables to each sites if MULTISITE=yes and if not present
        if config.get("MULTISITE", "no") == "yes":
            for server_name in config["SERVER_NAME"].split(" "):
                if server_name == "":
                    continue
                for settings in default_settings:
                    for setting, data in settings.items():
                        if data["context"] == "global":
                            continue
                        key = f"{server_name}_{setting}"
                        if key not in config:
                            if setting == "SERVER_NAME":
                                config[key] = server_name
                            elif setting in config:
                                config[key] = config[setting]
        return config

    def __check_var(self, variable):
        value = self.__variables[variable]
        # MULTISITE=no
        if not self.__multisite:
            where, real_var = self.__find_var(variable)
            if not where:
                return False, f"variable name {variable} doesn't exist"
            if not "regex" in where[real_var]:
                return False, f"missing regex for variable {variable}"
            if not re_search(where[real_var]["regex"], value):
                return (
                    False,
                    f"value {value} doesn't match regex {where[real_var]['regex']}",
                )
            return True, "ok"
        # MULTISITE=yes
        prefixed, real_var = self.__var_is_prefixed(variable)
        where, real_var = self.__find_var(real_var)
        if not where:
            return False, f"variable name {variable} doesn't exist"
        if prefixed and where[real_var]["context"] != "multisite":
            return False, f"context of {variable} isn't multisite"
        if not re_search(where[real_var]["regex"], value):
            return (
                False,
                f"value {value} doesn't match regex {where[real_var]['regex']}",
            )
        return True, "ok"

    def __find_var(self, variable):
        targets = [self.__settings, self.__core, self.__plugins]
        for target in targets:
            if variable in target:
                return target, variable
            for real_var, settings in target.items():
                if "multiple" in settings and re_search(
                    f"^{real_var}_[0-9]+$", variable
                ):
                    return target, real_var
        return False, variable

    def __var_is_prefixed(self, variable):
        for server in self.__servers:
            if variable.startswith(f"{server}_"):
                return True, variable.replace(f"{server}_", "", 1)
        return False, variable
