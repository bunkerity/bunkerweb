#!/usr/bin/env python3

from copy import deepcopy
from functools import cache
from io import BytesIO
from json import loads
from logging import Logger
from os import listdir, sep
from os.path import join
from pathlib import Path
from re import compile as re_compile, error as RegexError, search as re_search
from sys import path as sys_path
from tarfile import open as tar_open
from typing import Dict, List, Literal, Optional, Tuple, Union

if join(sep, "usr", "share", "bunkerweb", "utils") not in sys_path:
    sys_path.append(join(sep, "usr", "share", "bunkerweb", "utils"))

from common_utils import bytes_hash  # type: ignore


class Configurator:
    def __init__(
        self,
        settings: str,
        core: str,
        external_plugins: Union[str, List[Dict[str, str]]],
        pro_plugins: Union[str, List[Dict[str, str]]],
        variables: Union[str, Dict[str, str]],
        logger: Logger,
    ):
        self.__logger = logger
        self.__plugin_id_rx = re_compile(r"^[\w.-]{1,64}$")
        self.__plugin_version_rx = re_compile(r"^\d+\.\d+(\.\d+)?$")
        self.__setting_id_rx = re_compile(r"^[A-Z0-9_]{1,256}$")
        self.__name_rx = re_compile(r"^[\w.-]{1,128}$")
        self.__job_file_rx = re_compile(r"^[\w./-]{1,256}$")
        self.__settings = self.__load_settings(Path(settings))
        self.__core_plugins = []
        self.__load_plugins(Path(core))

        if isinstance(external_plugins, str):
            self.__external_plugins = []
            self.__load_plugins(Path(external_plugins), "external")
        else:
            self.__external_plugins = external_plugins

        if isinstance(pro_plugins, str):
            self.__pro_plugins = []
            self.__load_plugins(Path(pro_plugins), "pro")
        else:
            self.__pro_plugins = pro_plugins

        if isinstance(variables, str):
            self.__variables = self.__load_variables(Path(variables))
        else:
            self.__variables = variables

        self.__multisite = self.__variables.get("MULTISITE", "no") == "yes"
        self.__servers = self.__map_servers()

    def get_settings(self) -> Dict[str, str]:
        return self.__settings.copy()

    def get_plugins(self, _type: Literal["core", "external", "pro"]) -> List[Dict[str, str]]:
        return {"core": deepcopy(self.__core_plugins), "external": deepcopy(self.__external_plugins), "pro": deepcopy(self.__pro_plugins)}.get(_type, [])

    @cache
    def get_plugins_settings(self, _type: Literal["core", "external", "pro"]) -> Dict[str, str]:
        plugins_settings = {}
        for plugin in self.get_plugins(_type):
            plugins_settings.update(plugin.get("settings", {}))
        return plugins_settings

    @cache
    def __map_servers(self) -> Dict[str, List[str]]:
        if not self.__multisite or "SERVER_NAME" not in self.__variables:
            return {}

        servers = {}
        for server_name in self.__variables["SERVER_NAME"].strip().split(" "):
            if not server_name:
                continue

            if re_search(self.__settings["SERVER_NAME"]["regex"], server_name) is None:
                self.__logger.warning(f"Ignoring server name {server_name} because regex is not valid")
                continue

            names = [server_name]
            if f"{server_name}_SERVER_NAME" in self.__variables:
                if re_search(self.__settings["SERVER_NAME"]["regex"], self.__variables[f"{server_name}_SERVER_NAME"]) is None:
                    self.__logger.warning(f"Ignoring {server_name}_SERVER_NAME because regex is not valid")
                else:
                    names = self.__variables[f"{server_name}_SERVER_NAME"].strip().split(" ")

            servers[server_name] = names
        return servers

    def __load_settings(self, path: Path) -> Dict[str, str]:
        return loads(path.read_text())

    def __load_plugins(self, path: Path, _type: Literal["core", "external", "pro"] = "core"):
        x = 0
        for file in path.glob("*/plugin.json"):
            self.__logger.debug(f"Loading {_type} plugin {file}")
            self.__load_plugin(file, _type)
            x += 1

        self.__logger.info(f"Computed {x} {_type} plugin{'s' if x > 1 else ''}")

    def __load_plugin(self, file: Path, _type: Literal["core", "external", "pro"] = "core"):
        try:
            data = self.__load_settings(file)

            resp, msg = self.__validate_plugin(data)
            if not resp:
                self.__logger.warning(f"Ignoring {_type} plugin {file} : {msg}")
                return

            data["page"] = "ui" in listdir(file.parent)

            if _type != "core":
                with BytesIO() as plugin_content:
                    with tar_open(fileobj=plugin_content, mode="w:gz", compresslevel=9) as tar:
                        tar.add(file.parent, arcname=file.parent.name, recursive=True)
                    plugin_content.seek(0)
                    checksum = bytes_hash(plugin_content, algorithm="sha256")
                    value = plugin_content.getvalue()

                data.update({"type": _type, "method": "manual", "data": value, "checksum": checksum})

                if _type == "pro":
                    self.__pro_plugins.append(data)
                else:
                    self.__external_plugins.append(data)
                self.__logger.debug(f"Loaded {_type} plugin {file} with {len(data.get('settings', {}))} setting(s)")
                return
            self.__core_plugins.append(data)
            self.__logger.debug(f"Loaded core plugin {file} with {len(data.get('settings', {}))} setting(s)")
        except BaseException as e:
            self.__logger.error(f"Exception while loading JSON from {file} : {e}")

    def __load_variables(self, path: Path) -> Dict[str, str]:
        variables = {}
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                split = line.split("=", 1)
                variables[split[0]] = split[1]
        return variables

    def get_config(self, db=None, *, first_run: bool = False) -> Dict[str, str]:
        config = {}
        template = self.__variables.get("USE_TEMPLATE", "")

        # Extract default settings
        default_settings = [
            self.get_settings(),
            self.get_plugins_settings("core"),
            self.get_plugins_settings("external"),
            self.get_plugins_settings("pro"),
        ]

        if not default_settings[0]:
            self.__logger.error("No settings found, exiting")
            exit(1)
        elif not default_settings[1]:
            self.__logger.error("No core plugins found, exiting")
            exit(1)

        # Extract template overridden settings
        template_settings = {}
        if template and db:
            self.__logger.info(f"Using template {template}")
            template_settings = db.get_template_settings(template)

        for settings in default_settings:
            for setting, data in settings.items():
                config[setting] = template_settings.get(setting, data["default"])

        # Override with variables
        for variable, value in self.__variables.items():
            ret, err = self.__check_var(variable)
            if ret:
                config[variable] = value
            elif (not first_run or not self.__variables.get("EXTERNAL_PLUGIN_URLS")) and (
                variable == "KUBERNETES_MODE"
                or (
                    "CUSTOM_CONF" not in variable
                    and not variable.startswith(("_", "PYTHON", "KUBERNETES_", "SVC_", "LB_"))
                    and variable
                    not in (
                        "DOCKER_HOST",
                        "SLAVE_MODE",
                        "MASTER_MODE",
                        "CUSTOM_LOG_LEVEL",
                        "HEALTHCHECK_INTERVAL",
                        "GPG_KEY",
                        "HOME",
                        "HOSTNAME",
                        "LANG",
                        "PATH",
                        "NGINX_VERSION",
                        "NJS_VERSION",
                        "PATH",
                        "PKG_RELEASE",
                        "PWD",
                        "SHLVL",
                        "SERVER_SOFTWARE",
                        "NAMESPACE",
                        "TZ",
                        "DYNPKG_RELEASE",
                    )
                )
            ):
                self.__logger.warning(f"Ignoring variable {variable} : {err} - {value = !r}")

        # Expand variables to each sites if MULTISITE=yes and if not present
        if config.get("MULTISITE", "no") == "yes":
            for server_name in config["SERVER_NAME"].strip().split(" "):
                server_name = server_name.strip()
                if not server_name:
                    continue

                service_template = config.get(f"{server_name}_USE_TEMPLATE", template)
                service_template_settings = {}
                if service_template != template and db:
                    service_template_settings = db.get_template_settings(service_template)

                for settings in default_settings:
                    for setting, data in settings.items():
                        if data["context"] == "global":
                            continue

                        key = f"{server_name}_{setting}"
                        if key not in config:
                            if setting == "SERVER_NAME":
                                config[key] = server_name
                            elif setting in config:
                                config[key] = service_template_settings.get(setting, config[setting])

        return config

    def __check_var(self, variable: str) -> Tuple[bool, str]:
        value = self.__variables[variable]
        # MULTISITE=no
        if not self.__multisite:
            where, real_var = self.__find_var(variable)
            if not where:
                return False, f"variable name {variable} doesn't exist"

            try:
                if re_search(where[real_var]["regex"], value) is None:
                    return (False, f"value {value} doesn't match regex {where[real_var]['regex']}")
            except RegexError:
                self.__logger.warning(f"Invalid regex for {variable} : {where[real_var]['regex']}, ignoring regex check")

            return True, "ok"
        # MULTISITE=yes
        prefixed, real_var = self.__var_is_prefixed(variable)
        where, real_var = self.__find_var(real_var)
        if not where:
            return False, f"variable name {variable} doesn't exist"
        elif prefixed and where[real_var]["context"] != "multisite":
            return False, f"context of {variable} isn't multisite"

        try:
            if not re_search(where[real_var]["regex"], value):
                return (False, f"value {value} doesn't match regex {where[real_var]['regex']}")
        except RegexError:
            self.__logger.warning(f"Invalid regex for {variable} : {where[real_var]['regex']}, ignoring regex check")

        return True, "ok"

    def __find_var(self, variable: str) -> Tuple[Optional[Dict[str, str]], str]:
        targets = [
            self.get_settings(),
            self.get_plugins_settings("core"),
            self.get_plugins_settings("external"),
            self.get_plugins_settings("pro"),
        ]
        for target in targets:
            if variable in target:
                return target, variable
            for real_var, settings in target.items():
                if "multiple" in settings and re_search(f"^{real_var}_[0-9]+$", variable):
                    return target, real_var
        return None, variable

    def __var_is_prefixed(self, variable: str) -> Tuple[bool, str]:
        for server in self.__servers:
            if variable.startswith(f"{server}_"):
                return True, variable.replace(f"{server}_", "", 1)
        return False, variable

    def __validate_plugin(self, plugin: dict) -> Tuple[bool, str]:
        if not all(key in plugin for key in ("id", "name", "description", "version", "stream", "settings")):
            return (False, f"Missing mandatory keys for plugin {plugin.get('id', 'unknown')} (id, name, description, version, stream, settings)")

        if not self.__plugin_id_rx.match(plugin["id"]):
            return (False, f"Invalid id for plugin {plugin['id']} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 64))")
        elif len(plugin["name"]) > 128:
            return (False, f"Invalid name for plugin {plugin['id']} (Max 128 characters)")
        elif len(plugin["description"]) > 256:
            return (False, f"Invalid description for plugin {plugin['id']} (Max 256 characters)")
        elif not self.__plugin_version_rx.match(plugin["version"]):
            return (False, f"Invalid version for plugin {plugin['id']} (Must be in format \\d+\\.\\d+(\\.\\d+)?)")
        elif plugin["stream"] not in ("yes", "no", "partial"):
            return (False, f"Invalid stream for plugin {plugin['id']} (Must be yes, no or partial)")

        for setting, data in plugin.get("settings", {}).items():
            if not all(key in data.keys() for key in ("context", "default", "help", "id", "label", "regex", "type")):
                return (False, f"missing keys for setting {setting} in plugin {plugin['id']}, must have context, default, help, id, label, regex and type")

            if not self.__setting_id_rx.match(setting):
                return (
                    False,
                    f"Invalid setting name for setting {setting} in plugin {plugin['id']} (Can only contain capital letters and underscores (min 1 characters and max 256))",
                )
            elif data["context"] not in ("global", "multisite"):
                return (False, f"Invalid context for setting {setting} in plugin {plugin['id']} (Must be global or multisite)")
            elif len(data["default"]) > 4096:
                return (False, f"Invalid default for setting {setting} in plugin {plugin['id']} (Max 4096 characters)")
            elif len(data["help"]) > 512:
                return (False, f"Invalid help for setting {setting} in plugin {plugin['id']} (Max 512 characters)")
            elif len(data["label"]) > 256:
                return (False, f"Invalid label for setting {setting} in plugin {plugin['id']} (Max 256 characters)")
            elif len(data["regex"]) > 1024:
                return (False, f"Invalid regex for setting {setting} in plugin {plugin['id']} (Max 1024 characters)")
            elif data["type"] not in ("password", "text", "check", "select"):
                return (False, f"Invalid type for setting {setting} in plugin {plugin['id']} (Must be password, text, check or select)")

            if "multiple" in data:
                if not self.__name_rx.match(data["multiple"]):
                    return (
                        False,
                        f"Invalid multiple for setting {setting} in plugin {plugin['id']} (Can only contain numbers, letters, underscores and hyphens (min 1 characters and max 128))",
                    )

            for select in data.get("select", []):
                if len(select) > 256:
                    return (False, f"Invalid select value {select} for setting {setting} in plugin {plugin['id']} (Max 256 characters)")

        for job in plugin.get("jobs", []):
            if not all(key in job.keys() for key in ("name", "file", "every", "reload")):
                return (False, f"missing keys for job {job['name']} in plugin {plugin['id']}, must have name, file, every and reload")

            if not self.__name_rx.match(job["name"]):
                return (False, f"Invalid name for job {job['name']} in plugin {plugin['id']}")
            elif not self.__job_file_rx.match(job["file"]):
                return (
                    False,
                    f"Invalid file for job {job['name']} in plugin {plugin['id']} (Can only contain numbers, letters, underscores, hyphens and slashes (min 1 characters and max 256))",
                )
            elif job["every"] not in ("once", "minute", "hour", "day", "week"):
                return (False, f"Invalid every for job {job['name']} in plugin {plugin['id']} (Must be once, minute, hour, day or week)")
            elif job.get("reload", False) is not True and job.get("reload", False) is not False:
                return (False, f"Invalid reload for job {job['name']} in plugin {plugin['id']} (Must be true or false)")
            elif job.get("async", False) is not True and job.get("async", False) is not False:
                return (False, f"Invalid async for job {job['name']} in plugin {plugin['id']} (Must be true or false)")

        return True, "ok"
