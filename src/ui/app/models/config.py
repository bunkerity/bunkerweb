#!/usr/bin/env python3

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from operator import itemgetter
from os import sep
from flask import flash
from json import loads as json_loads
from pathlib import Path
from re import error as RegexError, search as re_search
from typing import List, Literal, Optional, Set, Tuple, Union

from app.utils import get_blacklisted_settings


class Config:
    def __init__(self, db, data) -> None:
        self.__settings = json_loads(Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text(encoding="utf-8"))
        self.__db = db
        self.__data = data

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

    def check_variables(
        self,
        variables: dict,
        config: dict,
        *,
        global_config: bool = False,
        ignored_multiples: Optional[Set[str]] = None,
        new: bool = False,
        threaded: bool = False,
    ) -> dict:
        """Testify that the variables passed are valid

        Parameters
        ----------
        variables : dict
            The dict to check

        Returns
        -------
        int
            Return the error code
        """
        self.__data.load_from_file()
        plugins_settings = self.get_plugins_settings()
        blacklisted_settings = get_blacklisted_settings(global_config)

        for k, v in variables.copy().items():
            check = False

            if k in plugins_settings:
                setting = k
            else:
                setting = k[0 : k.rfind("_")]  # noqa: E203
                if setting not in plugins_settings or "multiple" not in plugins_settings[setting]:
                    content = f"Variable {k} is not valid."
                    if threaded:
                        self.__data["TO_FLASH"].append({"content": content, "type": "error"})
                    else:
                        flash(content, "error")
                    variables.pop(k)
                    continue

            if setting in blacklisted_settings:
                message = f"Variable {k} is not editable, ignoring it"
                if threaded:
                    self.__data["TO_FLASH"].append({"content": message, "type": "error"})
                else:
                    flash(message, "error")
                variables.pop(k)
                continue
            elif setting not in config and plugins_settings[setting]["default"] == v:
                variables.pop(k)
                continue
            elif (
                not new
                and setting != "IS_DRAFT"
                and setting in config
                and ((global_config or not config[setting]["global"]) and config[setting]["method"] not in ("default", "ui"))
            ):
                message = f"Variable {k} is not editable as is it managed by the {config[setting]['method']}, ignoring it"
                if threaded:
                    self.__data["TO_FLASH"].append({"content": message, "type": "error"})
                else:
                    flash(message, "error")
                variables.pop(k)
                continue

            try:
                if re_search(plugins_settings[setting]["regex"], v):
                    check = True
            except RegexError as e:
                message = f"Invalid regex for setting {setting} : {plugins_settings[setting]['regex']}, ignoring regex check:{e}"
                if threaded:
                    self.__data["TO_FLASH"].append({"content": message, "type": "error"})
                else:
                    flash(message, "error")
                variables.pop(k)
                continue

            if not check:
                message = f"Variable {k} is not valid."
                if threaded:
                    self.__data["TO_FLASH"].append({"content": message, "type": "error"})
                else:
                    flash(message, "error")
                variables.pop(k)

        ignored_multiples = ignored_multiples or set()
        for k in config:
            if k in plugins_settings or k in ignored_multiples:
                continue
            setting = k[0 : k.rfind("_")]  # noqa: E203

            if setting not in plugins_settings or "multiple" not in plugins_settings[setting]:
                continue

            if k not in variables:
                variables[k] = plugins_settings[setting]["default"]

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
        for i, service in enumerate(deepcopy(services)):
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service["SERVER_NAME"] in server_name_splitted:
                if changed_server_name and service["SERVER_NAME"].split(" ")[0] != old_server_name_splitted[0]:
                    return f"Service {service['SERVER_NAME'].split(' ')[0]} already exists.", 1
                services.pop(i)
            elif changed_server_name and (service["SERVER_NAME"] == old_server_name or service["SERVER_NAME"] in old_server_name_splitted):
                services.pop(i)

        services.append(variables | {"IS_DRAFT": "yes" if is_draft else "no"})
        config = self.get_config(methods=False)

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
        ret = self.gen_conf(
            self.get_config(methods=False) | variables, self.get_services(methods=False), check_changes=check_changes, override_method=override_method
        )
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
