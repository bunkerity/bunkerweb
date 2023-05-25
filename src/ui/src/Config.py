#!/usr/bin/python3

from copy import deepcopy
from os import sep
from os.path import join
from flask import flash
from json import loads as json_loads
from pathlib import Path
from re import search as re_search
from subprocess import run, DEVNULL, STDOUT
from typing import List, Tuple
from uuid import uuid4


class Config:
    def __init__(self, db) -> None:
        self.__settings = json_loads(
            Path(sep, "usr", "share", "bunkerweb", "settings.json").read_text()
        )
        self.__db = db

    def __dict_to_env(self, filename: str, variables: dict) -> None:
        """Converts the content of a dict into an env file

        Parameters
        ----------
        filename : str
            The path to save the env file
        variables : dict
            The dict to convert to env file
        """
        Path(filename).write_text(
            "\n".join(f"{k}={variables[k]}" for k in sorted(variables))
        )

    def __gen_conf(self, global_conf: dict, services_conf: list[dict]) -> None:
        """Generates the nginx configuration file from the given configuration

        Parameters
        ----------
        variables : dict
            The configuration to add to the file

        Raises
        ------
        Exception
            If an error occurred during the generation of the configuration file, raises this exception
        """
        conf = deepcopy(global_conf)

        servers = []
        plugins_settings = self.get_plugins_settings()
        for service in services_conf:
            server_name = service["SERVER_NAME"].split(" ")[0]
            for k in service:
                key_without_server_name = k.replace(f"{server_name}_", "")
                if (
                    plugins_settings[key_without_server_name]["context"] != "global"
                    if key_without_server_name in plugins_settings
                    else True
                ):
                    if not k.startswith(server_name) or k in plugins_settings:
                        conf[f"{server_name}_{k}"] = service[k]
                    else:
                        conf[k] = service[k]

            servers.append(server_name)

        conf["SERVER_NAME"] = " ".join(servers)
        env_file = Path(sep, "tmp", f"{uuid4()}.env")
        self.__dict_to_env(env_file, conf)
        proc = run(
            [
                "python3",
                join(sep, "usr", "share", "bunkerweb", "gen", "save_config.py"),
                "--variables",
                str(env_file),
                "--method",
                "ui",
            ],
            stdin=DEVNULL,
            stderr=STDOUT,
        )

        if proc.returncode != 0:
            raise Exception(f"Error from generator (return code = {proc.returncode})")

        env_file.unlink()

    def get_plugins_settings(self) -> dict:
        return {
            **{k: v for x in self.get_plugins() for k, v in x["settings"].items()},
            **self.__settings,
        }

    def get_plugins(
        self, *, external: bool = False, with_data: bool = False
    ) -> List[dict]:
        plugins = self.__db.get_plugins(external=external, with_data=with_data)
        plugins.sort(key=lambda x: x["name"])

        general_plugin = None
        for plugin in plugins.copy():
            if plugin["id"] == "general":
                general_plugin = plugin
                plugins.remove(plugin)
                break

        if general_plugin:
            plugins.insert(0, general_plugin)

        return plugins

    def get_settings(self) -> dict:
        return self.__settings

    def get_config(self, methods: bool = True) -> dict:
        """Get the nginx variables env file and returns it as a dict

        Returns
        -------
        dict
            The nginx variables env file as a dict
        """
        return self.__db.get_config(methods=methods)

    def get_services(self, methods: bool = True) -> list[dict]:
        """Get nginx's services

        Returns
        -------
        list
            The services
        """
        return self.__db.get_services_settings(methods=methods)

    def check_variables(self, variables: dict, _global: bool = False) -> int:
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
        error = 0
        plugins_settings = self.get_plugins_settings()
        for k, v in variables.items():
            check = False

            if k in plugins_settings:
                if _global ^ (plugins_settings[k]["context"] == "global"):
                    error = 1
                    flash(f"Variable {k} is not valid.", "error")
                    continue

                setting = k
            else:
                setting = k[0 : k.rfind("_")]
                if (
                    setting not in plugins_settings
                    or "multiple" not in plugins_settings[setting]
                ):
                    error = 1
                    flash(f"Variable {k} is not valid.", "error")
                    continue

            if not (
                _global ^ (plugins_settings[setting]["context"] == "global")
            ) and re_search(plugins_settings[setting]["regex"], v):
                check = True

            if not check:
                error = 1
                flash(f"Variable {k} is not valid.", "error")
                continue

        return error

    def reload_config(self) -> None:
        self.__gen_conf(
            self.get_config(methods=False), self.get_services(methods=False)
        )

    def new_service(self, variables: dict, edit: bool = False) -> Tuple[str, int]:
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
        services = self.get_services(methods=False)
        for i, service in enumerate(services):
            if service["SERVER_NAME"] == variables["SERVER_NAME"] or service[
                "SERVER_NAME"
            ] in variables["SERVER_NAME"].split(" "):
                if not edit:
                    return (
                        f"Service {service['SERVER_NAME'].split(' ')[0]} already exists.",
                        1,
                    )

                services.pop(i)

        services.append(variables)
        self.__gen_conf(self.get_config(methods=False), services)
        return (
            f"Configuration for {variables['SERVER_NAME'].split(' ')[0]} has been generated.",
            0,
        )

    def edit_service(self, old_server_name: str, variables: dict) -> Tuple[str, int]:
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
        message, error = self.delete_service(old_server_name)

        if error:
            return message, error

        message, error = self.new_service(variables, edit=True)

        if error:
            return message, error

        return (
            f"Configuration for {old_server_name.split(' ')[0]} has been edited.",
            error,
        )

    def edit_global_conf(self, variables: dict) -> str:
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
        self.__gen_conf(
            self.get_config(methods=False) | variables, self.get_services(methods=False)
        )
        return f"The global configuration has been edited."

    def delete_service(self, service_name: str) -> Tuple[str, int]:
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
        services = self.get_services(methods=False)
        new_services = []
        found = False

        for service in services:
            if service["SERVER_NAME"].split(" ")[0] == service_name:
                found = True
            else:
                new_services.append(service)

        if not found:
            return f"Can't delete missing {service_name} configuration.", 1

        full_env["SERVER_NAME"] = " ".join(
            [s for s in full_env["SERVER_NAME"].split(" ") if s != service_name]
        )

        new_env = deepcopy(full_env)

        for k in full_env:
            if k.startswith(service_name):
                new_env.pop(k)

                for service in new_services:
                    if k in service:
                        service.pop(k)

        self.__gen_conf(new_env, new_services)
        return f"Configuration for {service_name} has been deleted.", 0
