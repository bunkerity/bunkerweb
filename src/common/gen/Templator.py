#!/usr/bin/python3

from glob import glob
from importlib import import_module
from os.path import basename, join
from pathlib import Path
from random import choice
from string import ascii_letters, digits
from sys import path as sys_path
from typing import Any, Dict, List, Optional

if join("usr", "share", "bunkerweb", "deps", "python") in sys_path:
    sys_path.append(join("usr", "share", "bunkerweb", "deps", "python"))

from jinja2 import Environment, FileSystemLoader


class Templator:
    def __init__(
        self,
        templates: str,
        core: str,
        plugins: str,
        output: str,
        target: str,
        config: Dict[str, Any],
    ):
        self.__templates = templates
        self.__core = core
        self.__plugins = plugins
        self.__output = output
        self.__target = target
        self.__config = config
        self.__jinja_env = self.__load_jinja_env()

    def render(self):
        self.__render_global()
        servers = [self.__config.get("SERVER_NAME", "").strip()]
        if self.__config.get("MULTISITE", "no") == "yes":
            servers = self.__config.get("SERVER_NAME", "").strip().split(" ")
        for server in servers:
            self.__render_server(server)

    def __load_jinja_env(self) -> Environment:
        searchpath = [self.__templates]
        for subpath in glob(join(self.__core, "*")) + glob(join(self.__plugins, "*")):
            if Path(subpath).is_dir():
                searchpath.append(join(subpath, "confs"))
        return Environment(
            loader=FileSystemLoader(searchpath=searchpath),
            lstrip_blocks=True,
            trim_blocks=True,
        )

    def __find_templates(self, contexts) -> List[str]:
        templates = []
        for template in self.__jinja_env.list_templates():
            if "global" in contexts and "/" not in template:
                templates.append(template)
                continue
            for context in contexts:
                if template.startswith(context):
                    templates.append(template)
        return templates

    def __write_config(
        self, subpath: Optional[str] = None, config: Optional[Dict[str, Any]] = None
    ):
        real_path = Path(self.__output, subpath or "", "variables.env")
        real_path.parent.mkdir(parents=True, exist_ok=True)
        real_path.write_text(
            "\n".join(f"{k}={v}" for k, v in (config or self.__config).items())
        )

    def __render_global(self):
        self.__write_config()
        templates = self.__find_templates(
            ["global", "http", "stream", "default-server-http"]
        )
        for template in templates:
            self.__render_template(template)

    def __render_server(self, server: str):
        templates = self.__find_templates(
            ["modsec", "modsec-crs", "server-http", "server-stream"]
        )
        if self.__config.get("MULTISITE", "no") == "yes":
            config = self.__config.copy()
            for variable, value in self.__config.items():
                if variable.startswith(f"{server}_"):
                    config[variable.replace(f"{server}_", "", 1)] = value
            self.__write_config(subpath=server, config=config)

        for template in templates:
            subpath = None
            config = None
            name = None
            if self.__config.get("MULTISITE", "no") == "yes":
                subpath = server
                config = self.__config.copy()
                for variable, value in self.__config.items():
                    if variable.startswith(f"{server}_"):
                        config[variable.replace(f"{server}_", "", 1)] = value
                config["NGINX_PREFIX"] = join(self.__target, server) + "/"
                server_key = f"{server}_SERVER_NAME"
                if server_key not in self.__config:
                    config["SERVER_NAME"] = server

            for root_conf in (
                "server.conf",
                "access-lua.conf",
                "init-lua.conf",
                "log-lua.conf",
                "set-lua.conf",
                "log-stream-lua.conf",
                "preread-stream-lua.conf",
                "server-stream.conf",
            ):
                if template.endswith(root_conf):
                    name = basename(template)
                    break
            self.__render_template(template, subpath=subpath, config=config, name=name)

    def __render_template(
        self,
        template: str,
        subpath: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ):
        # Get real config and output folder in case it's a server config and we are in multisite mode
        real_config = config.copy() if config else self.__config.copy()
        real_config["all"] = real_config.copy()
        real_config["import"] = import_module
        real_config["is_custom_conf"] = Templator.is_custom_conf
        real_config["has_variable"] = Templator.has_variable
        real_config["random"] = Templator.random
        real_config["read_lines"] = Templator.read_lines
        real_path = Path(self.__output, subpath or "", name or template)
        jinja_template = self.__jinja_env.get_template(template)
        real_path.parent.mkdir(parents=True, exist_ok=True)
        real_path.write_text(jinja_template.render(real_config))

    @staticmethod
    def is_custom_conf(path: str) -> bool:
        return bool(glob(join(path, "*.conf")))

    @staticmethod
    def has_variable(all_vars: Dict[str, Any], variable: str, value: Any) -> bool:
        if all_vars.get(variable) == value:
            return True
        elif all_vars.get("MULTISITE", "no") == "yes":
            for server_name in all_vars["SERVER_NAME"].strip().split(" "):
                if all_vars.get(f"{server_name}_{variable}") == value:
                    return True
        return False

    @staticmethod
    def random(nb: int) -> str:
        characters = ascii_letters + digits
        return "".join(choice(characters) for _ in range(nb))

    @staticmethod
    def read_lines(file: str) -> List[str]:
        try:
            return Path(file).read_text().splitlines()
        except:
            return []
