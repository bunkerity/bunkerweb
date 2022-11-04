from os import getenv
from time import sleep

from ConfigCaller import ConfigCaller
from Database import Database
from logger import setup_logger


class Config(ConfigCaller):
    def __init__(self, ctrl_type, lock=None):
        ConfigCaller.__init__(self)
        self.__ctrl_type = ctrl_type
        self.__lock = lock
        self.__logger = setup_logger("Config", getenv("LOG_LEVEL", "INFO"))
        self._db = None
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

    def apply(self, instances, services, configs=None) -> bool:

        success = True

        # update values
        self.__instances = instances
        self.__services = services
        self.__configs = configs
        self.__config = self.__get_full_env()

        if self._db is None:
            self._db = Database(
                self.__logger,
                sqlalchemy_string=self.__config.get("DATABASE_URI", None),
                bw_integration="Kubernetes"
                if self.__config.get("KUBERNETES_MODE", "no") == "yes"
                else "Cluster",
            )

            while not self._db.is_initialized():
                self.__logger.warning(
                    "Database is not initialized, retrying in 5 seconds ...",
                )
                sleep(5)

        custom_configs = []
        for config_type in self.__configs:
            for file, data in self.__configs[config_type].items():
                exploded = file.split("/")
                custom_configs.append(
                    {
                        "value": data,
                        "exploded": [
                            exploded[0],
                            config_type,
                            exploded[1].replace(".conf", ""),
                        ],
                    }
                )

        # save config to database
        ret = self._db.save_config(self.__config, "autoconf")
        if ret:
            success = False
            self.__logger.error(
                f"Can't save autoconf config in database: {ret}",
            )

        # save custom configs to database
        ret = self._db.save_custom_configs(custom_configs, "autoconf")
        if ret:
            success = False
            self.__logger.error(
                f"Can't save autoconf custom configs in database: {ret}",
            )

        return success
