#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from operator import itemgetter
from os import getenv, sep
from flask import flash
from json import loads as json_loads
from pathlib import Path
from re import error as RegexError, search as re_search
from typing import List, Literal, Optional, Set, Tuple, Union

from app.utils import get_blacklisted_settings, is_editable_method


class Config:
    def __init__(self, db, data) -> None:
        self.__settings = json_loads(Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text(encoding="utf-8"))
        self.__db = db
        self.__data = data
        self.__ignore_regex_check = getenv("IGNORE_REGEX_CHECK", "no").lower() == "yes"

    def gen_conf(
        self, global_conf: dict, services_conf: list[dict], *, check_changes: bool = True, changed_service: Optional[str] = None, override_method: str = "ui"
    ) -> Union[str, Set[str]]:
        """Generates the nginx configuration file from the given configuration

        Parameters
        ----------
        variables : dict
            The configuration to add to the file

        Raises
        ------
        ConfigGenerationError
            If an error occurred during the generation of the configuration file, raises this exception
        """
        conf = global_conf.copy()

        servers = []
        plugins_settings = self.get_plugins_settings()

        def process_service(service):
            server_name = service["SERVER_NAME"].split(" ")[0]
            if not server_name:
                return None

            for k, v in service.items():
                if server_name != changed_service and f"{server_name}_{k}" in conf:
                    continue

                if plugins_settings[k.rsplit("_", 1)[0] if re_search(r"_\d+$", k) else k]["context"] == "multisite":
                    conf[f"{server_name}_{k}"] = v

            return server_name

        with ThreadPoolExecutor() as executor:
            results = executor.map(process_service, services_conf)

        servers.extend(filter(None, results))

        if servers:
            conf["SERVER_NAME"] = " ".join(servers)
        conf["DATABASE_URI"] = self.__db.database_uri

        return self.__db.save_config(conf, override_method, changed=check_changes)

    def get_plugins_settings(self) -> dict:
        return {
            **{k: v for x in self.get_plugins().values() for k, v in x["settings"].items()},
            **self.__settings,
        }

    def get_plugins(self, *, _type: Literal["all", "external", "ui", "pro"] = "all", with_data: bool = False) -> dict:
        db_plugins = self.__db.get_plugins(_type=_type, with_data=with_data)
        db_plugins.sort(key=itemgetter("name"))

        plugins = {"general": {}}

        for plugin in db_plugins.copy():
            plugins[plugin.pop("id")] = plugin

        return plugins

    def get_settings(self) -> dict:
        return self.__settings

    def get_config(
        self,
        global_only: bool = False,
        methods: bool = True,
        with_drafts: bool = False,
        filtered_settings: Optional[Union[List[str], Set[str], Tuple[str]]] = None,
    ) -> dict:
        """Get the nginx variables env file and returns it as a dict

        Returns
        -------
        dict
            The nginx variables env file as a dict
        """
        return self.__db.get_non_default_settings(global_only=global_only, methods=methods, with_drafts=with_drafts, filtered_settings=filtered_settings)

    def get_services(self, methods: bool = True, with_drafts: bool = False) -> list[dict]:
        """Get nginx's services

        Returns
        -------
        list
            The services
        """
        return self.__db.get_services_settings(methods=methods, with_drafts=with_drafts)

    def check_variables(self, variables: dict, config: dict, to_check: dict, *, global_config: bool = False, new: bool = False, threaded: bool = False) -> dict:
        """
        Validate and filter variables based on allowed settings and patterns.

        This function checks each variable from 'to_check' to determine if it is editable:
         - Variables on the blacklist are removed.
         - Variables not defined in the plugin settings (or not matching the allowed multiple format)
           are considered invalid and removed.
         - Variables managed by a non-user method (i.e. not 'default' or 'ui') are not editable
           and are removed.
         - Each variable's value is validated against the regex provided in the plugin settings.
           A RegexError will also result in the variable being removed.

        Error messages are either flashed immediately (non-threaded) or appended to
        self.__data["TO_FLASH"] (threaded).
        """
        self.__data.load_from_file()
        plugins_settings = self.get_plugins_settings()
        blacklisted_settings = get_blacklisted_settings(global_config)

        def report_error(message: str) -> None:
            if threaded:
                self.__data["TO_FLASH"].append({"content": message, "type": "error"})
            else:
                flash(message, "error")

        # Iterate over a copy of the items to safely modify the dictionary.
        for key, value in to_check.items():
            # Remove blacklisted variables.
            if key in blacklisted_settings:
                report_error(f"Variable {key} is not editable, ignoring it.")
                variables.pop(key, None)
                continue

            # Determine the base setting key.
            setting = key
            if key not in plugins_settings:
                if "_" not in key:
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
                    continue

                setting, suffix = key.rsplit("_", 1)
                if setting not in plugins_settings or "multiple" not in plugins_settings[setting] or not suffix.isdigit():
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
                    continue

            # Check if the variable is not editable because it is managed externally.
            if (
                not new
                and setting != "IS_DRAFT"
                and key in config
                and ((global_config or not config[key].get("global", False)) and not is_editable_method(config[key].get("method"), allow_default=True))
            ):
                report_error(f"Variable {key} is not editable as it is managed by the {config[key]['method']}, ignoring it.")
                variables.pop(key, None)
                continue

            # Validate the variable's value against the regex pattern.
            try:
                if not self.__ignore_regex_check and re_search(plugins_settings[setting]["regex"], value) is None:
                    report_error(f"Variable {key} is not valid.")
                    variables.pop(key, None)
            except RegexError as e:
                report_error(f"Invalid regex for setting {setting}: {plugins_settings[setting]['regex']}. Ignoring regex check: {e}")
                variables.pop(key, None)

        return variables

    def new_service(self, variables: dict, is_draft: bool = False, override_method: str = "ui", check_changes: bool = True) -> Tuple[str, int]:
        """Creates a new service from the given variables

        Parameters
        ----------
        variables : dict
            The settings for the new service

        Returns
        -------
        str
            The confirmation message

        Raises
        ------
        Exception
            raise this if the service already exists
        """
        services = self.get_services(methods=False, with_drafts=True)
        server_name_splitted = variables["SERVER_NAME"].split(" ")
        for service in services:
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in server_name_splitted:
                return f"Service {service['SERVER_NAME'].split(' ')[0]} already exists.", 1

        services.append(variables | {"IS_DRAFT": "yes" if is_draft else "no"})
        ret = self.gen_conf(
            self.get_config(methods=False), services, check_changes=False if not check_changes else not is_draft, override_method=override_method
        )
        if isinstance(ret, str):
            return ret, 1
        return f"Configuration for {variables['SERVER_NAME'].split(' ')[0]} has been generated.", 0

    def edit_service(
        self, old_server_name: str, variables: dict, *, check_changes: bool = True, is_draft: bool = False, override_method: str = "ui"
    ) -> Tuple[str, int]:
        """Edits a service

        Parameters
        ----------
        old_server_name : str
            The old server name
        variables : dict
            The settings to change for the service

        Returns
        -------
        str
            the confirmation message
        """
        services = self.get_services(methods=False, with_drafts=True)
        changed_server_name = old_server_name != variables["SERVER_NAME"]
        server_name_splitted = variables["SERVER_NAME"].split(" ")
        old_server_name_splitted = old_server_name.split(" ")
        for i in range(len(services) - 1, -1, -1):
            service = services[i]
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in server_name_splitted:
                if changed_server_name and service["SERVER_NAME"].split(" ")[0] != old_server_name_splitted[0]:
                    return f"Service {service['SERVER_NAME'].split(' ')[0]} already exists.", 1
                services.pop(i)
            elif changed_server_name and (service["SERVER_NAME"] == old_server_name or service["SERVER_NAME"] in old_server_name_splitted):
                services.pop(i)

        services.append(variables | {"IS_DRAFT": "yes" if is_draft else "no"})
        config = self.get_config(global_only=True, methods=False)

        if changed_server_name and server_name_splitted[0] != old_server_name_splitted[0]:
            for k in config.copy():
                if k.startswith(old_server_name_splitted[0]):
                    config.pop(k)

        ret = self.gen_conf(config, services, check_changes=check_changes, changed_service=server_name_splitted[0], override_method=override_method)
        if isinstance(ret, str):
            return ret, 1
        return f"Configuration for {old_server_name_splitted[0]} has been edited.", 0

    def edit_global_conf(self, variables: dict, *, check_changes: bool = True, override_method: str = "ui") -> Tuple[str, int]:
        """Edits the global conf

        Parameters
        ----------
        variables : dict
            The settings to change for the conf

        Returns
        -------
        str
            the confirmation message
        """
        ret = self.gen_conf(variables, self.get_services(methods=False, with_drafts=True), check_changes=check_changes, override_method=override_method)
        if isinstance(ret, str):
            return ret, 1
        return "The global configuration has been edited.", 0

    def delete_service(self, service_name: str, *, check_changes: bool = True, override_method: str = "ui") -> Tuple[str, int]:
        """Deletes a service

        Parameters
        ----------
        service_name : str
            The name of the service to edit

        Returns
        -------
        str
            The confirmation message

        Raises
        ------
        Exception
            raises this if the service_name given isn't found
        """
        service_name = service_name.split(" ")[0]
        full_env = self.get_config(methods=False)
        services = self.get_services(methods=False, with_drafts=True)
        new_services = []
        found = False

        for service in services:
            if service["SERVER_NAME"].split(" ")[0] == service_name:
                found = True
            else:
                new_services.append(service)

        if not found:
            return f"Can't delete missing {service_name} configuration.", 1

        full_env["SERVER_NAME"] = " ".join([s for s in full_env["SERVER_NAME"].split(" ") if s != service_name])

        new_env = full_env.copy()

        for k in full_env:
            if k.startswith(service_name):
                new_env.pop(k)

                for service in new_services:
                    if k in service:
                        service.pop(k)

        ret = self.gen_conf(new_env, new_services, check_changes=check_changes, override_method=override_method)
        if isinstance(ret, str):
            return ret, 1
        return f"Configuration for {service_name} has been deleted.", 0
