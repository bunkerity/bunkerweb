from logging import Logger
from traceback import format_exc
from subprocess import run, DEVNULL, STDOUT
from glob import glob
from shutil import rmtree
from os import getenv, makedirs, remove, listdir
from os.path import dirname, isdir
from typing import Tuple

from API import API
from ApiCaller import ApiCaller
from ConfigCaller import ConfigCaller
from Database import Database
from logger import setup_logger


class Config(ApiCaller, ConfigCaller):
    def __init__(self, ctrl_type, lock=None):
        ApiCaller.__init__(self)
        ConfigCaller.__init__(self)
        self.__ctrl_type = ctrl_type
        self.__lock = lock
        self.__logger = setup_logger("Config", getenv("LOG_LEVEL", "INFO"))
        self.__db = None
        self.__instances = []
        self.__services = []
        self.__configs = []
        self.__config = {}

    def __get_full_env(self) -> dict:
        env_instances = {}
        for instance in self.__instances:
            for variable, value in instance["env"].items():
                env_instances[variable] = value
        env_services = {}
        if not "SERVER_NAME" in env_instances:
            env_instances["SERVER_NAME"] = ""
        for service in self.__services:
            for variable, value in service.items():
                env_services[
                    f"{service['SERVER_NAME'].split(' ')[0]}_{variable}"
                ] = value
            if env_instances["SERVER_NAME"] != "":
                env_instances["SERVER_NAME"] += " "
            env_instances["SERVER_NAME"] += service["SERVER_NAME"].split(" ")[0]
        return self._full_env(env_instances, env_services)

    def update_needed(self, instances, services, configs=None) -> bool:
        if instances != self.__instances:
            return True
        if services != self.__services:
            return True
        if not configs is None and configs != self.__configs:
            return True
        return False

    def __get_config(self) -> dict:
        config = {}
        # extract instances variables
        for instance in self.__instances:
            for variable, value in instance["env"].items():
                config[variable] = value
        # extract services variables
        server_names = []
        for service in self.__services:
            first_server = service["SERVER_NAME"].split(" ")[0]
            if not first_server in server_names:
                server_names.append(first_server)
            for variable, value in service.items():
                config[f"{first_server}_{variable}"] = value
        config["SERVER_NAME"] = " ".join(server_names)
        return config

    def __get_apis(self) -> list:
        apis = []
        for instance in self.__instances:
            endpoint = f"http://{instance['hostname']}:{instance['env'].get('API_HTTP_PORT', '5000')}"
            host = instance["env"].get("API_SERVER_NAME", "bwapi")
            apis.append(API(endpoint, host=host))
        return apis

    def __write_configs(self) -> Tuple[bool, list]:
        ret = True
        custom_configs = []
        for config_type in self.__configs:
            for file, data in self.__configs[config_type].items():
                path = f"/data/configs/{config_type}/{file}"
                if not path.endswith(".conf"):
                    path += ".conf"
                makedirs(dirname(path), exist_ok=True)
                try:
                    mode = "w"
                    if type(data) is bytes:
                        mode = "wb"

                    with open(path, mode) as f:
                        f.write(data)

                    exploded = file.split("/")
                    custom_configs.append(
                        {
                            "value": data if mode == "w" else data.decode("utf-8"),
                            "exploded": [exploded[0], config_type, exploded[1]],
                        }
                    )
                except:
                    print(format_exc())
                    self.__logger.error(f"Can't save file {path}")
                    ret = False
        return ret, custom_configs

    def __remove_configs(self) -> bool:
        ret = True
        for config_type in self.__configs:
            for file, _ in self.__configs[config_type].items():
                path = f"/data/configs/{config_type}/{file}"
                if not path.endswith(".conf"):
                    path += ".conf"
                try:
                    remove(path)
                except:
                    print(format_exc())
                    self.__logger.error(f"Can't remove file {path}")
                    ret = False
        check_empty_dirs = []
        for _type in ["server-http", "modsec", "modsec-crs"]:
            check_empty_dirs.extend(glob(f"/data/configs/{type}/*"))
        for check_empty_dir in check_empty_dirs:
            if isdir(check_empty_dir) and len(listdir(check_empty_dir)) == 0:
                try:
                    rmtree(check_empty_dir)
                except:
                    print(format_exc())
                    self.__logger.error(f"Can't remove directory {check_empty_dir}")
                    ret = False
        return ret

    def apply(self, instances, services, configs=None) -> bool:

        success = True

        # remove old autoconf configs if it exists
        if self.__configs:
            ret = self.__remove_configs()
            if not ret:
                success = False
                self.__logger.error(
                    "removing custom configs failed, configuration will not work as expected...",
                )

        # update values
        self.__instances = instances
        self.__services = services
        self.__configs = configs
        self.__config = self.__get_full_env()
        if self.__db is None:
            self.__db = Database(
                self.__logger, sqlalchemy_string=self.__config.get("DATABASE_URI", None)
            )
        self._set_apis(self.__get_apis())

        # write configs
        if configs != None:
            ret = self.__db.save_config(self.__config, "autoconf")
            if ret:
                self.__logger.error(
                    f"Can't save autoconf config in database: {ret}",
                )

            ret, custom_configs = self.__write_configs()
            if not ret:
                success = False
                self.__logger.error(
                    "saving custom configs failed, configuration will not work as expected...",
                )

            ret = self.__db.save_custom_configs(custom_configs, "autoconf")
            if ret:
                self.__logger.error(
                    f"Can't save autoconf custom configs in database: {ret}",
                )
        else:
            ret = self.__db.save_config({}, "autoconf")
            if ret:
                self.__logger.error(
                    f"Can't remove autoconf config from the database: {ret}",
                )

        # get env
        env = self.__get_full_env()

        # run jobs once
        i = 1
        for instance in self.__instances:
            endpoint = f"http://{instance['hostname']}:{instance['env'].get('API_HTTP_PORT', '5000')}"
            host = instance["env"].get("API_SERVER_NAME", "bwapi")
            env[f"CLUSTER_INSTANCE_{i}"] = f"{endpoint} {host}"
            i += 1

        # write config to /tmp/variables.env
        with open("/tmp/variables.env", "w") as f:
            for variable, value in self.__config.items():
                f.write(f"{variable}={value}\n")

        # run the generator
        cmd = f"python /opt/bunkerweb/gen/main.py --settings /opt/bunkerweb/settings.json --templates /opt/bunkerweb/confs --output /etc/nginx --variables /tmp/variables.env --method autoconf"
        proc = run(cmd.split(" "), stdin=DEVNULL, stderr=STDOUT)
        if proc.returncode != 0:
            success = False
            self.__logger.error(
                "config generator failed, configuration will not work as expected...",
            )
        # cmd = "chown -R root:101 /etc/nginx"
        # run(cmd.split(" "), stdin=DEVNULL, stdout=DEVNULL, stderr=STDOUT)
        # cmd = "chmod -R 770 /etc/nginx"
        # run(cmd.split(" "), stdin=DEVNULL, stdout=DEVNULL, stderr=STDOUT)

        # send nginx configs
        # send data folder
        # reload nginx
        ret = self._send_files("/etc/nginx", "/confs")
        if not ret:
            success = False
            self.__logger.error(
                "sending nginx configs failed, configuration will not work as expected...",
            )
        ret = self._send_files("/data/configs", "/custom_configs")
        if not ret:
            success = False
            self.__logger.error(
                "sending custom configs failed, configuration will not work as expected...",
            )
        ret = self._send_to_apis("POST", "/reload")
        if not ret:
            success = False
            self.__logger.error(
                "reload failed, configuration will not work as expected...",
            )

        return success
