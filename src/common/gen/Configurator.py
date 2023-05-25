#!/usr/bin/python3

from glob import glob
from hashlib import sha256
from io import BytesIO
from json import loads
from logging import Logger
from os import listdir, sep
from os.path import basename, dirname, join
from pathlib import Path
from re import compile as re_compile, search as re_search
from sys import path as sys_path
from tarfile import open as tar_open
from traceback import format_exc
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

if join(sep, "usr", "share", "bunkerweb", "utils") not in sys_path:
    sys_path.append(join(sep, "usr", "share", "bunkerweb", "utils"))


class Configurator:
    def __init__(
        self,
        settings: str,
        core: str,
        external_plugins: Union[str, List[Dict[str, Any]]],
        variables: Union[str, Dict[str, Any]],
        logger: Logger,
    ):
        self.__logger = logger
        self.__plugin_id_rx = re_compile(r"^[\w.-]{1,64}$")
        self.__plugin_version_rx = re_compile(r"^\d+\.\d+(\.\d+)?$")
        self.__setting_id_rx = re_compile(r"^[A-Z0-9_]{1,256}$")
        self.__name_rx = re_compile(r"^[\w.-]{1,128}$")
        self.__job_file_rx = re_compile(r"^[\w./-]{1,256}$")
        self.__settings = self.__load_settings(settings)
        self.__core_plugins = self.__load_plugins(core)

        if isinstance(external_plugins, str):
            self.__external_plugins = self.__load_plugins(external_plugins, "external")
        else:
            self.__external_plugins = external_plugins

        if isinstance(variables, str):
            self.__variables = self.__load_variables(variables)
        else:
            self.__variables = variables

        self.__multisite = self.__variables.get("MULTISITE", "no") == "yes"
        self.__servers = self.__map_servers()

    def get_settings(self) -> Dict[str, Any]:
        return self.__settings

    def get_plugins(
        self, _type: Union[Literal["core"], Literal["external"]]
    ) -> List[Dict[str, Any]]:
        return self.__core_plugins if _type == "core" else self.__external_plugins

    def get_plugins_settings(
        self, _type: Union[Literal["core"], Literal["external"]]
    ) -> Dict[str, Any]:
        if _type == "core":
            plugins = self.__core_plugins
        else:
            plugins = self.__external_plugins
        plugins_settings = {}

        for plugin in plugins:
            plugins_settings.update(plugin["settings"])

        return plugins_settings

    def __map_servers(self) -> Dict[str, List[str]]:
        if not self.__multisite or not "SERVER_NAME" in self.__variables:
            return {}
        servers = {}
        for server_name in self.__variables["SERVER_NAME"].strip().split(" "):
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
                    names = (
                        self.__variables[f"{server_name}_SERVER_NAME"]
                        .strip()
                        .split(" ")
                    )

            servers[server_name] = names
        return servers

    def __load_settings(self, path: str) -> Dict[str, Any]:
        return loads(Path(path).read_text())

    def __load_plugins(self, path: str, _type: str = "core") -> List[Dict[str, Any]]:
        plugins = []
        files = glob(join(path, "*", "plugin.json"))
        for file in files:
            try:
                data = self.__load_settings(file)

                resp, msg = self.__validate_plugin(data)
                if not resp:
                    self.__logger.warning(
                        f"Ignoring plugin {file} : {msg}",
                    )
                    continue

                if _type == "external":
                    plugin_content = BytesIO()
                    with tar_open(fileobj=plugin_content, mode="w:gz") as tar:
                        tar.add(
                            dirname(file),
                            arcname=basename(dirname(file)),
                            recursive=True,
                        )
                    plugin_content.seek(0)
                    value = plugin_content.getvalue()

                    data.update(
                        {
                            "external": path.startswith(
                                join(sep, "etc", "bunkerweb", "plugins")
                            ),
                            "page": "ui" in listdir(dirname(file)),
                            "method": "manual",
                            "data": value,
                            "checksum": sha256(value).hexdigest(),
                        }
                    )

                plugins.append(data)
            except:
                self.__logger.error(
                    f"Exception while loading JSON from {file} : {format_exc()}",
                )

        return plugins

    def __load_variables(self, path: str) -> Dict[str, Any]:
        variables = {}
        with open(path) as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or not "=" in line:
                    continue
                splitted = line.split("=", 1)
                variables[splitted[0]] = splitted[1]
        return variables

    def get_config(self) -> Dict[str, Any]:
        config = {}
        # Extract default settings
        default_settings = [
            self.__settings,
            self.get_plugins_settings("core"),
            self.get_plugins_settings("external"),
        ]
        for settings in default_settings:
            for setting, data in settings.items():
                config[setting] = data["default"]

        # Override with variables
        for variable, value in self.__variables.items():
            ret, err = self.__check_var(variable)
            if ret:
                config[variable] = value
            elif (
                not variable.startswith("PYTHON")
                and not variable.startswith("KUBERNETES_SERVICE_")
                and not variable.startswith("KUBERNETES_PORT_")
                and not variable.startswith("SVC_")
                and variable
                not in (
                    "GPG_KEY",
                    "LANG",
                    "PATH",
                    "NGINX_VERSION",
                    "NJS_VERSION",
                    "PKG_RELEASE",
                    "DOCKER_HOST",
                )
            ):
                self.__logger.warning(f"Ignoring variable {variable} : {err}")
        # Expand variables to each sites if MULTISITE=yes and if not present
        if config.get("MULTISITE", "no") == "yes":
            for server_name in config["SERVER_NAME"].split(" "):
                server_name = server_name.strip()
                if not server_name:
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

    def __check_var(self, variable: str) -> Tuple[bool, str]:
        value = self.__variables[variable]
        # MULTISITE=no
        if not self.__multisite:
            where, real_var = self.__find_var(variable)
            if not where:
                return False, f"variable name {variable} doesn't exist"
            elif not re_search(where[real_var]["regex"], value):
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
        elif prefixed and where[real_var]["context"] != "multisite":
            return False, f"context of {variable} isn't multisite"
        elif not re_search(where[real_var]["regex"], value):
            return (
                False,
                f"value {value} doesn't match regex {where[real_var]['regex']}",
            )
        return True, "ok"

    def __find_var(self, variable: str) -> Tuple[Optional[Dict[str, Any]], str]:
        targets = [
            self.__settings,
            self.get_plugins_settings("core"),
            self.get_plugins_settings("external"),
        ]
        for target in targets:
            if variable in target:
                return target, variable
            for real_var, settings in target.items():
                if "multiple" in settings and re_search(
                    f"^{real_var}_[0-9]+$", variable
                ):
                    return target, real_var
        return None, variable

    def __var_is_prefixed(self, variable: str) -> Tuple[bool, str]:
        for server in self.__servers:
            if variable.startswith(f"{server}_"):
                return True, variable.replace(f"{server}_", "", 1)
        return False, variable

    def __validate_plugin(self, plugin: dict) -> Tuple[bool, str]:
        if not all(
            key in plugin.keys()
            for key in [
                "id",
                "name",
                "description",
                "version",
                "stream",
                "settings",
            ]
        ):
            return (
                False,
                f"Missing mandatory keys for plugin {plugin.get('id', 'unknown')} (id, name, description, version, stream, settings)",
            )

        if not self.__plugin_id_rx.match(plugin["id"]):
            return (
                False,
                f"Invalid id for plugin {plugin['id']} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 64))",
            )
        elif len(plugin["name"]) > 128:
            return (
                False,
                f"Invalid name for plugin {plugin['id']} (Max 128 characters)",
            )
        elif len(plugin["description"]) > 256:
            return (
                False,
                f"Invalid description for plugin {plugin['id']} (Max 256 characters)",
            )
        elif not self.__plugin_version_rx.match(plugin["version"]):
            return (
                False,
                f"Invalid version for plugin {plugin['id']} (Must be in format \d+\.\d+(\.\d+)?)",
            )
        elif plugin["stream"] not in ["yes", "no", "partial"]:
            return (
                False,
                f"Invalid stream for plugin {plugin['id']} (Must be yes, no or partial)",
            )

        for setting, data in plugin["settings"].items():
            if not all(
                key in data.keys()
                for key in [
                    "context",
                    "default",
                    "help",
                    "id",
                    "label",
                    "regex",
                    "type",
                ]
            ):
                return (
                    False,
                    f"missing keys for setting {setting} in plugin {plugin['id']}, must have context, default, help, id, label, regex and type",
                )

            if not self.__setting_id_rx.match(setting):
                return (
                    False,
                    f"Invalid setting name for setting {setting} in plugin {plugin['id']} (Can only contain capital letters and underscores (min 1 characters and max 256))",
                )
            elif data["context"] not in ["global", "multisite"]:
                return (
                    False,
                    f"Invalid context for setting {setting} in plugin {plugin['id']} (Must be global or multisite)",
                )
            elif len(data["default"]) > 4096:
                return (
                    False,
                    f"Invalid default for setting {setting} in plugin {plugin['id']} (Max 4096 characters)",
                )
            elif len(data["help"]) > 512:
                return (
                    False,
                    f"Invalid help for setting {setting} in plugin {plugin['id']} (Max 512 characters)",
                )
            elif len(data["label"]) > 256:
                return (
                    False,
                    f"Invalid label for setting {setting} in plugin {plugin['id']} (Max 256 characters)",
                )
            elif len(data["regex"]) > 1024:
                return (
                    False,
                    f"Invalid regex for setting {setting} in plugin {plugin['id']} (Max 1024 characters)",
                )
            elif data["type"] not in ["password", "text", "check", "select"]:
                return (
                    False,
                    f"Invalid type for setting {setting} in plugin {plugin['id']} (Must be password, text, check or select)",
                )

            if "multiple" in data:
                if not self.__name_rx.match(data["multiple"]):
                    return (
                        False,
                        f"Invalid multiple for setting {setting} in plugin {plugin['id']} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 128))",
                    )

            for select in data.get("select", []):
                if len(select) > 256:
                    return (
                        False,
                        f"Invalid select value {select} for setting {setting} in plugin {plugin['id']} (Max 256 characters)",
                    )

        for job in plugin.get("jobs", []):
            if not all(
                key in job.keys()
                for key in [
                    "name",
                    "file",
                    "every",
                    "reload",
                ]
            ):
                return (
                    False,
                    f"missing keys for job {job['name']} in plugin {plugin['id']}, must have name, file, every and reload",
                )

            if not self.__name_rx.match(job["name"]):
                return (
                    False,
                    f"Invalid name for job {job['name']} in plugin {plugin['id']}",
                )
            elif not self.__job_file_rx.match(job["file"]):
                return (
                    False,
                    f"Invalid file for job {job['name']} in plugin {plugin['id']} (Can only contain numbers, letters, underscores, hyphens and slashes (min 1 characters and max 256))",
                )
            elif job["every"] not in ["once", "minute", "hour", "day", "week"]:
                return (
                    False,
                    f"Invalid every for job {job['name']} in plugin {plugin['id']} (Must be once, minute, hour, day or week)",
                )
            elif job["reload"] is not True and job["reload"] is not False:
                return (
                    False,
                    f"Invalid reload for job {job['name']} in plugin {plugin['id']} (Must be true or false)",
                )

        return True, "ok"
